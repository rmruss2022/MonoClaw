#!/usr/bin/env bash
# Hardened integration test for the thermostat/climate integration.
# Stands up a mock ESPHome web_server endpoint so the real success paths (reachable
# device → state updates) are exercised, then checks onboarding-to-a-room, control,
# input hardening, /devices merge, and agent/scene → real-primary sync (no-clobber).
#
# Usage: HUB=http://127.0.0.1:4700 ./test-climate.sh   (hub must be running new code)
set -u
HUB="${HUB:-http://127.0.0.1:4700}"
MOCK_PORT=4790
PASS=0; FAIL=0
ok(){ echo "  ✓ $1"; PASS=$((PASS+1)); }
bad(){ echo "  ✗ $1"; FAIL=$((FAIL+1)); }
jq(){ python3 -c "import sys,json;d=json.load(sys.stdin);print($1)" 2>/dev/null; }
cmd(){ curl -s -X POST "$HUB/climate/command" -H 'Content-Type: application/json' -d "$1"; }

# --- mock ESPHome endpoint: 200 to everything ---
python3 - "$MOCK_PORT" >/dev/null 2>&1 <<'PY' &
import sys,http.server,socketserver
class H(http.server.BaseHTTPRequestHandler):
    def _ok(self):self.send_response(200);self.end_headers();self.wfile.write(b'{}')
    def do_POST(self):self._ok()
    def do_GET(self):self._ok()
    def log_message(self,*a):pass
socketserver.TCPServer.allow_reuse_address=True
socketserver.TCPServer(("127.0.0.1",int(sys.argv[1])),H).serve_forever()
PY
MOCK_PID=$!
cleanup(){ curl -s -X POST "$HUB/climate/command" -H 'Content-Type: application/json' -d "{\"cmd\":\"remove-thermostat\",\"id\":\"$TID\"}" >/dev/null 2>&1; kill $MOCK_PID 2>/dev/null; }
trap cleanup EXIT
sleep 1

echo "1) Onboard ESPHome thermostat to a room (Bedroom)"
cmd '{"cmd":"onboard-thermostat","device":{"name":"Test Stat","backend":"esphome","address":"127.0.0.1","port":4790,"entity":"hvac"},"room":"Bedroom"}' >/dev/null
TID=""
for i in $(seq 1 8); do
  S=$(curl -s "$HUB/climate/state")
  TID=$(echo "$S" | jq "next((t['id'] for t in d['thermostats'] if t.get('real') and t['name']=='Test Stat'),'')")
  ST=$(echo "$S" | jq "next((t['status'] for t in d['thermostats'] if t['id']=='$TID'),'')")
  [ "$ST" = "connected" ] && break; sleep 1
done
[ -n "$TID" ] && ok "onboarded (id=$TID)" || { bad "onboard failed"; exit 1; }
RM=$(curl -s "$HUB/climate/state" | jq "next((t['room'] for t in d['thermostats'] if t['id']=='$TID'),'')")
[ "$RM" = "Bedroom" ] && ok "assigned to room Bedroom" || bad "room wrong: $RM"
[ "$ST" = "connected" ] && ok "reachable → connected" || bad "status: $ST"

echo "2) Control: set-temp / set-mode reflect (reachable device)"
cmd "{\"cmd\":\"set-temp\",\"id\":\"$TID\",\"targetF\":72}" >/dev/null
T=$(curl -s "$HUB/climate/state" | jq "next((t['targetF'] for t in d['thermostats'] if t['id']=='$TID'),0)")
[ "$T" = "72" ] && ok "set-temp 72 applied" || bad "target=$T"
cmd "{\"cmd\":\"set-mode\",\"id\":\"$TID\",\"mode\":\"heat\"}" >/dev/null
M=$(curl -s "$HUB/climate/state" | jq "next((t['mode'] for t in d['thermostats'] if t['id']=='$TID'),'')")
A=$(curl -s "$HUB/climate/state" | jq "next((t['action'] for t in d['thermostats'] if t['id']=='$TID'),'')")
[ "$M" = "heat" ] && ok "set-mode heat applied" || bad "mode=$M"
[ "$A" = "heating" ] && ok "action mode-aware (heating, target>current)" || bad "action=$A"

echo "3) Hardening: invalid inputs rejected/clamped"
H=$(cmd "{\"cmd\":\"set-mode\",\"id\":\"$TID\",\"mode\":\"banana\"}" | jq "d.get('hint','')")
echo "$H" | grep -qi invalid && ok "bad mode rejected ($H)" || bad "bad mode not rejected: $H"
M=$(curl -s "$HUB/climate/state" | jq "next((t['mode'] for t in d['thermostats'] if t['id']=='$TID'),'')")
[ "$M" = "heat" ] && ok "mode unchanged after bad input" || bad "mode corrupted: $M"
cmd "{\"cmd\":\"set-temp\",\"id\":\"$TID\",\"targetF\":999}" >/dev/null
T=$(curl -s "$HUB/climate/state" | jq "next((t['targetF'] for t in d['thermostats'] if t['id']=='$TID'),0)")
[ "$T" = "90" ] && ok "out-of-range temp clamped to 90" || bad "clamp failed: $T"
H=$(cmd "{\"cmd\":\"set-temp\",\"id\":\"$TID\",\"targetF\":\"abc\"}" | jq "d.get('hint','')")
echo "$H" | grep -qi invalid && ok "NaN temp rejected ($H)" || bad "NaN not rejected: $H"

echo "4) /devices merge: real thermostat shown, mock hidden"
D=$(curl -s "$HUB/devices")
echo "$D" | jq "any(x['id']=='$TID' for x in d['devices'])" | grep -qi true && ok "real thermostat in /devices" || bad "not in /devices"
echo "$D" | jq "any(x['id']=='thermostat_main' for x in d['devices'])" | grep -qi false && ok "mock thermostat hidden" || bad "mock still shown"

echo "5) No-clobber: direct dial change survives reconcile"
cmd "{\"cmd\":\"set-temp\",\"id\":\"$TID\",\"targetF\":68}" >/dev/null
sleep 6
T=$(curl -s "$HUB/climate/state" | jq "next((t['targetF'] for t in d['thermostats'] if t['id']=='$TID'),0)")
[ "$T" = "68" ] && ok "dial value 68 not clobbered by reconciler" || bad "clobbered to $T"

echo "6) Scene → real primary sync"
# establish a distinct baseline (good_morning) and let the reconciler adopt/push it,
# so the following good_night is a real delta regardless of prior mock state
curl -s -X POST "$HUB/scenes" -H 'Content-Type: application/json' -d '{"id":"good_morning"}' >/dev/null
sleep 5
curl -s -X POST "$HUB/scenes" -H 'Content-Type: application/json' -d '{"id":"good_night"}' >/dev/null
MT=$(curl -s "$HUB/home" | jq "next((x['raw']['target'] for x in d['devices'] if x['id']=='thermostat_main'),0)")
SYNCED=0
for i in $(seq 1 10); do
  T=$(curl -s "$HUB/climate/state" | jq "next((t['targetF'] for t in d['thermostats'] if t['id']=='$TID'),0)")
  [ "$T" = "$MT" ] && { SYNCED=1; break; }; sleep 1
done
[ "$SYNCED" = "1" ] && ok "scene target ($MT) mirrored to real thermostat" || bad "sync failed (real=$T mock=$MT)"

echo "7) Reconnect + remove"
R=$(cmd "{\"cmd\":\"reconnect-thermostat\",\"id\":\"$TID\"}" | jq "d.get('hint','')")
echo "$R" | grep -qi connected && ok "reconnect → connected" || bad "reconnect: $R"
cmd "{\"cmd\":\"remove-thermostat\",\"id\":\"$TID\"}" >/dev/null
curl -s "$HUB/climate/state" | jq "any(t['id']=='$TID' for t in d['thermostats'])" | grep -qi false && ok "removed from state" || bad "still present"
curl -s "$HUB/devices" | jq "any(x['id']=='thermostat_main' for x in d['devices'])" | grep -qi true && ok "mock reappears after remove" || bad "mock missing after remove"
TID=""  # already removed; skip trap remove

echo
echo "RESULT: $PASS passed, $FAIL failed"
[ "$FAIL" = "0" ]

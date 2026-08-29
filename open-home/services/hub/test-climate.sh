#!/usr/bin/env bash
# Hardened integration + device-contract test for the thermostat/climate integration.
# Stands up a FAITHFUL ESPHome web_server climate emulator (test/esphome-thermostat.py)
# that speaks the real REST contract — so it catches device-contract bugs a
# rubber-stamp 200 mock hides: heat_cool mode mapping, target_temperature_low/high
# setpoints, and GET state read-back. Then checks onboarding-to-a-room, control,
# input hardening, /devices merge, and agent/scene → real-primary sync (no-clobber).
#
# Usage: HUB=http://127.0.0.1:4700 ./test-climate.sh   (hub must be running new code)
set -u
HUB="${HUB:-http://127.0.0.1:4700}"
MOCK_PORT=4790
HERE="$(cd "$(dirname "$0")" && pwd)"
PASS=0; FAIL=0
ok(){ echo "  ✓ $1"; PASS=$((PASS+1)); }
bad(){ echo "  ✗ $1"; FAIL=$((FAIL+1)); }
jq(){ python3 -c "import sys,json;d=json.load(sys.stdin);print($1)" 2>/dev/null; }
cmd(){ curl -s -X POST "$HUB/climate/command" -H 'Content-Type: application/json' -d "$1"; }

# --- faithful ESPHome climate emulator (real contract, not a 200-stamp) ---
python3 "$HERE/test/esphome-thermostat.py" "$MOCK_PORT" hvac >/dev/null 2>&1 &
MOCK_PID=$!
cleanup(){ curl -s -X POST "$HUB/climate/command" -H 'Content-Type: application/json' -d "{\"cmd\":\"remove-thermostat\",\"id\":\"$TID\"}" >/dev/null 2>&1; kill $MOCK_PID 2>/dev/null; }
trap cleanup EXIT
sleep 1

echo "1) Onboard ESPHome thermostat to a room (Bedroom) + read real state back"
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
[ "$ST" = "connected" ] && ok "reachable → connected (via real climate GET)" || bad "status: $ST"
# device truth is 20.0°C (=68°F), mode heat — NOT our optimistic 70/auto default
CUR=$(curl -s "$HUB/climate/state" | jq "next((t['currentF'] for t in d['thermostats'] if t['id']=='$TID'),0)")
[ "$CUR" = "68" ] && ok "read-back: currentF=68 from device (not optimistic 70)" || bad "read-back currentF=$CUR (expected 68)"
M=$(curl -s "$HUB/climate/state" | jq "next((t['mode'] for t in d['thermostats'] if t['id']=='$TID'),'')")
[ "$M" = "heat" ] && ok "read-back: mode adopted from device (heat)" || bad "read-back mode=$M (expected heat)"

echo "2) Contract: auto→heat_cool mapping + two-setpoint (low/high) band"
# set-mode auto: the hub must send mode=heat_cool (a bare 'auto' would be 400'd by the
# device). Success + read-back mapping heat_cool→auto proves the mapping fix.
cmd "{\"cmd\":\"set-mode\",\"id\":\"$TID\",\"mode\":\"auto\"}" >/dev/null
M=$(curl -s "$HUB/climate/state" | jq "next((t['mode'] for t in d['thermostats'] if t['id']=='$TID'),'')")
[ "$M" = "auto" ] && ok "set-mode auto → device accepted heat_cool (mapping ok)" || bad "mode=$M (auto→heat_cool mapping broken)"
# set-temp 74 in heat_cool: hub must send target_temperature_low/high; the device stores
# the band and the read-back midpoint returns 74. A lone target_temperature would be
# ignored by the device → stale read-back → this fails.
cmd "{\"cmd\":\"set-temp\",\"id\":\"$TID\",\"targetF\":74}" >/dev/null
T=$(curl -s "$HUB/climate/state" | jq "next((t['targetF'] for t in d['thermostats'] if t['id']=='$TID'),0)")
[ "$T" = "74" ] && ok "set-temp 74 via low/high band round-trips to 74" || bad "target=$T (heat_cool setpoints broken)"
A=$(curl -s "$HUB/climate/state" | jq "next((t['action'] for t in d['thermostats'] if t['id']=='$TID'),'')")
[ "$A" = "heating" ] && ok "action mode-aware (heating, 74>68)" || bad "action=$A"
# single-setpoint path: switch to heat and confirm target_temperature round-trips
cmd "{\"cmd\":\"set-mode\",\"id\":\"$TID\",\"mode\":\"heat\"}" >/dev/null
cmd "{\"cmd\":\"set-temp\",\"id\":\"$TID\",\"targetF\":72}" >/dev/null
T=$(curl -s "$HUB/climate/state" | jq "next((t['targetF'] for t in d['thermostats'] if t['id']=='$TID'),0)")
[ "$T" = "72" ] && ok "heat mode: single target_temperature round-trips to 72" || bad "target=$T (single setpoint broken)"

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

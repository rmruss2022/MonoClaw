#!/usr/bin/env python3
"""Faithful ESPHome web_server *climate* emulator — a real device on the wire.

Unlike a "return 200 to everything" mock, this speaks the actual ESPHome
web_server REST contract (https://esphome.io/web-api/) so it can catch the
device-contract bugs a rubber-stamp mock hides:

  GET  /climate/<entity>            → JSON state, matching the real payload:
         { "id":"climate-<entity>", "mode":"heat_cool", "current_temperature":20.0,
           "target_temperature_low":19.0, "target_temperature_high":23.0 }
       single-setpoint modes return "target_temperature" instead of the low/high pair.

  POST /climate/<entity>/set?<params>
         mode=off|heat|cool|heat_cool|fan_only|dry     (case-insensitive)
         target_temperature=<°C>                       (single-setpoint modes)
         target_temperature_low=<°C>&target_temperature_high=<°C>  (heat_cool)

Deliberately strict — like a device that only advertises these traits:
  * an unsupported mode (e.g. the legacy "auto") → 400. This proves the hub maps
    our app "auto" to "heat_cool" and never sends a bare "auto".
  * setpoints are stored per the *effective* mode: in heat_cool a lone
    target_temperature is ignored (the band is unchanged), and in single modes
    the low/high pair is ignored. So a hub sending the wrong field shows up as a
    stale read-back — no false green.

Temperatures on the wire are °C (as ESPHome emits); the hub converts to/from °F.

Usage: esphome-thermostat.py <port> [entity]   (default entity: hvac)
"""
import sys, os, json, time, http.server, socketserver
from urllib.parse import urlparse, parse_qs

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 4790
ENTITY = sys.argv[2] if len(sys.argv) > 2 else "hvac"
# Set EMU_LOG=1 to print each request (method, path, query) + resulting state to
# stderr — so an end-to-end walkthrough can see the exact wire format the hub sends.
LOG = os.environ.get("EMU_LOG") == "1"


def log(msg):
    if LOG:
        sys.stderr.write(f"[emu {time.strftime('%H:%M:%S')}] {msg}\n")
        sys.stderr.flush()

# Modes this "device" advertises. Note: no "auto" — a hub must send heat_cool.
SUPPORTED = {"off", "heat", "cool", "heat_cool", "fan_only", "dry"}

# Initial device truth (°C). 20.0°C ≈ 68°F room, heating to 21.0°C ≈ 70°F.
state = {
    "mode": "heat",
    "current_temperature": 20.0,
    "target_temperature": 21.0,      # used in single-setpoint modes
    "target_temperature_low": 19.0,  # used in heat_cool
    "target_temperature_high": 23.0,
}


def state_json():
    m = state["mode"]
    out = {"id": f"climate-{ENTITY}", "mode": m, "current_temperature": state["current_temperature"]}
    if m == "heat_cool":
        out["target_temperature_low"] = state["target_temperature_low"]
        out["target_temperature_high"] = state["target_temperature_high"]
    else:
        out["target_temperature"] = state["target_temperature"]
    return out


class H(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body=b"{}"):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urlparse(self.path)
        if p.path == f"/climate/{ENTITY}":
            body = json.dumps(state_json())
            log(f"GET  {p.path}  →  {body}")
            self._send(200, body.encode())
        else:
            log(f"GET  {p.path}  →  404")
            self._send(404, b'{"error":"not found"}')

    def do_POST(self):
        p = urlparse(self.path)
        # Debug-only hook (NOT part of the ESPHome contract): simulate the room
        # temperature changing so read-back can be demonstrated end-to-end.
        if p.path == "/debug/set":
            q = parse_qs(p.query)
            c = q.get("current_temperature", [None])[0]
            if c is not None:
                state["current_temperature"] = float(c)
                log(f"POST {p.path}?{p.query}  (debug: room now {c}°C)")
            return self._send(200, json.dumps(state_json()).encode())
        if p.path != f"/climate/{ENTITY}/set":
            log(f"POST {p.path}  →  404")
            return self._send(404, b'{"error":"not found"}')
        q = parse_qs(p.query)

        def num(key):
            v = q.get(key, [None])[0]
            return float(v) if v not in (None, "") else None

        # mode first: rejecting an unsupported mode is how a real device behaves.
        new_mode = (q.get("mode", [None])[0] or "").lower() or None
        if new_mode is not None:
            if new_mode not in SUPPORTED:
                log(f"POST {p.path}?{p.query}  →  400 REJECTED unsupported mode '{new_mode}'")
                return self._send(400, json.dumps({"error": f"unsupported mode {new_mode}"}).encode())
            state["mode"] = new_mode

        eff = state["mode"]
        if eff == "heat_cool":
            lo, hi = num("target_temperature_low"), num("target_temperature_high")
            if lo is not None:
                state["target_temperature_low"] = lo
            if hi is not None:
                state["target_temperature_high"] = hi
            # a lone target_temperature in heat_cool is intentionally ignored
        else:
            t = num("target_temperature")
            if t is not None:
                state["target_temperature"] = t
        body = json.dumps(state_json())
        log(f"POST {p.path}?{p.query}  →  200  {body}")
        self._send(200, body.encode())

    def log_message(self, *a):
        pass


socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", PORT), H) as srv:
    srv.serve_forever()

#!/usr/bin/env python3
"""
The Pi-side ring client: accelerometer in, gestures out, hub told.

    ring  --BLE a1 03 poll-->  gestures.Engine  --POST /ring/gesture-->  hub
                                                                          |
                                                            UDP --> voice client

`--simulate` runs synthetic samples through the REAL engine and the REAL hub
endpoints, so the entire chain can be proved before the ring exists. That is
deliberate: everything between the accelerometer and the speaker is testable
today, and the only unverified link should be the one that needs hardware.

    ./.venv/bin/python ring_client.py --simulate double_tap
    ./.venv/bin/python ring_client.py --simulate triple_tap
    ./.venv/bin/python ring_client.py --calibrate      # needs the ring
    ./.venv/bin/python ring_client.py                  # needs the ring
"""
from __future__ import annotations

import argparse
import asyncio
import math
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gestures import COUNTS_PER_G, Config, Engine, Gesture, Sample  # noqa: E402

HUB = os.environ.get("OPEN_HOME_URL", "http://127.0.0.1:4700").rstrip("/")
PASSWORD = os.environ.get("OPEN_HOME_PASSWORD", "")
RING_ADDRESS = os.environ.get("RING_ADDRESS", "")
RING_NAME = os.environ.get("RING_NAME", "R0")

# Protocol, from the audit (see AUDIT.md). These are the constants that matter
# and the reason the LEDs stay off.
SERVICE_UUID = "6e40fff0-b5a3-f393-e0a9-e50e24dcca9e"
RX_CHAR = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"   # we write here
TX_CHAR = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"   # we subscribe here
CMD_RAW_SENSOR = 0xA1
SUB_POLL_ONCE = 0x03      # one snapshot, PPG untouched, LEDs stay OFF
SUB_DISABLE_RAW = 0x02    # stop the raw block (and the LEDs) on the way out
ACCEL_SUBTYPE = 0x03      # notifications whose data[1] is this carry accel


def log(*a: object) -> None:
    print(f"[ring {time.strftime('%H:%M:%S')}]", *a, flush=True)


def build_packet(command: int, payload: bytes = b"") -> bytearray:
    """16 bytes, last one a checksum.

    The checksum is the LOW BYTE OF THE SUM of the first 15 — i.e. modulo 256.
    Both reference implementations do this (`& 255`, `& 0xFF`) and both
    DOCUMENT it as "modulus 255", which is wrong and would produce a packet the
    ring rejects. See AUDIT.md.
    """
    if len(payload) > 14:
        raise ValueError("payload too long for a 16-byte packet")
    pkt = bytearray(16)
    pkt[0] = command
    pkt[1:1 + len(payload)] = payload
    pkt[15] = sum(pkt[:15]) & 0xFF
    return pkt


def i16_be(hi: int, lo: int) -> int:
    v = (hi << 8) | lo
    return v - 0x10000 if v >= 0x8000 else v


def parse_accel(data: bytearray) -> tuple[float, float, float] | None:
    """Big-endian signed 16-bit per axis, ~8192 counts per g."""
    if len(data) < 8 or data[1] != ACCEL_SUBTYPE:
        return None
    return (float(i16_be(data[2], data[3])),
            float(i16_be(data[4], data[5])),
            float(i16_be(data[6], data[7])))


class Hub:
    def __init__(self) -> None:
        self.s = requests.Session()
        self.ok = True

    def login(self) -> None:
        if not PASSWORD:
            return
        try:
            r = self.s.post(f"{HUB}/login", data={"password": PASSWORD},
                            headers={"Accept": "application/json"}, timeout=8)
            tok = (r.json() or {}).get("token", "")
            if tok:
                self.s.cookies.set("oh_auth", tok)
        except Exception as e:
            log("hub login failed:", e)

    def post(self, path: str, body: dict) -> dict | None:
        for attempt in (1, 2):
            try:
                r = self.s.post(f"{HUB}{path}", json=body, timeout=8)
                if r.status_code == 401 and attempt == 1:
                    self.login()
                    continue
                self.ok = True
                return r.json() if r.content else {}
            except Exception as e:
                if self.ok:
                    log(f"POST {path} failed:", e)
                self.ok = False
                return None
        return None


def send_gesture(hub: Hub, g: Gesture) -> None:
    body: dict = {"kind": g.kind}
    if g.value is not None:
        body["value"] = g.value
    r = hub.post("/ring/gesture", body)
    did = (r or {}).get("did", "no response from the hub")
    extra = f" ({g.value:+.0f}°)" if g.value is not None else ""
    log(f"{g.kind}{extra} -> {did}")


# ------------------------------------------------------------- simulate ----
def synth(kind: str, hz: float = 50.0) -> list[Sample]:
    """Synthetic traces, same generator shape as the tests.

    50 Hz because that is what we measured as sufficient (12 Hz detects a
    double tap 10% of the time; see AUDIT.md). Using the real rate here means
    the simulation exercises the same regime the firmware will.
    """
    G = COUNTS_PER_G
    taps = {"tap": [1.0], "double_tap": [1.0, 1.18],
            "triple_tap": [1.0, 1.18, 1.36]}.get(kind, [1.0, 1.18])
    roll_to = 35.0 if kind == "music" else 0.0
    if kind == "music":
        taps = [1.0, 1.18]
    out = []
    for i in range(int(3.5 * hz)):
        t = i / hz
        ang = 0.0
        if roll_to and 1.8 < t < 2.8:
            ang = roll_to * (t - 1.8) / 1.0
        elif roll_to and t >= 2.8:
            ang = roll_to
        rad = math.radians(ang)
        z = G * math.cos(rad)
        y = G * math.sin(rad)
        for tp in taps:
            if abs(t - tp) <= 0.015:
                z += 4000.0
        out.append(Sample(0.0, y, z, t))
    return out


def simulate(kind: str) -> int:
    log(f"simulating {kind!r} through the real engine and the real hub")
    hub = Hub()
    hub.login()
    engine = Engine(lambda g: send_gesture(hub, g), Config())
    samples = synth(kind)
    for s in samples:
        engine.feed(s)
    engine.tick(samples[-1].t + 1.0)
    if not hub.ok:
        log("the hub was unreachable — the engine still ran; see above")
        return 1
    return 0


# ------------------------------------------------------------------ live ----
async def live(calibrate_only: bool = False) -> int:
    from bleak import BleakClient, BleakScanner

    log(f"looking for the ring (name contains {RING_NAME!r})...")
    addr = RING_ADDRESS
    if not addr:
        found = await BleakScanner.discover(timeout=10.0, return_adv=True)
        best = None
        for dev, adv in found.values():
            name = (adv.local_name or dev.name or "")
            if SERVICE_UUID in [u.lower() for u in (adv.service_uuids or [])] \
               or (RING_NAME and RING_NAME.lower() in name.lower()):
                if best is None or (adv.rssi or -999) > best[1]:
                    best = (dev.address, adv.rssi)
        if best is None:
            log("no ring found. If it is paired to a phone, the phone has it — "
                "a Colmi ring accepts one connection and stops advertising.")
            return 2
        addr, rssi = best
        log(f"found {addr} at {rssi} dBm")

    hub = Hub()
    hub.login()
    engine = Engine(lambda g: send_gesture(hub, g), Config())
    peak = {"mag": 0.0, "dev": 0.0}

    async with BleakClient(addr, timeout=20.0) as c:
        log("connected")
        got: list[tuple[float, float, float]] = []

        def on_notify(_sender, data: bytearray) -> None:
            a = parse_accel(data)
            if a:
                got.append(a)

        await c.start_notify(TX_CHAR, on_notify)
        request = build_packet(CMD_RAW_SENSOR, bytes([SUB_POLL_ONCE]))
        t0 = time.monotonic()
        n = 0
        try:
            while True:
                await c.write_gatt_char(RX_CHAR, request, response=False)
                await asyncio.sleep(0.02)
                while got:
                    x, y, z = got.pop(0)
                    n += 1
                    s = Sample(x, y, z, time.monotonic())
                    if calibrate_only:
                        mag = s.mag
                        dev = abs(mag - (engine.rest or mag))
                        peak["mag"] = max(peak["mag"], mag)
                        peak["dev"] = max(peak["dev"], dev)
                        rate = n / max(0.001, time.monotonic() - t0)
                        print(f"\r  mag {mag:8.0f}  dev {dev:7.0f}   "
                              f"peak dev {peak['dev']:7.0f}   {rate:5.1f} Hz  "
                              f"rest {engine.rest or 0:8.0f}", end="", flush=True)
                    engine.feed(s)
                engine.tick(time.monotonic())
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            print()
            log(f"stopping the raw block so the LEDs go off ({n} samples, "
                f"{n / max(0.001, time.monotonic() - t0):.1f} Hz)")
            if calibrate_only:
                log(f"PEAK DEVIATION WAS {peak['dev']:.0f} — set Config.jolt "
                    f"to about {peak['dev'] * 0.4:.0f} and release to "
                    f"{peak['dev'] * 0.2:.0f}")
            try:
                await c.write_gatt_char(
                    RX_CHAR, build_packet(CMD_RAW_SENSOR, bytes([SUB_DISABLE_RAW])),
                    response=False)
                await c.stop_notify(TX_CHAR)
            except Exception:
                pass
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--simulate", metavar="KIND", nargs="?", const="double_tap",
                    help="tap | double_tap | triple_tap | music")
    ap.add_argument("--calibrate", action="store_true",
                    help="print live magnitudes so you can set the thresholds")
    args = ap.parse_args()

    if args.simulate:
        return simulate(args.simulate)
    try:
        return asyncio.run(live(calibrate_only=args.calibrate))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

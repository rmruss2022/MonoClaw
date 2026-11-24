#!/usr/bin/env python3
"""
openhome ring bridge — a Colmi R02 as a sensor the house can read.

WHY THIS RUNS ON THE PI AND NOT THE PHONE
-----------------------------------------
A BLE peripheral like the R02 accepts ONE central at a time, and it stops
advertising entirely while connected. So "connect it to the phone and the Pi"
is not a thing that exists: it is either/or. Whoever connects first owns it.

Given that, the Pi should own it — it is always on, always home, and already
has BlueZ. The phone then gets ring data the same way it gets everything else,
through the hub's API, which also means the React Native app needs no BLE code
at all. The cost is that QRing must stay closed, or it will steal the ring back.

WHAT IT FEEDS THE HOUSE
-----------------------
1. ROOM PROXIMITY. The ring is a transmitter and the Pi is a receiver, which is
   the inverse of how proximity.ts was written (the phone reporting beacons it
   hears) — but the API fits unchanged. Each RECEIVER reports hearing the ring:

       report(client="matthew-ring", readings=[{id: "<receiver>", rssi: -62}])

   with the receiver registered to a room. One receiver gives distance only;
   add an ESP32 per room later and the same code gives real rooms, because the
   EMA smoothing and the 6 dB hysteresis already live in the hub.

   This is the room detection that was previously blocked on buying beacons.
   The beacon turned out to be a thing he already wears.

2. WORN / NOT WORN, and BATTERY, STEPS, HEART RATE on a slow poll. Connecting
   costs a few seconds and interrupts advertising, so it is deliberately
   infrequent — RSSI comes from passive scanning, which costs nothing.

Run:
    ./.venv/bin/python ring_bridge.py --once     # one pass, print, exit
    ./.venv/bin/python ring_bridge.py            # the loop
Config: environment, see below.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time

import requests
from bleak import BleakScanner

from datetime import datetime

from colmi_r02_client.client import Client
from colmi_r02_client.real_time import RealTimeReading

HUB = os.environ.get("OPEN_HOME_URL", "http://127.0.0.1:4700").rstrip("/")
PASSWORD = os.environ.get("OPEN_HOME_PASSWORD", "")
# Which ring. An address is exact; a name is the fallback, and on macOS the
# address is a system-specific UUID rather than a MAC, so name matching is the
# only portable option there.
RING_ADDRESS = os.environ.get("RING_ADDRESS", "")
RING_NAME = os.environ.get("RING_NAME", "R02")
# Who is hearing it, and from which room. With one receiver this is just
# "near the hub or not"; it becomes meaningful with more.
RECEIVER_ID = os.environ.get("RING_RECEIVER_ID", "openhome-hub")
RECEIVER_ROOM = os.environ.get("RING_RECEIVER_ROOM", "Living Room")
RING_CLIENT = os.environ.get("RING_CLIENT_ID", "matthew-ring")

SCAN_SECONDS = float(os.environ.get("RING_SCAN_SECONDS", "6"))
SCAN_EVERY = float(os.environ.get("RING_SCAN_EVERY", "30"))
# Full connect is expensive and blocks advertising; once every 15 min is plenty
# for battery and steps, which do not move fast.
CONNECT_EVERY = float(os.environ.get("RING_CONNECT_EVERY", "900"))


def log(*a: object) -> None:
    print(f"[ring {time.strftime('%H:%M:%S')}]", *a, flush=True)


class Hub:
    def __init__(self) -> None:
        self.s = requests.Session()

    def login(self) -> bool:
        if not PASSWORD:
            return True
        try:
            r = self.s.post(f"{HUB}/login", data={"password": PASSWORD},
                            headers={"Accept": "application/json"}, timeout=8)
            tok = (r.json() or {}).get("token", "")
            if tok:
                self.s.cookies.set("oh_auth", tok)
            return bool(tok)
        except Exception as e:
            log("hub login failed:", e)
            return False

    def post(self, path: str, body: dict) -> dict | None:
        for attempt in (1, 2):
            try:
                r = self.s.post(f"{HUB}{path}", json=body, timeout=10)
                if r.status_code == 401 and attempt == 1:
                    self.login()
                    continue
                return r.json() if r.content else {}
            except Exception as e:
                log(f"POST {path} failed:", e)
                return None
        return None


async def find_ring() -> tuple[str, int] | None:
    """Passive scan. Returns (address, rssi) or None.

    Deliberately does not connect: an advertisement is free and the ring keeps
    broadcasting one every second or so when nothing is attached to it.
    """
    found = await BleakScanner.discover(timeout=SCAN_SECONDS, return_adv=True)
    best = None
    for dev, adv in found.values():
        name = (adv.local_name or dev.name or "")
        if RING_ADDRESS and dev.address.upper() == RING_ADDRESS.upper():
            return dev.address, adv.rssi
        if RING_NAME and RING_NAME.lower() in name.lower():
            if best is None or (adv.rssi or -999) > best[1]:
                best = (dev.address, adv.rssi)
    return best


async def read_ring(address: str, want_hr: bool = False) -> dict:
    """Connect once and take the slow readings.

    Every call is wrapped individually: a ring that answers battery but chokes
    on the step log should still give us the battery, and the firmware
    revisions in the wild do differ in what they implement.
    """
    out: dict = {}
    client = Client(address)
    try:
        await client.connect()

        # Device info first — this is what tells us which SoC revision we have,
        # which decides whether ATC_RF03_Ring's firmware is even applicable.
        try:
            out["info"] = await client.get_device_info()
        except Exception as e:
            out["info_error"] = str(e)

        try:
            b = await client.get_battery()
            out["battery"] = {"level": b.battery_level, "charging": b.charging}
        except Exception as e:
            out["battery_error"] = str(e)

        try:
            today = datetime.now()
            steps = await client.get_steps(today)
            if isinstance(steps, list):
                # The ring buckets the day; the house only wants the total.
                out["steps"] = sum(s.steps for s in steps)
                out["calories"] = sum(s.calories for s in steps)
                out["distance"] = sum(s.distance for s in steps)
        except Exception as e:
            out["steps_error"] = str(e)

        # Live heart rate takes ~30s of the sensor running, so it is opt-in
        # rather than part of the routine poll.
        if want_hr:
            try:
                hr = await client.get_realtime_reading(RealTimeReading.HEART_RATE)
                if hr:
                    out["heart_rate"] = hr
                    out["heart_rate_avg"] = round(sum(hr) / len(hr))
            except Exception as e:
                out["hr_error"] = str(e)
    except Exception as e:
        out["connect_error"] = str(e)
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
    return out


async def main() -> int:
    once = "--once" in sys.argv
    log(f"hub={HUB} ring_name={RING_NAME!r} address={RING_ADDRESS or '(by name)'} "
        f"receiver={RECEIVER_ID}@{RECEIVER_ROOM}")

    hub = Hub()
    hub.login()
    # Register this receiver as a room-anchored beacon. Idempotent, so it is
    # safe to do on every start.
    hub.post("/rooms/beacons", {"id": RECEIVER_ID, "room": RECEIVER_ROOM, "name": f"{RECEIVER_ROOM} hub"})

    last_connect = 0.0
    while True:
        hit = await find_ring()
        if hit is None:
            log("ring not seen — out of range, or the phone is holding it "
                "(the R02 stops advertising while connected)")
        else:
            address, rssi = hit
            log(f"ring at {address}, rssi {rssi} dBm")
            # Feed the existing room logic. One receiver today; the smoothing
            # and hysteresis in the hub are already right for more.
            hub.post("/rooms/proximity", {
                "client": RING_CLIENT,
                "readings": [{"id": RECEIVER_ID, "rssi": rssi}],
            })

            if time.time() - last_connect > CONNECT_EVERY or once:
                last_connect = time.time()
                log("connecting for battery/info (interrupts advertising briefly)...")
                data = await read_ring(address, want_hr="--hr" in sys.argv)
                log("  ", data)
                hub.post("/ring/state", {"client": RING_CLIENT, "rssi": rssi, **data})

        if once:
            return 0
        await asyncio.sleep(SCAN_EVERY)


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        pass

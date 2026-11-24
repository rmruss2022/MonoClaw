#!/usr/bin/env python3
"""
Continuous ring watcher — the receiver half of "double tap wakes Jarvis".

WHY CONTINUOUS AND NOT A POLL
-----------------------------
ring_bridge.py scans in discrete 6-second windows, which is fine for "how far
away is he" and useless for a gesture: a tap would land anywhere in that window
and be reported up to 6 seconds late. A gesture has a latency budget of a few
hundred milliseconds or it feels broken, so this holds the scanner open and
reacts in the detection callback.

THE TAP PATH, END TO END
------------------------
Nothing here needs a BLE *connection*, which is the whole trick — a connection
would cost 200 uA-1 mA against a 17 mAh battery. Instead:

    double tap  ->  firmware sets a counter in the advertisement
                ->  advertises fast (20 ms) for ~2 s
                ->  this watcher sees the counter change
                ->  POST /agent/wake  ->  Jarvis listens

Budget, from the datasheets in atc1441/ATC_RF03_Ring:
    accelerometer, low-power mode (25 ms sleep)       7 uA
    accelerometer, suspend                            1 uA
    accelerometer, normal (only during a tap window) 110 uA
    advertising at 1 s, typical                   ~15-25 uA
    17 mAh battery
So idling is tens of microamps and the tap window is milliseconds. Streaming
raw accelerometer over a live connection instead would flatten it in a day.

A counter rather than a boolean, because advertisements are unreliable
broadcasts: we may see the same one several times or miss some. A monotonic
counter makes "how many taps since I last looked" answerable and idempotent.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time

import requests
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

HUB = os.environ.get("OPEN_HOME_URL", "http://127.0.0.1:4700").rstrip("/")
PASSWORD = os.environ.get("OPEN_HOME_PASSWORD", "")
RING_ADDRESS = os.environ.get("RING_ADDRESS", "")
RING_CLIENT = os.environ.get("RING_CLIENT_ID", "matthew-ring")
RECEIVER_ID = os.environ.get("RING_RECEIVER_ID", "openhome-hub")
RECEIVER_ROOM = os.environ.get("RING_RECEIVER_ROOM", "Living Room")

# How often to push an RSSI reading up. Advertisements arrive about once a
# second; proximity does not need that resolution and the hub smooths anyway.
RSSI_EVERY = float(os.environ.get("RING_RSSI_EVERY", "20"))

# Names the Colmi-family rings are sold under — from
# atc1441/ATC_RF03_Ring/Known_BLE_OEM_Ring_Names.txt. Matching on a list beats
# matching on "R02" alone, because the same hardware ships as thirty things.
OEM_NAMES = {
    "r01", "r02", "r03", "r04", "r05", "r06", "r07", "r08", "r10",
    "vk-5098", "merlin", "hello ring", "ring1", "boatring", "tr-r02", "se",
    "evolveo", "gl-sr2", "blaupunkt", "ksix ring", "iget", "kogan", "fitness",
    "fyri", "onering sr01", "bok", "9fsm", "stf", "newgen", "ssr",
}
R02_SERVICE = "6e40fff0-b5a3-f393-e0a9-e50e24dcca9e"

# Where custom firmware will publish the tap counter. Manufacturer-specific
# data is the right place: it rides in the advertisement, needs no connection,
# and we choose the company id so nothing else collides with it.
#
# NOT YET IMPLEMENTED IN FIRMWARE — until the custom build exists this watcher
# reports RSSI and logs that no tap field is present, rather than pretending.
TAP_COMPANY_ID = int(os.environ.get("RING_TAP_COMPANY_ID", "0xFFFF"), 0)


def log(*a: object) -> None:
    print(f"[ring {time.strftime('%H:%M:%S')}]", *a, flush=True)


def is_ring(dev: BLEDevice, adv: AdvertisementData) -> bool:
    if RING_ADDRESS:
        return dev.address.upper() == RING_ADDRESS.upper()
    if R02_SERVICE in [u.lower() for u in (adv.service_uuids or [])]:
        return True
    name = (adv.local_name or dev.name or "").strip().lower()
    return bool(name) and name in OEM_NAMES


class Hub:
    def __init__(self) -> None:
        self.s = requests.Session()

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

    def post(self, path: str, body: dict) -> None:
        for attempt in (1, 2):
            try:
                r = self.s.post(f"{HUB}{path}", json=body, timeout=8)
                if r.status_code == 401 and attempt == 1:
                    self.login()
                    continue
                return
            except Exception as e:
                log(f"POST {path} failed:", e)
                return


class Watcher:
    def __init__(self, hub: Hub) -> None:
        self.hub = hub
        self.last_rssi_push = 0.0
        self.last_tap_count: int | None = None
        self.seen = False
        self.taps = 0

    def on_adv(self, dev: BLEDevice, adv: AdvertisementData) -> None:
        if not is_ring(dev, adv):
            return
        if not self.seen:
            self.seen = True
            log(f"ring found: {adv.local_name or dev.name} at {dev.address}")

        now = time.time()

        # --- the gesture ---
        blob = (adv.manufacturer_data or {}).get(TAP_COMPANY_ID)
        if blob:
            count = blob[0]
            if self.last_tap_count is None:
                self.last_tap_count = count
                log(f"tap counter baseline {count}")
            elif count != self.last_tap_count:
                # Wrap-safe difference over a byte.
                delta = (count - self.last_tap_count) % 256
                self.last_tap_count = count
                self.taps += delta
                log(f"DOUBLE TAP (+{delta}, total {self.taps}) rssi {adv.rssi} — waking Jarvis")
                self.hub.post("/agent/wake", {
                    "source": "ring", "client": RING_CLIENT, "taps": delta, "rssi": adv.rssi,
                })

        # --- proximity, rate-limited ---
        if now - self.last_rssi_push > RSSI_EVERY:
            self.last_rssi_push = now
            self.hub.post("/rooms/proximity", {
                "client": RING_CLIENT,
                "readings": [{"id": RECEIVER_ID, "rssi": adv.rssi}],
            })
            extra = "" if blob else "  (no tap field — still on stock firmware)"
            log(f"rssi {adv.rssi} dBm -> {RECEIVER_ID}@{RECEIVER_ROOM}{extra}")


async def main() -> int:
    log(f"hub={HUB} receiver={RECEIVER_ID}@{RECEIVER_ROOM} "
        f"tap_company_id=0x{TAP_COMPANY_ID:04X}")
    hub = Hub()
    hub.login()
    hub.post("/rooms/beacons", {"id": RECEIVER_ID, "room": RECEIVER_ROOM,
                                "name": f"{RECEIVER_ROOM} hub"})

    w = Watcher(hub)
    scanner = BleakScanner(detection_callback=w.on_adv)
    await scanner.start()
    log("watching continuously — double tap the ring")
    try:
        deadline = time.time() + float(os.environ.get("RING_WATCH_SECONDS", "0") or 0)
        while True:
            await asyncio.sleep(1)
            if deadline > time.time() - 1 and os.environ.get("RING_WATCH_SECONDS"):
                if time.time() >= deadline:
                    break
            if not w.seen and int(time.time()) % 30 == 0:
                log("still not seeing the ring — is QRing closed on the phone?")
                await asyncio.sleep(1)
    finally:
        await scanner.stop()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        pass

#!/usr/bin/env python3
"""
Find the ring, and say what it actually is.

Step one of flashing anything is knowing what chip is in it, and the Colmi R02
is sold with at least two different SoCs under the same model number:

  - BlueX RF03      -> atc1441/ATC_RF03_Ring has custom firmware for this one
  - Realtek RT02CR  -> different bootloader, different flashing path entirely

Picking the wrong one bricks the ring. So this does not flash, pair, or write
anything: it scans, connects read-only, and dumps the GATT tree plus whatever
the device will tell us about itself.

    ./.venv/bin/python ring_scan.py              # scan only
    ./.venv/bin/python ring_scan.py --inspect    # scan, then connect to the best match
"""
from __future__ import annotations

import asyncio
import sys

from bleak import BleakClient, BleakScanner

# The UART-style service the R02 family exposes. Same shape as Nordic's NUS but
# a Colmi-specific base, which is why it is worth matching on explicitly: the
# advertised NAME is unreliable (some units advertise "R02", some "Colmi R02",
# some a bare MAC).
R02_SERVICE = "6e40fff0-b5a3-f393-e0a9-e50e24dcca9e"
R02_WRITE = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
R02_NOTIFY = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

# Standard Device Information Service — where a firmware/model string lives if
# the vendor bothered to populate it.
DIS = {
    "00002a24-0000-1000-8000-00805f9b34fb": "model number",
    "00002a25-0000-1000-8000-00805f9b34fb": "serial number",
    "00002a26-0000-1000-8000-00805f9b34fb": "firmware revision",
    "00002a27-0000-1000-8000-00805f9b34fb": "hardware revision",
    "00002a28-0000-1000-8000-00805f9b34fb": "software revision",
    "00002a29-0000-1000-8000-00805f9b34fb": "manufacturer",
}

NAME_HINTS = ("r02", "r0", "colmi", "ring", "qring")


def looks_like_ring(dev, adv) -> int:
    """Score how likely this is the ring. Higher is better, 0 means no."""
    score = 0
    name = (adv.local_name or dev.name or "").lower()
    if R02_SERVICE.lower() in [u.lower() for u in (adv.service_uuids or [])]:
        score += 100          # definitive
    if any(h in name for h in NAME_HINTS):
        score += 10
    if name.startswith("r0"):
        score += 5
    return score


async def scan(seconds: float = 12.0):
    print(f"scanning {seconds:.0f}s for BLE devices...\n")
    found = await BleakScanner.discover(timeout=seconds, return_adv=True)
    rows = []
    for dev, adv in found.values():
        rows.append((looks_like_ring(dev, adv), adv.rssi, dev, adv))
    rows.sort(key=lambda r: (-r[0], -(r[1] or -999)))

    if not rows:
        print("  nothing advertising at all — is Bluetooth on, and is the")
        print("  terminal allowed Bluetooth access in System Settings > Privacy?")
        return None

    print(f"  {'score':>5}  {'rssi':>5}  {'name':<24} address")
    print(f"  {'-'*5}  {'-'*5}  {'-'*24} {'-'*36}")
    for score, rssi, dev, adv in rows[:25]:
        name = adv.local_name or dev.name or "(none)"
        mark = " <-- likely the ring" if score >= 10 else ""
        print(f"  {score:>5}  {rssi:>5}  {name:<24} {dev.address}{mark}")

    best = rows[0]
    if best[0] < 10:
        print("\n  No ring found. The R02 stops advertising while it is connected")
        print("  to a phone — force-quit QRing (or turn the phone's Bluetooth off)")
        print("  and run this again.")
        return None
    return best[2]


async def inspect(dev):
    print(f"\nconnecting to {dev.address} (read-only)...")
    try:
        async with BleakClient(dev.address, timeout=20.0) as client:
            print(f"  connected: {client.is_connected}\n")

            print("  Device Information Service:")
            got_any = False
            for uuid, label in DIS.items():
                try:
                    val = await client.read_gatt_char(uuid)
                    print(f"    {label:<20} {val.decode('utf-8', 'replace').strip()}")
                    got_any = True
                except Exception:
                    pass
            if not got_any:
                print("    (none exposed — common on these; the chip ID has to come")
                print("     from the protocol or from opening it up)")

            print("\n  GATT tree:")
            for svc in client.services:
                tag = "  <-- R02 UART" if svc.uuid.lower() == R02_SERVICE.lower() else ""
                print(f"    service {svc.uuid}  {svc.description}{tag}")
                for ch in svc.characteristics:
                    print(f"      char {ch.uuid}  {','.join(ch.properties):<28} {ch.description}")

            has_uart = any(s.uuid.lower() == R02_SERVICE.lower() for s in client.services)
            print()
            if has_uart:
                print("  VERDICT: R02-family UART service present — the reverse-engineered")
                print("           protocol applies, and we can read it WITHOUT flashing.")
            else:
                print("  VERDICT: no R02 UART service. Either not an R02, or a revision")
                print("           with a different protocol. Do not flash anything yet.")
    except Exception as e:
        print(f"  connect failed: {e}")
        print("  (if this is a timeout: the ring may still be paired to the phone)")


async def main():
    dev = await scan()
    if dev and "--inspect" in sys.argv:
        await inspect(dev)
    elif dev:
        print("\n  re-run with --inspect to connect and dump its GATT tree.")


if __name__ == "__main__":
    asyncio.run(main())

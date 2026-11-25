#!/usr/bin/env python3
"""Connect with GATT discovery narrowed to the one service we need.

Full discovery was the thing killing us. With BlueZ no longer offering to bond
(the earlier SMP failure), the ATT conversation does happen — but each round
trip was taking 100-300 ms and the link supervision timeout fired before the
whole tree was walked. Asking for a single service cuts the round trips to a
handful.
"""
from __future__ import annotations

import asyncio
import sys

from bleak import BleakClient, BleakScanner

ADDR = "32:32:46:31:E4:02"
UART = "6e40fff0-b5a3-f393-e0a9-e50e24dcca9e"


async def main() -> int:
    for n in range(1, 7):
        dev = await BleakScanner.find_device_by_address(ADDR, timeout=12.0)
        if dev is None:
            print(f"  {n}: not advertising", flush=True)
            await asyncio.sleep(1)
            continue
        try:
            async with BleakClient(dev, timeout=25.0, services=[UART]) as c:
                svcs = list(c.services)
                print(f"  {n}: CONNECTED — {len(svcs)} service(s)", flush=True)
                for s in svcs:
                    print(f"       {s.uuid}")
                    for ch in s.characteristics:
                        props = ",".join(ch.properties)
                        print(f"         {ch.uuid} [{props}]")
                return 0
        except Exception as e:
            print(f"  {n}: {type(e).__name__}: {str(e)[:60]}", flush=True)
        await asyncio.sleep(2)
    print("  all attempts failed")
    return 1


sys.exit(asyncio.run(main()))

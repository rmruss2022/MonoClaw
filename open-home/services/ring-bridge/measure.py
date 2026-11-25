#!/usr/bin/env python3
"""Battery, and the real a1 03 sample rate.

The rate is the number the whole gesture feature hangs on: our own harness
measured 12 Hz catching a natural double tap 10% of the time, and 50 Hz
catching it every time (see AUDIT.md).

Connects with discovery narrowed to the UART service, which is what finally
made the link survive — full discovery timed out on the supervision timeout.
"""
from __future__ import annotations

import asyncio
import math
import os
import sys
import time

from bleak import BleakClient, BleakScanner

ADDR = "32:32:46:31:E4:02"
UART = "6e40fff0-b5a3-f393-e0a9-e50e24dcca9e"
RX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
SECONDS = float(sys.argv[1]) if len(sys.argv) > 1 else 12.0
# Which radio. The Pi's built-in hci0 is busy streaming A2DP to the speaker,
# and a single radio cannot do that and BLE GATT discovery without starving one
# of them — which is what the 100-300 ms ATT round trips were. hci1 is the USB
# dongle, dedicated to the ring.
ADAPTER = os.environ.get("RING_ADAPTER", "hci1")


def pkt(cmd: int, payload: bytes = b"") -> bytearray:
    p = bytearray(16)
    p[0] = cmd
    p[1:1 + len(payload)] = payload
    p[15] = sum(p[:15]) & 0xFF      # low byte of the sum — see AUDIT.md
    return p


def i16(hi: int, lo: int) -> int:
    v = (hi << 8) | lo
    return v - 0x10000 if v >= 0x8000 else v


async def go() -> int:
    print(f"using adapter {ADAPTER}", flush=True)
    for n in range(1, 7):
        dev = await BleakScanner.find_device_by_address(ADDR, timeout=12.0, adapter=ADAPTER)
        if dev is None:
            print(f"  {n}: not advertising", flush=True)
            await asyncio.sleep(1)
            continue
        try:
            async with BleakClient(dev, timeout=25.0, services=[UART], adapter=ADAPTER) as c:
                # Touch the service table before using it. narrow.py worked
                # because it enumerated services first; calling start_notify
                # straight after connect raced bleak's resolution and failed
                # with "Service Discovery has not been performed yet".
                svcs = list(c.services)
                print(f"CONNECTED — {len(svcs)} service(s) resolved\n", flush=True)
                tx_char = c.services.get_characteristic(TX)
                rx_char = c.services.get_characteristic(RX)
                if tx_char is None or rx_char is None:
                    raise RuntimeError("UART characteristics not resolved")
                rx: dict[int, list[bytes]] = {}
                samples: list[tuple[float, int, int, int]] = []

                def on(_s, d: bytearray) -> None:
                    rx.setdefault(d[0] if d else -1, []).append(bytes(d))
                    if len(d) >= 8 and d[0] == 0xA1 and d[1] == 0x03:
                        samples.append((time.monotonic(), i16(d[2], d[3]),
                                        i16(d[4], d[5]), i16(d[6], d[7])))

                await c.start_notify(tx_char, on)

                await c.write_gatt_char(rx_char, pkt(0x03), response=False)
                await asyncio.sleep(1.5)
                b = rx.get(0x03)
                if b:
                    print(f"BATTERY: {b[0][1]}%   charging={bool(b[0][2])}", flush=True)
                else:
                    print("BATTERY: no reply", flush=True)

                print(f"\npolling a1 03 for {SECONDS:.0f}s (PPG untouched, LEDs off)...",
                      flush=True)
                t0 = time.monotonic()
                while time.monotonic() - t0 < SECONDS:
                    try:
                        await c.write_gatt_char(rx_char, pkt(0xA1, bytes([0x03])), response=False)
                    except Exception as e:
                        print(f"  write failed: {e}", flush=True)
                        break
                    await asyncio.sleep(0.01)
                await asyncio.sleep(0.4)
                el = time.monotonic() - t0
                try:
                    await c.write_gatt_char(rx_char, pkt(0xA1, bytes([0x02])), response=False)
                except Exception:
                    pass

                print(f"\nnotification commands: "
                      f"{ {hex(k): len(v) for k, v in rx.items()} }")
                if len(samples) > 3:
                    hz = len(samples) / el
                    mags = sorted(math.sqrt(x * x + y * y + z * z)
                                  for _, x, y, z in samples)
                    med = mags[len(mags) // 2]
                    gaps = sorted(samples[i + 1][0] - samples[i][0]
                                  for i in range(len(samples) - 1))
                    print(f"\nACCEL: {len(samples)} samples in {el:.1f}s")
                    print(f"  MEASURED RATE:      {hz:.1f} Hz")
                    print(f"  median sample gap:  {gaps[len(gaps) // 2] * 1000:.0f} ms")
                    print(f"  resting magnitude:  {med:.0f}  ({med / 8192:.2f} g at 8192/g)")
                    print(f"  min / max:          {mags[0]:.0f} / {mags[-1]:.0f}")
                    print(f"  first xyz:          {samples[0][1:]}")
                    print()
                    if hz >= 45:
                        print("  -> ENOUGH for a reliable double tap with no firmware change")
                    elif hz >= 25:
                        print("  -> MARGINAL: a deliberate double tap may work, a natural one will not")
                    else:
                        print("  -> TOO SLOW for a natural double tap (12 Hz = 10% in our tests)")
                        print("     Needs a slower deliberate gesture, or a faster channel.")
                else:
                    print(f"\nACCEL: only {len(samples)} samples — a1 03 may be unsupported here")
                    for k, v in rx.items():
                        print(f"  {hex(k)}: {v[0].hex()}")
                try:
                    await c.stop_notify(tx_char)
                except Exception:
                    pass
                return 0
        except Exception as e:
            print(f"  {n}: {type(e).__name__}: {str(e)[:60]}", flush=True)
        await asyncio.sleep(2)
    return 1


sys.exit(asyncio.run(go()))

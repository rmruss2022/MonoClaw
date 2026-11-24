# Repo audit — what we take, what we leave, what we measured ourselves

Read the source, not the READMEs. Three findings changed our design and one
corrected the documentation.

## `tahnok/colmi_r02_client` — the protocol layer

**Take it as a dependency.** It is maintained, documented, has tests, and the
API is honest. Verified against the installed package rather than the docs:

```
get_device_info() -> dict[str,str]        get_steps(date) -> [SportDetail]
get_battery() -> BatteryInfo(battery_level, charging)
get_realtime_reading(RealTimeReading.HEART_RATE|SPO2|HRV|...) -> [int]
get_heart_rate_log(date)   set_heart_rate_log_settings(enabled, interval)
set_time(dt)   blink_twice()   reboot()   raw(command, subdata, replies)
```

`blink_twice()` matters more than it looks: it is a local feedback channel, so
the ring can confirm a gesture landed without waiting for a speaker.

**One documentation bug worth pinning.** The README and the docstring both say
the checksum is "modulus 255". The code does `sum(packet) & 255`, which is
modulo **256**. `ring_control` independently implements `sum(pkt[:15]) & 0xFF`
— same thing. So the prose is wrong in two places and the two implementations
agree. Anyone deriving the checksum from the documentation gets a packet the
ring rejects.

Requires Python >=3.11,<3.14. The Pi has 3.13.5. Fine.

## `Georgescortas/ring_control` — the gesture prior art

The most useful repo, and its value is in measurements rather than code.

**The `a1 03` discovery, which we adopt wholesale:**

| Command | Effect | Rate | LEDs |
|---|---|---|---|
| `0xA1 0x04` | start the raw sensor block — **also powers the PPG** | ~1.2 Hz | **on**, hours of battery |
| `0xA1 0x02` | stop | — | off |
| `0xA1 0x03` | **one** snapshot, PPG untouched — poll in a loop | **~12 Hz** | **off** |

Axes are big-endian signed 16-bit, **~8192 counts per g**, so a still ring
reads magnitude ~8200. Accel notifications carry `data[1] == 0x03`.

**Four design ideas we keep**, each of which they clearly learned the hard way:

1. **Calibrate the resting magnitude**, don't assume 1g. It drifts per unit.
2. **Adapt the rest value only while quiet**, so a gesture never moves the
   reference it is measured against.
3. **Hysteresis** — after a jolt, require a fall back inside a release band.
   Without it one tap reads as several.
4. **Read orientation from BEFORE the gesture.** Mid-swing a moving hand
   produces samples that look like pure gravity while the wrist has already
   turned, so that reading is a confident lie. And reject stale readings: a
   pose from minutes ago describes where your hand was, "typically 90 degrees
   away, on a desk or at your side".

**Also free, and we want it:** the ring pushes step-counter updates unprompted
(command `0x73`), LEDs off, no polling — and only while it is *moving*. That is
worn-vs-in-the-charger for nothing.

### What we do differently

- **One mechanism for all tap counts.** They have separate `single` and
  `double` modes and fire the instant the second tap lands. We count jolts into
  a burst and fire when the burst *ends*, which yields double and triple from
  the same code and makes "was that two or three" answerable instead of a race.
- **A modal music mode** they don't have: double tap opens a window, wrist roll
  maps to volume while it is open, idle closes it.
- Their own caveat on double-tap: *"Limited by the ring's low sample rate, so a
  natural fast double-tap may not register."* Their timing window is **60 ms to
  1200 ms** — the upper bound stretched to 1.2 seconds, which makes it "two
  deliberate taps" rather than a double-tap. We measured why.

## What we measured ourselves

`test_gestures.py`, synthetic traces, 8 phase offsets per cell because whether
a 30 ms transient lands on a sample is luck at low rates:

```
        gap:    100ms    150ms    200ms    250ms    300ms
     12 Hz:     .(0/8)   .(1/8)   .(0/8)   .(3/8)   .(0/8)
     25 Hz:     .(2/8)   .(3/8)   D(5/8)   D(4/8)   .(2/8)
     50 Hz:     D(8/8)   D(8/8)   D(8/8)   D(8/8)   D(8/8)
    125 Hz:     D(8/8)   D(8/8)   D(8/8)   D(8/8)   D(8/8)
    250 Hz:     D(8/8)   D(8/8)   D(8/8)   D(8/8)   D(8/8)
```

**12 Hz detects 4 of 40 trials — 10%.** That is the stock protocol's ceiling,
and it is not a tuning problem: a tap is a ~30 ms transient and 12 Hz samples
every 83 ms, so the spike frequently does not exist in the data at all. No
threshold fixes a sample that was never taken.

**50 Hz is perfect, 40/40.** So the firmware requirement is **50 Hz, not 250** —
a much cheaper spec than the one in `FIRMWARE-PLAN.md`, which assumed 250.
Combined with the slope-interrupt wake, 50 Hz for half a second per gesture is
almost free.

That is the whole firmware argument in one table, and it is ours.

## What we need to do

**Done, no hardware required:**
- `gestures.py` — the state machine: tap, double, triple, hold, music mode with
  roll-to-volume. Pure function of (x, y, z, t).
- `test_gestures.py` — 9 tests, all passing, plus the rate measurement above.
- `ring_scan.py` / `ring_watch.py` — identify the device; passive advertisement
  listener for the fixed receivers.

**Blocked on the ring arriving:**
1. `ring_scan.py --inspect` — **confirm BlueX RF03 and not Realtek RT02CR.**
   Decides whether flashing is possible at all.
2. Wire `gestures.py` to a real `a1 03` poll loop and **log raw magnitudes while
   tapping**. Our `jolt=1200` and `release=700` come from `ring_control`'s R09;
   they need confirming on an R02 on Matthew's hand. Those measured numbers then
   become the firmware thresholds.
3. Confirm `roll_axes` — currently `("y", "z")`, which depends on how the ring
   sits on the finger and is one line to change.
4. Flash the **stock** dump over OTA first, to prove recovery works.

**Then firmware**, with a spec we can now state concretely: slope interrupt
wakes the MCU, sample at **50 Hz** for ~500 ms, run this same detector, emit the
event as both a GATT notification and an advertisement counter.

The detector is deliberately the same logic in both places. If it runs on the
host first, every threshold is validated before a single byte is flashed.

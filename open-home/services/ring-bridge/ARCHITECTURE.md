# Ring architecture — who connects, who listens, and what moves

Supersedes the transport assumptions in `FIRMWARE-PLAN.md`. The firmware design
there still holds; this is about where the data goes, and it changed because
"I'll be out of the house" is the requirement that breaks a Pi-centric design.

## The thing I had wrong

I said connecting the ring to the phone **and** the Pi was impossible. Half
right. A Colmi ring accepts **one GATT connection** at a time — but
*advertisements are broadcasts*, and any number of receivers can hear them
without connecting to anything.

So the two roles are different jobs, and they don't conflict:

```
                    ┌─────────── the ring ───────────┐
                    │  ONE connection + broadcasts   │
                    └───┬────────────────────────┬───┘
            GATT        │                        │   advertisements
         (connected)    │                        │   (passive, unlimited)
                        ▼                        ▼
                  ┌───────────┐          ┌──────────────────────┐
                  │   PHONE   │          │  Pi, + ESP32 per room │
                  │ always    │          │  fixed, at home only  │
                  │ with you  │          └──────────┬───────────┘
                  └─────┬─────┘                     │ RSSI
                        │ HTTPS, anywhere           │
                        ▼                           ▼
                  ┌──────────────────────────────────────┐
                  │   openhome hub  (proximity.ts etc.)  │
                  └──────────────────────────────────────┘
```

**The phone owns the connection**, because it is the only receiver that is
always in range of your hand. Taps and health go out over the internet, so the
ring works in a bar in Bushwick, not just the living room.

**The fixed receivers never connect** — they only listen for advertisements and
report RSSI. That is what gives rooms, and it is the one thing the phone
*cannot* do: the phone moves with you, so phone-RSSI tells you how far the ring
is from your own pocket. Useless. Room detection needs receivers that stay put.

## How the tap is measured — and the answer is "two ways, pick one"

This is prior art, not theory. [`Georgescortas/ring_control`](https://github.com/Georgescortas/ring_control)
does double-tap on the R02/R03/R06/R09 family **today, with no custom firmware**,
and their measurements are the reason to flash anyway.

### Option A — host-side, stock firmware (works the day it arrives)

Hold a BLE connection, poll the accelerometer, run a threshold detector on the
host. Their hard-won detail, which saves us the same mistake:

| Command | What it does | Rate | LEDs |
|---|---|---|---|
| `a1 04` | the "real" sensor stream — **also powers the PPG sensor** | ~1.2 Hz | **on**, battery gone in hours |
| `a1 03` | **one** sensor snapshot, PPG untouched — poll it in a loop | **~12 Hz** | **off** |

So the stream command is the trap and the snapshot command is the answer: ten
times the rate at a fraction of the power. Their own guidance is to use "a
deliberate, distinct gesture" and tune the threshold, because **12 Hz is thin
for a tap** — a tap is a sharp transient, and at 12 Hz you catch two or three
samples of it.

Cost: a held connection plus constant polling drains the ring in **hours**, and
on iOS it means the app must keep that connection alive in the background.

### Option B — in firmware (why flashing is actually worth it)

Everything in `FIRMWARE-PLAN.md`: the any-motion interrupt wakes the MCU, which
samples at ~250 Hz for half a second and decides locally.

**20x the sample rate, and days of battery instead of hours** — because nothing
is connected and nothing is polled while you are not tapping.

That is the real case for custom firmware, and it is stronger than the one I
made earlier. I said you probably didn't need to flash it because the stock
protocol exposes the sensors. True, and beside the point: stock exposes them at
a rate and a power cost that make a *gesture* barely viable. Capability was
never the issue. Sample rate and battery are.

**Build order:** A first, because it works on arrival and tells us what a real
tap looks like in raw units on *your* hand. Those measured thresholds are then
exactly what the firmware detector needs. Doing B first means guessing at
numbers we could have measured.

### Free, and better than either: wear detection

`ring_control` found that the ring pushes **step-counter updates unprompted**
(command byte `0x73`) — LEDs off, no polling, no connection cost beyond being
connected. They arrive only while the ring is *moving*, and stop when it is
still.

That is the worn/not-worn gate for nothing. It should land before any
automation: without it, a ring in its charger still reports proximity and still
accepts taps, so the house acts on a ring in a drawer.

## iOS: the constraints are specific

From Apple's Core Bluetooth background docs, and they shape the design:

- **`bluetooth-central` background mode** wakes the app when
  `CBPeripheralDelegate` methods fire — including *"when a peripheral sends
  updated characteristic values"*. So **a GATT notification wakes the app from
  suspended.** This is the reliable path.
- **Background scanning is deliberately crippled** — you cannot continuously
  discover nearby devices, you must name service UUIDs, and results are
  coalesced. So on iOS, do **not** build the tap path on advertisement
  scanning. It will work in the foreground and disappoint everywhere else.
- **The system can terminate the app** to reclaim memory, dropping connections.
  Needs state preservation and restoration
  (`CBCentralManagerOptionRestoreIdentifierKey`) or the ring silently stops
  working after a few hours in your pocket.

**Therefore the firmware should emit a tap two ways**, which costs almost
nothing to do:

1. a **GATT notification** — for the connected phone, works in background
2. a **counter in the advertisement** — for the fixed receivers at home

`ring_watch.py` already consumes (2).

## What the phone should actually send

| Data | Rate | Why | Honest value |
|---|---|---|---|
| **Tap / gesture events** | event-driven | wake Jarvis, stop the briefing, run a scene | the whole point |
| **Worn / not-worn** | on change | gates everything else | high — prevents acting on a ring in a drawer |
| **Sleep & wake times** | once a day | the morning scene trigger, instead of a fixed cron | **highest** of the health data |
| **Battery** | every 15 min | tell you before it dies mid-day | useful, nearly free |
| **Heart rate log** | stock interval, configurable | context: resting vs active | moderate — not medical |
| **Steps / calories / distance** | every 15 min | nothing in this house needs it yet | low, but free |
| **RSSI** | — | **don't bother from the phone** | zero: the phone moves with you |

Sleep/wake is the one I'd build first after the tap. A house that knows you are
actually awake is better than a house that guesses at 8 am, and nothing else
in this system can tell it.

## Continuous gestures — "turn my hand to change the volume"

Feasible, and the mechanism is simple: a 3-axis accelerometer at rest measures
the **gravity vector**, so wrist roll comes straight out of `atan2(y, z)`. No
gyro needed. It drifts only while you are accelerating the hand, which you are
not when deliberately rotating it.

The right shape is **modal**, exactly as described — a wake gesture, then a
control window:

```
double tap ──► enter MUSIC MODE ──► wrist roll maps to volume ──► 5 s idle ──► exit
                    │                                                  │
                 LED on                                            LED off
```

Three reasons it has to be modal rather than always-live:

1. **Power.** Continuous sampling is only affordable in bursts. A few seconds
   per adjustment is nothing; always-on is the thing that kills the battery.
2. **False positives.** Your hand rotates constantly — reaching, typing,
   gesturing. An always-live roll-to-volume control would be unusable within a
   minute.
3. **Feedback.** You need to know you are in the mode. The LED is the only
   local channel the ring has, and it is enough: on means listening.

Other modal controls that fall out of the same window for free: roll for
brightness after a different entry gesture, and roll-past-a-threshold as
next/previous track.

**But continuous control has a latency budget that decides where it runs.** A
volume knob needs response under ~100 ms or it feels broken, and that rules out
the long path:

| Path | Round trip | Good for |
|---|---|---|
| ring → **Pi** → speaker | ~50–100 ms | continuous control — volume, brightness |
| ring → phone → internet → hub → speaker | ~200–500 ms+ | discrete events only — taps, scenes |

So **continuous gestures are a home-only feature**, served by the Pi. Which is
fine: away from home there is no living-room volume to turn.

## Where the processing goes — and the industry answer

The split that every commercial wearable uses, and the reasoning behind it:

| Layer | Job | Why there |
|---|---|---|
| **Ring firmware** | **recognition** — emit `double_tap`, `roll=+15°` | power and latency; works regardless of what any app is doing |
| **Phone** | **gateway** — relay events, show UI, long-term history | it is the only thing always in range; it is *not* a good place to make decisions |
| **Hub / cloud** | **execution** and storage | it is where the speakers and lights are |

The rule underneath it: **never stream raw sensor data over BLE if a decision
can be made before it.** Raw streaming costs power at both ends, saturates the
link, and fails the moment the connection drops. Apple does tap detection in
the Watch's motion silicon, not in an app, for exactly these reasons. Oura,
Whoop and friends all extract features on-device and ship events and summaries.

This is the strongest argument for custom firmware, and it is not about
features — it is that **recognition belongs below the app layer**, and stock
firmware will not do recognition for us.

## The app-closed problem, which is the real one

This is the known hard problem in wearables, and iOS makes it sharp:

- **Backgrounded** app (not force-quit): fine. `bluetooth-central` plus state
  preservation and restoration keeps the connection and wakes the app on
  notifications.
- **Force-quit by you** (swiped out of the app switcher): iOS will **not**
  relaunch it for Bluetooth events. State restoration covers the system killing
  your app, not the user killing it. The ring is simply dead to the phone until
  you open the app again.
- **Phone dead, or in another room**: same outcome.

So a phone-primary design has a failure mode where double-tapping your ring in
your own living room does nothing, and the reason is invisible to you.

**The industry answer is not "fall back to the hub" — it is "don't make the
phone load-bearing at all."** The pattern has a name in home automation:
**local-first with direct binding.** A Zigbee wall switch is bound to the light
group directly; a Hue bridge executes scenes with no phone involved; a Matter
device works when your phone is in the sea. The phone is a *remote control and
a configuration surface*, never a required hop.

Applied here, and this is why the advertisement counter matters:

```
ring broadcasts the gesture event in its ADVERTISEMENT
        │
        ├──► Pi hears it (no connection)        ──► acts in ~100 ms   [AT HOME]
        │                                            works with the phone dead,
        │                                            closed, or in another room
        │
        └──► phone hears it (connected, iOS)    ──► relays over HTTPS  [AWAY]
                                                     needs the app alive
```

Both paths run **simultaneously at home**, and the hub **deduplicates on the
event counter** — which is precisely what a monotonic counter buys and a boolean
flag cannot. The ring does not need to know or care who is listening.

So: not phone-primary with a hub fallback. **Hub-primary at home, phone-primary
away, same event, deduplicated.** The home case is the one that has to be
reliable, and it is the one that does not depend on an app at all.

## Other people's work worth reading

- [`Georgescortas/ring_control`](https://github.com/Georgescortas/ring_control) — double-tap detection, the `a1 03` vs `a1 04` finding, wear detection
- [`tahnok/colmi_r02_client`](https://github.com/tahnok/colmi_r02_client) — the Python protocol client and the best protocol notes
- [`atc1441/ATC_RF03_Ring`](https://github.com/atc1441/ATC_RF03_Ring) — OTA flasher, firmware dumps, SDK, datasheets
- [Gadgetbridge PR #3896](https://codeberg.org/Freeyourgadget/Gadgetbridge/pulls/3896) — Android support for R02/R03/R06, derived from sniffing QRing
- `waldonaldo/colmi-ring` and `anikbharadwaj129/Colmi` — **SwiftUI iOS apps** doing sleep staging, HRV, temperature and readiness. Directly relevant to the phone half, and worth reading before writing any CoreBluetooth code.

## When the ring arrives

1. `ring_scan.py --inspect` — confirm the GATT tree and, if the DIS is
   populated, the firmware revision. **Which SoC it is decides whether flashing
   is even possible**, and the R02 ships with both BlueX RF03 and Realtek
   RT02CR.
2. Option A end to end: poll `a1 03`, log raw magnitude while you tap, and
   **write down the numbers**. Those become the firmware thresholds.
3. Only then: flash the stock dump over OTA to prove recovery works, then a
   custom build.

Nothing in this document is verified against hardware. It is all read off
datasheets, Apple's documentation, and other people's measurements.

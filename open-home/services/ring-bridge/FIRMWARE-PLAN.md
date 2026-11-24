# Custom firmware for the Colmi R02 — what exists, and the plan

## Prior art — you don't start from zero

[`atc1441/ATC_RF03_Ring`](https://github.com/atc1441/ATC_RF03_Ring) is the whole
foundation, and it contains more than documentation:

| What | Why it matters |
|---|---|
| **Browser OTA flasher** — [`ATC_RF03_Writer.html`](https://atc1441.github.io/ATC_RF03_Writer.html) | Flashes over BLE from Chrome. **No soldering, no opening the ring.** This is what makes the whole idea reasonable. |
| **Stock firmware dumps** — `R02_3.00.06_240523.bin`, `R02_1.00.05_211220.bin`, … | **Recovery.** A bad custom build gets the stock image flashed back over it. |
| **`R02_3.00.06_FasterRawValuesMOD.bin`** | A published mod of the stock firmware — an existing template for patching rather than rewriting. |
| **Full vendor SDK** — `SDKs/SDK3_3.3.6/` (~190 MB, split tar) | Build real firmware, not just patch bytes. |
| **`ROM_0_first128k_Bootloader_BLE_stack.bin`** | The bootloader + BLE stack dump, for understanding what OTA can and can't replace. |
| **Both datasheets** | SoC and accelerometer, which is how the facts below are known rather than guessed. |
| **QRing APK with cert pinning disabled** | For sniffing the stock app's protocol if we need a command we haven't mapped. |
| **`Known_BLE_OEM_Ring_Names.txt`** | The same hardware ships under 30 names — already wired into `ring_watch.py`. |

Two explainer videos are linked from that README. Worth watching before flashing.

## The hardware, from the datasheets

- **SoC:** BlueX Micro RF03 — ARM Cortex-M0, 200 KB RAM, 512 KB flash
- **Accelerometer:** Sensortek STK8321, ±2/4/8 g, 12-bit, I²C
- **Heart rate:** VCare VC30F
- **Battery: 17 mAh** — this number drives every decision below
- **SWD recovery pads:** P00 = SWCK, P01 = SWD (if OTA ever gets bricked)

## The finding that shapes the design

**The accelerometer has no tap detector.** I pulled the datasheet and counted:

```
"tap" / "double tap" / "single tap"     0 mentions
"slope" (any-motion)                   43
"any-motion"                           16
"interrupt"                           110
"INT1"                                 27
```

Most accelerometers in this class (Bosch BMA2x2 and friends) have a hardware
double-tap engine. **This one does not.** So double-tap has to be computed in
firmware — which is fine, but it means the MCU has to wake up and sample, and
on a 17 mAh battery that has to be done carefully.

What it *does* have is an **any-motion (slope) interrupt** with programmable
threshold and duration (`0x27 SLOPEDLY`, `SLP_DUR[1:0]`), plus three latch
modes. That is the wake source.

### Measured power, from the same datasheet

| State | Current |
|---|---|
| Accelerometer, suspend | **1 µA** |
| Accelerometer, low-power (25 ms sleep) | **7 µA** |
| Accelerometer, normal mode | **110 µA** |
| BLE advertising @ 1 s (typical for this class) | ~15–25 µA |

So the budget works only if normal mode is a *brief window*, not the steady
state. 17 mAh at ~35 µA idle is roughly three weeks; at 1 mA (a live BLE
connection streaming accelerometer data) it is **about seventeen hours**.

That rules out the obvious implementation — stream raw accelerometer to the Pi
and detect taps there. It would work, and the ring would be dead by morning.

## The design

```
  hand moves
      │
      ▼
  STK8321 slope interrupt (threshold tuned to a knock, not a wave)  ← 7 µA idle
      │ INT1
      ▼
  MCU wakes, accelerometer -> normal mode (110 µA), sample ~250 Hz for ~500 ms
      │
      ▼
  double-tap detector in firmware:
     two spikes above threshold, 80-400 ms apart, quiet before and after
      │ yes
      ▼
  increment a tap counter, put it in the ADVERTISEMENT payload
  advertise fast (20 ms) for ~2 s, then back to 1 s
      │
      ▼
  Pi: ring_watch.py sees the counter change        ← continuous passive scan
      │
      ▼
  POST /agent/wake  ->  Jarvis starts listening
```

**No BLE connection anywhere in the gesture path.** That is the point. A
connection costs 200 µA–1 mA and takes a second to establish; an advertisement
costs microamps and the Pi is already listening.

**A counter, not a flag.** Advertisements are unreliable broadcasts — we may see
one three times or miss it. A monotonic byte makes "how many taps since I last
looked" answerable and idempotent, which a boolean cannot do.

Expected latency, double-tap to Jarvis listening: **~0.6–1.0 s** (≈500 ms to
confirm the second tap, <100 ms for the Pi to see a 20 ms advertisement, then
the existing wake path). Comparable to the wake word, and it works when the
music is loud or you don't want to say anything out loud.

## Gesture vocabulary — proposed

The detector is already sampling a window, so extra gestures are nearly free:

| Gesture | Action | Why this one |
|---|---|---|
| **Double tap** | Wake Jarvis | What you asked for. |
| **Triple tap** | **Stop / shut up** | The thing most worth having. When a 45-second briefing is running and the speaker is loud, saying "stop" fights the speaker. A tap doesn't. |
| **Tap-and-hold (~1 s)** | Configurable scene | Lights off on the way to bed, without talking. |
| **Palm-down flick** | Next track | Only if it proves reliable; a flick is easy to trigger by accident. |

**LED confirmation.** The stock protocol already has a `blink_twice` command, so
the HR LED is addressable. In custom firmware the ring should blink the moment a
tap registers — then you know it worked without waiting for the speaker. That
closes the feedback loop locally, which matters because the failure mode of a
gesture is not knowing whether it landed.

## What else is worth adding

Beyond the taps and the obvious health telemetry:

1. **Worn / not-worn, as a gate on everything.** The HR sensor can tell. Without
   it, a ring on the nightstand still reports proximity and still accepts taps —
   so the house would act on a ring in a drawer. This should land before any of
   the automation below.
2. **Sleep and wake detection → the morning scene.** The ring knows when you
   actually woke up. That is a far better trigger than a fixed 8 am cron, and it
   is the single most useful thing the ring can tell this house.
3. **Room presence.** Already wired — see `ring_watch.py`. One receiver gives
   distance from the hub; an ESP32 per room gives real rooms through the EMA
   smoothing and 6 dB hysteresis already in `proximity.ts`.
4. **Workout detection** — sustained elevated HR plus motion → workout playlist,
   lights up. Honest caveat: HR plus motion is a *guess* at activity, and I would
   not have it do anything irreversible.
5. **Do-not-disturb from sleep state.** If the ring says asleep, the house should
   not announce anything. Cheap to implement, and prevents the 3 am briefing.

Explicitly **not** recommending: anything medical. HRV and SpO2 from a $20 ring
are interesting numbers, not clinical ones, and the house should not reason about
your health from them.

## Risk, honestly

- **Recovery exists**: stock dumps + the browser OTA flasher. A bad application
  image is re-flashable.
- **The real brick risk** is damaging the bootloader or the BLE stack, which
  lives in the first 128 KB. Custom builds must not touch it. If it goes, you
  are on SWD pads P00/P01 inside an epoxy-filled ring — i.e. the ring is gone.
- **Verify the chip first.** `ring_scan.py` exists for this. The R02 also ships
  with a Realtek RT02CR, and the BlueX OTA flasher will not help there.
- **Order of operations:** scan → confirm BlueX RF03 → flash the *stock* dump
  over OTA first (proves the flash path works and is recoverable) → only then
  flash a custom build.

That last step is the one people skip. Proving you can restore before you need
to is the difference between an experiment and a $20 lesson.

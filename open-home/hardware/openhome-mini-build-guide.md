# openhome mini — DIY Local "Alexa" Build Guide

A privacy-first smart speaker on a Raspberry Pi 4 that matches an Amazon Echo's core
experience — far-field "Alexa" wake word, natural voice replies, smart-home control,
timers, music, and a light ring — but runs **locally** and answers only to you.

> Status: design v1 (2026-07-30). Researched against current parts + software.
> Companion files: `hardware/enclosure/openhome-mini.scad` (printable shell),
> `hardware/mockups/06-photoreal.jpg` (retail concept), `07-mvp-prototype.jpg` (build).

---

## 1. Goal & requirements (what "match a real Alexa" means)

| Echo capability | openhome mini equivalent | Met by |
|---|---|---|
| "Alexa" wake word, hears across a room | 4-mic far-field array + openWakeWord `alexa` | XVF3800 + OWW |
| Understands speech | Local STT (Whisper) | faster-whisper |
| Talks back naturally | Local TTS | Piper |
| Controls smart home | Home Assistant Assist | HA |
| Timers / alarms / weather | Assist intents | HA |
| Plays music | Music Assistant → speaker | HA + MA |
| Light-ring feedback | 16-LED addressable ring | WS2812 |
| **Private / offline** | nothing leaves the LAN | (Alexa can't do this) |
| **Open-question "brain"** (optional) | LLM conversation agent | Gemini/OpenAI/local |

**Hard requirements**
- Wake from ~4–5 m in a normal room, with music playing (barge-in).
- End-to-end "Alexa, turn on the lights" → action + spoken confirm in **< 3 s**.
- Single 3D-printed device, USB-C powered, serviceable, no cloud account.

---

## 2. System architecture

```
                       ┌─────────────────────────── openhome mini (one Pi 4) ───────────────────────────┐
  voice ──▶ [XVF3800 4-mic array] ──USB(16k mono, AEC/beamformed)──▶ ┐
                                                                     │
                                              ┌── openWakeWord ("alexa")   ── wake ──┐
                                              │                                       ▼
                       [ Home Assistant + Assist pipeline ] ── STT (faster-whisper) ─▶ intent ─▶ TTS (Piper)
                                              │                                       │
   speaker ◀─ [3" driver] ◀─ [MAX98357A I2S] ◀── audio out ◀───────────────────────┘
                                              │
   ring   ◀─ [WS2812 ×16] ◀── SPI (GPIO10) ◀──┘   (state: idle/listen/think/speak/mute)
                       └───────────────────────────────────────────────────────────────────────────────┘
```

Two deployment shapes:
- **A. Self-contained (recommended to start):** everything above runs on the one Pi 4.
  Simplest; ~2–4 s latency with `whisper-base`. This is "one box I can build."
- **B. Satellite + server (performance path):** Pi 4 runs only mic + wake word + speaker +
  LEDs (via **linux-voice-assistant**); a separate HA box does STT/TTS/intent. Sub-second,
  scales to many rooms. Same hardware, just moves the heavy compute off-device.

---

## 3. Bill of materials (with links)

| # | Part | Why | Price | Link |
|---|------|-----|-------|------|
| 1 | Raspberry Pi 4 Model B (4 GB) | compute / runs everything | ~$55 | [buy](https://www.adafruit.com/product/4296) |
| 2 | SanDisk Extreme 32 GB microSD (A2) | OS + models | ~$10 | [buy](https://www.amazon.com/dp/B09X7BK27V) |
| 3 | **ReSpeaker XVF3800 USB 4-Mic Array** | far-field, HW AEC/beamforming/DoA, USB **or** I2S | $60.99 | [buy](https://www.seeedstudio.com/ReSpeaker-XVF3800-USB-Mic-Array-p-6488.html) |
| 4 | Adafruit MAX98357A I2S amp | digital audio out, 3 W | $5.95 | [buy](https://www.adafruit.com/product/3006) |
| 5 | 3" 4 Ω 3 W speaker | room-filling driver | $1.95 | [buy](https://www.adafruit.com/product/1314) |
| 6 | NeoPixel Ring — 16 × WS2812 | light-ring feedback | ~$9 | [buy](https://www.adafruit.com/product/1463) |
| 7 | Official USB-C PSU 5.1 V / 3 A | power (see §7 audit) | ~$8 | [buy](https://www.raspberrypi.com/products/type-c-power-supply/) |
| 8 | Heatsink + 30 mm fan | Whisper heats the Pi | ~$6 | [buy](https://www.amazon.com/dp/B07VVDN9K3) |
| 9 | M2.5 heat-set inserts + screws | serviceable base | ~$8 | [buy](https://www.amazon.com/dp/B08SQ4NVHW) |
| 10 | Dupont/JST jumper wires | wiring | ~$7 | [buy](https://www.amazon.com/dp/B07GD2BWPY) |
| 11 | 3D-printed shell (PETG, ~150 g) | enclosure (`openhome-mini.scad`) | ~$3 | in this repo |

**Total ≈ $175 @ qty 1** (~$150 at a batch of 10). Compare: Echo (4th gen) ~$100 but cloud-bound
and no local control; openhome mini adds privacy + a scriptable brain.

**Budget swaps**
- Cheaper mic: ReSpeaker XVF3000 4-Mic ($64) or **2-Mic** ($30-ish, near-field only).
- No-solder audio: a small **USB speaker** instead of MAX98357A+driver (loses the clean I2S path).
- Fancier sound: swap #5 for a Dayton Audio 2"/2.5" full-range + a small passive radiator.

---

## 4. Wiring

### 4a. MVP wiring (simple)
```
XVF3800 ── USB ─────────────▶ Pi 4 USB port         (mic in, processed)
MAX98357A  Vin → Pi 5V,  GND → Pi GND
           DIN → GPIO21,  BCLK → GPIO18,  LRCLK → GPIO19
Speaker  → MAX98357A screw terminals (4 Ω)
WS2812   DIN → GPIO10 (SPI MOSI) via 330 Ω,  5V → Pi 5V,  GND → Pi GND
Fan      → GPIO 5V / GND  (or a fan header)
Power    → USB-C 5.1V/3A
```

### 4b. AEC-correct wiring (matches Alexa "barge-in", recommended)
Route playback **through** the XVF3800 so its DSP has the echo reference:
```
Pi 4 ── USB ──▶ XVF3800  (USB soundcard: mic IN + speaker-reference OUT)
XVF3800 I2S OUT ──▶ MAX98357A ──▶ speaker
```
Now the array cancels your own music, so "Alexa, stop" works at volume. Zero extra parts —
just use the XVF3800's I2S output instead of the Pi's. (See §7 for why this matters.)

---

## 5. Software — step by step (self-contained build)

1. **Flash OS.** Raspberry Pi Imager → *Raspberry Pi OS (64-bit, Lite)*. Set hostname
   `openhome`, enable SSH + Wi-Fi. **Must be 64-bit** (wake word/VAD won't run on 32-bit).
2. **Enable the I2S DAC.** In `/boot/firmware/config.txt`:
   ```
   dtparam=audio=off
   dtoverlay=max98357a         # or hifiberry-dac
   dtparam=spi=on              # for WS2812 over SPI
   ```
   Reboot; confirm with `aplay -l` (playback) and `arecord -L` (XVF3800 shows as a capture device).
3. **Install Home Assistant** (self-contained option): HA Container via Docker, or HA OS on a
   second box for option B. Docs: https://www.home-assistant.io/installation/
4. **Wire up Assist** (STT + TTS + wake word) — all local:
   - STT: **wyoming-faster-whisper** (`base-int8` on Pi 4) — https://github.com/rhasspy/wyoming-faster-whisper
   - TTS: **wyoming-piper** (voice e.g. `en_US-amy-medium`) — https://github.com/rhasspy/wyoming-piper
   - Wake: **wyoming-openwakeword**, preload model **`alexa`** — https://github.com/rhasspy/wyoming-openwakeword
   - In HA: *Settings → Voice assistants → Assist* → pick Whisper + Piper + openWakeWord.
5. **Run the satellite** on the Pi:
   - Modern: **linux-voice-assistant** (ESPHome protocol; media player, timers, LED/button
     WebSocket API) — https://github.com/OHF-Voice/linux-voice-assistant
   - Classic/simple: **wyoming-satellite** tutorial — https://github.com/rhasspy/wyoming-satellite
   - Prebuilt Pi image (fastest): **PiCompose** — https://github.com/florian-asche/PiCompose
6. **Point wake word at `alexa`** and set `--mic-command` to the XVF3800 capture device
   (`arecord -D plughw:CARD=...`). It now answers to "Alexa."
7. **LEDs.** Drive the ring from the satellite's peripheral API (linux-voice-assistant WebSocket)
   or a small Python service using `adafruit-circuitpython-neopixel-spi` (SPI, GPIO10) — see §6.
8. **Music.** Add **Music Assistant** (https://www.music-assistant.io/) → play to the satellite
   media player (Spotify/local/DLNA).
9. **(Optional) smarter brain.** Assist → *Conversation agent* → wire an LLM (Google Gemini,
   OpenAI, or a local model via Ollama) for open-ended questions Alexa would punt on.

---

## 6. Light-ring language (WS2812 ×16, over SPI)

| State | Animation | Color |
|---|---|---|
| Idle | off / faint breathing | dim white 5% |
| Listening (post-wake) | full ring on | mint `#3ddc97` |
| Thinking (STT/intent) | spinner | mint → cyan |
| Speaking (TTS) | soft pulse | mint |
| Muted (HW mic switch) | solid | red `#ff5a5a` |
| Error / no network | double blink | amber `#f0b429` |

Drive over **SPI (GPIO10)**, *not* PWM — PWM's GPIO18 is taken by I2S BCLK (see audit).
`adafruit-circuitpython-neopixel-spi` needs no root and won't fight the audio clock.

---

## 7. Debug & design audit (the parts that bite people)

1. **GPIO clash: LEDs vs I2S.** The common `rpi_ws281x` PWM path uses **GPIO18** — which I2S
   BCLK also uses. Two fixes, one chosen: **drive WS2812 over SPI (GPIO10)**. Enabled with
   `dtparam=spi=on`. *Adjustment: BOM/wiring updated to SPI, not PWM.*
2. **Barge-in / AEC reference.** If audio goes out the Pi's I2S but the mic array is on USB, the
   XVF3800 never sees what you're playing, so it can't cancel it — "Alexa, stop" fails over loud
   music. *Adjustment: recommend wiring 4b (playback through XVF3800) for true AEC.* MVP wiring 4a
   still works quietly; barge-in just degrades at high volume.
3. **Power budget.** Pi 4 (~15 W) + XVF3800 (~2.5 W) + amp/speaker peaks (~3 W) + 16 LEDs
   (up to ~0.9 A at full white). A 5.1 V/3 A supply is **marginal** if everything peaks. *Adjustments:*
   cap LED brightness (≤30%) and never full-white all 16; for headroom use a 5 V/4–5 A supply or a
   small separate 5 V buck for the LED ring + amp. Don't pull >1.5 A through the Pi's 5V pin.
4. **Whisper latency/heat on Pi 4.** `whisper-base-int8` ≈ 1.5–3 s and warms the SoC. *Adjustments:*
   heatsink + fan (in BOM + enclosure vents); if too slow, move STT to option-B server.
5. **Enclosure acoustics.** The speaker can vibrate the mic array and self-trigger. *Adjustments in
   SCAD:* mic array mounts on the **top plate**, speaker chamber **sealed** below the grille, add a
   foam gasket / rubber foot to decouple; keep the LED ring diffuser from rattling.
6. **Onboard-audio pop / wrong device.** `dtparam=audio=off` kills the headphone-jack pop; verify
   `arecord -L` and set the exact XVF3800 `plughw:` string in the satellite mic command.
7. **32-bit trap.** VAD/wake word need 64-bit OS. Flash the 64-bit Lite image.
8. **Wake-word false accepts.** openWakeWord `alexa` threshold defaults can over-trigger near a TV.
   Tune threshold / use **microWakeWord** for a lighter, tighter model.

---

## 8. Adjustments made vs the first mockup

- Mic upgraded **ReSpeaker v2.0 → XVF3800** (newer, cheaper $61, dual USB/I2S, better far-field).
- Satellite software **wyoming-satellite → linux-voice-assistant** (maintained; media/timers/LED API).
- LEDs moved **PWM → SPI** to free the I2S clock (audit #1).
- Added the **AEC-correct audio path** so barge-in matches Alexa (audit #2).
- Power supply guidance upgraded for LED+amp headroom (audit #3).

---

## 9. Upgrade path
- **Better ears/voice:** XVF3800 "with case" option, or add a second Pi as a dedicated HA/STT server.
- **Better sound:** 2.5" full-range + tuned passive radiator; stereo = second MAX98357A (SD pin = L/R).
- **Physical mute:** hardware slide switch cutting XVF3800 mic power → drives red ring (real Alexa parity).
- **Matrix/voice PE parity:** compare against Home Assistant *Voice Preview Edition* ($59 prebuilt) —
  our build trades polish for a bigger speaker, bigger array, and a hackable brain.

---

## 10. All part links (flat list)
- [Raspberry Pi 4 (4 GB)](https://www.adafruit.com/product/4296)
- [microSD 32 GB A2](https://www.amazon.com/dp/B09X7BK27V)
- [ReSpeaker XVF3800 4-Mic Array](https://www.seeedstudio.com/ReSpeaker-XVF3800-USB-Mic-Array-p-6488.html)
- [MAX98357A I2S amp](https://www.adafruit.com/product/3006)
- [3" 4 Ω 3 W speaker](https://www.adafruit.com/product/1314)
- [NeoPixel Ring 16](https://www.adafruit.com/product/1463)
- [Official USB-C PSU](https://www.raspberrypi.com/products/type-c-power-supply/)
- [Heatsink + fan](https://www.amazon.com/dp/B07VVDN9K3)
- [Heat-set inserts](https://www.amazon.com/dp/B08SQ4NVHW)
- [Jumper wires](https://www.amazon.com/dp/B07GD2BWPY)

### Software
- [Home Assistant](https://www.home-assistant.io/installation/)
- [Assist / voice control](https://www.home-assistant.io/voice_control/)
- [linux-voice-assistant (satellite)](https://github.com/OHF-Voice/linux-voice-assistant)
- [wyoming-satellite (classic)](https://github.com/rhasspy/wyoming-satellite)
- [wyoming-openwakeword (wake "alexa")](https://github.com/rhasspy/wyoming-openwakeword)
- [wyoming-faster-whisper (STT)](https://github.com/rhasspy/wyoming-faster-whisper)
- [wyoming-piper (TTS)](https://github.com/rhasspy/wyoming-piper)
- [openWakeWord](https://github.com/dscripka/openWakeWord)
- [Music Assistant](https://www.music-assistant.io/)
- [PiCompose (prebuilt Pi image)](https://github.com/florian-asche/PiCompose)
- [NeoPixel over SPI](https://github.com/adafruit/Adafruit_CircuitPython_NeoPixel_SPI)

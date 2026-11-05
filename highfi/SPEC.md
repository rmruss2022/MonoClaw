# HighFi — Product & Hardware Spec

**Source of truth.** Firmware, app, and landing all follow this document.

## 1. Product concept

A 510-thread cannabis/aromatherapy cart battery that is *also* a music player.
One-handed use: screw a cart into the top, press **Fire** to vape, press **Play**
to hear music from the onboard speaker. A phone web app is the full remote.

Design pillars:
- **One device, two jobs** — vaping and audio share the same cell, enclosure, and UI.
- **Local-first** — plays MP3s off a microSD card and hosts its own control app;
  no cloud account required. (Same philosophy as the openhome hub in this monorepo.)
- **Honest safety** — a heating element + Li-ion battery is not a toy. Every fire
  path has interlocks; the docs say plainly where the maker-grade boundary is.

## 2. Form factor

- Roughly a chunky 18650 flashlight: ~92 mm tall × ~26 mm diameter (18650 class),
  or a slimmer 18350 "mini" variant.
- Top: spring-loaded **510 connector** (magnetic adapter optional).
- Body: speaker grille, control cluster, USB-C, status LED/OLED.
- Materials: anodized aluminum body, PC/ABS end caps.

## 3. Subsystems

### 3.1 Compute
- **ESP32-S3-WROOM-1-N16R8** (dual-core LX7, 16 MB flash, 8 MB PSRAM).
- Rationale: WiFi (hosts the controller app + WebSocket), BLE 5 (app control &
  WiFi provisioning), lots of I2S/DMA for glitch-free audio, USB-OTG for
  flashing/mass-storage.
- **Honest BT-audio caveat:** ESP32-S3 is **BLE-only** — it does *not* do Classic
  Bluetooth A2DP, so it can't stream to standard Bluetooth speakers/headphones.
  HighFi's primary output is its **onboard I2S speaker**. Bluetooth-out is a v2
  option requiring either the original ESP32 (Classic BT) as an audio co-processor
  or a dedicated BT-transmitter module (e.g. KCX_BT_EMITTER / BM83). Documented,
  not faked.

### 3.2 Audio
- Source: **microSD** (SDMMC 1-bit) for the music library; a few tracks can also
  live in flash (LittleFS). App can upload tracks over WiFi.
- Decode: MP3 / AAC / WAV / FLAC via the `ESP32-audioI2S` decoder pipeline.
- Output: **MAX98357A** I2S class-D amp → 4 Ω / 3 W micro speaker. Software volume.
- Optional 3.5 mm line-out (bypasses amp) for headphones.

### 3.3 Vape (510 coil driver)
- **510 connector** with spring center pin.
- Driver: low-side **N-channel MOSFET** (low Rds(on)) switching regulated power to
  the coil; **PWM** sets effective voltage (variable-voltage), with an optional
  buck/boost front-end for true constant-wattage.
- Activation: **Fire button** (default) and/or draw sensor (MEMS pressure). Standard
  **5-click** power lock/unlock.
- Sensing (ADC): coil resistance (no-atomizer / short detection), coil current
  (wattage estimate), battery voltage, NTC temperature on coil + cell.
- Setpoints: voltage 2.5–3.6 V or power 5–15 W, user-set in the app (clamped in
  firmware — the app can never command outside safe range).

### 3.4 Power
- Cell: single **18650** Li-ion (≈3000 mAh) or **18350** for the mini.
- Charge: **USB-C**, single-cell charger with power-path (BQ25895 preferred; TP4056
  acceptable for a bench prototype). Fuel gauge: **MAX17048**.
- Protection: dedicated protection IC (DW01+FS8205 or integrated) — over-charge,
  over-discharge, over-current, short.
- Rails: 3.3 V buck (TPS62840) for MCU/logic; amp + coil run from VBAT / boost.

### 3.5 UI (on-device)
- Buttons: **Fire**, **Play/Pause**, **Next**, **Prev**, **Vol±** (or rotary
  encoder), **Power**.
- Display: 0.96" **SSD1306 OLED** (track / battery / volume / coil status), *or* a
  **WS2812 RGB** ring for status + vibe. Both supported; OLED is the default.
- Optional haptic (vibration motor) for fire feedback and track change.

### 3.6 Connectivity
- **WiFi**: SoftAP (device serves the app + a captive portal) and STA (join home
  WiFi → control from anywhere on the LAN). `highfi.local` via mDNS.
- **WebSocket** `/ws`: realtime bidirectional state (now-playing, battery, coil
  temp, volume, session) — the same shape the app's emulator speaks.
- **HTTP** `/api/*`: REST for library, upload, config.
- **BLE**: alternate control + WiFi provisioning when no network yet.
- **OTA**: signed firmware update over WiFi.

## 4. Control protocol (device ⇆ app)

WebSocket JSON messages, versioned. Canonical shapes (firmware and the app emulator
MUST agree):

```jsonc
// device → app: full state snapshot on connect + deltas
{ "t": "state", "audio": { "playing": true, "track": {"id":"07","title":"...","artist":"...","durationS":214}, "positionS": 42, "volume": 60, "repeat":"off", "shuffle":false },
  "vape":  { "locked": false, "firing": false, "mode": "voltage", "setVolts": 3.2, "setWatts": 9, "coilOhms": 1.2, "coilTempC": 38, "sessionS": 0, "cartPresent": true },
  "power": { "battPct": 76, "charging": false, "voltage": 3.86 },
  "device":{ "name": "HighFi", "fw": "0.1.0", "wifi": "connected", "ip": "192.168.1.42" } }

// app → device: commands (firmware clamps/validates everything)
{ "t": "cmd", "audio": "play" }                     // play|pause|next|prev|stop
{ "t": "cmd", "seekS": 90 }
{ "t": "cmd", "volume": 55 }                         // 0..100
{ "t": "cmd", "playTrack": "07" }
{ "t": "cmd", "vape": "fire", "on": true }           // held; hard 10 s cutoff
{ "t": "cmd", "vapeSet": { "mode":"watts", "watts": 10 } }  // clamped 5..15 W / 2.5..3.6 V
{ "t": "cmd", "vapeLock": true }
{ "t": "cmd", "led": { "preset": "sunset" } }
```

## 5. Safety requirements (non-negotiable in firmware)

See [`hardware/SAFETY.md`](hardware/SAFETY.md). Enforced regardless of app input:
1. **10 s** hard fire cutoff.
2. **Short-circuit** cutoff (coil < 0.15 Ω) and **no-atomizer** lockout (open / >3 Ω).
3. **Over-temp** cutoff (coil or cell NTC over threshold).
4. **Battery** over-discharge / over-charge / over-current via protection IC + gauge.
5. **5-click lock** — device ships locked; fire disabled until unlocked.
6. Setpoints **clamped in firmware**; the app is untrusted input.
7. Independent **safety watchdog** task + hardware watchdog; fire defaults OFF on any
   fault, reset, or comms loss.

## 6. Out of scope (v1) / honest boundaries
- Not FDA/UL/CE certified; not for sale as-is. Nicotine devices need PMTA; cannabis
  hardware is state-regulated. This is a reference design for makers.
- No Classic-BT audio out (see §3.1). No cellular. No lossless streaming from cloud.

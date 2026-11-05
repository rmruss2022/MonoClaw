# HighFi — Architecture

Three deliverables, one shared control protocol (see [`SPEC.md`](SPEC.md) §4).

```
┌─────────────┐     WebSocket /ws (JSON)      ┌──────────────────────────┐
│  Web app     │  ◄─────── state deltas ──────  │  ESP32-S3 firmware        │
│ (controller) │  ──────── commands ─────────►  │                          │
│  Vite + TS   │     HTTP /api/* (library)      │  audioTask  (core 1)      │
│  emulator ▲  │                                │  netTask    (core 0)      │
└─────┬───────┘                                │  controlTask + safety WDT │
      │ same protocol                          │  uiTask                   │
      ▼ (no hardware)                          └──────┬──────────┬─────────┘
 in-app emulator                                      │ I2S      │ 510/MOSFET
                                                       ▼          ▼
                                                 MAX98357A     coil driver
                                                  speaker      (PWM + sense)
```

## Firmware (ESP32-S3, PlatformIO / Arduino-ESP32 + FreeRTOS)

Task model — safety-first, audio never blocks the fire path:

| Task | Core | Priority | Responsibility |
|------|------|----------|----------------|
| `controlTask` | 0 | **highest** | Buttons, fire state machine, **safety interlocks**, watchdog feed |
| `audioTask` | 1 | high | SD read → decode → I2S DMA (must not underrun) |
| `netTask` | 0 | normal | WiFi/AP, WebSocket + HTTP server, BLE, OTA |
| `uiTask` | 0 | low | OLED/LED render, haptics |

- **`AppState`** — one mutex-guarded struct mirrored to the app over `/ws`. Same
  fields as the protocol JSON. (Deliberately the same "single state, push deltas"
  shape as the openhome hub.)
- **Safety is independent of comms.** `controlTask` owns the coil GPIO. Net/app can
  only *request* fire via a flag; `controlTask` validates cart presence, resistance,
  temperature, lock state, and the 10 s timer every tick. Comms loss ⇒ fire OFF.
- **Modules** (`src/`): `audio/` (player, decoder, i2s), `vape/` (coil_control,
  safety), `power/` (battery, charger, gauge), `ui/` (buttons, display, leds),
  `net/` (wifi, ws_server, http_api, ble, ota), `storage/` (sd, config), `app_state`.

## App (Vite + TypeScript, mobile-first)

- **`api/deviceClient.ts`** — WebSocket client: connect, reconnect supervisor,
  snapshot + delta apply, typed command senders.
- **`api/emulator.ts`** — a full in-browser device speaking the *same* protocol:
  fake library, playback clock, battery drain, coil warm-up, safety lockouts. Gated
  behind a **dev flag / "🧪 Emulated device" toggle** so the whole UI is usable and
  testable with zero hardware. (This is the pattern Matthew liked from openhome's
  "Add test device" — build the emulator first, wire real hardware to the same seam.)
- **Screens:** Now Playing · Library (+ upload) · **Vape** (battery, coil status,
  wattage/voltage setpoint with firmware-clamped ranges, session timer, lock) ·
  Vibe/EQ (LED preset, EQ) · Device (WiFi provisioning, OTA, rename, calibrate).
- **State** is a single store fed by device deltas; UI is a pure render of it —
  reconnect and emulator swap in/out behind the same interface.

## Landing (static)

- Single-page `landing/index.html` + `styles.css`, no framework. Hero, how-it-works,
  features, specs, app preview, mockup gallery, waitlist CTA, FAQ (safety/legal),
  footer. Pulls renders from `hardware/mockups/`.

## Repo conventions
- TypeScript for the app; C++ (Arduino-ESP32) for firmware.
- No secrets in the tree. Mockup generation reads the Gemini key from `~/.gemini/imagekey`.
- Keep firmware/app protocol in lockstep with SPEC §4; changing one means changing both.

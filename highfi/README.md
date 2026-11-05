# HighFi 🎵🔋

**Screw in. Tune in.**

HighFi is a 510-thread cart battery with a built-in MP3 player and speaker. Screw
in your cart, hit the button, and play music at the same time — one pocket-sized
device for the whole session. It pairs with a mobile web app that doubles as the
device's remote control.

> ⚠️ **Safety & legal:** HighFi drives a heating element from a lithium-ion cell
> and is intended for legal cannabis/aromatherapy carts where permitted. This repo
> is an **experimental / maker reference design**, not a certified consumer product.
> Read [`hardware/SAFETY.md`](hardware/SAFETY.md) before building or powering anything.

---

## What's in here

| Path | What it is |
|------|-----------|
| [`SPEC.md`](SPEC.md) | Product + hardware spec (the source of truth) |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | System, firmware, and app architecture |
| [`firmware/`](firmware/) | ESP32-S3 firmware (PlatformIO) — audio, vape control, power, UI, net |
| [`app/`](app/) | Web app controller (Vite + TypeScript) — realtime remote over WebSocket, with a hardware-free emulator behind a dev flag |
| [`landing/`](landing/) | Marketing landing / info page |
| [`hardware/`](hardware/) | Bill of materials, pinout, safety, mockups |
| [`scripts/`](scripts/) | Mockup generation (Gemini) + tooling |

## The three pieces, one sentence each

1. **Device** — an ESP32-S3 drives a 510 coil (with real vape safety interlocks),
   decodes MP3/AAC off a microSD card to an onboard I2S speaker, and hosts a
   WebSocket control API over WiFi.
2. **App** — a mobile-first controller: now-playing transport, library, and a
   clearly-separated vape panel (battery, coil status, wattage, session timer).
   Runs fully against a built-in emulator so you can develop with zero hardware.
3. **Landing** — a single info/marketing page with the pitch, specs, app preview,
   and a waitlist CTA.

## Quick start (software, no hardware)

```bash
# Controller app against the emulator
cd app && npm install && npm run dev   # open the printed URL, toggle "🧪 Emulated device"

# Landing page
cd landing && python3 -m http.server 8080   # http://localhost:8080
```

Firmware build/flash instructions live in [`firmware/README.md`](firmware/README.md).

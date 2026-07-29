# The openhome box — reference hardware

![The openhome box](/assets/photo/box-studio.png)

An openhome box is just a computer you own. Buy a prebuilt one or build it. The
software is free and runs the same either way.

![The openhome box, at home](/assets/photo/box-lifestyle.png)

## Tiers

### Starter — "it runs the house"
For automations, a few cameras, and a small local model.
- **CPU**: modern 4–6 core mini-PC (Intel N100 / Ryzen equivalent)
- **RAM**: 16 GB
- **Storage**: 1× 1 TB NVMe (system + metadata) + 1× HDD for recordings
- **Local LLM**: 7–8B quantized (chat + simple reasoning)
- **Radios**: Matter-over-WiFi + a Zigbee/Thread USB stick

### Standard — "local AI, real NAS"
Comfortable local LLM + multi-camera recording + redundancy.
- **CPU**: 8-core (Ryzen 7 / Core i7 class)
- **RAM**: 32 GB
- **GPU**: entry discrete GPU or strong iGPU/NPU for video decode + LLM accel
- **Storage**: 2× NVMe (mirror) + 2–4× HDD in RAID for the NAS
- **Local LLM**: 13B quantized comfortably

### Power — "self-hosted everything"
Bigger models, many cameras, whole-home.
- **CPU**: 12+ cores
- **RAM**: 64 GB+
- **GPU**: 12–24 GB VRAM (run 30B+ or fast 13B, plus real-time vision)
- **Storage**: NVMe cache + large RAID array

## Radios & protocols
- **Matter / Thread** — default for new devices.
- **Zigbee** (Sonoff/ConBee stick + zigbee2mqtt), **Z-Wave** (Z-Wave JS stick).
- **Cameras**: ONVIF + RTSP (avoid cloud-only cameras — they defeat the purpose).

## Buy vs. build
- **Build**: any mini-PC or NAS chassis + drives + a radio stick. Flash the image,
  done.
- **Buy**: a prebuilt "open-home box" (a future first-party/partner option) — same
  open software, no assembly.

The principle: **whatever you run it on, you own it.** No device here should require a
vendor cloud to function on your LAN.

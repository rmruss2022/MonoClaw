# openhome Sound — speaker service & music app (design + tracker)

Whole-home audio for openhome: add Wi-Fi **and** Bluetooth speakers, group them into zones,
build a **surround / calibrated** system, and play music (Spotify first). This doc is the
living tracker — architecture, decisions, and the build checklist.

> Live app: [`/music`](/music) · Service: `services/hub/src/audio.ts` (Phase-0 in the hub;
> graduates to its own `services/speaker` process in Phase 1).

---

## Goals
- **Add any speaker.** Wi-Fi (Snapcast/AirPlay/Chromecast) as the backbone; **Bluetooth** as a
  single-room convenience.
- **Zones & groups.** Group rooms; play the same thing in sync, or different things per zone.
- **Surround + calibration.** Assign roles (L/R/center/surround/sub) and time-align speakers
  with per-speaker latency so a room sounds right.
- **Sources.** Spotify first; then local library, AirPlay-in, radio.
- **Local-first.** Sync/control never depends on a vendor cloud (Spotify account excepted).

## Architecture (maps onto the Pod Mesh stack — see [/docs/pod-mesh](/docs/pod-mesh))
| Layer | Real backend | Status |
|---|---|---|
| Multi-room sync | **Snapcast** (one client per speaker) | 🔌 modelled, not wired |
| Source bridge | **Music Assistant** (Spotify/AirPlay/Cast/DLNA) | 🔌 modelled |
| Spotify | OAuth + Web API (browse/control) + **librespot** (Connect playback) | ✅ OAuth + Web API · ⬜ librespot |
| Bluetooth | **BlueZ** A2DP sink | 🔌 modelled |
| Calibration | mic sweep → per-speaker delay/level | 🚧 stubbed (assigns delays) |

Everything currently runs as a **mock-but-real-shaped** model in `audio.ts` (same philosophy as
`home.ts`) so the app is fully clickable before the hardware/daemons are attached.

## Data model (`audio.ts`)
- **Speaker** — id, name, room, `kind` (wifi/bluetooth/airplay/chromecast/snapcast/pod), online,
  volume, muted, `zone`, `role`, `latencyMs`, `calibrated`.
- **Zone** — id, name, speakerIds, `surround`, master volume.
- **NowPlaying** — source, title/artist/album/art, playing, position/duration, zoneId.

## HTTP API (served by the hub)
- `GET /music` — the app.
- `GET /speakers` · `GET /audio/state` — speakers, zones, now-playing, spotify status, counts.
- `GET /audio/discover?kind=wifi|bluetooth` — mock discovery (→ mDNS / BlueZ scan later).
- `GET /audio/spotify/search?q=` — catalog search (→ Spotify Web API later).
- `POST /audio/command {cmd,...}` — `transport` · `volume` · `mute` · `add-speaker` ·
  `remove-speaker` · `create-zone` · `add-to-zone` · `remove-from-zone` · `dissolve-zone` ·
  `set-role` · `calibrate` · `spotify-connect` · `spotify-play` · `play-in-zone`.

## Build checklist
**Done (v0 — app + model)**
- ✅ Speaker/zone/now-playing model with seeded rooms
- ✅ `/music` app: now-playing + transport, per-speaker & per-zone volume, grouping
- ✅ Add speaker via Wi-Fi/Bluetooth discovery (mock)
- ✅ Surround roles + "calibrate room" (assigns per-speaker latency)
- ✅ Spotify scaffold: connect + search + play-to-zone

**Next (v1 — make it real)**
- ⬜ Snapcast server on hub + one real client (a Pi/ESP32 speaker) playing in sync
- ⬜ Music Assistant integration as the source/announce engine
- ✅ Spotify OAuth (Authorization Code) + Web API — profile, playlists, liked, top, search, play-to-device
- ✅ In-browser playback via **Spotify Web Playback SDK** — plays in the openhome tab on the Mac
  (mock-home stand-in for room speakers; no desktop app; Premium)
- ⬜ librespot on the box/pods so playback targets *our* real speakers (not the browser tab)
- ⬜ Real discovery: mDNS/Snapcast (Wi-Fi) + BlueZ (Bluetooth A2DP)
- ⬜ Real calibration: mic sweep → measured delay + level trim per speaker
- ⬜ Persist speakers/zones/calibration (ties into the hub persistence milestone)
- ⬜ Announce/intercom hooks (broadcast TTS, room↔room) — shares this service

## Open questions
- Bluetooth is single-sink — do we allow BT speakers *inside* a synced zone, or flag them "solo only"?
- Calibration UX: auto (mic sweep) vs. manual delay tuning — ship auto, expose manual.
- Per-zone independent sources vs. one house source at a time (Snapcast supports multiple streams).

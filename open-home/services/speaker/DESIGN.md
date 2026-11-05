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

---

## Room calibration & spatial audio (implemented)

Each room can be tuned into a time-aligned, level-matched spatial soundstage —
the technique behind Trueplay/Audyssey/Dirac, mapped onto our Snapcast layer
(`services/hub/src/calibration.ts`).

1. **Time-align** — sound from the farthest speaker takes longest to reach the
   seat, so every closer speaker is delayed by `(d_far − d) / c`, where
   `c = 331.3·√(1 + T/273.15)` m/s (temperature-corrected speed of sound). The
   delay is applied as each **Snapcast client's `latency`**.
2. **Level-match** — closer speakers are louder (inverse-square), so each gets a
   trim of `20·log10(d / d_far)` dB (attenuate-only, capped at −9 dB; sub gets a
   small boost allowance). Applied as **Snapcast client volume**.
3. **Spatialize** — a role→channel **matrix upmix** turns stereo into
   L / R / center / surround / sub / virtual-height (a passive matrix decode:
   center = ½(L+R), surround = ½(L−R) with a Haas delay, sub = lowpass, height =
   highpass differential). Roles auto-suggest from speaker count (2→L/R … 6→5.1).

Profiles persist per room (`.data/room-calibration.json`) and annotate each
speaker in `/audio/state` with `{role, delayMs, trimDb}`. The **Calibrate**
wizard on `/speakers` captures per-speaker distance + room temperature, computes
the profile, and shows the resulting delays/trims before applying.

**Boundary:** the numbers are real and correct, and are pushed to Snapcast — but
the audible spatial result needs the Snapcast server + one client per speaker
running on the hub (see [Run on your Pi](/docs/run-hub)). A future **auto** path
replaces manual distances with a mic sweep (log-chirp → cross-correlate the
impulse for per-speaker delay), Trueplay-style.

*Refs: speaker time-alignment (speed-of-sound delay) and Snapcast per-client
latency/volume — see Calculator Academy, Trinnov, and the Snapcast docs.*

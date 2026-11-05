# Slipstream (Chase) — Handoff

**AI video object-tracker / follow-cam.** Load a video, pick an object (e.g. a car),
and it keeps that object centered and zoomed as it moves across the frame —
auto-reframing the shot. Built for race footage (cars in a sand-dune race).

## What it is / how it works
- **Fully in-browser ML** — object detection via **COCO-SSD / TensorFlow.js**. No
  API keys, no server-side video processing. The user's video never leaves the device.
- **Server is a thin host** — `server.py` (Python stdlib, ~355 lines) just serves the
  single-page app and handles the optional auth gate. All the "AI" runs client-side.

## Run / deploy
- **Local:** `CHASE_PORT=18833 python3 server.py` (env: `CHASE_PORT`, `CHASE_BASE` e.g. `/track`).
- **Production:** runs on the droplet under systemd (`chase.service`), fronted by the
  bedrock tunnel at **https://slipstream.bedrock.casa** (ingress → `127.0.0.1:18843`).
- **Deploy a change:** edit `server.py`, then `systemctl restart chase.service`.

## Auth
- Optional email/password gate, enabled with `CHASE_AUTH=1` on the public instance.
- pbkdf2-sha256 (200k) + in-memory sessions (30-day TTL); users in `data/users.json` (chmod 600).
- Endpoints: `POST /api/signup`, `POST /api/login`, `POST /api/logout`.

## Current state
- **Working MVP:** object selection + follow/zoom reframing on an uploaded/loaded
  video, dark "Slipstream" UI, sign-in page, public deploy live behind login.

## Known gaps / next steps (good handoff backlog)
- **Export the reframed result** — right now it *displays* the follow-cam; add a
  "record/export" so users get an MP4 of the reframed clip (MediaRecorder on the canvas).
- **Smoothing** — damp the crop motion (easing/kalman) so the follow-cam isn't jittery.
- **Multi-object / re-acquire** — handle the tracked object leaving + re-entering frame.
- **Mobile camera capture** — allow live capture, not just file load.
- **Tighten the bedrock port** — confirm whether prod serves on 18833 or 18843 and
  make `chase.service` + the tunnel ingress agree (there are two listeners today).
- **Account polish** — password reset, per-user saved clips.

## File map
- `server.py` — host + auth + the embedded single-page app (HTML/JS/COCO-SSD).
- `data/users.json` — accounts (runtime; gitignored-worthy).
- `tunnel.sh` — legacy quick-tunnel launcher (superseded by the bedrock named tunnel).

# Contributing to openhome

![Build openhome with us](/assets/photo/community.png)

openhome exists so people own their homes. Contributions should push toward that:
local-first, open protocols, no lock-in.

## Ground rules
- **No mandatory cloud.** Core features must work on the LAN with the internet off.
- **Open protocols only** for device support (Matter, Zigbee, Z-Wave, ONVIF/RTSP, MQTT).
- **Privacy by default.** Don't add telemetry or off-box data flows that aren't opt-in.
- **Safety-critical actions** (unlock, disarm) must stay policy-gated and confirmable.

## Dev setup
```bash
git clone <repo>
cd open-home
npm install
npm run dev            # runs the hub
```

## Where things go
- New device support → `services/device-gateway` adapter + `packages/shared` types.
- Vetted hardware → add a row under `integrations/`.
- UI → `apps/app`.

## PRs
Small, focused, with a short description of *why*. Update `ROADMAP.md` if you move a
box from ⬜ to ✅. License is AGPL-3.0 — by contributing you agree your changes ship
under it.

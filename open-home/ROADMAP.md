# Roadmap

![The openhome box — a local-first home server you truly own](/assets/photo/box-lifestyle.png)

> **open-home** — an open-source home automation system you actually own. A box in your
> home runs local LLMs (or reaches to the cloud by choice), speaks open protocols to your
> cameras, locks, and lights, and an agent runs the whole thing. No subscription to unlock
> your own front door.

Status legend: ✅ done · 🚧 in progress · ⬜ planned

![openhome camera](/assets/photo/camera.png) ![openhome smart lock](/assets/photo/lock.png) ![openhome lighting](/assets/photo/lighting.png)

## Phase 0 — Scaffold (now)
- ✅ Monorepo layout + docs (README, ARCHITECTURE)
- ✅ Root workspace tooling (npm workspaces, TypeScript)
- 🚧 Hub skeleton: REST + WebSocket + health endpoint
- ⬜ Shared device schema (`packages/shared`)

![One private hub, your devices orbiting it — open protocols, no cloud](/assets/ecosystem.png)

## Phase 1 — Local core (MVP)
- ⬜ MQTT event bus wired into the hub
- ⬜ One real adapter end-to-end: **ONVIF/RTSP camera** → live view + snapshot
- ⬜ Storage service: record clips, retention policy, metadata DB
- ⬜ Web dashboard: device list, live camera tile, event feed
- ⬜ Local LLM agent loop (Ollama) with 3 tools: list devices, get status, search clips

![An agent that watches over your home — private, on your side, not surveillance](/assets/agent.png)

## Phase 2 — Control + automations
- ⬜ Smart lock adapter (Matter) with policy-gated unlock + confirmation
- ⬜ Lighting adapter (Matter/Zigbee)
- ⬜ Rules engine: declarative automations + schedules
- ⬜ Agent can take actions (with approval policy for sensitive ones)
- ⬜ Push notifications to the app

## Phase 3 — Ownership + polish
- ⬜ Multi-user accounts + per-room/device scopes
- ⬜ Cloud model opt-in + per-stream privacy toggles
- ⬜ Encrypted metadata backup/export
- ⬜ Mobile app (React Native)
- ⬜ Remote access guide via user-owned VPN (Tailscale/WireGuard)

## Phase 4 — Ecosystem
- ⬜ Adapter SDK so anyone can add a device
- ⬜ Compatibility program: vetted cameras / locks / lights (`integrations/`)
- ⬜ Reference hardware: DIY build guide + prebuilt "open-home box" spec
- ⬜ One-command installer image (like Home Assistant OS)

## Non-goals
- No proprietary cloud dependency for core function.
- No feature gated behind a subscription.
- No telemetry the user didn't turn on.

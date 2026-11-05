# Architecture

![The openhome box — every component runs here, on your box](/assets/photo/box-studio.png)

openhome is a local-first monorepo. Every component runs on the home box; the cloud
is optional and opt-in.

```
                          ┌─────────────────────────────┐
                          │        apps/app             │
                          │   web + mobile control UI   │
                          └──────────────┬──────────────┘
                                         │ HTTPS / WebSocket
                          ┌──────────────▼──────────────┐
                          │        services/hub         │
                          │  ┌───────────────────────┐  │
                          │  │      Agent loop       │  │  ← local LLM (Ollama)
                          │  │  monitor · automate · │  │     or cloud (opt-in)
                          │  │  answer · notify      │  │
                          │  └───────────────────────┘  │
                          │  REST API · rules engine ·  │
                          │  event bus · auth           │
                          └───┬──────────────┬──────────┘
                              │ MQTT         │ SQL / files
              ┌───────────────▼──┐   ┌───────▼──────────────┐
              │ device-gateway   │   │      storage         │
              │ Matter · Zigbee  │   │ recordings · backups │
              │ Z-Wave · ONVIF   │   │ metadata DB (SQLite/ │
              │ RTSP · MQTT      │   │ Postgres)            │
              └───┬────┬────┬────┘   └──────────────────────┘
                  │    │    │
              cameras locks lights ...   (integrations/)
```

## Principles

1. **Local-first.** The LAN is the source of truth. Internet outage ≠ home outage.
2. **Event-driven.** Devices publish events to an MQTT bus; the hub subscribes and reacts.
3. **Protocol-agnostic core.** The hub speaks a normalized device schema
   (`packages/shared`); adapters translate vendor protocols into it.
4. **Agent as operator, not gatekeeper.** The agent automates and informs. Safety-
   critical actions (unlock door, disable alarm) require explicit policy + confirmation.
5. **Privacy by construction.** Video/audio never leaves the box unless a user
   explicitly enables a cloud feature for a specific stream.

## Components

![Setting up the hub](/assets/photo/install.png)

### services/hub — the brain
- **API**: Fastify REST + WebSocket for the app and integrations.
- **Event bus**: subscribes to MQTT, normalizes events, fans out to rules + agent.
- **Rules engine**: declarative automations ("if door unlocked after 11pm and no one home → notify").
- **Agent loop**: an LLM-driven operator. Tools = device controls, footage search,
  notifications. Model is pluggable: local (Ollama) by default, cloud opt-in.
- **Auth**: local accounts, per-device/room scopes, and an approval policy for
  sensitive actions.

### services/device-gateway — the hands
Adapter processes that bridge physical protocols to the MQTT bus using the shared
device schema. Planned adapters:
- **Matter / Thread** (via `matter.js`) — the strategic default going forward.
- **Zigbee** (via zigbee2mqtt) and **Z-Wave** (via Z-Wave JS).
- **Cameras**: ONVIF discovery + RTSP ingest; snapshots and event clips to storage.
- **Generic MQTT** for DIY / ESPHome devices.

### services/storage — the NAS layer
- Recording storage with retention policies and ring-buffer eviction.
- Metadata DB (SQLite for single-box, Postgres for bigger installs).
- Backup/export so users can move their data off the box any time.

### apps/app — the face
- Web dashboard first (Vite + React), then React Native mobile.
- Live camera views, device control, automation editor, agent chat.
- Talks only to the hub — never directly to the cloud.

### packages/shared — the contract
- Normalized `Device`, `DeviceEvent`, `Capability` types.
- Zod schemas so hub, gateway, and app validate the same shapes.

## Data flows

**Event:** device → gateway adapter → MQTT → hub bus → (rules + agent + app push).

**Command:** app/agent → hub API → MQTT command topic → gateway adapter → device.

**Agent query** ("who was at the door at 2pm?"): agent → storage (clip search) +
device metadata → LLM → answer, with the source clip linked in the app.

## Cloud, when you want it
Cloud is a per-feature toggle, never a requirement:
- Swap the agent's model provider to a cloud LLM for heavier reasoning.
- Optional encrypted off-site backup of the metadata DB (not raw video by default).
- Optional remote access via the user's own relay/VPN (e.g. Tailscale) — no open-home
  cloud in the middle.

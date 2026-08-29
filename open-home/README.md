# 🏠 openhome

**An open-source home automation system you actually own.**

![A calm, safe, connected home](/assets/photo/home-golden.png)

openhome is what you get when you cross an [OpenClaw](https://openclaw.ai)-style agent with
IoT, a companion app, and a NAS — all running on hardware in *your* home, under *your*
control. No monthly subscription to unlock your own front door. No vendor deciding to brick
your cameras. No cloud silently training on your living room.

> **Your home. Your data. Your keys.**

---

## One box. Your whole home. Zero cloud required.

![The openhome box](/assets/photo/box-studio.png)

You buy (or build) a small **openhome box** — a hub with storage and enough compute for a
local LLM. It runs everything on your LAN, speaks open protocols to your devices, and an
**agent** ties it together and runs the house. Unplug the internet and your home still works.

![The openhome box, at home](/assets/photo/box-lifestyle.png)

## Why openhome

The smart-home market is a graveyard of dead hubs, revoked features, and hostage data.
"Smart" today means "rented." openhome flips that:

- **Local-first.** Everything works on your LAN with the internet unplugged.
- **You own the data.** Recordings, logs, and models live on your disk — export or delete anytime.
- **Open protocols only.** Matter, Zigbee, Z-Wave, ONVIF/RTSP, MQTT. No proprietary lock-in.
- **Agent-run.** A local agent monitors, automates, and answers — *"did anyone come to the door while I was out?"* — from your own footage and your own model.
- **Cloud is opt-in.** Use a bigger cloud model when you want power; fall back to local when you want privacy.

## The ecosystem

![Your devices orbit one private hub — no cloud in the middle](/assets/ecosystem.png)

A Tapo-scale catalog — cameras, doorbell, locks, lights, plugs, sensors — but every device
is **local-first and open**, so you truly own it.

![openhome camera](/assets/photo/camera.png) ![openhome doorbell](/assets/photo/doorbell.png)

## Control from anywhere — that only talks to your box

![The openhome app](/assets/photo/app-hand.png)

One clean app for live views, device control, automations, and a chat with the agent that
runs your home. It talks **only** to your hub — never straight to a cloud.

## Ambient intelligence, not surveillance

![The openhome Pod](/assets/photo/pod-hand.png)

The **openhome Pod** puts the agent in every outlet — a wall-plug node with a local mic and
edge compute that forms a whole-home mesh. On-device wake word, a hardware mute switch, and
open firmware mean it listens *for you*, and you can prove it. See [Concepts](/docs/concepts).

---

## Explore

- **[Business plan](/docs/business)** — market, model, catalog, go-to-market
- **[Roadmap](/docs/roadmap)** — what's built vs. planned
- **[Architecture](/docs/architecture)** — how the pieces fit
- **[Brand](/docs/brand)** — identity, voice, palette
- **[Concepts](/docs/concepts)** — the Pod and beyond
- **[Hardware](/docs/hardware)** — the openhome box, three tiers

## Quick start (dev)

> ⚠️ Early scaffold. The hub runs; device adapters are next. See the roadmap.

```bash
cd open-home
npm install
npm run dev        # starts the hub + dashboard on http://localhost:4700
```

## License

Licensed under **AGPL-3.0** — on purpose. If you run openhome as a service for others, you
share your changes. The point is to keep it open forever. See [`LICENSE`](./LICENSE).

---

*Own your home. Not a subscription to it.*

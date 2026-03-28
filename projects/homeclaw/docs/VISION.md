# HomeClaw — The Developer's Home Intelligence Platform

> *Your home. Your models. Your data. Never theirs.*

---

## The Problem Nobody Has Actually Solved

Alexa knows what you ask it. Google Home knows when you wake up. Apple HomePod knows your voice patterns, your routines, your sleep schedule, your music taste. Every "smart" home product today is a surveillance device that happens to turn on lights.

The alternative — Home Assistant — is powerful but built for tinkerers willing to spend 40 hours on YAML config files. It's not a product, it's a hobby.

There is a massive, completely underserved market sitting between these two options:

**Developers, engineers, and technically literate people who:**
- Want a genuinely smart home that understands natural language
- Refuse to pipe their private conversations to Amazon/Google/Apple servers
- Want to run their own AI models (Llama, Mistral, Ollama, or any API)
- Want clean APIs and extensible integrations — not a locked ecosystem
- Are willing to pay for something that actually works out of the box

This market is estimated at **25-40 million people in the US alone** and growing rapidly as AI literacy spreads. Not one product exists specifically for them.

**HomeClaw is that product.**

---

## The Core Concept

HomeClaw is a **local-first, AI-native home intelligence platform** with three components:

### 1. The PuckNode — Hardware
A small, attractive plugin device (3" diameter, 1" thick puck form factor) that plugs directly into any standard outlet. Each PuckNode contains:
- **Microphone array** (3-mic beamforming for directional voice pickup, background noise cancellation)
- **Speaker** (1.5W, surprisingly good for size — for TTS responses and alerts)
- **WiFi + Bluetooth** (connects to your local network, discovers nearby BT devices)
- **IR blaster** (controls TVs, air conditioners, and millions of IR-compatible devices)
- **Ambient light sensor** (for automatic brightness/color temperature adjustment)
- **USB-A passthrough** (doesn't eat your outlet — you still get it back)
- **LED ring** (status indicator: listening/processing/responding/offline)
- **Local compute** (ESP32-S3 with onboard inference for wake word detection — nothing leaves the device until wake word triggered)

**Estimated BOM cost: $18-22 per unit**
**Target retail price: $49 per PuckNode, $129 for 3-pack**

### 2. The HomeClaw Hub — Software
Open-source Node.js server that runs on any machine (Mac, Linux, Raspberry Pi, NUC, old laptop):
- REST + WebSocket API for all integrations
- LLM routing layer (connect to Ollama locally, or any API: OpenAI, Anthropic, Mistral, Groq)
- Device registry and mesh networking for PuckNodes
- Integration engine with 40+ pre-built connectors
- Automation engine with natural language rule creation
- Local voice processing pipeline (wake word → transcription → LLM → TTS → response)
- Dashboard UI for configuration and monitoring

### 3. The Integration Ecosystem — Extensibility
Any developer can write a HomeClaw integration in under 30 minutes using the SDK. Ships with:
- **Lighting:** Philips Hue, LIFX, Govee, Nanoleaf, Kasa
- **Thermostat/Comfort:** Nest, Ecobee, Honeywell, Sensibo (AC control), Dyson
- **Media:** Sonos, Spotify, Apple Music, Plex, YouTube Music, Chromecast
- **Security:** Ring, Arlo, Eufy, local cameras via RTSP
- **Locks:** August, Schlage, Yale
- **Sensors:** Any Zigbee/Z-Wave sensor via USB dongle
- **Appliances:** Smart plugs (TP-Link, Meross), robot vacuums (Roomba, Roborock)
- **Calendar/Context:** Google Calendar, Apple Calendar, Outlook — for context-aware automation
- **Weather:** Local weather API for predictive climate control
- **Custom webhooks:** Any HTTP endpoint

---

## Why This Beats Everything Else

### vs. Amazon Echo / Google Home / Apple HomePod

| Feature | Big Tech Voice | HomeClaw |
|---------|---------------|----------|
| Your data on their servers | ✅ Always | ❌ Never |
| Requires internet to function | ✅ Yes | ❌ No (local-first) |
| Model you run | Their model | Your choice |
| Open API | ❌ Locked | ✅ Fully open |
| Works without subscription | ❌ Degraded | ✅ Full functionality |
| Can understand context across devices | Limited | ✅ Mesh awareness |
| Programmable automations | Basic | ✅ Natural language + code |
| Offline mode | ❌ | ✅ Full offline with local LLM |

### vs. Home Assistant

| Feature | Home Assistant | HomeClaw |
|---------|----------------|----------|
| Setup time for non-expert | 20-40 hours | 15 minutes |
| Voice assistant quality | Basic (Assist) | Full LLM reasoning |
| Hardware included | ❌ DIY | ✅ PuckNode |
| Out-of-box experience | Poor | Polished |
| Developer-friendly API | Good | ✅ Excellent |
| Natural language automations | ❌ | ✅ |
| Target user | Power tinkerer | Technical but time-poor |

---

## The Technical Architecture

```
PuckNode (Hardware)
    │
    │  Wake word detected locally (ESP32-S3)
    │  Audio stream sent to Hub over LAN (encrypted)
    ▼
HomeClaw Hub (Your Machine / Raspberry Pi / NUC)
    │
    ├── Voice Pipeline
    │   ├── STT: Whisper (local) or Deepgram API
    │   ├── LLM Router → Ollama (local) | OpenAI | Anthropic | Groq
    │   └── TTS: Piper (local) or ElevenLabs | OpenAI TTS
    │
    ├── Intent Engine
    │   ├── Device Commands ("turn off living room lights")
    │   ├── Automation Rules ("when I say goodnight, run bedtime routine")
    │   ├── Information Queries ("what's on my calendar tomorrow")
    │   └── Contextual Memory ("remember I like it 68 degrees at night")
    │
    ├── Integration Layer
    │   ├── HTTP/REST integrations (most smart home devices)
    │   ├── Local Zigbee/Z-Wave bridge
    │   ├── MQTT broker for IoT devices
    │   └── WebSocket real-time event bus
    │
    └── Dashboard UI (localhost:8080)
        ├── Device map / floor plan
        ├── Automation editor (visual + natural language)
        ├── Conversation history
        ├── Integration marketplace
        └── PuckNode management

No traffic leaves your network unless you explicitly configure a cloud API.
```

---

## The PuckNode Form Factor — Why a Plug-In Device

Most people don't want to mount hardware on walls or deal with wiring. A plug-in device:
- **Zero installation** — plug in and it works
- **Optimal placement** — every room has outlets, and outlets are at conversation height
- **No damage** — apartment-friendly
- **USB passthrough** — you lose nothing
- **Dense mesh possible** — put one in every room for whole-home coverage, each one costs $49

The closest existing products (Alexa plug-in, Google Mini) prove the market. We take the same form factor and give it to developers with full local processing, open APIs, and BYOM.

---

## The Business Model

### Hardware
- PuckNode single: **$49**
- PuckNode 3-pack: **$129**
- PuckNode Pro (with Zigbee/Z-Wave radio built in): **$79**
- Manufactured at $18-22 BOM, assembled by PCBA partner (JLCPCB or similar)

### Software (Optional — Hub is always free/open source)
- **HomeClaw Hub**: Free, open source, MIT license
- **HomeClaw Cloud Sync** (optional): $4.99/month — syncs settings/automations across homes, remote access via secure tunnel, mobile push notifications
- **HomeClaw Pro**: $9.99/month — priority support, advanced AI features, multi-home management, team sharing
- **The SDK is always free** — developer adoption is the moat

### The Flywheel
Hardware sales → developers buy it, build integrations → integration library grows → more users buy hardware → larger market → enterprise/MDU (multi-dwelling unit) sales

### Enterprise / MDU (Long Term)
- Hotels, apartment buildings, student housing — all want smart room control without cloud lock-in or per-room subscription fees
- HomeClaw white-label for property management companies
- **ACV per 200-unit apartment building: $40-80K hardware + $5K/year software**

---

## Target Customer Personas

### Persona 1 — "The Developer Homeowner" (Primary)
- Software engineer, 28-42
- Owns or rents a home/apartment
- Has Hue lights, maybe a Nest, maybe an Echo they don't fully trust
- Reads Hacker News, follows tech privacy discourse
- Would pay $150-200 to get a system that respects their data and they can actually hack on
- **TAM segment: ~8M people in US**

### Persona 2 — "The Privacy-Conscious Early Adopter"
- Technical but not necessarily a software engineer
- Doctor, lawyer, executive — someone whose conversations at home matter
- Actively looking for non-Amazon/Google voice assistant options
- Willing to pay premium for privacy guarantee
- **TAM segment: ~15M people in US**

### Persona 3 — "The AI Tinkerer"
- Already running Ollama, has played with local LLMs
- Wants to connect their AI experiments to real-world devices
- HomeClaw is the best possible platform for their weekend projects
- Will become an evangelist and integration contributor
- **TAM segment: ~3M people in US (but punches above weight in influence)**

---

## GTM Strategy

### Phase 1 — Developer Launch (Month 1-6)
- Open source the Hub on GitHub
- Launch a killer README and docs site
- Post on Hacker News, r/homeautomation, r/selfhosted, r/LocalLLaMA
- Developer community builds traction before hardware ships
- **Goal: 5,000 GitHub stars, 500 Discord members**

### Phase 2 — Hardware Kickstarter (Month 4-6)
- Crowdfund PuckNode hardware — validates demand + funds first manufacturing run
- Target: $250K raise, minimum 5,000 units
- Kickstarter is also a massive PR channel for this category
- **Goal: $500K raise, 10,000 units**

### Phase 3 — Integration Marketplace (Month 6-12)
- Developer community has built 100+ integrations by this point
- Launch Integration Marketplace — discoverability and curation
- First party "featured integrations" for major platforms
- **Goal: 200+ integrations, 50K active Hub installs**

### Phase 4 — Scale (Year 2+)
- Retail channel (Amazon, B&H, Micro Center)
- Enterprise/MDU sales team
- HomeClaw Pro subscription growth
- International expansion

---

## Why Now

1. **Local LLM quality crossed the threshold** — Llama 3.1, Mistral, Gemma 2 running locally on a Mac Mini are good enough for home automation use cases. This wasn't true 18 months ago.

2. **Privacy awareness is at an all-time high** — Post-Cambridge Analytica, post-Alexa recordings leaking, people are actively seeking alternatives. The "developers who care about privacy" segment is growing fast.

3. **Raspberry Pi supply is back** — The Pi 5 is in stock, cheap, and powerful enough to run Whisper + Ollama + HomeClaw Hub simultaneously. The local hardware story finally works.

4. **PCBA costs are at historic lows** — A $20 BOM for a capable IoT device with mic array and WiFi was $50 two years ago.

5. **Home Assistant proved the demand exists** — 800K+ active installations of a product that requires 40 hours of setup. What would happen with one that requires 15 minutes?

---

## What We're NOT Doing

- **Not building a cloud AI service.** We are not competing with OpenAI or Anthropic.
- **Not locking you into our hardware.** The Hub works with any microphone.
- **Not building a subscription wall around basic features.** The software is always free.
- **Not collecting your data.** We don't even have a telemetry option by default.
- **Not fighting Home Assistant.** We're not the same product. We complement them.

---

*HomeClaw. Your home, your rules, your model.*

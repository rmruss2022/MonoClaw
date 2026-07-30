# openhome — Business Plan

![openhome ecosystem](/assets/ecosystem.png)

> **Your home. Your data. Your keys.**
> openhome is an open-source, local-first smart-home platform — a hub + agent + a Tapo-scale
> catalog of cameras, locks, lights, plugs, and sensors — that people **own outright**. No
> subscription to unlock your own front door, no vendor cloud holding your footage hostage.

*This is a working plan. Market figures are third-party estimates (sources at the end);
financials are illustrative assumptions to be validated, not forecasts.*

![The openhome box](/assets/photo/box-studio.png)

---

## 1. Executive summary

The smart home is booming but broken. It's a **$130–230B market growing ~12–26%/yr**
(estimates vary by firm), yet it runs on rented software: dead hubs, revoked features,
subscriptions to view your own cameras, and data flowing to clouds you don't control.

openhome flips the model. You buy (or build) a small **openhome box** — a hub with storage
and enough compute for a local LLM. It runs everything on your LAN, speaks open protocols
(Matter, Zigbee, Z-Wave, ONVIF/RTSP), and an **agent** operates the house and answers
questions from your own footage and your own model. Cloud is strictly opt-in.

We make money the honest way: **hardware sales** (the box + first-party devices), a
**certification program** ("openhome Certified"), and **optional cloud services** (remote
access, off-site backup, hosted-LLM credits) that add convenience but never gate core
function. Precedent: **Nabu Casa** (Home Assistant) reached ~$4M/yr, subscriber-funded, no
investors — and that's *software only*. We add hardware margin and a brand with a point of view.

---

## 2. Mission & thesis

**Mission:** give people true ownership of their homes — the devices, the data, and the
intelligence that runs them.

**Thesis:** three forces make now the moment:
1. **Privacy backlash** — people are done being the product; "local" and "own your data" now sell.
2. **Matter/Thread** — an open interoperability standard finally lets a neutral hub talk to everyone's devices.
3. **Local LLMs** — capable models now run on a $500–1500 box, so the "agent that runs your home" no longer needs the cloud.

No incumbent can fully follow us here: their business *is* the cloud lock-in and the data.

---

## 3. The problem

- **You rent your own home.** Camera history, smart-lock logs, even notifications sit behind monthly fees.
- **Hubs die.** When a vendor sunsets a product or gets acquired, your gear bricks.
- **Surveillance by default.** Footage and presence data leave the house; breaches and hand-overs follow.
- **Walled gardens.** Devices refuse to talk across brands; you're locked into one ecosystem.
- **The DIY escape is too hard.** Home Assistant is powerful but intimidating; normal people can't self-host it.

## 4. The solution

openhome = **one box, open protocols, an agent, and a brand that makes ownership easy.**

- **The openhome box** — plug-and-play hub: local storage (NAS), local LLM compute, radios for Matter/Zigbee/Z-Wave.
- **Open device support** — works with certified third-party gear *and* our own first-party line.
- **The agent** — monitors, automates, and answers ("who came to the door at 2pm?") from local footage + local model; cloud model opt-in.
- **The app** — clean control surface that talks only to your box.
- **Privacy by construction** — nothing leaves the house unless you flip a specific switch.

---

## 5. Market opportunity

| Metric | Estimate (2026) | Notes |
|--------|-----------------|-------|
| Global smart-home market | **$130B – $230B** | Wide range across firms; midpoint ~$180B |
| Growth (CAGR) | **~12% – 26%** | Strong across all estimates |
| Wedge segments | Cameras, locks, lighting, hubs | Tapo's exact catalog — proven demand |

**Beachhead (SOM):** privacy-conscious prosumers, self-hosters, the Home Assistant / r/homeautomation
/ Ubiquiti crowd — millions of people who already distrust Ring/Nest and want local. Land here,
then expand to mainstream via the "just works" box.

**Adjacent tailwinds:** right-to-repair sentiment, EU data regulation, the "de-Google/de-Amazon"
movement, and rising home-insurance interest in monitored security.

---

## 6. Competitive landscape

| Player | Model | Strength | Where they can't follow us |
|--------|-------|----------|----------------------------|
| **Tapo / TP-Link** | Cheap first-party devices, app, optional cloud | Price, breadth, retail reach | Data stays theirs; closed; no local agent |
| **Ring / Nest (Amazon/Google)** | Hardware loss-leader + subscription + ads/data | Brand, polish | Their business *is* the cloud & data |
| **Wyze** | Ultra-cheap cameras + subscription | Price | Trust (breaches); cloud-dependent |
| **Ubiquiti / UniFi** | Prosumer hardware, software free, local | Ownership ethos, quality | Not agent-driven; steep for normal users |
| **Home Assistant / Nabu Casa** | Open-source + optional cloud sub | Community, openness | Hard to self-host; no first-party hardware line/brand |
| **Apple Home** | Privacy-forward, closed ecosystem | Trust, integration | Closed; Apple-only; no ownership of a box/agent |

**Our whitespace:** *the only player that is open-source, local-first, agent-run, and
sells an easy owned box.* Home Assistant's openness + Ubiquiti's hardware ownership +
Tapo's catalog breadth + an AI agent — under one brand about ownership.

---

## 7. Product strategy — the catalog (Tapo as the map)

Tapo proves the shape of demand: hub, cameras, doorbell, locks, lighting, plugs, sensors,
NVR, even vacuums. We mirror that catalog but make every device **local-first and open**.

![openhome camera](/assets/photo/camera.png) ![openhome doorbell](/assets/photo/doorbell.png)
![openhome smart lock](/assets/photo/lock.png) ![openhome lighting](/assets/photo/lighting.png)

**Build vs. certify:** own the *hub* and a few *hero devices*; **certify** the long tail so
the catalog scales without us manufacturing everything.

| Category | openhome plan | Inspired by |
|----------|---------------|-------------|
| **Hub / box** ⭐ | First-party. 3 tiers (Starter/Standard/Power). The heart of the platform. | Tapo H200, Synology, UniFi Dream Machine |
| **Cameras** ⭐ | First-party ONVIF/RTSP cams w/ local recording; certify Reolink et al. | Tapo Cam, Reolink, Frigate |
| **Video doorbell** | First-party hero device. | Tapo/Ring doorbell |
| **Smart locks** | Certify Matter/Z-Wave locks first; first-party later. Policy-gated unlock. | Tapo PalmKey, August, Yale |
| **Lighting** | Certify Matter/Zigbee bulbs/switches; optional first-party. | Tapo Atom Link, Philips Hue |
| **Plugs & energy** | First-party smart plugs w/ local energy metering. | Tapo P-series |
| **Sensors** | Certify Zigbee/Thread motion/contact/temp. | Aqara, Tapo sensors |
| **NVR / storage** | The box *is* the NVR — multi-cam local recording. | Tapo NVR, Synology Surveillance |
| **The app** ⭐ | First-party. Control, live views, automations, agent chat. | Tapo app, HA Companion |
| **The agent** ⭐ | First-party. Our defining differentiator. | (nobody — this is our wedge) |
| **openhome Pod** ⭐ | First-party. Wall-plug ambient node: local mic + edge compute + Thread/WiFi mesh. Fills the home with senses; households buy several. Privacy-first (on-device wake word, hardware mute). | Amazon Echo — but local & auditable. See [Concepts](/docs/concepts) |

⭐ = first-party focus / where we invest.

---

## 8. Business model & revenue streams

Five streams, ordered by near-term weight. Rule: **core function is never behind a paywall.**

1. **Hardware — the box (primary).** Sell openhome boxes at healthy hardware margin (30–45%).
   Tiers from ~$299 to ~$1,499. This is the anchor.
2. **First-party devices.** Cameras, doorbell, plugs — Tapo-competitive pricing, ecosystem pull-through.
3. **openhome Certified (licensing).** A "Works with openhome" badge + test program. Partners pay
   for certification/listing; drives catalog breadth with near-zero COGS. (Mirrors "Works With Home Assistant.")
4. **Optional cloud services (opt-in, subscription).** Remote-access relay, encrypted off-site
   backup, hosted-LLM credits, priority support — ~$5–10/mo. Convenience, never a gate.
   (Nabu Casa proved this funds an OSS company.)
5. **Prosumer / SMB & support.** Multi-site, extended warranty, install partners, small-business security.

**Why this beats the incumbents' model:** they subsidize hardware to trap you in data/subscriptions.
We sell honest hardware + optional convenience, and our *brand promise is that we don't do the trap.*
That's the wedge and the marketing in one.

---

## 9. Open-source & certification strategy

- **AGPL-3.0 core** — hub, agent, adapters, app. Openness builds trust and a contributor flywheel;
  AGPL stops a giant from forking it into a closed cloud.
- **Open by protocol** — Matter/Zigbee/Z-Wave/ONVIF only. No device is a hostage.
- **Community-led** — public roadmap, adapter SDK, docs. The community writes device support faster than we could.
- **Certification = trust + revenue** — the badge means "verified local operation, no forced cloud."
  Consumers learn to look for it; partners pay to earn it.
- **Open core, commercial edges** — everything essential is free/open; we monetize hardware and
  *optional* hosted services, exactly where users happily pay for convenience.

## 10. Pricing (illustrative)

| Product | Price | Comp |
|---------|-------|------|
| openhome Box — Starter | **$299** | Below a Synology + sticks bundle |
| openhome Box — Standard | **$699** | vs. UniFi Dream Machine + NAS |
| openhome Box — Power | **$1,499** | Local-AI + multi-cam NVR |
| Camera (first-party) | **$39–89** | Tapo/Reolink range |
| Video doorbell | **$129** | Ring/Tapo range |
| Smart plug | **$14** | Tapo P-series |
| openhome Cloud (optional) | **$6.99/mo** | vs. Nabu Casa $6.50, Ring Protect |
| Certification (partner) | **annual fee + per-SKU** | vs. "Works With" programs |

## 11. Go-to-market

- **Phase A — Community & credibility.** Ship the open-source hub free. Win Hacker News,
  r/homeautomation, r/selfhosted, Home Assistant forums, privacy YouTube. Earn the "finally, local + easy" reputation.
- **Phase B — The box (crowdfunding).** Kickstarter/Crowd Supply for the first openhome box —
  the ownership story is *made* for crowdfunding; validates demand and funds the first run.
- **Phase C — DTC + marketplaces.** openhome store + Amazon; content-led (privacy, "own your home").
- **Phase D — Ecosystem & retail.** Certification partners, first-party device line, then retail once volume justifies it.
- **Developer motion throughout** — adapter SDK + bounties so the catalog outgrows our own team.

## 12. Financial model (illustrative, to validate)

Directional unit economics — assumptions, not forecasts:

| | Yr 1 (community + crowdfund) | Yr 2 (box GA + devices) | Yr 3 (ecosystem) |
|---|---|---|---|
| Boxes sold | 1,500 | 12,000 | 45,000 |
| Avg box price | $650 | $620 | $600 |
| Hardware gross margin | 30% | 35% | 38% |
| Cloud subscribers | 400 | 6,000 | 30,000 |
| Certification partners | 3 | 20 | 60 |
| **Rev (rough)** | **~$1.1M** | **~$8–9M** | **~$30M+** |

Key levers: box margin, attach rate of first-party devices, cloud-sub conversion (Nabu Casa
shows even single-digit % of an OSS base is a real business), and certification scaling.

## 13. Roadmap to market (ties to the tech ROADMAP)

- **Now → Q?:** OSS hub MVP (Phase 1: camera + storage + agent). Build community.
- **+1 quarter:** Reference box spec + installer image; crowdfunding prep.
- **+2 quarters:** Crowdfunding launch; certification program v1.
- **+3–4 quarters:** Box GA, first-party camera + doorbell, app polish, optional cloud services.
- **Year 2+:** Device catalog expansion, retail, prosumer/SMB.

## 14. Team & operations

Early hires in priority order: **embedded/hardware lead** (the box), **firmware/adapters**,
**app/design**, **agent/ML**, **community/devrel**, **ops/supply-chain**. Contract manufacturing
(ODM) for the box; open community for the long-tail adapters.

## 15. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| **Hardware is hard / capital-heavy** | Start with a reference spec + certified third-party boxes; crowdfund the first run; ODM not in-house factory |
| **Giants (Amazon/Google) copy "local"** | They can't abandon data/subscription revenue; AGPL + brand + community is the moat |
| **OSS monetization doubted** | Nabu Casa/Ubiquiti prove it; we add hardware margin on top |
| **Security liability (locks/cameras)** | Policy-gated actions, audits, responsible disclosure, no cloud attack surface by default |
| **Support burden for non-technical users** | The whole point of the box is "just works"; paid support tier; strong docs |
| **Matter fragmentation/immaturity** | Support Zigbee/Z-Wave/ONVIF today; ride Matter as it matures |

## 16. Why we win (the moat)

1. **Trust as a product.** "You own it" isn't a feature we bolt on — it's the whole brand, and incumbents structurally can't say it.
2. **The agent.** A local AI that actually runs the home is a capability no closed vendor is positioned to ship privately.
3. **Open ecosystem flywheel.** Community + certification make the catalog grow faster than any single company.
   Ambient **Pods** (see [Concepts](/docs/concepts)) turn the home into a mesh of local senses — the Alexa
   experience without the surveillance, provably, because the firmware is open.
4. **Hardware + open-source together.** Ubiquiti-style ownership economics with Home-Assistant-style openness — nobody else sits in that box.

## 17. Funding & the ask

Two viable paths, not mutually exclusive:
- **Subscriber/-community-funded** (the Nabu Casa route) — stay independent, no investors, slower.
- **Seed round** to fund the first hardware run + team — faster, needs a crowdfunding proof-point first.

**Recommended:** OSS + community now → crowdfunding to validate the box → optional seed to scale hardware.

---

## 18. Device sourcing & the v1 starter line (white-label strategy)

**The rule.** White-labeling is right for *commodity, low-risk* accessories and wrong for the
whole catalog. Rebranded hardware is a commodity trap — no moat, thin margins, and real liability
on cameras and locks. So: **white-label the cheap attach items, certify/partner the risky ones,
and never sell a device that can't run fully local.**

| Category | Day-1 play | Why |
|---|---|---|
| Plugs, bulbs, sensors, buttons | ✅ **White-label** | Commodity, low-risk, high-attach, easy to guarantee local |
| Cameras | ⚠️ **Certify + integrate** (ONVIF/RTSP, local NVR) | Security/privacy liability; a hacked "openhome cam" ends the brand |
| Locks | ⚠️ **Partner/resell** (Matter/Z-Wave) | Physical safety, BHMA/ANSI grading, legal liability |

**⚠️ Avoid Tuya as the core.** Most white-label smart-home startups are reskinned Tuya, which is
**cloud-dependent by default** — the opposite of our promise. Prefer **Zigbee, Matter-over-Thread,
Z-Wave, and ESPHome/ESP32** (flashable, provably local). ESPHome is the secret weapon: we own the
firmware and can truthfully say "you own it."

**Hidden dependency — the radio.** None of the low-power accessories work without a **Zigbee/Thread
coordinator inside the box.** The starter box must ship one (Silicon Labs EFR32-based). This is a
real BOM line people forget.

### v1 starter line — 5 accessories + the radio

Reference devices below are the ODM/white-label or certify targets — the ones to buy first, test,
and rebrand or badge.

| SKU | Protocol | Reference / ODM to start | ~Unit cost | Target retail |
|---|---|---|---|---|
| openhome Plug (energy) | Wi-Fi ESPHome *or* Zigbee | Athom Smart Plug V3 (ESPHome) · Third Reality Zigbee · Sonoff S60 | $8–12 | $14 |
| openhome Bulb (RGBWW) | Wi-Fi ESPHome *or* Zigbee | Athom RGBWW bulb (ESPHome) · Sengled/IKEA Zigbee | $6–9 | $14–19 |
| openhome Motion sensor | Zigbee / Thread | Aqara Motion P1 · Sonoff SNZB-03 · Third Reality | $5–8 | $15 |
| openhome Contact sensor | Zigbee / Thread | Aqara Door/Window P2 (Matter) · Sonoff SNZB-04 | $4–7 | $13 |
| openhome Button | Zigbee | Aqara Mini Switch · Sonoff SNZB-01 · Third Reality | $4–6 | $15 |
| **In-box radio** (dependency) | Zigbee + Thread | HA Connect ZBT-2 · Sonoff ZBDongle-E (EFR32MG21) | $12–20 | (in box) |

**Certify, don't build (day 1):**
- **Cameras** — Reolink (ONVIF/RTSP, local recording); also Amcrest. Frigate for local AI detection.
- **Locks** — Aqara U100/U200 (Matter-over-Thread) or Yale Assure 2 + Matter/Z-Wave module.

### Where to buy — verified exact products (v1)

Every link below was checked live. All run locally through the openhome hub.

| Product | Role | Protocol | Link |
|---|---|---|---|
| Home Assistant Connect ZBT-2 | In-box radio | **Zigbee + Thread** | [home-assistant.io](https://www.home-assistant.io/connect/zbt-2/) · [Amazon](https://www.amazon.com/dp/B0G34ZTW51) |
| Athom Smart Plug V3 | Plug (energy) | **Wi-Fi · ESPHome** (local) | [athom.tech](https://www.athom.tech/) |
| Athom RGBWW Bulb | Bulb | **Wi-Fi · ESPHome** (local) | [athom.tech](https://www.athom.tech/) |
| Aqara Motion Sensor P1 | Motion | **Zigbee 3.0** | [aqara.com](https://www.aqara.com/en/product/motion-sensor-p1/) |
| Aqara Door & Window Sensor P2 | Contact | **Matter-over-Thread** | [aqara.com](https://www.aqara.com/en/product/door-and-window-sensor-p2/) |
| Aqara Wireless Mini Switch | Button | **Zigbee 3.0** | [aqara.com](https://www.aqara.com/en/product/wireless-mini-switch/) |
| Reolink RLC-810A | Camera (certify) | **PoE · ONVIF/RTSP** (local NVR) | [reolink.com](https://reolink.com/product/rlc-810a/) |
| Aqara Smart Lock U100 | Lock (certify) | **Matter** (via Aqara hub) / Bluetooth | [aqara.com](https://www.aqara.com/en/product/smart-lock-u100/) |

**Why the radio earns its keep:** the ZBT-2 speaks *both* Zigbee (P1, Mini Switch) and Thread
(P2/Matter) — one ~$30 dongle covers both stacks.
**Lock caveat:** the U100 bridges to Matter *through an Aqara hub*; for no-bridge local, use **Z-Wave**
(Yale Assure Lock 2 + Z-Wave module) or the Thread-native **Aqara U200**.
**Play:** buy 1–2 of each, verify **fully-local** operation through the openhome hub, then pick the ODM
partner per SKU for the rebrand.

### More bulb options (pick by protocol)

| Bulb | Protocol | Why | Link |
|---|---|---|---|
| Athom RGBWW Bulb | **Wi-Fi · ESPHome** | flashable — we own the firmware | [athom.tech](https://www.athom.tech/) |
| Nanoleaf Essentials | **Matter-over-Thread** | standards-based, premium finish | [nanoleaf.me](https://nanoleaf.me/) |
| Innr E27 / GU10 | **Zigbee 3.0** | 36-SKU range, best value | [innr.com](https://innr.com/) |
| Sengled | **Zigbee** | cheap (note: end-device, doesn't repeat mesh) | [sengled.com](https://us.sengled.com/) |
| IKEA (ORMANÄS/TRÅDFRI) | **Zigbee** | cheapest | [ikea.com](https://www.ikea.com/) |
| Philips Hue | **Zigbee** | premium; pairs to our coordinator without a Hue bridge | [philips-hue.com](https://www.philips-hue.com/) |

### Going Z-Wave (locks & security layer)

Z-Wave is the **lock/security** layer — secure, its own sub-GHz band (no Wi-Fi congestion), long range.
⚠️ It needs its **own controller** — the ZBT-2 does *not* do Z-Wave; a Z-Wave box carries two radios.
⚠️ **Z-Wave has no real bulb ecosystem** — do lighting with a Z-Wave in-wall dimmer + a normal bulb, or
keep Zigbee/Matter bulbs above.

| Role | Product | Protocol | Link |
|---|---|---|---|
| Z-Wave controller | Zooz **ZST39 800 LR Stick** | Z-Wave Long Range (800) | [getzooz.com](https://www.getzooz.com/products/) |
| Lock | Yale Assure Lock 2 (Z-Wave) · Schlage BE469ZP | Z-Wave | [shopyalehome.com](https://shopyalehome.com/) |
| Plug (energy) | Zooz **ZEN04 / ZEN15** | Z-Wave | [getzooz.com](https://www.getzooz.com/products/) |
| Dimmer (lighting) | Zooz **ZEN72 / ZEN77** | Z-Wave | [getzooz.com](https://www.getzooz.com/products/) |
| Motion / multi | Zooz **ZSE11 Q Sensor** | Z-Wave | [getzooz.com](https://www.getzooz.com/products/) |
| Contact | Zooz **ZSE41 Open\|Close XS** | Z-Wave | [getzooz.com](https://www.getzooz.com/products/) |

### Benchmark — what Home Assistant / Nabu Casa actually ships (audit)

Our closest philosophical competitor. Note what they *build* vs. what they lean on the ecosystem for:

| Their product | What it is | Our equivalent |
|---|---|---|
| Home Assistant Green (~$99) | turnkey hub | openhome Box — Starter |
| Home Assistant Yellow | hackable PoE hub (CM4/CM5) | openhome Box — Standard |
| Connect ZBT-2 (~$30) | Zigbee + Thread USB radio | our in-box radio |
| Voice Preview Edition (~$59) | voice satellite (Echo-like) | openhome mini / Pod |
| HA OS · Assist · Music Assistant | local voice + automation | our hub + agent |

**Takeaway:** they build the **hub + radio + voice box** and **do not** make sensors, bulbs, or locks —
they lean on the open Zigbee/Z-Wave/Matter/ESPHome ecosystem and monetize hardware + an optional
~$6.50/mo cloud. That is exactly the model we mirror. **Our edge:** the agent, a curated white-label
accessory line, and no forced cloud.
Links — [Green](https://www.home-assistant.io/green/) ·
[Yellow](https://www.home-assistant.io/yellow/) ·
[Connect ZBT-2](https://www.home-assistant.io/connect/zbt-2/) ·
[Voice PE](https://www.home-assistant.io/voice-pe/)

---

## Appendix — sources

- Smart-home market size/CAGR (2026): MarketsandMarkets, Grand View Research, Fortune Business
  Insights, Straits Research, Coherent Market Insights, Precedence Research, Technavio — estimates
  range ~$130–230B, ~12–26% CAGR.
- Tapo catalog (CES 2025): TP-Link press; PCWorld; Tapo store — cameras, PalmKey lock, Atom Link
  lighting, plugs, sensors, H200 hub, NVR, vacuums.
- OSS smart-home monetization: Nabu Casa / Home Assistant — cloud subscription (~$6.50/mo),
  hardware, "Works With" program; ~$4M revenue, subscriber-funded, no external investors.

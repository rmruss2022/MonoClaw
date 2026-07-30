# openhome Pod Mesh — engineering design

Turn the [Pod concept](/docs/concepts) into a buildable system: a **wall-plug node** you drop
into outlets around the house so the openhome agent is **always in earshot**, every room has a
**good speaker** (synced multi-room music), and any two rooms can **talk to each other** (intercom
+ broadcast). No batteries, no wires, no dead zones.

> Design v1 (2026-07-30). Companion to `hardware/openhome-mini-build-guide.md` (the hub/"server").
> The mini is the brain in one spot; the Pod mesh gives it a body in every room.

---

## 1. Goal & requirements

| Requirement | Target |
|---|---|
| Agent reachable from anywhere | Wake word answered in every room, ≤ 5 m, ≤ 1.5 s |
| Good music | Room-filling for a plug; **sample-synced** multi-room; no drift |
| Communication | **Broadcast** (agent/announce to all) + **intercom** (2-way room↔room) |
| Always on | Mains-powered, no batteries, survives one node dying |
| Mesh backbone | Each pod extends coverage for low-power devices (Thread) |
| Privacy | On-device wake word · hardware mute · nothing leaves the LAN ([concept §privacy](/docs/concepts)) |
| Install | Plug in → it joins. Zero-config onboarding. |

Non-goal v1: audiophile bass from a plug (physics — see audit §7). "Good for a room," not a subwoofer.

---

## 2. System architecture — how the mesh actually works

Two networks, on purpose. Don't conflate them:

```
                         ┌──────────── openhome hub (the "server" / mini) ────────────┐
                         │  Snapcast SERVER · Music Assistant · Assist (STT/TTS/intent) │
                         │  Thread Border Router · wake-word arbitration                │
                         └───────▲───────────────▲───────────────▲────────────────────┘
             WiFi (audio+voice)  │               │               │
                    ┌────────────┴───┐   ┌────────┴───────┐   ┌───┴────────────┐
                    │  Pod — Kitchen │   │  Pod — Living  │   │  Pod — Bedroom │
                    │ Snapclient +   │   │ Snapclient +   │   │ Snapclient +   │
                    │ wake word + mic│   │ wake word + mic│   │ wake word + mic│
                    │ speaker + ring │   │ speaker + ring │   │ speaker + ring │
                    │ Thread ROUTER  │◄─►│ Thread ROUTER  │◄─►│ Thread ROUTER  │  ← Thread mesh
                    └───────┬────────┘   └───────┬────────┘   └───────┬────────┘   (802.15.4)
                            └─── extends coverage for battery sensors, locks, buttons ───┘
```

- **WiFi layer (star, through your router):** carries audio (Snapcast) and voice. This is the
  "agent everywhere + music everywhere" plane. It is *not* a WiFi mesh by default — your existing
  router/APs cover it. (Optional: pods can run a WiFi repeater, but that's a support headache; skip v1.)
- **Thread layer (true mesh):** every pod is **mains-powered → a Thread Router**. Drop pods around
  the house and you've blanketed it with an 802.15.4 mesh that the **battery sensors, locks, and
  buttons** ([starter line](/docs/business)) hop through. *This* is the mesh that matters, and it's
  free — the pods are always on anyway. More pods = stronger sensor mesh, automatically.

**The insight:** the pods do double duty. They're audio+voice satellites on WiFi **and** the Thread
backbone for everything low-power. One device makes both the agent and the sensor network omnipresent.

---

## 3. Compute — what runs in the plug

| Option | $ | Runs | Thread router? | Verdict |
|---|---|---|---|---|
| **Raspberry Pi Zero 2 W** | ~$15 | Snapclient + wyoming wake word + LED svc | via co-processor (ESP32-H2/C6 or dongle) | ✅ **recommended** — real Linux, easy |
| ESP32-A1S Audio Kit | ~$8 | Squeezelite/Snapclient (firmware) | no | budget, audio-only, no mesh role |
| ESP32-C6 / H2 | ~$6 | wake word + Thread, weak audio | ✅ native | great mesh node, poor speaker |
| **Pi Zero 2 W + ESP32-C6** | ~$21 | audio+voice (Pi) + Thread router (C6) | ✅ | the "does everything" pod |

Recommended pod = **Pi Zero 2 W** for audio/voice, with an **ESP32-C6** (or the hub's border router)
handling Thread. Budget "Pod Mini" (mesh + speaker, no premium mic) = ESP32 only.

---

## 4. Audio & the two communication modes

**Music (multi-room):** each pod runs a **Snapcast client**; the hub runs the Snapcast **server**
fed by **Music Assistant**. Snapcast timestamps every packet so all rooms play **bit-synced** — walk
the house, no echo/drift. Group/ungroup rooms from the app ("kitchen + living together").

**Communication — two features, one hardware set (mic + speaker in every pod):**
1. **Broadcast / announce** — the agent (or a doorbell, timer, "dinner's ready") plays TTS on
   one or all pods. Music Assistant's *announce* ducks the music, speaks, and resumes. One-way, all rooms.
2. **Intercom / drop-in** — 2-way room↔room. "openhome, intercom the bedroom" → the hub bridges the
   **kitchen pod's mic → bedroom pod's speaker** and back. Half or full duplex (full duplex needs the
   AEC from §7). This is the "walkie-talkie the house" feature.

**Agent everywhere:** every pod is a wake-word satellite. Multiple pods will hear "openhome" at once →
the hub does **loudest-mic arbitration** (linux-voice-assistant / HA `assist_satellite` already supports
this) so exactly **one** pod responds. No chorus of confirmations.

---

## 5. Per-pod bill of materials

| Part | Role | Protocol/Notes | ~Cost | Link |
|---|---|---|---|---|
| Raspberry Pi Zero 2 W | compute | WiFi (audio+voice) | $15 | [adafruit](https://www.adafruit.com/product/5291) |
| MAX98357A I2S amp | audio out | I2S | $6 | [adafruit](https://www.adafruit.com/product/3006) |
| 1.75–2″ full-range driver + passive radiator | speaker | tuned for a small ported box | $6–10 | [Dayton Audio](https://www.daytonaudio.com/) |
| I2S MEMS mic (INMP441) *or* 2-mic board | mic | far/mid-field | $3–8 | [Adafruit ICS-43434](https://www.adafruit.com/product/3421) |
| NeoPixel ring 12–16 (WS2812) | status ring | driven over SPI | $8 | [adafruit](https://www.adafruit.com/product/1463) |
| ESP32-C6 (optional) | Thread router | 802.15.4 + Matter | $6 | [adafruit](https://www.adafruit.com/product/5672) |
| **Hi-Link HLK-20M05** AC-DC | mains → 5 V / 4 A (20 W) | isolated, for audio peaks | $6 | [search HLK-20M05] |
| Hardware mute slide switch | cuts mic power | privacy (LED on when muted) | $1 | any SPST |
| 3D-printed wall-plug shell + NEMA 1-15P prongs | enclosure | grille + diffuser + vents | $3 | this repo |

**~$55–65 per pod** at qty 1; the point is you buy several. Budget "Pod Mini" (ESP32-A1S, no premium
mic) lands ~$25.

---

## 6. Software integration (adds to the hub you already built)

1. **Snapcast server** on the hub; **Snapclient** on each pod (systemd). — https://github.com/snapcast/snapcast
2. **Music Assistant** as the source + announce engine. — https://www.music-assistant.io/
3. **wyoming-satellite / linux-voice-assistant** on each pod → registers as an `assist_satellite`
   in the hub; wake word local, arbitration central. (Same stack as the mini.)
4. **Thread border router** on the hub + pods as routers (OpenThread / the ESP32-C6 RCP).
5. **Intercom** = a small hub service that, on intent, opens a two-way Snapcast/RTP stream between
   two pods (mic↔speaker). Ships as an openhome add-on.
6. Zero-config onboarding: pod boots → mDNS-advertises → hub adopts it → you name the room in the app.

---

## 7. Debug & design audit (the parts that bite)

1. **Mains in a sealed plug body = safety + heat (the big one).** AC-DC + amp + Pi in a small shell
   means **UL/CE certification**, creepage/clearance spacing, fusing, and thermal headroom. *Adjustments:*
   isolated AC-DC module (HLK, pre-certified), vents + internal baffling, keep mains on its own PCB zone,
   derate the supply (20 W for a ~10 W load). A **"brick + 30 cm pigtail"** variant relaxes all of this if
   the plug body runs hot — offer both.
2. **"Good speaker" vs a plug's volume.** A 2″ driver in a tiny box has **no low bass** — physics.
   *Adjustments:* ported enclosure + **passive radiator**, DSP bass EQ (safe limits), and honest
   marketing ("room audio," pair two for stereo). For a real music room, group a pod with the mini or a
   bigger speaker via Snapcast.
3. **Snapcast sync across many nodes.** Default buffering handles it, but a weak-WiFi pod can drift.
   *Adjustment:* per-client latency trim; put pods on good AP coverage (they're on 2.4 GHz).
4. **2.4 GHz congestion with N pods.** Audio + voice + Thread all crowd 2.4 GHz. *Adjustments:* Pi Zero 2 W
   is 2.4-only, so plan AP channels; Thread is 802.15.4 (separate), which actually *offloads* the sensors
   from WiFi — another reason to split the planes.
5. **Wake-word double-trigger.** Covered by loudest-mic arbitration (§4) — verify it's enabled or every
   pod answers.
6. **Full-duplex intercom needs AEC.** Without echo cancellation the far room hears itself. *Adjustment:*
   run software AEC (speexdsp/webrtc) on the pod, or a mic module with hardware AEC (XVF3800) for premium pods.
7. **Vampire power.** 6 always-on pods at ~2–3 W idle = ~15 W standby. *Adjustment:* efficient AC-DC,
   low-power idle (LEDs dim/off, Pi governor), publish the number honestly.
8. **Privacy is the product** ([concept](/docs/concepts)): on-device wake word, **hardware** mute that cuts
   mic power with the ring lit red-on-mute, open firmware. Non-negotiable — it's the whole pitch.

---

## 8. Rollout / mesh scaling

- **Start with 3** (kitchen, living, bedroom) → agent + music + intercom in the daily-path rooms.
- Coverage: ~1 pod per 1–2 rooms for voice; Thread mesh strengthens with every added pod.
- Upgrade path = the business model: "start with one, fill the house." Each pod adds a speaker, a mic,
  and a Thread router — device count and mesh resilience climb together.

## 9. Adjustments vs. the concept
- Split the "mesh" into **WiFi (audio/voice, star)** and **Thread (sensors, true mesh)** — the concept
  said "WiFi mesh node + Thread router"; in practice the Thread mesh is the one that earns its keep.
- Added the two **communication** modes (broadcast + intercom) and the **loudest-mic arbitration**.
- Speaker spec made honest: ported + passive radiator, "room audio," pair for stereo.
- Offered a **pigtail variant** to defuse the mains-in-plug thermal/cert risk.

## 10. Links
- Snapcast (synced multiroom): https://github.com/snapcast/snapcast
- Music Assistant (source + announce): https://www.music-assistant.io/
- Squeezelite-ESP32 (budget pod firmware): https://github.com/sle118/squeezelite-esp32
- Raspberry Pi Zero 2 W: https://www.adafruit.com/product/5291
- MAX98357A I2S amp: https://www.adafruit.com/product/3006
- ESP32-C6 (Thread/Matter): https://www.adafruit.com/product/5672
- I2S MEMS mic (ICS-43434): https://www.adafruit.com/product/3421
- NeoPixel Ring 16: https://www.adafruit.com/product/1463
- Dayton Audio drivers/radiators: https://www.daytonaudio.com/

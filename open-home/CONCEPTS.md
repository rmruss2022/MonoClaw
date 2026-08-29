# Concepts (experimental)

Forward-looking product concepts not yet on the committed roadmap. Ideas we're pressure-testing.

---

## Radial gesture control — the app's primary interface

**The idea:** the main way you control the home isn't a wall of toggles — it's a **radial
gesture**. Press the center of the screen, flick toward a direction (every 45° — cardinals
and diagonals), release to trigger. One thumb, eyes-half-closed, muscle memory. Flick
up-left for *Goodnight*, right for *Cameras*, down for *Lock*.

This is a **marking menu** (a.k.a. radial/pie menu): *touch → swipe → release*. The research
is clear on why it works — the menu teaches novices, but experts recall the *angle* and flick
blind, faster than visual memory; and a drawn trail lets you correct mid-gesture.

Why it fits openhome:
- **Speed.** The most-used actions are one gesture away — no menu diving.
- **Muscle memory.** Directions become reflexes; you stop looking at the screen.
- **Accessibility & one-handed.** Big targets, no precise tapping, works blind.

Design decisions (from the marking-menu literature):
- **Hidden until pressed.** At rest it's just the orb — icons fade in only when you press, so
  the screen stays calm and expert flicks feel instant.
- **Drawn trail.** A mint line follows your finger through the wedges so an off-course gesture
  is easy to fix before you release.
- **Directional chords → scenes.** Chain directions for compound actions. Live today:
  - **↑ → ↗** = 🌙 Nighttime (lights off, doors lock, music off)
  - **↑ → ↓** = ☀️ Good morning (lights on, unlock, coffee, music)
  - **↓ → ↑** = 🛏️ Matthew's Room (bedroom light + speaker + shades)
  - **↗ → ↘** = 🎉 Party (every light full, music up, shades open)
  - **← → →** = 📖 Reading (soft office + living light, quiet elsewhere)

  This is a multi-stroke marking menu — 8 directions become a deep, fast tree without more screen.

**Live prototype:** try it at [`/control`](/control) — hold the center, flick to act, or chain
directions for a scene. Each trigger toggles real device state (watch the chips + the
[dashboard](/) Devices card update live) and posts a `control.*` event.

Open question: action + chord mappings should be user-customizable, with smart defaults per home.

---

## openhome Pod — ambient mesh in every outlet

![openhome Pod concept](/assets/pod.png)

**The idea (credit: a friend of Matthew's):** take a wall charger, add a microphone and a
small compute module, and let the openhome agent *live in the outlet*. Drop a few around
the house and they form a **mesh** — whole-home coverage, no single point of failure.

![Plugging in an openhome Pod](/assets/photo/pod-hand.png)

### Why this is strong

The single-box design has one weakness: it's one box, in one spot. Pods fix that and add a
whole product line:

- **Distributed senses.** A mic + sensors in every room gives the agent real presence —
  voice control anywhere, plus acoustic events (smoke-alarm chirp, glass break, a knock,
  running water) without cameras.
- **Mesh resilience.** Each pod is a **Thread border router + WiFi mesh node + Matter
  controller**. Coverage scales with the number of pods; no dead zones; the home keeps
  working if one dies.
- **Edge compute at the edge.** Wake-word and simple inference run on the pod; the box (or
  cloud, opt-in) handles the heavy reasoning. Latency drops, privacy improves.
- **Power is free real estate.** It's already plugged in — no batteries, always on, and it
  still charges your phone. The most frictionless install in the home.
- **Business gold.** Households buy *several* pods, not one hub. It multiplies device count,
  strengthens the mesh, and creates a natural "start with one, fill the house" upgrade path.

### The landmine — and why it becomes our moat

An always-listening mic in every room is **exactly the Alexa/Echo surveillance model our
brand exists to reject.** If we get this wrong, we're the thing we're fighting. If we get it
right, it's the most convincing proof of the whole thesis.

**Non-negotiable privacy design:**

1. **On-device wake word.** Audio is processed locally; nothing is recorded or streamed until
   an explicit wake word. Raw audio **never leaves the home** — ever, by architecture.
2. **Hardware mute.** A real physical switch that cuts mic power (not a software toggle), with
   a mint LED that is *on when muted* — you can see the mic is dead across the room.
3. **Visible listening state.** A light that unambiguously shows when the mic is active.
4. **Local-only by default.** Voice → intent → action all happen on your box. Cloud voice/LLM
   is a per-pod opt-in, off out of the box.
5. **Auditable.** Open firmware; anyone can verify the mic behaves as claimed. That's the
   difference no closed vendor can offer.

> **Positioning:** *"Alexa listens for Amazon. openhome listens for you — and you can prove it,
> because you hold the key."* This is the Pod's entire pitch.

### Open questions

- **Compute vs. cost/heat/size** in a plug form factor — how much inference fits, and at what BOM?
- **Certification** (UL/CE) for a mains-powered mic device — real but standard hardware work.
- **Mic-only vs. mic + more** (temp, humidity, presence radar, IR blaster?) — how much sensor to pack in.
- **Regulatory** — two-party consent / always-on-mic laws vary by region; on-device-only helps.

### Where it lands

A **Phase 2–3 hardware concept** and a flagship first-party device: the openhome **Pod**
(and a **Pod Mini** without the mic, purely as a mesh/Thread extender for the privacy-averse).
It slots into the catalog beside the box as the thing that turns one hub into a whole-home
nervous system.

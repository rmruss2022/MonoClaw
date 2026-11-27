# Realized — Brand Guide

*How Realized looks everywhere — the app, the App Store, every post and page. The practice of becoming.*
*One job per element. If a rule here fights a screen, the screen is wrong.*

**The implemented version of this document lives at `/brand`** — the same guide rendered in the real theme, with live components rather than screenshots. This file is the source; that page is the proof. Change one, change the other.

**Direction locked Nov 24 (rev 2): Co-Star × OpenHome — austere monochrome, image-led.**
The earlier "Molten Dawn" gold-and-violet pass is superseded. Don't revive it, don't reintroduce an accent colour to "add warmth."

---

## 01 · The essence

**Realized** helps people become who they're meant to be — by **seeing, feeling, and operating from their highest self**, daily, until they transform into it.

- **Name:** Realized
- **Tagline:** *Become who you're meant to be.*
- **Mantra:** *See it. Feel it. Become it.*
- **In one line:** a daily practice — meditate, plan your life, feel your highest self — that raises your state and lets you act from it.

---

## 02 · Logo system

Two forms, one idea: **the Gateway** — a threshold opening onto the light you're rising into.

- **App icon (hero):** the rendered stone-arch-at-dawn (`brand/logo-icon.png`). Use where the brand is expected: App Store, home screen, splash, the top of a deck. Square — the OS rounds it.
- **The mark (small):** a minimal **arch doorway glyph** — a semicircle arch on two legs, a base line, one point of light. Use tiny: the in-app header beside "Realized", favicon (`icon.svg`), a corner sign-off.
- **Clear space:** ≥ 15% of the mark's height around it. Don't crowd.
- **Never:** recolour, add glow or gradient to the glyph, stretch, crop, or set the glyph on busy imagery without a dark scrim.

---

## 03 · Colour

Austere and monochrome. Light does the work — **there is no accent colour.**

| Name | Hex | Job |
|---|---|---|
| **Ink** | `#08080a` | the main background — every screen starts here |
| **Panel** | `#0b0b0e` | cards, raised blocks, the tab bar |
| **Bone** | `#ece9e2` | body text, the mark, the paper surface |
| **Bone-bright** | `#f2efe8` | headlines, emphasis, the primary button |
| **Muted** | `#7b7971` | labels, meta, secondary text |
| **Hairline** | `rgba(255,255,255,.12)` | borders, rules, dividers |

**The mix in every screen:** Ink fills it → Panel holds the cards → Bone carries the words → one B&W image breathes.

**The bone ramp.** Where the old theme used hue to separate things — gold vs violet vs blue icons, coloured progress bars, state badges — Realized separates them by **brightness only**. Anything that used to be a colour becomes its luminance, tinted very slightly warm toward Bone. Bright = active, earned, now. Dim = done, pending, secondary.

**Glows are gone.** An earlier note asked for "white or yellow glow instead of blue" on the Journeys tab; rev 2 supersedes it — the answer is **no glow at all**. Emphasis comes from brightness, weight and space, never from bloom. The one exception is light inside a photograph.

**The only warmth** permitted is a faint dawn-glow *inside* an image. Never in the UI.

---

## 04 · Surfaces

Three, and only three.

- **Ink** — the default. Near-black, with a 5%-opacity film grain fixed over the whole app so the blacks read as photography, not flat CSS.
- **Panel** — a card on Ink. One hairline border, 5px radius, **no shadow, no gradient, no glow.**
- **Paper** — the inverse, and the one bright block per screen. Bone fill carrying a woven grey texture so it reads as pressed paper rather than a white rectangle. Ink-on-paper type. This is the only place dark-on-light appears. Opt in with `class="paper"`; it sets its own text colours.

Use Paper sparingly — at most one per screen. Two competing bright blocks and the hierarchy collapses.

---

## 05 · Type

Three styles, each with one job. **Never add a fourth to a single screen.**

- **HEADLINES — Fraunces**, light (~340), italic for one emphasized word. The big editorial statements, the wordmark. *"Become who you're meant to be."*
- **LABELS — IBM Plex Mono**, 500, UPPERCASE, `.18em` tracking, 10–11px. Dates, counts, eyebrows, buttons, nav, captions: `TUE · NOV 25` / `DAY 019` / `6 MIN`.
- **BODY — Inter**. Sentences, descriptions, anything longer. Never centre it.

Script-equivalent = Fraunces *italic*, one or two words only. Numerals in sequence are mono and padded: `01 / 02 / 03`, never a filled circle.

### Combos
- **Label + Headline** → `TODAY YOU ARE` + *"Becoming the person who already has it."*
- **Headline + Body** → a statement, then one sentence that earns it.
- **Mono-meta + serif title** → `STOICS · III` over *The Dichotomy of Control*.

Three type styles max per graphic; the italic always gets the fewest words.

---

## 06 · Components

- **Primary button** — the one filled or outlined control per screen. Mono caps, `.14em`, pill radius. On Ink it's a bone outline on transparent; filled bone with Ink text when it's the single unmissable action.
- **Secondary** — an underlined mono link. The only underline in the system.
- **Rows over cards.** Lists are flat rows separated by hairlines, not floating cards with gaps. Where a grid is needed, divide it with 1px hairlines rather than spacing.
- **Selection is a border.** The chosen plan, tab or option gets a brighter or doubled outline — never a fill, never a tick, never a colour.
- **Fields** — transparent, hairline border, mono placeholder in caps.
- **Images** — always desaturated, always framed with a 1px hairline or full-bleed behind a dark scrim. Never a soft drop-shadow.
- **Tab bar** — flat Panel, no tint, no coloured icon backgrounds. Active is bone, inactive is muted.

---

## 07 · Imagery

Real light, deep black, room to breathe. Surreal **black-and-white celestial / architectural** scenes — stone archways opening onto misty dawns, marble statuary haloed by the moon, lone figures under vast skies (`brand/wallpaper-*.jpg`, `art/`).

- **Do:** full-bleed with a dark scrim behind text, or framed with a 1px border. Always desaturated. One subject, lots of negative space.
- **Don't:** stock wellness pastels, glossy 3D, saturated colour, literal sun-with-rays clichés, clutter.
- **How we make it:** OpenAI `gpt-image-2`, converted to grayscale (prompts and history in `art/`).
- **Words on imagery:** bold, legible, on the calm part of the frame — never small text over the busy part.

---

## 08 · Motifs

Use one, quietly — never a pile.
**The arch / gateway** (the throughline) · **a single point of light** · **concentric rings** (awareness) · **moon phases** (becoming whole). Bone line-work on Ink. The four-point sparkle `✦` is the list bullet and the "verified/earned" mark — it replaces every emoji and every tick.

---

## 09 · Voice

An **oracle that empowers**. Second person, present tense, short declaratives.

- **Always:** agency, becoming, capability, ownership — *"You are freer than you were told." / "Raise your state. Operate from there." / "Act as the one you're becoming."*
- **Never:** anything that shrinks the user — *"you are small / a speck / insignificant / it doesn't matter."* Elevated, not clinical; spiritual, not woo.
- No emoji anywhere in product copy. The sparkle is a glyph, not an emoji.

---

## 10 · Features (what Realized is)

- **Practice** — guided meditation plus a daily *"raise your state"* visualization: feel your highest self as already true.
- **Journeys** — guided paths through real traditions (the Stoics, Deities & Devotion, Foundations), lesson by lesson.
- **The Journal** — Deep (pillar work), Daily (today's letter), and **Season** (name and walk the chapter of life you're in; read it back).
- **Community** — read a letter from a real member, then sit alongside a worldwide practice.
- **Leagues & Light** — the habit made visible: Light, levels, and a weekly league, ranked in monochrome brightness tiers.

---

## 11 · Marketing — the post formula

One B&W celestial image · one Fraunces line · one mono tag · silence around it.

- **Hook:** a Fraunces statement on a dark image (`Become who you're meant to be.`).
- **Proof:** one screen of the practice, mono label visible.
- **Ask:** the mark plus a single line (`Begin · raise your state`).

Do: restraint, confidence, space. Don't: emoji spray, hype ("crush your goals"), pastel wellness.

---

## 12 · Implementation

The app is one file — `server.py` — and the theme lands in two places:

1. **The base stylesheet** (~line 2493). As of v129 its colour values are monochrome at source: every saturated hex was converted to its luminance on the bone ramp. Nothing in here should ever reintroduce a hue.
2. **The override layer** (`REALIZED · Co-Star monochrome theme`, ~line 4384). `!important` rules that fix *form* — flattening glows, shadows, gradients and radii — plus the paper surface. It only reaches the authed app.

Any page that builds its own `<style>` escapes the override layer and must carry the tokens itself: the marketing site, privacy, survey, admin, the transactional email template, and the PWA manifest. All six were converted in v128.

**Before shipping a theme change,** sweep for stray colour — any hex with saturation above ~0.35 and mid lightness outside the override layer is a bug. Near-white bone tones (`#f6f3ec`, `#fdfaf2`) read as "saturated" to a naive check and are correct; ignore those.

---

## 13 · The don'ts, in one place

No accent colour · no gold, violet, blue or green · no gradient fills or gradient text · no glows, blooms or coloured shadows · no rounded gradient cards · no emoji · no coloured icon backgrounds · no ticks for selection · no centred body copy · no fourth typeface · no more than one Paper block per screen.

---

### Assets (`lumen/brand/`)
`logo-icon.png` (app icon) · `logo-icon-rounded.png` (icon in the rounded shape) · `wallpaper-1…4.jpg` (full-screen backgrounds) · `_marks-explored.png` (archive).

*Living document — update as the system grows.*

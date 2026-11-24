# Realized — Brand Direction

> **DIRECTION LOCKED (Nov 24, rev 2): Co-Star × OpenHome — austere monochrome, image-led.**
> Supersedes the "Molten Dawn" gold-cosmic look below (that was a reskin; user wanted a whole new theme).
> - **Palette:** true black `#08080a` + bone `#eceae6`; muted `#6f6d66`; hairlines `#ffffff1a`. Pure monochrome, no gold glow, no gradient candy. (Pure Co-Star "A" — zero accent color.)
> - **Type:** `Fraunces` (light ~340 serif, big editorial statements, italic for emphasis) + `IBM Plex Mono` (uppercase, .2em tracked, 10–11px micro-labels/numbers: `TUE · NOV 24`, `DAY 019`, `6 MIN`) + Inter body.
> - **Components:** flat rows + 1px hairline rules + framed image blocks (1px border) + lots of negative space. Kill glows, box-shadows, rounded gradient cards, pill-glow buttons.
> - **Imagery = the soul of it:** surreal high-contrast **B&W celestial collage** (marble statuary + moons/planets/stars, lone figures dwarfed by the cosmos, eyes/hands). Generated via **OpenAI gpt-image-2**, grayscale. Framed, not full-bleed glossy. Staged in `/tmp/realized2/art-bw/`.
> - **Voice in layout:** second-person oracle cadence — `TODAY YOU ARE →` "Becoming the person who already has it"; captions like `THE SELF, REALIZED`.
> - Mocks: `/tmp/realized2/mock.png` (A/B), `/tmp/realized2/alive.png` (A with real imagery — the reference).
> - Build: new global CSS token system → roll out shell + home + journeys first, deploy coherent (don't ship a half-converted theme on the live app), then remaining screens.

---
_Below: the earlier Molten Dawn reskin (v116–v117), now superseded by the above._

# (superseded) Realized — Molten Dawn

**Rename:** Lumen → **Realized**. (Internal ids/paths/bundle stay `lumen`/`ai.lumen.app` for now — display strings, logo, copy, palette change.)

## The idea
We become who we're meant to be by repeatedly **seeing, feeling, and operating from our highest self**. Awareness → aspiration → *embodiment* → transformation. The practice loop: **meditate · plan the life · visualize + feel the best self** — and by feeling it, we raise our energy to that level and act from that vantage. Repetition transforms the life.

**Feeling it is the point** — not information, not even insight, but raising your state and operating from it.

## Name treatment
- Wordmark: **Realized** (Fraunces, 540 wght, -.02em).
- Tagline: **Become who you're meant to be.**
- Sub / mantra: **See it. Feel it. Become it.**
- Section eyebrows use verbs of state: "raise your state," "operating from your highest self," "feel it as already true."

## Mark
A **radiant aperture**: a bright core (the realized self) with concentric thin rings opening outward (awareness expanding) + four cardinal rays. Evolves the lotus/gold glow rather than discarding the equity.

## Type
- **Display/headlines:** Fraunces (editorial serif — gravitas, "realized").
- **UI/body:** Space Grotesk (kept from Lumen) / Inter for long body.

## Palette — two directions (pick one)
**A · Molten Dawn** *(recommended)* — keeps the beloved gold, reframed as a **sunrise rising over violet night** = energy rising, the dawn of the realized self. Differentiates from generic purple meditation apps.
- bg `#0c0a14` · dawn gradient `#f5b65e → #c97a3a → #5b3a7a → #241a3b → #0c0a14`
- gold `#f3c781` · warm text `#fdf7ee` · muted `#d9cfe0`

**B · Lucid** — cooler, cleaner, modern. Luminous violet + platinum. Reads "clear/lucid awareness."
- bg `#0b0a16` · gradient `#2b2550 → #191633 → #0b0a16`
- accent `#b79cff` · text `#f4f1fb` · muted `#d7d0ec`

## Tone
Confident, elevated, embodied. Not clinical, not woo. Short declaratives. Second person. Present tense ("you are," "it is already true").

## Scope of the sweep (once direction is locked)
1. Wordmark + all "Lumen" display strings → "Realized" (app, manifest, `<title>`s, premium/privacy/feedback pages).
2. New mark SVG + app icon + PWA/favicon.
3. Palette + Fraunces across the app shell, hero, cards, journal, journeys.
4. Copy pass toward the "see it / feel it / become it" voice on the key screens.
5. App Store listing + screenshots (separate 1.0.x submission when ready).

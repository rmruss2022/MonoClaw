# Realized — Brand Guidelines

*The practice of becoming. v1 — Nov 2026.*

---

## 1. The idea

**Realized** helps people become who they're meant to be. Not through information, but through a daily loop: **meditate → plan your life → see and *feel* your highest self → operate from that state.** Feeling it is the point — you raise your energy to the level of the self you're becoming, and by returning to it, you transform into it.

**One-line:** *Become who you're meant to be.*
**Mantra:** *See it. Feel it. Become it.*

---

## 2. Voice & tone

Confident, elevated, embodied. Second person. Present tense. An **oracle that empowers** — it tells you the power is already yours.

**Always:** agency, becoming, capability, ownership. ("You are freer than you were told." / "Act as the one you're becoming." / "Raise your state. Operate from there.")

**Never:** anything that shrinks the user — *"you are small," "a speck," "insignificant," "it doesn't matter."* The cosmos is the backdrop to your becoming, never a reason you're tiny.

Short declaratives > paragraphs. Editorial, not clinical; spiritual, not woo.

---

## 3. Logo & mark

**The Gateway** — a stone archway at dawn, opening onto the light you're rising into. The threshold you step through to your realized self.

- **App icon:** the rendered arch-at-dawn (`brand/logo-icon.png`). Square, no pre-rounding — the OS masks corners.
- **In-app / small mark:** the minimal **arch doorway glyph** (a semicircle arch on two legs, a base line, one dot of light). Use when the photographic icon is too small to read.
- **Favicon:** `icon.svg` — the arch glyph, bone on near-black.
- **Clear space:** keep padding ≥ 15% of the mark's height on all sides. Don't crowd it.
- **Don'ts:** don't recolor the icon, don't add gradients/glows to the glyph, don't stretch, don't place the glyph on busy imagery without a scrim.

---

## 4. Color

Austere, monochrome-first (Co-Star × OpenHome).

| Token | Hex | Use |
|---|---|---|
| **Ink / black** | `#08080a` | primary background |
| **Panel** | `#0b0b0e` | cards, raised surfaces |
| **Bone** | `#ece9e2` | primary text, the mark |
| **Bone-bright** | `#f2efe8` | headlines, emphasis |
| **Muted** | `#7b7971` | labels, secondary text |
| **Hairline** | `rgba(255,255,255,.12)` | borders, rules |

**No gold, no purple, no gradient candy, no glows.** Color is the absence of color — light does the work. (A single warm dawn-glow is allowed *inside imagery* only, never in UI chrome.)

---

## 5. Typography

- **Display — Fraunces** (light, ~340–400, italic for emphasis). Big editorial statements, the wordmark, hero headlines.
- **Labels/meta — IBM Plex Mono** (500, UPPERCASE, `.18em` tracking). Dates, counts, eyebrows: `TUE · NOV 25`, `DAY 019`, `6 MIN`.
- **Body — Inter / Space Grotesk**. Running text, descriptions.

Hierarchy = serif statement + mono micro-label + generous negative space. Never center long body copy.

---

## 6. Imagery

Surreal, high-contrast **black-and-white celestial / architectural** scenes — marble statuary haloed by the moon, lone figures under vast skies, stone archways opening onto misty dawns (`brand/wallpaper-*.jpg`). Fine-grain, cinematic, atmospheric, lots of negative space.

- Framed or full-bleed with a dark scrim behind text.
- Always desaturated (mono). A faint warm dawn-glow within the scene is the only permitted warmth.
- Generate via `gpt-image-2` (prompts in `art/` history), convert to grayscale.
- **Avoid:** stock gradients, glossy 3D, literal sun-with-rays clichés, anything saturated.

---

## 7. UI system

- **Layout:** flat. Hairline rules, 1px card borders, no shadows/glows, small radius (≤6px) or full pills.
- **Buttons:** flat outline pills — 1px bone border, transparent fill, IBM Plex Mono uppercase label.
- **Cards:** `#0b0b0e` + hairline border. No gradients.
- **Heroes:** B&W image + dark scrim + Fraunces greeting + mono eyebrow.
- Reference build: the live app (`lumen.bedrock.casa`), v123+.

---

## 8. Marketing

- **Hero formula:** one B&W celestial image + a single Fraunces line (`Become who you're meant to be.`) + a mono tag. Silence around it.
- **Social:** black canvas, bone type, the arch mark small in a corner; let one image or one line carry the post.
- **App Store:** screenshots on true black, Fraunces captions, the mono labels visible in-frame; lead with the practice, not features.
- **Do:** restraint, confidence, space. **Don't:** stock wellness pastels, emoji-heavy, exclamation energy, "crush your goals" hype.

---

## 9. Assets in this folder

- `logo-icon.png` — app icon (square master)
- `logo-icon-rounded.png` — icon previewed in the rounded app shape
- `wallpaper-1…4.jpg` — full-screen backgrounds / phone wallpapers
- `_marks-explored.png` — the mark exploration (archive)

*Living document — update as the system evolves.*

# GROUNDFLOOR — Design Vision

## The Problem with Current UI
Neon pink + cyan on black = every rave flyer from 2012. It screams "hobbyist project."
It doesn't look like something you'd trust with your social life or pay for.

---

## What GROUNDFLOOR Actually Is

A serious infrastructure product for the underground music scene.
Think: what if a Y Combinator company built the definitive nightlife OS for NYC?

Competitors to study: DICE (too corporate, losing soul), RA (editorial authority but dated UX),
Shotgun (European, clinical), Eventbrite (embarrassing). Nobody owns this space with a premium,
opinionated product that feels like it was built *by* the culture.

---

## Design Pillars

### 1. CONCRETE & SIGNAL
The visual language of underground spaces: raw concrete, steel, infrastructure.
Not the glamour of the club — the *bones* of it. Loading docks, boiler rooms,
electrical panels. That's where the real parties happen.

### 2. EDITORIAL AUTHORITY
We're a publication as much as an app. Every screen should feel like a well-designed
magazine spread. Typography-forward. Information-dense but breathable.
RA × Kinfolk × Linear.

### 3. EARNED ACCENT
One — and only one — accent color. Electric acid yellow (#E8FF41).
The color of a caution sign. A signal in the dark.
Used sparingly. Means something when it appears.

### 4. NO DECORATION
Zero emojis in UI chrome. No gradients. No glow effects. No rounded corners (or 2px max).
Every element earns its place. If it doesn't carry information, it doesn't exist.

---

## Color System

```
Background:      #0C0C0C   — near black, not pure (warmer)
Surface:         #141414   — cards, panels
Surface+:        #1C1C1C   — hover states, elevated
Border:          #2A2A2A   — 1px lines, subtle grid
Border+:         #3A3A3A   — active, focused states

Text/Primary:    #F0EEE9   — warm white (not pure white, less harsh)
Text/Secondary:  #888888   — metadata, labels
Text/Tertiary:   #444444   — disabled, placeholder

Accent:          #E8FF41   — acid yellow. GOING state. CTAs. Selection.
Accent/dim:      #B8CC2E   — pressed/active variant
Danger:          #FF4444   — errors, delete
```

---

## Typography

**Display (tab labels, hero text):**
- Font: system-ui → -apple-system → "Helvetica Neue"
- Weight: 800-900
- Transform: UPPERCASE
- Tracking: 0.08em
- Never decorative — always functional

**Body:**
- Weight: 400-500
- Size: 13-14px
- Line height: 1.5

**Metadata:**
- Weight: 500
- Size: 10-11px
- Tracking: 0.1em
- UPPERCASE

**The Rule:** If you're reaching for a font-size below 10px, redesign the element instead.

---

## Component Language

### Cards
- 1px border, #2A2A2A
- Background: #141414
- Zero border-radius (or 2px max on mobile for touch)
- Left accent bar: 3px solid for state (yellow = going, #888 = maybe, transparent = none)
- Hover: border brightens to #3A3A3A. No shadow.

### Navigation (bottom tabs)
- Full-width bar, #141414 background
- 1px top border, #2A2A2A
- Active tab: text turns #F0EEE9 + 2px top border accent yellow
- Inactive: #555555
- No icons + text — text only (or icon only on narrow screens)
- No background highlight on active — just the top border

### Buttons
- Primary: #E8FF41 background, #000 text, weight 800, 0px border-radius
- Secondary: transparent, 1px #3A3A3A border, #F0EEE9 text
- Destructive: transparent, 1px #FF4444, #FF4444 text
- NO: gradient buttons, glowing buttons, rounded pill buttons

### Calendar
- Grid: tight, 1px borders between cells (#1C1C1C)
- Today: acid yellow background, black text
- Has events: small 4px × 4px square dot (not circle), yellow or #555 depending on interest
- Selected: border 1px #E8FF41
- Event names inside cells: truncated, 10px, #888 unless going (then #E8FF41)

### Event Cards (list view)
- Left rail: 3px solid accent bar (yellow = going, #444 = untagged)
- Date block: left column, tight — day number large (28px, weight 900), month tiny (10px, #888)
- Title: 14px, 600 weight, warm white
- Venue: 12px, #888
- Genre tags: 10px, 1px border, letter-spaced — NO colored backgrounds
- Interest buttons: minimal — just "GOING" / "MAYBE" text toggle, no emoji

### Stats Bar
- Horizontal strip, 1px border bottom
- Numbers: 20px, 900 weight, yellow if >0
- Labels: 9px, uppercase, #555
- NOT a card — flush to header

### Login Screen
- Full bleed black
- GROUNDFLOOR in massive display type, weight 900
- Subtitle: "NYC · Underground" — small, spaced, #555
- Input fields: no background, just 1px bottom border
- No box shadows, no cards

---

## Motion & Interaction

- Transitions: 120ms ease-out max. Nothing longer.
- No bounce, no spring, no elastic.
- Hover states change border color or text color only.
- Loading: single 1px yellow line sweeping left-to-right (not a spinner)
- Tab switch: instant. No slide animation.

---

## What We're NOT

- Not a party app (no confetti, no balloons, no disco balls in the UI)
- Not a social network (no avatars, no feeds with photos)
- Not a corporate event platform (no blue, no rounded corners, no "Book Now" CTAs)
- Not a gig economy app (no cards with giant hero images)

---

## The Vibe in One Sentence

> **Linear's discipline. RA's cultural authority. The concrete walls of 99 Scott.**

---

## Reference Products
- Linear — information density, keyboard-first, no decoration
- Resident Advisor — editorial credibility, scene authority
- Pitch (formerly Pitch.com) — dark, typographic, confident
- MSCHF — irreverent but extremely precise
- Cash App — does one thing, looks great doing it

---

## Implementation Priority
1. Color tokens + CSS variables (foundation)
2. Typography scale
3. Navigation bar
4. Event cards (most-seen element)
5. Calendar grid
6. Login screen
7. Everything else

*This document is the source of truth. When in doubt: less color, more type, smaller radius, thinner borders.*

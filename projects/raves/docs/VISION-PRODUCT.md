# Rave Planner — Vision Doc

**Status:** Aspirational / future-state. Not implemented yet (despite what I just built 😅).

---

## Mission

Become the **passport to NYC rave culture** — a living wallet-pass and identity card that tracks where you've been, what you've spent, who's going next, and unlocks real perks at the door.

---

## Core Concepts

### 1. 🪩 Rave Card — Your Membership

A digital member card that grows with you. The more you show up, the more you unlock.

**Tier progression** (based on attended shows, all-time):

| Tier | Emoji | Shows | Vibe |
|------|-------|-------|------|
| Rookie | 🌱 | 0–4 | Just walked in. Welcome. |
| Regular | ⚡ | 5–14 | You're part of the scene now. |
| Headliner | 🔥 | 15–29 | People recognize your face at the door. |
| Legend | 👑 | 30–59 | You have *opinions* about Funktion-One vs. d&b. |
| Icon | 🪩 | 60+ | You ARE the local lineup. |

**The card itself:**
- Animated emblem per tier (concentric pulsing rings)
- Glow color matches tier
- Holographic shimmer on hover (eventually — CSS conic-gradient placeholder for now)
- Apple/Google Wallet pass — scan at door for entry
- Member-since date + venue diversity count + lifetime spend

**Tactile components I want:**
- QR code on the back → opens profile at `/rave/<username>`
- NFC chip support (theoretical — physical card tier eventually)
- Tier-up animation when you cross a threshold
- Annual "season recap" — your year in raves

---

### 2. 💸 Budget — Spend Without Regret

A money-aware rave calendar. Tracks the actual cost of the lifestyle.

**The flow:**
- Set monthly limit (default $400, configurable)
- Each Going show auto-estimates cost from venue averages
- Mark Attended → cost locks in as "spent"
- Progress bar: Spent (green) + Committed (pink) + Remaining
- **Over-budget warning** when committed > limit
- "Can I afford this?" check before adding Going events

**Smart features I want:**
- **Venue averages** — House of Yes averages $35, Knockdown $50, Mirage $80+
- **Auto-estimate** — when adding a show, pre-fill cost from venue history
- **Multi-month trends** — "You've spent $1,247 this quarter on raving"
- **Trade-off view** — "Skip Mirage, hit Basement 3x and save $80"
- **Tax tracking** — yes, ravers can deduct certain "research" expenses 😏
- **Group splits** — going with friends? Split the cab, the door, the bottles

**Receipts / loyalty:**
- Each venue tracks spend per user → tier up faster at your home spot
- "House of Yes Regular" sub-badge at 10+ attended shows
- Annual venue-specific recaps (where you went, what you spent)

---

### 3. 🎁 Perks — Real Local Bonuses

Not generic coupons. **Door-level perks** that actually work in NYC.

**Examples seeded (aspirational — need real partnerships):**

| Tier | Venue | Perk | Code |
|------|-------|------|------|
| Rookie | House of Yes | Welcome shot | HOY-WELCOME |
| Regular | Elsewhere | $5 off Zone 1 | ELS-R5OFF |
| Regular | Basement | Free coat check | BSMT-COAT |
| Regular | Market Hotel | $8 drink token | MKH-DRINK |
| Headliner | Knockdown Center | Skip-the-line entry | KD-SKIPLINE |
| Headliner | Mirage | Side → main stage upgrade | MRG-UPGRADE |
| Headliner | Goodroom | 20% off cloak | GR-CLOAK20 |
| Legend | Avant Gardner | Guest list + free drink | AG-GLIST1 |
| Legend | Brooklyn Mirage | Reserved lounge | BM-LOUNGE |
| Icon | Public Arts | Free entry +1 | PA-FREE2 |
| Icon | Basement | Annual membership | BSMT-ANNUAL |

**Perk mechanics I want:**
- **Tier match** — perks show up automatically as you level
- **Redeem codes** — copy-to-clipboard, show at door
- **Per-venue progress** — separate sub-tier per venue (e.g. "Mirage Headliner")
- **Time-limited drops** — weekend-only perks, "Sunday Industry" comp lists
- **First-100 alerts** — perk unlocks for first 100 to claim
- **Cross-venue comp lists** — house DJs get you on lists at other venues

---

### 4. 🕺 Scene — Where Are People Going Next

**The social layer.** Not generic "feed" — actual local intel.

**Features:**
- **Trending this week** — top picks + genre diversity scoring
- **Going-list match** — see which of your friends are at the same show
- **Crew coordination** — make a "we're going to Mirage Saturday" group
- **First-timer alerts** — "You've never been to Knockdown. They're playing Skrillex on Saturday. 🔥"
- **Last-minute deals** — "$5 off if you go tonight" (synced with venue calendars)
- **Conflict resolver** — "Honey Dijon at HOY and Boiler Room at Basement, same night. Pick one or do both (timing chart)."

**Friends graph (future):**
- Find friends by phone, Instagram handle, or RA profile
- Share your Going list with friends
- See aggregate Going lists — "12 of your friends are at Knockdown Sat"
- Group polls: "where we going Sat?" → everyone votes
- Group budget view: "$X total for 4 people at Mirage"

---

### 5. 📍 Add-Show Flow

**Manual mode** — current basic form.

**Link mode** (Firecrawl scrape) — current implementation. Works for RA, House of Yes, Dice, Eventbrite, etc.

**Smart suggestions (aspirational):**
- Email parsing — "your tickets for X have been confirmed" → auto-add
- Spotify/Apple Music listen history → "you've been playing this DJ on repeat, they're at HOY Friday"
- RA saved events → sync weekly
- Instagram saved posts (raves) → parse location tags
- SMS forwarding — text the link to a number, bot adds it
- Voice — "Add Honey Dijon at House of Yes Saturday" → speech-to-show

---

### 6. 📊 Analytics — Know Thyself

- **Lifetime stats**: total shows, venues explored, genre preferences, decade-in-rave-years
- **Heat map** — calendar density over the year (which months are heavy)
- **Travel radius** — where you go most often
- **Set-time optimizer** — for festivals, build your personal schedule
- **Crew leaderboard** — who's attended the most this year (gamify it)

---

## Visual Design — Bushwick Brooklyn Aesthetic

Already nailed in v1:
- Concrete brutalism base (`#0a0a0a`, `#1a1a1a`)
- Neon accent palette (pink `#ff2d92`, cyan `#00f0ff`, yellow `#fff700`, green `#00ff88`)
- Glow shadows on tiers
- Warehouse vibes — no rounded corners in UI chrome (card itself is the exception)

**Things I want to add:**
- Loading states with synthwave grid animations
- Sound design (subtle clicks, whooshes — toggleable)
- Dark/light mode toggle (light = "warehouse at noon")
- Custom font (currently using SF Mono — want something like "Tusker Grotesk" or "Roobert" for headings)

---

## Technical Architecture (current)

- **Frontend:** React 18 + Vite, port 3007
- **Backend:** Node.js + Express-like http server, port 3004
- **DB:** SQLite via `better-sqlite3` (single file, persistent)
- **Migration:** Idempotent ALTER TABLE on startup
- **Auto-start:** LaunchAgent `ai.openclaw.raves.plist` runs `start.sh`
- **Scraping:** Firecrawl API (key in start.sh env)

**Tables:**
- `events` — core (id, name, venue, date, genres, interest, notes, attended, cost, vibe_tags)
- `budget_config` — singleton monthly limit
- `perks` — venue perks with tier requirements

---

## Future State

**Phase 2: Real partnerships** — talk to HOY/Elsewhere/Basement owners. Get them on board. Issue actual comp lists.

**Phase 3: Wallet pass** — Apple/Google Wallet integration. Scan at door.

**Phase 4: Social graph** — friends, group polls, share Going lists.

**Phase 5: Festival mode** — multi-day events, set-time scheduler, camping logistics.

**Phase 6: Mobile-first** — PWA installable, offline-capable, push notifications for "your friend's at Knockdown tonight."

**Phase 7: NFT/collectible tier** — each tier upgrade mints a commemorative (lol but maybe).

---

## Why This Matters

NYC rave culture is **scene-driven, not algorithm-driven**. People go where their friends go, where the regulars go, where the door person knows your name.

This app isn't trying to replace RA or Dice. It's trying to capture the part those apps ignore: **your personal history, your spending, your loyalty, your status in the local scene.**

The Rave Card is a flex. The perks are real. The budget keeps you solvent. The scene graph keeps you connected.

Build the city, one show at a time. 🪩
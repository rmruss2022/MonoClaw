# Groundfloor Recommendations — Show Discovery Engine

**Status:** Aspirational / design spec  
**Author:** Claw  
**Date:** June 27, 2026

---

## The Concept

Recommend shows based on what people with similar taste are going to — not algorithmic genre-matching, but **real human signal**: who's going where, and what that says about their taste.

If you and 50 other ravers are all going to Honey Dijon at House of Yes, and 38 of them are *also* going to a smaller Teksupport afterparty you've never heard of — that's a recommendation worth surfacing.

This is **collaborative filtering applied to rave culture**. The same engine that powers Netflix ("people who watched X also watched Y") applied to the most trust-driven, word-of-mouth industry on earth.

---

## Why This Works Better Than Genre Matching

Genre tags are noisy. "Techno" means something different at Berghain vs. a Brooklyn warehouse party. "House" at House of Yes is not the same as "House" at a rooftop in Long Island City.

The crowd is the filter. Ravers with taste calibrate taste. If the people going to Dekmantel are *also* going to a small Tuesday night at Public Records — that Tuesday night is worth knowing about, regardless of what genre tags it has.

**Signal sources, ranked by quality:**

| Signal | Quality | Why |
|--------|---------|-----|
| Going overlap with taste-similar users | ★★★★★ | Real human commitment |
| Attended overlap (past shows both went to) | ★★★★★ | Proven taste alignment |
| Maybe overlap | ★★★☆☆ | Intent but not committed |
| Genre overlap | ★★☆☆☆ | Too broad, noisy |
| Venue overlap | ★★★☆☆ | Good venue loyalty signal |
| Artist overlap | ★★★★☆ | Strong when lineups are known |

---

## The Recommendation Algorithm

### Step 1 — Build your taste profile
From your Going + Attended history:
- Venues you frequent → venue affinity vector
- Genres on your shows → genre weight map
- Artists you've seen → artist graph
- Time patterns → weekend vs. weekday, early vs. late
- Price tolerance → average ticket cost on your Going shows

### Step 2 — Find taste neighbors
Users whose Going/Attended history overlaps most with yours.

**Jaccard similarity on Going sets:**
```
similarity(A, B) = |Going_A ∩ Going_B| / |Going_A ∪ Going_B|
```

If you and another user are both going to 4 of the same 10 shows — you're 40% similar. At scale across hundreds of users, you build a graph of who's most taste-aligned with you.

**Weight attended higher than going** (committed > intention).

### Step 3 — Surface their discoveries
From your top 20 taste neighbors, find shows they're going to that you haven't seen yet:

```
recommendations = 
  union(neighbor.going_shows) 
  - your.seen_shows 
  - your.dismissed_shows
  weighted by: neighbor_similarity × event_freshness × going_count
```

### Step 4 — Explain the recommendation
Don't just show the show. Show *why*:

> **"12 people also going to Teksupport are going to this →"**  
> **"Ravers who went to Honey Dijon at HOY tend to also love this"**  
> **"3 of your Knockdown regulars are going"**

The explanation is the product. Ravers trust word-of-mouth, not algorithms. Make the social signal visible.

---

## Recommendation Types

### 1. Crowd Match (primary)
*"People going to [X] are also going to [Y]"*

Surface shows with high co-attendance rates among users who share your Going list. Works even with small user bases — 50 active users generates useful signal.

### 2. Venue Loyalty Match
*"You've been to Knockdown 4 times. This is their most anticipated show of the summer."*

Based on your personal venue history, surface upcoming shows at your home venues before they sell out. Regulars should know first.

### 3. Artist Orbit
*"You went to DVS1 last month. He's mentored this artist. They're playing Basement Saturday."*

Artist graph traversal — not just "you liked X, here's X again," but "you like X, here's what X likes." Requires manually curated or RA-scraped artist relationship data.

### 4. Scene Velocity
*"This show went from 3 → 47 Going in the past 48 hours. Something's happening."*

Track rate-of-change on Going counts. A show picking up velocity among taste-aligned users is a leading indicator it's about to blow up. Surface it before ticket prices spike.

### 5. First Timer Nudge
*"You've never been to Public Records. 8 people from your taste graph have. They all loved it."*

Venue exploration nudge — helps ravers break out of their home venues and discover new spots the scene is gravitating toward.

### 6. The Conflict Resolver
*"Honey Dijon at HOY and Boiler Room at Basement are the same night. Here's who's going where."*

When two high-signal shows conflict, show a split: how many taste-neighbors chose each option and when the sets are (is it possible to do both?).

---

## UI Spec

### Discovery Section (new tab or integrated into Upcoming)

```
┌─────────────────────────────────────────────────────┐
│  🔥 TRENDING IN YOUR SCENE                          │
│  Based on people going to similar shows             │
│                                                     │
│  ▶ PUBLIC RECORDS — FRIDAY                          │
│    8 people from your taste graph are going         │
│    Techno · $15 · ★ First time at this venue        │
│    [GOING]  [MAYBE]  [DISMISS]                      │
│                                                     │
│  ▶ BASEMENT — SATURDAY                              │
│    12 of 47 Teksupport attendees are going here too │
│    Techno · $25 · You've been 3x                    │
│    [GOING]  [MAYBE]  [DISMISS]                      │
│                                                     │
│  ▶ JUPITER DISCO — TUESDAY                          │
│    ↑ Velocity: +23 Going in 24h                     │
│    Tech House · Free · New venue for you            │
│    [GOING]  [MAYBE]  [DISMISS]                      │
└─────────────────────────────────────────────────────┘
```

### On Event Cards
Add a "why recommended" line beneath the venue:
```
💡 12 people also going to Club Rawhide are going to this
```

### Recommendation Explanation Modal
Tap the 💡 chip → expand to show:
- Which of your taste neighbors are going
- What shows you have in common with them
- Option to follow/save those users as "trusted voices"

---

## Phase 1 — Single-User Mode (no social graph needed)

Before there's a community of users, still deliver value:

1. **Genre-based recommendations** from your own history — simple but honest
2. **Venue loyalty alerts** — "Knockdown announced a show, you've been 4x"
3. **Scanner-driven discovery** — surface new events from the weekly scan that match your genre/venue profile
4. **Velocity display** — even without user graph, show "12 people added this to their calendar" (source: scan data, not user Going counts)

### Implementation
```js
// Simple taste match from your own events
const myGenres = frequencyMap(myAttendedEvents.flatMap(e => e.genres))
const myVenues = frequencyMap(myAttendedEvents.map(e => e.venue))

const score = (event) =>
  event.genres.reduce((s, g) => s + (myGenres[g] || 0), 0) * 0.6 +
  (myVenues[event.venue] || 0) * 0.4

const recommended = allEvents
  .filter(e => !myGoingIds.has(e.id))
  .sort((a, b) => score(b) - score(a))
  .slice(0, 10)
```

This runs client-side, needs no backend, and works on day one with just your own event history.

---

## Phase 2 — Collaborative Filtering (multi-user)

When 50+ active users exist:

- Store anonymized Going sets server-side
- Run Jaccard similarity nightly (or on-demand)
- Cache top-20 taste neighbors per user
- Serve recommendations via `/api/recommendations` endpoint
- Allow users to see (but not identify) their taste neighbors: "8 ravers with similar taste"

**Privacy:** Never expose who specifically is going where without consent. Show aggregate counts only ("8 people from your taste graph") unless users opt into friend visibility.

---

## Phase 3 — The Social Graph

When users opt in to social features:

- Follow specific users as "trusted voices"
- See their Going lists (with permission)
- "Your crew" view: consolidated Going list for people you follow
- Group decision tools: "Where are we going Saturday?" poll
- Shared trip planning for festival travel

---

## The Broader Vision

The best music discovery happens through **trust networks** — your friend who DJs, the promoter whose parties you've been to 10 times, the regular at Knockdown who always knows what's good. These aren't algorithms — they're relationships.

Groundfloor can encode those relationships at scale. Not by replacing the human signal, but by making it visible and traversable. The ravers with the best taste become the curators. The scene's collective intelligence — who's going where — becomes a discovery engine that no playlist algorithm can replicate.

**Spotify knows what you listened to after. Groundfloor knows where you went before.**

---

*Part of the Groundfloor vision doc series. See also: VISION-PRODUCT.md, VISION-VENUE-CREDITS.md*

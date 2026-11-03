# Marquee — User Intake & Personalization Plan

A plan for a lightweight intake form that captures each user's **tastes** and the
**past events they've attended**, so Marquee can rank and filter its feed for them.

Marquee today is a single-file Python stdlib app (`server.py`, ~1820 lines:
`http.server` SPA + JSON API, port 18852, public at https://marquee.bedrock.casa/).
There are **no accounts/auth** — it's effectively single-user. This plan keeps that
reality: the profile lives in **`localStorage`** (client) with an **optional
`data/profile.json`** mirror (server), and a short note on how it extends to real
accounts later.

Scope of this doc: **plan only.** No form is implemented here. `server.py` is not
touched by this change (it stays `py_compile`-clean).

---

## 1. Intake questions

Two sections. Keep v1 to ~90 seconds of tapping — mostly chips, no typing required.
Every option reuses vocabulary already in the codebase so answers map cleanly onto
events.

### A. Tastes

1. **Favorite categories** (multi-select chips)
   Source of truth: the `CATEGORIES` list in `server.py:37` / the `CATS` array in the
   front-end (`server.py:1285`) — Music, Nightlife, Arts, Theater, Comedy, Sports,
   Food, Festival, Family, Film, Wellness. Render with the existing `catIcon()` +
   `CATCOLOR` so the chips look native. Let the user mark 0–N, and optionally tag a
   couple as **"love"** (double-weight) vs plain "like".

2. **Vibe / energy** (multi-select, 4–5 options)
   e.g. `chill`, `social`, `high-energy`, `artsy/cerebral`, `date-night`,
   `family-friendly`. These are *derived* tags (no field on events yet) — they map to
   categories/price/time in §4, and v2 can let Gemini tag events with them.

3. **Price sensitivity** (single-select)
   `free-only` · `budget (≤ $20)` · `mid ($20–60)` · `splurge-ok (any)`.
   Maps onto the existing `e.price` string (e.g. "Free", "$25", "$15–30").

4. **Preferred location** (reuses the exact loc model)
   - Default location mode: `near` (Near me / Bushwick) · `mine` · a specific
     `borough` · `all`. This seeds the front-end `loc` variable (`server.py:1288`,
     consumed by `matchLoc()` at `server.py:1292`).
   - Favorite **neighborhoods/boroughs** (multi-select): boroughs from the backend
     `BOROUGHS` list; near-home neighborhoods already named in the Gemini prompt
     (Bushwick, East Williamsburg, Williamsburg, Ridgewood, Bed-Stuy —
     `server.py:532`/`550`). Used for a soft boost, not a hard filter.

5. **Days / times they go out** (multi-select)
   - Weekdays: reuse the weekday picker pattern already built for the add-event form
     (`f_wdays`, `WD`, `selWd` — `server.py:1468–1471`). Store as `[0..6]` (Sun=0),
     the same convention `personal.json` uses.
   - Time buckets: `morning` · `afternoon` · `evening` · `late-night`. Mapped to
     `e.time` via the existing `parseTime()` / `_mins()` helpers.

6. **Group vs solo** (single-select)
   `usually-solo` · `with-a-friend` · `group/crew`. Light signal — nudges
   Nightlife/Festival/Sports for groups, Film/Arts/Wellness for solo. Advisory only.

### B. Past events attended

Goal: capture a few concrete past events + how they felt about them, to seed
"more-like-this".

1. **Pick from recent events** (primary path, zero typing)
   Show the current feed (the already-loaded `all[]` array from `api/events`) as a
   quick multi-select grid reusing `evCard()`-style tiles. For each picked event the
   user taps a rating:
   - 👎 *meh* · 👍 *liked* · ⭐ *loved* (store as `-1 / 1 / 2`).
   Because `all[]` only holds **future** events (`api/events` filters
   `date >= today`, `server.py:1663`), this path mostly captures *recurring / typical*
   events. That's fine — we store the event's **signature** (category, venue,
   neighborhood/borough, price band, title), not the dated instance.

2. **Free-text "tell us what you've loved"** (secondary)
   One or two free-text lines ("Nowadays, Baby Cobra Yoga, Brooklyn Steel shows…").
   Stored verbatim; v2 can run these through the existing Gemini layer to extract
   category/venue/neighborhood tags. v1 just keyword-matches titles/venues.

3. **Rating of their saved "Mine" events** (free signal)
   Anything already in `data/personal.json` (the ★ Mine events) is implicitly a
   positive signal — no question needed, folded in at ranking time.

---

## 2. Data model

One JSON object, versioned, matching the codebase's flat-dict + snake_case style
(same as a `personal.json` record and the `/api/events` payload).

### Storage
- **Primary:** `localStorage` key **`marquee.profile.v1`** (JSON string).
  Fits the "single-user-ish local app" reality and needs zero backend.
- **Optional mirror:** `data/profile.json` next to `events.json` / `personal.json`
  (same `DATA` dir, `server.py:34/41`), written via a new
  `POST /api/profile` + read via `GET /api/profile`, using the existing
  `load_personal()` / `save_personal()` pattern (`server.py:73–81`) as the template
  (`load_profile()` / `save_profile()`). This makes the profile survive a cache clear
  and lets the server-side feed sort use it (see §4). v1 can ship localStorage-only;
  the mirror is a drop-in follow-up.

### Shape

```json
{
  "version": 1,
  "updated_at": 1730000000,
  "completed_onboarding": true,
  "tastes": {
    "categories": { "Music": 2, "Comedy": 1, "Wellness": 2 },
    "vibes": ["chill", "date-night", "artsy"],
    "price": "budget",
    "location_mode": "near",
    "fav_neighborhoods": ["Bushwick", "Ridgewood"],
    "fav_boroughs": ["Brooklyn"],
    "weekdays": [4, 5, 6],
    "time_buckets": ["evening", "late-night"],
    "social": "with-a-friend"
  },
  "past_events": [
    {
      "title": "Baby Cobra Yoga",
      "category": "Wellness",
      "venue": "Baby Cobra",
      "neighborhood": "Bushwick",
      "borough": "Brooklyn",
      "price_band": "budget",
      "rating": 2,
      "source": "picked"
    },
    { "title": "Brooklyn Steel show", "rating": 1, "source": "freetext" }
  ],
  "freetext": "Nowadays, Baby Cobra, Brooklyn Steel"
}
```

Notes:
- `categories` is a **weight map** (`1` = like, `2` = love), not just a list — lets
  ranking be graded.
- `past_events[].category/venue/neighborhood/borough/price_band` mirror the exact
  field names on an event object, so matching in §4 is a direct field compare.
- `price_band` reuses the §1.3 buckets; a small `priceBand(e.price)` helper classifies
  an event's free-text `price` into the same buckets.
- Everything is optional/sparse — a half-finished profile is valid.

---

## 3. Where it hooks into the app

All front-end, inside the single `PAGE` string in `server.py`. Marker references:

### First-run onboarding (modal/sheet)
- **Trigger:** in `load()` (`server.py:1429`), after `all[]` is populated and
  `render()` runs, check `localStorage['marquee.profile.v1']`. If absent or
  `completed_onboarding` is false → call a new `openIntake()`.
- **Component:** a new modal built exactly like the existing ones — clone the
  structure/CSS of `addModal` (`server.py:1463`) or `appsModal`/`evModal`
  (`hidden` toggle, `.evm-x` close button, `data-close` backdrop handler at
  `server.py:1512`). Multi-step sheet: Tastes → Past events → Done.
- **Category chips** reuse `chips()` rendering + `catIcon()`/`CATCOLOR`; the
  **weekday picker** reuses the `f_wdays` init block (`server.py:1468`); the
  **"pick past events"** grid reuses `evCard()` (`server.py:1299`) against `all[]`.
- **Save:** `saveProfile(obj)` writes `localStorage`, (optionally) `POST /api/profile`,
  sets the module-level `profile` var, then calls `applyProfileDefaults()` + `render()`.

### Editable "Preferences" entry point
- Add a **⚙︎ Preferences** button into the existing toolbar row next to
  `addBtn` / `subBtn` / `appsBtn` (wired at `server.py:1503`, `1510`, `1511`). Its
  `onclick` reopens the same `openIntake()` modal, pre-filled from the current
  `profile` (so the intake form doubles as the editor — one component, two entry
  points).
- Optionally surface a one-line **"Tune your feed"** nudge in the `minebar` empty
  states inside `renderList()`/`renderWeek()` (`server.py:1372`, `1424`) when no
  profile exists.

### Applying the profile on load
- New `applyProfileDefaults()`: if `profile.tastes.location_mode` is set, seed the
  `loc` variable (`server.py:1288`) and mark the matching `#loc` button `.on`
  (same toggle logic as the `#loc` click handler, `server.py:1448`). This makes the
  feed open in the user's preferred location view.

No backend change is required for the localStorage-only v1. The optional
`/api/profile` route (do_GET branch near `server.py:1670` and do_POST branch near
`server.py:1736`, mirroring the `/api/personal` handlers) is the only server touch,
and only when we add the `data/profile.json` mirror.

---

## 4. How the answers personalize the feed

Personalization is a **score + sort** layered on top of the existing `filtered()`
pipeline, deliberately non-destructive: location/category **chips the user actively
toggles still win** (hard filter), and the profile only **reorders** what's left and
adds soft boosts. This keeps the current UX intact.

### Where it plugs in
- `filtered()` (`server.py:1293`) stays the hard filter (active category chips +
  `matchLoc()`).
- Add `scoreEvent(e)` and sort the result of `filtered()` by score **within each day**
  — the feed is day-grouped in `renderList()`, `renderCal()` (`byDay`), and
  `renderWeek()` (`byDate`), so chronology must stay primary. Concretely: in each
  render fn, after building `byDay/byDate`, sort each day's array by
  `scoreEvent` descending before mapping to `evCard()`. (Alternatively, do it once in
  a `rankedFiltered()` wrapper that `renderList`/`renderCal`/`renderWeek` call.)
- For the calendar's 3-chip cap (`MAXCHIP`, `server.py:1392`), sorting each day by
  score means the **best-matching events show as the visible chips**, not just the
  first 3 by time.

### scoreEvent(e) — concrete mapping

| Profile field | Rule | Weight |
|---|---|---|
| `tastes.categories[e.category]` | add the weight (1 or 2) if present | +1 / +2 |
| `tastes.price` vs `priceBand(e.price)` | match → boost; `free-only` and event is Free → extra | +2 / −2 if over budget |
| `tastes.fav_neighborhoods` includes `e.neighborhood` | boost | +2 |
| `tastes.fav_boroughs` includes `e.borough` | boost | +1 |
| `e.near_home` && location_mode favors near | boost (reuses existing near-home signal, `server.py:1706`) | +2 |
| `tastes.weekdays` includes `parseD(e.date).getDay()` | boost | +1 |
| `tastes.time_buckets` vs `e.time` (via `parseTime`) | bucket match | +1 |
| `e.mine` | already a saved regular → always float | +3 |
| **similar-to-past**: `e` matches any `past_events[]` by category **and** (venue or neighborhood) | graded by that event's `rating` (loved=+3, liked=+1, meh=−2) | ±3 |
| `tastes.social` → category nudge (group↑ Nightlife/Festival/Sports; solo↑ Film/Arts/Wellness) | small tiebreak | +0.5 |
| `tastes.vibes` → mapped category/price/time nudges (e.g. `chill`→Wellness/Arts & evening; `high-energy`→Nightlife/Music) | small | +0.5 |

- **"Surface similar-to-past"** is the `past_events` rows: for each future event,
  compare `(category, venue, neighborhood)` against the stored signatures and apply
  the stored rating as the delta. A negatively-rated signature **demotes** matches
  (e.g. a venue they disliked sinks).
- **Soft, never hidden:** scoring only reorders; it never removes an event (except the
  budget over-run, which is a demote, not a filter). The user's explicit chip/loc
  choices remain authoritative.
- **Optional "✨ For you" affordance:** a 4th view button next to the existing
  `#views` toggle (Calendar/This week/Upcoming, `server.py:1443`) that shows the
  top-scored upcoming events ignoring day-grouping — a pure recommendation list.
  Pure add-on; defaults off in v1.

### Optional server-side use
If `data/profile.json` exists, the `/api/events` sort (`server.py:1664`) and the
`/api/widget` near-home bubbling (`server.py:1706`) can apply the same `scoreEvent`
server-side so the **TV/widget** surfaces are personalized too, not just the SPA.
v1 keeps scoring client-side only.

---

## 5. Phased rollout & open questions

### v1 (minimal, client-only)
- `localStorage` profile (`marquee.profile.v1`), no backend change.
- Intake modal: category chips + price + location mode + weekdays/time buckets.
  Past events = pick-from-feed with 👎/👍/⭐ ratings. Skippable, resumable.
- `applyProfileDefaults()` seeds `loc`; `scoreEvent()` reorders within each day in
  `renderList`/`renderCal`/`renderWeek`.
- ⚙︎ Preferences button reopens the same modal to edit.

### v2
- `data/profile.json` mirror via `GET/POST /api/profile` (so it survives cache clears
  and powers server-side `/api/events` + `/api/widget` ranking and the TV app).
- Free-text past events parsed by the existing Gemini layer into
  category/venue/neighborhood tags; vibe tagging of discovered events.
- A dedicated **"✨ For you"** view and per-event "More like this / Less like this"
  thumbs that write back to `past_events[]`.
- Feed the profile into the Gemini discovery prompt (`server.py:~532/633`) to bias
  *what gets discovered*, not just how it's ranked.

### Extending to real accounts (note)
When auth lands, the profile shape is unchanged — it moves from
`localStorage` / single `data/profile.json` to a per-user row keyed by user id
(`data/profiles/<uid>.json` or a DB table). `load_profile(uid)` / `save_profile(uid, …)`
replace the single-file helpers; the client sends a session token instead of relying on
`localStorage`. Nothing in §2's shape or §4's `scoreEvent` has to change.

### Open questions
1. **Privacy of free-text past events** — send to Gemini (v2) or keep purely local?
   Default: local in v1, opt-in for v2 parsing.
2. **How aggressive should ranking be?** Reorder-only (proposed) vs. hide poor matches.
   Recommend reorder-only to avoid an empty-looking feed.
3. **Cold start** — before any profile, fall back to today's behavior (near-home
   bubbling). Confirmed fine.
4. **Weight tuning** — the §4 weights are a starting point; expose them in an admin
   view (`/admin`) later, or leave hard-coded?
5. **Do past-event signatures decay?** A venue loved a year ago may matter less — v2
   could add recency weighting, but we don't store attendance dates in v1.

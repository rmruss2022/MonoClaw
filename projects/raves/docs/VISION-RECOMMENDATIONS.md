# RECOMMENDATION ENGINE — Architecture

## Overview

Two new tabs in the app:
- **RECOMMENDED** — personalized picks based on scene graph + self-affinity
- **EXPLORE** — discovery feed of trending/popular events you haven't committed to

---

## Tab 1: RECOMMENDED

"Shows you should go to, based on the scene you're already in."

### Primary: Scene Graph (Layer 2 — Collaborative Filtering)

The core algorithm. Cross-references attendance across all users.

**How it works:**

```
1. Collect: all shows user A has attended (attended=1)
2. Find overlap: other users who also attended ≥2 of those same shows
3. Weight those users by overlap count (more shared shows = stronger signal)
4. Collect: shows those overlapping users are marked "going" for (future dates)
5. Score: sum of weighted user signals per show
6. Filter: exclude shows user A is already going/maybe/skip
7. Rank: return top N with scores + reasoning
```

**Scoring formula:**

```
For each upcoming show S:
  score(S) = Σ (overlap_weight(U) × recency_boost(U)) for each user U going to S

  overlap_weight(U) = shared_attended_count / total_attended_by_U
  recency_boost(U)  = 1.0 if overlap shows were in last 90 days
                       0.5 if 90-180 days
                       0.25 if older
```

**Minimum thresholds:**
- Need ≥2 shared attended shows with another user to count as "scene overlap"
- Need ≥3 recommendations to display the section
- If below threshold → fall through to Self-Affinity

**Reason tags:** "3 people from your scene are going", "You and @user both went to Honey Dijon at HOY"

### Fallback A: Self-Affinity (Layer 1 — Solo Signal)

When scene graph produces <3 results, score all upcoming events against user's own history.

**Signals extracted from attendance history:**

| Signal | Weight | How |
|--------|--------|-----|
| Genre match | 0.35 | Count genres in attended shows, normalize. Techno=8, House=3 → techno show gets 0.35 × (8/11) |
| Venue loyalty | 0.25 | Attended ≥3 shows at same venue → boost. Scale by visit count. |
| Day preference | 0.15 | Distribution of attended days. If 60% are Saturdays, Saturday shows get 0.15 × 0.6 |
| Price fit | 0.10 | Compare show cost to user's average. Within ±$15 = full score, beyond = decay |
| Artist repeat | 0.15 | If a performer in the show description matches any attended show description → full score |

**Combined score:** weighted sum, 0.0–1.0 range, show top 10.

**Reason tags:** "Matches your techno taste", "You love Elsewhere", "In your price range"

### Fallback B: Popular/Trending (Layer 3 — External)

When self-affinity also runs dry (new user, no history).

- Shows with the most "going" marks across all Groundfloor users
- Shows from weekly scan marked as `topPick`
- Sort by date (soonest first), cap at 10

**Reason tags:** "Popular on Groundfloor", "Top pick this week"

### Fallback cascade:

```
scene_graph_recs = getSceneGraphRecs(userId)  // Layer 2
if scene_graph_recs.length >= 3:
  return scene_graph_recs (up to 10)

affinity_recs = getSelfAffinityRecs(userId)   // Layer 1  
combined = dedupe(scene_graph_recs + affinity_recs)
if combined.length >= 3:
  return combined (up to 10)

popular_recs = getPopularRecs()               // Layer 3
return dedupe(combined + popular_recs) (up to 10)
```

---

## Tab 2: EXPLORE

"What's happening that you haven't looked at yet."

NOT personalized. This is the discovery/browsing feed.

**Content:**
- All upcoming events the user has NOT marked going/maybe/skip
- Sorted by: date (soonest first), with optional filters
- Pulled from weekly scan results + manually added events

**Filters:**
- Genre (multi-select)
- Date range (this week / this month / custom)
- Venue
- Price range (free / under $30 / under $50 / any)

**Layout:**
- Event cards (same component as calendar)
- Quick-action: tap to mark Going/Maybe or dismiss (Skip)
- Events you Skip disappear from Explore but stay in the DB

**Difference from Calendar:**
- Calendar shows YOUR schedule (going + maybe)
- Explore shows EVERYTHING ELSE (the unsorted inbox)

---

## Data Model Changes

### New table: `user_scene_overlap` (materialized, rebuilt periodically)

```sql
CREATE TABLE user_scene_overlap (
  user_id INTEGER NOT NULL,
  overlap_user_id INTEGER NOT NULL,
  shared_count INTEGER DEFAULT 0,
  last_shared_date TEXT,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, overlap_user_id)
);
```

### New table: `recommendations` (cached results, rebuilt daily)

```sql
CREATE TABLE recommendations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  event_id TEXT NOT NULL,
  score REAL DEFAULT 0,
  source TEXT NOT NULL,       -- 'scene_graph' | 'self_affinity' | 'popular'
  reason TEXT,                -- human-readable reason tag
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  dismissed INTEGER DEFAULT 0
);
CREATE INDEX idx_rec_user ON recommendations(user_id, dismissed);
```

### Extend `events` table:

- Add `popularity_score REAL DEFAULT 0` — updated during weekly scan from RA/Dice interest counts

### User attendance needs to be per-user:

Currently `attended` and `interest` are global fields on the event (single-user design). For scene graph to work, we need:

```sql
CREATE TABLE user_events (
  user_id INTEGER NOT NULL,
  event_id TEXT NOT NULL,
  interest TEXT,              -- 'going' | 'maybe' | 'skip' | NULL
  attended INTEGER DEFAULT 0,
  cost REAL DEFAULT 0,
  notes TEXT DEFAULT '',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, event_id)
);
```

**Migration path:** Move existing event.interest/attended/cost/notes into user_events for user_id=1 (Matthew). Keep the old columns as fallback for backward compat until migration is confirmed.

---

## Scheduler Integration

Add to `lib/scheduler.js`:

- **rebuild_recommendations**: Daily at 6:00 AM ET
  - Rebuild `user_scene_overlap` from user_events attendance data
  - Run recommendation cascade for each active user
  - Cache results in `recommendations` table
  - Log run to scheduler_runs

---

## API Endpoints

```
GET  /api/recommendations          — get current user's recs (from cache)
POST /api/recommendations/refresh  — force rebuild for current user
POST /api/recommendations/:id/dismiss — hide a rec

GET  /api/explore                  — all upcoming events user hasn't rated
     ?genre=Techno,House
     &dateRange=week|month|all
     &maxPrice=50
     &venue=Elsewhere
     &page=1&limit=20
```

---

## Frontend: RECOMMENDED Tab

**Layout:**
- Section header: "FOR YOU" (if scene graph) or "BASED ON YOUR HISTORY" (if affinity) or "POPULAR" (if fallback)
- Each recommendation card:
  - Left accent bar: #E8FF41
  - Event name, venue, date, genres
  - Score indicator: subtle 1-5 bar/dot scale (not a number)
  - Reason tag: small uppercase label, e.g. "3 FROM YOUR SCENE" / "GENRE MATCH" / "VENUE YOU LOVE"
  - Quick actions: GOING / MAYBE / DISMISS
- Empty state: "Not enough data yet. Mark more shows as attended to improve recommendations."

**Frontend: EXPLORE Tab**

- Filter bar at top (genre, date, price)
- Infinite scroll or paginated event cards
- Same card component as calendar but with GOING/MAYBE/SKIP quick actions
- Skip = dismiss from explore (doesn't delete event)
- No personalization — just the raw upcoming event feed, filtered

---

## Implementation Phases

### Phase 1 (MVP — build now)
- [ ] Create `user_events` table + migration from existing fields
- [ ] Self-affinity scoring (Layer 1) — works immediately with existing data
- [ ] RECOMMENDED tab showing affinity-scored results
- [ ] EXPLORE tab with filters
- [ ] API endpoints

### Phase 2 (Multi-user — when >1 active user)
- [ ] Scene graph overlap calculation
- [ ] Collaborative filtering scoring
- [ ] Scheduler job for daily rebuild
- [ ] Reason tags showing social proof

### Phase 3 (External enrichment)
- [ ] Scrape RA interested/going counts during weekly scan
- [ ] Popularity scoring
- [ ] Trending detection (events gaining interest fastest)

---

## Success Metrics

- User marks ≥1 recommended show as "going" per week
- Recommendations surface events user wouldn't have found on their own
- Explore tab reduces "I didn't know about that show" moments
- Scene graph accuracy: ≥50% of scene-graph recs match user's actual genre/venue preferences

---

*This is the source of truth for the recommendation engine. Update as we learn.*

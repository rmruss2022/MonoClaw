# How the "Season" journal pathway is actually built in `lumen/server.py`

File: `/Users/matthew_1/MonoClaw-realized/lumen/server.py` — 13,551 lines. One file: Python
server (SQLite + a hand-rolled `BaseHTTPRequestHandler` router) on top, then the entire
single-page client as a JS string literal from roughly line 4500 down.

**Important finding up front: "Season" is two different things in this file.** A new
pathway has to pick one of the two shapes, and they are not interchangeable.

| | **(A) Season journal pathway** | **(B) Season doc (structured workbook)** |
|---|---|---|
| Where | server-side Python, `SEASON_PLAN` L1579–1610 | client-side JS, `SEASON_STAGES` L7856–7866 |
| Shape | ordered list of `(title, invitation, [step prompts])` | list of `{key, kind, title, blurb, q}` objects |
| Storage | rows in `journal` table, `kind='season'` | one JSON blob per user in `season_doc` table |
| Progress | derived — `COUNT(*)` of `kind='season'` journal rows | explicit `stages[key].done` flags in the blob |
| Served by | `GET /api/journal/season` → `season_exercise()` L1992 | `GET/POST /api/season` |
| Rendered by | `renderSeasonCompose()` L7541–7569 | `renderSeasonMap()` L7890, `renderSeasonStage()` L8012 |

The brief says "guided pathway in the Journal … lessons/steps/prompts". That is **(A)**,
`SEASON_PLAN`. It is also the same shape as `PILLAR_PLANS` (Deep journaling). So the
canonical answer is: **a new pathway is a module-level Python list of 3-tuples, plus a
`*_exercise()` accessor, plus a new member of `JOURNAL_KINDS`, plus a client render
function.** Details below.

---

## 1. The data structure to match (the load-bearing part)

### `SEASON_PLAN` — L1576–1610

```
# Season = a guided arc too. An onboarding lesson plan that helps someone name the
# chapter of life they're in and keep tending it, one sitting at a time.
#   (title, invitation, [step prompts])
SEASON_PLAN = [
    ("Name your season",
     "Before anything else — give this chapter of your life a name.",
     ["Step back from today and feel for the larger chapter you're in. …",
      "What's been true of this whole stretch of time, not just today?",
      "How did this season begin? What ended or started to let it in?"]),
    …
]
```

Exactly:

- A flat Python `list`.
- Each element is a **3-tuple**: `(title: str, invitation: str, steps: list[str])`.
- `title` — short chapter name. Rendered in the `.deep-pill` chip (L7558). Keep it under
  ~28 chars; it also appears in `chapter_titles` for the progress bar.
- `invitation` — one line. **This doubles as the saved `prompt`** (see §3), and
  `prompt` is truncated to 300 chars on save (L10650) and 80 chars in list views.
  One sentence, second person.
- `steps` — Season uses exactly **3** per chapter; `PILLAR_FUTURE` capstones use **5**.
  The count is not validated anywhere, so 3–5 is the safe convention. Rendered as a
  plain `<ol class="deep-steps">` (L7556, L7563).
- There is **no** field for an eyebrow label, teaching paragraphs, narration, timings, or
  a "done" definition. Those have no home in this structure (see §6 for where they go).
- Entries are plain Python strings with typographic apostrophes (`'`) used freely. Note
  the file mixes `'` and `'`; `esc()` handles escaping on the client.

### The sibling structure, for comparison: `PILLAR_PLANS` — L1264–1497

```
#   PILLAR_PLANS[pillar] = (arc_blurb, [ (title, invitation, [step prompts]), ... ])
PILLAR_PLANS = { "Family": ("Turn toward where you came from — one honest sitting at a time.", [ (…), (…) ]), … }
```

So a pillar plan is `(arc_blurb, [chapters])` — i.e. `SEASON_PLAN` **plus** a one-line
arc blurb wrapping it. `PILLAR_FUTURE` (L1497–1554) is a dict of single capstone 3-tuples
appended by `pillar_chapters()` (L1556–1566). `PILLAR_EXERCISES` (L1574) is a
back-compat view taking chapter[0] of each plan.

**If "Becoming" wants a top-level arc blurb (recommended — `planBar()` renders it),
model it on `PILLAR_PLANS`' tuple: `BECOMING_PLAN = (arc_blurb, [chapters])`, or keep
`SEASON_PLAN`'s flat list and return `arc` as a constant from the exercise function.**

### `PLAN_FIELDS` — L1496

`["vision", "drift", "goal", "why", "step"]` — only relevant to the `PILLAR_FUTURE`
capstones, whose 5 steps map 1:1 into the `life_plan` table via
`synthesize_plan_slice()`. A new pathway does not need this unless it should write into
the 5-Year Plan.

---

## 2. Registration: `JOURNAL_KINDS` — L1612–1614

```
# The three journaling modes. Deep = pillar work; Daily = a letter to today;
# Season = where you are in the larger arc of your life right now.
JOURNAL_KINDS = ("deep", "daily", "season")
```

This tuple is the gate everywhere. A new `kind` **must** be added here or the save
endpoint silently rewrites it to `"daily"` (L10651–10653). Consequences of adding a
4th member, all of which need checking:

- L9584 `GET /api/journal?kind=` filter — works automatically.
- L9666–9682 `GET /api/journal/week` — builds `counts`/`touched`/`missing` over
  `JOURNAL_KINDS`, and `complete` = "no missing kinds". **Adding a 4th kind makes the
  weekly-completion badge require a 4th entry per week.** Decide deliberately.
- L9684–9700 `GET /api/journal/recommend` — has its own hardcoded
  `order = ["deep", "season", "daily"]` (L9698), *not* derived from `JOURNAL_KINDS`.
  A new kind is invisible to the recommender until added here too.
- L10694–10703 the POST response's `week` block — same `JOURNAL_KINDS` loop.
- L2475 `ME.journal` counts dict — `{"daily": …, "season": …, "deep": …}`, hardcoded
  keys; add one for the new kind if the profile Atlas should show it.

### Schema — L106–113, L220–225

```
-- Season: the structured "season of life" the user fills out. One live doc per
-- user (JSON blob of stages/answers/viz), plus an archive of past seasons …
CREATE TABLE IF NOT EXISTS season_doc(
  user_id INTEGER PRIMARY KEY, data TEXT, started TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS season_archive(
  id INTEGER PRIMARY KEY, user_id INTEGER, data TEXT, started TEXT, ended TEXT);
```

Those two tables belong to shape **(B)** only. The pathway shape **(A)** needs **no new
tables** — it reuses `journal`:

```
# L220-225: Three journaling categories: 'daily' (default), 'deep' (pillar work), 'season'.
# Deep entries carry their pillar; season entries carry an optional season label (in `place`).
for jcol, jddl in (("kind", "kind TEXT DEFAULT 'daily'"),
                   ("pillar", "pillar TEXT"), ("place", "place TEXT")):
```

`journal` columns in play: `id, user_id, prompt, text, mood, reflection, shared,
created, kind, pillar, place`. **`pillar` is reserved for `kind='deep'`, `place` for
`kind='season'`** — both are nulled out for other kinds at L10654–10657. A new pathway
that needs a per-entry label (e.g. "the identity you're becoming") must either add a
column via the same `PRAGMA table_info` + `ALTER TABLE` idempotent-migration pattern
(L217–225), or relax the `place` guard at L10657 to allow the new kind.

---

## 3. The accessor: `season_exercise()` — L1992–2021

This is the function a new pathway must mirror. Full body:

```python
def season_exercise(c, u):
    """The next chapter of the Season onboarding plan — a guided arc that walks a
    person through naming and tending the chapter of life they're in. Advances by
    how many season sittings they've logged, then gently cycles."""
    chapters = SEASON_PLAN
    done = c.execute("SELECT COUNT(*) n FROM journal WHERE user_id=? AND kind='season'",
                     (u["id"],)).fetchone()["n"]
    n = len(chapters)
    idx = done % n if n else 0
    title, invitation, steps = chapters[idx]
    opening = ""
    if ai_enabled():
        prev = c.execute("SELECT text,place,created FROM journal WHERE user_id=? AND kind='season' "
                         "ORDER BY id DESC LIMIT 2", (u["id"],)).fetchall()
        …
        r = ai_json(p, timeout=20) or {}
        opening = (r.get("opening") or "").strip()[:200]
    return {"title": title, "invitation": invitation, "steps": steps, "opening": opening,
            "chapter": idx + 1, "chapters": n, "chapter_titles": [ch[0] for ch in chapters],
            "looped": done >= n}
```

Key behaviours a new pathway inherits if it copies this:

- **Progress is implicit**: `idx = done % n`. No per-chapter completion record. Entries
  do not have to be answered in order; the server just counts.
- **It cycles forever** (`% n`) and flags `looped` once you've been round once. There is
  no "finished" state and no gate on re-walking.
- The AI `opening` is **best-effort and optional** — `ai_enabled()` guard, `ai_json()`
  returns `None` on failure, and `opening` stays `""`. The pathway must be fully usable
  with `opening` empty. Max 200 chars, 22-word instruction, second person, no emoji.
- The return dict is the exact contract `planBar()` + `renderSeasonCompose()` read:
  `title, invitation, steps, opening, chapter, chapters, chapter_titles, looped`
  (and `arc` is also read by `planBar()` though `season_exercise` never sets it).

Compare `deep_exercise(c, u, pillar, chapter=None)` at **L1888** — same return contract,
plus `arc`, plus an optional explicit 1-based `chapter` override, plus capstone handling.
**A new pathway should copy `deep_exercise`'s signature if lessons should be openable out
of order** (which "Becoming" wants, since its lessons are a sequence of practices a user
may want to repeat individually), and `season_exercise`'s if it should just advance.

### Route — L9659–9664

```python
if p == "/api/journal/season":
    u = self._me(c)
    if not u:
        self._send(401, {"error": "sign in"}); return
    ex = season_exercise(c, u)
    self._send(200, {"ready": True, **ex}); return
```

Note the `{"ready": True, **ex}` wrapper — the client branches on `ex.ready` and falls
back to a flat prompt list if it's missing (L7544). A new route goes in the same `GET`
dispatch chain, next to `/api/journal/deep` (L9622) and `/api/pillar` (L9634).

`/api/pillar` (L9634–9657) is the "show me the whole plan as a list" endpoint — it
returns `chapters: [{n, title, invitation, steps: <count>, done, next}]` plus
`arc, total, sittings, rounds`. **If "Becoming" needs a lesson-list screen (it does —
10 lessons is too many for blind sequencing), copy this endpoint's shape.**

---

## 4. Writing an entry: `POST /api/journal` — L10642–10704

The single write path for all journal kinds. The relevant lines:

```python
kind = (d.get("kind") or "daily").strip().lower()
if kind not in JOURNAL_KINDS:          # L10652 — unknown kind silently becomes 'daily'
    kind = "daily"
pillar = (d.get("pillar") or "").strip()[:24]
if kind != "deep" or pillar not in PILLARS:
    pillar = None                       # L10656
place = (d.get("place") or "").strip()[:80] if kind == "season" else None   # L10657
…
refl = journal_reflect(prompt, text, kind=kind, pillar=pillar, place=place)  # L10674
mood = ((d.get("mood") or refl["mood"] or "")).strip()[:24]
_ins = c.execute("INSERT INTO journal(user_id,prompt,text,mood,reflection,shared,created,kind,pillar,place) "
                 "VALUES(?,?,?,?,?,?,?,?,?,?)",
                 (u["id"], prompt, text[:2000], mood, refl["reflection"],
                  1 if d.get("share") else 0, now_iso(), kind, pillar, place))
```

Hard limits to design against: **`prompt` ≤ 300 chars, `text` ≤ 2000 chars, `place` ≤ 80
chars, `mood` ≤ 24 chars.** Text is hard-truncated at 2000 — journal prompts must not
invite an essay longer than that.

Also at L10658–10672: `on_capstone` detection, and L10683–10689 writes the 5-Year Plan
slice. Pathway-specific post-save side effects hook in here.

### `journal_reflect()` — L1857–1886

The Keeper's post-seal reflection. **Mode-aware via an `if/elif/else` on `kind`** —
L1863 `deep`, L1868 `season`, L1874 `else: daily`. A new kind falls into the generic
`else` ("This is a daily journal letter") unless a branch is added:

```python
elif kind == "season":
    named = (" they named '%s'" % place) if place else ""
    ctx = ("This is a 'season of life' reflection%s — about the larger chapter they are "
           "living through right now, not just today. …" % named)
```

**A new pathway must add its own `elif` branch here or the reflection voice will be
wrong.** The prompt rules enforced in the shared tail (L1876–1883): 1–2 short sentences,
second person, gentle, "Do NOT advise, diagnose, or sound clinical", returns
`{"reflection", "mood"}` JSON, reflection truncated to 400 chars.

---

## 5. Client wiring — the six things to add

All inside the JS string literal.

1. **Mode registration.** Four parallel hardcoded lists, all needing the new mode:
   - L7082 `let journalMode='daily';  // 'deep' | 'daily' | 'season'`
   - L7093 `const J_MODES=[['deep','Deep','jdeep'],['daily','Daily','jdaily'],['season','Season','season']]` — `[key, label, icon]`
   - L7094 `J_MODE_BLURB={deep:…, daily:…, season:'What chapter of life are you living through right now?'}`
   - L7104 `JFACETS=[['deep','Deep','jdeep','#72716d','#999793'], …]` — `[key, label, icon, colorA, colorB]`
   - L7120 `J_MODE_ICON={deep:'jdeep',daily:'jdaily',season:'season'}`
   - L8095–8098 inside `renderJournalHome()`: `DOORS`, `JDOOR_COL`, `JMODE_IMG`, `JMODE_EYE`
     (`JMODE_EYE` is literally the **mono eyebrow label** — `season:'This chapter of life'`)
   - L7098–7100 `jweekbar()` dot row — hardcoded `['deep','daily','season']`
   - L8278 `const lbl={deep:'Deep',daily:'Daily',season:'Season'}[journalMode]||'Journal'`

2. **Fallback prompt list.** L7006 `const SEASON_PROMPTS=[…]` — 6 flat strings, used only
   when `/api/journal/season` fails or returns no `ready`. A new pathway wants its own.

3. **An icon.** L4653 `season:'<path d="…"/>'` in the icon sprite map. Raw SVG path data,
   24×24 viewBox, stroke-based, no fill.

4. **The compose renderer.** `renderSeasonCompose()` **L7541–7569**. Structure:
   fetch → fallback branch → build `topHTML` (pill + title + `planBar(ex)` + the
   `#jplace` name input + optional `.keeper-note` opening + `<ol class="deep-steps">`)
   → `composerHTML({prompt, shuffle:false, topHTML, placeholder})` →
   `wireComposerCommon(()=>composeSpeech(ex))` → `$('#jsave').onclick = sealHandler(…)`.
   `sealHandler` (L7506–7518) POSTs `{text, prompt, share:false, kind, pillar, place, chapter}`.
   Mirror `renderDeepCompose()` (L7571) if a lesson-picker screen is wanted.

5. **Dispatch.** L8284–8286 in `renderJournalCompose()`:
   `if(journalMode==='deep')renderDeepCompose(); else if(journalMode==='season')renderSeasonCompose(); else renderDailyCompose();`
   And the `jScreen` router in `renderJournal()` L8074–8083.

6. **The intro/explainer screen.** `renderSeasonIntro()` **L7837–7851** — three
   `[icon, title, body]` rows, a hero image (`/art/season-hero.jpg`), a cited evidence
   line, and a `Begin your season` button. House citation style, from L7658:
   `'Writing about your life's larger arc and goals lifted mood and <b>cut illness-related doctor visits</b> months later.'` + `'King, 2001'`
   — i.e. **plain-language finding, one bolded outcome phrase, author+year as a separate
   short field.** This is where the Dispenza evidence framing belongs, and it is why
   `research.md`'s evidence/claim split matters: this slot only takes real citations.

7. **Premium gate.** L8066–8073 — `journalMode==='season'` is gated behind `_isPrem()`.
   A new pathway is free unless added here. Also L5451 and L7701 marketing copy strings
   enumerate "Deep & Season journaling"; L7678 notes `FREE_PILLAR` mirrors the server.

8. **Demo seed data.** L581–594 and L641–642 — the seeded demo account's `kind` rotation
   list and `_demo_text()` per-kind sample text. Add the new kind or demo accounts will
   show an empty pathway.

---

## 6. Where "Becoming"'s extra fields have to go — the gap

The brief asks for, per lesson: title, mono eyebrow label, teaching (2–4 paragraphs),
guided practice narration with timings, journal prompt, and a "done" definition.
**`SEASON_PLAN`'s 3-tuple holds only three of those six.** The mapping:

| Brief's field | Home in the Season shape | Verdict |
|---|---|---|
| title | `chapter[0]` | fits |
| mono eyebrow label | `JMODE_EYE` is per-*mode*, not per-lesson | **no home** |
| teaching, 2–4 paras | nothing; `invitation` is one line | **no home** |
| guided practice + timings | nothing | **no home** |
| journal prompt | `chapter[2]` steps, or `chapter[1]` invitation-as-prompt | fits |
| what "done" looks like | nothing | **no home** |

The narration-with-timings field **does** exist in this file — but in the *meditation*
structure, not the journal one. `LESSONS` at **L6300** (client-side JS, runs to ~L6663):

```js
const LESSONS=[{
  code:'vishnu', title:'Vishnu · I', subtitle:'The Preserver',
  track:'devotion', level:'Core', focus:'Sustenance · steadiness', part:1, series:'Vishnu',
  technique:'Settling · sattva', tradition:'Hindu · the Preserver', img:'',
  soundscape:'ocean', accent:'#9f9d98',
  prompt:'What in your life are you being asked to preserve — and …?',
  blurb:'Part 1 of the Vishnu course. Meet the Preserver — …',
  segments:[
    {title:'The Preserver', cue:'Breathe naturally. Let the body settle.', secs:130,
     teach:"Come and take the seat of Vishnu, the Preserver — …"},
    …
  ]
}, …]
```

So the meditation lesson object gives exactly the missing fields:

- `subtitle` → the **mono eyebrow label**.
- `blurb` → the **teaching** (one paragraph here; it is a plain string, so 2–4
  paragraphs separated by `\n\n` would work, though no renderer currently splits them).
- `segments[].teach` → the **narration a voice reads**.
- `segments[].secs` → the **timings**. Integer seconds. Observed range 120–220s per
  segment, 3 segments per lesson, so ~8–10 min total. `lessonMins()` L6675 sums them.
- `segments[].cue` → the short on-screen instruction under the narration.
- `prompt` → the **journal prompt answered afterward**.
- `focus` / `technique` → short mono metadata strings.
- `track` → groups lessons into a journey; `TRACKS` L6665–6669
  (`{key, name, sub, accent}`), currently `philosophy` / `devotion` / `foundations`.
- `code` → stable id; progress is tracked per-code in `sessions.lesson` (L202–203) and
  read via `lessonProg(code)` L6156 / `ME.lessons` L2445–2452.
- `LESSON_ICON` L6220–6227 maps code → icon.
- Narration delivery: `lessonPlay()` **L6682+**, documented at L6677–6681 as "The
  Realized Method" — calm lead-in, each `teach` spoken **one line at a time** with
  silences between lines, a longer guided stillness closing each segment, a bell at each
  threshold, signature return. **The narration must therefore be written as discrete
  sentences/lines that stand alone when read with a pause after each.** `secs` is the
  segment budget the pacer distributes across those lines.
- "What done looks like" has **no field anywhere in either structure.** It is new.

### Recommended integration shape for "Becoming"

Given the brief's content, "Becoming" is a **hybrid**: it is a journal pathway (prompts,
sealed entries, a `kind`) whose chapters each carry a *guided visualization* (narration +
timings). Neither existing structure holds both. The two clean options:

**Option 1 — journal-primary (closest to "matching the Season pathway's shape"):**
extend the tuple to a dict so the extra fields have a home, and keep everything else
identical to Season:

```python
# BECOMING_PLAN = (arc_blurb, [lessons])
#   lesson = {"title", "eyebrow", "teach": [paras], "practice": [{"cue","secs","say"}],
#             "prompt", "done", "steps": [prompt, …]}
```
Then `becoming_exercise(c, u, lesson=None)` mirrors `deep_exercise` (L1888) and returns
`{"ready": True, title, eyebrow, invitation, teach, practice, steps, prompt, done,
opening, chapter, chapters, chapter_titles, arc, looped}` — a **superset** of the Season
contract, so `planBar()` (L7531) and `composerHTML()` (L7141) keep working unmodified and
the new fields are additive. Add `"becoming"` to `JOURNAL_KINDS` (L1614), the
`elif kind == "becoming"` branch in `journal_reflect()` (L1868), the
`/api/journal/becoming` route (next to L9659), a `/api/becoming` plan-list route
(copy L9634), and the 8 client registration points in §5.

**Option 2 — split it:** the narration lives in client `LESSONS` as a new
`track:'becoming'` (L6665), and the journal side is a thin `BECOMING_PLAN` of
`(title, invitation, [steps])` 3-tuples keyed 1:1 to the lesson codes. Zero changes to
either existing structure; the cost is that lesson content lives in two places and has
to be kept in sync by hand.

`pathway-becoming.md` is written so **either** route works: each lesson carries all six
brief fields explicitly labelled, with narration already split into standalone lines and
per-segment `secs`, and prompts kept well under the 300/2000-char save limits.

---

## 7. Line-number index

| What | Lines |
|---|---|
| `season_doc` / `season_archive` schema | 106–113 |
| `journal` kind/pillar/place migration | 217–225 |
| demo seed `kind` rotation, `_demo_text` | 581–594, 641–642 |
| `PILLARS` | 1261–1262 |
| `PILLAR_PLANS` (+ its shape comment) | 1264–1497 |
| `PLAN_FIELDS`, `PILLAR_FUTURE` | 1496, 1497–1554 |
| `pillar_chapters`, `pillar_capstone_index`, `PILLAR_EXERCISES` | 1556–1574 |
| **`SEASON_PLAN`** | **1576–1610** |
| **`JOURNAL_KINDS`** | **1612–1614** |
| `journal_reflect` (kind-aware Keeper voice) | 1857–1886 |
| `deep_exercise` | 1888–~1955 |
| `synthesize_plan_slice`, `life_plan` | ~1955–1990 |
| **`season_exercise`** | **1992–2021** |
| `journal_insights` | 2023–2045 |
| `ME.lessons` / `ME.journal` payload | 2445–2475 |
| `GET /api/journal` (list, kind filter) | 9579–9591 |
| `GET /api/pillars` | 9599–9620 |
| `GET /api/journal/deep` | 9622–9632 |
| `GET /api/pillar` (whole-plan list) | 9634–9657 |
| **`GET /api/journal/season`** | **9659–9664** |
| `GET /api/journal/week` | 9666–9682 |
| `GET /api/journal/recommend` (hardcoded order L9698) | 9684–9705 |
| **`POST /api/journal`** (the write path) | **10642–10704** |
| `POST /api/journal/share` | 10708+ |
| icon sprite, `season:` path | 4653 |
| `LESSONS` (meditation: narration + `secs`) | 6300–~6663 |
| `TRACKS`, `ROADMAP`, `lessonMins` | 6665–6675 |
| `lessonPlay()` + "The Realized Method" comment | 6677–6682+ |
| `SEASON_PROMPTS` fallback | 7006 |
| journal mode state + `J_MODES` + blurbs + facets | 7081–7120 |
| `composerHTML` | 7141 |
| `wireComposerCommon` | 7464 |
| `sealHandler` | 7506–7518 |
| `renderDailyCompose` | 7520–7527 |
| **`planBar`** | **7531–7539** |
| **`renderSeasonCompose`** | **7541–7569** |
| `renderDeepCompose` | 7571+ |
| journal-mode evidence cards (`_jwCard`, King 2001) | 7658 |
| **`renderSeasonIntro`** (explainer + citation style) | **7837–7851** |
| `SEASON_STAGES` / `RETRO_STAGE` (shape B) | 7853–7868 |
| `seasonBegin`, `seasonSave`, `seasonRadialSVG` | 7871–7889 |
| `renderSeasonMap` | 7890–7921 |
| season review helpers, `_seasonThroughline` | 7922–7946 |
| `renderSeasonJourney` | 7948+ |
| `renderSeasonEntry`, `renderSeasonStage` | 7988, 8012 |
| `renderJournal` (jScreen router) | 8059–8084 |
| premium gate | 8066–8073 |
| `renderJournalHome` (`DOORS`, `JMODE_EYE`) | 8088–8098 |
| `renderJournalCompose` (mode dispatch L8284–8286) | 8271–8287 |
| `PILLAR_LESSON`, `plesson()` | 8395–8406 |
| `renderPillarLessons` | 8162+ |

# Lumen — The 5-Year Plan (Self-Authoring Journal System)

> **Thesis.** The journal is no longer a loose set of reflective prompts. It is a
> *method* — modeled on Jordan Peterson's Self Authoring Suite (Past → Present →
> Future) — that assembles, in the user's own words, a concrete **5-Year Plan**
> across the eight pillars of life. The plan is the **product**: a tangible thing
> the app builds *with* you that measurably improves your life, and an easy,
> credible story for creators to tell ("these exercises gave me a real 5-year plan").

## The model we're basing this on (Self Authoring → 5-Year Plan)

| Self Authoring module | Lumen equivalent | Horizon |
|---|---|---|
| **Past Authoring** (understand who you were) | Pillar chapters 1–N-1 (the reflective sittings already in each pillar) | past / present |
| **Present Authoring** (faults & virtues, who you are) | Season arc + present-tense pillar chapters | present |
| **Future Authoring** (design the life you want, 3–5 yrs out) | Each pillar's **"five years on" capstone** chapter | future |

A pillar is therefore a full arc: you walk your past and present through its
reflective chapters, and the **final** chapter is the Future capstone that turns
everything you surfaced into a forward commitment. Sealing that capstone writes
that pillar's **slice** of your 5-Year Plan.

The Future capstone follows the canonical Future-Authoring structure, in Lumen's
voice, in five steps that map 1:1 to the plan fields:

1. **Vision** — the realistic best-case picture of this pillar in five years.
2. **Drift** — the cost if nothing changes (the motivational engine).
3. **Goal** — one concrete, checkable thing you want true in five years.
4. **Why** — the real reason underneath.
5. **Step** — the main obstacle + the first 90-day step.

Eight sealed capstones = a complete, personal 5-Year Plan across Family,
Relationships, Career, Finances, Health, Hobbies, Inner Growth, and Purpose.

## Architecture

### Data
- `life_plan(user_id, pillar, vision, drift, goal, why, obstacle, step, source, updated)`
  — one row per user per pillar. `source ∈ {draft, edited}`: `draft` = AI-drafted
  from the sealed capstone; `edited` = user hand-edited (protected from auto-redraft).

### Content
- `PILLAR_FUTURE[pillar]` — the 8 "five years on" capstones (title, invitation, 5 steps).
- `pillar_chapters(pillar)` — reflective chapters **+** the Future capstone appended last.
- `PLAN_FIELDS` — vision/drift/goal/why/step mapping.

### Pipeline
1. `deep_exercise()` serves the capstone as the pillar's final chapter and flags `is_plan`.
2. On seal, the journal POST handler detects a capstone sitting and calls
   `synthesize_plan_slice()` → extracts the slice **from the user's own words**
   (AI tidies, never invents; empty fields allowed; never clobbers an `edited` slice).
3. `life_plan()` assembles all eight slices + progress.

### API
- `GET  /api/plan` — the assembled 5-Year Plan (8 slices, done/total).
- `POST /api/plan` — save a hand-edited slice (`source='edited'`). *(added in this pass)*
- `POST /api/journal` — returns `plan_slice` when a capstone was just sealed.

### Frontend
- **`Your 5-Year Plan` screen** (`jScreen='plan'`): all 8 slices rendered as cards
  (vision / drift / goal / why / obstacle / first-90-days), per-pillar edit, and a
  "N of 8 pillars authored" progress bar. Unauthored pillars show a CTA to walk them.
- **Entry points:** a prominent band on the Journal home ("the product"), and the
  capstone **seal finale** ("✦ Added to your 5-Year Plan") with a view button.

## Acceptance criteria — VALIDATED 2026-11-11

Status: **all criteria met. Built, committed (`ca23d19`), and live on prod**
(`lumen-production-a8c6.up.railway.app`, SW `lumen-v28`). Evidence per item.

### A. Method fidelity
- [x] A1. All 8 pillars have a "five years on" Future capstone (vision/drift/goal/why/step).
      — `PILLAR_FUTURE` keys == `PILLARS` (8/8); each is (title, invitation, 5 steps). AST-verified.
- [x] A2. The capstone is each pillar's **final** chapter — arc runs past/present → future.
      — `pillar_chapters()` appends the capstone last; seal detects `ch_idx == nch-1`.
- [x] A3. Capstone prompts are pillar-specific and in Lumen's voice (not generic).
      — e.g. Family "the feeling in the room when you're together"; Finances "not a fantasy number".
- [x] A4. The chapter progress bar shows the capstone as the last chapter.
      — chapter list (`plessons`) is built from `pillar_chapters()`, capstone included as final.

### B. The product
- [x] B1. Sealing a capstone drafts that pillar's slice **from the user's own words**.
      — `synthesize_plan_slice()` ("extract … IN THEIR OWN WORDS … never invented"); returned as `plan_slice`.
- [x] B2. A dedicated "Your 5-Year Plan" screen shows all 8 pillar slices.
      — `renderFivePlan()` (`jScreen='plan'`), one card per pillar in `PILLARS` order.
- [x] B3. Progress reads "N of 8 pillars authored".
      — `${done} of ${total} pillars authored` + progress bar.
- [x] B4. Unauthored pillars show a CTA that opens that pillar's chapters.
      — blank card → "Walk this pillar" → `jScreen='plessons'` for that pillar.
- [x] B5. Each slice is hand-editable; saving persists and is protected from auto-redraft.
      — inline edit form → `POST /api/plan` sets `source='edited'`; synth skips `edited` slices.
- [x] B6. The plan is reachable from the Journal home and from the seal finale.
      — `#planband` on journal home + "✦ Added to your 5-Year Plan" seal finale with view button.

### C. Engineering
- [x] C1. `life_plan` table exists with (user_id, pillar) PK. — `CREATE TABLE … PRIMARY KEY(user_id,pillar)`.
- [x] C2. `GET /api/plan` returns the assembled plan (auth-gated). — prod returns 401 unauth ✓.
- [x] C3. `POST /api/plan` saves edits (auth-gated, sets source='edited'). — prod returns 401 unauth ✓.
- [x] C4. Deep seal passes `chapter` so capstone detection is exact.
      — client sends `chapter:ex.chapter||journalChapter||null`; server honors explicit chapter.
- [x] C5. compiles clean; no regressions to deep/daily/season. — `ast.parse` OK; daily/season `pillar=None` path unchanged.
- [x] C6. Committed, pushed, **deployed**, and verified live on prod.
      — `renderFivePlan`/`planband`/`Your 5-Year Plan` all served; SW `lumen-v28` live.

### D. Positioning
- [x] D1. The onboarding "self-authoring" claim is now literally true. — Future Authoring delivered across 8 pillars.
- [x] D2. The outcome is nameable in one creator-friendly line. — "Lumen built me a real 5-year plan, in my own words."

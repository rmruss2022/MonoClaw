# Life OS — Implementation Spec (ora-health-26)

**Status:** Draft for review · **Author:** Aura AI · **Date:** 2026-08-08
**Target repo:** `github.com/rmruss2022/ora-health-26` (deploys to Vercel from `frontend/`)
**Intended home when adopted:** `PLANS/10_LIFE_OS.md`

---

## 0. Guiding principle

**Extend the existing Psychological OS (PsychOS); do not build a parallel system.**
The app already owns *pillars* and *goals* (rated in onboarding via `PsychOsFirstPassScreen`,
persisted to `/api/psych-os/*`, surfaced on Home via `PillarSessionCards`). Life OS adds the four
missing pieces **on top of** PsychOS:

1. **Journeys** — a stateful arc inside a pillar (e.g. Guitar in `hobbies`, Inner-Child work in `family`).
2. **Topic Cloud** — the constellation of topics you pick from to shape a journey.
3. **Roadmap** — an ordered set of steps built from picked topics, toward a goal.
4. **Practice** — an agent-coached session scoped to the roadmap's focus, reusing the voice agent.
5. **Cycle** — close out → reflect → revamp → repeat.

Reuse, don't duplicate: `PillarKey` taxonomy, the therapy **session engine** as the Practice unit,
the ElevenLabs **voice agent** for coaching, and the **theme + UI primitives**.

---

## 1. Data model

New client service **`frontend/src/services/lifeOs.ts`** (mirrors the `psychOs.ts` convention:
thin typed client over `apiClient`, types co-located). Import `PillarKey` from `psychOs.ts` — do
NOT redefine pillars.

```ts
import { PillarKey } from './psychOs';

export type JourneyStatus = 'active' | 'closed';
export type TopicStatus   = 'idle' | 'selected' | 'in_progress' | 'done';

export interface Topic {
  id: string;
  label: string;
  weight: number;            // 1-3 → bubble size in the cloud
  status: TopicStatus;
  source: 'seed' | 'user';   // seeded library vs user-added
}

export interface RoadmapStep {
  id: string;
  journey_id: string;
  topic_id: string;
  title: string;
  order: number;
  done: boolean;
  notes?: string;
  practice_session_id?: string;  // FK → TherapySession (see §2)
}

export interface RoadmapCycle {
  id: string;
  journey_id: string;
  number: number;                // 1-based
  status: JourneyStatus;
  created_at: string;
  closed_at?: string;
  reflection?: string;
  steps: RoadmapStep[];
}

export interface Journey {
  id: string;
  user_id: string;
  pillar_key: PillarKey;         // FK to PsychOS pillar — the reuse link
  title: string;
  emoji: string;
  goal: string;                  // "where you want to get to"
  seeded?: boolean;              // structured aspects (Family) can't be deleted
  topics: Topic[];
  cycles: RoadmapCycle[];
  active_cycle_id?: string;
  created_at: string;
  updated_at: string;
}

export const lifeOsApi = {
  listJourneys(): Promise<Journey[]>,                       // GET  /api/life-os/journeys
  createJourney(input): Promise<Journey>,                   // POST /api/life-os/journeys
  updateJourney(id, patch): Promise<Journey>,               // PATCH /api/life-os/journeys/:id
  deleteJourney(id): Promise<void>,                         // DELETE /api/life-os/journeys/:id
  addTopic(journeyId, label): Promise<Topic>,               // POST /api/life-os/journeys/:id/topics
  toggleTopic(journeyId, topicId): Promise<Topic>,
  buildRoadmap(journeyId, topicIds[]): Promise<RoadmapCycle>,// POST …/journeys/:id/cycles
  toggleStep(cycleId, stepId): Promise<RoadmapStep>,
  closeCycle(cycleId, reflection): Promise<RoadmapCycle>,
};
```

**The Guitar example** maps to: `Journey{ pillar_key:'hobbies', title:'Guitar', goal:'…' }` with a
seeded topic library. **Family aspects** (Understanding My Parents, Inner Child Healing, Family
Shadow Work, …) map to `seeded:true` Journeys under `pillar_key:'family'`.

---

## 2. Backend changes (`ora-health-26/backend`)

Two additions. Both mirror the existing `psychOs` service + the therapy schema.

1. **`life_os` tables + routes** — `journeys`, `topics`, `roadmap_cycles`, `roadmap_steps`
   (user-scoped, `pillar_key` FK by string enum, matching `psych_os` conventions). Service
   `backend/src/services/lifeOs.service.ts` + routes `/api/life-os/*`. Taxonomy for seeded topic
   libraries lives beside `backend/src/services/psychOs/taxonomy.ts`.
2. **Close the `TherapySession` gap** — add nullable `pillar_key` **and** `journey_id` columns to
   `therapy_sessions` (migration). `Goal` already has `pillar_key`; sessions don't. This lets a
   Practice session roll up into its journey/pillar and feed the Topic Cloud "what have I worked
   on" view. Update `frontend/src/services/therapy.ts` `TherapySession` type + `start()` payload to
   accept optional `pillarKey` / `journeyId`.

> ⚠️ Frontend + backend taxonomy must change together (see the comment at `psychOs.ts:10-22`).

---

## 3. Agent / Practice wiring

**Seam:** the ElevenLabs voice agent, via `useElevenVoiceAgent.enterVoiceMode(behaviorId?, firstMessage?, { systemPrompt })`
(`frontend/src/hooks/useElevenVoiceAgent.ts:415`, prompt composition at `:502-526`). This is the
same channel the Marcus/therapy path already uses — no hook changes required.

**Two steps:**
1. Add **`buildCoachingPrompt(goal: string, focusTopics: string[]): string`** next to the other
   prompt builders in `frontend/src/config/dynamicBehaviors.ts` (near `generateBehaviorPrompt`
   `:1509` / `buildMeditationContextBlock` `:70`). Produces a `GOAL / FOCUS TOPICS` frame.
2. Register a **`'practice-with-ora'` `BehaviorConfig`** (add to the id union `:13-27` and the
   `DYNAMIC_BEHAVIORS` array): warm, one-step-at-a-time coach `agentInstructions`, scoped `tools`.
   Practice opens it with the goal/topics appended as `opts.systemPrompt`.

**Do NOT** build Practice on the *text* guided-session agent — it is currently stubbed
(`GuidedSessionScreen.tsx`, `TODO(06-12): wire real agent`). Practice = the therapy **session
record** (start/complete for history + `summary_text`) + the **voice agent** for the live coaching.

**Offline / no-server fallback:** keep the prototype's `localCoach` scripted fallback so Practice
degrades gracefully in web preview / App Store review with no backend.

---

## 4. Screens & navigation

New screens under **`frontend/src/screens/lifeOs/`**, reusing `components/common/Typography.tsx`,
`components/ui/Button.tsx`, `theme/index.ts` tokens, and the gradient-card recipe from
`PillarSessionCards`/`RoomCard` (there is no generic `<Card>`).

| Screen | Purpose | Notes |
|---|---|---|
| `LifeOsScreen` | Pillar dashboard (reads PsychOS pillars + journey counts) | Uses `PILLAR_KEYS`/`PILLAR_LABELS`, `assets/pillars/*.png` |
| `PillarJourneysScreen` | Journeys in a pillar + add-journey | Family shows seeded aspects |
| `JourneyScreen` | Topic Cloud ⇄ Roadmap tabs, build/close/revamp | Cloud = reskinned constellation |
| `PracticeLaunchScreen` (or reuse voice screen) | Opens the coached session | Clones `MarcusConversationScreen` pattern |

**Nav integration** (`frontend/src/navigation/AppNavigator.tsx`): add a `LifeOsStack` and route the
screens; entry point either (a) a new tab, or (b) from Home pillar cards. Decision below.

**Topic Cloud component:** port `TopicCloud.tsx` (constellation math is framework-agnostic), reskin
to forest-green/lavender; optionally upgrade bubbles to `react-native-svg` (already a dep) later.

---

## 5. Onboarding

The Life OS setup already lives in onboarding as `PsychOsFirstPassScreen` (step ~18: pillars →
goals → conditions → focus). **Extend it**, don't add a competing store:
- Add one step after goals: "**Start a journey**" — pick a pillar, name a first journey + goal
  (optional; skippable). Persists via `lifeOsApi.createJourney`.
- Keep it *upstream of AccessCode* (onboarding only completes when AccessCode flips both flags —
  `OnboardingContext.tsx:151-165`, `AppNavigator.tsx:287`) and soft-fail on server error like
  `PsychOsFirstPassScreen` already does, so a hiccup never traps the user.

---

## 6. Topic Cloud content (seed libraries)

Per-pillar seed topic libraries in the backend taxonomy, so a fresh journey isn't empty:
- **hobbies/career (Guitar-style):** user names the journey; Ora can suggest a starter set (triads,
  chords, picking, theory…) — or generated on demand from the goal via the agent.
- **family (structured):** ship the 5 seeded aspects with their topic sets (parents' story,
  inherited patterns, reparenting, intergenerational cycles, …) exactly as in the prototype.

---

## 7. Feature flag & Home entry

- Add **`flags.life_os`** (`EXPO_PUBLIC_LIFE_OS`) in `frontend/src/config/featureFlags.ts`
  (same pattern as `home_v2`), so we can ship dark and enable per-build.
- Home entry: the **live** Home is flag-driven (`HomeScreenV2` when `home_v2` on) and only the
  *legacy* `HomeScreen` renders `PillarSessionCards`. **Decision needed** (see §9) on where the
  Life OS entry point lives.

---

## 8. Phasing (recommended build order)

- **Phase 1 — Frontend slice on a branch (fast Vercel preview).** `lifeOs.ts` with a client-side
  shim (AsyncStorage) standing in for the API, all screens, Topic Cloud, Roadmap, Practice via
  voice-agent `systemPrompt` + local fallback. Behind `flags.life_os`. → **reviewable preview URL.**
- **Phase 2 — Backend.** `life_os` tables/routes + `TherapySession.pillar_key/journey_id` migration;
  swap the shim for real `apiClient` calls.
- **Phase 3 — Agent polish.** `practice-with-ora` behavior + `buildCoachingPrompt`; attribute
  sessions to journeys; Topic Cloud "worked on" derivation from completed sessions.
- **Phase 4 — Onboarding step + Home entry** once the flow feels right.

---

## 9. Open decisions for Matthew

1. **Entry point:** new bottom tab ("Life OS"), or reached from Home pillar cards? (Tabs are
   Therapy · Home · Community today.)
2. **Journeys per pillar:** cap/curate, or unlimited user-created?
3. **Practice modality:** voice-first (recommended, it's the wired path), text, or both?
4. **Family aspects:** ship exactly the prototype's 5, or your final list?
5. **Guitar topic seeds:** curated list, or agent-generated from the goal each time?

---

## 10. File-by-file change list (the PR plan)

**Frontend — new**
- `src/services/lifeOs.ts`
- `src/screens/lifeOs/{LifeOsScreen,PillarJourneysScreen,JourneyScreen,PracticeLaunchScreen}.tsx`
- `src/components/lifeOs/TopicCloud.tsx`
- `src/navigation/LifeOsStack.tsx`

**Frontend — edit**
- `src/config/dynamicBehaviors.ts` (+ `buildCoachingPrompt`, + `practice-with-ora` behavior)
- `src/config/featureFlags.ts` (+ `life_os`)
- `src/navigation/AppNavigator.tsx` (+ Life OS stack/entry)
- `src/services/therapy.ts` (optional `pillarKey`/`journeyId` on session)
- `src/screens/onboarding/PsychOsFirstPassScreen.tsx` (+ journey step) — Phase 4

**Backend — new/edit (Phase 2)**
- `backend/src/services/lifeOs.service.ts` + `/api/life-os/*` routes
- `backend/src/services/psychOs/taxonomy.ts` (seed topic libraries)
- Migration: `life_os` tables + `therapy_sessions.pillar_key`, `therapy_sessions.journey_id`

**Docs**
- `PLANS/10_LIFE_OS.md` (this spec)
```

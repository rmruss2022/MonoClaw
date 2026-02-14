# Ora AI - App Store Polish Roadmap
## Project ID: 3 | Total Tasks: 96 | Estimated Hours: 434

---

## 📊 Task Breakdown by Category

| # | Category | Tasks | Est. Hours | Priority | Key Agent |
|---|----------|-------|-----------|----------|-----------|
| 1 | Home Screen Redesign | 10 | 37h | P0 Critical | iOS-Dev + Designer |
| 2 | Multi-Vector Chat System | 15 | 83h | P0 Critical | Backend-Dev |
| 3 | Letters System | 12 | 54h | P0 Critical | iOS-Dev + Backend |
| 4 | Forum Card Redesign | 9 | 37h | P1 Important | iOS-Dev |
| 5 | Auth + Intake Quiz | 11 | 50h | P0 Critical | iOS-Dev + Backend |
| 6 | Meditation Enhancements | 8 | 34h | P1 Important | iOS-Dev + Content |
| 7 | Visual Design & Branding | 9 | 38h | P0-P2 Mixed | Designer + iOS-Dev |
| 8 | Backend Infrastructure | 9 | 39h | P0-P1 Mixed | Backend-Dev |
| 9 | Performance & Testing | 7 | 37h | P0-P1 Mixed | QA + iOS-Dev |
| 10 | App Store Preparation | 6 | 25h | P0-P1 Mixed | Designer + Content |
| **Total** | | **96** | **434h** | | |

---

## 🏗️ Phased Execution Plan

### Phase 1: Foundation & Design (Days 1-2)
**Goal:** Set up infrastructure, finalize designs, prepare brand assets

**Parallel Tracks:**
- **Designer-Agent-1:** ORA-001 (home screen design), ORA-028 (letter UX), ORA-047 (auth screens), ORA-052 (quiz design)
- **Designer-Agent-2:** ORA-066 (brand asset integration), ORA-067 (color palette), ORA-038 (forum card design)
- **Backend-Dev-1:** ORA-011 (multi-vector architecture), ORA-075 (pgvector setup), ORA-083 (migration system)
- **Backend-Dev-2:** ORA-050 (auth backend), ORA-026 (letters data model), ORA-079 (rate limiting)
- **Content-Agent:** ORA-053 (quiz questions), ORA-037 (letter templates), ORA-060 (ambient sounds)

**Deliverables:**
- [ ] All design mockups approved
- [ ] Brand assets extracted and configured
- [ ] Database schema migrations ready
- [ ] Auth backend functional
- [ ] Content written for quiz and letters

**Tasks (22):** ORA-001, 006, 011, 026, 028, 037, 038, 047, 050, 052, 053, 060, 064, 066, 067, 075, 076, 079, 081, 083, 094, 095

---

### Phase 2: Core Feature Build (Days 3-7)
**Goal:** Build all critical P0 features in parallel

**Track A - Home Screen (iOS-Dev-1):**
- ORA-002 → ORA-003 → ORA-004 → ORA-005 → ORA-007
- Dependencies: ORA-001 (design), ORA-006 (icons)

**Track B - Multi-Vector Chat (Backend-Dev-1 + Backend-Dev-2):**
- ORA-012 → ORA-013 → ORA-014 → ORA-023 (embedding pipeline)
- ORA-015 → ORA-016 (behavior selection + persistence)
- ORA-017 → ORA-018 → ORA-019 → ORA-020 (conversation flows)
- Dependencies: ORA-011 (architecture), ORA-075 (pgvector)

**Track C - Letters System (iOS-Dev-2 + Backend-Dev-3):**
- Backend: ORA-027 → ORA-035 → ORA-036
- Frontend: ORA-029 → ORA-030 → ORA-031 → ORA-032 → ORA-034
- Dependencies: ORA-026 (data model), ORA-028 (design)

**Track D - Auth + Quiz (iOS-Dev-3):**
- ORA-048 → ORA-049 → ORA-051 → ORA-054 → ORA-055 → ORA-056
- Dependencies: ORA-047 (design), ORA-050 (backend), ORA-053 (questions)

**Track E - Branding (iOS-Dev-4):**
- ORA-068 → ORA-071
- Dependencies: ORA-066, ORA-067

**Deliverables:**
- [ ] Home screen matches reference image
- [ ] Embedding-based behavior detection working
- [ ] Goal-oriented chat flows complete in 3-4 exchanges
- [ ] Letters system functional (send/receive/reply)
- [ ] Auth flow complete with quiz
- [ ] Brand fonts and colors applied

**Tasks (38):** ORA-002-005, 007, 012-023, 027, 029-032, 034-036, 048-049, 051, 054-056, 068, 071

---

### Phase 3: Enhancement & Polish (Days 8-10)
**Goal:** Build P1 features, enhance UX, polish visuals

**Parallel Tracks:**
- **iOS-Dev-1:** ORA-021 (behavior-aware chat UI), ORA-022 (completion cards), ORA-058 (meditation timer), ORA-061 (breathing guide)
- **iOS-Dev-2:** ORA-039 (forum PostCard), ORA-041 (threaded comments), ORA-043 (full post view), ORA-042 (reactions)
- **iOS-Dev-3:** ORA-059 (ambient sounds), ORA-062 (session history), ORA-063 (session types), ORA-065 (meditation completion)
- **Backend-Dev:** ORA-040 (threaded discussions backend), ORA-077 (Redis), ORA-078 (WebSocket), ORA-080 (analytics)
- **Designer-Agent:** ORA-069 (transitions), ORA-070 (loading/empty states), ORA-091 (app icon)
- **Content-Agent:** ORA-064 (meditation scripts)

**Deliverables:**
- [ ] Chat UI shows behavior state and flow progress
- [ ] Forum supports threaded discussions with reactions
- [ ] Meditation has circular timer, ambient sounds, breathing guide
- [ ] All screens have loading/empty/error states
- [ ] Real-time features via WebSocket

**Tasks (26):** ORA-008-010, 021-022, 024, 033, 039-045, 057-059, 061-063, 065, 069-070, 077-078, 080, 091

---

### Phase 4: Testing & Optimization (Days 11-12)
**Goal:** Comprehensive testing, performance optimization, bug fixes

**Parallel Tracks:**
- **QA-Agent-1:** ORA-084 (unit tests), ORA-085 (integration tests)
- **QA-Agent-2:** ORA-086 (E2E tests), ORA-090 (accessibility audit)
- **iOS-Dev:** ORA-087 (bundle size), ORA-088 (Sentry), ORA-089 (performance profiling)
- **Backend-Dev:** ORA-025 (vector broadcast perf), ORA-076 (query optimization)

**Deliverables:**
- [ ] 80%+ unit test coverage
- [ ] Integration tests for all critical flows
- [ ] 60fps scrolling, <300ms transitions
- [ ] Vector broadcast <2s latency
- [ ] Error tracking live in Sentry
- [ ] WCAG AA accessibility compliance

**Tasks (9):** ORA-025, 084-090

---

### Phase 5: App Store Prep (Days 13-15)
**Goal:** Final polish, screenshots, submission

**Parallel Tracks:**
- **Designer-Agent:** ORA-092 (screenshots), ORA-093 (preview video)
- **iOS-Dev:** ORA-072 (micro-interactions), ORA-073 (dark mode)
- **Content-Agent:** ORA-094 (App Store copy) — already started Phase 1
- **QA-Agent:** ORA-096 (submission checklist), final regression testing
- **Backend-Dev:** ORA-082 (API docs)

**Deliverables:**
- [ ] 6 professional App Store screenshots
- [ ] 30s app preview video
- [ ] App Store metadata complete
- [ ] Privacy policy and ToS published
- [ ] Dark mode support (stretch)
- [ ] App Store submission ready

**Tasks (7):** ORA-046, 072-074, 082, 092-093, 096

---

## 🔴 Critical Path

The critical path determines the minimum project duration:

```
ORA-011 (Architecture) ──→ ORA-012 (Embeddings) ──→ ORA-013 (Vector DB)
    ──→ ORA-014 (Broadcast) ──→ ORA-015 (LLM Selection)
    ──→ ORA-017 (Flow Engine) ──→ ORA-018 (Journal Flow)
    ──→ ORA-021 (Chat UI) ──→ ORA-022 (Completion UI)
    ──→ ORA-025 (Perf Test) ──→ ORA-085 (Integration Tests)
    ──→ ORA-092 (Screenshots) ──→ ORA-096 (Submission)
```

**Critical path duration: ~11 days** (with parallel execution reducing total)

**Second critical path (Auth + Onboarding):**
```
ORA-050 (Auth Backend) ──→ ORA-051 (Auth Context) ──→ ORA-054 (Quiz UI)
    ──→ ORA-056 (Onboarding Flow) ──→ ORA-085 (Integration Tests)
```

**Third critical path (Letters):**
```
ORA-026 (Data Model) ──→ ORA-027 (API) ──→ ORA-029 (Inbox UI)
    ──→ ORA-031 (Read View) ──→ ORA-032 (Thread View)
    ──→ ORA-034 (Navigation) ──→ ORA-085 (Integration Tests)
```

---

## 👥 Team Composition

| Agent Type | Count | Assignments | Hours |
|-----------|-------|------------|-------|
| **Designer-Agent** | 2 | UI/UX mockups, brand integration, app icon, screenshots | ~52h |
| **iOS-Dev-Agent** | 3-4 | React Native screens, components, animations, navigation | ~200h |
| **Backend-Dev-Agent** | 2-3 | Node.js API, embeddings, vector DB, WebSocket | ~130h |
| **QA-Agent** | 1-2 | Unit tests, integration tests, E2E, accessibility | ~28h |
| **Content-Agent** | 1 | Quiz questions, meditation scripts, App Store copy, letters | ~24h |

**Total team: 9-12 agents running in parallel**

### Agent Assignment Summary

**Designer-Agent (14 tasks):** ORA-001, 006, 028, 038, 047, 052, 066, 067, 069, 070, 074, 091, 092, 093

**iOS-Dev-Agent (44 tasks):** ORA-002-005, 007-010, 021-022, 029-034, 039, 041-046, 048-049, 051, 054, 056-059, 061-063, 065, 068, 071-073, 087-089

**Backend-Dev-Agent (27 tasks):** ORA-011-020, 023-027, 035-036, 040, 050, 055, 075-083

**QA-Agent (5 tasks):** ORA-084-086, 090, 096

**Content-Agent (6 tasks):** ORA-037, 053, 060, 064, 094, 095

---

## ⚡ Parallelization Strategy

### Maximum parallelism points:

**Day 1:** 5 agents working simultaneously (2 designers, 2 backend, 1 content)
**Days 3-7:** 9-12 agents across 5 parallel tracks
**Days 8-10:** 6 agents on enhancement tracks
**Days 11-12:** 4 agents on testing + optimization
**Days 13-15:** 5 agents on final polish + submission

### Key dependency bottlenecks:
1. **ORA-011** (Architecture doc) blocks all multi-vector work → Start immediately
2. **ORA-050** (Auth backend) blocks all auth frontend → Start Day 1
3. **ORA-066** (Brand assets) blocks all branding work → Start Day 1
4. **ORA-001/028/047/052** (Designs) block respective frontend tracks → Prioritize Day 1

---

## 📈 Priority Distribution

| Priority | Count | % | Description |
|----------|-------|---|-------------|
| Critical | 30 | 31% | Must-have for quality launch |
| High | 33 | 34% | Important for App Store quality |
| Medium | 25 | 26% | Significant enhancements |
| Low | 8 | 8% | Nice-to-have polish |

---

## 🎯 Success Metrics

### Technical Quality
- [ ] Multi-vector chat: 6 vector types operational, behavior selection <2s
- [ ] Goal-oriented flows: Natural 3-4 exchange completion
- [ ] Letters: Full CRUD with threading and AI daily letters
- [ ] Auth: Secure JWT with optional biometric
- [ ] Quiz: 10 thoughtful questions with personalization data saved

### User Experience
- [ ] App Store rating target: 4.7+ stars
- [ ] Cold start: <3s to interactive
- [ ] Scroll performance: 60fps
- [ ] All transitions: <300ms
- [ ] Accessibility: WCAG AA compliant

### Code Quality
- [ ] Unit test coverage: 80%+
- [ ] Integration tests: All critical flows covered
- [ ] Zero P0 bugs at submission
- [ ] Error tracking via Sentry
- [ ] API documentation complete

---

## 🚀 Recommended Next Steps

1. **Immediately:** Start Phase 1 — spawn Designer and Backend agents for foundational work
2. **Day 2:** Review Phase 1 deliverables, approve designs, start Phase 2 spawning
3. **Day 5:** Mid-project review — assess critical path progress, adjust if needed
4. **Day 10:** Feature freeze — no new features, testing and polish only
5. **Day 13:** App Store prep begins — screenshots need stable, polished UI
6. **Day 15:** Submission target

### First 5 Tasks to Start (No Dependencies):
1. **ORA-011** — Multi-vector architecture design (unlocks all chat work)
2. **ORA-050** — Auth backend (unlocks all frontend auth)
3. **ORA-066** — Brand asset integration (unlocks all branding)
4. **ORA-001** — Home screen design (unlocks home screen build)
5. **ORA-053** — Quiz question writing (unlocks quiz UI)

---

*Generated: 2026-02-13 by PM-Agent*
*Project: Ora AI App Store Polish (ID: 3)*
*Dashboard: http://localhost:3001/dashboard.html*

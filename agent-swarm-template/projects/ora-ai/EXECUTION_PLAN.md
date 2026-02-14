# Ora AI - Execution Plan
**Generated:** 2026-02-13 21:17 EST
**Orchestrator:** ora-orchestrator-v2

## 📊 Project Status

- **Total Tasks:** 96
- **Estimated Hours:** 434
- **Timeline:** 11-15 days
- **Goal:** App Store polish to Calm/Headspace quality level

## 🎯 Phase 1 Priority Tasks (Ready to Start)

### Critical Tasks - No Blockers

| Task ID | Title | Type | Hours | Status |
|---------|-------|------|-------|--------|
| ORA-075 | Set up pgvector extension | Backend | 4h | 🟢 READY |
| ORA-026 | Design letters system data model/API | Backend | 4h | 🟢 READY |
| ORA-047 | Design auth screens | Design | 4h | 🟢 READY |
| ORA-028 | Design letter UI/UX flow | Design | 5h | 🟢 READY |
| ORA-052 | Design intake quiz flow | Design | 5h | 🟢 READY |

### Blocked Tasks (Dependencies In-Progress)

| Task ID | Title | Blocked By | Status |
|---------|-------|-----------|--------|
| ORA-002 | Home screen header with gradient | ORA-001 | ⏳ WAITING |
| ORA-003 | Build Focus card list component | ORA-001 | ⏳ WAITING |
| ORA-004 | Wire cards to navigation | ORA-003 | ⏳ WAITING |
| ORA-012 | Embedding generation service | ORA-011 | ⏳ WAITING |

## 🚀 Recommended Execution Order

### Wave 1: Foundation (Start Immediately)
1. **ORA-075** (Backend-Dev) - pgvector setup
   - Unblocks: All AI/embedding features
   - Critical path item
   
2. **ORA-047** (Designer) - Auth screens design
   - Unblocks: Auth implementation
   - User entry point - highest visibility

3. **ORA-026** (Backend-Dev) - Letters data model
   - Unblocks: Letter implementation
   - Can run parallel with ORA-075

### Wave 2: Design Foundation (After Wave 1 Starts)
4. **ORA-028** (Designer) - Letter UI/UX flow
   - Depends on: ORA-026 (soft dependency)
   - Creates design language for letters

5. **ORA-052** (Designer) - Intake quiz flow
   - Independent work
   - Critical for onboarding experience

### Wave 3: When Dependencies Clear
6. **ORA-002** - Home screen header (iOS-Dev)
   - Starts when: ORA-001 completes
   
7. **ORA-003** - Focus card component (iOS-Dev)
   - Starts when: ORA-001 completes

8. **ORA-012** - Embedding service (Backend-Dev)
   - Starts when: ORA-011 completes

## 📋 Next Actions

### For Main Agent:
1. Review this execution plan
2. Spawn 3 specialist agents for Wave 1:
   - Backend-Dev → ORA-075
   - Designer → ORA-047
   - Backend-Dev → ORA-026

3. Monitor task ORA-001 and ORA-011 (currently in-progress)
4. When dependencies clear, spawn agents for blocked tasks

### Agent Spawn Commands Needed:
See individual task spec files in `projects/ora-ai/specs/` directory.

## 🎯 Success Metrics

- **Concurrent agents:** 3-5 maximum
- **Task completion rate:** Target >90%
- **Quality bar:** Matches Calm/Headspace standards
- **Timeline:** Complete all 96 tasks in 11-15 days

## 📁 Project Structure

```
projects/ora-ai/
├── EXECUTION_PLAN.md (this file)
├── specs/
│   ├── ORA-075-spec.md
│   ├── ORA-047-spec.md
│   ├── ORA-026-spec.md
│   ├── ORA-028-spec.md
│   └── ORA-052-spec.md
└── agents/
    └── (agent work directories)
```

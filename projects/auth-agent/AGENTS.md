# AuthAgent — Coding Agent Instructions

## Project Overview
AuthAgent is an autonomous prior authorization (PA) platform for healthcare providers.
Read docs/MVP_SCOPE.md for the complete technical spec before writing any code.
Read docs/DATA_STRATEGY.md for data sources and structures.
Read docs/ROADMAP.md for the phased build plan.

## Current Task: Loop 0 + Loop 1

Build the complete working skeleton for the AuthAgent MVP.

### Deliverables (in order):

1. **Root package.json** with npm workspaces (packages/api + packages/ui)

2. **docker-compose.yml** with:
   - PostgreSQL 15
   - Redis 7
   - API service (port 3011)
   - UI service (port 3010)
   - Environment variables for dev

3. **packages/api/** — Express.js backend:
   - `src/index.js` — server entry point, port 3011
   - `src/db.js` — PostgreSQL connection (pg library)
   - `src/migrations/001_init.sql` — full schema from MVP_SCOPE.md
   - `src/routes/pa.js` — PA request CRUD routes
   - `src/routes/dashboard.js` — stats routes
   - `src/agents/extractClinical.js` — Claude API integration for PDF analysis
   - `src/agents/buildJustification.js` — PA letter generation agent
   - `src/agents/scoreProbability.js` — rule-based probability scoring
   - `src/fhir/coverMyMeds.js` — CoverMyMeds API client (mock/sandbox)
   - `src/seeds/seed.js` — seed script for demo data

4. **packages/ui/** — Next.js 14 frontend:
   - `app/page.tsx` — Dashboard with stats + PA list
   - `app/pa/new/page.tsx` — New PA request wizard (multi-step)
   - `app/pa/[id]/page.tsx` — PA detail view
   - `app/intelligence/page.tsx` — Payer intelligence stats
   - `components/PACard.tsx` — PA request card component
   - `components/StatusBadge.tsx` — Status indicator
   - `components/ProbabilityGauge.tsx` — Approval probability display
   - `lib/api.ts` — API client (fetch wrapper)

5. **data/samples/** — Synthetic clinical note text files (10 sample cases, no real PHI):
   - `lumbar_mri_request.txt` — Lower back pain, failed PT
   - `total_knee_replacement.txt` — End-stage OA
   - `ozempic_obesity.txt` — Obesity without diabetes
   - `brain_mri_migraine.txt` — Chronic migraine
   - `scs_chronic_pain.txt` — Spinal cord stimulator
   - `cardiac_stress_test.txt` — Chest pain workup
   - `sleep_study_osa.txt` — Suspected sleep apnea
   - `nerve_conduction_neuropathy.txt` — Peripheral neuropathy
   - `post_surgical_pt.txt` — PT after knee surgery
   - `behavioral_health_medication.txt` — Psychiatric medication management

6. **scripts/seed-demo-data.js** — Populates DB with:
   - 5 payers (United, Aetna, Cigna, Humana, BCBS)
   - 20 payer_requirements rows (top 5 payers × top 4 CPT codes)
   - 2 demo practices
   - 20 demo PA requests in various states (draft/submitted/approved/denied/appealed)

## Tech Stack (use exactly these)
- **API:** Node.js, Express 4, pg (PostgreSQL client), multer (file upload), pdf-parse (PDF text), @anthropic-ai/sdk (Claude), cors, dotenv
- **UI:** Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui, recharts, React Query (@tanstack/react-query), lucide-react

## Environment Variables (.env)
```
DATABASE_URL=postgresql://authagent:authagent@localhost:5432/authagent
REDIS_URL=redis://localhost:6379
ANTHROPIC_API_KEY=your_key_here
PORT=3011
NEXT_PUBLIC_API_URL=http://localhost:3011
DEMO_MODE=true
```

## Code Quality Rules
- Use async/await (no callbacks)
- Handle all errors with try/catch — return meaningful error messages
- Log all AI API calls with timing
- Keep Claude prompts in separate prompt files (src/prompts/)
- All clinical data handling: add a comment "// PHI: treat as sensitive"
- TypeScript strict mode in UI

## Demo Data Requirements
The seed script must create realistic demo data:
- PA requests in every status (draft, submitted, approved, denied, appealed, closed)
- Realistic timestamps spread over 30 days
- Realistic approval rates (~75% approved, 15% denied, 10% pending)
- Denial reasons using real CARC codes
- Pre-generated justification letters (can be static strings for demo)
- Dashboard stats: ~$47K recovered, 89 PAs this month, 76% approval rate, avg 2.3 days

## When Done
Run this command to notify:
```bash
openclaw system event --text "AuthAgent Loop 0+1 complete: skeleton running at localhost:3010" --mode now
```

Then update docs/ROADMAP.md — change Loop 0 and Loop 1 status to ✅ Complete.

# AuthAgent — Build Roadmap

## Overview

This roadmap is structured as progressive loops — each loop produces something runnable and useful. Smaller tasks nest inside larger milestones. The agent (Claw) works through these autonomously, from bottom to top.

---

## Loop 0: Foundation (Day 1-2) ← START HERE
*Goal: Running skeleton app with demo data*

### Tasks
- [ ] `npm init` — set up monorepo with workspaces (api + ui)
- [ ] Docker Compose — Postgres + Redis + API + UI
- [ ] Database migrations (schema from MVP_SCOPE.md)
- [ ] Seed script: 5 payers, 20 CPT codes, payer requirements table
- [ ] Seed script: 2 demo practices
- [ ] Seed script: 20 demo PA requests with realistic data
- [ ] Express API skeleton: all routes returning mock data
- [ ] Next.js UI skeleton: all pages with placeholder content
- [ ] Basic auth: API key per practice (no OAuth yet)
- [ ] Health check endpoints

**Done when:** `npm run dev` shows a dashboard with demo data at localhost:3010

---

## Loop 1: AI Clinical Extraction (Day 3-5)
*Goal: Upload a PDF, get structured clinical facts out*

### Tasks
- [ ] PDF upload endpoint (Multer)
- [ ] PDF text extraction (pdf-parse)
- [ ] Claude API integration (Anthropic SDK)
- [ ] `extractClinical()` agent — prompt engineering
- [ ] Clinical extract schema + DB storage
- [ ] UI: upload step + "analyzing..." state + results display
- [ ] Error handling: bad PDF, no text extracted, API failure
- [ ] Test with 10 synthetic clinical note PDFs (create these)
- [ ] Extraction accuracy evaluation (manual review of 10 test cases)

**Done when:** Upload a clinical note PDF → see structured JSON of clinical facts in under 30 seconds

**Test PDFs to create (synthetic, no real PHI):**
1. Lumbar MRI request — lower back pain, failed PT
2. Total knee replacement — end-stage OA, BMI concerns
3. Ozempic (semaglutide) — obesity, no diabetes
4. Brain MRI — migraine, failed medications
5. Spinal cord stimulator — chronic pain, failed surgical intervention
6. Cardiac stress test — chest pain, risk factors
7. Sleep study — suspected OSA, hypertension
8. Nerve conduction study — peripheral neuropathy workup
9. PT authorization — post-surgical
10. Behavioral health — medication management

---

## Loop 2: Payer Requirements (Day 5-7)
*Goal: Know what each payer needs for each procedure code*

### Tasks
- [ ] CoverMyMeds developer account + API keys
- [ ] CoverMyMeds API client (Node.js)
- [ ] Payer requirements fetcher (CPT code + payer → requirements)
- [ ] Local requirements cache (DB + Redis)
- [ ] Manual payer requirements for top 5 payers × top 20 codes
- [ ] CMS FHIR CRD client (basic implementation)
- [ ] Payer requirements UI: show what's needed for this PA
- [ ] Gap detection: "Missing: PT records required by this payer"

**Top 5 payers to support at MVP:**
1. United Healthcare (largest, ~28% of commercial market)
2. Aetna (second, ~15%)
3. Cigna (~13%)
4. Humana (~11%)
5. BlueCross BlueShield (~13%)

**Top 20 CPT codes to support (highest PA volume + denial rate):**
```
72148 — MRI Lumbar Spine w/o contrast
72141 — MRI Cervical Spine w/o contrast
70553 — MRI Brain w/w/o contrast
27447 — Total Knee Arthroplasty
27130 — Total Hip Arthroplasty
64483 — Injection epidural steroid, lumbar
64490 — Injection facet joint
90837 — Psychotherapy 60 min
J0274 — Ozempic/Wegovy (semaglutide) injection
43239 — EGD with biopsy
93306 — Echo with doppler
95910 — Nerve conduction study (8-9 studies)
63030 — Lumbar laminotomy/discectomy
22612 — Lumbar fusion posterior
63650 — Spinal cord stimulator implant
95800 — Sleep study (polysomnography)
78452 — Nuclear cardiac stress test
93971 — Duplex scan lower extremity
77067 — Screening mammography bilateral
29881 — Knee arthroscopy with meniscectomy
```

**Done when:** Select payer + CPT code → see the specific requirements checklist for that combination

---

## Loop 3: AI Justification Drafter (Day 7-10)
*Goal: Generate a complete PA letter from clinical facts + requirements*

### Tasks
- [x] `buildJustification()` agent — prompt engineering
- [x] Prompt template library (one per PA type/specialty)
- [x] Clinical guidelines integration (NLM API or local cache)
- [x] Letter formatter (proper medical letter format with sections)
- [x] Gap handling: what to write when documentation is missing
- [x] Payer-specific language adaptation (United vs Aetna have different styles)
- [x] Justification quality scoring (internal self-evaluation prompt)
- [x] UI: justification display with rich text editor for human review
- [x] Track edits: log what humans changed from AI draft (training signal)

**Letter sections to generate:**
```
1. Patient Information Header
2. Procedure Requested + Clinical Indication
3. Clinical History (from extracted facts)
4. Prior Treatment Attempts + Outcomes
5. Medical Necessity Statement (citing guidelines)
6. Supporting Clinical Evidence
7. Expected Outcome + Alternatives Considered
8. Physician Attestation Block
```

**Prompt engineering notes:**
- System prompt includes: payer name, payer requirements, relevant clinical guidelines
- User prompt includes: extracted clinical facts formatted as structured data
- Chain-of-thought: ask model to reason through each payer requirement before writing
- Temperature: 0.3 (consistent, not creative)
- Max tokens: 2000 (full letter)

**Done when:** Clinical facts + payer requirements → complete PA letter in <20 seconds that requires <20% editing

---

## Loop 4: Probability Scoring (Day 10-12)
*Goal: Show approval probability + specific risk factors before submitting*

### Tasks
- [x] `scoreProbability()` function (rule-based v1)
- [x] CMS public use data download + processing
- [x] Base rate table: approval rate by CPT code × payer type (commercial/Medicare/Medicaid)
- [x] Risk factor rules engine:
  - POSITIVE: each payer criterion met +%
  - NEGATIVE: each missing document -%
  - NEGATIVE: known high-denial payer -%
  - POSITIVE: strong clinical history documented +%
  - NEGATIVE: procedure on high-scrutiny list -%
- [x] Probability display: gauge/progress bar + factor breakdown
- [x] Risk factor explanations: "United denies 40% of lumbar MRIs without PT records. You have PT records. ✓"
- [x] Recommendation: "Submit as-is" vs "Get missing documentation first"

**Done when:** Every PA request shows a probability score with plain-English explanation of top 3 risk factors

---

## Loop 5: Submission + Tracking (Day 12-15)
*Goal: Actually submit to payer and track status*

### Tasks
- [x] CoverMyMeds submission API integration
- [x] PA submission flow (human approval required before submit)
- [x] Submission confirmation + CoverMyMeds PA reference ID storage
- [x] Status polling (CoverMyMeds webhook or polling)
- [x] Status update notifications (simple email or Telegram message)
- [x] Status dashboard: timeline view per PA
- [x] Outcome logging: approved/denied + reason code

**HIPAA note:** CoverMyMeds production access requires:
- BAA with CoverMyMeds (they have a standard one)
- SOC 2 Type II or equivalent (or their vendor assessment process)
- For MVP demo: use sandbox, real production access after design partner onboarding

**Done when:** PA goes from "draft" → "submitted" → status updates appear in dashboard

---

## Loop 6: Appeal Automation (Day 15-18)
*Goal: When denied, auto-draft an appeal in seconds*

### Tasks
- [x] Denial reason code (CARC) database + counter-strategy mapping
- [x] `draftAppeal()` agent
- [x] Appeal types: first-level, second-level, peer-to-peer escalation
- [x] Deadline tracker: 30/60/90 day appeal windows with countdown
- [x] Appeal submission via CoverMyMeds
- [x] UI: denial notification + one-click "Generate Appeal"
- [x] Appeal outcome tracking

**CARC code counter-strategies (top 10 by volume):**
```
CO-50  (not medically necessary)    → cite clinical guidelines + peer-reviewed evidence
CO-4   (invalid procedure code)     → coding correction + resubmit  
CO-197 (no precert)                 → provide authorization records + date proof
CO-16  (claim lacks info)           → provide missing info
CO-119 (benefit max reached)        → check plan documents, file exception
CO-96  (non-covered service)        → check plan, escalate to coverage review
PR-204 (not covered, member resp)   → medical exception request
CO-170 (payment for diagnosis)      → clinical necessity argument
CO-151 (payment adjusted)           → clinical appeal with evidence
CO-22  (other insurance primary)    → COB investigation + resubmit
```

**Done when:** Denial received → click "Generate Appeal" → complete appeal letter in <30 seconds

---

## Loop 7: Polish + Demo Mode (Day 18-21)
*Goal: Demo-ready, investor-presentable product*

### Tasks
- [x] Demo mode (DEMO_MODE=true env var)
- [x] Pre-built demo scenarios (20 cases with clinical extracts + status histories)
- [x] Demo animations: animated stats count-up, skeleton loading, status transitions
- [x] Dashboard stats: total PAs, approval rate, time saved, $ recovered
- [x] Export: PA letter to PDF (HTML export for browser print-to-PDF)
- [x] Print-friendly PA letter view
- [x] Empty states: helpful onboarding when no data
- [x] Error states: graceful handling of API failures (fallback data)
- [x] DEMO_SCRIPT.md: step-by-step demo walkthrough
- [x] Activity feed: last 10 PA events with timestamps
- [x] CPT code autocomplete (20 codes searchable by code or description)
- [x] Drag-and-drop file upload for clinical notes
- [x] Clinical extract structured viewer (expandable, not raw JSON)
- [x] Letter diff view (AI draft vs human-edited)
- [x] Financial impact section (procedure value, daily pending cost)
- [x] Time saved widget (hours saved vs manual process)

**Done when:** A non-technical investor can click through the demo and understand the value in 5 minutes

---

## Loop 8: Production Hardening (Post-MVP, Month 2-3)
*Goal: Safe enough to run real PHI for design partners*

### Tasks
- [ ] HIPAA-compliant infrastructure (AWS with BAA, encrypted everything)
- [ ] BAAs signed with all vendors (Anthropic, OpenAI, AWS/Railway)
- [ ] Audit logging (every PHI access logged)
- [ ] Role-based access control (admin, billing staff, read-only)
- [ ] CoverMyMeds production API access
- [ ] First design partner onboarding
- [ ] Monitoring + alerting (basic uptime + error alerts)
- [ ] Backup + disaster recovery
- [ ] Data retention policies

---

## Loop 9: EHR Integration (Month 3-6, Post-Seed)
*Goal: Eliminate manual PDF upload — read directly from EHR*

### Tasks
- [ ] Epic FHIR R4 app registration
- [ ] SMART on FHIR OAuth implementation
- [ ] Epic FHIR client: pull Patient, Condition, MedicationRequest, Observation
- [ ] Athena FHIR client
- [ ] Auto-trigger PA on new order (instead of manual upload)
- [ ] Epic App Orchard certification submission

---

## Loop 10: ML Denial Prediction (Month 6-12, Post-Seed)
*Goal: Replace rule-based scoring with trained ML model*

### Tasks
- [ ] Training dataset: 10,000+ PA outcomes from design partners
- [ ] Feature engineering pipeline
- [ ] Model training (XGBoost or gradient boosting initially)
- [ ] Model evaluation: AUC, precision, recall by payer + CPT code
- [ ] A/B test: ML model vs rule-based, measure improvement
- [ ] Payer intelligence dashboard (what arguments win per payer)
- [ ] Model retraining pipeline (monthly)

---

## Overnight Agent Tasks

The following tasks can be handed to Claude Code to run autonomously:

### Tonight: Loop 0 + Loop 1
```
Build the complete project skeleton for auth-agent. 
See docs/MVP_SCOPE.md for architecture, schema, and UI pages.
See docs/DATA_STRATEGY.md for data structures.

Deliverables:
1. package.json with workspaces (api + ui)
2. docker-compose.yml (postgres + redis + api + ui)  
3. Database migration files (schema from MVP_SCOPE.md)
4. Seed scripts (payers, requirements, demo data)
5. Express API with all routes (mock data responses)
6. Next.js app with all pages (dashboard, new PA, PA detail, settings)
7. Synthetic clinical note PDFs (10 samples as text files)
8. Claude integration for extractClinical()

When done: openclaw system event --text "Loop 0+1 complete: AuthAgent skeleton running"
```

---

## Progress Tracking

Update this section as loops complete:

| Loop | Status | Completed | Notes |
|------|--------|-----------|-------|
| 0: Foundation | ✅ Complete | 2026-03-27 | Monorepo, Docker, schema, seed, API routes, UI pages |
| 1: AI Extraction | ✅ Complete | 2026-03-27 | Claude integration, PDF upload, demo mode fallback |
| 2: Payer Requirements | ✅ Complete | 2026-03-27 | CoverMyMeds client, payerService w/ Redis cache, 100 payer×CPT requirements, payers UI page, RequirementsChecklist component |
| 3: Justification Drafter | ✅ Complete | 2026-03-27 | buildJustification agent w/ Claude + demo mode, 5 specialty templates, quality scoring (completeness/payer-specificity/clinical-accuracy), gap detection, generate-justification endpoint, UI with regenerate + edit tracking |
| 4: Probability Scoring | ✅ Complete | 2026-03-27 | scoreProbability rewrite w/ CMS base rates (20 CPT×5 payers), 14-rule risk engine, enhanced ProbabilityGauge w/ expandable factors, probability distribution dashboard widget, /score endpoint |
| 5: Submission + Tracking | ✅ Complete | 2026-03-27 | CoverMyMeds submit/status/refresh, status state machine w/ history, polling job (30s demo/4h prod), notifications, Timeline component, submit modal w/ confirmation, demo mode: 2min decisions + 25% denial rate |
| 6: Appeal Automation | ✅ Complete | 2026-03-27 | CARC strategies (10 codes), draftAppeal agent w/ Claude + demo mode, generate-appeal/submit-appeal/appeals endpoints, pa_appeals schema (deadline_date, escalation_type, days_remaining), appeal flow UI (split view, CARC tips, deadline badges), payer intelligence appeal stats (win rate by CARC/payer, most winnable, urgent deadlines widget) |
| 7: Polish + Demo | ✅ Complete | 2026-03-27 | Demo mode banner, animated dashboard stats, activity feed, time saved widget, CPT autocomplete wizard, drag-drop upload, skeleton loading, clinical extract viewer, letter diff view, financial impact, PDF export, enriched seed data (clinical extracts + status histories), empty states |
| 8: Production Hardening | 🔲 Not started | | |
| 9: EHR Integration | 🔲 Not started | | |
| 10: ML Denial Prediction | 🔲 Not started | | |

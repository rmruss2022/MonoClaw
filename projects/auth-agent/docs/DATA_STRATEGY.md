# AuthAgent — Data Strategy

## Overview

The hardest part of building AuthAgent isn't the AI — it's the data. This document outlines exactly where every piece of data comes from, how we use it, and how we evolve the data layer from MVP to production.

---

## Data We Need (and Where to Get It)

### 1. Payer PA Requirements (What does each payer require for each procedure?)

**What it is:** The clinical criteria each payer uses to approve/deny PA requests. 
Example: "United Healthcare requires documentation of 6 weeks of failed conservative treatment before approving lumbar MRI (CPT 72148)."

**Where it comes from:**

#### MVP: CMS FHIR APIs (Free, Available Now)
The CMS Prior Authorization Final Rule (Jan 2026) requires payers to expose PA criteria via standardized FHIR APIs:

- **Coverage Requirements Discovery (CRD)** — Real-time lookup: "Does this procedure need PA for this patient's plan?"
- **Documentation Templates & Rules (DTR)** — Returns the actual questionnaire/criteria the payer requires
- **Prior Authorization Support (PAS)** — Submits PA requests electronically

**Payer FHIR Sandboxes (for development):**
```
United Healthcare:  https://developer.uhc.com/fhir
Aetna:              https://developerportal.aetna.com
Cigna:              https://developer.cigna.com
Humana:             https://developers.humana.com
BlueCross:          https://developer.bcbs.com
```

All have free developer sandboxes. Production access requires a business agreement.

#### MVP: CoverMyMeds API
CoverMyMeds is the dominant PA clearinghouse — 75%+ of electronic PAs go through them.
- Free developer API: `developer.covermymeds.com`
- Has payer requirements for 1,000+ payers
- Returns the specific fields each payer needs populated

#### MVP: Availity API (secondary clearinghouse)
- `developer.availity.com`
- Covers payers CoverMyMeds doesn't

**Data format we build:** A structured payer requirements database:
```json
{
  "payer": "United Healthcare",
  "cpt_code": "72148",
  "description": "MRI Lumbar Spine without contrast",
  "requires_pa": true,
  "criteria": [
    "Failed conservative treatment (PT) x6 weeks",
    "Documented radiculopathy or myelopathy",
    "No prior MRI in last 6 months"
  ],
  "supporting_docs_required": ["office_notes", "PT_records"],
  "average_approval_time_days": 3.2,
  "denial_rate_estimated": 0.18
}
```

---

### 2. Clinical Guidelines (What clinical evidence justifies approval?)

**What it is:** The published medical evidence that supports why a procedure is medically necessary.

**Where it comes from (all free):**

#### National Clinical Guidelines (Free)
- **NCCN** (oncology): `nccn.org/guidelines` — free with registration
- **ACC/AHA** (cardiology): `acc.org/guidelines`
- **AAOS** (orthopedics): `aaos.org/quality/clinical-practice-guidelines`
- **AAN** (neurology): `aan.com/practice/guidelines`
- **USPSTF**: `uspreventiveservicestaskforce.org`

#### NLM/PubMed (Free)
- `pubmed.ncbi.nlm.nih.gov` — searchable via API (`api.ncbi.nlm.nih.gov/lit/ctxp`)
- Use this to find supporting literature for any clinical argument

#### MCG/InterQual (Paid - Long Term)
- These are the actual criteria payers use. License ~$50-100K/year.
- **MVP workaround:** Use the public clinical guidelines above as proxies — MCG/InterQual cite the same evidence
- **Year 2:** License MCG or partner with a company that already has the license

---

### 3. Patient Clinical Data (What does this specific patient's chart say?)

**MVP: Manual upload (no EHR integration yet)**
- Practice uploads a PDF of the relevant office notes, lab results, imaging reports
- We parse with Claude/GPT-4o + PDF extraction
- Extract: diagnosis codes, symptoms, prior treatments, duration, severity

**MVP format — what we extract from the chart:**
```json
{
  "patient_id": "anon_123",
  "diagnoses": ["M54.5", "M51.16"],
  "symptoms": ["lower back pain", "right leg radiculopathy"],
  "duration_weeks": 8,
  "prior_treatments": ["physical therapy x 6 weeks", "NSAIDs"],
  "imaging": "No prior lumbar MRI",
  "provider_notes": "Patient failed conservative management..."
}
```

**Production (Year 1-2):** SMART on FHIR integration
- Epic FHIR API: `fhir.epic.com` (developer sandbox free)
- Athena FHIR API: `developer.athenahealth.com` (developer sandbox free)
- Pull structured clinical data directly from EHR — no manual upload

---

### 4. Payer Denial Pattern Data (The Secret Weapon)

**What it is:** Proprietary data on *why* each payer denies specific procedures and *what arguments win on appeal.*

**This data does not exist anywhere publicly.** We build it ourselves.

**How we build it (from day 1 with design partners):**

Every PA we process, we log:
```json
{
  "payer": "Aetna",
  "cpt_code": "27447",
  "icd10": "M17.11",
  "justification_text": "Patient has end-stage OA, failed 12 months conservative...",
  "submitted_date": "2026-03-27",
  "outcome": "denied",
  "denial_reason_code": "CO-197",
  "denial_reason_text": "Precertification/authorization/notification absent",
  "appeal_filed": true,
  "appeal_arguments": ["Clinical necessity established per MCG criterion 23.1..."],
  "appeal_outcome": "approved",
  "total_days_to_resolution": 18
}
```

After 1,000 PAs processed: we know which arguments win for which payers.
After 10,000 PAs: we have the best payer intelligence database in healthcare.
After 100,000 PAs: this database is worth more than the software.

**MVP target data collection:**
- 3-5 design partner practices
- Target: 500+ PAs in first 90 days
- Store everything, even outcomes we didn't control (ask design partners to backfill historical PA data)

---

### 5. Public CMS Claims Data (Statistical Baseline)

**What it is:** CMS publishes Medicare/Medicaid claims data with procedure code volume, denial rates, and payment amounts.

**Where to get it (all free):**
- **CMS Open Data:** `data.cms.gov/datasets`
- **Medicare Part B Provider Utilization:** Procedure code volumes by specialty
- **Medicare Inpatient/Outpatient PUF:** Payment patterns by DRG/APC
- **MEDPAR:** Inpatient claims data

**How we use it:**
- Statistical baseline for "how often does code X get denied in Medicare vs commercial"
- Identify highest-volume, highest-denial-rate codes to prioritize in MVP
- Build initial denial probability estimates before we have our own data

**Top 20 highest-volume PA codes by denial rate (from CMS data — target for MVP):**
```
CPT 72148 — MRI Lumbar Spine (high denial)
CPT 27447 — Total Knee Replacement (high denial commercial)
CPT 70553 — MRI Brain with/without contrast
CPT 64483 — Injection epidural (spine)
CPT 90837 — Psychotherapy 60 min (behavioral health)
CPT 43239 — EGD with biopsy (GI)
...
```

---

## Data Architecture

### MVP Data Stack

```
PostgreSQL (main DB)
├── payers              — Payer definitions, FHIR endpoints
├── pa_requirements     — Per-payer per-CPT-code requirements
├── pa_requests         — Every PA we've processed
├── clinical_extracts   — Extracted patient data (de-identified)
├── outcomes            — Approval/denial/appeal results
└── guidelines          — Cached clinical guideline snippets

Redis (caching)
└── payer_api_responses — Cache CRD/DTR API calls (15 min TTL)

Files (S3 or local for MVP)
└── uploaded_charts     — PDF uploads from practices (encrypted)
```

### HIPAA Compliance from Day 1

Even in MVP, we treat all patient data as PHI:
- **Encryption at rest:** AES-256 for all patient data in Postgres
- **Encryption in transit:** TLS 1.3 everywhere
- **De-identification:** Strip patient identifiers before storing in analytics tables
- **BAAs required:** Sign BAA with every vendor that touches PHI (OpenAI, AWS, etc.)
- **Audit logging:** Every access to patient data logged with timestamp + user
- **Data retention:** Delete raw PHI after PA resolution unless practice opts in to longer retention

OpenAI has a BAA for healthcare customers (API usage): `platform.openai.com/docs/baa`
Anthropic has a BAA for enterprise customers: `anthropic.com/enterprise`

---

## Seeding Demo Data (For MVP Demo)

We create a fully realistic demo dataset with no real PHI:

**Demo Practices:**
- Tri-State Orthopedic Group (5 physicians, 120 PAs/month)
- NYC Neurology Associates (3 physicians, 60 PAs/month)

**Demo PA Requests (20 pre-built scenarios):**
1. United Healthcare — Lumbar MRI — likely approve → show 89% confidence score
2. Aetna — Total Knee Replacement — likely deny first round → show appeal flow
3. Cigna — Nerve Conduction Study — quick approve → show 2-minute turnaround
4. United — Ozempic for obesity (not diabetes) — high denial → show appeal win
5. Humana — Spinal cord stimulator — complex PA → show multi-step justification build
... (15 more)

**Demo outcome data:** Pre-populate with 6 months of historical outcomes so the dashboard shows meaningful statistics.

---

## Immediate Next Steps for Real Data

### Week 1-2
- [ ] Register for CoverMyMeds developer API
- [ ] Register for Epic FHIR sandbox
- [ ] Register for Athena developer API  
- [ ] Download CMS Part B Utilization data (identify top 20 target CPT codes)
- [ ] Build payer requirements JSON for top 5 payers × top 20 codes (manually curated to start)

### Week 3-4
- [ ] Implement CRD FHIR API client (live payer requirement lookups)
- [ ] Build PDF clinical note parser (GPT-4o based)
- [ ] Test end-to-end with 3 synthetic PA requests

### Month 2
- [ ] Onboard first design partner
- [ ] Process first 50 real PAs (human-assisted, agent-drafted)
- [ ] Begin logging outcomes database

---

*This is the data foundation everything else is built on.*

# AuthAgent MVP Scope

## What We're Building (and What We're Not)

The MVP has one job: **demonstrate that AI can draft a better PA justification letter than a human, faster, with measurable outcomes.**

Everything else is future. This is the thing we validate before raising money.

---

## MVP Definition

### In Scope ✅

1. **PA Intake Dashboard** — Practice uploads a clinical note PDF + selects procedure code + payer
2. **AI Clinical Extraction** — Parse the PDF, extract relevant clinical facts (diagnosis, symptoms, prior treatments, duration)
3. **Payer Requirements Lookup** — Query CoverMyMeds API / local payer requirements DB to get what this payer needs for this code
4. **AI Justification Drafter** — Generate a complete, structured PA letter using patient data + payer requirements + clinical guidelines
5. **Approval Probability Score** — Initial statistical score based on CMS data + payer (pre-ML, rule-based to start)
6. **Manual Review + Edit** — Human (billing staff) reviews the AI draft, edits if needed, approves
7. **CoverMyMeds Submission** — One-click submission via CoverMyMeds API
8. **Status Tracking Dashboard** — Track pending/approved/denied PAs per practice
9. **Denial Alert + Basic Appeal Draft** — When denied, auto-draft initial appeal letter for human review
10. **Demo Mode** — Full working demo with synthetic data, no real PHI required

### Out of Scope for MVP ❌

- EHR direct integration (Epic, Athena) — too slow to get approved
- Fully autonomous submission (no human review) — too much liability before we have outcome data
- ML-based denial prediction — need data first
- Automated peer-to-peer scheduling
- Multi-practice billing (each practice is independent for now)
- Mobile app
- SOC 2 certification (start immediately, complete post-seed)
- CoverMyMeds production access (use sandbox for MVP, get production for design partners)

---

## MVP Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Browser (React/Next.js)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  PA Intake   │  │  AI Review   │  │  Status Dashboard │  │
│  │  Upload PDF  │  │  Edit Draft  │  │  Pending/Done/    │  │
│  │  Select CPT  │  │  Approve     │  │  Denied/Appealed  │  │
│  │  Select Payer│  │  Submit      │  │  Outcome stats    │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬──────────┘  │
└─────────┼─────────────────┼───────────────────┼─────────────┘
          │                 │                   │
          ▼                 ▼                   ▼
┌─────────────────────────────────────────────────────────────┐
│                  Express API (Node.js :3011)                  │
│  POST /api/pa/create     GET  /api/pa/:id                    │
│  POST /api/pa/analyze    POST /api/pa/:id/submit             │
│  POST /api/pa/draft      POST /api/pa/:id/appeal             │
│  GET  /api/pa/list       GET  /api/dashboard/stats           │
└────────┬──────────────────────────────────────┬─────────────┘
         │                                      │
         ▼                                      ▼
┌─────────────────────┐              ┌──────────────────────┐
│   AI Agents Layer   │              │   External APIs      │
│                     │              │                      │
│  extractClinical()  │              │  CoverMyMeds API     │
│  buildJustification │◄────────────►│  CMS FHIR CRD/DTR   │
│  scoreProbability() │              │  OpenAI/Claude       │
│  draftAppeal()      │              │  NLM PubMed API      │
└────────┬────────────┘              └──────────────────────┘
         │
         ▼
┌─────────────────────┐
│    PostgreSQL DB     │
│  pa_requests        │
│  payer_requirements │
│  clinical_extracts  │
│  outcomes           │
│  practices          │
└─────────────────────┘
```

---

## Core AI Agent Logic

### Agent 1: `extractClinical(pdfText)`
```
Input:  Raw text from office notes PDF
Output: Structured clinical facts

Prompt strategy:
- Extract: primary diagnosis + ICD-10, symptoms, duration, severity
- Extract: prior treatments attempted + outcomes
- Extract: relevant test results (labs, prior imaging)
- Extract: physician's clinical impression
- Flag: any missing info commonly needed for PA
```

### Agent 2: `buildJustification(clinicalFacts, payerRequirements, guidelines)`
```
Input:  Clinical facts + what this payer requires + relevant guidelines
Output: Complete PA justification letter, formatted

Prompt strategy:
- Match each payer requirement to available clinical evidence
- For each requirement: cite specific patient data + guideline support
- Flag gaps: "Payer requires PT records but none found in chart"
- Generate letter in standard medical justification format
- Include: medical necessity statement, clinical history, treatment summary, supporting evidence

Key: Letter must be specific to THIS payer's criteria, not generic
```

### Agent 3: `scoreProbability(clinicalFacts, payerRequirements, payerStats)`
```
Input:  Extracted clinical data + payer requirements + historical stats
Output: Approval probability % + confidence + key risk factors

MVP (rule-based, no ML yet):
- Start with base rate from CMS data for this CPT code
- Adjust UP for: each payer criterion met
- Adjust DOWN for: missing documentation, high-denial payer, high-denial code
- Flag specific risks: "United denies 40% of lumbar MRIs without PT documentation"

Year 2 (ML model):
- Train on our own outcomes database
- Feature engineering from payer + CPT + clinical data + letter quality score
```

### Agent 4: `draftAppeal(originalPA, denialReasonCode, payerPolicies)`
```
Input:  Original PA, denial reason code (CARC), payer policy language
Output: Appeal letter + recommended escalation path

Denial reason code mapping:
- CO-50 (not medically necessary): cite clinical guidelines + peer-reviewed literature
- CO-197 (no precert): administrative issue, cite submission records
- CO-4 (invalid code): coding correction
- PR-204 (not covered): check plan documents, escalate to peer-to-peer

Key: Each CARC code has a different optimal counter-strategy
```

---

## Tech Stack

### Frontend
- **Next.js 14** (App Router)
- **Tailwind CSS** + shadcn/ui components
- **React Query** for API state management
- **React Hook Form** for PA intake form
- **recharts** for dashboard statistics

### Backend
- **Node.js + Express** (familiar from monoclaw services)
- **PostgreSQL** (local dev: Docker; prod: Railway or Supabase)
- **Multer** for PDF upload handling
- **pdf-parse** or **pdf.js** for text extraction

### AI
- **Anthropic Claude claude-sonnet-4-6** (primary — best for medical reasoning, long context)
- **OpenAI GPT-4o** (fallback / comparison testing)
- Both have HIPAA BAAs available

### External APIs
- **CoverMyMeds API** (PA submission + payer requirements)
- **CMS FHIR APIs** (payer criteria — CRD/DTR)
- **NLM Entrez API** (clinical literature lookup — free)

### Infrastructure (MVP)
- **Local dev:** Docker Compose (Postgres + Redis + API + Frontend)
- **Demo deploy:** Railway.app (fast, cheap, familiar from Daylight Energy project)
- **File storage:** Local filesystem for MVP → S3 for production

---

## Database Schema (MVP)

```sql
-- Core entities
CREATE TABLE practices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  npi TEXT,
  specialty TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE payers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  payer_id TEXT, -- CoverMyMeds payer ID
  fhir_endpoint TEXT,
  covermymeds_id TEXT
);

CREATE TABLE payer_requirements (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  payer_id UUID REFERENCES payers(id),
  cpt_code TEXT NOT NULL,
  requires_pa BOOLEAN DEFAULT true,
  criteria JSONB, -- array of requirement strings
  supporting_docs TEXT[], -- list of required document types
  avg_approval_days DECIMAL,
  denial_rate_estimate DECIMAL,
  last_updated TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE pa_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  practice_id UUID REFERENCES practices(id),
  payer_id UUID REFERENCES payers(id),
  patient_id TEXT, -- anonymized/hashed
  cpt_code TEXT NOT NULL,
  icd10_codes TEXT[],
  status TEXT DEFAULT 'draft', -- draft|submitted|approved|denied|appealed|closed
  clinical_extract JSONB, -- extracted clinical facts
  justification_draft TEXT, -- AI-generated letter
  justification_final TEXT, -- human-approved version
  approval_probability DECIMAL,
  probability_factors JSONB, -- breakdown of score
  covermymeds_pa_id TEXT, -- CoverMyMeds reference
  submitted_at TIMESTAMPTZ,
  decision_at TIMESTAMPTZ,
  outcome TEXT, -- approved|denied|partial
  denial_reason_code TEXT,
  denial_reason_text TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE pa_appeals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pa_request_id UUID REFERENCES pa_requests(id),
  appeal_draft TEXT,
  appeal_final TEXT,
  appeal_type TEXT, -- first_level|second_level|peer_to_peer|external
  submitted_at TIMESTAMPTZ,
  outcome TEXT,
  outcome_date TIMESTAMPTZ
);

CREATE TABLE uploaded_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pa_request_id UUID REFERENCES pa_requests(id),
  doc_type TEXT, -- office_notes|lab_results|imaging|pt_records
  filename TEXT,
  filepath TEXT,
  extracted_text TEXT, -- raw text after PDF parsing
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## MVP Pages / UI

### 1. Dashboard (/)
- Stats: Total PAs this month, Approval rate, Avg processing time, $ recovered
- Recent PA requests table with status badges
- Quick action: "New PA Request"

### 2. New PA Request (/pa/new)
- Step 1: Select practice, enter patient (anonymized ID), select payer
- Step 2: Enter CPT code + ICD-10 codes + procedure description
- Step 3: Upload clinical notes PDF
- Step 4: "Analyze" → AI extracts clinical facts (show loading, then results for review)
- Step 5: "Generate Draft" → AI writes justification (show draft with edit capability)
- Step 6: Review probability score + risk factors
- Step 7: Approve + Submit (or save as draft)

### 3. PA Detail (/pa/:id)
- Full PA record: clinical extract, justification letter, submission status
- Timeline of events (created, submitted, decision received, appeal filed)
- If denied: "Generate Appeal" button → appeal draft

### 4. Payer Intelligence (/intelligence)
- Denial rates by payer × CPT code (from our accumulated data)
- "Winning arguments" for common denial types
- Tips by payer: "United Healthcare always requires PT records for lumbar codes"

### 5. Settings (/settings)
- Practice profile
- API connections (CoverMyMeds, EHR integrations)
- Notification preferences

---

## Demo Mode

The app ships with a `DEMO_MODE=true` env var that:
- Loads 20 pre-built PA scenarios (no real PHI)
- Shows realistic processing animations
- Pre-populates the outcome database with 6 months of stats
- Lets anyone click through a full PA workflow without uploading anything

**Demo scenarios (see DATA_STRATEGY.md):**
- Fast approve (orthopedic brace — United)
- Likely deny, successful appeal (lumbar MRI — Aetna)
- Complex multi-step (spinal cord stimulator — Cigna)
- High-stakes urgent (oncology chemo — United)

---

## Definition of Done (MVP)

MVP is "done" when a real billing staff member at a real practice can:

1. Upload a clinical note PDF
2. Select payer + CPT code
3. Review the AI-generated justification
4. Click submit
5. See status updates in the dashboard
6. Generate an appeal if denied

...and do it in under 5 minutes for a PA that previously took 24 minutes.

**Success metric:** AI draft requires less than 20% editing by the human reviewer.
**Stretch metric:** Approval rate on AI-drafted PAs ≥ baseline approval rate for practice.

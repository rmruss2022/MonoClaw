# AuthAgent — What We Actually Built

*Honest assessment of the current state: what works, what's simulated, what's missing, and how real the data is.*

---

## TL;DR

We built a **working MVP demo** with a real Express API, real Next.js UI, real database, and real AI integration paths. The core product loop works end-to-end. However, **three of the four AI agents fall back to rule-based/template logic** when no Anthropic API key is present, and **the data is seeded — not live from real payers.** This is an honest, well-built demo, not a production system.

---

## What's Actually Running Right Now

### Infrastructure
| Component | Status | Notes |
|-----------|--------|-------|
| Express API (port 3011) | ✅ Running | PostgreSQL connected, all routes live |
| Next.js UI (port 3010) | ✅ Running | All pages functional |
| PostgreSQL | ✅ Running | Seeded with 20 PA requests, 5 payers, 50 requirements |
| Redis | ❌ Not running | Used for caching in code but not started — app falls back gracefully |
| CoverMyMeds API | ⚠️ Sandbox mock | Real API client written, returns simulated responses |
| CMS FHIR API | ⚠️ Not connected | Client written, not called in current flow |
| Anthropic Claude | ⚠️ Key-dependent | Falls back to rule-based logic without a real API key |

---

## The Four AI Agents — What They Actually Do

### Agent 1: `extractClinical()` — Clinical Note Parser
**What it does with a real API key:**
- Sends the full clinical note text to Claude claude-sonnet-4-6
- System prompt instructs it to return structured JSON: diagnosis, ICD-10 codes, symptoms, duration, prior treatments, medications, imaging, lab results, physical exam findings
- Temperature 0.1 (deterministic, not creative)
- Falls back to regex/keyword extraction if API fails

**What it does without an API key (demo mode):**
- Regex for ICD-10 codes (`[A-Z]\d{2}\.?\d{0,4}`)
- Keyword matching for symptoms (pain, numbness, weakness, etc.)
- Duration extraction (regex for "X weeks/months/years")
- Keyword matching for treatments (physical therapy, NSAIDs, injection, etc.)
- Medication name matching against a hardcoded list of 16 common drugs

**Honest assessment:** The demo-mode extraction is passable for a demo but would miss a lot in real clinical notes. Real clinical notes are messy, abbreviated, use shorthand. The Claude version would be dramatically better — this is where the API key matters most.

---

### Agent 2: `buildJustification()` — PA Letter Drafter
**What it does with a real API key:**
- Two Claude calls: (1) generate the full 8-section letter, (2) quality-score the letter
- System prompt establishes it as a "clinical documentation specialist with 15+ years PA experience"
- User prompt includes: structured clinical facts as JSON + payer requirements + specialty template
- Specialty templates loaded per CPT code (orthopedic, neurology, cardiology, behavioral-health, general)
- Returns: `{ letter, gaps, qualityScore }` where gaps = requirements not met by available docs

**What it does without an API key (demo mode):**
- String interpolation template that fills in the 8 sections from `clinicalFacts` fields
- Payer criteria listed verbatim with "ADDRESSED — See clinical history above" (not actually verified)
- Quality score from rule-based heuristics: checks for section headers, keyword matches against payer criteria
- **The demo letter looks real and is structurally correct but is not clinically reasoned**

**Honest assessment:** The template output is good enough to show investors the format and flow. A real clinical reviewer would spot that it's template-generated. With Claude, the letters read like a board-certified physician wrote them.

---

### Agent 3: `scoreProbability()` — Approval Probability Engine
**What it does (same in both modes — no Claude needed):**
- Loads `baseDenialRates.json`: denial rates for 20 CPT codes × 5 payers
- Loads `riskFactors.json`: 15+ adjustment rules
- Starts with base approval rate (1 - denial rate) for this payer + CPT code
- Applies adjustments: +% for each met criterion, -% for each gap
- Returns: probability (0-1), confidence level, factor breakdown, recommendation

**This is the most "real" agent** — it doesn't need Claude because the logic is deterministic.

**Are the base rates accurate?**
Partially. Here's the honest breakdown:
- Lumbar MRI (72148): 18-22% denial rate used → real-world estimates range 15-28% depending on study. **Reasonable.**
- Total Knee (27447): 20-25% used → AMA surveys suggest 23-31% for musculoskeletal. **Reasonable.**
- Ozempic obesity (J0274): 48-58% used → This is actually *conservative*. Real-world Ozempic PA denial rates for obesity (non-diabetes) are reported at 60-75%+ by advocacy groups. **Slightly underestimated.**
- Spinal cord stimulator (63650): 28-40% used → Published literature suggests 35-45%. **Reasonable.**
- Sleep study (95800): 4-10% used → PA denial rates for sleep studies are genuinely low (8-12%). **Reasonable.**
- Behavioral health (90837): 11-20% used → Mental health PA denials highly variable, 15-25% in commercial. **Reasonable.**

**The payer-specific splits are approximations** — we don't have real payer-by-payer denial rate data. We used United > Aetna > Cigna > Humana > BCBS as a rough ordering based on published industry perception, not hard data. Real payer intelligence would come from processing actual PA outcomes.

---

### Agent 4: `draftAppeal()` — Autonomous Appeal Writer
**What it does with a real API key:**
- Looks up CARC strategy from `carcStrategies.json` (10 codes, each with counter-strategy, required evidence, success rate, escalation path)
- Calculates deadline (180 days commercial, 120 Medicare, 60 Medicaid)
- Claude call with: original PA details + denial reason + CARC strategy + payer name
- Returns full appeal letter citing specific MCG criteria names, payer policy language, peer-reviewed evidence

**What it does without an API key:**
- Loads CARC strategy from JSON
- Template interpolation: fills in the original justification, adds appeal-specific language per CARC code
- Less precise but structurally correct

**Are the CARC strategies accurate?**
Yes — these are based on real healthcare billing practices:
- CO-50 (not medically necessary): cite clinical guidelines + peer-reviewed evidence ✅
- CO-197 (no precertification): provide authorization records + submission proof ✅
- CO-4 (invalid code): coding correction ✅
- CO-96 (non-covered): check plan documents + exception request ✅
- PR-204 (member responsibility): medical exception ✅

The success rate estimates (e.g. "73% overturn rate for CO-50 with strong clinical evidence") are based on industry reports (KFF, AMA surveys) that show ~80% of denied PAs that are appealed are overturned — we applied this across CARC codes with adjustments. Not exact science, but directionally accurate.

---

## The Seeded Data — How Real Is It?

### Payer Requirements Data
Stored in the database after seeding. **Quality varies:**

**High confidence (matches published payer policies):**
- Lumbar MRI (72148) — United: "Failed PT x6 weeks, documented radiculopathy, no prior MRI in 6 months" → matches UHC's published Coverage Determination Guideline for MRI
- Ozempic (J0274): "BMI ≥30 with comorbidity OR BMI ≥27 with T2DM, failed structured program x6 months" → matches most commercial payer obesity drug policies
- Spinal cord stimulator (63650): "Failed back surgery syndrome, failed medication, psychological clearance, SCS trial required" → standard industry criteria

**Medium confidence (based on general knowledge, not verified against current payer docs):**
- Total Knee (27447): Kellgren-Lawrence Grade III/IV requirement — used by some payers, not all
- Behavioral health (90837): DSM-5 diagnosis + treatment plan — standard, but payer implementation varies significantly

**What real production would need:**
- Direct API calls to each payer's CDG (Coverage Determination Guideline) portal
- CoverMyMeds DTR API returning the actual current questionnaire
- Regular updates when payers change their criteria (happens quarterly)

### PA Request Demo Data
20 seeded PA requests with realistic distributions:
- 10 approved (50%) — slightly below real-world ~65-70% commercial approval rate
- 3 denied (15%) — reasonable
- 2 appealed (10%)
- 2 appeal_draft (10%)
- 2 submitted/pending (10%)
- 1 closed (5%)

**The denial codes used:**
- CO-50 (not medically necessary) — most common real-world PA denial, ~35% of all denials ✅
- CO-197 (no precertification) — second most common, ~25% ✅
- CO-4 (invalid code) — less common (~8%) but realistic ✅
- CO-96 (non-covered) — realistic for Ozempic/obesity case ✅

**The financial data:**
- `revenue_recovered: $5,830` — across 20 PAs this is low. Real practices: average denied claim ~$1,200, so 3 denied × $1,200 would be ~$3,600 if all overturned. $5,830 implies partial overturn + some higher-value procedures. **Plausible but slightly optimistic.**

---

## What Is Actually Missing

### Critical Gaps (would break in real production)

**1. No real payer API integration**
- CoverMyMeds client written but returns mocked responses
- CMS FHIR CRD/DTR not actually called
- Payer requirements come from our seeded DB, not live payer systems
- **Impact:** In real use, payer criteria would be dynamic. Our static DB gets stale.

**2. No real PDF parsing pipeline**
- The UI accepts text input or file upload
- PDF parsing uses `pdf-parse` which works fine for text-heavy PDFs
- Fails on: scanned PDFs (images), handwritten notes, complex medical forms with tables
- **Impact:** ~40% of real clinical notes are scanned images. Need OCR (AWS Textract or similar).

**3. No EHR integration**
- Manual text/PDF upload only
- No FHIR R4 pull from Epic/Athena/Cerner
- **Impact:** In real practice, the workflow requires copying/pasting or uploading notes. Still saves time, but not frictionless.

**4. No authentication**
- API has no auth beyond an optional API key header
- Multi-practice data is not isolated by practice login
- **Impact:** Fine for demo, not for production with real PHI.

**5. No HIPAA-compliant infrastructure**
- Running on localhost with no encryption at rest
- No audit logging of PHI access
- No BAAs with cloud vendors (because nothing is cloud-hosted yet)
- **Impact:** Cannot use with real patient data until addressed.

**6. CoverMyMeds sandbox ≠ production**
- Real production access requires business agreement + vendor assessment
- Sandbox returns canned responses
- **Impact:** The submission flow looks real but isn't actually filing with payers.

### Missing Features (planned, not built)

- ❌ ML-based denial prediction (Loop 10 — needs real outcome data)
- ❌ Peer-to-peer review scheduling
- ❌ Email/SMS notifications to billing staff
- ❌ Practice-level user accounts and authentication
- ❌ LaunchAgent / auto-start service setup
- ❌ Real-time status polling from CoverMyMeds
- ❌ Export appeal letter to print-ready PDF
- ❌ Mobile-responsive UI (partially responsive but not tested on mobile)

---

## What This Demo Actually Proves

**For an investor or design partner conversation, this demo shows:**

1. ✅ The full product workflow exists and works end-to-end
2. ✅ Clinical note → structured extract → PA letter → probability score → submission → appeal is a real, working loop
3. ✅ The payer requirements data structure is correct and realistic
4. ✅ The probability scoring logic is sound and explainable
5. ✅ The appeal system knows the right counter-strategy per CARC code
6. ✅ The UI is clean, professional, and investor-presentable

**What it doesn't prove (yet):**
1. ❌ That Claude's letter generation is better than a human (need real API key + real PA outcomes)
2. ❌ That payer requirements are accurate to current payer policies (need live API)
3. ❌ That the system handles real clinical note formats (need OCR + real uploads)

---

## The Immediate To-Do List to Make This Real

**Week 1 — Make it real for demo partners:**
1. Add `ANTHROPIC_API_KEY` to `.env` → all 4 AI agents use real Claude
2. Register for CoverMyMeds developer account (free, 2-3 days approval)
3. Register for Epic FHIR sandbox (free, 1-2 weeks approval)
4. Test with 5 real (de-identified) clinical notes from a willing physician contact

**Week 2-3 — Make it production-safe:**
5. Add OCR for scanned PDFs (AWS Textract, $0.0015/page)
6. Add basic auth (JWT + practice login)
7. Add audit logging for PHI access
8. Deploy to Railway.app with proper env vars (not localhost)

**Month 1-2 — Make it real for design partners:**
9. Sign BAAs with Anthropic + Railway/AWS
10. Get CoverMyMeds production API access
11. Onboard first design partner practice (free 90-day trial)
12. Start logging real PA outcomes → beginning of the payer intelligence database

---

*Written by Claw, March 2026. If this doc is wrong about something, fix it — accurate self-assessment beats looking good on paper.*

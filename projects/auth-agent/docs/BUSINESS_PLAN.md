# AuthAgent — Business Plan

## Executive Summary

AuthAgent is a B2B SaaS platform targeting the $35B+ prior authorization (PA) administrative burden in US healthcare. We build the only fully agentic PA system that autonomously drafts clinical justifications, predicts denial probability, submits to payers, and autonomously appeals denials — requiring zero physician or staff time after the initial order is placed.

**Target market:** Independent and mid-size physician practices (1-50 physicians), specialty groups (oncology, orthopedics, neurology), and digital health companies that prescribe medications or procedures requiring PA.

**Revenue model:** Per-PA transaction fee ($6-8/PA) + monthly platform fee + contingency on recovered appeals (10-15%).

**Funding target:** $1.5-3M seed round after MVP validation with 3-5 design partner practices.

---

## The Problem

### By the Numbers

| Metric | Value | Source |
|--------|-------|--------|
| Annual PA administrative cost | $35B+ | AMA 2024 |
| Physician time on PA per week | 13 hours | AMA Survey |
| Average cost per PA (manual) | $14 | CAQH Index 2024 |
| PAs per physician per month | ~40 | Industry average |
| PA denials eventually overturned | 80%+ | KFF Analysis |
| Patients who abandon care due to PA | 1 in 4 | AMA Survey |
| Time per authorization (staff) | 24 minutes | CAQH Index 2024 |

### The Human Cost

- More than 1 in 4 physicians report a PA has led to a **serious adverse event** for a patient
- 78% of physicians report PA causes patients to **abandon recommended treatment**
- Average wait time for payer approval: **4+ days** (Waystar data)
- A single denied PA that gets appealed and overturned costs the practice $80-120 in staff time — for money that was always owed

### Why Current Solutions Fail

| Tool | What they do | What they don't do |
|------|-------------|-------------------|
| Waystar Auth Accelerate | Automates PA *submission* workflow | Doesn't draft clinical justifications |
| Cohere Health | Helps payers auto-approve | Works for payers, not providers |
| Rhyme | EHR-integrated PA tracking | No AI reasoning, no appeal automation |
| Develop Health | Medication PA only | Narrow scope |
| Epic (built-in) | Surfaces PA requirements | No autonomous action |
| Athena (built-in) | Gap identification in forms | Workflow tool, not agent |

**The gap:** Nobody autonomously drafts the clinical argument, scores it for approval likelihood, and autonomously fights the appeal. That's AuthAgent.

---

## Market Size

### Total Addressable Market (TAM)
- 230,000+ physician practices in the US
- ~$14/PA × 40 PAs/practice/month × 12 months = **$1.5B/year** just in administrative cost
- AuthAgent charges ~$7/PA → captures ~50% of the administrative cost as software revenue
- **TAM: $750M-1.5B/year** in the practice segment alone

### Serviceable Addressable Market (SAM)
- Focus on specialty practices (highest PA volume): Oncology, Ortho, Neurology, Cardiology, Radiology
- ~25,000 specialty practices in US
- Average 80-200 PAs/practice/month in high-volume specialties
- **SAM: ~$150-300M/year**

### Serviceable Obtainable Market (SOM) — Year 3
- 500 practices at $1,500/month average = **$9M ARR**
- + appeals contingency = **+$2M ARR**
- **Year 3 target: $11M ARR**

---

## Revenue Model

### Pricing Tiers

#### Starter — Small Practice (1-5 physicians)
- $8/PA + $299/month platform fee
- ~40-100 PAs/month = $320-800/month in PA fees
- **Total: $619-1,099/month per practice**
- ARR per customer: ~$7,400-13,200

#### Growth — Mid-Size Group (6-20 physicians)
- $6/PA + $799/month platform fee
- ~150-400 PAs/month = $900-2,400 in PA fees
- **Total: $1,699-3,199/month**
- ARR per customer: ~$20,000-38,000

#### Enterprise — Large Group/Health System (20+ physicians)
- Custom pricing + % of recovered appeals
- **ARR: $50,000-500,000+**

### Secondary Revenue Streams

**Appeal Contingency (Year 2+)**
- 10-15% of successfully recovered denied claims
- Average denied claim value: $1,200
- If AuthAgent recovers $200K in denials/year for a practice: **$20-30K additional revenue**

**Payer Intelligence API (Year 3+)**
- License the anonymized payer-denial-pattern database to:
  - Other health tech startups
  - Revenue cycle management companies
  - Healthcare consulting firms
- **$50-200K/year per enterprise license**

---

## Go-To-Market Strategy

### Phase 1: Design Partners (Months 1-6)
**Goal:** 3-5 practices using MVP in exchange for free access and data sharing

**Target:** 
- Orthopedic surgery groups (high PA volume, mostly elective procedures, clear ROI)
- Neurology practices (high denial rates, complex justifications)
- Oncology groups (life-or-death urgency, strong motivation to adopt)

**Approach:**
1. Cold outreach to practice administrators (not physicians) — they own the billing pain
2. Lead with the AMA survey data: "You're spending 13 hours/week on this. We eliminate it."
3. Offer 90-day free trial in exchange for: outcome data + feedback + reference
4. White-glove onboarding: we set it up, we monitor, we fix everything

### Phase 2: Specialty Association Channel (Months 6-18)
- Partner with AAOS (American Academy of Orthopaedic Surgeons) — 39,000 members
- Partner with AAN (American Academy of Neurology) — 40,000 members
- Offer member discount → instant distribution to target buyer
- Present at annual conferences with live demo

### Phase 3: EHR Marketplace (Months 12-24)
- Epic App Orchard listing → 250M patient records
- Athena Marketplace listing → 160,000+ providers
- Certification process: 6-12 months, worth it for distribution

### Phase 4: Digital Health Partnerships (Year 2+)
- White-label AuthAgent to digital health companies with PA-heavy drugs/procedures
- GLP-1 telehealth companies (Ozempic/Wegovy PA is a nightmare — huge market right now)
- Specialty pharmacy PA support

---

## Competitive Advantage & Moats

### Short-Term (MVP - Year 1)
- **First mover** on fully agentic PA (not just workflow)
- **CMS FHIR API data** — new regulatory requirement gives us payer criteria data nobody has systematically used yet
- **Clinical reasoning quality** — not just form-filling, actual argument construction from patient history

### Medium-Term (Year 1-3)
- **Payer intelligence database** — proprietary data on what arguments win per payer per code per denial reason
- This data doesn't exist anywhere. We build it from every PA we process.
- After 10,000 PAs, our denial prediction model is better than any human

### Long-Term (Year 3+)
- **Network effects** — more practices → more payer data → better predictions → more practices
- **EHR integration depth** — Epic certification is a moat (6-12 months to replicate)
- **Appeals win rate** — becomes a published metric that sells itself

---

## Financial Projections

| Year | Customers | Avg MRR/Customer | ARR | Gross Margin |
|------|-----------|-----------------|-----|--------------|
| 1 | 25 | $1,200 | $360K | 70% |
| 2 | 120 | $1,800 | $2.6M | 75% |
| 3 | 400 | $2,200 | $10.6M | 78% |
| 4 | 900 | $2,800 | $30M | 80% |

**Path to profitability:** ~200 customers at average $1,800/month MRR

---

## The Team We Need

**Immediate (MVP):**
- 1 Full-stack engineer (Next.js + Node + Python)
- 1 Healthcare regulatory advisor (part-time/advisor equity)
- 1 Medical billing specialist (advisor equity or part-time)

**Post-seed:**
- CTO / Lead Engineer
- 1-2 Backend engineers (FHIR integration specialists)
- 1 Clinical AI specialist
- VP Sales / first sales hire (healthcare RCM background)
- Compliance officer (HIPAA, SOC 2)

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Epic builds this natively | Medium | High | 3-5 year lag; build distribution moat now |
| Optum acquires a competitor | Medium | Medium | Positions us for acquisition at higher price |
| HIPAA/compliance issue | Low | Very High | SOC 2 from day 1, legal counsel, BAAs |
| Payer API changes | Medium | Medium | Multi-clearinghouse approach, redundancy |
| Low adoption by practices | Medium | High | Start with design partners, prove ROI before scaling |
| Physician liability concerns | Medium | Medium | Human-in-loop option always available, clear disclaimers |

---

*Last updated: March 2026*

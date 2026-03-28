# AuthAgent — Demo Script

## The 5-Minute Investor Demo

**Setup:** Open http://localhost:3010 in demo mode. Have the dashboard visible.

---

### Opening Line (30 seconds)
> "Every day, 40 million Americans wait for insurance approval before they can get care. The average wait is 4 days. Doctors spend 13 hours a week on paperwork to get that approval. 80% of the time when insurance says no, they're wrong — and the doctor wins on appeal. We built the AI agent that does all of this automatically."

---

### Scene 1: The Dashboard (1 minute)

Point to stats:
- "Tri-State Orthopedics processes 120 prior authorizations a month. Before AuthAgent, that was 48 hours of staff time. Now it's 4 hours of review."
- "Their approval rate is up 12% because our AI knows what each payer actually wants to see."
- "They've recovered $47K in overturned denials this month alone."

---

### Scene 2: Create a New PA — Live (2 minutes)

Click "New PA Request"

> "Let's say a patient comes in, Dr. Johnson orders an MRI. Insurance requires prior authorization. Here's what used to happen: a billing staff member spends 24 minutes pulling together the chart, calling the payer, filling out a form. Here's what happens now."

**Step through:**
1. Select patient (demo: Patient #4471), select payer (United Healthcare), enter CPT code: 72148
2. Upload the pre-loaded PDF ("lumbar_notes_demo.pdf")
3. Hit "Analyze" → watch the loading animation
4. **Clinical Extract appears:**
   > "The AI just read this patient's chart. Lower back pain, 8 weeks duration, failed 6 weeks of PT, radiculopathy symptoms. These are exactly the facts United Healthcare needs to see."
5. Hit "Generate Justification" → letter appears
   > "In 12 seconds, it wrote a complete, clinically precise justification letter. Notice it specifically addresses United's criteria — the PT documentation, the symptom duration, the conservative treatment failure. A human billing staff member would take 20 minutes to write something less specific."
6. Show probability score: 87%
   > "87% approval probability. It knows United's patterns. If this were missing the PT records, it would drop to 41% and flag the risk."

---

### Scene 3: The Appeal (1 minute)

Click to the pre-built "Aetna — Denied" demo case.

> "This one was denied. Aetna used denial code CO-50 — not medically necessary. Standard boilerplate. Here's what happens next."

Click "Generate Appeal":
> "Aetna denied it in 3 days. AuthAgent generated this appeal in 8 seconds. It specifically cites the MCG clinical criteria Aetna uses, the peer-reviewed evidence, and the exact policy language in Aetna's 2026 coverage guidelines. This is the argument that wins this type of denial 73% of the time in our data."

> "The practice reviews it, hits submit, and the appeal is filed. Average overturn time with a generic appeal letter: 3 weeks. With this: 9 days."

---

### Closing (30 seconds)

> "We're processing 200 PAs a month in beta with two orthopedic practices. Approval rates up. Staff time down. The average practice pays us $900/month and saves $3,200 in labor. The unit economics are obvious."

> "We're raising a seed round to get into 50 practices and build the payer intelligence layer that becomes the defensible moat. Every PA we process makes the model smarter. Nobody else is building this on the provider side."

---

## Technical Demo (for engineering-savvy audience)

After the main demo, open the browser dev tools or show the API:

```bash
# Show the API directly
curl -X POST http://localhost:3011/api/pa/analyze \
  -H "Content-Type: application/json" \
  -d '{"cpt_code": "72148", "payer": "united", "clinical_text": "Patient presents with..."}'
```

Show the response JSON — clinical extract, justification letter, probability score.

> "The whole thing is an API. EHR vendors can embed this. Digital health companies can white-label it. We're building the PA infrastructure layer for the industry."

---

## Objection Handling

**"Epic will build this."**
> "Epic moves on a 5-7 year roadmap. Their 2026 roadmap mentions PA suggestions — not AI reasoning, not appeals. We'll have 2 years of payer intelligence data by the time they ship anything competitive. And Epic won't build something that antagonizes payers, who are also their customers."

**"Cohere Health is doing this."**
> "Cohere works for payers — United and Humana are their customers. They help payers approve faster. We help providers fight harder. Completely different product, completely different buyer."

**"Doctors won't trust AI for medical decisions."**
> "We're not making medical decisions. The doctor made the decision when they ordered the procedure. We're doing the paperwork — the bureaucratic translation of that clinical decision into the language insurance companies understand. Billing staff don't have medical degrees either."

**"HIPAA compliance is hard."**
> "We have BAAs with Anthropic and our cloud providers. We encrypt at rest and in transit. We're on the same compliance path as every EHR vendor. It's a standard process — we're not doing anything unusual."

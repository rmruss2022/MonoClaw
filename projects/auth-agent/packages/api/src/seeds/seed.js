require('dotenv').config({ path: '../../../../.env' });
const db = require('../db');

async function seed() {
  console.log('Seeding demo data...');

  try {
    // Clear existing data
    await db.query('DELETE FROM pa_appeals');
    await db.query('DELETE FROM uploaded_documents');
    await db.query('DELETE FROM pa_requests');
    await db.query('DELETE FROM payer_requirements');
    await db.query('DELETE FROM payers');
    await db.query('DELETE FROM practices');

    // --- Practices ---
    const practices = [
      { name: 'Tri-State Orthopedic Group', npi: '1234567890', specialty: 'Orthopedics' },
      { name: 'NYC Neurology Associates', npi: '0987654321', specialty: 'Neurology' },
    ];
    const practiceIds = [];
    for (const p of practices) {
      const { rows } = await db.query(
        'INSERT INTO practices (name, npi, specialty) VALUES ($1, $2, $3) RETURNING id',
        [p.name, p.npi, p.specialty]
      );
      practiceIds.push(rows[0].id);
    }
    console.log(`  Created ${practices.length} practices`);

    // --- Payers ---
    const payers = [
      { name: 'United Healthcare', payer_id: 'UHC001', covermymeds_id: 'uhc' },
      { name: 'Aetna', payer_id: 'AETNA001', covermymeds_id: 'aetna' },
      { name: 'Cigna', payer_id: 'CIGNA001', covermymeds_id: 'cigna' },
      { name: 'Humana', payer_id: 'HUMANA001', covermymeds_id: 'humana' },
      { name: 'BlueCross BlueShield', payer_id: 'BCBS001', covermymeds_id: 'bcbs' },
    ];
    const payerIds = [];
    for (const p of payers) {
      const { rows } = await db.query(
        'INSERT INTO payers (name, payer_id, covermymeds_id) VALUES ($1, $2, $3) RETURNING id',
        [p.name, p.payer_id, p.covermymeds_id]
      );
      payerIds.push(rows[0].id);
    }
    console.log(`  Created ${payers.length} payers`);

    // --- Payer Requirements (5 payers × 10 CPT codes = 50 rows) ---
    const cptCodes = ['72148', '27447', '70553', '63650', 'J0274', '95910', '97110', '90837', '78452', '95800'];
    const requirementsData = {
      '72148': {
        criteria: ['Failed conservative treatment (PT) x6 weeks', 'Documented radiculopathy or myelopathy', 'No prior MRI in last 6 months'],
        supporting_docs: ['office_notes', 'PT_records'],
        avg_approval_days: 3.2,
        denial_rates: [0.18, 0.22, 0.15, 0.12, 0.14],
      },
      '27447': {
        criteria: ['Failed conservative treatment x12 months', 'Kellgren-Lawrence Grade III or IV', 'BMI documented', 'PT records required'],
        supporting_docs: ['office_notes', 'imaging', 'PT_records'],
        avg_approval_days: 5.1,
        denial_rates: [0.20, 0.25, 0.18, 0.15, 0.16],
      },
      '70553': {
        criteria: ['Failed at least 2 preventive medications', 'Neurological symptoms documented', 'No prior brain MRI in 12 months'],
        supporting_docs: ['office_notes', 'medication_history'],
        avg_approval_days: 2.8,
        denial_rates: [0.12, 0.15, 0.10, 0.08, 0.11],
      },
      '63650': {
        criteria: ['Failed back surgery syndrome documented', 'Failed medication management', 'Psychological clearance obtained', 'SCS trial required before permanent implant'],
        supporting_docs: ['office_notes', 'surgical_records', 'psych_evaluation', 'PT_records'],
        avg_approval_days: 14.2,
        denial_rates: [0.35, 0.40, 0.32, 0.28, 0.30],
      },
      'J0274': {
        criteria: ['BMI >= 30 with weight-related comorbidity OR BMI >= 27 with type 2 diabetes', 'Failed structured diet/exercise program x6 months', 'Documentation of prior weight-loss medication trial', 'Endocrinology or obesity medicine referral'],
        supporting_docs: ['office_notes', 'medication_history', 'lab_results', 'BMI_trend'],
        avg_approval_days: 7.5,
        denial_rates: [0.52, 0.58, 0.48, 0.45, 0.50],
      },
      '95910': {
        criteria: ['Clinical symptoms of neuropathy documented', 'Failed empiric treatment or diagnostic uncertainty', 'Relevant neurological exam findings', 'Ordering provider is neurologist or qualified specialist'],
        supporting_docs: ['office_notes', 'neurology_referral', 'lab_results'],
        avg_approval_days: 3.8,
        denial_rates: [0.14, 0.18, 0.12, 0.10, 0.13],
      },
      '97110': {
        criteria: ['Post-surgical rehabilitation or documented functional deficit', 'Individualized treatment plan with measurable goals', 'Progress notes from prior sessions if continuation', 'Maximum 24 visits per authorization period'],
        supporting_docs: ['office_notes', 'PT_plan_of_care', 'surgical_records'],
        avg_approval_days: 2.1,
        denial_rates: [0.08, 0.12, 0.07, 0.06, 0.09],
      },
      '90837': {
        criteria: ['DSM-5 diagnosis documented', 'Treatment plan with specific goals and modalities', 'Failed lower-intensity intervention or clinical justification for 60-min sessions', 'Licensed mental health provider'],
        supporting_docs: ['office_notes', 'treatment_plan', 'medication_history'],
        avg_approval_days: 4.2,
        denial_rates: [0.16, 0.20, 0.14, 0.11, 0.15],
      },
      '78452': {
        criteria: ['Intermediate or high pre-test probability of CAD', 'Abnormal or inconclusive stress ECG, or unable to exercise', 'No prior myocardial perfusion study in 12 months', 'Cardiology referral or primary care with documented risk factors'],
        supporting_docs: ['office_notes', 'ECG_results', 'cardiac_risk_assessment'],
        avg_approval_days: 3.5,
        denial_rates: [0.10, 0.14, 0.09, 0.07, 0.11],
      },
      '95800': {
        criteria: ['Epworth Sleepiness Scale score >= 10 or clinical suspicion of OSA', 'BMI >= 30 or documented craniofacial abnormality', 'No prior sleep study in 12 months', 'Symptoms present >= 3 months'],
        supporting_docs: ['office_notes', 'sleep_questionnaire', 'BMI_documentation'],
        avg_approval_days: 2.5,
        denial_rates: [0.06, 0.10, 0.05, 0.04, 0.07],
      },
    };

    let reqCount = 0;
    for (let pi = 0; pi < payerIds.length; pi++) {
      for (const cpt of cptCodes) {
        const data = requirementsData[cpt];
        await db.query(
          `INSERT INTO payer_requirements (payer_id, cpt_code, requires_pa, criteria, supporting_docs, avg_approval_days, denial_rate_estimate)
           VALUES ($1, $2, true, $3, $4, $5, $6)`,
          [payerIds[pi], cpt, JSON.stringify(data.criteria), data.supporting_docs, data.avg_approval_days, data.denial_rates[pi]]
        );
        reqCount++;
      }
    }
    console.log(`  Created ${reqCount} payer requirements`);

    // --- Clinical extract data for key demo scenarios ---
    const clinicalExtracts = {
      'PAT-001': {
        primary_diagnosis: 'Lumbar radiculopathy',
        icd10_codes: ['M54.5', 'M51.16'],
        symptoms: ['lower back pain', 'left leg numbness', 'radiating pain'],
        duration_weeks: 8,
        severity: 'moderate-severe',
        prior_treatments: [
          { treatment: 'Physical therapy', duration: '6 weeks', outcome: 'Minimal improvement' },
          { treatment: 'NSAIDs (ibuprofen 800mg)', duration: '8 weeks', outcome: 'Partial pain control' },
          { treatment: 'Muscle relaxants', duration: '4 weeks', outcome: 'No significant benefit' },
        ],
        medications: ['Ibuprofen 800mg TID', 'Cyclobenzaprine 10mg QHS'],
        physical_exam: 'Positive straight leg raise L, decreased L4-L5 sensation',
        provider_assessment: 'MRI indicated to evaluate for disc herniation vs spinal stenosis',
        requested_procedure: 'MRI Lumbar Spine without contrast',
        cpt_code: '72148',
      },
      'PAT-002': {
        primary_diagnosis: 'Primary osteoarthritis, right knee',
        icd10_codes: ['M17.11'],
        symptoms: ['knee pain', 'stiffness', 'inability to walk >1 block'],
        duration_weeks: 78,
        severity: 'severe',
        prior_treatments: [
          { treatment: 'Physical therapy', duration: '12 weeks', outcome: 'Minimal improvement' },
          { treatment: 'Corticosteroid injection', duration: '3 injections', outcome: 'Temporary relief, 2-3 weeks each' },
          { treatment: 'NSAIDs', duration: '18 months', outcome: 'Inadequate pain control' },
        ],
        medications: ['Meloxicam 15mg daily', 'Acetaminophen 1000mg TID'],
        imaging_results: 'X-ray: Kellgren-Lawrence Grade IV, bone-on-bone medial compartment',
        physical_exam: 'BMI 28.4, varus deformity 8 degrees, ROM 5-95 degrees',
        provider_assessment: 'End-stage OA, conservative measures exhausted, TKA indicated',
        requested_procedure: 'Total Knee Arthroplasty',
        cpt_code: '27447',
      },
      'PAT-004': {
        primary_diagnosis: 'Morbid obesity',
        icd10_codes: ['E66.01'],
        symptoms: ['weight gain', 'inability to lose weight', 'fatigue', 'joint pain'],
        duration_weeks: 156,
        severity: 'severe',
        prior_treatments: [
          { treatment: 'Supervised diet program', duration: '6 months', outcome: 'Lost 8 lbs, regained' },
          { treatment: 'Exercise program', duration: '12 months', outcome: 'Minimal weight change' },
          { treatment: 'Phentermine', duration: '3 months', outcome: 'Lost 12 lbs, regained after stopping' },
        ],
        medications: ['Metformin 500mg BID', 'Lisinopril 10mg daily'],
        physical_exam: 'BMI 42.1, BP 142/88, waist circumference 48 inches',
        provider_assessment: 'Semaglutide indicated for chronic weight management',
        requested_procedure: 'Semaglutide (Ozempic) injection',
        cpt_code: 'J0274',
      },
      'PAT-005': {
        primary_diagnosis: 'Failed back surgery syndrome',
        icd10_codes: ['M96.1', 'G89.4'],
        symptoms: ['chronic pain', 'radiculopathy', 'functional impairment'],
        duration_weeks: 104,
        severity: 'severe',
        prior_treatments: [
          { treatment: 'Lumbar fusion L4-L5', duration: 'Surgery 2024', outcome: 'Persistent pain' },
          { treatment: 'Physical therapy post-op', duration: '16 weeks', outcome: 'Limited improvement' },
          { treatment: 'Epidural steroid injections', duration: '3 sessions', outcome: 'Temporary relief' },
          { treatment: 'Gabapentin 1800mg/day', duration: '6 months', outcome: 'Partial pain control' },
        ],
        medications: ['Gabapentin 600mg TID', 'Duloxetine 60mg daily'],
        imaging_results: 'Post-surgical changes L4-L5, no hardware failure',
        physical_exam: 'Pain score 8/10, limited flexion, positive Waddell signs 1/5',
        psych_evaluation: 'Cleared for SCS trial — no contraindications',
        provider_assessment: 'SCS trial indicated given failed back surgery and exhausted conservative options',
        requested_procedure: 'Spinal Cord Stimulator implant',
        cpt_code: '63650',
      },
      'PAT-006': {
        primary_diagnosis: 'Migraine with aura',
        icd10_codes: ['G43.709'],
        symptoms: ['chronic headaches', 'visual aura', 'nausea', 'photophobia'],
        duration_weeks: 52,
        severity: 'moderate-severe',
        prior_treatments: [
          { treatment: 'Sumatriptan 100mg', duration: '6 months', outcome: 'Partial relief' },
          { treatment: 'Topiramate 100mg', duration: '4 months', outcome: 'Discontinued — cognitive side effects' },
          { treatment: 'Propranolol 80mg', duration: '3 months', outcome: 'Inadequate prevention' },
        ],
        medications: ['Sumatriptan 100mg PRN', 'Propranolol 80mg daily'],
        physical_exam: 'Neurological exam grossly normal, fundoscopic exam normal',
        provider_assessment: 'Brain MRI indicated to rule out secondary causes given refractory migraines with aura',
        requested_procedure: 'MRI Brain with and without contrast',
        cpt_code: '70553',
      },
    };

    // --- Helper to build status_history based on PA status and dates ---
    function buildStatusHistory(req, createdAt, submittedAt, decisionAt, payerName) {
      const history = [];
      const ts = (d) => d.toISOString();

      // All PAs start as draft
      history.push({ from: null, to: 'draft', actor: 'system', detail: 'PA request created', timestamp: ts(createdAt) });

      if (req.status === 'draft') return history;

      // Reviewed step (30 min after creation, before submission)
      const reviewedAt = new Date(createdAt.getTime() + 1000 * 60 * 15);
      history.push({ from: 'draft', to: 'reviewed', actor: 'staff', detail: 'Clinical notes reviewed and justification generated', timestamp: ts(reviewedAt) });

      // Submitted
      history.push({ from: 'reviewed', to: 'submitted', actor: 'staff', detail: `Submitted to ${payerName}`, timestamp: ts(submittedAt) });

      // Pending decision (a few hours after submission)
      const pendingAt = new Date(submittedAt.getTime() + 1000 * 60 * 60 * 2);
      const cmmRef = `CMM-DEMO-${req.patient.replace('PAT-', '')}`;
      history.push({ from: 'submitted', to: 'pending_decision', actor: 'system', detail: `CoverMyMeds ref: ${cmmRef}`, timestamp: ts(pendingAt) });

      if (req.status === 'submitted') return history;

      // Decision
      if (req.outcome === 'approved') {
        history.push({ from: 'pending_decision', to: 'approved', actor: 'system', detail: `Approved by ${payerName}`, timestamp: ts(decisionAt) });
      } else if (req.outcome === 'denied') {
        history.push({ from: 'pending_decision', to: 'denied', actor: 'system', detail: `Denied by ${payerName}: ${req.denial_code} — ${req.denial_text}`, timestamp: ts(decisionAt) });
      }

      // Appealed
      if (req.status === 'appealed') {
        const appealedAt = new Date(decisionAt.getTime() + 1000 * 60 * 60 * 24 * 3);
        history.push({ from: 'denied', to: 'appealed', actor: 'staff', detail: `First-level appeal submitted for ${req.denial_code}`, timestamp: ts(appealedAt) });
      }

      // Closed
      if (req.status === 'closed') {
        const closedAt = new Date(decisionAt.getTime() + 1000 * 60 * 60 * 24 * 2);
        history.push({ from: 'approved', to: 'closed', actor: 'system', detail: 'PA request closed — authorization period ended', timestamp: ts(closedAt) });
      }

      return history;
    }

    // --- PA Requests (20 demo cases) ---
    const statuses = ['draft', 'submitted', 'approved', 'denied', 'appealed', 'closed'];
    const demoRequests = [
      { patient: 'PAT-001', cpt: '72148', icd: ['M54.5', 'M51.16'], status: 'approved', outcome: 'approved', prob: 89, payer: 0, practice: 0, daysAgo: 25 },
      { patient: 'PAT-002', cpt: '27447', icd: ['M17.11'], status: 'denied', outcome: 'denied', prob: 62, payer: 1, practice: 0, daysAgo: 20, denial_code: 'CO-50', denial_text: 'Not medically necessary — insufficient PT documentation' },
      { patient: 'PAT-003', cpt: '95910', icd: ['G62.9', 'E11.42'], status: 'approved', outcome: 'approved', prob: 82, payer: 2, practice: 1, daysAgo: 18 },
      { patient: 'PAT-004', cpt: 'J0274', icd: ['E66.01'], status: 'denied', outcome: 'denied', prob: 45, payer: 0, practice: 0, daysAgo: 15, denial_code: 'CO-96', denial_text: 'Non-covered service for this indication' },
      { patient: 'PAT-005', cpt: '63650', icd: ['M96.1', 'G89.4'], status: 'submitted', outcome: null, prob: 58, payer: 2, practice: 1, daysAgo: 12 },
      { patient: 'PAT-006', cpt: '70553', icd: ['G43.709'], status: 'approved', outcome: 'approved', prob: 85, payer: 3, practice: 1, daysAgo: 28 },
      { patient: 'PAT-007', cpt: '78452', icd: ['R07.9', 'I10'], status: 'approved', outcome: 'approved', prob: 88, payer: 4, practice: 0, daysAgo: 22 },
      { patient: 'PAT-008', cpt: '95800', icd: ['G47.30', 'R06.83'], status: 'approved', outcome: 'approved', prob: 91, payer: 0, practice: 0, daysAgo: 19 },
      { patient: 'PAT-009', cpt: '97110', icd: ['Z96.651', 'M25.661'], status: 'approved', outcome: 'approved', prob: 94, payer: 1, practice: 0, daysAgo: 8 },
      { patient: 'PAT-010', cpt: '90837', icd: ['F33.2'], status: 'submitted', outcome: null, prob: 78, payer: 2, practice: 1, daysAgo: 5 },
      { patient: 'PAT-011', cpt: '72148', icd: ['M54.5'], status: 'approved', outcome: 'approved', prob: 76, payer: 2, practice: 0, daysAgo: 27 },
      { patient: 'PAT-012', cpt: '27447', icd: ['M17.12'], status: 'appealed', outcome: 'denied', prob: 55, payer: 0, practice: 0, daysAgo: 24, denial_code: 'CO-197', denial_text: 'Precertification/authorization/notification absent' },
      { patient: 'PAT-013', cpt: '72148', icd: ['M54.5', 'M47.816'], status: 'draft', outcome: null, prob: 72, payer: 3, practice: 1, daysAgo: 3 },
      { patient: 'PAT-014', cpt: '64483', icd: ['M54.16'], status: 'approved', outcome: 'approved', prob: 80, payer: 4, practice: 0, daysAgo: 26 },
      { patient: 'PAT-015', cpt: '43239', icd: ['K21.0'], status: 'approved', outcome: 'approved', prob: 90, payer: 1, practice: 1, daysAgo: 21 },
      { patient: 'PAT-016', cpt: '27130', icd: ['M16.11'], status: 'denied', outcome: 'denied', prob: 60, payer: 0, practice: 0, daysAgo: 17, denial_code: 'CO-4', denial_text: 'The procedure code is inconsistent with the modifier used' },
      { patient: 'PAT-017', cpt: '72141', icd: ['M50.12'], status: 'approved', outcome: 'approved', prob: 83, payer: 3, practice: 1, daysAgo: 14 },
      { patient: 'PAT-018', cpt: '63650', icd: ['G89.4'], status: 'draft', outcome: null, prob: 52, payer: 1, practice: 0, daysAgo: 2 },
      { patient: 'PAT-019', cpt: '70553', icd: ['G43.909'], status: 'closed', outcome: 'approved', prob: 87, payer: 4, practice: 1, daysAgo: 30 },
      { patient: 'PAT-020', cpt: 'J0274', icd: ['E66.01', 'I10'], status: 'appealed', outcome: 'denied', prob: 48, payer: 2, practice: 0, daysAgo: 10, denial_code: 'CO-50', denial_text: 'Not medically necessary per payer policy' },
    ];

    const justificationTemplate = `PRIOR AUTHORIZATION JUSTIFICATION LETTER

This letter serves as a request for prior authorization for the procedure described below. Based on the clinical evidence documented in the patient's chart, the requested procedure meets medical necessity criteria as outlined by relevant clinical practice guidelines.

The patient has undergone conservative management which has been insufficient to address their clinical condition. The treating physician has determined that the requested procedure represents the most appropriate next step in the patient's care plan.

Supporting clinical documentation is attached for review.

Respectfully submitted,
[Treating Physician]`;

    for (const req of demoRequests) {
      const createdAt = new Date();
      createdAt.setDate(createdAt.getDate() - req.daysAgo);

      const submittedAt = req.status !== 'draft' ? new Date(createdAt.getTime() + 1000 * 60 * 30) : null;
      const decisionAt = req.outcome ? new Date(createdAt.getTime() + 1000 * 60 * 60 * 24 * (Math.random() * 5 + 1)) : null;

      const payerName = payers[req.payer].name;
      const clinicalExtract = clinicalExtracts[req.patient] || null;
      const statusHistory = buildStatusHistory(req, createdAt, submittedAt, decisionAt, payerName);

      // PHI: treat as sensitive
      const { rows } = await db.query(
        `INSERT INTO pa_requests
         (practice_id, payer_id, patient_id, cpt_code, icd10_codes, status, approval_probability,
          probability_factors, justification_draft, justification_final,
          submitted_at, decision_at, outcome, denial_reason_code, denial_reason_text,
          clinical_extract, status_history, created_at, updated_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
         RETURNING id`,
        [
          practiceIds[req.practice],
          payerIds[req.payer],
          req.patient,
          req.cpt,
          req.icd,
          req.status,
          req.prob,
          JSON.stringify([{ factor: 'Demo data', impact: 'neutral', detail: 'Pre-seeded probability score' }]),
          justificationTemplate,
          req.status !== 'draft' ? justificationTemplate : null,
          submittedAt,
          decisionAt,
          req.outcome,
          req.denial_code || null,
          req.denial_text || null,
          clinicalExtract ? JSON.stringify(clinicalExtract) : null,
          JSON.stringify(statusHistory),
          createdAt,
          createdAt,
        ]
      );

      // Add appeals for appealed requests (with deadline and denial analysis for demo)
      if (req.status === 'appealed') {
        const deadlineDate = decisionAt ? new Date(decisionAt.getTime() + 1000 * 60 * 60 * 24 * 30) : null;
        const denialReasonCode = req.denial_code || null;
        const carcStrategy = req.patient === 'PAT-012'
          ? JSON.stringify({
              carc: 'CO-197',
              rarc: 'N479',
              strategy: 'Submit retroactive authorization with clinical documentation proving medical necessity was established prior to service date',
              success_rate: 0.68,
              recommended_actions: [
                'Obtain signed attestation from ordering physician with date of medical necessity determination',
                'Include all clinical notes from the 30-day window prior to service',
                'Reference payer policy section on retroactive auth exceptions',
              ],
            })
          : JSON.stringify({
              carc: 'CO-50',
              rarc: 'N386',
              strategy: 'Submit peer-to-peer review request with updated clinical evidence demonstrating medical necessity per payer policy criteria',
              success_rate: 0.42,
              recommended_actions: [
                'Request peer-to-peer review with payer medical director',
                'Submit additional documentation: BMI trend, comorbidity list, failed medication log',
                'Reference FDA-approved indications and clinical guidelines (AGA/Endocrine Society)',
              ],
            });
        await db.query(
          `INSERT INTO pa_appeals (pa_request_id, appeal_draft, appeal_type, submitted_at, deadline_date, denial_reason_code, carc_strategy)
           VALUES ($1, $2, 'first_level', $3, $4, $5, $6)`,
          [
            rows[0].id,
            `Appeal for ${req.patient}: Requesting reconsideration of denial (${req.denial_code}).`,
            submittedAt,
            deadlineDate,
            denialReasonCode,
            carcStrategy,
          ]
        );
      }
    }
    console.log(`  Created ${demoRequests.length} PA requests`);

    console.log('Seed complete!');
  } catch (err) {
    console.error('Seed failed:', err);
    process.exit(1);
  } finally {
    await db.pool.end();
  }
}

seed();

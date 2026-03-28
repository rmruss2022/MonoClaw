const express = require('express');
const router = express.Router();
const db = require('../db');
const { extractClinical } = require('../agents/extractClinical');
const { buildJustification } = require('../agents/buildJustification');
const { scoreProbability } = require('../agents/scoreProbability');
const { canTransition, appendStatusEvent } = require('../services/statusMachine');
const { notifyStatusChange } = require('../services/notifications');
const { getClient } = require('../fhir/coverMyMeds');
const { draftAppeal, getCarcStrategy, carcStrategies } = require('../agents/draftAppeal');

// List all PA requests
router.get('/list', async (req, res) => {
  try {
    const { rows } = await db.query(`
      SELECT pr.*, p.name as payer_name, prac.name as practice_name
      FROM pa_requests pr
      LEFT JOIN payers p ON pr.payer_id = p.id
      LEFT JOIN practices prac ON pr.practice_id = prac.id
      ORDER BY pr.created_at DESC
      LIMIT 50
    `);
    res.json(rows);
  } catch (err) {
    console.error('Error listing PAs:', err);
    res.status(500).json({ error: 'Failed to fetch PA requests' });
  }
});

// Get single PA request
router.get('/:id', async (req, res) => {
  try {
    const { rows } = await db.query(`
      SELECT pr.*, p.name as payer_name, prac.name as practice_name
      FROM pa_requests pr
      LEFT JOIN payers p ON pr.payer_id = p.id
      LEFT JOIN practices prac ON pr.practice_id = prac.id
      WHERE pr.id = $1
    `, [req.params.id]);

    if (rows.length === 0) {
      return res.status(404).json({ error: 'PA request not found' });
    }
    res.json(rows[0]);
  } catch (err) {
    console.error('Error fetching PA:', err);
    res.status(500).json({ error: 'Failed to fetch PA request' });
  }
});

// Create new PA request
router.post('/create', async (req, res) => {
  try {
    const { practice_id, payer_id, patient_id, cpt_code, icd10_codes } = req.body;

    const initialHistory = [{
      from: null,
      to: 'draft',
      actor: 'system',
      detail: 'PA request created',
      timestamp: new Date().toISOString(),
    }];

    const { rows } = await db.query(`
      INSERT INTO pa_requests (practice_id, payer_id, patient_id, cpt_code, icd10_codes, status_history)
      VALUES ($1, $2, $3, $4, $5, $6)
      RETURNING *
    `, [practice_id, payer_id, patient_id, cpt_code, icd10_codes || [], JSON.stringify(initialHistory)]);

    res.status(201).json(rows[0]);
  } catch (err) {
    console.error('Error creating PA:', err);
    res.status(500).json({ error: 'Failed to create PA request' });
  }
});

// ─── Submit PA to payer (human approval required) ───────────────────────────

router.post('/:id/submit', async (req, res) => {
  try {
    const { justification_final, actor } = req.body;

    // Fetch PA with payer info
    const { rows: paRows } = await db.query(`
      SELECT pr.*, p.name as payer_name, p.covermymeds_id
      FROM pa_requests pr
      LEFT JOIN payers p ON pr.payer_id = p.id
      WHERE pr.id = $1
    `, [req.params.id]);

    if (paRows.length === 0) {
      return res.status(404).json({ error: 'PA request not found' });
    }

    const pa = paRows[0];

    // Validate status transition: must be reviewed (or draft for backwards compat)
    if (!['reviewed', 'draft'].includes(pa.status)) {
      return res.status(400).json({
        error: `Cannot submit PA in status '${pa.status}'. Must be 'reviewed' or 'draft'.`,
      });
    }

    // First transition to reviewed if currently draft
    let currentStatus = pa.status;
    let history = Array.isArray(pa.status_history) ? pa.status_history : [];

    if (currentStatus === 'draft') {
      history = appendStatusEvent(history, 'draft', 'reviewed', actor || 'staff', 'Human reviewed and approved for submission');
      currentStatus = 'reviewed';
    }

    // Submit to CoverMyMeds
    const cmm = getClient();
    const submission = await cmm.submitPA({
      payer_id: pa.covermymeds_id || pa.payer_id,
      cpt_code: pa.cpt_code,
      icd10_codes: pa.icd10_codes,
      patient: { id: pa.patient_id },
      clinical_info: pa.justification_final || justification_final || pa.justification_draft,
    });

    // Transition: reviewed → submitted
    history = appendStatusEvent(history, 'reviewed', 'submitted', actor || 'staff', `Submitted to ${pa.payer_name} via CoverMyMeds`);

    // Immediately transition to pending_decision (CoverMyMeds accepted it)
    history = appendStatusEvent(history, 'submitted', 'pending_decision', 'system', `CoverMyMeds ref: ${submission.paId}`);

    const { rows } = await db.query(`
      UPDATE pa_requests
      SET status = 'pending_decision',
          justification_final = COALESCE($1, justification_final, justification_draft),
          covermymeds_pa_id = $2,
          submitted_at = NOW(),
          estimated_decision_date = $3,
          status_history = $4,
          updated_at = NOW()
      WHERE id = $5
      RETURNING *
    `, [
      justification_final,
      submission.paId,
      submission.estimatedDecisionDate,
      JSON.stringify(history),
      req.params.id,
    ]);

    const updatedPA = rows[0];
    updatedPA.payer_name = pa.payer_name;

    notifyStatusChange(updatedPA, 'reviewed', 'submitted');

    console.log(`[Submit] PA ${req.params.id} submitted → CMM ref: ${submission.paId}`);

    res.json({
      pa: updatedPA,
      submission: {
        paId: submission.paId,
        estimatedDecisionDate: submission.estimatedDecisionDate,
      },
    });
  } catch (err) {
    console.error('Error submitting PA:', err);
    res.status(500).json({ error: 'Failed to submit PA request' });
  }
});

// ─── Check PA status ────────────────────────────────────────────────────────

router.get('/:id/status', async (req, res) => {
  try {
    const { rows } = await db.query(`
      SELECT pr.*, p.name as payer_name
      FROM pa_requests pr
      LEFT JOIN payers p ON pr.payer_id = p.id
      WHERE pr.id = $1
    `, [req.params.id]);

    if (rows.length === 0) {
      return res.status(404).json({ error: 'PA request not found' });
    }

    const pa = rows[0];

    // Calculate days pending for submitted PAs
    let daysPending = null;
    if (pa.submitted_at && ['submitted', 'pending_decision'].includes(pa.status)) {
      daysPending = Math.floor((Date.now() - new Date(pa.submitted_at).getTime()) / 86400000);
    }

    res.json({
      id: pa.id,
      status: pa.status,
      covermymeds_pa_id: pa.covermymeds_pa_id,
      submitted_at: pa.submitted_at,
      estimated_decision_date: pa.estimated_decision_date,
      decision_at: pa.decision_at,
      outcome: pa.outcome,
      denial_reason_code: pa.denial_reason_code,
      denial_reason_text: pa.denial_reason_text,
      days_pending: daysPending,
      status_history: pa.status_history || [],
    });
  } catch (err) {
    console.error('Error fetching PA status:', err);
    res.status(500).json({ error: 'Failed to fetch PA status' });
  }
});

// ─── Manually refresh PA status from CoverMyMeds ───────────────────────────

router.post('/:id/refresh', async (req, res) => {
  try {
    const { rows: paRows } = await db.query(`
      SELECT pr.*, p.name as payer_name
      FROM pa_requests pr
      LEFT JOIN payers p ON pr.payer_id = p.id
      WHERE pr.id = $1
    `, [req.params.id]);

    if (paRows.length === 0) {
      return res.status(404).json({ error: 'PA request not found' });
    }

    const pa = paRows[0];

    if (!pa.covermymeds_pa_id) {
      return res.status(400).json({ error: 'PA has not been submitted yet — no CoverMyMeds reference ID' });
    }

    if (['approved', 'denied', 'closed'].includes(pa.status)) {
      return res.json({ pa, changed: false, message: 'PA already has a final status' });
    }

    // Poll CoverMyMeds for current status
    const cmm = getClient();
    const cmmStatus = await cmm.getStatus(pa.covermymeds_pa_id);

    // Map CoverMyMeds status to our status
    const statusMap = {
      pending_decision: 'pending_decision',
      pending_review: 'pending_decision',
      in_review: 'pending_decision',
      additional_info_needed: 'pending_decision',
      approved: 'approved',
      denied: 'denied',
    };

    const newStatus = statusMap[cmmStatus.status] || pa.status;

    if (newStatus === pa.status) {
      return res.json({ pa, changed: false, cmmStatus });
    }

    // Status changed — update DB
    let history = Array.isArray(pa.status_history) ? pa.status_history : [];
    history = appendStatusEvent(history, pa.status, newStatus, 'system', `Payer decision received via CoverMyMeds`);

    const updateFields = {
      status: newStatus,
      status_history: JSON.stringify(history),
      updated_at: 'NOW()',
    };

    if (newStatus === 'approved' || newStatus === 'denied') {
      updateFields.outcome = newStatus;
      updateFields.decision_at = cmmStatus.decisionDate || new Date().toISOString();
    }

    if (newStatus === 'denied' && cmmStatus.denialReasonCode) {
      updateFields.denial_reason_code = cmmStatus.denialReasonCode;
      updateFields.denial_reason_text = cmmStatus.denialReasonText;
    }

    const { rows } = await db.query(`
      UPDATE pa_requests
      SET status = $1,
          outcome = COALESCE($2, outcome),
          decision_at = COALESCE($3, decision_at),
          denial_reason_code = COALESCE($4, denial_reason_code),
          denial_reason_text = COALESCE($5, denial_reason_text),
          status_history = $6,
          updated_at = NOW()
      WHERE id = $7
      RETURNING *
    `, [
      newStatus,
      updateFields.outcome || null,
      updateFields.decision_at !== 'NOW()' ? updateFields.decision_at : null,
      updateFields.denial_reason_code || null,
      updateFields.denial_reason_text || null,
      JSON.stringify(history),
      req.params.id,
    ]);

    const updatedPA = rows[0];
    updatedPA.payer_name = pa.payer_name;

    notifyStatusChange(updatedPA, pa.status, newStatus, cmmStatus.denialReasonText || '');

    res.json({ pa: updatedPA, changed: true, previousStatus: pa.status, newStatus, cmmStatus });
  } catch (err) {
    console.error('Error refreshing PA status:', err);
    res.status(500).json({ error: 'Failed to refresh PA status' });
  }
});

// ─── Score probability ──────────────────────────────────────────────────────

router.post('/:id/score', async (req, res) => {
  try {
    const { rows: paRows } = await db.query(`
      SELECT pr.*, p.name as payer_name
      FROM pa_requests pr
      LEFT JOIN payers p ON pr.payer_id = p.id
      WHERE pr.id = $1
    `, [req.params.id]);

    if (paRows.length === 0) {
      return res.status(404).json({ error: 'PA request not found' });
    }

    const pa = paRows[0];
    const clinicalExtract = pa.clinical_extract || req.body.clinical_extract;

    if (!clinicalExtract) {
      return res.status(400).json({ error: 'No clinical extract available. Run analysis first.' });
    }

    let payerRequirements = null;
    const payerService = tryRequirePayerService();
    if (payerService && pa.payer_id && pa.cpt_code) {
      try {
        payerRequirements = await payerService.getRequirements(pa.payer_id, pa.cpt_code);
      } catch (e) {
        console.log('[Score] payerService lookup failed, trying DB:', e.message);
      }
    }
    if (!payerRequirements && pa.payer_id && pa.cpt_code) {
      const { rows } = await db.query(
        'SELECT * FROM payer_requirements WHERE payer_id = $1 AND cpt_code = $2',
        [pa.payer_id, pa.cpt_code]
      );
      payerRequirements = rows[0] || null;
    }

    const probability = scoreProbability(clinicalExtract, payerRequirements, pa.payer_name);

    await db.query(
      `UPDATE pa_requests SET approval_probability = $1, probability_factors = $2, updated_at = NOW() WHERE id = $3`,
      [probability.probability, JSON.stringify(probability.factors), req.params.id]
    );

    res.json(probability);
  } catch (err) {
    console.error('Error scoring PA:', err);
    res.status(500).json({ error: 'Failed to score PA probability' });
  }
});

// ─── Upload document ────────────────────────────────────────────────────────

router.post('/:id/upload', (req, res, next) => {
  const upload = req.app.locals.upload;
  upload.single('document')(req, res, next);
}, async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No file uploaded' });
    }

    let extractedText = '';

    if (req.file.mimetype === 'application/pdf') {
      const pdfParse = require('pdf-parse');
      const fs = require('fs');
      const buffer = fs.readFileSync(req.file.path);
      const data = await pdfParse(buffer);
      extractedText = data.text;
    } else {
      const fs = require('fs');
      extractedText = fs.readFileSync(req.file.path, 'utf8');
    }

    await db.query(`
      INSERT INTO uploaded_documents (pa_request_id, doc_type, filename, filepath, extracted_text)
      VALUES ($1, $2, $3, $4, $5)
    `, [req.params.id, req.body.doc_type || 'office_notes', req.file.originalname, req.file.path, extractedText]);

    res.json({ text: extractedText, filename: req.file.originalname });
  } catch (err) {
    console.error('Error uploading document:', err);
    res.status(500).json({ error: 'Failed to process uploaded document' });
  }
});

// ─── Analyze clinical notes ─────────────────────────────────────────────────

router.post('/analyze', async (req, res) => {
  try {
    const { clinical_text, pa_id } = req.body;

    if (!clinical_text) {
      return res.status(400).json({ error: 'clinical_text is required' });
    }

    const startTime = Date.now();
    console.log('[AI] Starting clinical extraction...');

    const clinicalFacts = await extractClinical(clinical_text);

    const elapsed = Date.now() - startTime;
    console.log(`[AI] Clinical extraction completed in ${elapsed}ms`);

    if (pa_id) {
      await db.query(
        'UPDATE pa_requests SET clinical_extract = $1, updated_at = NOW() WHERE id = $2',
        [JSON.stringify(clinicalFacts), pa_id]
      );
    }

    res.json({ clinical_extract: clinicalFacts, processing_time_ms: elapsed });
  } catch (err) {
    console.error('Error analyzing clinical notes:', err);
    res.status(500).json({ error: 'Failed to analyze clinical notes' });
  }
});

// ─── Draft justification ────────────────────────────────────────────────────

router.post('/draft', async (req, res) => {
  try {
    const { clinical_extract, payer_id, cpt_code, pa_id } = req.body;

    if (!clinical_extract) {
      return res.status(400).json({ error: 'clinical_extract is required' });
    }

    let payerRequirements = null;
    const payerService = tryRequirePayerService();
    if (payerService && payer_id && cpt_code) {
      try {
        payerRequirements = await payerService.getRequirements(payer_id, cpt_code);
      } catch (e) {
        console.log('[Draft] payerService lookup failed, trying DB:', e.message);
      }
    }
    if (!payerRequirements && payer_id && cpt_code) {
      const { rows } = await db.query(
        'SELECT * FROM payer_requirements WHERE payer_id = $1 AND cpt_code = $2',
        [payer_id, cpt_code]
      );
      payerRequirements = rows[0] || null;
    }

    let payerName = 'Unknown Payer';
    if (payer_id) {
      const { rows } = await db.query('SELECT name FROM payers WHERE id = $1', [payer_id]);
      if (rows[0]) payerName = rows[0].name;
    }

    const startTime = Date.now();
    console.log('[AI] Starting justification draft...');

    const result = await buildJustification(clinical_extract, payerRequirements, payerName, cpt_code);

    const elapsed = Date.now() - startTime;
    console.log(`[AI] Justification draft completed in ${elapsed}ms`);

    const probability = scoreProbability(clinical_extract, payerRequirements, payerName);

    if (pa_id) {
      await db.query(
        `UPDATE pa_requests
         SET justification_draft = $1, approval_probability = $2, probability_factors = $3, updated_at = NOW()
         WHERE id = $4`,
        [result.letter, probability.probability, JSON.stringify(probability.factors), pa_id]
      );
    }

    res.json({
      justification: result.letter,
      gaps: result.gaps,
      quality_score: result.qualityScore,
      probability,
      processing_time_ms: elapsed,
    });
  } catch (err) {
    console.error('Error drafting justification:', err);
    res.status(500).json({ error: 'Failed to draft justification' });
  }
});

// ─── Generate justification for existing PA ─────────────────────────────────

router.post('/:id/generate-justification', async (req, res) => {
  try {
    const { rows: paRows } = await db.query(`
      SELECT pr.*, p.name as payer_name
      FROM pa_requests pr
      LEFT JOIN payers p ON pr.payer_id = p.id
      WHERE pr.id = $1
    `, [req.params.id]);

    if (paRows.length === 0) {
      return res.status(404).json({ error: 'PA request not found' });
    }

    const pa = paRows[0];
    const clinicalExtract = pa.clinical_extract;

    if (!clinicalExtract) {
      return res.status(400).json({ error: 'PA request has no clinical extract. Run analysis first.' });
    }

    let payerRequirements = null;
    const payerService = tryRequirePayerService();
    if (payerService && pa.payer_id && pa.cpt_code) {
      try {
        payerRequirements = await payerService.getRequirements(pa.payer_id, pa.cpt_code);
      } catch (e) {
        console.log('[Generate] payerService lookup failed, trying DB:', e.message);
      }
    }
    if (!payerRequirements && pa.payer_id && pa.cpt_code) {
      const { rows } = await db.query(
        'SELECT * FROM payer_requirements WHERE payer_id = $1 AND cpt_code = $2',
        [pa.payer_id, pa.cpt_code]
      );
      payerRequirements = rows[0] || null;
    }

    const payerName = pa.payer_name || 'Unknown Payer';

    const startTime = Date.now();
    console.log(`[AI] Generating justification for PA ${req.params.id}...`);

    const result = await buildJustification(clinicalExtract, payerRequirements, payerName, pa.cpt_code);
    const probability = scoreProbability(clinicalExtract, payerRequirements, payerName);

    const elapsed = Date.now() - startTime;

    await db.query(
      `UPDATE pa_requests
       SET justification_draft = $1, approval_probability = $2, probability_factors = $3, updated_at = NOW()
       WHERE id = $4`,
      [result.letter, probability.probability, JSON.stringify(probability.factors), req.params.id]
    );

    res.json({
      justification: result.letter,
      gaps: result.gaps,
      quality_score: result.qualityScore,
      probability,
      processing_time_ms: elapsed,
    });
  } catch (err) {
    console.error('Error generating justification:', err);
    res.status(500).json({ error: 'Failed to generate justification' });
  }
});

// ─── Save edited justification ──────────────────────────────────────────────

router.post('/:id/save-justification', async (req, res) => {
  try {
    const { justification_final } = req.body;

    if (!justification_final) {
      return res.status(400).json({ error: 'justification_final is required' });
    }

    const { rows: paRows } = await db.query(
      'SELECT justification_draft FROM pa_requests WHERE id = $1',
      [req.params.id]
    );

    if (paRows.length === 0) {
      return res.status(404).json({ error: 'PA request not found' });
    }

    const original = paRows[0].justification_draft || '';
    const editPercentage = calculateEditPercentage(original, justification_final);

    const { rows } = await db.query(
      `UPDATE pa_requests
       SET justification_final = $1, updated_at = NOW()
       WHERE id = $2
       RETURNING *`,
      [justification_final, req.params.id]
    );

    console.log(`[Edit] PA ${req.params.id} — edit percentage: ${editPercentage.toFixed(1)}%`);

    res.json({ pa: rows[0], edit_percentage: editPercentage });
  } catch (err) {
    console.error('Error saving justification:', err);
    res.status(500).json({ error: 'Failed to save justification' });
  }
});

// ─── Generate appeal (AI-powered) ────────────────────────────────────────────

router.post('/:id/generate-appeal', async (req, res) => {
  try {
    const { rows: paRows } = await db.query(`
      SELECT pr.*, p.name as payer_name
      FROM pa_requests pr
      LEFT JOIN payers p ON pr.payer_id = p.id
      WHERE pr.id = $1
    `, [req.params.id]);

    if (paRows.length === 0) {
      return res.status(404).json({ error: 'PA request not found' });
    }

    const pa = paRows[0];
    if (pa.status !== 'denied' && pa.status !== 'appeal_draft') {
      return res.status(400).json({ error: `Can only appeal denied PA requests. Current status: ${pa.status}` });
    }

    const denialReasonCode = pa.denial_reason_code;
    const denialReasonText = pa.denial_reason_text;
    const payerName = pa.payer_name || 'Unknown Payer';

    const startTime = Date.now();
    console.log(`[Appeal] Generating appeal for PA ${req.params.id} (${denialReasonCode})...`);

    const result = await draftAppeal({
      originalPA: pa,
      denialReasonCode,
      denialReasonText,
      payerName,
    });

    const elapsed = Date.now() - startTime;
    console.log(`[Appeal] Appeal draft completed in ${elapsed}ms`);

    // Transition to appeal_draft
    let history = Array.isArray(pa.status_history) ? pa.status_history : [];
    if (pa.status === 'denied') {
      history = appendStatusEvent(history, 'denied', 'appeal_draft', 'staff',
        `Appeal drafted for denial (${denialReasonCode || 'N/A'}) — ${result.carcStrategy ? result.carcStrategy.success_rate_estimate + '% historical overturn rate' : 'generating counter-arguments'}`);
    }

    // Insert or update appeal record
    const { rows: existingAppeals } = await db.query(
      'SELECT id FROM pa_appeals WHERE pa_request_id = $1 AND outcome IS NULL ORDER BY created_at DESC LIMIT 1',
      [req.params.id]
    );

    let appealRow;
    if (existingAppeals.length > 0) {
      const { rows } = await db.query(`
        UPDATE pa_appeals
        SET appeal_draft = $1, appeal_type = $2, deadline_date = $3, escalation_type = $4,
            denial_reason_code = $5, carc_strategy = $6
        WHERE id = $7
        RETURNING *
      `, [
        result.appealLetter, result.appealType, result.deadlineDate,
        result.appealType, denialReasonCode, JSON.stringify(result.carcStrategy),
        existingAppeals[0].id,
      ]);
      appealRow = rows[0];
    } else {
      const { rows } = await db.query(`
        INSERT INTO pa_appeals (pa_request_id, appeal_draft, appeal_type, deadline_date, escalation_type, denial_reason_code, carc_strategy)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING *
      `, [
        req.params.id, result.appealLetter, result.appealType, result.deadlineDate,
        result.appealType, denialReasonCode, JSON.stringify(result.carcStrategy),
      ]);
      appealRow = rows[0];
    }

    await db.query(
      `UPDATE pa_requests SET status = 'appeal_draft', status_history = $1, updated_at = NOW() WHERE id = $2`,
      [JSON.stringify(history), req.params.id]
    );

    res.json({
      appeal: appealRow,
      appeal_draft: result.appealLetter,
      appeal_type: result.appealType,
      escalation_recommended: result.escalationRecommended,
      deadline_date: result.deadlineDate,
      carc_strategy: result.carcStrategy,
      processing_time_ms: elapsed,
    });
  } catch (err) {
    console.error('Error generating appeal:', err);
    res.status(500).json({ error: 'Failed to generate appeal' });
  }
});

// Legacy alias
router.post('/:id/appeal', async (req, res) => {
  // Forward to the new endpoint
  req.url = `/${req.params.id}/generate-appeal`;
  router.handle(req, res);
});

// ─── Submit approved appeal ──────────────────────────────────────────────────

router.post('/:id/submit-appeal', async (req, res) => {
  try {
    const { appeal_final, actor } = req.body;

    const { rows: paRows } = await db.query(`
      SELECT pr.*, p.name as payer_name, p.covermymeds_id
      FROM pa_requests pr
      LEFT JOIN payers p ON pr.payer_id = p.id
      WHERE pr.id = $1
    `, [req.params.id]);

    if (paRows.length === 0) {
      return res.status(404).json({ error: 'PA request not found' });
    }

    const pa = paRows[0];
    if (pa.status !== 'appeal_draft') {
      return res.status(400).json({ error: `Cannot submit appeal — PA status is '${pa.status}', expected 'appeal_draft'` });
    }

    // Get the latest appeal
    const { rows: appealRows } = await db.query(
      'SELECT * FROM pa_appeals WHERE pa_request_id = $1 ORDER BY created_at DESC LIMIT 1',
      [req.params.id]
    );

    if (appealRows.length === 0) {
      return res.status(400).json({ error: 'No appeal draft found. Generate an appeal first.' });
    }

    const appeal = appealRows[0];
    const finalAppealText = appeal_final || appeal.appeal_draft;

    // Submit via CoverMyMeds (demo mode will simulate)
    const cmm = getClient();
    const submission = await cmm.submitPA({
      payer_id: pa.covermymeds_id || pa.payer_id,
      cpt_code: pa.cpt_code,
      icd10_codes: pa.icd10_codes,
      patient: { id: pa.patient_id },
      clinical_info: finalAppealText,
      is_appeal: true,
    });

    // Update appeal record
    await db.query(`
      UPDATE pa_appeals
      SET appeal_final = $1, submitted_at = NOW()
      WHERE id = $2
    `, [finalAppealText, appeal.id]);

    // Transition PA status
    let history = Array.isArray(pa.status_history) ? pa.status_history : [];
    history = appendStatusEvent(history, 'appeal_draft', 'appeal_submitted', actor || 'staff',
      `Appeal submitted to ${pa.payer_name} via CoverMyMeds`);

    await db.query(`
      UPDATE pa_requests
      SET status = 'appeal_submitted', covermymeds_pa_id = $1, status_history = $2, updated_at = NOW()
      WHERE id = $3
    `, [submission.paId, JSON.stringify(history), req.params.id]);

    notifyStatusChange({ ...pa, status: 'appeal_submitted' }, 'appeal_draft', 'appeal_submitted');

    console.log(`[Appeal] PA ${req.params.id} appeal submitted → CMM ref: ${submission.paId}`);

    res.json({
      success: true,
      appeal_id: appeal.id,
      covermymeds_pa_id: submission.paId,
    });
  } catch (err) {
    console.error('Error submitting appeal:', err);
    res.status(500).json({ error: 'Failed to submit appeal' });
  }
});

// ─── List appeals for a PA ───────────────────────────────────────────────────

router.get('/:id/appeals', async (req, res) => {
  try {
    const { rows } = await db.query(`
      SELECT a.*,
        CASE
          WHEN a.deadline_date IS NOT NULL AND a.outcome IS NULL
          THEN GREATEST(0, EXTRACT(DAY FROM (a.deadline_date - NOW()))::int)
          ELSE NULL
        END as days_remaining
      FROM pa_appeals a
      WHERE a.pa_request_id = $1
      ORDER BY a.created_at DESC
    `, [req.params.id]);

    res.json(rows);
  } catch (err) {
    console.error('Error fetching appeals:', err);
    res.status(500).json({ error: 'Failed to fetch appeals' });
  }
});

// ─── Update PA (for demo/admin) ─────────────────────────────────────────────

router.patch('/:id', async (req, res) => {
  try {
    const allowedFields = ['status', 'justification_final', 'outcome', 'denial_reason_code', 'denial_reason_text'];
    const updates = [];
    const values = [];
    let idx = 1;

    for (const field of allowedFields) {
      if (req.body[field] !== undefined) {
        updates.push(`${field} = $${idx}`);
        values.push(req.body[field]);
        idx++;
      }
    }

    if (updates.length === 0) {
      return res.status(400).json({ error: 'No valid fields to update' });
    }

    updates.push(`updated_at = NOW()`);
    values.push(req.params.id);

    const { rows } = await db.query(
      `UPDATE pa_requests SET ${updates.join(', ')} WHERE id = $${idx} RETURNING *`,
      values
    );

    if (rows.length === 0) {
      return res.status(404).json({ error: 'PA request not found' });
    }

    res.json(rows[0]);
  } catch (err) {
    console.error('Error updating PA:', err);
    res.status(500).json({ error: 'Failed to update PA request' });
  }
});

// ─── Export PA as printable HTML (browser print-to-PDF) ──────────────────────

router.get('/:id/export-pdf', async (req, res) => {
  try {
    const { rows } = await db.query(`
      SELECT pr.*, p.name as payer_name
      FROM pa_requests pr
      LEFT JOIN payers p ON pr.payer_id = p.id
      WHERE pr.id = $1
    `, [req.params.id]);

    if (rows.length === 0) {
      return res.status(404).json({ error: 'PA request not found' });
    }

    const pa = rows[0];
    const isAppeal = req.query.type === 'appeal';
    let letterContent = '';
    let letterTitle = '';

    if (isAppeal) {
      // Fetch the latest appeal letter
      const { rows: appealRows } = await db.query(
        'SELECT appeal_final, appeal_draft FROM pa_appeals WHERE pa_request_id = $1 ORDER BY created_at DESC LIMIT 1',
        [req.params.id]
      );
      letterContent = appealRows[0]?.appeal_final || appealRows[0]?.appeal_draft || 'No appeal letter available.';
      letterTitle = 'Appeal Letter';
    } else {
      letterContent = pa.justification_final || pa.justification_draft || 'No justification letter available.';
      letterTitle = 'Prior Authorization Justification Letter';
    }

    const payerName = pa.payer_name || 'Unknown Payer';
    const today = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

    // Escape HTML entities in the letter content
    const escapeHtml = (str) => str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\n/g, '<br>');

    const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${letterTitle} — PA ${pa.id}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'Times New Roman', Times, Georgia, serif;
      font-size: 12pt;
      line-height: 1.5;
      color: #1a1a1a;
      padding: 1in;
      max-width: 8.5in;
      margin: 0 auto;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 2em;
      border-bottom: 2px solid #333;
      padding-bottom: 1em;
    }
    .logo-placeholder {
      width: 180px;
      height: 60px;
      background: #e5e7eb;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #6b7280;
      font-family: Arial, sans-serif;
      font-size: 11px;
      border: 1px solid #d1d5db;
    }
    .header-info {
      text-align: right;
      font-size: 10pt;
      color: #555;
    }
    .meta {
      margin-bottom: 2em;
    }
    .meta table {
      border-collapse: collapse;
    }
    .meta td {
      padding: 2px 12px 2px 0;
      vertical-align: top;
    }
    .meta td:first-child {
      font-weight: bold;
      color: #555;
      white-space: nowrap;
    }
    .title {
      font-size: 16pt;
      font-weight: bold;
      text-align: center;
      margin: 1.5em 0 1em;
      text-transform: uppercase;
      letter-spacing: 1px;
    }
    .letter-body {
      text-align: justify;
      white-space: pre-wrap;
      word-wrap: break-word;
    }
    .footer {
      margin-top: 3em;
      padding-top: 1em;
      border-top: 1px solid #ccc;
      font-size: 9pt;
      color: #888;
      text-align: center;
    }
    @media print {
      body { padding: 0.5in; }
      .no-print { display: none; }
      @page {
        size: letter;
        margin: 0.75in;
      }
    }
  </style>
</head>
<body>
  <div class="header">
    <div class="logo-placeholder">Practice Logo</div>
    <div class="header-info">
      <div>${today}</div>
      <div>PA Reference: ${pa.id}</div>
    </div>
  </div>

  <div class="meta">
    <table>
      <tr><td>Patient ID:</td><td>${pa.patient_id || 'N/A'}</td></tr>
      <tr><td>Payer:</td><td>${escapeHtml(payerName)}</td></tr>
      <tr><td>CPT Code:</td><td>${pa.cpt_code || 'N/A'}</td></tr>
      <tr><td>Date:</td><td>${today}</td></tr>
      ${isAppeal ? '<tr><td>Type:</td><td>Appeal Letter</td></tr>' : ''}
    </table>
  </div>

  <div class="title">${letterTitle}</div>

  <div class="letter-body">${escapeHtml(letterContent)}</div>

  <div class="footer">
    Generated by AuthAgent &mdash; ${today}
  </div>

  <div class="no-print" style="text-align:center; margin-top:2em;">
    <button onclick="window.print()" style="padding:8px 24px; font-size:14px; cursor:pointer;">
      Print / Save as PDF
    </button>
  </div>
</body>
</html>`;

    res.setHeader('Content-Type', 'text/html');
    res.send(html);
  } catch (err) {
    console.error('Error exporting PA as PDF:', err);
    res.status(500).json({ error: 'Failed to export PA' });
  }
});

// --- Helpers ---

function calculateEditPercentage(original, final) {
  if (!original || !final) return 100;
  if (original === final) return 0;

  const origWords = original.split(/\s+/);
  const finalWords = final.split(/\s+/);

  const origSet = new Set(origWords);
  const finalSet = new Set(finalWords);

  let changed = 0;
  for (const word of finalWords) {
    if (!origSet.has(word)) changed++;
  }
  for (const word of origWords) {
    if (!finalSet.has(word)) changed++;
  }

  const totalWords = Math.max(origWords.length, finalWords.length, 1);
  return Math.min(100, (changed / (totalWords * 2)) * 100);
}

function tryRequirePayerService() {
  try {
    return require('../services/payerService');
  } catch {
    return null;
  }
}

module.exports = router;

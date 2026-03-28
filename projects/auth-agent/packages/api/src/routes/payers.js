const express = require('express');
const router = express.Router();
const db = require('../db');
const payerService = require('../services/payerService');

/**
 * GET /api/payers
 * List all payers with summary stats.
 */
router.get('/', async (req, res) => {
  try {
    const { rows } = await db.query('SELECT * FROM payers ORDER BY name');

    // Enrich with requirement counts from local DB
    const allReqs = await payerService.getAllRequirements();
    const payers = rows.map((payer) => {
      const reqs = allReqs.filter((r) => r.payer_id === payer.payer_id);
      return {
        ...payer,
        requirements_count: reqs.length,
        avg_denial_rate: reqs.length > 0
          ? reqs.reduce((sum, r) => sum + (r.denial_rate_estimate || 0), 0) / reqs.length
          : 0,
      };
    });

    res.json(payers);
  } catch (err) {
    console.error('Error fetching payers:', err);
    res.status(500).json({ error: 'Failed to fetch payers' });
  }
});

/**
 * GET /api/payers/requirements
 * Get all payer requirements (all payers, all CPT codes). Supports query filters.
 * Query params: ?payer_id=xxx&cpt_code=xxx&search=xxx
 */
router.get('/requirements', async (req, res) => {
  try {
    const { payer_id, cpt_code, search } = req.query;
    let results = await payerService.getAllRequirements();

    if (payer_id) {
      results = results.filter((r) => r.payer_id === payer_id);
    }
    if (cpt_code) {
      results = results.filter((r) => r.cpt_code === cpt_code);
    }
    if (search) {
      const s = search.toLowerCase();
      results = results.filter(
        (r) =>
          r.payer_name?.toLowerCase().includes(s) ||
          r.cpt_code?.includes(s) ||
          r.description?.toLowerCase().includes(s)
      );
    }

    res.json(results);
  } catch (err) {
    console.error('Error fetching requirements:', err);
    res.status(500).json({ error: 'Failed to fetch requirements' });
  }
});

/**
 * GET /api/payers/:id/requirements/:cptCode
 * Get specific payer requirements for a CPT code.
 */
router.get('/:id/requirements/:cptCode', async (req, res) => {
  try {
    const { id, cptCode } = req.params;

    // id could be UUID (postgres) or payer_id string (local)
    // Try to resolve to payer_id string first
    let payerId = id;
    try {
      const { rows } = await db.query('SELECT payer_id FROM payers WHERE id = $1', [id]);
      if (rows.length > 0) {
        payerId = rows[0].payer_id;
      }
    } catch (err) {
      // Not a UUID, use as-is
    }

    const result = await payerService.getRequirements(payerId, cptCode);

    if (!result) {
      return res.status(404).json({
        error: 'Requirements not found',
        payer_id: payerId,
        cpt_code: cptCode,
      });
    }

    res.json(result);
  } catch (err) {
    console.error('Error fetching payer requirements:', err);
    res.status(500).json({ error: 'Failed to fetch payer requirements' });
  }
});

/**
 * POST /api/payers/:id/requirements/:cptCode/check-gaps
 * Check which requirements are met vs missing given a clinical extract.
 * Body: { clinical_extract: { ... } }
 */
router.post('/:id/requirements/:cptCode/check-gaps', async (req, res) => {
  try {
    const { id, cptCode } = req.params;
    const { clinical_extract } = req.body;

    if (!clinical_extract) {
      return res.status(400).json({ error: 'clinical_extract is required' });
    }

    let payerId = id;
    try {
      const { rows } = await db.query('SELECT payer_id FROM payers WHERE id = $1', [id]);
      if (rows.length > 0) {
        payerId = rows[0].payer_id;
      }
    } catch (err) {
      // Not a UUID, use as-is
    }

    const requirements = await payerService.getRequirements(payerId, cptCode);

    if (!requirements) {
      return res.status(404).json({
        error: 'Requirements not found',
        payer_id: payerId,
        cpt_code: cptCode,
      });
    }

    const gaps = payerService.checkGaps(clinical_extract, requirements);

    res.json({
      payer_id: payerId,
      cpt_code: cptCode,
      requirements,
      gaps,
      summary: {
        total: requirements.criteria?.length || 0,
        met: gaps.met.length,
        missing: gaps.missing.length,
        uncertain: gaps.uncertain.length,
      },
    });
  } catch (err) {
    console.error('Error checking gaps:', err);
    res.status(500).json({ error: 'Failed to check gaps' });
  }
});

module.exports = router;

const express = require('express');
const router = express.Router();
const db = require('../db');

// Dashboard statistics
router.get('/stats', async (req, res) => {
  try {
    // Total PAs this month
    const totalResult = await db.query(`
      SELECT COUNT(*) as total
      FROM pa_requests
      WHERE created_at >= date_trunc('month', CURRENT_DATE)
    `);

    // Status breakdown
    const statusResult = await db.query(`
      SELECT status, COUNT(*) as count
      FROM pa_requests
      GROUP BY status
    `);

    // Approval rate
    const outcomeResult = await db.query(`
      SELECT
        COUNT(*) FILTER (WHERE outcome = 'approved') as approved,
        COUNT(*) FILTER (WHERE outcome = 'denied') as denied,
        COUNT(*) FILTER (WHERE outcome IS NOT NULL) as total_decided
      FROM pa_requests
    `);

    // Average processing time (submitted to decision)
    const avgTimeResult = await db.query(`
      SELECT AVG(EXTRACT(EPOCH FROM (decision_at - submitted_at)) / 86400) as avg_days
      FROM pa_requests
      WHERE submitted_at IS NOT NULL AND decision_at IS NOT NULL
    `);

    // Revenue recovered estimate ($530 avg per approved PA)
    const approvedCount = parseInt(outcomeResult.rows[0]?.approved || 0);
    const revenueRecovered = approvedCount * 530;

    const approvalRate = outcomeResult.rows[0]?.total_decided > 0
      ? (outcomeResult.rows[0].approved / outcomeResult.rows[0].total_decided * 100).toFixed(1)
      : 0;

    // By payer breakdown
    const payerResult = await db.query(`
      SELECT p.name as payer_name,
             COUNT(*) as total,
             COUNT(*) FILTER (WHERE pr.outcome = 'approved') as approved,
             COUNT(*) FILTER (WHERE pr.outcome = 'denied') as denied
      FROM pa_requests pr
      JOIN payers p ON pr.payer_id = p.id
      GROUP BY p.name
      ORDER BY total DESC
    `);

    // By CPT code breakdown
    const cptResult = await db.query(`
      SELECT cpt_code,
             COUNT(*) as total,
             COUNT(*) FILTER (WHERE outcome = 'approved') as approved,
             COUNT(*) FILTER (WHERE outcome = 'denied') as denied
      FROM pa_requests
      GROUP BY cpt_code
      ORDER BY total DESC
      LIMIT 10
    `);

    res.json({
      total_this_month: parseInt(totalResult.rows[0]?.total || 0),
      approval_rate: parseFloat(approvalRate),
      avg_processing_days: parseFloat(avgTimeResult.rows[0]?.avg_days || 0).toFixed(1),
      revenue_recovered: revenueRecovered,
      status_breakdown: statusResult.rows,
      by_payer: payerResult.rows,
      by_cpt: cptResult.rows,
    });
  } catch (err) {
    console.error('Error fetching dashboard stats:', err);
    res.status(500).json({ error: 'Failed to fetch dashboard statistics' });
  }
});

// Probability distribution for pending PAs
router.get('/probability-distribution', async (req, res) => {
  try {
    const { rows } = await db.query(`
      SELECT
        CASE
          WHEN approval_probability <= 30 THEN '0-30'
          WHEN approval_probability <= 50 THEN '31-50'
          WHEN approval_probability <= 70 THEN '51-70'
          WHEN approval_probability <= 85 THEN '71-85'
          ELSE '86-100'
        END as bucket,
        COUNT(*) as count
      FROM pa_requests
      WHERE status IN ('draft', 'submitted')
        AND approval_probability IS NOT NULL
      GROUP BY bucket
      ORDER BY bucket
    `);

    const buckets = [
      { name: '0-30%', count: 0 },
      { name: '31-50%', count: 0 },
      { name: '51-70%', count: 0 },
      { name: '71-85%', count: 0 },
      { name: '86-100%', count: 0 },
    ];

    for (const row of rows) {
      const match = buckets.find(b => b.name.startsWith(row.bucket));
      if (match) match.count = parseInt(row.count);
    }

    res.json(buckets);
  } catch (err) {
    console.error('Error fetching probability distribution:', err);
    res.status(500).json({ error: 'Failed to fetch probability distribution' });
  }
});

// Payer intelligence data
router.get('/intelligence', async (req, res) => {
  try {
    const { rows } = await db.query(`
      SELECT pr.payer_id, p.name as payer_name, pr.cpt_code,
             pr.requires_pa, pr.criteria, pr.supporting_docs,
             pr.avg_approval_days, pr.denial_rate_estimate
      FROM payer_requirements pr
      JOIN payers p ON pr.payer_id = p.id
      ORDER BY p.name, pr.cpt_code
    `);

    res.json(rows);
  } catch (err) {
    console.error('Error fetching intelligence:', err);
    res.status(500).json({ error: 'Failed to fetch payer intelligence' });
  }
});

// Appeal statistics for payer intelligence
router.get('/appeal-stats', async (req, res) => {
  try {
    // Win rate by CARC code
    const carcResult = await db.query(`
      SELECT a.denial_reason_code as carc_code,
             COUNT(*) as total_appeals,
             COUNT(*) FILTER (WHERE a.outcome = 'approved') as won,
             COUNT(*) FILTER (WHERE a.outcome = 'denied') as lost,
             COUNT(*) FILTER (WHERE a.outcome IS NULL) as pending,
             AVG(EXTRACT(DAY FROM (
               CASE WHEN a.outcome IS NOT NULL THEN COALESCE(a.outcome_date, NOW()) ELSE NULL END - a.submitted_at
             ))) as avg_days_to_resolve
      FROM pa_appeals a
      WHERE a.denial_reason_code IS NOT NULL
      GROUP BY a.denial_reason_code
      ORDER BY total_appeals DESC
    `);

    // Win rate by payer
    const payerResult = await db.query(`
      SELECT p.name as payer_name,
             COUNT(*) as total_appeals,
             COUNT(*) FILTER (WHERE a.outcome = 'approved') as won,
             COUNT(*) FILTER (WHERE a.outcome = 'denied') as lost,
             COUNT(*) FILTER (WHERE a.outcome IS NULL) as pending,
             AVG(EXTRACT(DAY FROM (
               CASE WHEN a.outcome IS NOT NULL THEN COALESCE(a.outcome_date, NOW()) ELSE NULL END - a.submitted_at
             ))) as avg_days_to_overturn
      FROM pa_appeals a
      JOIN pa_requests pr ON a.pa_request_id = pr.id
      JOIN payers p ON pr.payer_id = p.id
      GROUP BY p.name
      ORDER BY total_appeals DESC
    `);

    // Upcoming deadlines (< 7 days)
    const urgentResult = await db.query(`
      SELECT a.id, a.pa_request_id, a.deadline_date, a.escalation_type, a.denial_reason_code,
             pr.cpt_code, pr.patient_id, p.name as payer_name,
             GREATEST(0, EXTRACT(DAY FROM (a.deadline_date - NOW()))::int) as days_remaining
      FROM pa_appeals a
      JOIN pa_requests pr ON a.pa_request_id = pr.id
      LEFT JOIN payers p ON pr.payer_id = p.id
      WHERE a.outcome IS NULL
        AND a.deadline_date IS NOT NULL
        AND a.deadline_date > NOW()
      ORDER BY a.deadline_date ASC
    `);

    const urgentAppeals = urgentResult.rows.filter(r => r.days_remaining <= 7);

    // Most winnable denials (by CARC code, based on historical + strategy data)
    const { carcStrategies } = require('../agents/draftAppeal');
    const winnableRanking = carcStrategies
      .map(s => {
        const dbMatch = carcResult.rows.find(r => r.carc_code === s.code);
        const actualWinRate = dbMatch && dbMatch.total_appeals > 0
          ? (parseInt(dbMatch.won) / parseInt(dbMatch.total_appeals)) * 100
          : null;
        return {
          code: s.code,
          name: s.name,
          estimated_win_rate: s.success_rate_estimate,
          actual_win_rate: actualWinRate,
          total_appeals: dbMatch ? parseInt(dbMatch.total_appeals) : 0,
          typical_resolution_days: s.typical_resolution_days,
        };
      })
      .sort((a, b) => (b.actual_win_rate || b.estimated_win_rate) - (a.actual_win_rate || a.estimated_win_rate));

    res.json({
      by_carc_code: carcResult.rows.map(r => ({
        ...r,
        total_appeals: parseInt(r.total_appeals),
        won: parseInt(r.won),
        lost: parseInt(r.lost),
        pending: parseInt(r.pending),
        win_rate: r.total_appeals > 0 && (parseInt(r.won) + parseInt(r.lost)) > 0
          ? ((parseInt(r.won) / (parseInt(r.won) + parseInt(r.lost))) * 100).toFixed(1)
          : null,
        avg_days_to_resolve: r.avg_days_to_resolve ? parseFloat(r.avg_days_to_resolve).toFixed(1) : null,
      })),
      by_payer: payerResult.rows.map(r => ({
        ...r,
        total_appeals: parseInt(r.total_appeals),
        won: parseInt(r.won),
        lost: parseInt(r.lost),
        pending: parseInt(r.pending),
        win_rate: r.total_appeals > 0 && (parseInt(r.won) + parseInt(r.lost)) > 0
          ? ((parseInt(r.won) / (parseInt(r.won) + parseInt(r.lost))) * 100).toFixed(1)
          : null,
        avg_days_to_overturn: r.avg_days_to_overturn ? parseFloat(r.avg_days_to_overturn).toFixed(1) : null,
      })),
      urgent_appeals: urgentAppeals,
      all_pending_appeals: urgentResult.rows,
      most_winnable: winnableRanking,
    });
  } catch (err) {
    console.error('Error fetching appeal stats:', err);
    res.status(500).json({ error: 'Failed to fetch appeal statistics' });
  }
});

// Activity feed — last 10 PA events with timestamps
router.get('/activity-feed', async (req, res) => {
  try {
    const { rows } = await db.query(`
      SELECT pr.id, pr.patient_id, pr.cpt_code, pr.status, pr.status_history,
             pr.created_at, pr.updated_at, p.name as payer_name
      FROM pa_requests pr
      LEFT JOIN payers p ON pr.payer_id = p.id
      ORDER BY pr.updated_at DESC
      LIMIT 20
    `);

    const events = [];

    for (const row of rows) {
      const history = Array.isArray(row.status_history) ? row.status_history : [];

      if (history.length > 0) {
        // Extract the most recent event from status_history
        const lastEvent = history[history.length - 1];
        events.push({
          id: `${row.id}-${history.length - 1}`,
          pa_id: row.id,
          patient_id: row.patient_id,
          payer_name: row.payer_name || 'Unknown Payer',
          cpt_code: row.cpt_code,
          event: lastEvent.to || row.status,
          detail: lastEvent.detail || `PA status: ${lastEvent.to || row.status}`,
          timestamp: lastEvent.timestamp || row.updated_at,
        });
      } else {
        // Fallback: generate event from current PA state
        events.push({
          id: `${row.id}-current`,
          pa_id: row.id,
          patient_id: row.patient_id,
          payer_name: row.payer_name || 'Unknown Payer',
          cpt_code: row.cpt_code,
          event: row.status,
          detail: `PA ${row.status} by ${row.payer_name || 'Unknown Payer'}`,
          timestamp: row.updated_at || row.created_at,
        });
      }
    }

    // Sort by timestamp DESC and limit to 10
    events.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    const feed = events.slice(0, 10);

    res.json(feed);
  } catch (err) {
    console.error('Error fetching activity feed:', err);
    res.status(500).json({ error: 'Failed to fetch activity feed' });
  }
});

module.exports = router;

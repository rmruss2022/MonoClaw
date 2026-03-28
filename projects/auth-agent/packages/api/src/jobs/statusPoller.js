/**
 * Background job: polls CoverMyMeds for status updates on pending PAs.
 *
 * Dev: runs via setInterval every 4 hours (or every 30s in DEMO_MODE).
 * Prod: could be replaced with cron or a proper job queue.
 */

const db = require('../db');
const { getClient } = require('../fhir/coverMyMeds');
const { appendStatusEvent } = require('../services/statusMachine');
const { notifyStatusChange } = require('../services/notifications');

// Poll interval: 30s in demo mode, 4 hours in prod
const POLL_INTERVAL_MS = process.env.DEMO_MODE === 'true'
  ? 30 * 1000        // 30 seconds for demo — status changes fast
  : 4 * 60 * 60 * 1000; // 4 hours for real

let pollerHandle = null;

async function pollPendingPAs() {
  try {
    // Find all PAs awaiting a decision
    const { rows: pendingPAs } = await db.query(`
      SELECT pr.*, p.name as payer_name
      FROM pa_requests pr
      LEFT JOIN payers p ON pr.payer_id = p.id
      WHERE pr.status IN ('submitted', 'pending_decision')
        AND pr.covermymeds_pa_id IS NOT NULL
      ORDER BY pr.submitted_at ASC
    `);

    if (pendingPAs.length === 0) return;

    console.log(`[Poller] Checking ${pendingPAs.length} pending PA(s)...`);

    const cmm = getClient();

    for (const pa of pendingPAs) {
      try {
        const cmmStatus = await cmm.getStatus(pa.covermymeds_pa_id);

        // Map CoverMyMeds status
        const statusMap = {
          pending_decision: 'pending_decision',
          pending_review: 'pending_decision',
          in_review: 'pending_decision',
          additional_info_needed: 'pending_decision',
          approved: 'approved',
          denied: 'denied',
        };

        const newStatus = statusMap[cmmStatus.status] || pa.status;

        if (newStatus === pa.status) continue;

        // Status changed!
        let history = Array.isArray(pa.status_history) ? pa.status_history : [];
        history = appendStatusEvent(history, pa.status, newStatus, 'system', 'Status update from payer via CoverMyMeds');

        const updates = {
          status: newStatus,
          status_history: JSON.stringify(history),
        };

        if (newStatus === 'approved' || newStatus === 'denied') {
          updates.outcome = newStatus;
          updates.decision_at = cmmStatus.decisionDate || new Date().toISOString();
        }

        if (newStatus === 'denied' && cmmStatus.denialReasonCode) {
          updates.denial_reason_code = cmmStatus.denialReasonCode;
          updates.denial_reason_text = cmmStatus.denialReasonText;
        }

        await db.query(`
          UPDATE pa_requests
          SET status = $1,
              outcome = COALESCE($2, outcome),
              decision_at = COALESCE($3, decision_at),
              denial_reason_code = COALESCE($4, denial_reason_code),
              denial_reason_text = COALESCE($5, denial_reason_text),
              status_history = $6,
              updated_at = NOW()
          WHERE id = $7
        `, [
          newStatus,
          updates.outcome || null,
          updates.decision_at || null,
          updates.denial_reason_code || null,
          updates.denial_reason_text || null,
          updates.status_history,
          pa.id,
        ]);

        notifyStatusChange(pa, pa.status, newStatus, cmmStatus.denialReasonText || '');
        console.log(`[Poller] PA ${pa.id.slice(0, 8)}: ${pa.status} → ${newStatus}`);
      } catch (err) {
        console.error(`[Poller] Error checking PA ${pa.id.slice(0, 8)}:`, err.message);
      }
    }
  } catch (err) {
    console.error('[Poller] Error in status polling job:', err.message);
  }
}

function startPoller() {
  if (pollerHandle) return;
  console.log(`[Poller] Starting status polling (interval: ${POLL_INTERVAL_MS / 1000}s)`);
  // Run once on startup after a short delay
  setTimeout(pollPendingPAs, 5000);
  pollerHandle = setInterval(pollPendingPAs, POLL_INTERVAL_MS);
}

function stopPoller() {
  if (pollerHandle) {
    clearInterval(pollerHandle);
    pollerHandle = null;
    console.log('[Poller] Stopped status polling');
  }
}

module.exports = { startPoller, stopPoller, pollPendingPAs };

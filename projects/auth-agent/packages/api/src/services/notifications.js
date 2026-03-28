/**
 * Notification service for PA status changes.
 *
 * Dev: console log
 * Prod: email/SMS to billing staff (stub)
 * OpenClaw: system event for approved/denied
 */

const { execSync } = require('child_process');

/**
 * Send a notification when PA status changes.
 */
function notifyStatusChange(pa, fromStatus, toStatus, detail = '') {
  const paLabel = `PA ${pa.id?.slice(0, 8)} (${pa.cpt_code} / ${pa.patient_id})`;

  // Always log to console
  console.log(`[Notification] ${paLabel}: ${fromStatus} → ${toStatus}${detail ? ` — ${detail}` : ''}`);

  // OpenClaw system events for key transitions
  if (toStatus === 'approved') {
    sendOpenClawEvent(`PA approved: ${pa.cpt_code} for ${pa.patient_id} by ${pa.payer_name || 'payer'}`);
  } else if (toStatus === 'denied') {
    sendOpenClawEvent(`PA denied: ${pa.cpt_code} for ${pa.patient_id} — action needed`);
  } else if (toStatus === 'submitted') {
    sendOpenClawEvent(`PA submitted: ${pa.cpt_code} for ${pa.patient_id} to ${pa.payer_name || 'payer'}`);
  }
}

/**
 * Send openclaw system event (best-effort, non-blocking).
 */
function sendOpenClawEvent(text) {
  try {
    execSync(`openclaw system event --text "${text.replace(/"/g, '\\"')}" --mode now`, {
      timeout: 5000,
      stdio: 'ignore',
    });
  } catch {
    // Non-critical — openclaw CLI may not be available
    console.log(`[OpenClaw] Would send: ${text}`);
  }
}

module.exports = { notifyStatusChange, sendOpenClawEvent };

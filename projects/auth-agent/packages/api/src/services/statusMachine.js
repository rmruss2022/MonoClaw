/**
 * PA Status State Machine
 *
 * Valid transitions:
 *   draft → reviewed → submitted → pending_decision → approved | denied
 *   denied → appeal_draft → appeal_submitted → appeal_decided → closed
 *   approved → closed
 *   appeal_decided → closed
 */

const VALID_TRANSITIONS = {
  draft: ['reviewed'],
  reviewed: ['submitted'],
  submitted: ['pending_decision', 'approved', 'denied'],
  pending_decision: ['approved', 'denied'],
  approved: ['closed'],
  denied: ['appeal_draft'],
  appeal_draft: ['appeal_submitted'],
  appeal_submitted: ['appeal_decided'],
  appeal_decided: ['closed'],
  closed: [],
};

const ALL_STATUSES = Object.keys(VALID_TRANSITIONS);

/**
 * Check if a transition is valid.
 */
function canTransition(from, to) {
  const allowed = VALID_TRANSITIONS[from];
  return allowed ? allowed.includes(to) : false;
}

/**
 * Create a status history event entry.
 */
function createStatusEvent(fromStatus, toStatus, actor = 'system', detail = '') {
  return {
    from: fromStatus,
    to: toStatus,
    actor,
    detail,
    timestamp: new Date().toISOString(),
  };
}

/**
 * Append a status event to the history array and return the new array.
 */
function appendStatusEvent(existingHistory, fromStatus, toStatus, actor = 'system', detail = '') {
  const history = Array.isArray(existingHistory) ? [...existingHistory] : [];
  history.push(createStatusEvent(fromStatus, toStatus, actor, detail));
  return history;
}

module.exports = {
  VALID_TRANSITIONS,
  ALL_STATUSES,
  canTransition,
  createStatusEvent,
  appendStatusEvent,
};

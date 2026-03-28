-- Loop 5: Add status_history for PA lifecycle tracking
-- Append-only event log tracking every status transition

ALTER TABLE pa_requests
  ADD COLUMN IF NOT EXISTS status_history JSONB DEFAULT '[]'::jsonb;

-- Add estimated_decision_date for tracking expected payer response
ALTER TABLE pa_requests
  ADD COLUMN IF NOT EXISTS estimated_decision_date TIMESTAMPTZ;

-- Index for polling pending PAs
CREATE INDEX IF NOT EXISTS idx_pa_requests_pending
  ON pa_requests(status) WHERE status IN ('submitted', 'pending_decision', 'appeal_submitted');

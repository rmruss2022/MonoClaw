-- Appeal Automation Schema Enhancements
-- Loop 6: Add deadline tracking, escalation types, and computed fields

ALTER TABLE pa_appeals
  ADD COLUMN IF NOT EXISTS deadline_date TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS escalation_type TEXT DEFAULT 'first_level',
  ADD COLUMN IF NOT EXISTS denial_reason_code TEXT,
  ADD COLUMN IF NOT EXISTS carc_strategy JSONB,
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

-- Add constraint for escalation types
-- Valid: first_level, second_level, peer_to_peer, external_review
ALTER TABLE pa_appeals
  ADD CONSTRAINT check_escalation_type
  CHECK (escalation_type IN ('first_level', 'second_level', 'peer_to_peer', 'external_review'));

-- Index for deadline tracking queries
CREATE INDEX IF NOT EXISTS idx_pa_appeals_deadline ON pa_appeals(deadline_date)
  WHERE outcome IS NULL;

CREATE INDEX IF NOT EXISTS idx_pa_appeals_pa_request ON pa_appeals(pa_request_id);

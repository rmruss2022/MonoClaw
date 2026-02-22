"""add claim feedback tracking fields

Revision ID: 0004_claim_feedback
Revises: 0003_sync_match_ts
Create Date: 2026-02-22
"""

from alembic import op

revision = "0004_claim_feedback"
down_revision = "0003_sync_match_ts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='user_settlement_preferences' AND column_name='claim_status'
            ) THEN
                ALTER TABLE user_settlement_preferences ADD COLUMN claim_status VARCHAR(30);
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='user_settlement_preferences' AND column_name='claim_submitted_at'
            ) THEN
                ALTER TABLE user_settlement_preferences ADD COLUMN claim_submitted_at TIMESTAMPTZ;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='user_settlement_preferences' AND column_name='claim_outcome_at'
            ) THEN
                ALTER TABLE user_settlement_preferences ADD COLUMN claim_outcome_at TIMESTAMPTZ;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='user_settlement_preferences' AND column_name='claim_feedback_json'
            ) THEN
                ALTER TABLE user_settlement_preferences ADD COLUMN claim_feedback_json JSONB;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='user_settlement_preferences' AND column_name='claim_feedback_json'
            ) THEN
                ALTER TABLE user_settlement_preferences DROP COLUMN claim_feedback_json;
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='user_settlement_preferences' AND column_name='claim_outcome_at'
            ) THEN
                ALTER TABLE user_settlement_preferences DROP COLUMN claim_outcome_at;
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='user_settlement_preferences' AND column_name='claim_submitted_at'
            ) THEN
                ALTER TABLE user_settlement_preferences DROP COLUMN claim_submitted_at;
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='user_settlement_preferences' AND column_name='claim_status'
            ) THEN
                ALTER TABLE user_settlement_preferences DROP COLUMN claim_status;
            END IF;
        END
        $$;
        """
    )

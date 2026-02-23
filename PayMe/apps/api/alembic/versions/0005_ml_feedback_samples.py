"""add ml_feedback_samples table

Revision ID: 0005_ml_feedback_samples
Revises: 0004_claim_feedback
Create Date: 2026-02-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_ml_feedback_samples"
down_revision = "0004_claim_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ml_feedback_samples (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            settlement_id UUID NOT NULL REFERENCES settlements(id),
            run_id UUID REFERENCES match_runs(id),
            rules_confidence FLOAT NOT NULL,
            similarity FLOAT NOT NULL,
            payout FLOAT NOT NULL,
            urgency FLOAT NOT NULL,
            ease FLOAT NOT NULL,
            label INTEGER,
            outcome VARCHAR(30),
            export_version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_ml_feedback_user_settlement
            ON ml_feedback_samples(user_id, settlement_id);
        CREATE INDEX IF NOT EXISTS idx_ml_feedback_label
            ON ml_feedback_samples(label);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS ml_feedback_samples;
        """
    )

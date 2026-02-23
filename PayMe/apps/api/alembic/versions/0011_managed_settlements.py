"""add managed settlement tables (settlement_questions, claim_submissions)

Revision ID: 0011_managed_settlements
Revises: 0010_user_roles
Create Date: 2026-02-22
"""

from alembic import op

revision = "0011_managed_settlements"
down_revision = "0010_user_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS settlement_questions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            settlement_id UUID NOT NULL REFERENCES settlements(id) ON DELETE CASCADE,
            attorney_id UUID NOT NULL REFERENCES attorney_accounts(id),
            question_text TEXT NOT NULL,
            question_type VARCHAR(20) NOT NULL DEFAULT 'text',
            options_json JSONB,
            order_index INTEGER NOT NULL DEFAULT 0,
            required BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_settlement_questions_settlement
            ON settlement_questions(settlement_id);

        CREATE TABLE IF NOT EXISTS claim_submissions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            settlement_id UUID NOT NULL REFERENCES settlements(id) ON DELETE CASCADE,
            answers_json JSONB NOT NULL DEFAULT '[]',
            gmail_evidence_ids JSONB NOT NULL DEFAULT '[]',
            plaid_evidence_ids JSONB NOT NULL DEFAULT '[]',
            auto_match_score FLOAT,
            auto_approved BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(user_id, settlement_id)
        );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS claim_submissions;
        DROP INDEX IF EXISTS idx_settlement_questions_settlement;
        DROP TABLE IF EXISTS settlement_questions;
        """
    )

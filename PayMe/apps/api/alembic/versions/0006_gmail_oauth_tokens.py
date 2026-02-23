"""add gmail_oauth_tokens table

Revision ID: 0006_gmail_oauth_tokens
Revises: 0005_ml_feedback_samples
Create Date: 2026-02-22
"""

from alembic import op

revision = "0006_gmail_oauth_tokens"
down_revision = "0005_ml_feedback_samples"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS gmail_oauth_tokens (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            access_token_enc TEXT NOT NULL,
            refresh_token_enc TEXT,
            token_expiry TIMESTAMPTZ,
            scopes TEXT,
            gmail_history_id VARCHAR(80),
            granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            revoked_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS gmail_oauth_tokens;")

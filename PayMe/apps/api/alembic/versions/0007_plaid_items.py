"""add plaid_items table

Revision ID: 0007_plaid_items
Revises: 0006_gmail_oauth_tokens
Create Date: 2026-02-22
"""

from alembic import op

revision = "0007_plaid_items"
down_revision = "0006_gmail_oauth_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS plaid_items (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            item_id VARCHAR(255) NOT NULL,
            access_token_enc TEXT NOT NULL,
            institution_id VARCHAR(80),
            institution_name VARCHAR(255),
            status VARCHAR(30) NOT NULL DEFAULT 'active',
            cursor TEXT,
            linked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            revoked_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS plaid_items;")

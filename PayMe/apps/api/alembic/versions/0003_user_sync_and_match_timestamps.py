"""add user sync and first match timestamps

Revision ID: 0003_sync_match_ts
Revises: 0002_add_plaid_transactions
Create Date: 2026-02-22
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_sync_match_ts"
down_revision = "0002_add_plaid_transactions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='users' AND column_name='onboarding_completed_at'
            ) THEN
                ALTER TABLE users ADD COLUMN onboarding_completed_at TIMESTAMPTZ;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='users' AND column_name='gmail_synced_at'
            ) THEN
                ALTER TABLE users ADD COLUMN gmail_synced_at TIMESTAMPTZ;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='users' AND column_name='plaid_synced_at'
            ) THEN
                ALTER TABLE users ADD COLUMN plaid_synced_at TIMESTAMPTZ;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='users' AND column_name='first_match_completed_at'
            ) THEN
                ALTER TABLE users ADD COLUMN first_match_completed_at TIMESTAMPTZ;
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
                WHERE table_name='users' AND column_name='first_match_completed_at'
            ) THEN
                ALTER TABLE users DROP COLUMN first_match_completed_at;
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='users' AND column_name='plaid_synced_at'
            ) THEN
                ALTER TABLE users DROP COLUMN plaid_synced_at;
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='users' AND column_name='gmail_synced_at'
            ) THEN
                ALTER TABLE users DROP COLUMN gmail_synced_at;
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='users' AND column_name='onboarding_completed_at'
            ) THEN
                ALTER TABLE users DROP COLUMN onboarding_completed_at;
            END IF;
        END
        $$;
        """
    )

"""add role to users and user_id to attorney_accounts

Revision ID: 0010_user_roles
Revises: 0009_gateway_payout_tables
Create Date: 2026-02-22
"""

from alembic import op

revision = "0010_user_roles"
down_revision = "0009_gateway_payout_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user';

        ALTER TABLE attorney_accounts
            ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE SET NULL;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE attorney_accounts DROP COLUMN IF EXISTS user_id;
        ALTER TABLE users DROP COLUMN IF EXISTS role;
        """
    )

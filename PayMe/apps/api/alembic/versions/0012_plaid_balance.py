"""add balance columns to plaid_items

Revision ID: 0012_plaid_balance
Revises: 0011_managed_settlements
Create Date: 2026-02-22
"""

from alembic import op

revision = "0012_plaid_balance"
down_revision = "0011_managed_settlements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE plaid_items
            ADD COLUMN IF NOT EXISTS balance_available_cents INTEGER,
            ADD COLUMN IF NOT EXISTS balance_current_cents INTEGER;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE plaid_items
            DROP COLUMN IF EXISTS balance_available_cents,
            DROP COLUMN IF EXISTS balance_current_cents;
        """
    )

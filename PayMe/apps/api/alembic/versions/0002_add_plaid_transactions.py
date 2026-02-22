"""add plaid transactions

Revision ID: 0002_add_plaid_transactions
Revises: 0001_initial
Create Date: 2026-02-22
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_add_plaid_transactions"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plaid_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider_txn_id", sa.String(255), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("merchant_name", sa.String(255)),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(100)),
        sa.Column("is_subscription", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.UniqueConstraint("user_id", "provider_txn_id", name="uq_user_provider_txn"),
    )
    op.create_index("idx_plaid_user_time", "plaid_transactions", ["user_id", "posted_at"])


def downgrade() -> None:
    op.drop_index("idx_plaid_user_time", table_name="plaid_transactions")
    op.drop_table("plaid_transactions")

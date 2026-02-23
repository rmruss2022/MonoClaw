"""add attorney_accounts, settlement_accounts, claim_approvals, payout_batches, payout_transfers

Revision ID: 0009_gateway_payout_tables
Revises: 0008_autofill_tables
Create Date: 2026-02-22
"""

from alembic import op

revision = "0009_gateway_payout_tables"
down_revision = "0008_autofill_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS attorney_accounts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            firm_name VARCHAR(255),
            api_key_hash VARCHAR(255) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS settlement_accounts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            attorney_id UUID NOT NULL REFERENCES attorney_accounts(id),
            settlement_id UUID NOT NULL UNIQUE REFERENCES settlements(id),
            bank_name VARCHAR(255),
            account_ref_enc TEXT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            linked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS claim_approvals (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            settlement_id UUID NOT NULL REFERENCES settlements(id),
            attorney_id UUID NOT NULL REFERENCES attorney_accounts(id),
            approved_amount_cents INTEGER,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            review_note TEXT,
            approved_at TIMESTAMPTZ,
            rejected_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(user_id, settlement_id)
        );
        CREATE INDEX IF NOT EXISTS idx_claim_approvals_status
            ON claim_approvals(settlement_id, status);

        CREATE TABLE IF NOT EXISTS payout_batches (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            attorney_id UUID NOT NULL REFERENCES attorney_accounts(id),
            settlement_id UUID NOT NULL REFERENCES settlements(id),
            status VARCHAR(20) NOT NULL DEFAULT 'queued',
            total_transfers INTEGER NOT NULL DEFAULT 0,
            successful_transfers INTEGER NOT NULL DEFAULT 0,
            failed_transfers INTEGER NOT NULL DEFAULT 0,
            total_amount_cents INTEGER NOT NULL DEFAULT 0,
            idempotency_key VARCHAR(255) NOT NULL UNIQUE,
            initiated_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_payout_batch_settlement
            ON payout_batches(settlement_id, status);

        CREATE TABLE IF NOT EXISTS payout_transfers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            batch_id UUID NOT NULL REFERENCES payout_batches(id),
            approval_id UUID NOT NULL REFERENCES claim_approvals(id),
            user_id UUID NOT NULL REFERENCES users(id),
            amount_cents INTEGER NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            idempotency_key VARCHAR(255) NOT NULL UNIQUE,
            provider_transfer_id VARCHAR(255),
            failure_reason TEXT,
            initiated_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_payout_transfer_batch
            ON payout_transfers(batch_id, status);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS payout_transfers;
        DROP TABLE IF EXISTS payout_batches;
        DROP TABLE IF EXISTS claim_approvals;
        DROP TABLE IF EXISTS settlement_accounts;
        DROP TABLE IF EXISTS attorney_accounts;
        """
    )

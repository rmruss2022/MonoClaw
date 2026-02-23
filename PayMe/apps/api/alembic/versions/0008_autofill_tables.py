"""add autofill_jobs, autofill_job_steps, autofill_artifacts tables

Revision ID: 0008_autofill_tables
Revises: 0007_plaid_items
Create Date: 2026-02-22
"""

from alembic import op

revision = "0008_autofill_tables"
down_revision = "0007_plaid_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS autofill_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            settlement_id UUID NOT NULL REFERENCES settlements(id),
            status VARCHAR(20) NOT NULL DEFAULT 'queued',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            next_retry_at TIMESTAMPTZ,
            claim_url VARCHAR(500),
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_autofill_job_user_status
            ON autofill_jobs(user_id, status);

        CREATE TABLE IF NOT EXISTS autofill_job_steps (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            job_id UUID NOT NULL REFERENCES autofill_jobs(id) ON DELETE CASCADE,
            step_name VARCHAR(80) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            input_json JSONB,
            output_json JSONB,
            error_message TEXT,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_autofill_step_job
            ON autofill_job_steps(job_id);

        CREATE TABLE IF NOT EXISTS autofill_artifacts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            job_id UUID NOT NULL REFERENCES autofill_jobs(id) ON DELETE CASCADE,
            step_id UUID REFERENCES autofill_job_steps(id) ON DELETE SET NULL,
            artifact_type VARCHAR(30) NOT NULL,
            content_type VARCHAR(80) NOT NULL,
            storage_key VARCHAR(500) NOT NULL,
            size_bytes INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_autofill_artifact_job
            ON autofill_artifacts(job_id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS autofill_artifacts;
        DROP TABLE IF EXISTS autofill_job_steps;
        DROP TABLE IF EXISTS autofill_jobs;
        """
    )

"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-02-22
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(120)),
        sa.Column("last_name", sa.String(120)),
        sa.Column("state", sa.String(10)),
        sa.Column("dob", sa.Date()),
        sa.Column("gender", sa.String(30)),
        sa.Column("payout_preference_type", sa.String(40)),
        sa.Column("payout_preference_value", sa.String(255)),
        sa.Column("finance_check_frequency", sa.String(40)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "settlements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("website_url", sa.String(500)),
        sa.Column("claim_url", sa.String(500)),
        sa.Column("deadline", sa.DateTime(timezone=True)),
        sa.Column("payout_min_cents", sa.Integer()),
        sa.Column("payout_max_cents", sa.Integer()),
        sa.Column("covered_brands", postgresql.ARRAY(sa.String())),
        sa.Column("tags", postgresql.ARRAY(sa.String())),
        sa.Column("eligibility_predicates", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("summary_text", sa.Text()),
        sa.Column("eligibility_text", sa.Text()),
        sa.Column("embedding", postgresql.ARRAY(sa.Float())),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "settlement_feature_index",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("settlement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("settlements.id", ondelete="CASCADE")),
        sa.Column("feature_key", sa.String(255), nullable=False),
        sa.Column("feature_kind", sa.String(20), nullable=False),
    )
    op.create_index("idx_feature_kind_key", "settlement_feature_index", ["feature_kind", "feature_key"])
    op.create_index("idx_settlement_id", "settlement_feature_index", ["settlement_id"])
    op.create_table(
        "user_features",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("feature_key", sa.String(255), nullable=False),
        sa.Column("value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True)),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_user_feature", "user_features", ["user_id", "feature_key"])
    op.create_table(
        "match_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("experiment_key", sa.String(80), nullable=False),
        sa.Column("variant", sa.String(40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text())),
    )
    op.create_table(
        "match_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("match_runs.id")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("settlement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("settlements.id")),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("reasons_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("missing_features_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_user_latest_results", "match_results", ["user_id", "created_at"])
    op.create_table(
        "user_settlement_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("settlement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("settlements.id"), nullable=False),
        sa.Column("starred", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("pinned_order", sa.Integer()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "settlement_id", name="uq_user_settlement_pref"),
    )
    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("type", sa.String(80), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_events_type_time", "events", ["type", "created_at"])
    op.create_index("idx_events_user_time", "events", ["user_id", "created_at"])
    op.create_table(
        "experiment_exposures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("experiment_key", sa.String(80), nullable=False),
        sa.Column("variant", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "experiment_key", name="uq_exposure_user_exp"),
    )
    op.create_table(
        "gmail_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider_msg_id", sa.String(255), nullable=False),
        sa.Column("internal_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("from_domain", sa.String(255)),
        sa.Column("subject", sa.String(500)),
        sa.Column("snippet", sa.Text()),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.UniqueConstraint("user_id", "provider_msg_id", name="uq_user_provider_msg"),
    )
    op.create_table(
        "gmail_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("evidence_type", sa.String(30), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True)),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("examples_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.UniqueConstraint("user_id", "evidence_type", "key", name="uq_user_evidence"),
    )


def downgrade() -> None:
    for table in [
        "gmail_evidence",
        "gmail_messages",
        "experiment_exposures",
        "events",
        "user_settlement_preferences",
        "match_results",
        "match_runs",
        "user_features",
        "settlement_feature_index",
        "settlements",
        "users",
    ]:
        op.drop_table(table)

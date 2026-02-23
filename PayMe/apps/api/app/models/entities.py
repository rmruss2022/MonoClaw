import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(120))
    last_name: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(10))
    dob: Mapped[datetime | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(30))
    payout_preference_type: Mapped[str | None] = mapped_column(String(40))
    payout_preference_value: Mapped[str | None] = mapped_column(String(255))
    finance_check_frequency: Mapped[str | None] = mapped_column(String(40))
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gmail_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    plaid_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_match_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="user")


class Settlement(Base, TimestampMixin):
    __tablename__ = "settlements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="open")
    website_url: Mapped[str | None] = mapped_column(String(500))
    claim_url: Mapped[str | None] = mapped_column(String(500))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payout_min_cents: Mapped[int | None] = mapped_column(Integer)
    payout_max_cents: Mapped[int | None] = mapped_column(Integer)
    covered_brands: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    eligibility_predicates: Mapped[dict] = mapped_column(JSON, default=dict)
    summary_text: Mapped[str | None] = mapped_column(Text)
    eligibility_text: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Float))


class SettlementFeatureIndex(Base):
    __tablename__ = "settlement_feature_index"
    __table_args__ = (
        Index("idx_feature_kind_key", "feature_kind", "feature_key"),
        Index("idx_settlement_id", "settlement_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    settlement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("settlements.id", ondelete="CASCADE"), nullable=False
    )
    feature_key: Mapped[str] = mapped_column(String(255), nullable=False)
    feature_kind: Mapped[str] = mapped_column(String(20), nullable=False)


class UserFeature(Base):
    __tablename__ = "user_features"
    __table_args__ = (Index("idx_user_feature", "user_id", "feature_key"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    feature_key: Mapped[str] = mapped_column(String(255), nullable=False)
    value_json: Mapped[dict | bool] = mapped_column(JSON, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MatchRun(Base):
    __tablename__ = "match_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    experiment_key: Mapped[str] = mapped_column(String(80), nullable=False)
    variant: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    candidate_count: Mapped[int] = mapped_column(Integer, default=0)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class MatchResult(Base):
    __tablename__ = "match_results"
    __table_args__ = (Index("idx_user_latest_results", "user_id", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("match_runs.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    settlement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("settlements.id"), nullable=False
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    reasons_json: Mapped[dict] = mapped_column(JSON, default=dict)
    missing_features_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserSettlementPreference(Base):
    __tablename__ = "user_settlement_preferences"
    __table_args__ = (UniqueConstraint("user_id", "settlement_id", name="uq_user_settlement_pref"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    settlement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("settlements.id"), nullable=False
    )
    starred: Mapped[bool] = mapped_column(Boolean, default=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    pinned_order: Mapped[int | None] = mapped_column(Integer)
    claim_status: Mapped[str | None] = mapped_column(String(30))
    claim_submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claim_outcome_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claim_feedback_json: Mapped[dict | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("idx_events_type_time", "type", "created_at"),
        Index("idx_events_user_time", "user_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExperimentExposure(Base):
    __tablename__ = "experiment_exposures"
    __table_args__ = (UniqueConstraint("user_id", "experiment_key", name="uq_exposure_user_exp"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    experiment_key: Mapped[str] = mapped_column(String(80), nullable=False)
    variant: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GmailMessage(Base):
    __tablename__ = "gmail_messages"
    __table_args__ = (UniqueConstraint("user_id", "provider_msg_id", name="uq_user_provider_msg"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    provider_msg_id: Mapped[str] = mapped_column(String(255), nullable=False)
    internal_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    from_domain: Mapped[str | None] = mapped_column(String(255))
    subject: Mapped[str | None] = mapped_column(String(500))
    snippet: Mapped[str | None] = mapped_column(Text)
    raw_json: Mapped[dict | None] = mapped_column(JSON)


class GmailEvidence(Base):
    __tablename__ = "gmail_evidence"
    __table_args__ = (UniqueConstraint("user_id", "evidence_type", "key", name="uq_user_evidence"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(30), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    count: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    examples_json: Mapped[list] = mapped_column(JSON, default=list)


class PlaidTransaction(Base):
    __tablename__ = "plaid_transactions"
    __table_args__ = (
        UniqueConstraint("user_id", "provider_txn_id", name="uq_user_provider_txn"),
        Index("idx_plaid_user_time", "user_id", "posted_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    provider_txn_id: Mapped[str] = mapped_column(String(255), nullable=False)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    merchant_name: Mapped[str | None] = mapped_column(String(255))
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    is_subscription: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_json: Mapped[dict | None] = mapped_column(JSON)


# ---------------------------------------------------------------------------
# Track 1: ML feedback loop
# ---------------------------------------------------------------------------


class MlFeedbackSample(Base, TimestampMixin):
    """Labeled training sample derived from match + claim outcome events."""

    __tablename__ = "ml_feedback_samples"
    __table_args__ = (
        Index("idx_ml_feedback_user_settlement", "user_id", "settlement_id"),
        Index("idx_ml_feedback_label", "label"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    settlement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("settlements.id"), nullable=False
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("match_runs.id"))
    # Feature snapshot at match time
    rules_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    similarity: Mapped[float] = mapped_column(Float, nullable=False)
    payout: Mapped[float] = mapped_column(Float, nullable=False)
    urgency: Mapped[float] = mapped_column(Float, nullable=False)
    ease: Mapped[float] = mapped_column(Float, nullable=False)
    # Outcome label: 1=claimed+positive_outcome, 0=ignored/negative, NULL=pending
    label: Mapped[int | None] = mapped_column(Integer)
    outcome: Mapped[str | None] = mapped_column(String(30))  # paid_out | not_paid_out | ignored | pending
    export_version: Mapped[int] = mapped_column(Integer, default=1)


# ---------------------------------------------------------------------------
# Track 2: Gmail real OAuth tokens
# ---------------------------------------------------------------------------


class GmailOAuthToken(Base, TimestampMixin):
    """Stores per-user Gmail OAuth credentials (tokens encrypted at rest)."""

    __tablename__ = "gmail_oauth_tokens"
    __table_args__ = (UniqueConstraint("user_id", name="uq_gmail_oauth_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    access_token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text)
    token_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[str | None] = mapped_column(Text)
    gmail_history_id: Mapped[str | None] = mapped_column(String(80))  # last synced historyId
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Track 3: Plaid real integration
# ---------------------------------------------------------------------------


class PlaidItem(Base, TimestampMixin):
    """Stores per-user Plaid item (access token encrypted at rest)."""

    __tablename__ = "plaid_items"
    __table_args__ = (UniqueConstraint("user_id", name="uq_plaid_item_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    institution_id: Mapped[str | None] = mapped_column(String(80))
    institution_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), default="active")  # active|requires_reauth|disconnected
    cursor: Mapped[str | None] = mapped_column(Text)  # Plaid transactions cursor
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    balance_available_cents: Mapped[int | None] = mapped_column(Integer)
    balance_current_cents: Mapped[int | None] = mapped_column(Integer)


# ---------------------------------------------------------------------------
# Track 4: Autofill agent service
# ---------------------------------------------------------------------------


class AutofillJob(Base, TimestampMixin):
    """Top-level autofill job per (user, settlement)."""

    __tablename__ = "autofill_jobs"
    __table_args__ = (Index("idx_autofill_job_user_status", "user_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    settlement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("settlements.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|blocked|done|failed
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claim_url: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)


class AutofillJobStep(Base):
    """Step-level progress record within an autofill job."""

    __tablename__ = "autofill_job_steps"
    __table_args__ = (Index("idx_autofill_step_job", "job_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("autofill_jobs.id", ondelete="CASCADE"), nullable=False
    )
    step_name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|running|done|failed|skipped
    input_json: Mapped[dict | None] = mapped_column(JSON)
    output_json: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AutofillArtifact(Base):
    """Binary/text artifact produced during an autofill job step."""

    __tablename__ = "autofill_artifacts"
    __table_args__ = (Index("idx_autofill_artifact_job", "job_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("autofill_jobs.id", ondelete="CASCADE"), nullable=False
    )
    step_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("autofill_job_steps.id", ondelete="SET NULL")
    )
    artifact_type: Mapped[str] = mapped_column(String(30), nullable=False)  # screenshot|html|log
    content_type: Mapped[str] = mapped_column(String(80), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# Track 5: Settlement gateway + payout flow
# ---------------------------------------------------------------------------


class AttorneyAccount(Base, TimestampMixin):
    """Attorney or settlement administrator account."""

    __tablename__ = "attorney_accounts"
    __table_args__ = (UniqueConstraint("email", name="uq_attorney_email"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    firm_name: Mapped[str | None] = mapped_column(String(255))
    api_key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|suspended


class SettlementAccount(Base, TimestampMixin):
    """Bank account linked to a settlement by an attorney."""

    __tablename__ = "settlement_accounts"
    __table_args__ = (UniqueConstraint("settlement_id", name="uq_settlement_account"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attorney_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attorney_accounts.id"), nullable=False
    )
    settlement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("settlements.id"), nullable=False
    )
    bank_name: Mapped[str | None] = mapped_column(String(255))
    account_ref_enc: Mapped[str] = mapped_column(Text, nullable=False)  # encrypted routing+account ref
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|closed
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClaimApproval(Base, TimestampMixin):
    """Attorney approval of a claimant for a specific settlement."""

    __tablename__ = "claim_approvals"
    __table_args__ = (UniqueConstraint("user_id", "settlement_id", name="uq_claim_approval_user_settlement"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    settlement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("settlements.id"), nullable=False
    )
    attorney_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attorney_accounts.id"), nullable=False
    )
    approved_amount_cents: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected|paid|failed
    review_note: Mapped[str | None] = mapped_column(Text)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PayoutBatch(Base, TimestampMixin):
    """Batch payout triggered by an attorney for a settlement."""

    __tablename__ = "payout_batches"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_payout_batch_idem"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attorney_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attorney_accounts.id"), nullable=False
    )
    settlement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("settlements.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|processing|completed|partial|failed
    total_transfers: Mapped[int] = mapped_column(Integer, default=0)
    successful_transfers: Mapped[int] = mapped_column(Integer, default=0)
    failed_transfers: Mapped[int] = mapped_column(Integer, default=0)
    total_amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    initiated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PayoutTransfer(Base, TimestampMixin):
    """Individual payout transfer to a single approved claimant."""

    __tablename__ = "payout_transfers"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_payout_transfer_idem"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payout_batches.id"), nullable=False
    )
    approval_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claim_approvals.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|processing|completed|failed
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_transfer_id: Mapped[str | None] = mapped_column(String(255))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    initiated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Managed settlements: in-app claim Q&A
# ---------------------------------------------------------------------------


class SettlementQuestion(Base, TimestampMixin):
    """Custom question posted by an attorney for a managed settlement."""

    __tablename__ = "settlement_questions"
    __table_args__ = (Index("idx_settlement_questions_settlement", "settlement_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    settlement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("settlements.id", ondelete="CASCADE"), nullable=False
    )
    attorney_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attorney_accounts.id"), nullable=False
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    options_json: Mapped[list | None] = mapped_column(JSON)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ClaimSubmission(Base):
    """In-app claim submission with answers and evidence links."""

    __tablename__ = "claim_submissions"
    __table_args__ = (UniqueConstraint("user_id", "settlement_id", name="uq_claim_submission_user_settlement"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    settlement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("settlements.id", ondelete="CASCADE"), nullable=False
    )
    answers_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    gmail_evidence_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    plaid_evidence_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    auto_match_score: Mapped[float | None] = mapped_column(Float)
    auto_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

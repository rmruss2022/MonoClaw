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

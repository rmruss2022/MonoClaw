from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class MatchResultResponse(BaseModel):
    settlement_id: UUID
    title: str
    score: float
    summary_text: str | None = None
    claim_url: str | None = None
    website_url: str | None = None
    payout_min_cents: int | None = None
    payout_max_cents: int | None = None
    deadline: datetime | None = None
    states: list[str] = []
    claim_status: str | None = None
    claim_submitted_at: datetime | None = None
    claim_outcome_at: datetime | None = None
    reasons_json: dict
    missing_features_json: list
    pinned: bool = False


class MatchRunResponse(BaseModel):
    run_id: UUID
    completed_at: datetime | None
    results: list[MatchResultResponse]


class ClaimOutcomeRequest(BaseModel):
    outcome: Literal["paid_out", "not_paid_out"]


class OngoingClaimResponse(BaseModel):
    settlement_id: UUID
    title: str
    claim_url: str | None = None
    claim_status: str
    claim_submitted_at: datetime | None = None
    claim_outcome_at: datetime | None = None
    score: float | None = None


class ClaimHistoryResponse(BaseModel):
    settlement_id: UUID
    title: str
    claim_url: str | None = None
    claim_status: str
    claim_submitted_at: datetime | None = None
    claim_outcome_at: datetime | None = None
    amount_paid_cents: int | None = None

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MatchResultResponse(BaseModel):
    settlement_id: UUID
    title: str
    score: float
    reasons_json: dict
    missing_features_json: list
    pinned: bool = False


class MatchRunResponse(BaseModel):
    run_id: UUID
    completed_at: datetime | None
    results: list[MatchResultResponse]

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.settings import settings
from app.models.entities import (
    Event,
    GmailEvidence,
    GmailMessage,
    MatchResult,
    MatchRun,
    PlaidTransaction,
    Settlement,
    SettlementFeatureIndex,
    User,
    UserFeature,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin_enabled() -> None:
    if not settings.admin_debug:
        raise HTTPException(status_code=404, detail="Debug endpoint disabled")


@router.get("/events")
def list_events(
    limit: int = Query(default=100, le=500),
    type: str | None = None,  # noqa: A002
    user_id: UUID | None = None,
    db: Session = Depends(get_db),
):
    _require_admin_enabled()
    stmt = select(Event).order_by(desc(Event.created_at)).limit(limit)
    if type:
        stmt = stmt.where(Event.type == type)
    if user_id:
        stmt = stmt.where(Event.user_id == user_id)
    events = db.scalars(stmt).all()
    return [
        {"id": str(e.id), "type": e.type, "user_id": str(e.user_id) if e.user_id else None, "payload": e.payload_json}
        for e in events
    ]


@router.get("/logs/tail")
def tail_logs(n: int = Query(default=200, le=500)):
    _require_admin_enabled()
    log_path = Path(settings.log_file_path)
    if not log_path.exists():
        return {"lines": []}
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return {"lines": lines[-n:]}


@router.get("/users")
def list_users(
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    _require_admin_enabled()
    users = db.scalars(select(User).order_by(desc(User.created_at)).offset(offset).limit(limit)).all()
    return [
        {
            "id": str(u.id),
            "username": u.username,
            "email": u.email,
            "state": u.state,
            "created_at": u.created_at,
            "onboarding_completed_at": u.onboarding_completed_at,
            "gmail_synced_at": u.gmail_synced_at,
            "plaid_synced_at": u.plaid_synced_at,
            "first_match_completed_at": u.first_match_completed_at,
            "match_count": db.scalar(select(func.count(MatchResult.id)).where(MatchResult.user_id == u.id)) or 0,
        }
        for u in users
    ]


@router.get("/users/{user_id}")
def get_user_details(user_id: UUID, db: Session = Depends(get_db)):
    _require_admin_enabled()
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    latest_run = db.scalar(
        select(MatchRun.id).where(MatchRun.user_id == user_id).order_by(desc(MatchRun.completed_at)).limit(1)
    )
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "state": user.state,
        "sync": {
            "gmail_synced_at": user.gmail_synced_at,
            "plaid_synced_at": user.plaid_synced_at,
            "first_match_completed_at": user.first_match_completed_at,
        },
        "counts": {
            "user_features": db.scalar(select(func.count(UserFeature.id)).where(UserFeature.user_id == user.id)) or 0,
            "gmail_messages": db.scalar(select(func.count(GmailMessage.id)).where(GmailMessage.user_id == user.id)) or 0,
            "gmail_evidence": db.scalar(select(func.count(GmailEvidence.id)).where(GmailEvidence.user_id == user.id)) or 0,
            "plaid_transactions": db.scalar(select(func.count(PlaidTransaction.id)).where(PlaidTransaction.user_id == user.id)) or 0,
            "match_results": db.scalar(select(func.count(MatchResult.id)).where(MatchResult.user_id == user.id)) or 0,
        },
        "latest_run_id": str(latest_run) if latest_run else None,
    }


@router.get("/settlements")
def list_settlements(
    limit: int = Query(default=200, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    _require_admin_enabled()
    rows = db.scalars(select(Settlement).order_by(desc(Settlement.created_at)).offset(offset).limit(limit)).all()
    return [
        {
            "id": str(s.id),
            "title": s.title,
            "status": s.status,
            "deadline": s.deadline,
            "payout_min_cents": s.payout_min_cents,
            "payout_max_cents": s.payout_max_cents,
            "tags": s.tags or [],
            "feature_index_count": db.scalar(
                select(func.count(SettlementFeatureIndex.id)).where(SettlementFeatureIndex.settlement_id == s.id)
            )
            or 0,
        }
        for s in rows
    ]


@router.get("/settlements/{settlement_id}")
def get_settlement_details(settlement_id: UUID, db: Session = Depends(get_db)):
    _require_admin_enabled()
    settlement = db.get(Settlement, settlement_id)
    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")
    features = db.scalars(
        select(SettlementFeatureIndex.feature_key).where(SettlementFeatureIndex.settlement_id == settlement.id)
    ).all()
    return {
        "id": str(settlement.id),
        "title": settlement.title,
        "status": settlement.status,
        "website_url": settlement.website_url,
        "claim_url": settlement.claim_url,
        "deadline": settlement.deadline,
        "payout_min_cents": settlement.payout_min_cents,
        "payout_max_cents": settlement.payout_max_cents,
        "covered_brands": settlement.covered_brands or [],
        "tags": settlement.tags or [],
        "summary_text": settlement.summary_text,
        "eligibility_text": settlement.eligibility_text,
        "eligibility_predicates": settlement.eligibility_predicates,
        "feature_keys": features,
    }


@router.get("/stats/overview")
def stats_overview(db: Session = Depends(get_db)):
    _require_admin_enabled()
    return {
        "users": db.scalar(select(func.count(User.id))) or 0,
        "settlements": db.scalar(select(func.count(Settlement.id))) or 0,
        "match_runs": db.scalar(select(func.count(MatchRun.id))) or 0,
        "match_results": db.scalar(select(func.count(MatchResult.id))) or 0,
        "gmail_messages": db.scalar(select(func.count(GmailMessage.id))) or 0,
        "gmail_evidence": db.scalar(select(func.count(GmailEvidence.id))) or 0,
        "plaid_transactions": db.scalar(select(func.count(PlaidTransaction.id))) or 0,
        "users_with_onboarding": db.scalar(
            select(func.count(User.id)).where(User.onboarding_completed_at.is_not(None))
        )
        or 0,
        "users_with_gmail_sync": db.scalar(select(func.count(User.id)).where(User.gmail_synced_at.is_not(None))) or 0,
        "users_with_plaid_sync": db.scalar(select(func.count(User.id)).where(User.plaid_synced_at.is_not(None))) or 0,
    }


@router.get("/stats/users/{user_id}")
def stats_for_user(user_id: UUID, db: Session = Depends(get_db)):
    _require_admin_enabled()
    if not db.get(User, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    latest_run = db.scalar(
        select(MatchRun.id).where(MatchRun.user_id == user_id).order_by(desc(MatchRun.completed_at)).limit(1)
    )
    latest_count = (
        db.scalar(select(func.count(MatchResult.id)).where(MatchResult.run_id == latest_run))
        if latest_run
        else 0
    )
    avg_score = db.scalar(select(func.avg(MatchResult.score)).where(MatchResult.user_id == user_id)) or 0
    return {
        "user_id": str(user_id),
        "total_match_results": db.scalar(select(func.count(MatchResult.id)).where(MatchResult.user_id == user_id)) or 0,
        "latest_run_id": str(latest_run) if latest_run else None,
        "latest_run_result_count": latest_count or 0,
        "average_score": float(avg_score),
        "gmail_messages": db.scalar(select(func.count(GmailMessage.id)).where(GmailMessage.user_id == user_id)) or 0,
        "plaid_transactions": db.scalar(select(func.count(PlaidTransaction.id)).where(PlaidTransaction.user_id == user_id))
        or 0,
    }

from datetime import UTC, datetime

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    ClaimApproval,
    MatchResult,
    PayoutTransfer,
    Settlement,
    UserSettlementPreference,
)
from app.services.events.service import emit_event


def _get_pref(db: Session, user_id, settlement_id) -> UserSettlementPreference:
    pref = db.scalar(
        select(UserSettlementPreference).where(
            and_(
                UserSettlementPreference.user_id == user_id,
                UserSettlementPreference.settlement_id == settlement_id,
            )
        )
    )
    if not pref:
        pref = UserSettlementPreference(user_id=user_id, settlement_id=settlement_id, pinned=False)
        db.add(pref)
        db.flush()
    return pref


def set_pinned(db: Session, user_id, settlement_id, pinned: bool) -> UserSettlementPreference:
    pref = _get_pref(db, user_id, settlement_id)
    pref.pinned = pinned
    if pinned and pref.pinned_order is None:
        max_order = db.scalar(
            select(func.max(UserSettlementPreference.pinned_order)).where(
                and_(UserSettlementPreference.user_id == user_id, UserSettlementPreference.pinned == True)  # noqa: E712
            )
        )
        pref.pinned_order = (max_order or 0) + 1
    if not pinned:
        pref.pinned_order = None
    emit_event(db, "settlement_pinned" if pinned else "settlement_unpinned", user_id, {"settlement_id": str(settlement_id)})
    db.flush()
    return pref


def _claim_event_context(db: Session, user_id, settlement_id) -> dict:
    latest_match = db.scalar(
        select(MatchResult)
        .where(and_(MatchResult.user_id == user_id, MatchResult.settlement_id == settlement_id))
        .order_by(desc(MatchResult.created_at))
        .limit(1)
    )
    score = latest_match.score if latest_match else None
    if score is None:
        score_bucket = "unknown"
    elif score >= 0.8:
        score_bucket = "high"
    elif score >= 0.5:
        score_bucket = "medium"
    else:
        score_bucket = "low"
    return {
        "settlement_id": str(settlement_id),
        "run_id": str(latest_match.run_id) if latest_match else None,
        "score": score,
        "score_bucket": score_bucket,
    }


def record_claim_form_opened(db: Session, user_id, settlement_id) -> None:
    emit_event(db, "claim_form_opened", user_id, _claim_event_context(db, user_id, settlement_id))
    db.flush()


def set_claim_submitted(db: Session, user_id, settlement_id) -> UserSettlementPreference:
    pref = _get_pref(db, user_id, settlement_id)
    pref.claim_status = "submitted"
    pref.claim_submitted_at = datetime.now(UTC)
    pref.claim_outcome_at = None
    emit_event(db, "claim_submitted", user_id, _claim_event_context(db, user_id, settlement_id))
    db.flush()
    return pref


def set_claim_outcome(db: Session, user_id, settlement_id, outcome: str) -> UserSettlementPreference:
    pref = _get_pref(db, user_id, settlement_id)
    pref.claim_status = outcome
    pref.claim_outcome_at = datetime.now(UTC)
    emit_event(db, f"claim_{outcome}", user_id, _claim_event_context(db, user_id, settlement_id))
    db.flush()
    return pref


def list_ongoing_claims(db: Session, user_id):
    prefs = db.scalars(
        select(UserSettlementPreference).where(
            and_(
                UserSettlementPreference.user_id == user_id,
                UserSettlementPreference.claim_status == "submitted",
            )
        )
    ).all()
    rows = []
    for pref in prefs:
        settlement = db.get(Settlement, pref.settlement_id)
        latest_score = db.scalar(
            select(MatchResult.score)
            .where(and_(MatchResult.user_id == user_id, MatchResult.settlement_id == pref.settlement_id))
            .order_by(desc(MatchResult.created_at))
            .limit(1)
        )
        rows.append(
            {
                "settlement_id": pref.settlement_id,
                "title": settlement.title if settlement else "Unknown settlement",
                "claim_url": settlement.claim_url if settlement else None,
                "claim_status": pref.claim_status or "submitted",
                "claim_submitted_at": pref.claim_submitted_at,
                "claim_outcome_at": pref.claim_outcome_at,
                "score": latest_score,
            }
        )
    return rows


def list_claim_history(db: Session, user_id) -> list[dict]:
    """Return resolved claims (paid_out or not_paid_out) ordered by outcome date."""
    prefs = db.scalars(
        select(UserSettlementPreference)
        .where(
            and_(
                UserSettlementPreference.user_id == user_id,
                UserSettlementPreference.claim_status.in_(["paid_out", "not_paid_out"]),
            )
        )
        .order_by(desc(UserSettlementPreference.claim_outcome_at))
    ).all()

    rows = []
    for pref in prefs:
        settlement = db.get(Settlement, pref.settlement_id)

        # Look up the completed payout transfer amount, if any
        approval = db.scalar(
            select(ClaimApproval).where(
                and_(
                    ClaimApproval.user_id == user_id,
                    ClaimApproval.settlement_id == pref.settlement_id,
                    ClaimApproval.status == "paid",
                )
            )
        )
        amount_paid_cents = None
        if approval is not None:
            transfer = db.scalar(
                select(PayoutTransfer)
                .where(
                    and_(
                        PayoutTransfer.approval_id == approval.id,
                        PayoutTransfer.status == "completed",
                    )
                )
                .order_by(PayoutTransfer.created_at.desc())
                .limit(1)
            )
            if transfer is not None:
                amount_paid_cents = transfer.amount_cents

        rows.append(
            {
                "settlement_id": pref.settlement_id,
                "title": settlement.title if settlement else "Unknown settlement",
                "claim_url": settlement.claim_url if settlement else None,
                "claim_status": pref.claim_status,
                "claim_submitted_at": pref.claim_submitted_at,
                "claim_outcome_at": pref.claim_outcome_at,
                "amount_paid_cents": amount_paid_cents,
            }
        )
    return rows

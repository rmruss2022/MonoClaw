from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.entities import User
from app.models.entities import Settlement
from app.models.entities import UserSettlementPreference
from pydantic import BaseModel as _BaseModel
from app.schemas.matching import ClaimHistoryResponse, ClaimOutcomeRequest, MatchResultResponse, MatchRunResponse, OngoingClaimResponse
from app.services.matching.engine import explain_for_settlement, latest_results, run_match
from app.services.matching.preferences import (
    list_claim_history,
    list_ongoing_claims,
    record_claim_form_opened,
    set_claim_outcome,
    set_claim_submitted,
    set_pinned,
)
from app.services.events.service import emit_event

router = APIRouter(prefix="/match", tags=["matching"])
settlement_router = APIRouter(prefix="/settlements", tags=["settlements"])
claims_router = APIRouter(prefix="/claims", tags=["claims"])


@router.post("/run", response_model=MatchRunResponse)
def run_match_route(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    run = run_match(db, user)
    db.commit()
    rows = latest_results(db, user.id)
    return MatchRunResponse(
        run_id=run.id,
        completed_at=run.completed_at,
        results=[MatchResultResponse(**{k: v for k, v in row.items() if k != "pinned_order"}) for row in rows],
    )


@router.get("/results", response_model=list[MatchResultResponse])
def get_results_route(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = latest_results(db, user.id)
    return [MatchResultResponse(**{k: v for k, v in row.items() if k != "pinned_order"}) for row in rows]


@router.get("/explain/{settlement_id}")
def explain_route(settlement_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    payload = explain_for_settlement(db, user.id, settlement_id)
    if not payload:
        raise HTTPException(status_code=404, detail="No match explanation found")
    return payload


@settlement_router.post("/{settlement_id}/pin")
def pin_route(settlement_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    pref = set_pinned(db, user.id, settlement_id, True)
    db.commit()
    return {"settlement_id": settlement_id, "pinned": pref.pinned}


@settlement_router.delete("/{settlement_id}/pin")
def unpin_route(settlement_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    pref = set_pinned(db, user.id, settlement_id, False)
    db.commit()
    return {"settlement_id": settlement_id, "pinned": pref.pinned}


@settlement_router.post("/{settlement_id}/claim/submitted")
def claim_submitted_route(settlement_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    pref = set_claim_submitted(db, user.id, settlement_id)
    db.commit()
    return {"settlement_id": settlement_id, "claim_status": pref.claim_status}


@settlement_router.post("/{settlement_id}/claim/opened")
def claim_opened_route(settlement_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    record_claim_form_opened(db, user.id, settlement_id)
    db.commit()
    return {"settlement_id": settlement_id, "status": "opened_recorded"}


@settlement_router.post("/{settlement_id}/claim/outcome")
def claim_outcome_route(
    settlement_id: UUID,
    payload: ClaimOutcomeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    pref = set_claim_outcome(db, user.id, settlement_id, payload.outcome)
    db.commit()
    return {"settlement_id": settlement_id, "claim_status": pref.claim_status}


@settlement_router.get("/{settlement_id}")
def settlement_detail(settlement_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    settlement = db.get(Settlement, settlement_id)
    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")
    pref = (
        db.query(UserSettlementPreference)
        .filter(
            UserSettlementPreference.user_id == user.id,
            UserSettlementPreference.settlement_id == settlement_id,
        )
        .first()
    )
    emit_event(db, "settlement_viewed", user.id, {"settlement_id": str(settlement_id)})
    db.commit()
    return {
        "id": str(settlement.id),
        "title": settlement.title,
        "summary_text": settlement.summary_text,
        "eligibility_text": settlement.eligibility_text,
        "status": settlement.status,
        "claim_url": settlement.claim_url,
        "website_url": settlement.website_url,
        "payout_min_cents": settlement.payout_min_cents,
        "payout_max_cents": settlement.payout_max_cents,
        "deadline": settlement.deadline,
        "states": (settlement.eligibility_predicates or {}).get("states", []),
        "claim_status": pref.claim_status if pref else None,
        "claim_submitted_at": pref.claim_submitted_at if pref else None,
        "claim_outcome_at": pref.claim_outcome_at if pref else None,
    }


@claims_router.get("/ongoing", response_model=list[OngoingClaimResponse])
def ongoing_claims_route(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [OngoingClaimResponse(**row) for row in list_ongoing_claims(db, user.id)]


@claims_router.get("/history", response_model=list[ClaimHistoryResponse])
def claim_history_route(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [ClaimHistoryResponse(**row) for row in list_claim_history(db, user.id)]


# ---------------------------------------------------------------------------
# Managed settlements: in-app claim Q&A (user-facing)
# ---------------------------------------------------------------------------


class ClaimSubmitRequest(_BaseModel):
    answers: list[dict]  # [{question_id, value}]
    gmail_evidence_ids: list[str] = []
    plaid_evidence_ids: list[str] = []


@settlement_router.get("/{settlement_id}/questions")
def settlement_questions_route(
    settlement_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return questions for a settlement (empty list means not managed)."""
    from app.services.settlements.questions_service import list_questions  # noqa: PLC0415

    questions = list_questions(db, settlement_id)
    return [
        {
            "id": str(q.id),
            "settlement_id": str(q.settlement_id),
            "question_text": q.question_text,
            "question_type": q.question_type,
            "options_json": q.options_json,
            "order_index": q.order_index,
            "required": q.required,
        }
        for q in questions
    ]


@settlement_router.get("/{settlement_id}/evidence")
def settlement_evidence_route(
    settlement_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return matching gmail + plaid evidence for the current user and settlement."""
    from app.services.settlements.submission_service import get_evidence_for_user  # noqa: PLC0415

    return get_evidence_for_user(db, user.id, settlement_id)


@settlement_router.post("/{settlement_id}/submit")
def settlement_submit_route(
    settlement_id: UUID,
    body: ClaimSubmitRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Submit an in-app claim with answers and optional evidence."""
    from app.services.settlements.submission_service import submit_claim  # noqa: PLC0415

    try:
        result = submit_claim(
            db,
            user_id=user.id,
            settlement_id=settlement_id,
            answers=body.answers,
            gmail_ids=body.gmail_evidence_ids,
            plaid_ids=body.plaid_evidence_ids,
        )
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result

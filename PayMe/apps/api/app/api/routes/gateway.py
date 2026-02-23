"""Settlement gateway and attorney payout routes — Track 5.

Attorney account registration, settlement-account linking, claimant approval,
payout batch execution, and reconciliation.

Auth: JWT Bearer token required.  The requesting user must have role
'attorney', 'admin', or 'super_user'.  The AttorneyAccount is resolved
from the current user's user_id FK.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.entities import AttorneyAccount, User
from app.services.gateway.attorney_service import (
    approve_claimant,
    link_settlement_account,
    list_all_submitted_claimants,
    list_submitted_claimants,
    reject_claimant,
)
from app.services.gateway.payout_service import (
    create_payout_batch,
    execute_payouts,
    get_account_balance,
    get_batch_reconciliation,
    list_payout_history,
    process_payout_batch,
)

router = APIRouter(prefix="/gateway", tags=["gateway"])

_GATEWAY_ROLES = {"attorney", "admin", "super_user"}


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------


async def get_attorney(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AttorneyAccount:
    if user.role not in _GATEWAY_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Gateway access requires attorney, admin, or super_user role",
        )
    attorney = db.scalar(
        select(AttorneyAccount).where(AttorneyAccount.user_id == user.id)
    )
    if attorney is None or attorney.status != "active":
        raise HTTPException(
            status_code=404,
            detail="No active attorney account linked to your user. "
            "Contact an admin to provision one.",
        )
    return attorney


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class RegisterAttorneyRequest(BaseModel):
    name: str
    firm_name: str | None = None


class LinkSettlementAccountRequest(BaseModel):
    settlement_id: UUID
    bank_name: str | None = None
    account_ref: str


class ApproveClaimantRequest(BaseModel):
    amount_cents: int | None = None
    note: str | None = None


class RejectClaimantRequest(BaseModel):
    note: str | None = None


class CreatePayoutBatchRequest(BaseModel):
    settlement_id: UUID
    idempotency_key: str


class ExecutePayoutsItem(BaseModel):
    user_id: UUID
    settlement_id: UUID
    amount_cents: int | None = None


class ExecutePayoutsRequest(BaseModel):
    items: list[ExecutePayoutsItem]
    idempotency_key: str


class CreateQuestionRequest(BaseModel):
    question_text: str
    question_type: str = "text"  # text|yes_no|date|amount|select
    options_json: list[str] | None = None
    order_index: int = 0
    required: bool = True


class UpdateQuestionRequest(BaseModel):
    question_text: str | None = None
    question_type: str | None = None
    options_json: list[str] | None = None
    order_index: int | None = None
    required: bool | None = None


# ---------------------------------------------------------------------------
# Attorney self-registration (authenticated)
# ---------------------------------------------------------------------------


@router.post("/attorneys", status_code=201)
def register_attorney_route(
    body: RegisterAttorneyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create or update an attorney account for the current user.

    Requires the user's role to be 'attorney', 'admin', or 'super_user'.
    Returns the attorney account details (no API key — JWT is used for auth).
    """
    if user.role not in _GATEWAY_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Gateway access requires attorney, admin, or super_user role",
        )

    existing = db.scalar(
        select(AttorneyAccount).where(AttorneyAccount.user_id == user.id)
    )
    if existing is not None:
        # Update in place
        existing.name = body.name
        existing.firm_name = body.firm_name
        existing.status = "active"
        db.commit()
        return {
            "attorney_id": str(existing.id),
            "name": existing.name,
            "email": existing.email,
            "firm_name": existing.firm_name,
        }

    from app.services.gateway.attorney_service import generate_api_key  # noqa: PLC0415
    import uuid as _uuid  # noqa: PLC0415

    _, hashed_key = generate_api_key()
    account = AttorneyAccount(
        id=_uuid.uuid4(),
        user_id=user.id,
        name=body.name,
        email=user.email,
        firm_name=body.firm_name,
        api_key_hash=hashed_key,
        status="active",
    )
    db.add(account)
    db.commit()
    return {
        "attorney_id": str(account.id),
        "name": account.name,
        "email": account.email,
        "firm_name": account.firm_name,
    }


# ---------------------------------------------------------------------------
# Gateway "me" — resolve current attorney session
# ---------------------------------------------------------------------------


@router.get("/me")
def gateway_me(attorney: AttorneyAccount = Depends(get_attorney)):
    """Return the attorney account for the currently authenticated user."""
    return {
        "attorney_id": str(attorney.id),
        "name": attorney.name,
        "email": attorney.email,
        "firm_name": attorney.firm_name,
    }


# ---------------------------------------------------------------------------
# Account balance
# ---------------------------------------------------------------------------


@router.get("/account/balance")
def get_balance(
    db: Session = Depends(get_db),
    attorney: AttorneyAccount = Depends(get_attorney),
):
    """Return sandbox balance summary for the current attorney's settlement fund."""
    return get_account_balance(db, attorney=attorney)


# ---------------------------------------------------------------------------
# Settlement account linking
# ---------------------------------------------------------------------------


@router.post("/attorneys/{attorney_id}/settlement-accounts", status_code=201)
def link_settlement_account_route(
    attorney_id: UUID,
    body: LinkSettlementAccountRequest,
    db: Session = Depends(get_db),
    attorney: AttorneyAccount = Depends(get_attorney),
):
    """Link a bank account to a settlement for this attorney."""
    account = link_settlement_account(
        db,
        attorney=attorney,
        settlement_id=body.settlement_id,
        bank_name=body.bank_name,
        account_ref=body.account_ref,
    )
    db.commit()
    return {
        "account_id": str(account.id),
        "settlement_id": str(account.settlement_id),
        "status": account.status,
    }


# ---------------------------------------------------------------------------
# Claimant listing
# ---------------------------------------------------------------------------


@router.get("/attorneys/{attorney_id}/claimants/{settlement_id}")
def list_claimants_route(
    attorney_id: UUID,
    settlement_id: UUID,
    db: Session = Depends(get_db),
    attorney: AttorneyAccount = Depends(get_attorney),
):
    """List users who have submitted claims for this settlement."""
    return list_submitted_claimants(db, attorney=attorney, settlement_id=settlement_id)


# ---------------------------------------------------------------------------
# Approve / reject
# ---------------------------------------------------------------------------


@router.post("/attorneys/{attorney_id}/approve/{settlement_id}/{user_id}")
def approve_claimant_route(
    attorney_id: UUID,
    settlement_id: UUID,
    user_id: UUID,
    body: ApproveClaimantRequest,
    db: Session = Depends(get_db),
    attorney: AttorneyAccount = Depends(get_attorney),
):
    """Approve a claimant for a settlement payout."""
    try:
        approval = approve_claimant(
            db,
            attorney=attorney,
            user_id=user_id,
            settlement_id=settlement_id,
            amount_cents=body.amount_cents,
            note=body.note,
        )
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {"approval_id": str(approval.id), "status": approval.status}


@router.post("/attorneys/{attorney_id}/reject/{settlement_id}/{user_id}")
def reject_claimant_route(
    attorney_id: UUID,
    settlement_id: UUID,
    user_id: UUID,
    body: RejectClaimantRequest,
    db: Session = Depends(get_db),
    attorney: AttorneyAccount = Depends(get_attorney),
):
    """Reject a claimant for a settlement."""
    approval = reject_claimant(
        db,
        attorney=attorney,
        user_id=user_id,
        settlement_id=settlement_id,
        note=body.note,
    )
    db.commit()
    return {"approval_id": str(approval.id), "status": approval.status}


# ---------------------------------------------------------------------------
# Global payout queue and execution (primary gateway view)
# ---------------------------------------------------------------------------


@router.get("/payouts/queue")
def get_payout_queue(
    db: Session = Depends(get_db),
    attorney: AttorneyAccount = Depends(get_attorney),
):
    """Return all submitted claimants across every settlement this attorney manages."""
    return list_all_submitted_claimants(db, attorney=attorney)


@router.post("/payouts/execute")
def execute_payouts_route(
    body: ExecutePayoutsRequest,
    db: Session = Depends(get_db),
    attorney: AttorneyAccount = Depends(get_attorney),
):
    """Approve and immediately pay a set of selected claimants.

    Creates one payout batch per unique settlement_id and processes it
    immediately (sandbox simulation).  Fully idempotent.
    """
    try:
        result = execute_payouts(
            db,
            attorney=attorney,
            items=[item.model_dump() for item in body.items],
            idempotency_key=body.idempotency_key,
        )
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result


@router.get("/payouts/history")
def get_payout_history(
    db: Session = Depends(get_db),
    attorney: AttorneyAccount = Depends(get_attorney),
):
    """Return all past payout transfers for this attorney's settlements."""
    return list_payout_history(db, attorney=attorney)


# ---------------------------------------------------------------------------
# Payout batch endpoints (kept for backward compatibility)
# ---------------------------------------------------------------------------


@router.post("/payouts/batch", status_code=201)
def create_payout_batch_route(
    body: CreatePayoutBatchRequest,
    db: Session = Depends(get_db),
    attorney: AttorneyAccount = Depends(get_attorney),
):
    """Create (or retrieve) a payout batch by idempotency key."""
    batch = create_payout_batch(
        db,
        attorney=attorney,
        settlement_id=body.settlement_id,
        idempotency_key=body.idempotency_key,
    )
    db.commit()
    return {
        "batch_id": str(batch.id),
        "status": batch.status,
        "total_transfers": batch.total_transfers,
        "total_amount_cents": batch.total_amount_cents,
    }


@router.post("/payouts/{batch_id}/process")
def process_payout_batch_route(
    batch_id: UUID,
    db: Session = Depends(get_db),
    attorney: AttorneyAccount = Depends(get_attorney),
):
    """Execute all pending transfers in the batch (mock simulation)."""
    from app.models.entities import PayoutBatch  # noqa: PLC0415

    batch = db.get(PayoutBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Payout batch not found")
    if batch.attorney_id != attorney.id:
        raise HTTPException(
            status_code=403,
            detail="This batch does not belong to your attorney account",
        )
    batch = process_payout_batch(db, batch_id=batch_id)
    db.commit()
    return {
        "batch_id": str(batch.id),
        "status": batch.status,
        "successful_transfers": batch.successful_transfers,
        "failed_transfers": batch.failed_transfers,
    }


@router.get("/payouts/{batch_id}/reconcile")
def reconcile_payout_batch_route(
    batch_id: UUID,
    db: Session = Depends(get_db),
    attorney: AttorneyAccount = Depends(get_attorney),
):
    """Return the full reconciliation report for a payout batch."""
    from app.models.entities import PayoutBatch  # noqa: PLC0415

    batch = db.get(PayoutBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Payout batch not found")
    if batch.attorney_id != attorney.id:
        raise HTTPException(
            status_code=403,
            detail="This batch does not belong to your attorney account",
        )
    try:
        report = get_batch_reconciliation(db, batch_id=batch_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return report


# ---------------------------------------------------------------------------
# Settlement questions (managed settlements Q&A)
# ---------------------------------------------------------------------------


@router.get("/settlements")
def list_managed_settlements_route(
    db: Session = Depends(get_db),
    attorney: AttorneyAccount = Depends(get_attorney),
):
    """List all settlements managed by this attorney."""
    from app.models.entities import Settlement, SettlementAccount  # noqa: PLC0415

    rows = db.execute(
        select(Settlement.id, Settlement.title)
        .join(SettlementAccount, SettlementAccount.settlement_id == Settlement.id)
        .where(SettlementAccount.attorney_id == attorney.id)
        .order_by(Settlement.title)
    ).all()
    return [{"id": str(r.id), "title": r.title} for r in rows]


@router.get("/settlements/{settlement_id}/questions")
def list_questions_route(
    settlement_id: UUID,
    db: Session = Depends(get_db),
    attorney: AttorneyAccount = Depends(get_attorney),
):
    """List all questions for a managed settlement."""
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


@router.post("/settlements/{settlement_id}/questions", status_code=201)
def create_question_route(
    settlement_id: UUID,
    body: CreateQuestionRequest,
    db: Session = Depends(get_db),
    attorney: AttorneyAccount = Depends(get_attorney),
):
    """Create a new question for a managed settlement."""
    from app.services.settlements.questions_service import create_question  # noqa: PLC0415

    q = create_question(
        db,
        attorney=attorney,
        settlement_id=settlement_id,
        text=body.question_text,
        q_type=body.question_type,
        options=body.options_json,
        order=body.order_index,
        required=body.required,
    )
    db.commit()
    return {
        "id": str(q.id),
        "settlement_id": str(q.settlement_id),
        "question_text": q.question_text,
        "question_type": q.question_type,
        "options_json": q.options_json,
        "order_index": q.order_index,
        "required": q.required,
    }


@router.post("/settlements/{settlement_id}/questions/seed")
def seed_questions_route(
    settlement_id: UUID,
    db: Session = Depends(get_db),
    attorney: AttorneyAccount = Depends(get_attorney),
):
    """Seed 4 default questions for a managed settlement (idempotent)."""
    from app.services.settlements.questions_service import seed_default_questions  # noqa: PLC0415

    questions = seed_default_questions(db, attorney, settlement_id)
    db.commit()
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


@router.put("/questions/{question_id}")
def update_question_route(
    question_id: UUID,
    body: UpdateQuestionRequest,
    db: Session = Depends(get_db),
    attorney: AttorneyAccount = Depends(get_attorney),
):
    """Update a question (attorney must own it)."""
    from app.services.settlements.questions_service import update_question  # noqa: PLC0415

    try:
        q = update_question(
            db,
            attorney=attorney,
            question_id=question_id,
            question_text=body.question_text,
            question_type=body.question_type,
            options_json=body.options_json,
            order_index=body.order_index,
            required=body.required,
        )
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "id": str(q.id),
        "question_text": q.question_text,
        "question_type": q.question_type,
        "options_json": q.options_json,
        "order_index": q.order_index,
        "required": q.required,
    }


@router.delete("/questions/{question_id}", status_code=204)
def delete_question_route(
    question_id: UUID,
    db: Session = Depends(get_db),
    attorney: AttorneyAccount = Depends(get_attorney),
):
    """Delete a question (attorney must own it)."""
    from app.services.settlements.questions_service import delete_question  # noqa: PLC0415

    try:
        delete_question(db, attorney=attorney, question_id=question_id)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

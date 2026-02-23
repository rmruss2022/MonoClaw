"""Service layer for in-app claim submissions.

Handles answer validation, auto-match scoring, upsert of ClaimSubmission,
and optional auto-approval with immediate payout.
"""

import uuid
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AttorneyAccount,
    ClaimSubmission,
    GmailMessage,
    PlaidTransaction,
    Settlement,
    SettlementAccount,
    SettlementQuestion,
)
from app.services.matching.preferences import set_claim_submitted


def _settlement_keywords(settlement: Settlement) -> list[str]:
    """Combine covered_brands and tags into a single keyword list."""
    brands = settlement.covered_brands or []
    tags = settlement.tags or []
    return [k for k in brands + tags if k]


def _evidence_keywords(settlement: Settlement) -> list[str]:
    """Use high-signal terms for evidence matching; avoid generic tag noise."""
    brands = [b.strip() for b in (settlement.covered_brands or []) if b and b.strip()]
    if brands:
        return brands

    generic_tags = {
        "consumer",
        "billing",
        "class-action",
        "class action",
        "lawsuit",
        "settlement",
        "claim",
        "refund",
    }
    filtered_tags = [
        t.strip()
        for t in (settlement.tags or [])
        if t and t.strip() and t.strip().lower() not in generic_tags
    ]
    return filtered_tags


def get_evidence_for_user(db: Session, user_id, settlement_id) -> dict:
    """Return matching gmail messages and plaid transactions for a user/settlement."""
    settlement = db.get(Settlement, settlement_id)
    if settlement is None:
        return {"gmail": [], "plaid": []}

    keywords = _evidence_keywords(settlement)
    if not keywords:
        return {"gmail": [], "plaid": []}

    # Gmail evidence
    gmail_filters = or_(
        *[
            GmailMessage.subject.ilike(f"%{kw}%") | GmailMessage.snippet.ilike(f"%{kw}%")
            for kw in keywords
        ]
    )
    gmail_rows = (
        db.scalars(
            select(GmailMessage)
            .where(GmailMessage.user_id == user_id, gmail_filters)
            .order_by(GmailMessage.internal_date.desc())
            .limit(5)
        ).all()
    )

    # Plaid evidence
    plaid_filters = or_(
        *[PlaidTransaction.merchant_name.ilike(f"%{kw}%") for kw in keywords]
    )
    plaid_rows = (
        db.scalars(
            select(PlaidTransaction)
            .where(PlaidTransaction.user_id == user_id, plaid_filters)
            .order_by(PlaidTransaction.posted_at.desc())
            .limit(5)
        ).all()
    )

    return {
        "gmail": [
            {
                "id": str(m.id),
                "subject": m.subject,
                "from_domain": m.from_domain,
                "internal_date": m.internal_date.isoformat() if m.internal_date else None,
                "snippet": m.snippet,
            }
            for m in gmail_rows
        ],
        "plaid": [
            {
                "id": str(t.id),
                "merchant_name": t.merchant_name,
                "amount_cents": t.amount_cents,
                "posted_at": t.posted_at.isoformat() if t.posted_at else None,
                "category": t.category,
            }
            for t in plaid_rows
        ],
    }


def submit_claim(
    db: Session,
    user_id,
    settlement_id,
    answers: list[dict],
    gmail_ids: list[str] | None = None,
    plaid_ids: list[str] | None = None,
) -> dict:
    """Validate answers, compute auto_match_score, upsert ClaimSubmission, trigger payout if approved."""
    gmail_ids = gmail_ids or []
    plaid_ids = plaid_ids or []

    # 1. Load questions and validate required answers
    questions = (
        db.scalars(
            select(SettlementQuestion)
            .where(SettlementQuestion.settlement_id == settlement_id)
            .order_by(SettlementQuestion.order_index)
        ).all()
    )

    answer_map = {str(a["question_id"]): a.get("value") for a in answers}
    for q in questions:
        if q.required and str(q.id) not in answer_map:
            raise ValueError(f"Missing required answer for question: {q.question_text}")

    # 2. Compute auto_match_score
    settlement = db.get(Settlement, settlement_id)
    if settlement is None:
        raise ValueError(f"Settlement {settlement_id} not found")

    keywords = _evidence_keywords(settlement)
    score = 0.0

    # First yes_no question answered "yes" -> +0.3
    first_yes_no = next((q for q in questions if q.question_type == "yes_no"), None)
    if first_yes_no is not None:
        answer_val = answer_map.get(str(first_yes_no.id))
        if answer_val and str(answer_val).lower() in ("yes", "true", "1"):
            score += 0.3

    # Matching plaid transactions -> +0.4
    if plaid_ids and keywords:
        plaid_uuids = [UUID(pid) for pid in plaid_ids]
        plaid_filters = or_(
            *[PlaidTransaction.merchant_name.ilike(f"%{kw}%") for kw in keywords]
        )
        matching_plaid = db.scalar(
            select(PlaidTransaction)
            .where(
                PlaidTransaction.id.in_(plaid_uuids),
                plaid_filters,
            )
            .limit(1)
        )
        if matching_plaid is not None:
            score += 0.4

    # Matching gmail messages -> +0.3
    if gmail_ids and keywords:
        gmail_uuids = [UUID(gid) for gid in gmail_ids]
        gmail_filters = or_(
            *[
                GmailMessage.subject.ilike(f"%{kw}%") | GmailMessage.snippet.ilike(f"%{kw}%")
                for kw in keywords
            ]
        )
        matching_gmail = db.scalar(
            select(GmailMessage)
            .where(
                GmailMessage.id.in_(gmail_uuids),
                gmail_filters,
            )
            .limit(1)
        )
        if matching_gmail is not None:
            score += 0.3

    score = min(score, 1.0)
    auto_approved = score >= 0.5

    # 3. Upsert ClaimSubmission
    existing = db.scalar(
        select(ClaimSubmission).where(
            ClaimSubmission.user_id == user_id,
            ClaimSubmission.settlement_id == settlement_id,
        )
    )
    if existing is not None:
        existing.answers_json = answers
        existing.gmail_evidence_ids = gmail_ids
        existing.plaid_evidence_ids = plaid_ids
        existing.auto_match_score = score
        existing.auto_approved = auto_approved
    else:
        db.add(
            ClaimSubmission(
                id=uuid.uuid4(),
                user_id=user_id,
                settlement_id=settlement_id,
                answers_json=answers,
                gmail_evidence_ids=gmail_ids,
                plaid_evidence_ids=plaid_ids,
                auto_match_score=score,
                auto_approved=auto_approved,
            )
        )
    db.flush()

    # 4. Mark claim as submitted
    set_claim_submitted(db, user_id, settlement_id)

    # 5. Auto-approve payout if score >= 0.5
    payout_triggered = False
    amount_cents = None

    if auto_approved:
        sa = db.scalar(
            select(SettlementAccount).where(
                SettlementAccount.settlement_id == settlement_id,
                SettlementAccount.status == "active",
            )
        )
        if sa is not None:
            attorney = db.get(AttorneyAccount, sa.attorney_id)
            if attorney is not None:
                from app.services.gateway.payout_service import execute_payouts  # noqa: PLC0415

                amount_cents = settlement.payout_min_cents
                execute_payouts(
                    db,
                    attorney=attorney,
                    items=[
                        {
                            "user_id": str(user_id),
                            "settlement_id": str(settlement_id),
                            "amount_cents": amount_cents,
                        }
                    ],
                    idempotency_key=f"auto:{user_id}:{settlement_id}",
                )
                payout_triggered = True

    return {
        "auto_approved": auto_approved,
        "auto_match_score": score,
        "payout_triggered": payout_triggered,
        "amount_cents": amount_cents,
    }

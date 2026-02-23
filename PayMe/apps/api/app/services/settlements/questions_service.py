"""Service layer for settlement questions (managed settlements Q&A).

Provides CRUD for attorney-defined questions and an idempotent seed helper
that populates the 4 default questions when a settlement is first managed.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import AttorneyAccount, SettlementQuestion


def list_questions(db: Session, settlement_id) -> list[SettlementQuestion]:
    """Return all questions for a settlement, ordered by order_index."""
    return list(
        db.scalars(
            select(SettlementQuestion)
            .where(SettlementQuestion.settlement_id == settlement_id)
            .order_by(SettlementQuestion.order_index)
        ).all()
    )


def create_question(
    db: Session,
    attorney: AttorneyAccount,
    settlement_id,
    text: str,
    q_type: str = "text",
    options: list[str] | None = None,
    order: int = 0,
    required: bool = True,
) -> SettlementQuestion:
    """Create a new question for a settlement."""
    q = SettlementQuestion(
        id=uuid.uuid4(),
        settlement_id=settlement_id,
        attorney_id=attorney.id,
        question_text=text,
        question_type=q_type,
        options_json=options,
        order_index=order,
        required=required,
    )
    db.add(q)
    db.flush()
    return q


def update_question(
    db: Session,
    attorney: AttorneyAccount,
    question_id,
    **fields,
) -> SettlementQuestion:
    """Update a question. Validates the attorney owns the question via settlement."""
    q = db.get(SettlementQuestion, question_id)
    if q is None:
        raise ValueError(f"Question {question_id} not found")
    if q.attorney_id != attorney.id:
        raise ValueError("Not authorised to update this question")
    for key, value in fields.items():
        if value is not None and hasattr(q, key):
            setattr(q, key, value)
    db.flush()
    return q


def delete_question(
    db: Session,
    attorney: AttorneyAccount,
    question_id,
) -> None:
    """Delete a question. Validates the attorney owns it."""
    q = db.get(SettlementQuestion, question_id)
    if q is None:
        raise ValueError(f"Question {question_id} not found")
    if q.attorney_id != attorney.id:
        raise ValueError("Not authorised to delete this question")
    db.delete(q)
    db.flush()


def seed_default_questions(
    db: Session,
    attorney: AttorneyAccount,
    settlement_id,
) -> list[SettlementQuestion]:
    """Idempotently create 4 default questions if none exist for this settlement."""
    existing = db.scalar(
        select(SettlementQuestion).where(
            SettlementQuestion.settlement_id == settlement_id
        )
    )
    if existing is not None:
        return list_questions(db, settlement_id)

    defaults = [
        ("Did you purchase or use this service?", "yes_no", None, 0, True),
        ("What email address was associated with your purchase?", "text", None, 1, True),
        ("Approximately how much did you spend?", "amount", None, 2, False),
        (
            "Do you consent to us reviewing your linked receipts and transactions as supporting evidence?",
            "yes_no",
            None,
            3,
            True,
        ),
    ]
    questions = []
    for text, q_type, options, order, required in defaults:
        q = create_question(
            db,
            attorney=attorney,
            settlement_id=settlement_id,
            text=text,
            q_type=q_type,
            options=options,
            order=order,
            required=required,
        )
        questions.append(q)
    return questions

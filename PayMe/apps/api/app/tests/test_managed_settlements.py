"""Tests for managed settlements: in-app claim Q&A feature.

Covers questions_service (seed, list, CRUD), submission_service (evidence,
scoring, validation), and the user-facing HTTP routes on settlement_router.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.models.entities import (
    AttorneyAccount,
    GmailMessage,
    PlaidTransaction,
    Settlement,
    SettlementAccount,
    SettlementQuestion,
    User,
)
from app.services.gateway.attorney_service import generate_api_key
from app.tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# DB-level helpers (mirrors test_gateway.py patterns)
# ---------------------------------------------------------------------------


def _make_settlement(db, **kwargs) -> Settlement:
    s = Settlement(
        id=uuid.uuid4(),
        title=kwargs.get("title", "Test Settlement"),
        status=kwargs.get("status", "open"),
        payout_min_cents=kwargs.get("payout_min_cents", 5000),
        payout_max_cents=kwargs.get("payout_max_cents", 20000),
        covered_brands=kwargs.get("covered_brands", ["acme"]),
        tags=kwargs.get("tags", ["consumer"]),
        eligibility_predicates={},
    )
    db.add(s)
    db.flush()
    return s


def _make_user(db, email=None, role: str = "user") -> User:
    uid = uuid.uuid4()
    u = User(
        id=uid,
        username=f"user_{uid.hex[:8]}",
        email=email or f"user_{uid.hex[:8]}@example.com",
        password_hash=hash_password("testpass"),
        first_name="Test",
        last_name="User",
        role=role,
    )
    db.add(u)
    db.flush()
    return u


def _make_attorney(db) -> tuple[User, AttorneyAccount, str]:
    user = _make_user(db, role="attorney")
    _, hashed_key = generate_api_key()
    account = AttorneyAccount(
        id=uuid.uuid4(),
        user_id=user.id,
        name=f"Attorney {user.username}",
        email=user.email,
        firm_name="Test Firm",
        api_key_hash=hashed_key,
        status="active",
    )
    db.add(account)
    db.flush()
    token = create_access_token(str(user.id))
    return user, account, token


def _link_settlement_account(db, attorney: AttorneyAccount, settlement: Settlement):
    from app.core.crypto import encrypt_token

    sa = SettlementAccount(
        id=uuid.uuid4(),
        attorney_id=attorney.id,
        settlement_id=settlement.id,
        bank_name="Test Bank",
        account_ref_enc=encrypt_token("test-routing:000:test-acct:111"),
        status="active",
    )
    db.add(sa)
    db.flush()
    return sa


def _add_gmail_message(db, user_id, subject="Acme receipt", snippet="Your Acme purchase"):
    m = GmailMessage(
        id=uuid.uuid4(),
        user_id=user_id,
        provider_msg_id=f"msg_{uuid.uuid4().hex[:12]}",
        internal_date=datetime.now(timezone.utc),
        from_domain="acme.com",
        subject=subject,
        snippet=snippet,
    )
    db.add(m)
    db.flush()
    return m


def _add_plaid_txn(db, user_id, merchant_name="ACME Corp", amount_cents=1500):
    t = PlaidTransaction(
        id=uuid.uuid4(),
        user_id=user_id,
        provider_txn_id=f"txn_{uuid.uuid4().hex[:12]}",
        posted_at=datetime.now(timezone.utc),
        merchant_name=merchant_name,
        amount_cents=amount_cents,
        category="shopping",
    )
    db.add(t)
    db.flush()
    return t


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db(db_setup):
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# questions_service: seed_default_questions
# ---------------------------------------------------------------------------


def test_seed_default_questions_creates_four(db):
    _, attorney, _ = _make_attorney(db)
    settlement = _make_settlement(db)
    db.commit()

    from app.services.settlements.questions_service import seed_default_questions

    questions = seed_default_questions(db, attorney, settlement.id)
    db.commit()
    assert len(questions) == 4
    assert questions[0].question_type == "yes_no"
    assert questions[1].question_type == "text"
    assert questions[2].question_type == "amount"
    assert questions[3].question_type == "yes_no"


def test_seed_default_questions_idempotent(db):
    _, attorney, _ = _make_attorney(db)
    settlement = _make_settlement(db)
    db.commit()

    from app.services.settlements.questions_service import seed_default_questions

    q1 = seed_default_questions(db, attorney, settlement.id)
    db.commit()
    q2 = seed_default_questions(db, attorney, settlement.id)
    db.commit()
    assert len(q1) == len(q2) == 4
    assert [str(q.id) for q in q1] == [str(q.id) for q in q2]


# ---------------------------------------------------------------------------
# questions_service: list_questions
# ---------------------------------------------------------------------------


def test_list_questions_ordered(db):
    _, attorney, _ = _make_attorney(db)
    settlement = _make_settlement(db)
    db.commit()

    from app.services.settlements.questions_service import seed_default_questions, list_questions

    seed_default_questions(db, attorney, settlement.id)
    db.commit()
    questions = list_questions(db, settlement.id)
    assert len(questions) == 4
    orders = [q.order_index for q in questions]
    assert orders == sorted(orders)


# ---------------------------------------------------------------------------
# submission_service: get_evidence_for_user
# ---------------------------------------------------------------------------


def test_get_evidence_empty_when_no_data(db):
    user = _make_user(db)
    settlement = _make_settlement(db)
    db.commit()

    from app.services.settlements.submission_service import get_evidence_for_user

    result = get_evidence_for_user(db, user.id, settlement.id)
    assert result == {"gmail": [], "plaid": []}


def test_get_evidence_ignores_generic_tag_keyword_noise(db):
    """Generic tags like 'billing' should not pull unrelated Gmail evidence."""
    user = _make_user(db)
    settlement = _make_settlement(
        db,
        title="Starbucks Overcharge Consumer Settlement",
        covered_brands=["starbucks"],
        tags=["consumer", "billing", "class-action"],
    )
    _add_gmail_message(
        db,
        user.id,
        subject="[action needed] Your Claude API access is turned off",
        snippet="Go to the Billing page to add credits.",
    )
    _add_plaid_txn(db, user.id, merchant_name="Starbucks", amount_cents=433)
    db.commit()

    from app.services.settlements.submission_service import get_evidence_for_user

    result = get_evidence_for_user(db, user.id, settlement.id)
    assert result["gmail"] == []
    assert len(result["plaid"]) >= 1


# ---------------------------------------------------------------------------
# submission_service: submit_claim
# ---------------------------------------------------------------------------


def test_submit_claim_yes_only_not_approved(db):
    """yes answer + no evidence -> score 0.3 -> not auto-approved."""
    _, attorney, _ = _make_attorney(db)
    settlement = _make_settlement(db)
    _link_settlement_account(db, attorney, settlement)
    db.commit()

    from app.services.settlements.questions_service import seed_default_questions
    from app.services.settlements.submission_service import submit_claim

    questions = seed_default_questions(db, attorney, settlement.id)
    db.commit()

    answers = [
        {"question_id": str(questions[0].id), "value": "yes"},
        {"question_id": str(questions[1].id), "value": "test@example.com"},
        {"question_id": str(questions[3].id), "value": "yes"},
    ]

    result = submit_claim(db, user_id=attorney.user_id, settlement_id=settlement.id, answers=answers)
    db.commit()

    assert result["auto_match_score"] == pytest.approx(0.3)
    assert result["auto_approved"] is False


def test_submit_claim_yes_plus_plaid_approved(db):
    """yes answer + matching plaid transaction -> score 0.7 -> auto-approved."""
    _, attorney, _ = _make_attorney(db)
    user = _make_user(db)
    settlement = _make_settlement(db, covered_brands=["acme"])
    _link_settlement_account(db, attorney, settlement)
    db.commit()

    from app.services.settlements.questions_service import seed_default_questions
    from app.services.settlements.submission_service import submit_claim

    questions = seed_default_questions(db, attorney, settlement.id)
    txn = _add_plaid_txn(db, user.id, merchant_name="ACME Corp")
    db.commit()

    answers = [
        {"question_id": str(questions[0].id), "value": "yes"},
        {"question_id": str(questions[1].id), "value": "test@example.com"},
        {"question_id": str(questions[3].id), "value": "yes"},
    ]

    result = submit_claim(
        db,
        user_id=user.id,
        settlement_id=settlement.id,
        answers=answers,
        plaid_ids=[str(txn.id)],
    )
    db.commit()

    assert result["auto_match_score"] == pytest.approx(0.7)
    assert result["auto_approved"] is True
    assert result["payout_triggered"] is True


def test_submit_claim_missing_required_raises(db):
    """Missing required answer raises ValueError."""
    _, attorney, _ = _make_attorney(db)
    user = _make_user(db)
    settlement = _make_settlement(db)
    db.commit()

    from app.services.settlements.questions_service import seed_default_questions
    from app.services.settlements.submission_service import submit_claim

    questions = seed_default_questions(db, attorney, settlement.id)
    db.commit()

    # Only answer the optional question (index 2), skip all required ones
    answers = [
        {"question_id": str(questions[2].id), "value": "50"},
    ]

    with pytest.raises(ValueError, match="Missing required answer"):
        submit_claim(db, user_id=user.id, settlement_id=settlement.id, answers=answers)


# ---------------------------------------------------------------------------
# HTTP routes: GET /settlements/{id}/questions
# ---------------------------------------------------------------------------


def test_get_questions_returns_empty_for_unmanaged(client):
    """GET /settlements/{id}/questions returns [] for settlement without questions."""
    # Sign up a user to get a token
    signup = client.post(
        "/auth/signup",
        json={"username": "q_test_user", "email": "q_test@example.com", "password": "password123"},
    )
    token = signup.json()["access_token"]

    # The conftest creates an Amazon Prime Settlement with no questions
    # Get the settlement id via match results or just use the conftest settlement
    db = TestingSessionLocal()
    try:
        s = db.scalar(select(Settlement).where(Settlement.title == "Amazon Prime Settlement"))
        settlement_id = str(s.id) if s else str(uuid.uuid4())
    finally:
        db.close()

    resp = client.get(
        f"/settlements/{settlement_id}/questions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_questions_returns_questions_for_managed(client):
    """GET /settlements/{id}/questions returns questions after seeding."""
    db = TestingSessionLocal()
    try:
        _, attorney, _ = _make_attorney(db)
        settlement = _make_settlement(db)
        db.commit()

        from app.services.settlements.questions_service import seed_default_questions

        seed_default_questions(db, attorney, settlement.id)
        db.commit()
        settlement_id = str(settlement.id)
    finally:
        db.close()

    # Create a regular user to query
    signup = client.post(
        "/auth/signup",
        json={"username": "q_managed_user", "email": "q_managed@example.com", "password": "password123"},
    )
    token = signup.json()["access_token"]

    resp = client.get(
        f"/settlements/{settlement_id}/questions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 4
    assert data[0]["question_type"] == "yes_no"


# ---------------------------------------------------------------------------
# HTTP routes: POST /settlements/{id}/submit
# ---------------------------------------------------------------------------


def test_submit_route_returns_auto_approved(client):
    """POST /settlements/{id}/submit returns auto_approved field."""
    db = TestingSessionLocal()
    try:
        _, attorney, _ = _make_attorney(db)
        settlement = _make_settlement(db)
        _link_settlement_account(db, attorney, settlement)
        db.commit()

        from app.services.settlements.questions_service import seed_default_questions

        questions = seed_default_questions(db, attorney, settlement.id)
        db.commit()
        settlement_id = str(settlement.id)
        q_ids = [str(q.id) for q in questions]
    finally:
        db.close()

    signup = client.post(
        "/auth/signup",
        json={"username": "submit_test_user", "email": "submit_test@example.com", "password": "password123"},
    )
    token = signup.json()["access_token"]

    resp = client.post(
        f"/settlements/{settlement_id}/submit",
        json={
            "answers": [
                {"question_id": q_ids[0], "value": "yes"},
                {"question_id": q_ids[1], "value": "test@example.com"},
                {"question_id": q_ids[3], "value": "yes"},
            ],
            "gmail_evidence_ids": [],
            "plaid_evidence_ids": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "auto_approved" in data
    assert "auto_match_score" in data
    assert isinstance(data["auto_approved"], bool)

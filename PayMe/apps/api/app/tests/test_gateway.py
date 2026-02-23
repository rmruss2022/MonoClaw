"""Tests for Track 5: Settlement gateway and attorney payout flow.

All DB setup is done directly via the db fixture to keep tests focused on the
gateway logic rather than the user-facing API.  The HTTP client is only used
for gateway endpoints.

Auth: all gateway routes now require JWT Bearer token with an attorney/admin/
super_user role.  Test helpers create users + AttorneyAccounts directly in the
DB and issue JWTs via create_access_token.
"""

import uuid

import pytest
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.models.entities import (
    AttorneyAccount,
    ClaimApproval,
    PayoutBatch,
    PayoutTransfer,
    Settlement,
    User,
    UserSettlementPreference,
)
from app.services.gateway.attorney_service import generate_api_key
from app.tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# DB-level helpers
# ---------------------------------------------------------------------------


def _make_settlement(db, **kwargs) -> Settlement:
    s = Settlement(
        id=uuid.uuid4(),
        title=kwargs.get("title", "Test Settlement"),
        status=kwargs.get("status", "open"),
        payout_min_cents=kwargs.get("payout_min_cents", 5000),
        payout_max_cents=kwargs.get("payout_max_cents", 20000),
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


def _make_attorney_user(db) -> tuple[User, AttorneyAccount, str]:
    """Create a user with role='attorney', a linked AttorneyAccount, and a JWT token."""
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


def _set_submitted(db, user: User, settlement: Settlement) -> UserSettlementPreference:
    from datetime import datetime, timezone

    pref = UserSettlementPreference(
        id=uuid.uuid4(),
        user_id=user.id,
        settlement_id=settlement.id,
        claim_status="submitted",
        claim_submitted_at=datetime.now(timezone.utc),
    )
    db.add(pref)
    db.flush()
    return pref


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db(db_setup):
    """Provide a short-lived DB session for direct fixture setup."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Attorney registration (self-registration via JWT)
# ---------------------------------------------------------------------------


def test_register_attorney_returns_id(client):
    """Attorney users can register (or update) their attorney account via POST /gateway/attorneys."""
    # Sign up a user and elevate to attorney in DB
    signup = client.post(
        "/auth/signup",
        json={"username": "atty_reg_test", "email": "atty_reg@example.com", "password": "password123"},
    )
    assert signup.status_code == 200
    token = signup.json()["access_token"]

    # Set role to attorney directly via DB
    db = TestingSessionLocal()
    try:
        me_data = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
        user = db.scalar(select(User).where(User.id == uuid.UUID(me_data["id"])))
        user.role = "attorney"
        db.commit()
    finally:
        db.close()

    resp = client.post(
        "/gateway/attorneys",
        json={"name": "Alice Smith", "firm_name": "Smith & Co"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "attorney_id" in data
    assert data["email"] == "atty_reg@example.com"
    assert "api_key" not in data  # No API key in new auth model


def test_register_attorney_duplicate_upserts(client):
    """Calling POST /gateway/attorneys twice for the same user updates the record."""
    signup = client.post(
        "/auth/signup",
        json={"username": "atty_dup_test", "email": "atty_dup@example.com", "password": "password123"},
    )
    token = signup.json()["access_token"]

    db = TestingSessionLocal()
    try:
        me_data = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
        user = db.scalar(select(User).where(User.id == uuid.UUID(me_data["id"])))
        user.role = "attorney"
        db.commit()
    finally:
        db.close()

    resp1 = client.post(
        "/gateway/attorneys",
        json={"name": "Bob Jones"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 201
    id1 = resp1.json()["attorney_id"]

    resp2 = client.post(
        "/gateway/attorneys",
        json={"name": "Bob Jones Updated", "firm_name": "Jones LLC"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 201
    assert resp2.json()["attorney_id"] == id1
    assert resp2.json()["firm_name"] == "Jones LLC"


# ---------------------------------------------------------------------------
# Settlement account linking
# ---------------------------------------------------------------------------


def _register_and_link(client, db, settlement_id):
    """Helper: create attorney user in DB, link a settlement account, return (attorney_id, jwt_token)."""
    _, account, token = _make_attorney_user(db)
    db.commit()

    link = client.post(
        f"/gateway/attorneys/{account.id}/settlement-accounts",
        json={
            "settlement_id": str(settlement_id),
            "bank_name": "Test Bank",
            "account_ref": "routing:000000000:account:111111111",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert link.status_code == 201
    return str(account.id), token


def test_link_settlement_account(client, db):
    settlement = _make_settlement(db)
    db.commit()

    _, account, token = _make_attorney_user(db)
    db.commit()

    resp = client.post(
        f"/gateway/attorneys/{account.id}/settlement-accounts",
        json={
            "settlement_id": str(settlement.id),
            "bank_name": "First National",
            "account_ref": "routing:123456789:account:987654321",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["settlement_id"] == str(settlement.id)
    assert data["status"] == "active"
    assert "account_id" in data


# ---------------------------------------------------------------------------
# Claimant listing
# ---------------------------------------------------------------------------


def test_list_claimants_empty(client, db):
    settlement = _make_settlement(db)
    db.commit()

    _, account, token = _make_attorney_user(db)
    db.commit()

    resp = client.get(
        f"/gateway/attorneys/{account.id}/claimants/{settlement.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_claimants_returns_submitted(client, db):
    settlement = _make_settlement(db)
    user = _make_user(db)
    _set_submitted(db, user, settlement)
    db.commit()

    _, account, token = _make_attorney_user(db)
    db.commit()

    resp = client.get(
        f"/gateway/attorneys/{account.id}/claimants/{settlement.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    claimants = resp.json()
    assert len(claimants) == 1
    assert claimants[0]["user_id"] == str(user.id)
    assert claimants[0]["email"] == user.email


# ---------------------------------------------------------------------------
# Approve / reject claimants
# ---------------------------------------------------------------------------


def test_approve_claimant(client, db):
    settlement = _make_settlement(db)
    user = _make_user(db)
    _set_submitted(db, user, settlement)
    db.commit()

    attorney_id, token = _register_and_link(client, db, settlement.id)

    resp = client.post(
        f"/gateway/attorneys/{attorney_id}/approve/{settlement.id}/{user.id}",
        json={"amount_cents": 7500, "note": "Verified purchase records"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert "approval_id" in data

    # Verify persistence
    fresh_db = TestingSessionLocal()
    try:
        approval = fresh_db.scalar(
            select(ClaimApproval).where(
                ClaimApproval.user_id == user.id,
                ClaimApproval.settlement_id == settlement.id,
            )
        )
        assert approval is not None
        assert approval.status == "approved"
        assert approval.approved_amount_cents == 7500
    finally:
        fresh_db.close()


def test_reject_claimant(client, db):
    settlement = _make_settlement(db)
    user = _make_user(db)
    _set_submitted(db, user, settlement)
    db.commit()

    attorney_id, token = _register_and_link(client, db, settlement.id)

    resp = client.post(
        f"/gateway/attorneys/{attorney_id}/reject/{settlement.id}/{user.id}",
        json={"note": "Insufficient documentation"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"

    fresh_db = TestingSessionLocal()
    try:
        approval = fresh_db.scalar(
            select(ClaimApproval).where(
                ClaimApproval.user_id == user.id,
                ClaimApproval.settlement_id == settlement.id,
            )
        )
        assert approval is not None
        assert approval.status == "rejected"
        assert approval.rejected_at is not None
    finally:
        fresh_db.close()


def test_approve_without_settlement_account_fails(client, db):
    settlement = _make_settlement(db)
    user = _make_user(db)
    _set_submitted(db, user, settlement)
    db.commit()

    # Create attorney but do NOT link a settlement account
    _, account, token = _make_attorney_user(db)
    db.commit()

    resp = client.post(
        f"/gateway/attorneys/{account.id}/approve/{settlement.id}/{user.id}",
        json={"amount_cents": 5000},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Payout batches
# ---------------------------------------------------------------------------


def _create_approved_setup(client, db):
    """Create settlement + user + submitted claim + attorney + approval. Return context dict."""
    settlement = _make_settlement(db, payout_min_cents=10000)
    user = _make_user(db)
    _set_submitted(db, user, settlement)
    db.commit()

    attorney_id, token = _register_and_link(client, db, settlement.id)

    approve_resp = client.post(
        f"/gateway/attorneys/{attorney_id}/approve/{settlement.id}/{user.id}",
        json={"amount_cents": 10000},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert approve_resp.status_code == 200

    return {
        "settlement": settlement,
        "user": user,
        "attorney_id": attorney_id,
        "token": token,
    }


def test_create_payout_batch_idempotent(client, db):
    ctx = _create_approved_setup(client, db)
    token = ctx["token"]
    settlement = ctx["settlement"]

    idem_key = f"idem-test-{uuid.uuid4().hex}"

    resp1 = client.post(
        "/gateway/payouts/batch",
        json={
            "settlement_id": str(settlement.id),
            "idempotency_key": idem_key,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 201
    batch_id_1 = resp1.json()["batch_id"]

    resp2 = client.post(
        "/gateway/payouts/batch",
        json={
            "settlement_id": str(settlement.id),
            "idempotency_key": idem_key,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 201
    assert resp2.json()["batch_id"] == batch_id_1


def test_process_batch_completes(client, db):
    ctx = _create_approved_setup(client, db)
    token = ctx["token"]
    settlement = ctx["settlement"]

    idem_key = f"idem-process-{uuid.uuid4().hex}"

    batch_resp = client.post(
        "/gateway/payouts/batch",
        json={
            "settlement_id": str(settlement.id),
            "idempotency_key": idem_key,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert batch_resp.status_code == 201
    batch_id = batch_resp.json()["batch_id"]

    process_resp = client.post(
        f"/gateway/payouts/{batch_id}/process",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert process_resp.status_code == 200
    data = process_resp.json()
    assert data["status"] in {"completed", "partial", "failed"}
    total = data["successful_transfers"] + data["failed_transfers"]
    assert total >= 1


def test_reconciliation_report(client, db):
    ctx = _create_approved_setup(client, db)
    token = ctx["token"]
    settlement = ctx["settlement"]

    idem_key = f"idem-recon-{uuid.uuid4().hex}"

    batch_resp = client.post(
        "/gateway/payouts/batch",
        json={
            "settlement_id": str(settlement.id),
            "idempotency_key": idem_key,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    batch_id = batch_resp.json()["batch_id"]

    client.post(f"/gateway/payouts/{batch_id}/process", headers={"Authorization": f"Bearer {token}"})

    recon_resp = client.get(
        f"/gateway/payouts/{batch_id}/reconcile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert recon_resp.status_code == 200
    report = recon_resp.json()

    assert report["batch_id"] == batch_id
    assert report["settlement_id"] == str(settlement.id)
    assert "total" in report
    assert "successful" in report
    assert "failed" in report
    assert "total_amount_cents" in report
    assert isinstance(report["transfers"], list)
    assert report["successful"] + report["failed"] == report["total"]


# ---------------------------------------------------------------------------
# Auth / security
# ---------------------------------------------------------------------------


def test_missing_auth_rejected(client, db):
    """Requests without a JWT are rejected with 401 or 422."""
    settlement = _make_settlement(db)
    db.commit()

    _, account, _ = _make_attorney_user(db)
    db.commit()

    resp = client.get(
        f"/gateway/attorneys/{account.id}/claimants/{settlement.id}"
        # no Authorization header
    )
    assert resp.status_code in (401, 422)


def test_non_attorney_role_rejected(client, db):
    """Users with role='user' cannot access gateway routes."""
    settlement = _make_settlement(db)
    db.commit()

    plain_user = _make_user(db, role="user")
    db.commit()
    plain_token = create_access_token(str(plain_user.id))

    resp = client.get(
        f"/gateway/attorneys/{uuid.uuid4()}/claimants/{settlement.id}",
        headers={"Authorization": f"Bearer {plain_token}"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Transfer idempotency key uniqueness
# ---------------------------------------------------------------------------


def test_payout_transfer_idempotency_key_unique(client, db):
    """Verify that every PayoutTransfer in a batch has a distinct idempotency key."""
    settlement = _make_settlement(db, payout_min_cents=5000)
    users = [_make_user(db) for _ in range(5)]
    for u in users:
        _set_submitted(db, u, settlement)
    db.commit()

    attorney_id, token = _register_and_link(client, db, settlement.id)

    for u in users:
        resp = client.post(
            f"/gateway/attorneys/{attorney_id}/approve/{settlement.id}/{u.id}",
            json={"amount_cents": 5000},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    idem_key = f"idem-unique-{uuid.uuid4().hex}"
    batch_resp = client.post(
        "/gateway/payouts/batch",
        json={
            "settlement_id": str(settlement.id),
            "idempotency_key": idem_key,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert batch_resp.status_code == 201
    batch_id = batch_resp.json()["batch_id"]

    fresh_db = TestingSessionLocal()
    try:
        transfers = fresh_db.scalars(
            select(PayoutTransfer).where(
                PayoutTransfer.batch_id == uuid.UUID(batch_id)
            )
        ).all()

        assert len(transfers) == 5
        keys = [t.idempotency_key for t in transfers]
        assert len(keys) == len(set(keys)), "Duplicate transfer idempotency keys detected"
    finally:
        fresh_db.close()

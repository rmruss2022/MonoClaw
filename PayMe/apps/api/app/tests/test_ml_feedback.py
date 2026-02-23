"""Tests for ML feedback loop service and admin endpoints — Track 1.

Covers:
- Label assignment: paid_out->1, ignored->0, pending->None
- No label leakage (outcome fields absent before they exist)
- Reproducibility: two consecutive exports yield identical results
- get_labeled_dataset schema
- GET /admin/ml/export-labeled endpoint (200 + structure)
- GET /admin/ml/dataset endpoint (200)
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.models.entities import (
    MatchResult,
    MatchRun,
    MlFeedbackSample,
    Settlement,
    User,
    UserSettlementPreference,
)
from app.services.ml.feedback import _assign_label, export_labeled_samples, get_labeled_dataset
from app.tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_user(db: Session, **kwargs) -> User:
    user = User(
        id=uuid.uuid4(),
        username=kwargs.get("username", f"user_{uuid.uuid4().hex[:8]}"),
        email=kwargs.get("email", f"{uuid.uuid4().hex[:8]}@test.com"),
        password_hash="hashed",
        state="CA",
    )
    db.add(user)
    db.flush()
    return user


def _make_settlement(db: Session) -> Settlement:
    s = Settlement(
        id=uuid.uuid4(),
        title=f"Settlement {uuid.uuid4().hex[:6]}",
        status="open",
        eligibility_predicates={},
    )
    db.add(s)
    db.flush()
    return s


def _make_run(db: Session, user: User) -> MatchRun:
    run = MatchRun(
        id=uuid.uuid4(),
        user_id=user.id,
        experiment_key="matching_v1",
        variant="rules_only",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    db.add(run)
    db.flush()
    return run


def _make_match_result(
    db: Session,
    run: MatchRun,
    user: User,
    settlement: Settlement,
    reasons_json: dict | None = None,
) -> MatchResult:
    mr = MatchResult(
        id=uuid.uuid4(),
        run_id=run.id,
        user_id=user.id,
        settlement_id=settlement.id,
        score=0.75,
        reasons_json=reasons_json or {"confidence_breakdown": {"rules": 0.8}},
        missing_features_json=[],
    )
    db.add(mr)
    db.flush()
    return mr


def _make_pref(
    db: Session,
    user: User,
    settlement: Settlement,
    claim_status: str | None,
) -> UserSettlementPreference:
    pref = UserSettlementPreference(
        id=uuid.uuid4(),
        user_id=user.id,
        settlement_id=settlement.id,
        claim_status=claim_status,
        claim_submitted_at=datetime.now(UTC) if claim_status in ("submitted", "opened", "paid_out", "not_paid_out") else None,
        claim_outcome_at=datetime.now(UTC) if claim_status in ("paid_out", "not_paid_out") else None,
    )
    db.add(pref)
    db.flush()
    return pref


# ---------------------------------------------------------------------------
# Unit tests: _assign_label
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "claim_status, expected_label, expected_outcome",
    [
        ("paid_out", 1, "paid_out"),
        ("not_paid_out", 0, "not_paid_out"),
        ("submitted", None, "pending"),
        ("opened", None, "pending"),
        (None, 0, "ignored"),
        ("", 0, "ignored"),
    ],
)
def test_assign_label(claim_status, expected_label, expected_outcome):
    label, outcome = _assign_label(claim_status)
    assert label == expected_label
    assert outcome == expected_outcome


# ---------------------------------------------------------------------------
# Integration tests (require Postgres test DB via db_setup fixture)
# ---------------------------------------------------------------------------


@pytest.fixture
def db(db_setup):
    """Provide a fresh session for each test, rolling back after."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_export_assigns_paid_out_label(db):
    """Samples for paid_out claim_status must receive label=1."""
    user = _make_user(db)
    settlement = _make_settlement(db)
    run = _make_run(db, user)
    _make_match_result(db, run, user, settlement)
    _make_pref(db, user, settlement, "paid_out")
    db.commit()

    samples = export_labeled_samples(db)
    target = [s for s in samples if s["settlement_id"] == str(settlement.id)]
    assert len(target) == 1
    assert target[0]["label"] == 1
    assert target[0]["outcome"] == "paid_out"


def test_export_assigns_ignored_label_when_no_claim(db):
    """Samples with no claim preference must receive label=0, outcome='ignored'."""
    user = _make_user(db)
    settlement = _make_settlement(db)
    run = _make_run(db, user)
    _make_match_result(db, run, user, settlement)
    # No UserSettlementPreference created
    db.commit()

    samples = export_labeled_samples(db)
    target = [s for s in samples if s["settlement_id"] == str(settlement.id)]
    assert len(target) == 1
    assert target[0]["label"] == 0
    assert target[0]["outcome"] == "ignored"


def test_export_pending_claim_has_none_label(db):
    """Samples with submitted/opened status must have label=None (pending)."""
    user = _make_user(db)
    settlement = _make_settlement(db)
    run = _make_run(db, user)
    _make_match_result(db, run, user, settlement)
    _make_pref(db, user, settlement, "submitted")
    db.commit()

    samples = export_labeled_samples(db)
    target = [s for s in samples if s["settlement_id"] == str(settlement.id)]
    assert len(target) == 1
    assert target[0]["label"] is None
    assert target[0]["outcome"] == "pending"


def test_no_label_leakage_before_outcome_exists(db):
    """When claim_outcome_at has not been set, label must NOT be 1.

    This checks that we are reading the current claim_status (which reflects
    whether an outcome has actually been recorded) rather than deriving a label
    from any future-dated field.
    """
    user = _make_user(db)
    settlement = _make_settlement(db)
    run = _make_run(db, user)
    _make_match_result(db, run, user, settlement)
    # Claim is opened but no outcome yet
    _make_pref(db, user, settlement, "opened")
    db.commit()

    samples = export_labeled_samples(db)
    target = [s for s in samples if s["settlement_id"] == str(settlement.id)]
    assert len(target) == 1
    # Must NOT be labeled as positive — outcome hasn't arrived yet
    assert target[0]["label"] is None, (
        "Label leakage: a positive label was assigned before a paid_out outcome was recorded"
    )


def test_export_reproducibility(db):
    """Calling export twice for the same data yields identical sample results."""
    user = _make_user(db)
    settlement = _make_settlement(db)
    run = _make_run(db, user)
    _make_match_result(db, run, user, settlement)
    _make_pref(db, user, settlement, "paid_out")
    db.commit()

    first = export_labeled_samples(db)
    second = export_labeled_samples(db)

    # Compare label and outcome fields — not timestamps
    def _key_fields(samples):
        return [
            {k: v for k, v in s.items() if k not in ("id", "created_at", "updated_at")}
            for s in samples
        ]

    assert _key_fields(first) == _key_fields(second)


def test_export_upserts_existing_sample(db):
    """Running export twice should upsert, not duplicate, ml_feedback_samples rows."""
    from sqlalchemy import func, select

    user = _make_user(db)
    settlement = _make_settlement(db)
    run = _make_run(db, user)
    _make_match_result(db, run, user, settlement)
    _make_pref(db, user, settlement, "paid_out")
    db.commit()

    export_labeled_samples(db)
    export_labeled_samples(db)

    count = db.scalar(
        select(func.count(MlFeedbackSample.id)).where(
            MlFeedbackSample.user_id == user.id,
            MlFeedbackSample.settlement_id == settlement.id,
        )
    )
    assert count == 1, f"Expected 1 row after two exports, got {count}"


def test_get_labeled_dataset_schema(db):
    """get_labeled_dataset must return rows with the expected keys."""
    user = _make_user(db)
    settlement = _make_settlement(db)
    run = _make_run(db, user)
    _make_match_result(db, run, user, settlement)
    _make_pref(db, user, settlement, "paid_out")
    db.commit()

    export_labeled_samples(db)
    rows = get_labeled_dataset(db)

    assert len(rows) >= 1
    expected_keys = {
        "id",
        "user_id",
        "settlement_id",
        "run_id",
        "rules_confidence",
        "similarity",
        "payout",
        "urgency",
        "ease",
        "label",
        "outcome",
        "export_version",
        "created_at",
        "updated_at",
    }
    assert expected_keys.issubset(rows[0].keys())


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


def test_admin_ml_export_labeled_endpoint(client):
    """GET /admin/ml/export-labeled returns 200 with count + samples keys."""
    response = client.get("/admin/ml/export-labeled")
    assert response.status_code == 200
    body = response.json()
    assert "count" in body
    assert "samples" in body
    assert isinstance(body["count"], int)
    assert isinstance(body["samples"], list)


def test_admin_ml_export_labeled_returns_correct_structure(client, db_setup):
    """After seeding a paid_out match, export-labeled should return a sample with label=1."""
    # Sign up, log in, run match, set paid_out
    signup = client.post(
        "/auth/signup",
        json={"username": "mltest_user", "email": "mltest@example.com", "password": "testpass123"},
    )
    assert signup.status_code == 200
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/auth/me", headers=headers)
    user_id = me.json()["id"]

    # Complete onboarding so user has a state
    client.post(
        "/onboarding",
        json={
            "first_name": "ML",
            "last_name": "Test",
            "state": "CA",
            "dob": "1990-01-01",
            "gender": "prefer_not_to_say",
        },
        headers=headers,
    )

    # Trigger a match run
    client.post("/match/run", headers=headers)

    # Fetch matches to get a settlement_id
    matches_resp = client.get("/match/results", headers=headers)
    matches = matches_resp.json()
    if not matches:
        # No matches found (no seeded settlements with CA eligibility beyond conftest one)
        # Still expect the endpoint to return 200
        resp = client.get("/admin/ml/export-labeled")
        assert resp.status_code == 200
        return

    settlement_id = matches[0]["settlement_id"]

    # Mark as paid_out
    client.post(f"/settlements/{settlement_id}/claim/outcome", json={"outcome": "paid_out"}, headers=headers)

    resp = client.get("/admin/ml/export-labeled")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 1
    paid_out_samples = [s for s in body["samples"] if s.get("outcome") == "paid_out"]
    assert len(paid_out_samples) >= 1
    assert paid_out_samples[0]["label"] == 1


def test_admin_ml_dataset_endpoint(client):
    """GET /admin/ml/dataset returns 200 with count + rows keys."""
    response = client.get("/admin/ml/dataset")
    assert response.status_code == 200
    body = response.json()
    assert "count" in body
    assert "rows" in body
    assert isinstance(body["count"], int)
    assert isinstance(body["rows"], list)


def test_admin_ml_train_endpoint_structure(client, monkeypatch):
    """POST /admin/ml/train returns 200 with promoted/metrics fields (trainer mocked)."""
    import sys
    import types

    mock_tr = types.ModuleType("train_ranker")
    mock_tr.main = lambda artifacts_dir=None: {  # type: ignore[attr-defined]
        "promoted": True,
        "weights_version": 1,
        "new_metrics": {
            "precision_at_5": 0.8,
            "precision_at_10": 0.7,
            "auc_approx": 0.75,
            "sample_count": 2,
            "labeled_count": 2,
            "positive_rate": 0.5,
        },
        "previous_metrics": None,
    }
    monkeypatch.setitem(sys.modules, "train_ranker", mock_tr)

    response = client.post("/admin/ml/train")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) >= {"promoted", "weights_version", "new_metrics", "previous_metrics"}
    assert isinstance(body["promoted"], bool)
    assert isinstance(body["weights_version"], int)


def test_admin_ml_train_no_labeled_data_returns_422(client, monkeypatch):
    """POST /admin/ml/train returns 422 when trainer raises SystemExit (no labeled rows)."""
    import sys
    import types

    mock_tr = types.ModuleType("train_ranker")
    mock_tr.main = lambda artifacts_dir=None: (_ for _ in ()).throw(  # type: ignore[attr-defined]
        SystemExit("No labeled rows found in training data (all labels are None/pending).")
    )
    monkeypatch.setitem(sys.modules, "train_ranker", mock_tr)

    response = client.post("/admin/ml/train")
    assert response.status_code == 422
    assert "No labeled rows" in response.json()["detail"]

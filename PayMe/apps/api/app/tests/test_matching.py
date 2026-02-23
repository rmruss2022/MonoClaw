from sqlalchemy import select

from app.models.entities import MatchResult, MatchRun, Settlement, UserSettlementPreference
from app.tests.conftest import TestingSessionLocal


def _token(client):
    return client.post(
        "/auth/signup",
        json={"username": "matcher", "email": "matcher@example.com", "password": "password123"},
    ).json()["access_token"]


def _onboard(client, token):
    return client.post(
        "/onboarding",
        json={
            "first_name": "M",
            "last_name": "H",
            "state": "NY",
            "dob": "1990-01-01",
            "brands_purchased": ["Amazon"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )


def test_rules_match_run_persists(client):
    token = _token(client)
    _onboard(client, token)
    run = client.post("/match/run", headers={"Authorization": f"Bearer {token}"})
    assert run.status_code == 200
    assert run.json()["results"]
    db = TestingSessionLocal()
    try:
        assert db.scalar(select(MatchRun.id).limit(1)) is not None
        match_result = db.scalar(select(MatchResult).limit(1))
        assert match_result is not None
        reasons = match_result.reasons_json or {}
        assert "confidence_breakdown" in reasons
        assert "rules" in reasons["confidence_breakdown"]
        assert "similarity" in reasons
        assert "payout" in reasons
        assert "urgency" in reasons
        assert "ease" in reasons
    finally:
        db.close()


def test_pinned_ordering(client):
    token = _token(client)
    _onboard(client, token)
    client.post("/match/run", headers={"Authorization": f"Bearer {token}"})
    db = TestingSessionLocal()
    try:
        settlement = db.scalar(select(Settlement))
        assert settlement is not None
        settlement_id = settlement.id
    finally:
        db.close()
    pin = client.post(f"/settlements/{settlement_id}/pin", headers={"Authorization": f"Bearer {token}"})
    assert pin.status_code == 200
    results = client.get("/match/results", headers={"Authorization": f"Bearer {token}"})
    assert results.status_code == 200
    assert results.json()[0]["settlement_id"] == str(settlement_id)
    db = TestingSessionLocal()
    try:
        pref = db.scalar(select(UserSettlementPreference).where(UserSettlementPreference.settlement_id == settlement_id))
        assert pref.pinned is True
    finally:
        db.close()

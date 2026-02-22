from sqlalchemy import select

from app.models.entities import Event, Settlement, UserSettlementPreference
from app.tests.conftest import TestingSessionLocal


def _token(client):
    return client.post(
        "/auth/signup",
        json={"username": "claimer", "email": "claimer@example.com", "password": "password123"},
    ).json()["access_token"]


def _onboard(client, token):
    return client.post(
        "/onboarding",
        json={
            "first_name": "C",
            "last_name": "L",
            "state": "NY",
            "dob": "1990-01-01",
            "brands_purchased": ["Amazon"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )


def test_claim_tracking_lifecycle_and_feedback_events(client):
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

    opened = client.post(f"/settlements/{settlement_id}/claim/opened", headers={"Authorization": f"Bearer {token}"})
    assert opened.status_code == 200

    submitted = client.post(
        f"/settlements/{settlement_id}/claim/submitted",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert submitted.status_code == 200
    assert submitted.json()["claim_status"] == "submitted"

    ongoing = client.get("/claims/ongoing", headers={"Authorization": f"Bearer {token}"})
    assert ongoing.status_code == 200
    assert ongoing.json()
    assert ongoing.json()[0]["claim_status"] == "submitted"

    outcome = client.post(
        f"/settlements/{settlement_id}/claim/outcome",
        json={"outcome": "paid_out"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert outcome.status_code == 200
    assert outcome.json()["claim_status"] == "paid_out"

    results = client.get("/match/results", headers={"Authorization": f"Bearer {token}"})
    assert results.status_code == 200
    assert results.json()[0]["claim_status"] == "paid_out"

    db = TestingSessionLocal()
    try:
        pref = db.scalar(select(UserSettlementPreference).where(UserSettlementPreference.settlement_id == settlement_id))
        assert pref is not None
        assert pref.claim_status == "paid_out"
        assert pref.claim_submitted_at is not None
        assert pref.claim_outcome_at is not None

        event_types = {
            e.type
            for e in db.scalars(
                select(Event).where(Event.type.in_(["claim_form_opened", "claim_submitted", "claim_paid_out"]))
            ).all()
        }
        assert "claim_form_opened" in event_types
        assert "claim_submitted" in event_types
        assert "claim_paid_out" in event_types
    finally:
        db.close()

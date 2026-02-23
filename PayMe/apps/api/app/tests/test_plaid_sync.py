from sqlalchemy import select

from app.models.entities import Event, PlaidTransaction, UserFeature
from app.tests.conftest import TestingSessionLocal


def _token(client):
    return client.post(
        "/auth/signup",
        json={"username": "plaid_user", "email": "plaid@example.com", "password": "password123"},
    ).json()["access_token"]


def test_plaid_sync_inserts_transactions_and_features_idempotent(client, monkeypatch):
    import app.services.ingestion.plaid_sync as _mod
    monkeypatch.setattr(_mod.settings, "mock_plaid", True)
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    first = client.post("/integrations/plaid/sync", headers=headers)
    assert first.status_code == 200
    assert first.json()["inserted_transactions"] >= 1
    second = client.post("/integrations/plaid/sync", headers=headers)
    assert second.status_code == 200
    assert second.json()["inserted_transactions"] == 0

    db = TestingSessionLocal()
    try:
        txns = db.scalars(select(PlaidTransaction)).all()
        features = db.scalars(select(UserFeature).where(UserFeature.source == "plaid")).all()
        events = db.scalars(select(Event).where(Event.type == "plaid_sync_completed")).all()
        assert len(txns) >= 4
        assert len(features) >= 3
        assert len(events) >= 2
    finally:
        db.close()

from sqlalchemy import select

from app.models.entities import GmailEvidence, GmailMessage, UserFeature
from app.tests.conftest import TestingSessionLocal


def _token(client):
    return client.post(
        "/auth/signup",
        json={"username": "gmail", "email": "gmail@example.com", "password": "password123"},
    ).json()["access_token"]


def test_gmail_sync_idempotent(client, monkeypatch):
    import app.services.ingestion.gmail_sync as _mod
    monkeypatch.setattr(_mod.settings, "mock_gmail", True)
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    first = client.post("/integrations/gmail/sync", headers=headers)
    assert first.status_code == 200
    assert first.json()["inserted_messages"] >= 1
    second = client.post("/integrations/gmail/sync", headers=headers)
    assert second.status_code == 200
    assert second.json()["inserted_messages"] == 0
    db = TestingSessionLocal()
    try:
        messages = db.scalars(select(GmailMessage)).all()
        evidence = db.scalars(select(GmailEvidence)).all()
        gmail_features = db.scalars(select(UserFeature).where(UserFeature.source == "gmail")).all()
        assert len(messages) >= 3
        assert len(evidence) >= 2
        assert len(gmail_features) >= 2
    finally:
        db.close()

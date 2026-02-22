from sqlalchemy import select

from app.models.entities import Settlement, User
from app.tests.conftest import TestingSessionLocal


def _token(client):
    return client.post(
        "/auth/signup",
        json={"username": "adminview", "email": "adminview@example.com", "password": "password123"},
    ).json()["access_token"]


def test_admin_endpoints_expose_core_data(client):
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    client.post(
        "/onboarding",
        json={
            "first_name": "Admin",
            "last_name": "View",
            "state": "NY",
            "dob": "1990-01-01",
            "brands_purchased": ["Amazon"],
        },
        headers=headers,
    )
    client.post("/integrations/gmail/sync", headers=headers)
    client.post("/integrations/plaid/sync", headers=headers)
    client.post("/match/run", headers=headers)

    users = client.get("/admin/users?limit=10")
    assert users.status_code == 200
    assert users.json()

    db = TestingSessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == "adminview@example.com"))
        settlement = db.scalar(select(Settlement))
        assert user is not None
        assert settlement is not None
        user_stats = client.get(f"/admin/stats/users/{user.id}")
        assert user_stats.status_code == 200
        assert user_stats.json()["gmail_messages"] >= 1
        settlement_details = client.get(f"/admin/settlements/{settlement.id}")
        assert settlement_details.status_code == 200
    finally:
        db.close()

    overview = client.get("/admin/stats/overview")
    assert overview.status_code == 200
    assert overview.json()["users"] >= 1

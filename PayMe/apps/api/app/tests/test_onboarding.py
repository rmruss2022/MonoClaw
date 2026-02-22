from sqlalchemy import select

from app.models.entities import User, UserFeature
from app.tests.conftest import TestingSessionLocal


def _token(client):
    response = client.post(
        "/auth/signup",
        json={"username": "onboard", "email": "onboard@example.com", "password": "password123"},
    )
    return response.json()["access_token"]


def test_onboarding_writes_profile_and_features(client):
    token = _token(client)
    payload = {
        "first_name": "Matt",
        "last_name": "H",
        "state": "NY",
        "dob": "1990-01-01",
        "gender": "male",
        "brands_purchased": ["Amazon", "Uber"],
        "payout_preference_type": "venmo",
        "payout_preference_value": "@matt",
        "finance_check_frequency": "weekly",
    }
    response = client.post("/onboarding", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["first_name"] == "Matt"
    db = TestingSessionLocal()
    try:
        features = db.scalars(select(UserFeature)).all()
        keys = {f.feature_key for f in features}
        assert "merchant:amazon" in keys
        assert "merchant:uber" in keys
        user = db.scalar(select(User).where(User.email == "onboard@example.com"))
        assert user is not None
        assert user.onboarding_completed_at is not None
    finally:
        db.close()

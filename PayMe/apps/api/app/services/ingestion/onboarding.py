from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.entities import User, UserFeature
from app.schemas.onboarding import OnboardingRequest
from app.services.events.service import emit_event


def upsert_onboarding(db: Session, user: User, payload: OnboardingRequest) -> User:
    user.first_name = payload.first_name
    user.last_name = payload.last_name
    user.state = payload.state
    user.dob = payload.dob
    user.gender = payload.gender
    user.payout_preference_type = payload.payout_preference_type
    user.payout_preference_value = payload.payout_preference_value
    user.finance_check_frequency = payload.finance_check_frequency
    user.onboarding_completed_at = datetime.now(UTC)

    db.execute(delete(UserFeature).where(UserFeature.user_id == user.id, UserFeature.source == "onboarding"))
    now = datetime.now(UTC)
    for brand in payload.brands_purchased:
        db.add(
            UserFeature(
                user_id=user.id,
                feature_key=f"merchant:{brand.lower()}",
                value_json=True,
                confidence=0.6,
                first_seen_at=now,
                last_seen_at=now,
                source="onboarding",
            )
        )
    emit_event(db, "onboarding_completed", user.id, {"brands": payload.brands_purchased})
    db.flush()
    return user

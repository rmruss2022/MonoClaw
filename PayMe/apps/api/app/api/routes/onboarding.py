from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.entities import User
from app.schemas.auth import MeResponse
from app.schemas.onboarding import OnboardingRequest
from app.services.ingestion.onboarding import upsert_onboarding

router = APIRouter(tags=["onboarding"])


@router.post("/onboarding", response_model=MeResponse)
def onboarding_route(
    payload: OnboardingRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    updated = upsert_onboarding(db, user, payload)
    db.commit()
    db.refresh(updated)
    return MeResponse.model_validate(updated)

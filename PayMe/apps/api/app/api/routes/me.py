from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.models.entities import User
from app.schemas.auth import MeResponse

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeResponse)
def me_route(user: User = Depends(get_current_user)):
    return MeResponse.model_validate(user)

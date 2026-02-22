from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.entities import User
from app.schemas.auth import AuthResponse, LoginRequest, MeResponse, SignupRequest
from app.services.auth.service import login, signup

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse)
def signup_route(payload: SignupRequest, db: Session = Depends(get_db)):
    try:
        token = signup(db, payload)
        db.commit()
        return AuthResponse(access_token=token)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/login", response_model=AuthResponse)
def login_route(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        token = login(db, payload)
        db.commit()
        return AuthResponse(access_token=token)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.get("/me", response_model=MeResponse)
def me_route(user: User = Depends(get_current_user)):
    return MeResponse.model_validate(user)

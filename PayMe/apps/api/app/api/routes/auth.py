from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
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
def me_route(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models.entities import GmailOAuthToken, PlaidItem  # noqa: PLC0415

    gmail_connected = (
        db.scalar(
            select(GmailOAuthToken).where(
                GmailOAuthToken.user_id == user.id,
                GmailOAuthToken.revoked_at == None,  # noqa: E711
            )
        )
        is not None
    )
    plaid_item = db.scalar(
        select(PlaidItem).where(
            PlaidItem.user_id == user.id,
            PlaidItem.status == "active",
        )
    )
    plaid_linked = plaid_item is not None
    plaid_institution_name = plaid_item.institution_name if plaid_item else None
    plaid_balance_available_cents = plaid_item.balance_available_cents if plaid_item else None
    plaid_balance_current_cents = plaid_item.balance_current_cents if plaid_item else None
    return MeResponse.model_validate(user).model_copy(
        update={
            "gmail_oauth_connected": gmail_connected,
            "plaid_linked": plaid_linked,
            "plaid_institution_name": plaid_institution_name,
            "plaid_balance_available_cents": plaid_balance_available_cents,
            "plaid_balance_current_cents": plaid_balance_current_cents,
            "role": user.role,
        }
    )

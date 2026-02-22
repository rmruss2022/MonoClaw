from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.entities import User
from app.schemas.auth import LoginRequest, SignupRequest
from app.services.events.service import emit_event


def signup(db: Session, payload: SignupRequest) -> str:
    existing = db.scalar(
        select(User).where(or_(User.email == payload.email, User.username == payload.username))
    )
    if existing:
        raise ValueError("Username or email already exists")
    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.flush()
    emit_event(db, "user_signed_up", user.id, {"username": user.username})
    return create_access_token(str(user.id))


def login(db: Session, payload: LoginRequest) -> str:
    user = db.scalar(
        select(User).where(
            or_(User.email == payload.username_or_email, User.username == payload.username_or_email)
        )
    )
    if not user or not verify_password(payload.password, user.password_hash):
        raise ValueError("Invalid credentials")
    emit_event(db, "user_logged_in", user.id, {})
    return create_access_token(str(user.id))

from datetime import date
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupRequest(BaseModel):
    username: str = Field(min_length=3)
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    username_or_email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    username: str
    email: EmailStr
    first_name: str | None = None
    last_name: str | None = None
    state: str | None = None
    dob: date | None = None
    gmail_synced_at: datetime | None = None
    plaid_synced_at: datetime | None = None
    gmail_oauth_connected: bool = False
    plaid_linked: bool = False
    plaid_institution_name: str | None = None
    plaid_balance_available_cents: int | None = None
    plaid_balance_current_cents: int | None = None
    role: str = "user"

from datetime import date

from pydantic import BaseModel, Field


class OnboardingRequest(BaseModel):
    first_name: str
    last_name: str
    state: str
    dob: date
    gender: str | None = None
    brands_purchased: list[str] = Field(default_factory=list)
    payout_preference_type: str | None = None
    payout_preference_value: str | None = None
    finance_check_frequency: str | None = None

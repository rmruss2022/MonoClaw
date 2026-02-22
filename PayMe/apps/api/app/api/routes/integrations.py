from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.entities import User
from app.services.ingestion.gmail_sync import sync_gmail_mock
from app.services.ingestion.plaid_sync import sync_plaid_mock

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.post("/gmail/sync")
def gmail_sync_route(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    result = sync_gmail_mock(db, user)
    db.commit()
    return result


@router.post("/plaid/sync")
def plaid_sync_route(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    result = sync_plaid_mock(db, user)
    db.commit()
    return result

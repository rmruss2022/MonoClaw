from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.entities import UserSettlementPreference
from app.services.events.service import emit_event


def _get_pref(db: Session, user_id, settlement_id) -> UserSettlementPreference:
    pref = db.scalar(
        select(UserSettlementPreference).where(
            and_(
                UserSettlementPreference.user_id == user_id,
                UserSettlementPreference.settlement_id == settlement_id,
            )
        )
    )
    if not pref:
        pref = UserSettlementPreference(user_id=user_id, settlement_id=settlement_id, pinned=False)
        db.add(pref)
        db.flush()
    return pref


def set_pinned(db: Session, user_id, settlement_id, pinned: bool) -> UserSettlementPreference:
    pref = _get_pref(db, user_id, settlement_id)
    pref.pinned = pinned
    if pinned and pref.pinned_order is None:
        max_order = db.scalar(
            select(func.max(UserSettlementPreference.pinned_order)).where(
                and_(UserSettlementPreference.user_id == user_id, UserSettlementPreference.pinned == True)  # noqa: E712
            )
        )
        pref.pinned_order = (max_order or 0) + 1
    if not pinned:
        pref.pinned_order = None
    emit_event(db, "settlement_pinned" if pinned else "settlement_unpinned", user_id, {"settlement_id": str(settlement_id)})
    db.flush()
    return pref

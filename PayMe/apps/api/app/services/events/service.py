from sqlalchemy.orm import Session

from app.models.entities import Event


def emit_event(db: Session, event_type: str, user_id=None, payload: dict | None = None) -> Event:
    event = Event(type=event_type, user_id=user_id, payload_json=payload or {})
    db.add(event)
    db.flush()
    return event

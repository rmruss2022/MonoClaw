import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.models.entities import GmailEvidence, GmailMessage, User, UserFeature
from app.services.events.service import emit_event

# ---------------------------------------------------------------------------
# Public dispatcher — call this from route handlers.
# ---------------------------------------------------------------------------


def sync_gmail(db: Session, user: User) -> dict:
    """Dispatch to mock or real Gmail sync based on OAuth connection status.
    
    If user has connected Gmail OAuth → use real sync.
    If user has NOT connected Gmail → use mock sync.
    Connected users always use real sync, even when mock mode is enabled.
    """
    # Check if user has a valid Gmail OAuth token.
    from app.models.entities import GmailOAuthToken  # noqa: PLC0415
    token = db.scalar(
        select(GmailOAuthToken).where(
            and_(
                GmailOAuthToken.user_id == user.id,
                GmailOAuthToken.revoked_at.is_(None)
            )
        )
    )

    # Connected user -> real sync regardless of global mock flag.
    if token is not None:
        from app.services.ingestion.gmail_real import sync_gmail_real  # noqa: PLC0415
        return sync_gmail_real(db, user)

    # No connection: allow mock fallback behavior.
    if settings.mock_gmail:
        return sync_gmail_mock(db, user)
    return {"status": "not_connected", "message": "Connect Gmail OAuth first to run real sync."}


BRAND_MAP = {
    "amazon": "merchant:amazon",
    "uber": "merchant:uber",
    "at&t": "merchant:at&t",
    "paramount": "merchant:paramount",
    "walmart": "merchant:walmart",
    "united airlines": "merchant:united_airlines",
    "united air": "merchant:united_airlines",
    "mcdonald": "merchant:mcdonald_s",
    "starbucks": "merchant:starbucks",
    "kfc": "merchant:kfc",
}


def _read_fixture_messages() -> list[dict]:
    fixture = Path("/workspace/fixtures/gmail/sample_messages.json")
    if not fixture.exists():
        fixture = Path(__file__).resolve().parents[5] / "fixtures/gmail/sample_messages.json"
    return json.loads(fixture.read_text(encoding="utf-8"))


def sync_gmail_mock(db: Session, user: User) -> dict:
    emit_event(db, "gmail_sync_started", user.id, {})
    if not settings.mock_gmail:
        emit_event(db, "gmail_sync_failed", user.id, {"reason": "not implemented"})
        return {"status": "not_implemented", "message": "Real Gmail OAuth integration is not implemented yet."}

    messages = _read_fixture_messages()
    inserted = 0
    token_counts: dict[str, int] = {}
    for msg in messages:
        exists = db.scalar(
            select(GmailMessage).where(
                and_(GmailMessage.user_id == user.id, GmailMessage.provider_msg_id == msg["id"])
            )
        )
        if not exists:
            db.add(
                GmailMessage(
                    user_id=user.id,
                    provider_msg_id=msg["id"],
                    internal_date=datetime.fromisoformat(msg["internalDate"].replace("Z", "+00:00")),
                    from_domain=msg.get("from_domain"),
                    subject=msg.get("subject"),
                    snippet=msg.get("snippet"),
                    raw_json=msg,
                )
            )
            inserted += 1
        text = f'{msg.get("subject", "")} {msg.get("snippet", "")}'.lower()
        for token, feature_key in BRAND_MAP.items():
            if token in text:
                token_counts[feature_key] = token_counts.get(feature_key, 0) + 1
        if "prime" in text:
            token_counts["subscription:prime"] = token_counts.get("subscription:prime", 0) + 1
        if "paramount+" in text:
            token_counts["subscription:paramount_plus"] = token_counts.get("subscription:paramount_plus", 0) + 1
        if any(k in text for k in ["casino", "sportsbook", "bet", "gambling"]):
            token_counts["category:gambling"] = token_counts.get("category:gambling", 0) + 1

    now = datetime.now(UTC)
    user.gmail_synced_at = now
    for key, count in token_counts.items():
        evidence = db.scalar(
            select(GmailEvidence).where(
                and_(GmailEvidence.user_id == user.id, GmailEvidence.evidence_type == "merchant", GmailEvidence.key == key)
            )
        )
        confidence = min(0.95, 0.7 + min(0.2, count * 0.05))
        if not evidence:
            evidence = GmailEvidence(
                user_id=user.id,
                evidence_type="merchant",
                key=key,
                first_seen_at=now,
                last_seen_at=now,
                count=count,
                confidence=confidence,
                examples_json=[],
            )
            db.add(evidence)
        else:
            evidence.count = count
            evidence.last_seen_at = now
            evidence.confidence = confidence

        feature = db.scalar(
            select(UserFeature).where(
                and_(UserFeature.user_id == user.id, UserFeature.feature_key == key, UserFeature.source == "gmail")
            )
        )
        if not feature:
            db.add(
                UserFeature(
                    user_id=user.id,
                    feature_key=key,
                    value_json=True,
                    confidence=confidence,
                    first_seen_at=now,
                    last_seen_at=now,
                    source="gmail",
                )
            )
        else:
            feature.confidence = confidence
            feature.last_seen_at = now
            feature.updated_at = now
    emit_event(db, "gmail_sync_completed", user.id, {"inserted_messages": inserted, "feature_count": len(token_counts)})
    db.flush()
    return {"status": "ok", "inserted_messages": inserted, "feature_count": len(token_counts)}

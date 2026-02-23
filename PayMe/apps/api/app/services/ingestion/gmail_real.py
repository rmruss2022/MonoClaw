"""Real Gmail OAuth + incremental sync service (Track 2).

Uses google-auth-oauthlib and google-api-python-client.
If those packages are not installed, all public functions raise ImportError
with a clear message so the caller can surface a 503 to the client.

Security rules:
- Decrypted tokens are NEVER logged.
- All tokens are stored encrypted via crypto.encrypt_token / decrypt_token.
- Events emitted: gmail_oauth_granted, gmail_oauth_revoked,
  gmail_sync_started, gmail_sync_completed, gmail_sync_failed.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_token, encrypt_token
from app.core.settings import settings
from app.models.entities import (
    GmailEvidence,
    GmailMessage,
    GmailOAuthToken,
    User,
    UserFeature,
)
from app.services.events.service import emit_event

logger = logging.getLogger(__name__)

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Re-use the same feature extraction logic as the mock sync.
BRAND_MAP = {
    "amazon": "merchant:amazon",
    "uber": "merchant:uber",
    "at&t": "merchant:at&t",
    "paramount": "merchant:paramount",
    "walmart": "merchant:walmart",
}

_GOOGLE_IMPORT_ERROR: ImportError | None = None

try:
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build as google_build
except ImportError as _exc:
    _GOOGLE_IMPORT_ERROR = _exc


def _require_google_libs() -> None:
    if _GOOGLE_IMPORT_ERROR is not None:
        raise ImportError(
            "Google OAuth libraries are not installed. "
            "Run: pip install google-auth-oauthlib google-api-python-client. "
            f"Original error: {_GOOGLE_IMPORT_ERROR}"
        )


def _require_google_credentials() -> None:
    if not settings.google_client_id or not settings.google_client_secret:
        raise ValueError(
            "Google OAuth credentials are not configured. "
            "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your environment."
        )


def _build_client_config() -> dict[str, Any]:
    return {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uris": [settings.google_redirect_uri],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


# ---------------------------------------------------------------------------
# OAuth flow
# ---------------------------------------------------------------------------


def get_oauth_authorization_url(user_id: str) -> tuple[str, str]:
    """Build the Google OAuth authorization URL.

    Returns (auth_url, state) where state encodes user_id for the callback.
    Raises ValueError if credentials are not configured.
    Raises ImportError if the Google libraries are not installed.
    """
    _require_google_libs()
    _require_google_credentials()

    flow = Flow.from_client_config(
        _build_client_config(),
        scopes=GMAIL_SCOPES,
        redirect_uri=settings.google_redirect_uri,
    )
    # Encode user_id as the state so the callback can look up the user.
    state = user_id
    auth_url, _state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=state,
        prompt="consent",
    )
    return auth_url, _state


def exchange_oauth_code(db: Session, user: User, code: str, state: str) -> dict:
    """Exchange an authorization code for OAuth tokens and persist them.

    Stores encrypted access + refresh tokens in gmail_oauth_tokens (upsert).
    Emits event: gmail_oauth_granted.
    Returns {status: 'ok', email: <gmail address>}.
    """
    _require_google_libs()
    _require_google_credentials()

    flow = Flow.from_client_config(
        _build_client_config(),
        scopes=GMAIL_SCOPES,
        redirect_uri=settings.google_redirect_uri,
        state=state,
    )
    flow.fetch_token(code=code)
    credentials: Credentials = flow.credentials

    # Derive the Gmail address from the token info endpoint.
    gmail_email: str | None = None
    try:
        service = google_build("oauth2", "v2", credentials=credentials)
        userinfo = service.userinfo().get().execute()
        gmail_email = userinfo.get("email")
    except Exception:  # noqa: BLE001
        pass  # Non-fatal — we still store the token.

    access_token_enc = encrypt_token(credentials.token)
    refresh_token_enc = encrypt_token(credentials.refresh_token) if credentials.refresh_token else None
    expiry: datetime | None = credentials.expiry
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    scopes_str = " ".join(credentials.scopes or GMAIL_SCOPES)

    existing = db.scalar(
        select(GmailOAuthToken).where(GmailOAuthToken.user_id == user.id)
    )
    if existing:
        existing.access_token_enc = access_token_enc
        if refresh_token_enc is not None:
            existing.refresh_token_enc = refresh_token_enc
        existing.token_expiry = expiry
        existing.scopes = scopes_str
        existing.revoked_at = None
        existing.granted_at = datetime.now(UTC)
    else:
        db.add(
            GmailOAuthToken(
                user_id=user.id,
                access_token_enc=access_token_enc,
                refresh_token_enc=refresh_token_enc,
                token_expiry=expiry,
                scopes=scopes_str,
                granted_at=datetime.now(UTC),
            )
        )

    emit_event(db, "gmail_oauth_granted", user.id, {"email": gmail_email})
    db.flush()
    return {"status": "ok", "email": gmail_email}


# ---------------------------------------------------------------------------
# Revoke
# ---------------------------------------------------------------------------


def revoke_gmail_access(db: Session, user: User) -> dict:
    """Revoke the user's Gmail OAuth access.

    Calls the Google token revocation endpoint, then marks the
    GmailOAuthToken row as revoked.
    Emits event: gmail_oauth_revoked.
    Returns {status: 'ok'}.
    """
    _require_google_libs()

    token_row = db.scalar(
        select(GmailOAuthToken).where(GmailOAuthToken.user_id == user.id)
    )
    if token_row is None:
        raise ValueError("No Gmail OAuth token found for this user.")

    # Attempt to call Google's revoke endpoint; treat errors as non-fatal.
    try:
        import requests as _requests  # noqa: PLC0415

        access_token = decrypt_token(token_row.access_token_enc)
        _requests.post(
            "https://oauth2.googleapis.com/revoke",
            params={"token": access_token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
    except Exception:  # noqa: BLE001
        logger.warning("Failed to call Google revoke endpoint; marking token revoked locally.")

    token_row.revoked_at = datetime.now(UTC)
    emit_event(db, "gmail_oauth_revoked", user.id, {})
    db.flush()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Incremental sync
# ---------------------------------------------------------------------------


def _build_credentials(token_row: GmailOAuthToken) -> "Credentials":
    """Build a google.oauth2.credentials.Credentials from a stored token row.

    Refreshes the access token if it is expired or within 60 seconds of
    expiring, using the stored refresh token.
    """
    access_token = decrypt_token(token_row.access_token_enc)
    refresh_token = (
        decrypt_token(token_row.refresh_token_enc) if token_row.refresh_token_enc else None
    )
    expiry = token_row.token_expiry
    scopes = token_row.scopes.split() if token_row.scopes else GMAIL_SCOPES
    # google-auth internals compare against naive utcnow(); normalize to naive UTC.
    if expiry and expiry.tzinfo is not None:
        expiry = expiry.astimezone(UTC).replace(tzinfo=None)

    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=scopes,
    )
    if expiry:
        creds.expiry = expiry

    # Avoid creds.expired here because google-auth can compare naive vs aware
    # datetimes depending on provider response shape.
    now = datetime.utcnow()
    effective_expiry = creds.expiry or expiry
    if effective_expiry is not None and effective_expiry.tzinfo is not None:
        effective_expiry = effective_expiry.astimezone(UTC).replace(tzinfo=None)
        creds.expiry = effective_expiry

    needs_refresh = bool(
        refresh_token and (effective_expiry is None or effective_expiry - now < timedelta(seconds=60))
    )
    if needs_refresh:
        creds.refresh(GoogleRequest())
        # Re-normalize after refresh because provider libraries may return aware datetimes.
        if creds.expiry is not None and creds.expiry.tzinfo is not None:
            creds.expiry = creds.expiry.astimezone(UTC).replace(tzinfo=None)

    return creds


def _extract_message_fields(full_msg: dict) -> dict:
    """Extract subject, from_domain, snippet from a Gmail API message object."""
    headers: list[dict] = full_msg.get("payload", {}).get("headers", [])
    header_map = {h["name"].lower(): h["value"] for h in headers}
    subject = header_map.get("subject", "")
    from_header = header_map.get("from", "")
    from_domain: str | None = None
    if "@" in from_header:
        domain_part = from_header.split("@")[-1].strip(">").strip()
        from_domain = domain_part.lower()
    snippet = full_msg.get("snippet", "")
    raw_date_ms = full_msg.get("internalDate", "0")
    internal_date = datetime.fromtimestamp(int(raw_date_ms) / 1000, tz=UTC)
    return {
        "subject": subject,
        "from_domain": from_domain,
        "snippet": snippet,
        "internal_date": internal_date,
    }


def _derive_token_counts(subject: str, snippet: str) -> dict[str, int]:
    """Apply the same token-extraction logic used by the mock sync."""
    token_counts: dict[str, int] = {}
    text = f"{subject} {snippet}".lower()
    for token, feature_key in BRAND_MAP.items():
        if token in text:
            token_counts[feature_key] = token_counts.get(feature_key, 0) + 1
    if "prime" in text:
        token_counts["subscription:prime"] = token_counts.get("subscription:prime", 0) + 1
    if "paramount+" in text:
        token_counts["subscription:paramount_plus"] = token_counts.get("subscription:paramount_plus", 0) + 1
    if any(k in text for k in ["casino", "sportsbook", "bet", "gambling"]):
        token_counts["category:gambling"] = token_counts.get("category:gambling", 0) + 1
    return token_counts


def _upsert_features(db: Session, user: User, token_counts: dict[str, int], now: datetime) -> None:
    """Upsert GmailEvidence + UserFeature rows for the given token_counts."""
    for key, count in token_counts.items():
        confidence = min(0.95, 0.7 + min(0.2, count * 0.05))

        evidence = db.scalar(
            select(GmailEvidence).where(
                and_(
                    GmailEvidence.user_id == user.id,
                    GmailEvidence.evidence_type == "merchant",
                    GmailEvidence.key == key,
                )
            )
        )
        if not evidence:
            db.add(
                GmailEvidence(
                    user_id=user.id,
                    evidence_type="merchant",
                    key=key,
                    first_seen_at=now,
                    last_seen_at=now,
                    count=count,
                    confidence=confidence,
                    examples_json=[],
                )
            )
        else:
            evidence.count = count
            evidence.last_seen_at = now
            evidence.confidence = confidence

        feature = db.scalar(
            select(UserFeature).where(
                and_(
                    UserFeature.user_id == user.id,
                    UserFeature.feature_key == key,
                    UserFeature.source == "gmail",
                )
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


def sync_gmail_real(db: Session, user: User) -> dict:
    """Incremental Gmail sync using the Gmail REST API.

    1. Load GmailOAuthToken for user; raise ValueError if missing.
    2. Decrypt + refresh access token if needed.
    3. If gmail_history_id is set: use history.list for incremental sync.
       Otherwise: use messages.list to fetch the last 90 days.
    4. Upsert GmailMessage rows.
    5. Extract features using BRAND_MAP + subscription keywords.
    6. Upsert UserFeature rows (source='gmail').
    7. Update gmail_history_id + user.gmail_synced_at.
    8. Emit event: gmail_sync_completed.

    Returns {status: 'ok', inserted_messages: N, feature_count: M}.
    """
    _require_google_libs()

    emit_event(db, "gmail_sync_started", user.id, {})

    token_row = db.scalar(
        select(GmailOAuthToken).where(GmailOAuthToken.user_id == user.id)
    )
    if token_row is None:
        emit_event(db, "gmail_sync_failed", user.id, {"reason": "no_oauth_token"})
        raise ValueError(
            "No Gmail OAuth token found for this user. Complete the OAuth flow first."
        )

    if token_row.revoked_at is not None:
        emit_event(db, "gmail_sync_failed", user.id, {"reason": "token_revoked"})
        raise ValueError("Gmail OAuth token has been revoked. Re-authorize to continue.")

    try:
        creds = _build_credentials(token_row)
    except Exception as exc:  # noqa: BLE001
        emit_event(db, "gmail_sync_failed", user.id, {"reason": "credential_refresh_failed"})
        raise ValueError(f"Failed to refresh Gmail credentials: {exc}") from exc

    # Persist any refreshed tokens back to the DB (do not log the raw value).
    if creds.token:
        token_row.access_token_enc = encrypt_token(creds.token)
    if creds.refresh_token:
        token_row.refresh_token_enc = encrypt_token(creds.refresh_token)
    if creds.expiry:
        token_row.token_expiry = (
            creds.expiry if creds.expiry.tzinfo else creds.expiry.replace(tzinfo=UTC)
        )

    try:
        service = google_build("gmail", "v1", credentials=creds)
        user_service = service.users()

        inserted = 0
        all_token_counts: dict[str, int] = {}

        if token_row.gmail_history_id:
            # ---------- incremental path ----------
            history_list_resp = (
                user_service.history()
                .list(
                    userId="me",
                    startHistoryId=token_row.gmail_history_id,
                    historyTypes=["messageAdded"],
                )
                .execute()
            )
            history_items = history_list_resp.get("history", [])
            new_history_id: str | None = history_list_resp.get("historyId")

            msg_ids_seen: set[str] = set()
            for item in history_items:
                for msg_added in item.get("messagesAdded", []):
                    msg_id = msg_added["message"]["id"]
                    if msg_id in msg_ids_seen:
                        continue
                    msg_ids_seen.add(msg_id)
                    full_msg = (
                        user_service.messages()
                        .get(userId="me", id=msg_id, format="metadata",
                             metadataHeaders=["Subject", "From"])
                        .execute()
                    )
                    fields = _extract_message_fields(full_msg)
                    exists = db.scalar(
                        select(GmailMessage).where(
                            and_(
                                GmailMessage.user_id == user.id,
                                GmailMessage.provider_msg_id == msg_id,
                            )
                        )
                    )
                    if not exists:
                        db.add(
                            GmailMessage(
                                user_id=user.id,
                                provider_msg_id=msg_id,
                                internal_date=fields["internal_date"],
                                from_domain=fields["from_domain"],
                                subject=fields["subject"],
                                snippet=fields["snippet"],
                                raw_json=full_msg,
                            )
                        )
                        inserted += 1

                    counts = _derive_token_counts(fields["subject"], fields["snippet"])
                    for k, v in counts.items():
                        all_token_counts[k] = all_token_counts.get(k, 0) + v

            if new_history_id:
                token_row.gmail_history_id = new_history_id

        else:
            # ---------- full (initial) path: last 90 days ----------
            after_epoch = int(
                (datetime.now(UTC) - timedelta(days=90)).timestamp()
            )
            query = f"after:{after_epoch}"
            page_token: str | None = None
            new_history_id = None

            while True:
                list_kwargs: dict[str, Any] = {
                    "userId": "me",
                    "q": query,
                    "maxResults": 500,
                }
                if page_token:
                    list_kwargs["pageToken"] = page_token
                list_resp = user_service.messages().list(**list_kwargs).execute()
                messages_page = list_resp.get("messages", [])

                for msg_ref in messages_page:
                    msg_id = msg_ref["id"]
                    full_msg = (
                        user_service.messages()
                        .get(userId="me", id=msg_id, format="metadata",
                             metadataHeaders=["Subject", "From"])
                        .execute()
                    )
                    if not new_history_id:
                        new_history_id = full_msg.get("historyId")

                    fields = _extract_message_fields(full_msg)
                    exists = db.scalar(
                        select(GmailMessage).where(
                            and_(
                                GmailMessage.user_id == user.id,
                                GmailMessage.provider_msg_id == msg_id,
                            )
                        )
                    )
                    if not exists:
                        db.add(
                            GmailMessage(
                                user_id=user.id,
                                provider_msg_id=msg_id,
                                internal_date=fields["internal_date"],
                                from_domain=fields["from_domain"],
                                subject=fields["subject"],
                                snippet=fields["snippet"],
                                raw_json=full_msg,
                            )
                        )
                        inserted += 1

                    counts = _derive_token_counts(fields["subject"], fields["snippet"])
                    for k, v in counts.items():
                        all_token_counts[k] = all_token_counts.get(k, 0) + v

                page_token = list_resp.get("nextPageToken")
                if not page_token:
                    break

            if new_history_id:
                token_row.gmail_history_id = new_history_id

    except Exception as exc:  # noqa: BLE001
        emit_event(db, "gmail_sync_failed", user.id, {"reason": str(exc)})
        raise ValueError(f"Gmail sync failed: {str(exc)[:500]}") from exc

    now = datetime.now(UTC)
    _upsert_features(db, user, all_token_counts, now)
    user.gmail_synced_at = now

    emit_event(
        db,
        "gmail_sync_completed",
        user.id,
        {"inserted_messages": inserted, "feature_count": len(all_token_counts)},
    )
    db.flush()
    return {"status": "ok", "inserted_messages": inserted, "feature_count": len(all_token_counts)}

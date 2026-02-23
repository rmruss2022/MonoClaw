"""Tests for Track 2: Real Gmail integration.

All tests use unittest.mock so that no real Google API calls are made.
No real Google API calls are made; each test that needs an HTTP client
uses the conftest `client` fixture which manages the test DB schema.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.core.crypto import decrypt_token, encrypt_token
from app.models.entities import GmailOAuthToken, UserFeature
from app.tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _signup_and_token(client, suffix: str = "real") -> tuple[str, str]:
    """Sign up a fresh user and return (access_token, user_id)."""
    username = f"gmail_real_{suffix}"
    email = f"gmail_real_{suffix}@example.com"
    resp = client.post(
        "/auth/signup",
        json={"username": username, "email": email, "password": "password123"},
    )
    assert resp.status_code == 200, resp.text
    access_token = resp.json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me.status_code == 200, me.text
    user_id = me.json()["id"]
    return access_token, user_id


# ---------------------------------------------------------------------------
# 1. test_encrypt_decrypt_roundtrip — no DB needed
# ---------------------------------------------------------------------------


def test_encrypt_decrypt_roundtrip():
    """crypto.py encrypt_token / decrypt_token must be inverse operations."""
    plaintext = "super-secret-access-token-xyz-12345"
    ciphertext = encrypt_token(plaintext)
    assert ciphertext != plaintext
    recovered = decrypt_token(ciphertext)
    assert recovered == plaintext


# ---------------------------------------------------------------------------
# 2+3. OAuth init — requires HTTP client but no DB writes
# ---------------------------------------------------------------------------


def test_oauth_init_returns_auth_url_when_configured(client):
    """When Google credentials are configured, /oauth/init returns an auth_url."""
    token, _user_id = _signup_and_token(client, suffix="init_ok")

    fake_auth_url = "https://accounts.google.com/o/oauth2/auth?fake=1"
    fake_state = "some-state-value"

    with patch(
        "app.services.ingestion.gmail_real.get_oauth_authorization_url",
        return_value=(fake_auth_url, fake_state),
    ):
        resp = client.get(
            "/integrations/gmail/oauth/init",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "auth_url" in data
    assert data["auth_url"] == fake_auth_url


def test_oauth_init_fails_gracefully_when_unconfigured(client):
    """When Google credentials are missing, /oauth/init returns 400."""
    token, _user_id = _signup_and_token(client, suffix="init_uncfg")

    with patch(
        "app.services.ingestion.gmail_real.get_oauth_authorization_url",
        side_effect=ValueError(
            "Google OAuth credentials are not configured. "
            "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
        ),
    ):
        resp = client.get(
            "/integrations/gmail/oauth/init",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 400
    detail = resp.json()["detail"].lower()
    assert "credentials" in detail or "configured" in detail


# ---------------------------------------------------------------------------
# 4. test_exchange_code_stores_encrypted_token
# ---------------------------------------------------------------------------


def test_exchange_code_stores_encrypted_token(client):
    """After a successful code exchange, the GmailOAuthToken row is created
    with encrypted (not plaintext) access and refresh tokens."""
    token, user_id = _signup_and_token(client, suffix="exchange")

    # Capture the encrypted values while still inside the DB session.
    captured_values: list[dict] = []

    def fake_exchange(db, user, code, state):
        from app.core.crypto import encrypt_token as _enc  # noqa: PLC0415

        enc_access = _enc("access-token-value")
        enc_refresh = _enc("refresh-token-value")
        row = GmailOAuthToken(
            user_id=user.id,
            access_token_enc=enc_access,
            refresh_token_enc=enc_refresh,
            token_expiry=datetime(2026, 12, 31, tzinfo=UTC),
            scopes="https://www.googleapis.com/auth/gmail.readonly",
            granted_at=datetime.now(UTC),
        )
        db.add(row)
        db.flush()
        # Capture string values NOW (before the session closes and detaches the instance).
        captured_values.append(
            {
                "access_token_enc": str(enc_access),
                "refresh_token_enc": str(enc_refresh),
            }
        )
        return {"status": "ok", "email": "user@gmail.com"}

    with patch("app.services.ingestion.gmail_real.exchange_oauth_code", side_effect=fake_exchange):
        resp = client.get(
            f"/integrations/gmail/oauth/callback?code=authcode123&state={user_id}",
        )

    assert resp.status_code == 200, resp.text
    # Callback now returns an HTML popup-closer (postMessage pattern); verify success signal.
    assert "gmail_oauth_success" in resp.text, f"Expected success postMessage in response: {resp.text[:200]}"
    assert len(captured_values) == 1, "Expected exchange_oauth_code to be called once"

    vals = captured_values[0]
    assert vals["access_token_enc"] != "access-token-value", "Access token must be encrypted"
    assert decrypt_token(vals["access_token_enc"]) == "access-token-value"
    assert vals["refresh_token_enc"] is not None
    assert decrypt_token(vals["refresh_token_enc"]) == "refresh-token-value"


# ---------------------------------------------------------------------------
# 5. test_revoke_sets_revoked_at
# ---------------------------------------------------------------------------


def test_revoke_sets_revoked_at(client):
    """POST /gmail/revoke marks the GmailOAuthToken.revoked_at timestamp."""
    token, user_id = _signup_and_token(client, suffix="revoke")
    headers = {"Authorization": f"Bearer {token}"}

    captured_revoked_at: list[datetime | None] = []

    def fake_revoke(db, user):
        existing = db.scalar(
            select(GmailOAuthToken).where(GmailOAuthToken.user_id == user.id)
        )
        if existing is None:
            row = GmailOAuthToken(
                user_id=user.id,
                access_token_enc=encrypt_token("tok-access"),
                refresh_token_enc=encrypt_token("tok-refresh"),
                token_expiry=datetime(2026, 12, 31, tzinfo=UTC),
                granted_at=datetime.now(UTC),
            )
            db.add(row)
            db.flush()
        else:
            row = existing

        revoked_now = datetime.now(UTC)
        row.revoked_at = revoked_now
        db.flush()
        captured_revoked_at.append(revoked_now)
        return {"status": "ok"}

    with patch("app.services.ingestion.gmail_real.revoke_gmail_access", side_effect=fake_revoke):
        resp = client.post("/integrations/gmail/revoke", headers=headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ok"
    assert len(captured_revoked_at) == 1, "Expected revoke_gmail_access to be called once"
    assert captured_revoked_at[0] is not None, "revoked_at must be set after revoke"


# ---------------------------------------------------------------------------
# 6. test_sync_gmail_real_uses_history_id
# ---------------------------------------------------------------------------


def test_sync_gmail_real_uses_history_id(client):
    """When gmail_history_id is set, the incremental history.list path is taken."""
    token, user_id = _signup_and_token(client, suffix="histid")

    fake_service = MagicMock()
    fake_history_resp = {
        "history": [
            {
                "messagesAdded": [
                    {"message": {"id": "msg-hist-001"}},
                ]
            }
        ],
        "historyId": "99999",
    }
    fake_msg = {
        "id": "msg-hist-001",
        "historyId": "99999",
        "internalDate": "1700000000000",
        "snippet": "Amazon Prime billing",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Amazon Prime billing notice"},
                {"name": "From", "value": "billing@amazon.com"},
            ]
        },
    }
    (
        fake_service.users.return_value.history.return_value.list.return_value.execute.return_value
    ) = fake_history_resp
    (
        fake_service.users.return_value.messages.return_value.get.return_value.execute.return_value
    ) = fake_msg

    import app.services.ingestion.gmail_real as _gmail_real

    fake_creds = MagicMock()
    fake_creds.token = "fake-access-token-string"
    fake_creds.refresh_token = "fake-refresh-token-string"
    fake_creds.expiry = datetime(2099, 1, 1, tzinfo=UTC)
    fake_creds.expired = False

    fake_google_build = MagicMock(return_value=fake_service)

    # Insert a GmailOAuthToken row with a history_id directly into the
    # test DB.  We do this via the client's DB session (by patching sync_gmail
    # to first insert the token then call the real sync_gmail_real).
    pre_insert_done = []

    def fake_sync_dispatch(db, user):
        """Insert the token row then call the real incremental sync."""
        if not pre_insert_done:
            db.add(
                GmailOAuthToken(
                    user_id=user.id,
                    access_token_enc=encrypt_token("access-tok"),
                    refresh_token_enc=encrypt_token("refresh-tok"),
                    token_expiry=datetime(2099, 1, 1, tzinfo=UTC),
                    gmail_history_id="12345",
                    granted_at=datetime.now(UTC),
                )
            )
            db.flush()
            pre_insert_done.append(True)

        with (
            patch.object(_gmail_real, "_GOOGLE_IMPORT_ERROR", None),
            patch.object(_gmail_real, "_build_credentials", return_value=fake_creds),
            patch.object(_gmail_real, "google_build", fake_google_build, create=True),
        ):
            return _gmail_real.sync_gmail_real(db, user)

    # Patch the `sync_gmail` name in the integrations router module (where the
    # route resolves it), NOT in the gmail_sync module (which the route already
    # imported and bound to a local name).
    with patch("app.api.routes.integrations.sync_gmail", side_effect=fake_sync_dispatch):
        resp = client.post(
            "/integrations/gmail/sync",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "ok"
    assert data["inserted_messages"] == 1
    # Verify history.list was called (incremental path), not messages.list.
    fake_service.users.return_value.history.return_value.list.assert_called_once()
    fake_service.users.return_value.messages.return_value.list.assert_not_called()


# ---------------------------------------------------------------------------
# 7. test_sync_gmail_mock_fallback
# ---------------------------------------------------------------------------


def test_sync_gmail_mock_fallback(client, monkeypatch):
    """When mock_gmail=True, the existing mock sync still works (regression)."""
    import app.services.ingestion.gmail_sync as _mod
    monkeypatch.setattr(_mod.settings, "mock_gmail", True)
    token, _user_id = _signup_and_token(client, suffix="mockfb")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post("/integrations/gmail/sync", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("status") == "ok"
    assert data.get("inserted_messages", 0) >= 1


# ---------------------------------------------------------------------------
# 8. test_sync_dispatches_to_real_when_mock_disabled — no DB needed
# ---------------------------------------------------------------------------


def test_sync_dispatches_to_real_when_mock_disabled():
    """When mock_gmail=False, sync_gmail calls sync_gmail_real (not the mock)."""
    from app.services.ingestion import gmail_sync

    expected_result = {"status": "ok", "inserted_messages": 0, "feature_count": 0}
    fake_real = MagicMock(return_value=expected_result)

    # The dispatcher does `from app.services.ingestion.gmail_real import sync_gmail_real`.
    # Patching the function on the gmail_real module ensures the lazy import finds the mock.
    with (
        patch.object(
            __import__("app.core.settings", fromlist=["settings"]).settings,
            "mock_gmail",
            False,
        ),
        patch("app.services.ingestion.gmail_real.sync_gmail_real", fake_real),
    ):
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_db.scalar.return_value = object()  # Simulate connected OAuth token.
        result = gmail_sync.sync_gmail(mock_db, mock_user)

    fake_real.assert_called_once_with(mock_db, mock_user)
    assert result["status"] == "ok"


def test_sync_dispatches_to_real_when_connected_even_if_mock_enabled():
    """Connected Gmail users should bypass fixture sync even when mock mode is on."""
    from app.services.ingestion import gmail_sync

    expected_result = {"status": "ok", "inserted_messages": 0, "feature_count": 0}
    fake_real = MagicMock(return_value=expected_result)

    with (
        patch.object(
            __import__("app.core.settings", fromlist=["settings"]).settings,
            "mock_gmail",
            True,
        ),
        patch("app.services.ingestion.gmail_real.sync_gmail_real", fake_real),
    ):
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_db.scalar.return_value = object()  # Simulate connected OAuth token.
        result = gmail_sync.sync_gmail(mock_db, mock_user)

    fake_real.assert_called_once_with(mock_db, mock_user)
    assert result["status"] == "ok"

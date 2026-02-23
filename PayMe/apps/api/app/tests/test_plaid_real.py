"""Tests for Track 3: Real Plaid integration.

All tests mock the plaid-python SDK — no real API calls are made.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.models.entities import Event, PlaidItem, PlaidTransaction, UserFeature
from app.tests.conftest import TestingSessionLocal

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PLAID_MODULE = "app.services.ingestion.plaid_real"


def _signup_and_token(client, username: str = "plaid_real_user"):
    resp = client.post(
        "/auth/signup",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "password123",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _stub_cls():
    return MagicMock(return_value=MagicMock())


def _plaid_patches(mock_client: MagicMock):
    """Context managers that fully mock the Plaid SDK for a given mock_client."""
    sc = _stub_cls()
    return [
        patch(f"{_PLAID_MODULE}.PLAID_AVAILABLE", True),
        patch(f"{_PLAID_MODULE}._build_client", return_value=mock_client),
        patch(f"{_PLAID_MODULE}.LinkTokenCreateRequest", sc),
        patch(f"{_PLAID_MODULE}.LinkTokenCreateRequestUser", sc),
        patch(f"{_PLAID_MODULE}.Products", sc),
        patch(f"{_PLAID_MODULE}.CountryCode", sc),
        patch(f"{_PLAID_MODULE}.ItemPublicTokenExchangeRequest", sc),
        patch(f"{_PLAID_MODULE}.ItemRemoveRequest", sc),
        patch(f"{_PLAID_MODULE}.TransactionsSyncRequest", sc),
        patch("app.core.settings.settings.plaid_client_id", "test_client_id"),
        patch("app.core.settings.settings.plaid_secret", "test_secret"),
    ]


def _apply_patches(patches):
    """Enter a list of context managers and return a cleanup list."""
    entered = []
    for p in patches:
        entered.append(p.__enter__())
    return patches  # caller must call __exit__ on each


def _seed_plaid_item(
    client,
    token: str,
    mock_client: MagicMock,
    patches: list,
    institution_name: str = "Test Bank",
):
    """Create a PlaidItem via the /plaid/exchange endpoint (using mocked Plaid SDK)."""
    mock_exchange_response = MagicMock()
    mock_exchange_response.__getitem__ = lambda self, key: {
        "access_token": "access-sandbox-abc",
        "item_id": "item-test-123",
    }[key]
    mock_client.item_public_token_exchange.return_value = mock_exchange_response

    for p in patches:
        p.__enter__()

    resp = client.post(
        "/integrations/plaid/exchange",
        json={
            "public_token": "public-sandbox-xyz",
            "institution_id": "ins_1",
            "institution_name": institution_name,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 200, f"exchange failed: {resp.text}"

    for p in reversed(patches):
        p.__exit__(None, None, None)


# ---------------------------------------------------------------------------
# Test: link token fails gracefully when credentials are not configured
# ---------------------------------------------------------------------------


def test_link_token_fails_gracefully_when_unconfigured(client):
    """When plaid_client_id is empty the endpoint returns 400."""
    token = _signup_and_token(client, "plaid_link_user")

    with (
        patch(f"{_PLAID_MODULE}.PLAID_AVAILABLE", True),
        patch("app.core.settings.settings.plaid_client_id", ""),
        patch("app.core.settings.settings.plaid_secret", ""),
    ):
        resp = client.post("/integrations/plaid/link-token", headers=_auth(token))

    assert resp.status_code == 400
    detail = resp.json()["detail"].lower()
    assert "credentials" in detail or "configured" in detail


# ---------------------------------------------------------------------------
# Test: exchange stores an encrypted access token
# ---------------------------------------------------------------------------


def test_exchange_stores_encrypted_access_token(client):
    """After exchange, PlaidItem row has an encrypted token that decrypts to the original."""
    token = _signup_and_token(client, "plaid_exchange_user")

    mock_exchange_response = MagicMock()
    mock_exchange_response.__getitem__ = lambda self, key: {
        "access_token": "access-sandbox-abc123",
        "item_id": "item-abc123",
    }[key]

    mock_client = MagicMock()
    mock_client.item_public_token_exchange.return_value = mock_exchange_response

    sc = _stub_cls()
    with (
        patch(f"{_PLAID_MODULE}.PLAID_AVAILABLE", True),
        patch(f"{_PLAID_MODULE}._build_client", return_value=mock_client),
        patch(f"{_PLAID_MODULE}.ItemPublicTokenExchangeRequest", sc),
        patch("app.core.settings.settings.plaid_client_id", "test_client_id"),
        patch("app.core.settings.settings.plaid_secret", "test_secret"),
    ):
        resp = client.post(
            "/integrations/plaid/exchange",
            json={
                "public_token": "public-sandbox-xyz",
                "institution_id": "ins_1",
                "institution_name": "Test Bank",
            },
            headers=_auth(token),
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ok"
    assert resp.json()["institution_name"] == "Test Bank"

    db = TestingSessionLocal()
    try:
        items = db.scalars(select(PlaidItem)).all()
        assert len(items) == 1
        item = items[0]
        assert item.item_id == "item-abc123"
        # Stored token must not be plaintext.
        assert item.access_token_enc != "access-sandbox-abc123"
        assert item.access_token_enc != ""
        # Decryption must recover the original.
        from app.core.crypto import decrypt_token

        assert decrypt_token(item.access_token_enc) == "access-sandbox-abc123"
        events = db.scalars(select(Event).where(Event.type == "plaid_item_linked")).all()
        assert len(events) >= 1
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test: sync uses cursor for incremental pulls
# ---------------------------------------------------------------------------


def test_sync_uses_cursor_for_incremental(client):
    """After two syncs, the cursor stored on PlaidItem reflects the second response."""
    token = _signup_and_token(client, "plaid_cursor_user")

    first_txn = {
        "transaction_id": "txn_first_001",
        "date": date(2024, 1, 10),
        "merchant_name": "Netflix",
        "name": "Netflix",
        "amount": 15.99,
        "personal_finance_category": {"primary": "ENTERTAINMENT"},
        "is_subscription": True,
        "recurring_transaction_id": "recur_001",
    }
    second_txn = {
        "transaction_id": "txn_second_001",
        "date": date(2024, 2, 1),
        "merchant_name": "Spotify",
        "name": "Spotify",
        "amount": 9.99,
        "personal_finance_category": {"primary": "ENTERTAINMENT"},
        "is_subscription": True,
        "recurring_transaction_id": "recur_002",
    }

    call_count = [0]

    def fake_transactions_sync(request):
        call_count[0] += 1
        mock_resp = MagicMock()
        if call_count[0] == 1:
            mock_resp.__getitem__ = lambda self, key: {
                "added": [first_txn],
                "modified": [],
                "removed": [],
                "next_cursor": "cursor_after_first",
                "has_more": False,
            }[key]
        else:
            mock_resp.__getitem__ = lambda self, key: {
                "added": [second_txn],
                "modified": [],
                "removed": [],
                "next_cursor": "cursor_after_second",
                "has_more": False,
            }[key]
        return mock_resp

    mock_exchange_response = MagicMock()
    mock_exchange_response.__getitem__ = lambda self, key: {
        "access_token": "access-sandbox-cursor",
        "item_id": "item-cursor-123",
    }[key]

    mock_client = MagicMock()
    mock_client.item_public_token_exchange.return_value = mock_exchange_response
    mock_client.transactions_sync.side_effect = fake_transactions_sync

    sc = _stub_cls()
    with (
        patch(f"{_PLAID_MODULE}.PLAID_AVAILABLE", True),
        patch(f"{_PLAID_MODULE}._build_client", return_value=mock_client),
        patch(f"{_PLAID_MODULE}.ItemPublicTokenExchangeRequest", sc),
        patch(f"{_PLAID_MODULE}.TransactionsSyncRequest", sc),
        patch(f"{_PLAID_MODULE}.decrypt_token", return_value="access-sandbox-cursor"),
        patch("app.core.settings.settings.plaid_client_id", "test_client_id"),
        patch("app.core.settings.settings.plaid_secret", "test_secret"),
        patch("app.core.settings.settings.mock_plaid", False),
    ):
        # Create the PlaidItem via the exchange endpoint.
        exch_resp = client.post(
            "/integrations/plaid/exchange",
            json={"public_token": "public-sandbox-xyz", "institution_id": "ins_1", "institution_name": "Bank"},
            headers=_auth(token),
        )
        assert exch_resp.status_code == 200, exch_resp.text

        resp1 = client.post("/integrations/plaid/sync", headers=_auth(token))
        assert resp1.status_code == 200, resp1.text

        resp2 = client.post("/integrations/plaid/sync", headers=_auth(token))
        assert resp2.status_code == 200, resp2.text

    assert call_count[0] == 2

    db = TestingSessionLocal()
    try:
        item = db.scalars(select(PlaidItem)).first()
        assert item is not None
        assert item.cursor == "cursor_after_second"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test: reauth required error handling
# ---------------------------------------------------------------------------


def test_sync_handles_reauth_required(client):
    """When Plaid raises ITEM_LOGIN_REQUIRED, item.status becomes 'requires_reauth'."""
    token = _signup_and_token(client, "plaid_reauth_user")

    mock_exchange_response = MagicMock()
    mock_exchange_response.__getitem__ = lambda self, key: {
        "access_token": "access-sandbox-reauth",
        "item_id": "item-reauth-123",
    }[key]

    mock_client = MagicMock()
    mock_client.item_public_token_exchange.return_value = mock_exchange_response
    mock_client.transactions_sync.side_effect = Exception(
        "ApiException: ITEM_LOGIN_REQUIRED — credentials expired"
    )

    sc = _stub_cls()
    with (
        patch(f"{_PLAID_MODULE}.PLAID_AVAILABLE", True),
        patch(f"{_PLAID_MODULE}._build_client", return_value=mock_client),
        patch(f"{_PLAID_MODULE}.ItemPublicTokenExchangeRequest", sc),
        patch(f"{_PLAID_MODULE}.TransactionsSyncRequest", sc),
        patch(f"{_PLAID_MODULE}.decrypt_token", return_value="access-sandbox-reauth"),
        patch("app.core.settings.settings.plaid_client_id", "test_client_id"),
        patch("app.core.settings.settings.plaid_secret", "test_secret"),
        patch("app.core.settings.settings.mock_plaid", False),
    ):
        exch_resp = client.post(
            "/integrations/plaid/exchange",
            json={"public_token": "public-sandbox-xyz"},
            headers=_auth(token),
        )
        assert exch_resp.status_code == 200, exch_resp.text

        resp = client.post("/integrations/plaid/sync", headers=_auth(token))
        # ValueError is re-raised → FastAPI returns 500 (unhandled) or 400.
        assert resp.status_code in (400, 500), resp.text

    db = TestingSessionLocal()
    try:
        item = db.scalars(select(PlaidItem)).first()
        assert item is not None
        assert item.status == "requires_reauth"
        events = db.scalars(select(Event).where(Event.type == "plaid_reauth_required")).all()
        assert len(events) >= 1
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test: disconnect sets revoked_at
# ---------------------------------------------------------------------------


def test_disconnect_sets_revoked_at(client):
    """After disconnect, PlaidItem.revoked_at is set and status becomes 'disconnected'."""
    token = _signup_and_token(client, "plaid_disconnect_user")

    mock_exchange_response = MagicMock()
    mock_exchange_response.__getitem__ = lambda self, key: {
        "access_token": "access-sandbox-disc",
        "item_id": "item-disc-123",
    }[key]

    mock_client = MagicMock()
    mock_client.item_public_token_exchange.return_value = mock_exchange_response
    mock_client.item_remove.return_value = MagicMock()

    sc = _stub_cls()
    with (
        patch(f"{_PLAID_MODULE}.PLAID_AVAILABLE", True),
        patch(f"{_PLAID_MODULE}._build_client", return_value=mock_client),
        patch(f"{_PLAID_MODULE}.ItemPublicTokenExchangeRequest", sc),
        patch(f"{_PLAID_MODULE}.ItemRemoveRequest", sc),
        patch(f"{_PLAID_MODULE}.decrypt_token", return_value="access-sandbox-disc"),
        patch("app.core.settings.settings.plaid_client_id", "test_client_id"),
        patch("app.core.settings.settings.plaid_secret", "test_secret"),
    ):
        exch_resp = client.post(
            "/integrations/plaid/exchange",
            json={"public_token": "public-sandbox-xyz"},
            headers=_auth(token),
        )
        assert exch_resp.status_code == 200, exch_resp.text

        resp = client.post("/integrations/plaid/disconnect", headers=_auth(token))
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "ok"

    db = TestingSessionLocal()
    try:
        item = db.scalars(select(PlaidItem)).first()
        assert item is not None
        assert item.status == "disconnected"
        assert item.revoked_at is not None
        events = db.scalars(select(Event).where(Event.type == "plaid_item_disconnected")).all()
        assert len(events) >= 1
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test: mock fallback regression
# ---------------------------------------------------------------------------


def test_sync_mock_fallback(client, monkeypatch):
    """When mock_plaid=True the existing mock sync works without any Plaid credentials."""
    import app.services.ingestion.plaid_sync as _mod
    monkeypatch.setattr(_mod.settings, "mock_plaid", True)
    token = _signup_and_token(client, "plaid_mock_fallback_user")

    resp = client.post("/integrations/plaid/sync", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "ok"
    assert data["inserted_transactions"] >= 1

    db = TestingSessionLocal()
    try:
        txns = db.scalars(select(PlaidTransaction)).all()
        assert len(txns) >= 1
        events = db.scalars(select(Event).where(Event.type == "plaid_sync_completed")).all()
        assert len(events) >= 1
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test: dispatcher routes to real sync when mock_plaid=False
# ---------------------------------------------------------------------------


def test_sync_dispatches_to_real_when_mock_disabled():
    """When mock_plaid=False and user is connected, sync_plaid uses real sync."""
    from app.services.ingestion import plaid_sync

    expected_result = {"status": "ok", "inserted_transactions": 0, "feature_count": 0}
    fake_real = MagicMock(return_value=expected_result)

    with (
        patch("app.core.settings.settings.mock_plaid", False),
        patch(f"{_PLAID_MODULE}.sync_plaid_real", fake_real),
    ):
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_db.scalar.return_value = object()  # Simulate an active PlaidItem.
        result = plaid_sync.sync_plaid(mock_db, mock_user)

    fake_real.assert_called_once_with(mock_db, mock_user)
    assert result["status"] == "ok"


def test_sync_dispatches_to_real_when_connected_even_if_mock_enabled():
    """Connected Plaid users should bypass fixture sync even when mock mode is on."""
    from app.services.ingestion import plaid_sync

    expected_result = {"status": "ok", "inserted_transactions": 0, "feature_count": 0}
    fake_real = MagicMock(return_value=expected_result)

    with (
        patch("app.core.settings.settings.mock_plaid", True),
        patch(f"{_PLAID_MODULE}.sync_plaid_real", fake_real),
    ):
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_db.scalar.return_value = object()  # Simulate an active PlaidItem.
        result = plaid_sync.sync_plaid(mock_db, mock_user)

    fake_real.assert_called_once_with(mock_db, mock_user)
    assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# Test: feature extraction from transactions
# ---------------------------------------------------------------------------


def test_feature_extraction_from_transactions(client):
    """Merchant, category, and subscription features are derived correctly."""
    token = _signup_and_token(client, "plaid_feature_user")

    transactions = [
        {
            "transaction_id": "txn_feat_001",
            "date": date(2024, 3, 1),
            "merchant_name": "Walmart",
            "name": "Walmart Supercenter",
            "amount": 52.34,
            "personal_finance_category": {"primary": "FOOD_AND_DRINK"},
            "is_subscription": False,
            "recurring_transaction_id": None,
        },
        {
            "transaction_id": "txn_feat_002",
            "date": date(2024, 3, 5),
            "merchant_name": "Walmart",
            "name": "Walmart Neighborhood Market",
            "amount": 30.00,
            "personal_finance_category": {"primary": "FOOD_AND_DRINK"},
            "is_subscription": False,
            "recurring_transaction_id": None,
        },
        {
            "transaction_id": "txn_feat_003",
            "date": date(2024, 3, 10),
            "merchant_name": "Hulu",
            "name": "Hulu",
            "amount": 17.99,
            "personal_finance_category": {"primary": "ENTERTAINMENT"},
            "is_subscription": True,
            "recurring_transaction_id": "recur_hulu",
        },
    ]

    sync_response = MagicMock()
    sync_response.__getitem__ = lambda self, key: {
        "added": transactions,
        "modified": [],
        "removed": [],
        "next_cursor": "cursor_feat_v1",
        "has_more": False,
    }[key]

    mock_exchange_response = MagicMock()
    mock_exchange_response.__getitem__ = lambda self, key: {
        "access_token": "access-sandbox-feat",
        "item_id": "item-feat-123",
    }[key]

    mock_client = MagicMock()
    mock_client.item_public_token_exchange.return_value = mock_exchange_response
    mock_client.transactions_sync.return_value = sync_response

    sc = _stub_cls()
    with (
        patch(f"{_PLAID_MODULE}.PLAID_AVAILABLE", True),
        patch(f"{_PLAID_MODULE}._build_client", return_value=mock_client),
        patch(f"{_PLAID_MODULE}.ItemPublicTokenExchangeRequest", sc),
        patch(f"{_PLAID_MODULE}.TransactionsSyncRequest", sc),
        patch(f"{_PLAID_MODULE}.decrypt_token", return_value="access-sandbox-feat"),
        patch("app.core.settings.settings.plaid_client_id", "test_client_id"),
        patch("app.core.settings.settings.plaid_secret", "test_secret"),
        patch("app.core.settings.settings.mock_plaid", False),
    ):
        exch_resp = client.post(
            "/integrations/plaid/exchange",
            json={"public_token": "public-sandbox-xyz"},
            headers=_auth(token),
        )
        assert exch_resp.status_code == 200, exch_resp.text

        resp = client.post("/integrations/plaid/sync", headers=_auth(token))
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["inserted_transactions"] == 3

    db = TestingSessionLocal()
    try:
        features = db.scalars(select(UserFeature).where(UserFeature.source == "plaid")).all()
        feature_keys = {f.feature_key for f in features}

        assert "merchant:walmart" in feature_keys
        assert "category:food_and_drink" in feature_keys
        assert "merchant:hulu" in feature_keys
        assert "subscription:active" in feature_keys

        walmart_feature = next(f for f in features if f.feature_key == "merchant:walmart")
        assert walmart_feature.confidence > 0.75
        assert walmart_feature.value_json["count"] == 2
    finally:
        db.close()

"""Real Plaid integration service.

Uses conditional imports so the app still starts if plaid-python is not installed.
All Plaid SDK class instantiations are guarded so they only execute when the
package is actually available.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_token, encrypt_token
from app.core.settings import settings
from app.models.entities import PlaidItem, PlaidTransaction, User, UserFeature
from app.services.events.service import emit_event

try:
    import plaid  # noqa: F401
    from plaid.api import plaid_api
    from plaid.api_client import ApiClient
    from plaid.configuration import Configuration
    from plaid.model.country_code import CountryCode
    from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
    from plaid.model.item_remove_request import ItemRemoveRequest
    from plaid.model.link_token_create_request import LinkTokenCreateRequest
    from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
    from plaid.model.products import Products
    from plaid.model.transactions_sync_request import TransactionsSyncRequest

    PLAID_AVAILABLE = True
except ImportError:
    # Stub names so the module body parses cleanly.  Actual usage is always
    # gated by the `if not PLAID_AVAILABLE` guard at the top of each function.
    plaid_api = None  # type: ignore[assignment]
    ApiClient = None  # type: ignore[assignment]
    Configuration = None  # type: ignore[assignment]
    CountryCode = None  # type: ignore[assignment]
    ItemPublicTokenExchangeRequest = None  # type: ignore[assignment]
    ItemRemoveRequest = None  # type: ignore[assignment]
    LinkTokenCreateRequest = None  # type: ignore[assignment]
    LinkTokenCreateRequestUser = None  # type: ignore[assignment]
    Products = None  # type: ignore[assignment]
    TransactionsSyncRequest = None  # type: ignore[assignment]
    PLAID_AVAILABLE = False

# Sentinel error code used by Plaid when re-authentication is required.
_ITEM_LOGIN_REQUIRED = "ITEM_LOGIN_REQUIRED"

# Map plaid_env string to the corresponding Plaid API host URL.
_ENV_MAP: dict[str, str] = {
    "sandbox": "https://sandbox.plaid.com",
    "development": "https://development.plaid.com",
    "production": "https://production.plaid.com",
}


def _build_client():
    """Build and return a configured Plaid API client."""
    host = _ENV_MAP.get(settings.plaid_env, "https://sandbox.plaid.com")
    configuration = Configuration(
        host=host,
        api_key={
            "clientId": settings.plaid_client_id,
            "secret": settings.plaid_secret,
        },
    )
    api_client = ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)


def _normalize_token(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _make_json_safe(obj):
    """Recursively convert a dict/list to be JSON-serializable.

    Converts date/datetime objects to ISO 8601 strings so that the value can
    be stored in a PostgreSQL JSON column without a serialization error.
    """
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_json_safe(v) for v in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "isoformat"):  # datetime.date and similar
        return obj.isoformat()
    return obj


def _require_credentials() -> None:
    """Raise ValueError if Plaid credentials are not configured."""
    if not settings.plaid_client_id or not settings.plaid_secret:
        raise ValueError(
            "Plaid credentials not configured. "
            "Set PLAID_CLIENT_ID and PLAID_SECRET environment variables."
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_link_token(user_id: str) -> dict:
    """Create a Plaid Link token for the given user.

    Returns {link_token: "...", expiration: "..."}.
    Raises ValueError if plaid-python is not installed or credentials are missing.
    """
    if not PLAID_AVAILABLE:
        raise ValueError("plaid-python package not installed")
    _require_credentials()

    client = _build_client()
    request = LinkTokenCreateRequest(
        products=[Products("transactions")],
        client_name="PayMe",
        country_codes=[CountryCode("US")],
        language="en",
        user=LinkTokenCreateRequestUser(client_user_id=str(user_id)),
    )
    response = client.link_token_create(request)
    return {
        "link_token": response["link_token"],
        "expiration": response["expiration"],
    }


def exchange_public_token(
    db: Session,
    user: User,
    public_token: str,
    institution_id: str | None,
    institution_name: str | None,
) -> dict:
    """Exchange a Plaid public token for a persistent access token.

    Upserts a PlaidItem for the user (one per user — updates if already exists).
    Access token is encrypted before storage.
    Emits event: plaid_item_linked.
    Returns {status: 'ok', institution_name: ...}.
    """
    if not PLAID_AVAILABLE:
        raise ValueError("plaid-python package not installed")
    _require_credentials()

    client = _build_client()
    exchange_request = ItemPublicTokenExchangeRequest(public_token=public_token)
    exchange_response = client.item_public_token_exchange(exchange_request)

    access_token: str = exchange_response["access_token"]
    item_id: str = exchange_response["item_id"]

    # Encrypt before storing — never persist plaintext.
    access_token_enc = encrypt_token(access_token)

    now = datetime.now(UTC)

    existing = db.scalar(select(PlaidItem).where(PlaidItem.user_id == user.id))
    if existing:
        existing.item_id = item_id
        existing.access_token_enc = access_token_enc
        existing.institution_id = institution_id
        existing.institution_name = institution_name
        existing.status = "active"
        existing.revoked_at = None
        existing.cursor = None  # Reset cursor so next sync is a full re-sync.
        existing.linked_at = now
    else:
        db.add(
            PlaidItem(
                user_id=user.id,
                item_id=item_id,
                access_token_enc=access_token_enc,
                institution_id=institution_id,
                institution_name=institution_name,
                status="active",
                linked_at=now,
            )
        )

    emit_event(
        db,
        "plaid_item_linked",
        user.id,
        {"institution_id": institution_id, "institution_name": institution_name},
    )
    db.flush()
    return {"status": "ok", "institution_name": institution_name}


def disconnect_item(db: Session, user: User) -> dict:
    """Disconnect the user's Plaid item.

    1. Calls Plaid /item/remove.
    2. Sets plaid_items.status = 'disconnected', revoked_at = now.
    3. Emits event: plaid_item_disconnected.
    """
    if not PLAID_AVAILABLE:
        raise ValueError("plaid-python package not installed")

    item = db.scalar(select(PlaidItem).where(PlaidItem.user_id == user.id))
    if not item or item.status == "disconnected":
        raise ValueError("No active Plaid item found for this user.")

    access_token = decrypt_token(item.access_token_enc)

    client = _build_client()
    remove_request = ItemRemoveRequest(access_token=access_token)
    # Best-effort — even if Plaid returns an error we still mark as disconnected.
    try:
        client.item_remove(remove_request)
    except Exception:  # noqa: BLE001
        pass

    now = datetime.now(UTC)
    item.status = "disconnected"
    item.revoked_at = now

    emit_event(db, "plaid_item_disconnected", user.id, {"item_id": item.item_id})
    db.flush()
    return {"status": "ok"}


def sync_plaid_real(db: Session, user: User) -> dict:
    """Incremental transaction sync using the Plaid Transactions Sync API.

    Steps:
    1. Load PlaidItem for user; raise ValueError if missing or disconnected.
    2. Decrypt access token.
    3. Call /transactions/sync with stored cursor (None = initial full sync).
    4. Process added / modified / removed transactions.
    5. Upsert PlaidTransaction rows.
    6. Derive features (merchant:X, category:X, subscription:active).
    7. Upsert UserFeature rows (source='plaid').
    8. Update PlaidItem.cursor and user.plaid_synced_at.
    9. Handle ITEM_LOGIN_REQUIRED: set status = 'requires_reauth', emit event.
    10. Emit event: plaid_sync_completed.
    Returns {status: 'ok', inserted_transactions: N, feature_count: M}.
    """
    if not PLAID_AVAILABLE:
        raise ValueError("plaid-python package not installed")

    emit_event(db, "plaid_sync_started", user.id, {})

    item = db.scalar(select(PlaidItem).where(PlaidItem.user_id == user.id))
    if not item:
        emit_event(db, "plaid_sync_failed", user.id, {"reason": "no_plaid_item"})
        raise ValueError("No Plaid item found for this user. Please link a bank account first.")
    if item.status == "disconnected":
        emit_event(db, "plaid_sync_failed", user.id, {"reason": "disconnected"})
        raise ValueError("Plaid item is disconnected. Please re-link your bank account.")

    access_token = decrypt_token(item.access_token_enc)
    client = _build_client()

    inserted = 0
    feature_counts: dict[str, int] = {}
    cursor = item.cursor  # None on first call triggers full historical pull.
    has_more = True

    try:
        while has_more:
            kwargs: dict = {"access_token": access_token}
            if cursor is not None:
                kwargs["cursor"] = cursor
            sync_request = TransactionsSyncRequest(**kwargs)
            response = client.transactions_sync(sync_request)

            added = response.added
            modified = response.modified
            removed = response.removed
            has_more = response.has_more
            cursor = response.next_cursor

            # Process added transactions.
            for txn in added:
                txn_id = txn.transaction_id
                existing_txn = db.scalar(
                    select(PlaidTransaction).where(
                        and_(
                            PlaidTransaction.user_id == user.id,
                            PlaidTransaction.provider_txn_id == txn_id,
                        )
                    )
                )
                date_val = getattr(txn, "date", None) or getattr(txn, "authorized_date", None)
                if hasattr(date_val, "year"):  # datetime.date object
                    posted_at = datetime(
                        date_val.year, date_val.month, date_val.day, tzinfo=UTC
                    )
                elif isinstance(date_val, str):
                    posted_at = datetime.fromisoformat(date_val.replace("Z", "+00:00"))
                else:
                    posted_at = datetime.now(UTC)

                amount_cents = int(round(float(getattr(txn, "amount", 0)) * 100))
                merchant_name = getattr(txn, "merchant_name", None) or getattr(txn, "name", None)
                category_raw = getattr(txn, "personal_finance_category", {})
                if category_raw and hasattr(category_raw, "primary"):
                    category = category_raw.primary or getattr(category_raw, "detailed", None)
                else:
                    category = getattr(txn, "category", None)
                    if isinstance(category, list) and category:
                        category = category[0]
                is_subscription = bool(
                    getattr(txn, "recurring_transaction_id", None) or getattr(txn, "is_subscription", False)
                )

                if not existing_txn:
                    db.add(
                        PlaidTransaction(
                            user_id=user.id,
                            provider_txn_id=txn_id,
                            posted_at=posted_at,
                            merchant_name=merchant_name,
                            amount_cents=amount_cents,
                            category=category,
                            is_subscription=is_subscription,
                            raw_json=_make_json_safe(txn if isinstance(txn, dict) else txn.to_dict()),
                        )
                    )
                    inserted += 1
                else:
                    # Update mutable fields on already-stored transactions.
                    existing_txn.merchant_name = merchant_name
                    existing_txn.amount_cents = amount_cents
                    existing_txn.category = category
                    existing_txn.is_subscription = is_subscription

                # Accumulate feature signals regardless of insert/update status.
                if merchant_name:
                    key = f"merchant:{_normalize_token(merchant_name)}"
                    feature_counts[key] = feature_counts.get(key, 0) + 1
                if category:
                    key = f"category:{_normalize_token(str(category))}"
                    feature_counts[key] = feature_counts.get(key, 0) + 1
                if is_subscription:
                    feature_counts["subscription:active"] = (
                        feature_counts.get("subscription:active", 0) + 1
                    )

            # Process modified transactions.
            for txn in modified:
                txn_id = txn.transaction_id
                row = db.scalar(
                    select(PlaidTransaction).where(
                        and_(
                            PlaidTransaction.user_id == user.id,
                            PlaidTransaction.provider_txn_id == txn_id,
                        )
                    )
                )
                merchant_name = getattr(txn, "merchant_name", None) or getattr(txn, "name", None)
                category_raw = getattr(txn, "personal_finance_category", {})
                if category_raw and hasattr(category_raw, "primary"):
                    category = category_raw.primary or getattr(category_raw, "detailed", None)
                else:
                    category = getattr(txn, "category", None)
                    if isinstance(category, list) and category:
                        category = category[0]
                is_subscription = bool(
                    getattr(txn, "recurring_transaction_id", None) or getattr(txn, "is_subscription", False)
                )

                if row:
                    row.merchant_name = merchant_name
                    row.category = category
                    row.is_subscription = is_subscription
                    row.raw_json = _make_json_safe(txn if isinstance(txn, dict) else txn.to_dict())

                if merchant_name:
                    key = f"merchant:{_normalize_token(merchant_name)}"
                    feature_counts[key] = feature_counts.get(key, 0) + 1
                if category:
                    key = f"category:{_normalize_token(str(category))}"
                    feature_counts[key] = feature_counts.get(key, 0) + 1
                if is_subscription:
                    feature_counts["subscription:active"] = (
                        feature_counts.get("subscription:active", 0) + 1
                    )

            # Process removals.
            for removed_txn in removed:
                txn_id = removed_txn.transaction_id
                row = db.scalar(
                    select(PlaidTransaction).where(
                        and_(
                            PlaidTransaction.user_id == user.id,
                            PlaidTransaction.provider_txn_id == txn_id,
                        )
                    )
                )
                if row:
                    db.delete(row)

    except Exception as exc:  # noqa: BLE001
        error_str = str(exc)
        # Check if this is a Plaid ITEM_LOGIN_REQUIRED error.
        if _ITEM_LOGIN_REQUIRED in error_str:
            item.status = "requires_reauth"
            emit_event(db, "plaid_reauth_required", user.id, {"item_id": item.item_id})
            db.flush()
            raise ValueError("Plaid item requires re-authentication.") from exc
        emit_event(db, "plaid_sync_failed", user.id, {"reason": error_str[:500]})
        db.flush()
        raise

    # Persist cursor and sync timestamp.
    item.cursor = cursor
    now = datetime.now(UTC)
    user.plaid_synced_at = now

    # Upsert UserFeature rows.
    for key, count in feature_counts.items():
        confidence = min(0.95, 0.75 + min(0.2, count * 0.04))
        feature = db.scalar(
            select(UserFeature).where(
                and_(
                    UserFeature.user_id == user.id,
                    UserFeature.feature_key == key,
                    UserFeature.source == "plaid",
                )
            )
        )
        if not feature:
            db.add(
                UserFeature(
                    user_id=user.id,
                    feature_key=key,
                    value_json={"count": count},
                    confidence=confidence,
                    first_seen_at=now,
                    last_seen_at=now,
                    source="plaid",
                )
            )
        else:
            feature.value_json = {"count": count}
            feature.confidence = confidence
            feature.last_seen_at = now
            feature.updated_at = now

    emit_event(
        db,
        "plaid_sync_completed",
        user.id,
        {"inserted_transactions": inserted, "feature_count": len(feature_counts)},
    )
    db.flush()
    return {"status": "ok", "inserted_transactions": inserted, "feature_count": len(feature_counts)}

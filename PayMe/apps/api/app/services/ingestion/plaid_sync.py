import json
import re
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.models.entities import PlaidTransaction, User, UserFeature
from app.services.events.service import emit_event


def _read_fixture_transactions() -> list[dict]:
    fixture = Path("/workspace/fixtures/plaid/transactions.json")
    if not fixture.exists():
        fixture = Path(__file__).resolve().parents[5] / "fixtures/plaid/transactions.json"
    return json.loads(fixture.read_text(encoding="utf-8"))


def _normalize_token(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def sync_plaid_mock(db: Session, user: User) -> dict:
    emit_event(db, "plaid_sync_started", user.id, {})
    if not settings.mock_plaid:
        emit_event(db, "plaid_sync_failed", user.id, {"reason": "not implemented"})
        return {"status": "not_implemented", "message": "Real Plaid integration is not implemented yet."}

    transactions = _read_fixture_transactions()
    inserted = 0
    feature_counts: dict[str, int] = {}
    for txn in transactions:
        exists = db.scalar(
            select(PlaidTransaction).where(
                and_(PlaidTransaction.user_id == user.id, PlaidTransaction.provider_txn_id == txn["transaction_id"])
            )
        )
        if not exists:
            db.add(
                PlaidTransaction(
                    user_id=user.id,
                    provider_txn_id=txn["transaction_id"],
                    posted_at=datetime.fromisoformat(txn["date"].replace("Z", "+00:00")),
                    merchant_name=txn.get("merchant_name"),
                    amount_cents=int(round(float(txn["amount"]) * 100)),
                    category=txn.get("category"),
                    is_subscription=bool(txn.get("is_subscription", False)),
                    raw_json=txn,
                )
            )
            inserted += 1

        merchant_name = txn.get("merchant_name")
        if merchant_name:
            key = f"merchant:{_normalize_token(merchant_name)}"
            feature_counts[key] = feature_counts.get(key, 0) + 1
        category = txn.get("category")
        if category:
            key = f"category:{_normalize_token(category)}"
            feature_counts[key] = feature_counts.get(key, 0) + 1
        if txn.get("is_subscription"):
            sub_key = "subscription:active"
            feature_counts[sub_key] = feature_counts.get(sub_key, 0) + 1

    now = datetime.now(UTC)
    user.plaid_synced_at = now
    for key, count in feature_counts.items():
        confidence = min(0.95, 0.75 + min(0.2, count * 0.04))
        feature = db.scalar(
            select(UserFeature).where(
                and_(UserFeature.user_id == user.id, UserFeature.feature_key == key, UserFeature.source == "plaid")
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

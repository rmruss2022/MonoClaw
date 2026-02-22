import argparse
from datetime import date
from datetime import datetime, timedelta, UTC
import os
import random

from sqlalchemy import and_, func, select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.entities import GmailMessage, PlaidTransaction, User
from app.schemas.onboarding import OnboardingRequest
from app.services.ingestion.gmail_sync import sync_gmail_mock
from app.services.ingestion.onboarding import upsert_onboarding
from app.services.ingestion.plaid_sync import sync_plaid_mock
from app.services.matching.engine import run_match


def build_messages(count: int, seed: int = 42) -> list[dict]:
    random.seed(seed)
    merchants = [
        ("amazon.com", "Amazon", "Prime subscription renewed"),
        ("uber.com", "Uber", "Your ride receipt is ready"),
        ("walmart.com", "Walmart", "Order delivered and receipt attached"),
        ("paramountplus.com", "Paramount+", "Monthly streaming subscription charge"),
    ]
    base_time = datetime.now(UTC)
    messages = []
    for i in range(count):
        domain, brand, snippet = merchants[i % len(merchants)]
        messages.append(
            {
                "id": f"msg_{i+1:05d}",
                "internalDate": (base_time.replace(microsecond=0)).isoformat(),
                "from_domain": domain,
                "subject": f"{brand} statement #{i+1}",
                "snippet": snippet if i % 11 else f"{snippet} and gaming bonus terms update",
            }
        )
    return messages


def build_transactions(count: int, seed: int = 42) -> list[dict]:
    random.seed(seed)
    merchants = [
        ("Amazon", "shopping", True),
        ("Uber", "transportation", False),
        ("Walmart", "groceries", False),
        ("Paramount+", "streaming", True),
    ]
    start = datetime.now(UTC) - timedelta(days=180)
    rows = []
    for i in range(count):
        merchant, category, is_subscription = merchants[i % len(merchants)]
        rows.append(
            {
                "transaction_id": f"txn_{i+1:05d}",
                "merchant_name": merchant,
                "amount": round(random.uniform(5.0, 180.0), 2),
                "date": (start + timedelta(hours=i * 3)).isoformat(),
                "category": category,
                "is_subscription": is_subscription if i % 3 else False,
            }
        )
    return rows


def ensure_fixtures(email_count: int, txn_count: int) -> None:
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    gmail_path = root / "fixtures/gmail/sample_messages.json"
    gmail_path.parent.mkdir(parents=True, exist_ok=True)
    gmail_path.write_text(json.dumps(build_messages(email_count), indent=2), encoding="utf-8")

    plaid_path = root / "fixtures/plaid/transactions.json"
    plaid_path.parent.mkdir(parents=True, exist_ok=True)
    plaid_path.write_text(json.dumps(build_transactions(txn_count), indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision large test user and data.")
    parser.add_argument("--username", default=os.getenv("MOCK_PROVISION_USERNAME", "large_test_user"))
    parser.add_argument("--email", default=os.getenv("MOCK_PROVISION_EMAIL", "large_test_user@example.com"))
    parser.add_argument("--password", default=os.getenv("MOCK_PROVISION_PASSWORD", "password123"))
    parser.add_argument("--emails", type=int, default=int(os.getenv("MOCK_PROVISION_EMAILS", "1000")))
    parser.add_argument(
        "--transactions", type=int, default=int(os.getenv("MOCK_PROVISION_TRANSACTIONS", "1000"))
    )
    parser.add_argument("--auto", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = db.scalar(
            select(User).where(and_(User.username == args.username, User.email == args.email))
        )
        if not user:
            user = User(
                username=args.username,
                email=args.email,
                password_hash=hash_password(args.password),
            )
            db.add(user)
            db.flush()

        if args.auto:
            existing_msgs = db.scalar(select(func.count(GmailMessage.id)).where(GmailMessage.user_id == user.id)) or 0
            existing_txs = db.scalar(
                select(func.count(PlaidTransaction.id)).where(PlaidTransaction.user_id == user.id)
            ) or 0
            if existing_msgs >= args.emails and existing_txs >= args.transactions:
                db.commit()
                print("large test user already provisioned; skipping auto run")
                return

        ensure_fixtures(args.emails, args.transactions)
        upsert_onboarding(
            db,
            user,
            OnboardingRequest(
                first_name="Large",
                last_name="Tester",
                state="NY",
                dob=date(1990, 1, 1),
                brands_purchased=["Amazon", "Uber", "Walmart", "Paramount"],
                payout_preference_type="paypal",
                payout_preference_value="large@test",
                finance_check_frequency="daily",
            ),
        )
        sync_gmail_mock(db, user)
        sync_plaid_mock(db, user)
        run_match(db, user)
        db.commit()
        print(f"provisioned {args.username}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

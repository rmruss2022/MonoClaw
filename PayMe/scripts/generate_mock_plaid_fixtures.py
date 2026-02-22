import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
import random


def build_transactions(count: int, seed: int = 42) -> list[dict]:
    random.seed(seed)
    merchants = [
        ("Amazon", "shopping", True),
        ("Uber", "transportation", False),
        ("Walmart", "groceries", False),
        ("Paramount+", "streaming", True),
        ("AT&T", "telecom", True),
        ("TikTok Shop", "shopping", False),
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate mock Plaid fixtures.")
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default="fixtures/plaid/transactions.json")
    args = parser.parse_args()
    txs = build_transactions(args.count, args.seed)
    root = Path(__file__).resolve().parents[1]
    target = Path(args.output)
    if not target.is_absolute():
        target = root / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(txs, indent=2), encoding="utf-8")
    print(f"wrote {len(txs)} transactions to {target}")


if __name__ == "__main__":
    main()

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
import random


def build_messages(count: int, seed: int = 42) -> list[dict]:
    random.seed(seed)
    merchants = [
        ("amazon.com", "Amazon", "Prime subscription renewed"),
        ("uber.com", "Uber", "Your ride receipt is ready"),
        ("walmart.com", "Walmart", "Order delivered and receipt attached"),
        ("paramountplus.com", "Paramount+", "Monthly streaming subscription charge"),
        ("att.com", "AT&T", "Billing statement available"),
        ("meta.com", "Meta", "Account purchase confirmation"),
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate mock Gmail fixtures.")
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default="fixtures/gmail/sample_messages.json")
    args = parser.parse_args()
    messages = build_messages(args.count, args.seed)
    root = Path(__file__).resolve().parents[1]
    target = Path(args.output)
    if not target.is_absolute():
        target = root / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(messages, indent=2), encoding="utf-8")
    print(f"wrote {len(messages)} messages to {target}")


if __name__ == "__main__":
    main()

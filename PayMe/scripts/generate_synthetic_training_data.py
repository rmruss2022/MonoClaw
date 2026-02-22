import csv
import json
import random
from pathlib import Path


def generate_rows(n_users: int = 250, n_settlements: int = 40) -> list[dict]:
    brands = ["amazon", "uber", "walmart", "paramount", "meta", "tiktok"]
    rows: list[dict] = []
    for uid in range(n_users):
        user_brand = random.choice(brands)
        for sid in range(n_settlements):
            settlement_brand = brands[sid % len(brands)]
            rules_confidence = 1.0 if user_brand == settlement_brand else random.uniform(0.1, 0.6)
            similarity = random.uniform(0.2, 0.95)
            payout = random.uniform(0.0, 1.0)
            urgency = random.uniform(0.0, 1.0)
            ease = random.uniform(0.0, 1.0)
            base_label = 1 if user_brand == settlement_brand else 0
            noisy = 1 if random.random() < 0.03 else 0
            label = 1 if (base_label or noisy) else 0
            rows.append(
                {
                    "user_id": uid,
                    "settlement_id": sid,
                    "rules_confidence": rules_confidence,
                    "similarity": similarity,
                    "payout": payout,
                    "urgency": urgency,
                    "ease": ease,
                    "label": label,
                }
            )
    return rows


def main() -> None:
    out_dir = Path("artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = generate_rows()
    with (out_dir / "synthetic_training.json").open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)
    with (out_dir / "synthetic_training.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows")


if __name__ == "__main__":
    main()

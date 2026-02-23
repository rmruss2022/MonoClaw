"""Build a realistic expanded feedback dataset from live match/claim data.

This script avoids hand-tuned directional feature edits. It:
1) Pulls base rows from real DB joins (match_results + settlements + claim status).
2) De-duplicates repeated (user_id, settlement_id) exposures.
3) Expands to a target size via within-class interpolation (SMOTE-like) with tiny noise.

The output is suitable for train_ranker.py consumption.
"""

from __future__ import annotations

import argparse
import json
import random
from decimal import Decimal
from pathlib import Path

import psycopg


FEATURES = ["rules_confidence", "similarity", "payout", "urgency", "ease"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate realistic augmented feedback data.")
    parser.add_argument(
        "--db-url",
        default="postgresql://payme:payme@localhost:5432/payme",
        help="PostgreSQL URL used to pull base rows (default: %(default)s).",
    )
    parser.add_argument(
        "--target",
        type=int,
        default=500,
        help="Total target rows after augmentation (default: %(default)s).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260222,
        help="Random seed for reproducible output (default: %(default)s).",
    )
    parser.add_argument(
        "--base-output",
        default="artifacts/feedback_export_enriched_base.json",
        help="Path for writing base de-duplicated labeled rows.",
    )
    parser.add_argument(
        "--aug-output",
        default="artifacts/feedback_export_augmented_realistic.json",
        help="Path for writing augmented rows.",
    )
    parser.add_argument(
        "--train-output",
        default="artifacts/feedback_export.json",
        help="Path for train_ranker.py input.",
    )
    return parser.parse_args()


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def fetch_base_rows(db_url: str) -> list[dict]:
    sql = """
        SELECT
          mr.user_id::text AS user_id,
          mr.settlement_id::text AS settlement_id,
          mr.run_id::text AS run_id,
          COALESCE((mr.reasons_json->'confidence_breakdown'->>'rules')::float, 0.5) AS rules_confidence,
          COALESCE(
            (mr.reasons_json->>'similarity')::float,
            LEAST(
              1.0,
              0.3 + 0.15 * json_array_length(COALESCE(mr.reasons_json->'matched_features', '[]'::json))
            ),
            0.3
          ) AS similarity,
          LEAST(1.0, COALESCE((s.payout_max_cents)::float / 10000.0, 0.1)) AS payout,
          CASE WHEN s.deadline IS NULL THEN 0.3 ELSE 0.7 END AS urgency,
          CASE WHEN s.claim_url IS NULL OR s.claim_url = '' THEN 0.4 ELSE 0.8 END AS ease,
          CASE
            WHEN usp.claim_status = 'paid_out' THEN 1
            WHEN usp.claim_status = 'not_paid_out' THEN 0
            WHEN usp.claim_status IN ('submitted', 'opened') THEN NULL
            ELSE 0
          END AS label,
          CASE
            WHEN usp.claim_status = 'paid_out' THEN 'paid_out'
            WHEN usp.claim_status = 'not_paid_out' THEN 'not_paid_out'
            WHEN usp.claim_status IN ('submitted', 'opened') THEN 'pending'
            ELSE 'ignored'
          END AS outcome
        FROM match_results mr
        JOIN settlements s ON s.id = mr.settlement_id
        LEFT JOIN user_settlement_preferences usp
          ON usp.user_id = mr.user_id AND usp.settlement_id = mr.settlement_id
        ORDER BY mr.created_at ASC;
    """

    rows: list[dict] = []
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            cols = [c.name for c in cur.description]
            for rec in cur.fetchall():
                row = dict(zip(cols, rec))
                for feature in FEATURES:
                    value = row.get(feature)
                    if isinstance(value, Decimal):
                        row[feature] = float(value)
                rows.append(row)

    labeled = [r for r in rows if r.get("label") in (0, 1)]

    # Use latest row per (user, settlement) pair to reduce repeated-exposure overweighting.
    dedup: dict[tuple[str, str], dict] = {}
    for row in labeled:
        dedup[(row["user_id"], row["settlement_id"])] = row
    return list(dedup.values())


def augment_rows(base_rows: list[dict], target: int, seed: int) -> list[dict]:
    random.seed(seed)

    by_label = {
        0: [r for r in base_rows if r["label"] == 0],
        1: [r for r in base_rows if r["label"] == 1],
    }
    if not by_label[0] or not by_label[1]:
        raise RuntimeError("Need both positive and negative labeled rows to augment.")

    rows = list(base_rows)
    positive_rate = len(by_label[1]) / len(base_rows)

    while len(rows) < target:
        label = 1 if random.random() < positive_rate else 0
        pool = by_label[label]
        if len(pool) >= 2:
            left, right = random.sample(pool, 2)
        else:
            left = right = pool[0]

        mix = random.betavariate(2.0, 2.0)
        synthetic = {
            "user_id": f"synth_u_{random.randint(1, 9_999_999)}",
            "settlement_id": f"synth_s_{random.randint(1, 9_999_999)}",
            "run_id": None,
            "label": label,
            "outcome": "paid_out" if label == 1 else random.choice(["ignored", "not_paid_out"]),
        }
        for feature in FEATURES:
            value = mix * float(left[feature]) + (1.0 - mix) * float(right[feature])
            synthetic[feature] = _clamp01(value + random.gauss(0.0, 0.015))

        rows.append(synthetic)

    random.shuffle(rows)
    return rows


def main() -> None:
    args = parse_args()
    base = fetch_base_rows(args.db_url)
    if len(base) < 10:
        raise SystemExit(f"Not enough base labeled rows to augment: {len(base)}")

    if args.target < len(base):
        raise SystemExit(f"target ({args.target}) cannot be lower than base rows ({len(base)})")

    final_rows = augment_rows(base, args.target, args.seed)

    base_path = Path(args.base_output)
    aug_path = Path(args.aug_output)
    train_path = Path(args.train_output)
    for path in (base_path, aug_path, train_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    base_path.write_text(json.dumps(base, indent=2), encoding="utf-8")
    aug_path.write_text(json.dumps(final_rows, indent=2), encoding="utf-8")
    train_path.write_text(json.dumps(final_rows, indent=2), encoding="utf-8")

    positive = sum(1 for r in final_rows if r["label"] == 1)
    negative = sum(1 for r in final_rows if r["label"] == 0)
    print(
        f"base_rows={len(base)} final_rows={len(final_rows)} "
        f"positive={positive} negative={negative} positive_rate={positive/len(final_rows):.3f}"
    )
    print(f"wrote {base_path}")
    print(f"wrote {aug_path}")
    print(f"wrote {train_path}")


if __name__ == "__main__":
    main()

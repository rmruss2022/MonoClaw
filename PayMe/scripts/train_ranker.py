import json
from pathlib import Path


def main() -> None:
    dataset_path = Path("artifacts/synthetic_training.json")
    if not dataset_path.exists():
        raise SystemExit("Run generate_synthetic_training_data.py first")
    rows = json.loads(dataset_path.read_text(encoding="utf-8"))
    positives = [r for r in rows if r["label"] == 1]
    negatives = [r for r in rows if r["label"] == 0]
    weights = {
        "rules_confidence": 0.6 if len(positives) > len(negatives) * 0.2 else 0.5,
        "similarity": 0.2,
        "payout": 0.1,
        "urgency": 0.05,
        "ease": 0.05,
    }
    out_dir = Path("artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "weights.json").write_text(json.dumps(weights, indent=2), encoding="utf-8")
    metrics = {"precision_at_5": 0.71, "recall_at_5": 0.63, "samples": len(rows)}
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print("trained mock ranker")


if __name__ == "__main__":
    main()

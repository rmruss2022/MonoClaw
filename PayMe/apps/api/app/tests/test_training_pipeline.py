import json
import subprocess
from pathlib import Path


def test_generate_synthetic_data_outputs_schema():
    root = Path(__file__).resolve().parents[4]
    subprocess.run(["python", "scripts/generate_synthetic_training_data.py"], cwd=root, check=True)
    data_path = root / "artifacts/synthetic_training.json"
    rows = json.loads(data_path.read_text(encoding="utf-8"))
    assert rows
    required = {"user_id", "settlement_id", "rules_confidence", "similarity", "payout", "urgency", "ease", "label"}
    assert required.issubset(rows[0].keys())


def test_train_ranker_produces_weights():
    root = Path(__file__).resolve().parents[4]
    subprocess.run(["python", "scripts/generate_synthetic_training_data.py"], cwd=root, check=True)
    subprocess.run(["python", "scripts/train_ranker.py"], cwd=root, check=True)
    weights = json.loads((root / "artifacts/weights.json").read_text(encoding="utf-8"))
    assert "rules_confidence" in weights

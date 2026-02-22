import json
from pathlib import Path

from app.services.matching.engine import _load_ranker_weights


def test_ranker_loads_weights_file(tmp_path, monkeypatch):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "weights.json").write_text(json.dumps({"rules_confidence": 0.1, "similarity": 0.7, "payout": 0.1, "urgency": 0.05, "ease": 0.05}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    weights = _load_ranker_weights()
    assert weights["similarity"] == 0.7

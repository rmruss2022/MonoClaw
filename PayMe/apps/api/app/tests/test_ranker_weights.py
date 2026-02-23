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


def test_ranker_fallback_uses_env_configurable_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_exists = Path.exists

    def _patched_exists(self):
        if str(self) == "/workspace/artifacts/weights.json":
            return False
        return original_exists(self)

    monkeypatch.setattr("pathlib.Path.exists", _patched_exists)

    monkeypatch.setattr(
        "app.services.matching.engine.settings.ranker_default_rules_confidence_weight",
        0.51,
    )
    monkeypatch.setattr(
        "app.services.matching.engine.settings.ranker_default_similarity_weight",
        0.21,
    )
    monkeypatch.setattr(
        "app.services.matching.engine.settings.ranker_default_payout_weight",
        0.17,
    )
    monkeypatch.setattr(
        "app.services.matching.engine.settings.ranker_default_urgency_weight",
        0.07,
    )
    monkeypatch.setattr(
        "app.services.matching.engine.settings.ranker_default_ease_weight",
        0.04,
    )

    weights = _load_ranker_weights()
    assert weights == {
        "rules_confidence": 0.51,
        "similarity": 0.21,
        "payout": 0.17,
        "urgency": 0.07,
        "ease": 0.04,
    }

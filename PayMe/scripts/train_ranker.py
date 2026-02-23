"""Train a logistic-regression-style ranker on labeled feedback samples.

Data source priority:
  1. artifacts/feedback_export.json  (real labeled data from export endpoint)
  2. artifacts/synthetic_training.json  (fallback synthetic data)

No external ML libraries required — uses scipy.optimize.minimize + numpy only.

Outputs:
  artifacts/weights.json        — active feature weights (only updated on promotion)
  artifacts/metrics.json        — active model metrics (only updated on promotion)
  artifacts/weights_vN.json     — versioned snapshot for every training run
  artifacts/metrics_vN.json     — versioned metrics snapshot for every training run

Auto-promotion:
  New weights are only written to artifacts/weights.json when the new model's
  precision@5 strictly exceeds the currently active model's precision@5.
  The version number is embedded in weights.json as "_version" so match runs
  can record which weight version produced each result.

Drift detection:
  If artifacts/metrics_prev.json exists, compares new precision@5 against it
  and logs a warning if it drops more than 5 percentage points.
"""

import json
import logging
import math
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

FEATURES = ["rules_confidence", "similarity", "payout", "urgency", "ease"]
ARTIFACTS = Path("artifacts")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_data() -> list[dict]:
    """Load training rows, preferring real feedback over synthetic data."""
    feedback_path = ARTIFACTS / "feedback_export.json"
    synthetic_path = ARTIFACTS / "synthetic_training.json"

    if feedback_path.exists():
        log.info("Loading real labeled data from %s", feedback_path)
        rows = json.loads(feedback_path.read_text(encoding="utf-8"))
    elif synthetic_path.exists():
        log.info("No feedback export found; falling back to %s", synthetic_path)
        rows = json.loads(synthetic_path.read_text(encoding="utf-8"))
    else:
        raise SystemExit(
            "No training data found. Run generate_synthetic_training_data.py "
            "or export real feedback first."
        )
    return rows


def build_matrices(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """Build feature matrix X and label vector y, skipping pending (label=None) rows."""
    labeled = [r for r in rows if r.get("label") is not None]
    if not labeled:
        raise SystemExit("No labeled rows found in training data (all labels are None/pending).")

    X = np.array([[float(r.get(f, 0.0)) for f in FEATURES] for r in labeled], dtype=np.float64)
    y = np.array([float(r["label"]) for r in labeled], dtype=np.float64)
    return X, y


# ---------------------------------------------------------------------------
# Logistic regression via scipy
# ---------------------------------------------------------------------------


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -500, 500)))


def _binary_cross_entropy(weights: np.ndarray, X: np.ndarray, y: np.ndarray) -> float:
    """Binary cross-entropy loss (no regularisation)."""
    p = _sigmoid(X @ weights)
    eps = 1e-12
    return -float(np.mean(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps)))


def _gradient(weights: np.ndarray, X: np.ndarray, y: np.ndarray) -> np.ndarray:
    p = _sigmoid(X @ weights)
    return X.T @ (p - y) / len(y)


def train(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Minimise binary cross-entropy to obtain feature weights."""
    w0 = np.zeros(X.shape[1])
    result = minimize(
        fun=_binary_cross_entropy,
        x0=w0,
        jac=_gradient,
        args=(X, y),
        method="L-BFGS-B",
        options={"maxiter": 500, "ftol": 1e-10},
    )
    if not result.success:
        log.warning("Optimiser did not fully converge: %s", result.message)
    return result.x


# ---------------------------------------------------------------------------
# Evaluation metrics
# ---------------------------------------------------------------------------


def _predict_scores(weights: np.ndarray, X: np.ndarray) -> np.ndarray:
    return _sigmoid(X @ weights)


def precision_at_k(scores: np.ndarray, y: np.ndarray, k: int) -> float:
    """Fraction of the top-k predictions that are positive."""
    if len(scores) == 0:
        return 0.0
    k = min(k, len(scores))
    top_k = np.argsort(scores)[::-1][:k]
    return float(np.mean(y[top_k]))


def approximate_auc(scores: np.ndarray, y: np.ndarray) -> float:
    """Approximate ROC-AUC via the Mann-Whitney U statistic."""
    pos_scores = scores[y == 1]
    neg_scores = scores[y == 0]
    if len(pos_scores) == 0 or len(neg_scores) == 0:
        return 0.5
    # Count (pos > neg) pairs
    wins = sum(1 for p in pos_scores for n in neg_scores if p > n)
    ties = sum(0.5 for p in pos_scores for n in neg_scores if p == n)
    total = len(pos_scores) * len(neg_scores)
    return (wins + ties) / total


def compute_metrics(weights: np.ndarray, X: np.ndarray, y: np.ndarray, total_rows: int) -> dict:
    scores = _predict_scores(weights, X)
    positive_rate = float(np.mean(y)) if len(y) > 0 else 0.0
    return {
        "precision_at_5": precision_at_k(scores, y, 5),
        "precision_at_10": precision_at_k(scores, y, 10),
        "auc_approx": approximate_auc(scores, y),
        "sample_count": total_rows,
        "labeled_count": len(y),
        "positive_rate": positive_rate,
    }


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------


DRIFT_THRESHOLD = 0.05  # 5 percentage point drop triggers a warning


def check_drift(new_metrics: dict, artifacts: Path) -> None:
    prev_path = artifacts / "metrics_prev.json"
    if not prev_path.exists():
        return
    try:
        prev = json.loads(prev_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        log.warning("Could not read metrics_prev.json for drift comparison.")
        return

    prev_p5 = prev.get("precision_at_5", None)
    new_p5 = new_metrics.get("precision_at_5", None)
    if prev_p5 is None or new_p5 is None:
        return
    drop = prev_p5 - new_p5
    if drop > DRIFT_THRESHOLD:
        log.warning(
            "DRIFT DETECTED: precision@5 dropped by %.3f (%.3f -> %.3f). "
            "Review training data quality before deploying new weights.",
            drop,
            prev_p5,
            new_p5,
        )
    else:
        log.info(
            "Drift check passed: precision@5 delta=%.3f (%.3f -> %.3f)",
            prev_p5 - new_p5,
            prev_p5,
            new_p5,
        )


def _next_version(artifacts: Path) -> int:
    """Return the next sequential version number based on existing weights_vN.json files."""
    versions = []
    for p in artifacts.glob("weights_v*.json"):
        try:
            versions.append(int(p.stem.split("_v")[-1]))
        except ValueError:
            pass
    return max(versions, default=0) + 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(artifacts_dir: Path | None = None) -> dict:  # noqa: PLW0603
    """Train ranker and auto-promote weights if precision@5 improves.

    Args:
        artifacts_dir: Override the artifacts directory (used when called from
            the API admin endpoint). Defaults to the module-level ARTIFACTS path.

    Returns:
        dict with keys: promoted, weights_version, new_metrics, previous_metrics
    """
    global ARTIFACTS
    if artifacts_dir is not None:
        ARTIFACTS = artifacts_dir
    ARTIFACTS.mkdir(parents=True, exist_ok=True)

    rows = load_data()
    log.info("Loaded %d total rows", len(rows))

    X, y = build_matrices(rows)
    log.info("Training on %d labeled samples (%.1f%% positive)", len(y), 100 * float(np.mean(y)))

    optimised_weights = train(X, y)

    # Map weights back to feature names
    weights_dict = {feat: float(w) for feat, w in zip(FEATURES, optimised_weights)}
    log.info("Trained weights: %s", weights_dict)

    metrics = compute_metrics(optimised_weights, X, y, total_rows=len(rows))
    log.info(
        "Metrics: precision@5=%.3f  precision@10=%.3f  AUC=%.3f",
        metrics["precision_at_5"],
        metrics["precision_at_10"],
        metrics["auc_approx"],
    )

    # Always save a versioned snapshot so every training run is auditable
    version = _next_version(ARTIFACTS)
    (ARTIFACTS / f"weights_v{version}.json").write_text(
        json.dumps(weights_dict, indent=2), encoding="utf-8"
    )
    (ARTIFACTS / f"metrics_v{version}.json").write_text(
        json.dumps({**metrics, "weights_version": version}, indent=2), encoding="utf-8"
    )
    log.info("Saved candidate artifacts: weights_v%d.json, metrics_v%d.json", version, version)

    # --- Auto-promotion: only replace active weights if metrics improve ---
    metrics_path = ARTIFACTS / "metrics.json"
    metrics_prev_path = ARTIFACTS / "metrics_prev.json"
    current_metrics: dict | None = None
    if metrics_path.exists():
        try:
            current_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    current_p5 = current_metrics.get("precision_at_5", 0.0) if current_metrics else 0.0
    new_p5 = metrics["precision_at_5"]
    promoted = False

    if current_metrics is None or new_p5 > current_p5:
        # Rotate active metrics → prev before overwriting
        if metrics_path.exists():
            metrics_prev_path.write_text(metrics_path.read_text(encoding="utf-8"), encoding="utf-8")

        check_drift(metrics, ARTIFACTS)

        # Embed version in weights.json so engine.py can record it on each match run
        promoted_weights = {**weights_dict, "_version": version}
        (ARTIFACTS / "weights.json").write_text(
            json.dumps(promoted_weights, indent=2), encoding="utf-8"
        )
        metrics_path.write_text(
            json.dumps({**metrics, "weights_version": version}, indent=2), encoding="utf-8"
        )
        promoted = True
        log.info(
            "PROMOTED v%d: precision@5=%.3f (was %.3f)", version, new_p5, current_p5
        )
    else:
        log.info(
            "NOT promoted: new precision@5=%.3f did not beat current=%.3f",
            new_p5,
            current_p5,
        )

    return {
        "promoted": promoted,
        "weights_version": version,
        "new_metrics": metrics,
        "previous_metrics": current_metrics,
    }


if __name__ == "__main__":
    main()

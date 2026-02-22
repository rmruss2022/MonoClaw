import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.models.entities import (
    ExperimentExposure,
    MatchResult,
    MatchRun,
    Settlement,
    SettlementFeatureIndex,
    User,
    UserFeature,
    UserSettlementPreference,
)
from app.services.events.service import emit_event

VARIANTS = ["rules_only", "rules_vector", "rules_vector_ranker"]


def _load_ranker_weights() -> dict:
    weights_path = Path("/workspace/artifacts/weights.json")
    if not weights_path.exists():
        weights_path = Path("artifacts/weights.json")
    if not weights_path.exists():
        return {
            "rules_confidence": 0.65,
            "similarity": 0.2,
            "payout": 0.1,
            "urgency": 0.03,
            "ease": 0.02,
        }
    return json.loads(weights_path.read_text(encoding="utf-8"))


def assign_variant(user_id: UUID, experiment_key: str) -> str:
    digest = hashlib.md5(f"{user_id}:{experiment_key}".encode(), usedforsecurity=False).hexdigest()
    idx = int(digest, 16) % 3
    return VARIANTS[idx]


def get_or_create_exposure(db: Session, user_id: UUID, experiment_key: str) -> str:
    exposure = db.scalar(
        select(ExperimentExposure).where(
            and_(
                ExperimentExposure.user_id == user_id,
                ExperimentExposure.experiment_key == experiment_key,
            )
        )
    )
    if exposure:
        return exposure.variant
    variant = assign_variant(user_id, experiment_key)
    db.add(ExperimentExposure(user_id=user_id, experiment_key=experiment_key, variant=variant))
    emit_event(
        db,
        "experiment_exposed",
        user_id,
        {"experiment_key": experiment_key, "variant": variant},
    )
    return variant


def run_match(db: Session, user: User, top_n: int = 20) -> MatchRun:
    user_features = db.scalars(select(UserFeature).where(UserFeature.user_id == user.id)).all()
    feature_map = {f.feature_key: f for f in user_features}
    feature_keys = set(feature_map.keys())

    variant = get_or_create_exposure(db, user.id, settings.experiment_key)
    run = MatchRun(
        user_id=user.id,
        experiment_key=settings.experiment_key,
        variant=variant,
        started_at=datetime.now(UTC),
    )
    db.add(run)
    db.flush()
    emit_event(db, "match_run_started", user.id, {"run_id": str(run.id), "variant": variant})

    index_rows = db.scalars(
        select(SettlementFeatureIndex).where(
            and_(SettlementFeatureIndex.feature_kind == "required", SettlementFeatureIndex.feature_key.in_(feature_keys))
        )
    ).all() if feature_keys else []
    hit_settlement_ids = {row.settlement_id for row in index_rows}

    settlements = db.scalars(select(Settlement)).all()
    candidate_rows: list[tuple[Settlement, float, list[str], list[str]]] = []
    weights = _load_ranker_weights()
    for settlement in settlements:
        predicates = settlement.eligibility_predicates or {}
        required = predicates.get("required_features", [])
        state_whitelist = predicates.get("states", [])
        state_ok = not state_whitelist or (user.state in state_whitelist)
        matched = [f for f in required if f in feature_keys]
        missing = [f for f in required if f not in feature_keys]
        required_ok = len(missing) == 0
        if required:
            candidate = settlement.id in hit_settlement_ids
        else:
            candidate = True
        if not candidate:
            continue
        rules_confidence = 0.4 + 0.4 * (len(matched) / max(1, len(required)))
        if state_ok:
            rules_confidence += 0.2
        similarity = min(1.0, 0.3 + 0.15 * len(matched))
        payout_signal = min(1.0, ((settlement.payout_max_cents or 1000) / 10000))
        urgency_signal = 0.7 if settlement.deadline else 0.3
        ease_signal = 0.8 if settlement.claim_url else 0.4
        if variant == "rules_only":
            score = rules_confidence
        elif variant == "rules_vector":
            score = 0.85 * rules_confidence + 0.15 * similarity
        else:
            score = (
                weights["rules_confidence"] * rules_confidence
                + weights["similarity"] * similarity
                + weights["payout"] * payout_signal
                + weights["urgency"] * urgency_signal
                + weights["ease"] * ease_signal
            )
        score = max(0.0, min(1.0, score))
        if not state_ok:
            missing.append("state")
        if required_ok and state_ok:
            candidate_rows.append((settlement, score, matched, missing))

    candidate_rows.sort(key=lambda x: x[1], reverse=True)
    run.candidate_count = len(candidate_rows)

    for settlement, score, matched, missing in candidate_rows[:top_n]:
        db.add(
            MatchResult(
                run_id=run.id,
                user_id=user.id,
                settlement_id=settlement.id,
                score=score,
                reasons_json={
                    "matched_features": matched,
                    "predicate_passes": {"state": user.state},
                    "confidence_breakdown": {"rules": score},
                },
                missing_features_json=missing,
            )
        )

    run.result_count = min(top_n, len(candidate_rows))
    run.completed_at = datetime.now(UTC)
    user.first_match_completed_at = run.completed_at
    run.metadata_json = {"feature_count": len(feature_keys), "variant": variant}
    emit_event(
        db,
        "match_run_completed",
        user.id,
        {"run_id": str(run.id), "candidate_count": run.candidate_count, "result_count": run.result_count},
    )
    db.flush()
    return run


def latest_results(db: Session, user_id: UUID) -> list[dict]:
    latest_run_id = db.scalar(
        select(MatchResult.run_id)
        .where(MatchResult.user_id == user_id)
        .order_by(desc(MatchResult.created_at))
        .limit(1)
    )
    if not latest_run_id:
        return []

    pref_map = {
        p.settlement_id: p
        for p in db.scalars(select(UserSettlementPreference).where(UserSettlementPreference.user_id == user_id)).all()
    }

    rows = db.execute(
        select(MatchResult, Settlement)
        .join(Settlement, Settlement.id == MatchResult.settlement_id)
        .where(MatchResult.run_id == latest_run_id)
    ).all()

    response = []
    for result, settlement in rows:
        pref = pref_map.get(result.settlement_id)
        response.append(
            {
                "settlement_id": settlement.id,
                "title": settlement.title,
                "score": result.score,
                "reasons_json": result.reasons_json,
                "missing_features_json": result.missing_features_json,
                "pinned": bool(pref and pref.pinned),
                "pinned_order": pref.pinned_order if pref else None,
            }
        )
    response.sort(key=lambda r: (not r["pinned"], r["pinned_order"] or 999999, -r["score"]))
    return response


def explain_for_settlement(db: Session, user_id: UUID, settlement_id: UUID) -> dict | None:
    row = db.execute(
        select(MatchResult).where(
            and_(MatchResult.user_id == user_id, MatchResult.settlement_id == settlement_id)
        ).order_by(desc(MatchResult.created_at))
    ).scalars().first()
    if not row:
        return None
    return {"reasons_json": row.reasons_json, "missing_features_json": row.missing_features_json}

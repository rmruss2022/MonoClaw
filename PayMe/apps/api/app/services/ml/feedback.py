"""
ML feedback loop service — Track 1.

Materializes labeled training samples from match results and claim outcomes,
then upserts them into the ml_feedback_samples table.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import MatchResult, MlFeedbackSample, UserSettlementPreference
from app.services.events.service import emit_event

# ---------------------------------------------------------------------------
# Label assignment rules
# ---------------------------------------------------------------------------
# claim_status == 'paid_out'              -> label=1,    outcome='paid_out'
# claim_status == 'not_paid_out'          -> label=0,    outcome='not_paid_out'
# claim_status in ('submitted', 'opened') -> label=None, outcome='pending'
# no claim_status (None / missing pref)   -> label=0,    outcome='ignored'
# ---------------------------------------------------------------------------

_FEATURE_KEYS = ("rules_confidence", "similarity", "payout", "urgency", "ease")


def _extract_features(reasons_json: dict) -> dict:
    """Pull feature signals out of a MatchResult.reasons_json.

    The engine stores a ``confidence_breakdown`` sub-dict with a 'rules' key.
    Other signals are stored directly or we fall back to safe defaults so the
    sample is still usable for training.
    """
    breakdown = reasons_json.get("confidence_breakdown", {})
    return {
        "rules_confidence": float(breakdown.get("rules", 0.5)),
        "similarity": float(reasons_json.get("similarity", 0.3)),
        "payout": float(reasons_json.get("payout", 0.1)),
        "urgency": float(reasons_json.get("urgency", 0.3)),
        "ease": float(reasons_json.get("ease", 0.4)),
    }


def _assign_label(claim_status: str | None) -> tuple[int | None, str]:
    """Return (label, outcome) for a given claim_status value."""
    if claim_status == "paid_out":
        return 1, "paid_out"
    if claim_status == "not_paid_out":
        return 0, "not_paid_out"
    if claim_status in ("submitted", "opened"):
        return None, "pending"
    return 0, "ignored"


def export_labeled_samples(db: Session) -> list[dict]:
    """Join match_results + user_settlement_preferences to create labeled training samples.

    For each (user_id, settlement_id) pair that has a MatchResult, extract feature
    signals and a label derived from the claim lifecycle, then upsert into
    ml_feedback_samples.  When a row already exists for a (user_id, settlement_id)
    pair the label, outcome, and feature snapshot are refreshed.

    Emits an ``ml_export_completed`` event with sample_count and labeled_count.

    Returns a list of exported row dicts.
    """
    match_results = db.scalars(select(MatchResult)).all()

    # Build a lookup from (user_id, settlement_id) -> UserSettlementPreference
    prefs = db.scalars(select(UserSettlementPreference)).all()
    pref_map: dict[tuple, UserSettlementPreference] = {
        (p.user_id, p.settlement_id): p for p in prefs
    }

    # Pre-load existing feedback samples keyed by (user_id, settlement_id)
    existing_samples = db.scalars(select(MlFeedbackSample)).all()
    sample_map: dict[tuple, MlFeedbackSample] = {
        (s.user_id, s.settlement_id): s for s in existing_samples
    }

    exported: list[dict] = []
    now = datetime.now(UTC)

    for mr in match_results:
        pref = pref_map.get((mr.user_id, mr.settlement_id))
        claim_status = pref.claim_status if pref else None
        label, outcome = _assign_label(claim_status)
        features = _extract_features(mr.reasons_json or {})

        key = (mr.user_id, mr.settlement_id)
        existing = sample_map.get(key)

        if existing:
            existing.label = label
            existing.outcome = outcome
            existing.run_id = mr.run_id
            existing.rules_confidence = features["rules_confidence"]
            existing.similarity = features["similarity"]
            existing.payout = features["payout"]
            existing.urgency = features["urgency"]
            existing.ease = features["ease"]
            existing.updated_at = now
        else:
            sample = MlFeedbackSample(
                user_id=mr.user_id,
                settlement_id=mr.settlement_id,
                run_id=mr.run_id,
                rules_confidence=features["rules_confidence"],
                similarity=features["similarity"],
                payout=features["payout"],
                urgency=features["urgency"],
                ease=features["ease"],
                label=label,
                outcome=outcome,
                export_version=1,
            )
            db.add(sample)
            sample_map[key] = sample

        exported.append(
            {
                "user_id": str(mr.user_id),
                "settlement_id": str(mr.settlement_id),
                "run_id": str(mr.run_id) if mr.run_id else None,
                "rules_confidence": features["rules_confidence"],
                "similarity": features["similarity"],
                "payout": features["payout"],
                "urgency": features["urgency"],
                "ease": features["ease"],
                "label": label,
                "outcome": outcome,
            }
        )

    db.flush()

    labeled_count = sum(1 for r in exported if r["label"] is not None)
    emit_event(
        db,
        "ml_export_completed",
        payload={"sample_count": len(exported), "labeled_count": labeled_count},
    )
    db.commit()

    return exported


def get_labeled_dataset(db: Session) -> list[dict]:
    """Return all ml_feedback_samples rows as dicts for training consumption."""
    rows = db.scalars(select(MlFeedbackSample)).all()
    return [
        {
            "id": str(r.id),
            "user_id": str(r.user_id),
            "settlement_id": str(r.settlement_id),
            "run_id": str(r.run_id) if r.run_id else None,
            "rules_confidence": r.rules_confidence,
            "similarity": r.similarity,
            "payout": r.payout,
            "urgency": r.urgency,
            "ease": r.ease,
            "label": r.label,
            "outcome": r.outcome,
            "export_version": r.export_version,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]

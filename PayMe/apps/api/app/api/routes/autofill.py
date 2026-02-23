"""Autofill job management routes — Track 4.

Enqueue jobs, check status, list user jobs.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.db import get_db
from app.models.entities import AutofillArtifact, AutofillJobStep, Settlement, User
from app.services.autofill.service import (
    ACTIVE_STATUSES,
    enqueue_job,
    get_job,
    list_jobs,
    list_steps,
)
from app.services.events.service import emit_event

router = APIRouter(prefix="/autofill", tags=["autofill"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class EnqueueJobRequest(BaseModel):
    settlement_id: uuid.UUID


class StepSummary(BaseModel):
    id: uuid.UUID
    step_name: str
    status: str
    error_message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class JobResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    settlement_id: uuid.UUID
    status: str
    attempt_count: int
    claim_url: str | None = None
    error_message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str
    updated_at: str
    steps: list[StepSummary] = []
    artifact_keys: list[str] = []


def _step_to_summary(step: AutofillJobStep) -> StepSummary:
    return StepSummary(
        id=step.id,
        step_name=step.step_name,
        status=step.status,
        error_message=step.error_message,
        started_at=step.started_at.isoformat() if step.started_at else None,
        completed_at=step.completed_at.isoformat() if step.completed_at else None,
    )


def _job_to_response(
    db: Session,
    job,
    include_steps: bool = True,
) -> dict:
    steps: list[StepSummary] = []
    artifact_keys: list[str] = []

    if include_steps:
        raw_steps = list_steps(db, job.id)
        steps = [_step_to_summary(s) for s in raw_steps]

        artifacts = db.query(AutofillArtifact).filter(AutofillArtifact.job_id == job.id).all()
        artifact_keys = [a.storage_key for a in artifacts]

    return {
        "id": str(job.id),
        "user_id": str(job.user_id),
        "settlement_id": str(job.settlement_id),
        "status": job.status,
        "attempt_count": job.attempt_count,
        "claim_url": job.claim_url,
        "error_message": job.error_message,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "steps": [s.model_dump(mode="json") for s in steps],
        "artifact_keys": artifact_keys,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
def enqueue_job_route(
    body: EnqueueJobRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Enqueue a new autofill job for the authenticated user.

    Returns 409 with the existing job if an active (non-terminal) job already
    exists for the same (user, settlement) pair.
    """
    # Resolve claim_url from the settlement record.
    settlement = db.get(Settlement, body.settlement_id)
    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")

    # Check for existing active job BEFORE creating one.
    from sqlalchemy import select as sa_select
    from app.models.entities import AutofillJob

    existing = db.scalar(
        sa_select(AutofillJob).where(
            AutofillJob.user_id == user.id,
            AutofillJob.settlement_id == body.settlement_id,
            AutofillJob.status.in_(ACTIVE_STATUSES),
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Active autofill job already exists for this settlement.",
                "job": _job_to_response(db, existing),
            },
        )

    job = enqueue_job(db, user.id, body.settlement_id, claim_url=settlement.claim_url)

    emit_event(
        db,
        "autofill_job_queued",
        user_id=user.id,
        payload={
            "job_id": str(job.id),
            "settlement_id": str(body.settlement_id),
            "user_id": str(user.id),
        },
    )
    db.commit()

    return _job_to_response(db, job)


@router.get("/jobs/{job_id}")
def get_job_route(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return a single autofill job with steps and artifact keys.

    Returns 404 if the job does not exist or belongs to a different user.
    """
    job = get_job(db, job_id, user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Autofill job not found")

    return _job_to_response(db, job)


@router.get("/jobs")
def list_jobs_route(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return all autofill jobs for the authenticated user, most recent first."""
    jobs = list_jobs(db, user.id)
    return [_job_to_response(db, job) for job in jobs]

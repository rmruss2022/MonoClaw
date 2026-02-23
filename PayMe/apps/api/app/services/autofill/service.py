"""Autofill job management service — Track 4.

Handles job creation (with idempotency), retrieval, listing, step recording,
and status transitions for AutofillJob records.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import AutofillJob, AutofillJobStep

# Terminal statuses — a job in one of these is considered complete and a new one may be created.
TERMINAL_STATUSES = {"done", "failed"}

# Active (non-terminal) statuses — used for idempotency guard.
ACTIVE_STATUSES = {"queued", "running", "blocked"}


def enqueue_job(db: Session, user_id: uuid.UUID, settlement_id: uuid.UUID, claim_url: str | None = None) -> AutofillJob:
    """Return existing active job if one exists; otherwise create a new queued job.

    Idempotency: if an active job (status in queued/running/blocked) already
    exists for the (user, settlement) pair, return that job unchanged.
    """
    existing = db.scalar(
        select(AutofillJob).where(
            AutofillJob.user_id == user_id,
            AutofillJob.settlement_id == settlement_id,
            AutofillJob.status.in_(ACTIVE_STATUSES),
        )
    )
    if existing is not None:
        return existing

    job = AutofillJob(
        user_id=user_id,
        settlement_id=settlement_id,
        status="queued",
        claim_url=claim_url,
        attempt_count=0,
    )
    db.add(job)
    db.flush()
    return job


def get_job(db: Session, job_id: uuid.UUID, user_id: uuid.UUID) -> AutofillJob | None:
    """Fetch a single job by ID with ownership check. Returns None if not found or not owned."""
    return db.scalar(
        select(AutofillJob).where(
            AutofillJob.id == job_id,
            AutofillJob.user_id == user_id,
        )
    )


def list_jobs(db: Session, user_id: uuid.UUID) -> list[AutofillJob]:
    """Return all autofill jobs for a user, newest first."""
    return list(
        db.scalars(
            select(AutofillJob)
            .where(AutofillJob.user_id == user_id)
            .order_by(AutofillJob.created_at.desc())
        ).all()
    )


def list_steps(db: Session, job_id: uuid.UUID) -> list[AutofillJobStep]:
    """Return all steps for a job, ordered by creation time."""
    return list(
        db.scalars(
            select(AutofillJobStep)
            .where(AutofillJobStep.job_id == job_id)
            .order_by(AutofillJobStep.created_at.asc())
        ).all()
    )


def record_step(
    db: Session,
    job_id: uuid.UUID,
    step_name: str,
    status: str,
    input_json: dict | None = None,
    output_json: dict | None = None,
    error_message: str | None = None,
) -> AutofillJobStep:
    """Create and persist a job step record."""
    now = datetime.now(timezone.utc)
    step = AutofillJobStep(
        job_id=job_id,
        step_name=step_name,
        status=status,
        input_json=input_json,
        output_json=output_json,
        error_message=error_message,
        started_at=now if status in {"running", "done", "failed", "skipped"} else None,
        completed_at=now if status in {"done", "failed", "skipped"} else None,
    )
    db.add(step)
    db.flush()
    return step


def transition_job(
    db: Session,
    job: AutofillJob,
    new_status: str,
    error_message: str | None = None,
) -> None:
    """Transition job to a new status with appropriate timestamp updates.

    Allowed transitions (enforced loosely — callers are responsible for
    honouring the state machine):
      queued -> running
      running -> done | blocked | failed | queued (retry)
      blocked -> queued (manual re-queue)
    """
    now = datetime.now(timezone.utc)
    job.status = new_status

    if new_status == "running":
        job.started_at = job.started_at or now
        job.attempt_count = (job.attempt_count or 0) + 1

    if new_status in {"done", "failed", "blocked"}:
        job.completed_at = now

    if error_message is not None:
        job.error_message = error_message

    db.flush()

"""Autofill worker — polls for queued jobs and executes browser automation.

Run with:
    python -m autofill.worker

Polling loop:
    1. SELECT autofill_jobs WHERE status='queued'
          AND (next_retry_at IS NULL OR next_retry_at <= now())
          ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED
    2. Set status='running', started_at=now(), attempt_count += 1
    3. Execute run_autofill_job(job)
    4. On success: status='done', completed_at=now()
    5. On BlockedError: status='blocked', error_message=reason
    6. On Exception and attempt_count < max_retries:
          status='queued', next_retry_at = now() + retry_delay
    7. On Exception and attempt_count >= max_retries: status='failed'
    8. Sleep POLL_INTERVAL seconds between polls when queue is empty.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine

from autofill.browser import BlockedError, run_autofill_job
from autofill.settings import worker_settings

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("autofill.worker")

# ---------------------------------------------------------------------------
# DB setup — synchronous (psycopg v3 sync driver)
# ---------------------------------------------------------------------------

engine = create_engine(worker_settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)

# ---------------------------------------------------------------------------
# Import entity models from the shared package path at runtime.
# The worker container mounts the API app so the models are importable.
# ---------------------------------------------------------------------------

try:
    from app.models.entities import AutofillArtifact, AutofillJob, AutofillJobStep
except ImportError:
    # Fallback: define lightweight stubs so the worker is importable in
    # environments where the API package is not on sys.path (e.g. unit tests).
    AutofillJob = None  # type: ignore[assignment]
    AutofillJobStep = None  # type: ignore[assignment]
    AutofillArtifact = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# DB helpers (synchronous)
# ---------------------------------------------------------------------------


def _emit_event(db: Session, event_type: str, user_id, payload: dict) -> None:
    try:
        from app.models.entities import Event

        ev = Event(type=event_type, user_id=user_id, payload_json=payload)
        db.add(ev)
        db.flush()
    except Exception as exc:  # noqa: BLE001
        log.warning("Failed to emit event %s: %s", event_type, exc)


def _record_step(
    db: Session,
    job_id: uuid.UUID,
    step_name: str,
    status: str,
    output_json: dict | None = None,
    error_message: str | None = None,
) -> "AutofillJobStep":
    now = datetime.now(timezone.utc)
    step = AutofillJobStep(
        job_id=job_id,
        step_name=step_name,
        status=status,
        output_json=output_json,
        error_message=error_message,
        started_at=now,
        completed_at=now,
    )
    db.add(step)
    db.flush()
    return step


def _save_artifact(
    db: Session,
    job_id: uuid.UUID,
    step_id: uuid.UUID | None,
    artifact_type: str,
    content_type: str,
    storage_key: str,
    size_bytes: int | None,
) -> None:
    artifact = AutofillArtifact(
        job_id=job_id,
        step_id=step_id,
        artifact_type=artifact_type,
        content_type=content_type,
        storage_key=storage_key,
        size_bytes=size_bytes,
    )
    db.add(artifact)
    db.flush()


# ---------------------------------------------------------------------------
# Fetch user profile from the API
# ---------------------------------------------------------------------------


def _fetch_user_data(user_id: str) -> dict:
    """Retrieve user profile fields needed for form-filling via internal API."""
    try:
        with httpx.Client(base_url=worker_settings.api_base_url, timeout=10.0) as client:
            resp = client.get(f"/admin/users/{user_id}")
            if resp.status_code == 200:
                return resp.json()
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not fetch user data for %s: %s", user_id, exc)
    return {}


# ---------------------------------------------------------------------------
# Core job runner
# ---------------------------------------------------------------------------


async def _execute_job(job: "AutofillJob", db: Session) -> None:
    """Run all browser automation steps for a single job and persist results."""
    user_data = _fetch_user_data(str(job.user_id))

    job_data = {
        "id": str(job.id),
        "claim_url": job.claim_url,
        "settlement_title": "",  # populated below if available
    }

    # Attempt to enrich settlement title.
    try:
        from app.models.entities import Settlement

        settlement = db.get(Settlement, job.settlement_id)
        if settlement:
            job_data["settlement_title"] = settlement.title
    except Exception:  # noqa: BLE001
        pass

    log.info("Executing autofill job %s (attempt %s)", job.id, job.attempt_count)

    _emit_event(
        db,
        "autofill_job_started",
        user_id=job.user_id,
        payload={"job_id": str(job.id), "attempt_count": job.attempt_count},
    )
    db.commit()

    step_results = await run_autofill_job(job_data, user_data)

    # Persist individual step records and screenshot artifacts.
    for step_name, result in step_results.items():
        step_status = result.get("status", "done")
        err = result.get("error")
        step = _record_step(
            db,
            job_id=job.id,
            step_name=step_name,
            status=step_status,
            output_json={k: v for k, v in result.items() if k not in ("status", "error")},
            error_message=err,
        )
        db.commit()

        _emit_event(
            db,
            "autofill_step_completed",
            user_id=job.user_id,
            payload={"job_id": str(job.id), "step_name": step_name, "status": step_status},
        )
        db.commit()

        # Persist screenshot artifact record.
        if step_name == "screenshot" and step_status == "done":
            storage_key = result.get("storage_key", "")
            size_bytes = result.get("size_bytes")
            if storage_key:
                _save_artifact(
                    db,
                    job_id=job.id,
                    step_id=step.id,
                    artifact_type="screenshot",
                    content_type="image/png",
                    storage_key=storage_key,
                    size_bytes=size_bytes,
                )
                db.commit()


# ---------------------------------------------------------------------------
# Polling loop
# ---------------------------------------------------------------------------


def _claim_next_job(db: Session) -> "AutofillJob | None":
    """Claim the next queued job using FOR UPDATE SKIP LOCKED."""
    now = datetime.now(timezone.utc)
    row = db.scalar(
        select(AutofillJob)
        .where(
            AutofillJob.status == "queued",
            (AutofillJob.next_retry_at == None) | (AutofillJob.next_retry_at <= now),  # noqa: E711
        )
        .order_by(AutofillJob.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if row is None:
        return None

    now_ts = datetime.now(timezone.utc)
    row.status = "running"
    row.started_at = row.started_at or now_ts
    row.attempt_count = (row.attempt_count or 0) + 1
    db.flush()
    return row


async def _process_job(job: "AutofillJob", db: Session) -> None:
    """Execute job; handle success, blocked, and retry/fail paths."""
    max_retries = worker_settings.autofill_max_retries
    retry_delay = worker_settings.autofill_retry_delay_seconds

    try:
        await _execute_job(job, db)
        # Success path.
        job.status = "done"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        _emit_event(db, "autofill_job_done", user_id=job.user_id, payload={"job_id": str(job.id)})
        db.commit()

        log.info("Job %s completed successfully.", job.id)

    except BlockedError as exc:
        reason = str(exc)
        log.warning("Job %s blocked: %s", job.id, reason)
        job.status = "blocked"
        job.error_message = reason
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        _emit_event(
            db,
            "autofill_job_blocked",
            user_id=job.user_id,
            payload={"job_id": str(job.id), "reason": reason},
        )
        db.commit()

    except Exception as exc:  # noqa: BLE001
        error_message = str(exc)
        log.exception("Job %s failed (attempt %s/%s): %s", job.id, job.attempt_count, max_retries, error_message)

        if job.attempt_count < max_retries:
            # Re-queue with backoff.
            job.status = "queued"
            job.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)
            job.error_message = error_message
            db.commit()
            log.info("Job %s re-queued for retry at %s.", job.id, job.next_retry_at)
        else:
            # Exhausted retries.
            job.status = "failed"
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = error_message
            db.commit()

            _emit_event(
                db,
                "autofill_job_failed",
                user_id=job.user_id,
                payload={"job_id": str(job.id), "error_message": error_message},
            )
            db.commit()

            log.error("Job %s permanently failed after %s attempts.", job.id, job.attempt_count)


async def run_worker() -> None:
    """Main async polling loop — runs indefinitely."""
    poll_interval = worker_settings.poll_interval_seconds
    log.info(
        "Autofill worker started. Poll interval: %ss, max_retries: %s, retry_delay: %ss",
        poll_interval,
        worker_settings.autofill_max_retries,
        worker_settings.autofill_retry_delay_seconds,
    )

    while True:
        db = SessionLocal()
        try:
            with db.begin():
                job = _claim_next_job(db)

            if job is None:
                await asyncio.sleep(poll_interval)
                continue

            log.info("Claimed job %s (attempt %s)", job.id, job.attempt_count)
            await _process_job(job, db)

        except Exception as exc:  # noqa: BLE001
            log.exception("Unhandled error in polling loop: %s", exc)
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(poll_interval)

        finally:
            db.close()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()

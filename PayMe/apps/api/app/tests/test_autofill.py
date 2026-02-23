"""Tests for Track 4: Autofill agent — API routes, service layer, and browser module.

Uses the existing conftest.py fixtures (db_setup, client) which spin up an
isolated payme_test schema and a FastAPI TestClient wired to it.

The browser-level tests mock Playwright so they don't require a real browser and
can run inside the API container without the autofill-agent package installed.
The autofill.browser module is imported lazily (inside the test functions) so
that a missing package causes a skip rather than a collection-time failure.
"""

from __future__ import annotations

import sys
import uuid
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.models.entities import AutofillJob, AutofillJobStep, Event, Settlement, User
from app.services.autofill.service import (
    enqueue_job,
    get_job,
    list_jobs,
    record_step,
    transition_job,
)
from app.tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _signup_and_token(client, username: str = "autofill_user", email: str = "autofill@example.com") -> str:
    resp = client.post(
        "/auth/signup",
        json={"username": username, "email": email, "password": "password123"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _get_settlement_id() -> uuid.UUID:
    """Return the settlement ID seeded by conftest.py's db_setup fixture."""
    db = TestingSessionLocal()
    try:
        settlement = db.scalar(select(Settlement))
        assert settlement is not None
        return settlement.id
    finally:
        db.close()


def _create_user(db, username: str = "svc_user", email: str = "svc@example.com") -> User:
    """Insert a minimal User row directly (for service-layer tests that bypass HTTP)."""
    user = User(
        username=username,
        email=email,
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$placeholder",
    )
    db.add(user)
    db.flush()
    return user


# ---------------------------------------------------------------------------
# API route tests
# ---------------------------------------------------------------------------


def test_enqueue_job_creates_queued_job(client):
    """POST /autofill/jobs returns 201 with status='queued'."""
    token = _signup_and_token(client)
    settlement_id = _get_settlement_id()

    resp = client.post(
        "/autofill/jobs",
        json={"settlement_id": str(settlement_id)},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "queued"
    assert body["settlement_id"] == str(settlement_id)
    assert "id" in body
    assert body["attempt_count"] == 0


def test_enqueue_job_idempotent_returns_existing(client):
    """Second POST for same (user, settlement) returns 409 with the existing job id."""
    token = _signup_and_token(client, "autofill_idem", "autofill_idem@example.com")
    settlement_id = _get_settlement_id()

    first = client.post(
        "/autofill/jobs",
        json={"settlement_id": str(settlement_id)},
        headers=_auth(token),
    )
    assert first.status_code == 201, first.text
    first_job_id = first.json()["id"]

    second = client.post(
        "/autofill/jobs",
        json={"settlement_id": str(settlement_id)},
        headers=_auth(token),
    )
    assert second.status_code == 409, second.text
    detail = second.json()["detail"]
    assert detail["job"]["id"] == first_job_id


def test_get_job_returns_job(client):
    """GET /autofill/jobs/{job_id} returns the correct job."""
    token = _signup_and_token(client, "autofill_getter", "autofill_getter@example.com")
    settlement_id = _get_settlement_id()

    created = client.post(
        "/autofill/jobs",
        json={"settlement_id": str(settlement_id)},
        headers=_auth(token),
    )
    assert created.status_code == 201
    job_id = created.json()["id"]

    fetched = client.get(f"/autofill/jobs/{job_id}", headers=_auth(token))
    assert fetched.status_code == 200, fetched.text
    body = fetched.json()
    assert body["id"] == job_id
    assert body["status"] == "queued"
    assert "steps" in body
    assert "artifact_keys" in body


def test_get_job_not_found_for_other_user(client):
    """GET /autofill/jobs/{job_id} returns 404 when the job belongs to a different user."""
    owner_token = _signup_and_token(client, "owner_user", "owner@example.com")
    other_token = _signup_and_token(client, "other_user", "other@example.com")
    settlement_id = _get_settlement_id()

    created = client.post(
        "/autofill/jobs",
        json={"settlement_id": str(settlement_id)},
        headers=_auth(owner_token),
    )
    assert created.status_code == 201
    job_id = created.json()["id"]

    # Other user must not see the owner's job.
    resp = client.get(f"/autofill/jobs/{job_id}", headers=_auth(other_token))
    assert resp.status_code == 404, resp.text


def test_list_jobs_returns_user_jobs(client):
    """GET /autofill/jobs returns only the authenticated user's jobs."""
    token = _signup_and_token(client, "list_jobs_user", "list_jobs@example.com")
    settlement_id = _get_settlement_id()

    # Enqueue one job.
    client.post(
        "/autofill/jobs",
        json={"settlement_id": str(settlement_id)},
        headers=_auth(token),
    )

    resp = client.get("/autofill/jobs", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    jobs = resp.json()
    assert len(jobs) >= 1
    for job in jobs:
        assert job["status"] in {"queued", "running", "blocked", "done", "failed"}


def test_enqueue_job_emits_event(client):
    """Enqueueing a job should write an autofill_job_queued event to the DB."""
    token = _signup_and_token(client, "event_user", "event_user@example.com")
    settlement_id = _get_settlement_id()

    resp = client.post(
        "/autofill/jobs",
        json={"settlement_id": str(settlement_id)},
        headers=_auth(token),
    )
    assert resp.status_code == 201

    db = TestingSessionLocal()
    try:
        event = db.scalar(select(Event).where(Event.type == "autofill_job_queued"))
        assert event is not None
        assert event.payload_json["settlement_id"] == str(settlement_id)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Service layer tests (direct DB, no HTTP)
# ---------------------------------------------------------------------------


def test_job_status_transitions(db_setup):
    """service.transition_job correctly advances job status and sets timestamps."""
    db = TestingSessionLocal()
    try:
        settlement = db.scalar(select(Settlement))
        assert settlement is not None
        user = _create_user(db)
        db.commit()

        job = enqueue_job(db, user_id=user.id, settlement_id=settlement.id)
        db.commit()

        assert job.status == "queued"
        assert job.attempt_count == 0
        assert job.started_at is None

        # queued -> running
        transition_job(db, job, "running")
        db.commit()
        assert job.status == "running"
        assert job.attempt_count == 1
        assert job.started_at is not None

        # running -> done
        transition_job(db, job, "done")
        db.commit()
        assert job.status == "done"
        assert job.completed_at is not None

    finally:
        db.close()


def test_job_transition_to_failed_records_error(db_setup):
    """transition_job(failed) persists error_message."""
    db = TestingSessionLocal()
    try:
        settlement = db.scalar(select(Settlement))
        user = _create_user(db, username="fail_user", email="fail@example.com")
        db.commit()

        job = enqueue_job(db, user_id=user.id, settlement_id=settlement.id)
        db.commit()

        transition_job(db, job, "running")
        db.commit()

        transition_job(db, job, "failed", error_message="network timeout")
        db.commit()

        assert job.status == "failed"
        assert job.error_message == "network timeout"
        assert job.completed_at is not None
    finally:
        db.close()


def test_record_step_creates_step(db_setup):
    """service.record_step creates an AutofillJobStep row with correct fields."""
    db = TestingSessionLocal()
    try:
        settlement = db.scalar(select(Settlement))
        user = _create_user(db, username="step_user", email="step@example.com")
        db.commit()

        job = enqueue_job(db, user_id=user.id, settlement_id=settlement.id)
        db.commit()

        step = record_step(
            db,
            job_id=job.id,
            step_name="navigate",
            status="done",
            output_json={"url": "https://example.com", "http_status": 200},
        )
        db.commit()

        assert step.id is not None
        assert step.job_id == job.id
        assert step.step_name == "navigate"
        assert step.status == "done"
        assert step.output_json["url"] == "https://example.com"
        assert step.completed_at is not None

        # Verify row is readable from DB.
        fetched = db.scalar(select(AutofillJobStep).where(AutofillJobStep.id == step.id))
        assert fetched is not None
        assert fetched.step_name == "navigate"
    finally:
        db.close()


def test_enqueue_job_idempotency_service_layer(db_setup):
    """enqueue_job returns the existing active job on repeated calls."""
    db = TestingSessionLocal()
    try:
        settlement = db.scalar(select(Settlement))
        user = _create_user(db, username="idem_svc_user", email="idem_svc@example.com")
        db.commit()

        job1 = enqueue_job(db, user_id=user.id, settlement_id=settlement.id)
        db.commit()

        job2 = enqueue_job(db, user_id=user.id, settlement_id=settlement.id)
        db.commit()

        assert job1.id == job2.id
    finally:
        db.close()


def test_get_job_ownership_check(db_setup):
    """get_job returns None when user_id does not match the job owner."""
    db = TestingSessionLocal()
    try:
        settlement = db.scalar(select(Settlement))
        owner = _create_user(db, username="owner_svc", email="owner_svc@example.com")
        db.commit()

        job = enqueue_job(db, user_id=owner.id, settlement_id=settlement.id)
        db.commit()

        found = get_job(db, job.id, owner.id)
        assert found is not None

        # A random UUID that doesn't correspond to any user should not find the job.
        not_found = get_job(db, job.id, uuid.uuid4())
        assert not_found is None
    finally:
        db.close()


def test_list_jobs_returns_user_jobs_service_layer(db_setup):
    """list_jobs returns jobs for the correct user only."""
    db = TestingSessionLocal()
    try:
        settlement = db.scalar(select(Settlement))
        user_a = _create_user(db, username="list_a", email="list_a@example.com")
        db.commit()

        enqueue_job(db, user_id=user_a.id, settlement_id=settlement.id)
        db.commit()

        jobs_a = list_jobs(db, user_a.id)
        # A random UUID that corresponds to no user — should return empty list.
        jobs_b = list_jobs(db, uuid.uuid4())

        assert len(jobs_a) == 1
        assert len(jobs_b) == 0
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Browser module unit tests (mock Playwright)
#
# These tests inject the autofill-agent package into sys.path so the browser
# module can be imported and exercised without Playwright actually installed in
# the API container.  If the package is unavailable the tests are skipped.
# pytest.mark.anyio is used because anyio (4.x) is already installed and
# registered as a pytest plugin in this container.
# ---------------------------------------------------------------------------


def _ensure_autofill_importable() -> tuple[ModuleType, ModuleType]:
    """Add the autofill-agent source tree to sys.path if needed, then import.

    Returns the (browser_module, settings_module) pair, or pytest-skips if
    the path cannot be resolved (e.g. running in a stripped container image).
    """
    import importlib
    import os

    # File is at: apps/api/app/tests/test_autofill.py
    # autofill-agent is at: apps/autofill-agent/
    # Relative path from this file: ../../../autofill-agent
    agent_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "autofill-agent")
    )
    if agent_root not in sys.path:
        sys.path.insert(0, agent_root)

    # Stub out playwright if not installed so the module is importable
    # purely for unit-testing its logic.  We need to supply stub names for
    # everything that browser.py imports at module level.
    if "playwright" not in sys.modules:
        pw_async_api = ModuleType("playwright.async_api")
        # Provide stub callables/classes for all names imported at module level
        # in autofill/browser.py:
        #   from playwright.async_api import BrowserContext, Page, Response, async_playwright
        for name in ("BrowserContext", "Page", "Response", "async_playwright"):
            setattr(pw_async_api, name, MagicMock())

        pw_stub = ModuleType("playwright")
        pw_stub.async_api = pw_async_api  # type: ignore[attr-defined]
        sys.modules["playwright"] = pw_stub
        sys.modules["playwright.async_api"] = pw_async_api

    try:
        settings_mod = importlib.import_module("autofill.settings")
        # Force reload in case it was already imported with a stale path.
        if "autofill.browser" in sys.modules:
            browser_mod = sys.modules["autofill.browser"]
        else:
            browser_mod = importlib.import_module("autofill.browser")
        return browser_mod, settings_mod
    except Exception as exc:
        pytest.skip(f"autofill-agent package not importable from API container: {exc}")


@pytest.mark.anyio
async def test_browser_blocked_error_on_403():
    """BlockedError is raised when the page returns HTTP 403."""
    browser_mod, _ = _ensure_autofill_importable()
    BlockedError = browser_mod.BlockedError
    run_autofill_job = browser_mod.run_autofill_job

    # Build mock chain: async_playwright -> chromium -> browser -> context -> page
    mock_response = MagicMock()
    mock_response.status = 403

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock(return_value=mock_response)
    mock_page.wait_for_timeout = AsyncMock()
    mock_page.screenshot = AsyncMock()

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.close = AsyncMock()

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_browser.close = AsyncMock()

    mock_chromium = AsyncMock()
    mock_chromium.launch = AsyncMock(return_value=mock_browser)

    mock_pw_instance = AsyncMock()
    mock_pw_instance.chromium = mock_chromium
    mock_pw_instance.__aenter__ = AsyncMock(return_value=mock_pw_instance)
    mock_pw_instance.__aexit__ = AsyncMock(return_value=False)

    job_data = {
        "id": str(uuid.uuid4()),
        "claim_url": "https://example.com/claim",
        "settlement_title": "Test Settlement",
    }
    user_data = {"first_name": "Alice", "last_name": "Smith", "email": "alice@example.com"}

    with patch.object(browser_mod, "async_playwright", return_value=mock_pw_instance):
        with pytest.raises(BlockedError):
            await run_autofill_job(job_data, user_data)


@pytest.mark.anyio
async def test_browser_blocked_error_on_missing_claim_url():
    """BlockedError is raised when claim_url is empty."""
    browser_mod, _ = _ensure_autofill_importable()
    BlockedError = browser_mod.BlockedError
    run_autofill_job = browser_mod.run_autofill_job

    mock_page = AsyncMock()
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.close = AsyncMock()
    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_browser.close = AsyncMock()
    mock_chromium = AsyncMock()
    mock_chromium.launch = AsyncMock(return_value=mock_browser)
    mock_pw_instance = AsyncMock()
    mock_pw_instance.chromium = mock_chromium
    mock_pw_instance.__aenter__ = AsyncMock(return_value=mock_pw_instance)
    mock_pw_instance.__aexit__ = AsyncMock(return_value=False)

    job_data = {"id": str(uuid.uuid4()), "claim_url": "", "settlement_title": ""}
    user_data = {}

    with patch.object(browser_mod, "async_playwright", return_value=mock_pw_instance):
        with pytest.raises(BlockedError, match="No claim URL provided"):
            await run_autofill_job(job_data, user_data)

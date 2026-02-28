# PayMe Agent Team Session Playbook

**Date:** 2026-02-22
**Purpose:** Coordinate parallel multi-agent (or multi-developer) build sessions on PayMe-Lite.
Each track is scoped so it can be executed in parallel by a dedicated agent or developer with minimal cross-track interference. This document is the single source of truth for session coordination.

---

## 1. Purpose

This file exists to let a team of agents (or humans) divide and conquer the next phase of PayMe development without stepping on each other. It defines:

- What is already done vs. what still needs to be built
- Exact file boundaries each track owns
- Contracts between tracks (inputs, outputs, shared tables)
- Coordination rules that prevent conflicts
- Acceptance criteria that must pass before a track is considered complete

---

## 2. System State Snapshot

### Infrastructure
- Docker Compose: `db`, `api`, `web`, `autofill-agent` services
- DB: PostgreSQL with pgvector, schema managed via Alembic
- Migrations through: `apps/api/alembic/versions/0001_initial.py` ... `0012_plaid_balance.py`
- Single model file: `apps/api/app/models/entities.py` — all SQLAlchemy models live here

### Auth
- JWT auth: `/auth/signup`, `/auth/login`, `/auth/me`
- User roles: `user`, `attorney`, `admin`, `super_user`

### Matching Engine
- Experiment variants: `rules_only`, `rules_vector`, `rules_vector_ranker`
- Persisted `match_runs` + `match_results`
- Ranker weights loaded from `artifacts/weights.json` at request time

### Track Status Summary

| Track | Name | Core Status | Remaining Work |
|-------|------|-------------|---------------|
| 1 | ML Feedback Loop | Implemented | Scheduled export, auto-retrain trigger, calibration metrics |
| 2 | Gmail Integration | Real OAuth + sync done | Consent UX, revoke UI, periodic scheduler, audit events |
| 3 | Plaid Integration | Real link/sync/disconnect done | Reconnect UI, balance display, periodic scheduler, webhooks |
| 4 | Autofill Agent | Worker + vision loop done | Real form patterns, artifact storage (S3), monitoring |
| 5 | Attorney Gateway & Payout | Mock payout full cycle done | Real ACH/Stripe, webhook confirmations, audit log exports |

---

## 3. Track Assignments

---

### Track 1: ML Feedback Loop

**Goal:** Close the ML learning loop — scheduled export of labeled samples, auto-retrain, calibration metrics, and drift alerting.

**Current state:**
- `ml_feedback_samples` table exists (migration `0005`)
- `export_labeled_samples()` materializes labeled training data from `match_results` + `user_settlement_preferences`
- `train_ranker.py` trains logistic regression on `artifacts/feedback_export.json`, outputs `artifacts/weights.json`
- Auto-promotion gate: new weights only replace active weights when `precision@5` strictly improves
- Drift detection: compares against `artifacts/metrics_prev.json`, warns on >5pp drop
- `ml_export_completed` event emitted on each export run

**Remaining work:**
1. Add a scheduled export job (cron or APScheduler inside `apps/workers/` or a new `apps/api/app/jobs/` module) that calls `export_labeled_samples()` nightly and writes `artifacts/feedback_export.json`
2. Add an auto-retrain trigger: after export, if labeled_count >= threshold (suggest 50), invoke `train_ranker.main()`
3. Add calibration metrics (Brier score, ECE) to `compute_metrics()` in `train_ranker.py`
4. Add an `ml_retrain_completed` event emitted after each training run with `promoted`, `weights_version`, and metric deltas
5. Add admin API endpoint `POST /admin/ml/retrain` that triggers training on demand (already partially wired — verify)

**Key files:**
```
apps/api/app/services/ml/feedback.py       # export_labeled_samples(), get_labeled_dataset()
scripts/train_ranker.py                    # training pipeline, promotion gate, drift detection
apps/api/app/services/matching/engine.py   # _load_ranker_weights(), match run execution
apps/api/app/api/routes/admin.py           # admin endpoints (retrain trigger lives here)
artifacts/                                 # weights.json, metrics.json, feedback_export.json
```

**Input contract:**
- `match_results` table populated by matching engine
- `user_settlement_preferences.claim_status` set by claim lifecycle events (`claim_submitted`, `claim_paid_out`, etc.)
- `events` table: `claim_submitted`, `claim_paid_out`, `claim_not_paid_out`

**Output contract:**
- `ml_feedback_samples` table upserted with `(user_id, settlement_id, label, outcome, features)`
- `artifacts/weights.json` updated only on promotion (contains `_version` key)
- `artifacts/metrics.json` reflects active model metrics
- Event emitted: `ml_export_completed`, `ml_retrain_completed`

**Acceptance criteria:**
- `export_labeled_samples()` runs without error against a seeded test DB
- `train_ranker.main()` completes and writes versioned artifacts
- When `precision@5` of new run < current, weights.json is NOT overwritten
- Drift warning fires when `precision@5` drops > 5pp vs `metrics_prev.json`
- `POST /admin/ml/retrain` returns 200 with `{promoted, weights_version, new_metrics}`
- All existing tests pass: `pytest apps/api/app/tests/test_matching.py`

---

### Track 2: Gmail Integration

**Goal:** Improve consent UX, add revoke/disconnect UI, add periodic sync scheduling, and emit data-access audit events.

**Current state:**
- Real OAuth flow: `GET /integrations/gmail/oauth/init` → redirect to Google → `GET /integrations/gmail/oauth/callback`
- Token exchange, encrypted storage in `gmail_oauth_tokens` (migration `0006`)
- Incremental sync via `history.list` (history-based delta), full initial sync for new connections
- Mock fallback: `MOCK_GMAIL=true` env var routes to fixture-based `gmail_sync.py`
- Events emitted: `gmail_oauth_granted`, `gmail_oauth_revoked`, `gmail_sync_started`, `gmail_sync_completed`, `gmail_sync_failed`
- Feature extraction writes `user_features` rows with `source='gmail'`

**Remaining work:**
1. Frontend consent UX: show connected email address, last sync timestamp, and data scope explanation before OAuth
2. Revoke/disconnect button in settings UI calling `DELETE /integrations/gmail/revoke`
3. Periodic sync scheduler: add `POST /integrations/gmail/sync` endpoint (already exists) to a cron job that fires every 6 hours for all users with active tokens
4. Add `gmail_data_accessed` event on every sync completion (include `user_id`, `messages_scanned`, timestamp) for privacy audit trail
5. Handle token expiry gracefully in the UI: surface a "reconnect Gmail" prompt when sync fails with `reason=credential_refresh_failed`

**Key files:**
```
apps/api/app/services/ingestion/gmail_real.py    # OAuth, token refresh, incremental sync
apps/api/app/services/ingestion/gmail_sync.py    # mock sync path (fixture-based)
apps/api/app/api/routes/integrations.py          # /gmail/oauth/init, /callback, /sync, /revoke
apps/web/src/pages/OnboardingPage.tsx            # Gmail connect step
apps/web/src/context/AppContext.tsx              # integration state
```

**Input contract:**
- Google OAuth credentials: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` in env
- `MOCK_GMAIL=true` bypasses real OAuth and uses fixture

**Output contract:**
- `gmail_oauth_tokens` row with encrypted `access_token_enc`, `refresh_token_enc`
- `gmail_messages` rows (one per message fetched)
- `gmail_evidence` rows (merchant/subscription evidence)
- `user_features` rows with `source='gmail'`
- `user.gmail_synced_at` updated on each sync

**Acceptance criteria:**
- `MOCK_GMAIL=true` path: sync endpoint returns `{status: ok, inserted_messages: N}` and writes `user_features`
- Real path: OAuth callback stores encrypted token, sync derives features
- Revoke endpoint marks token `revoked_at`, emits `gmail_oauth_revoked`
- After revoke, sync returns 400 with reason `token_revoked`
- Mock path never broken even when `MOCK_GMAIL` is unset (check graceful fallback)
- All existing tests pass

---

### Track 3: Plaid Integration

**Goal:** Add reconnect/reauth UI flow, improve balance display, add periodic sync scheduling, and handle Plaid webhooks.

**Current state:**
- Real Plaid Link token creation: `POST /integrations/plaid/link-token`
- Public token exchange: `POST /integrations/plaid/exchange`
- Cursor-based incremental sync via `/transactions/sync`: `POST /integrations/plaid/sync`
- Disconnect: `DELETE /integrations/plaid/disconnect` calls Plaid `/item/remove`
- `ITEM_LOGIN_REQUIRED` detected → sets `plaid_items.status = 'requires_reauth'`, emits `plaid_reauth_required`
- Mock fallback: `MOCK_PLAID=true` routes to fixture-based `plaid_sync.py`
- Events: `plaid_item_linked`, `plaid_sync_started`, `plaid_sync_completed`, `plaid_sync_failed`, `plaid_item_disconnected`, `plaid_reauth_required`

**Remaining work:**
1. Reconnect/reauth UI: when `plaid_items.status = 'requires_reauth'`, surface a "Reconnect bank" prompt in settings that re-launches Plaid Link with the existing item's update mode
2. Balance display: use `plaid_balance` data (migration `0012`) to show account balance on dashboard/settings
3. Periodic sync scheduler: add a job that syncs all users with active Plaid items every 12 hours
4. Webhook handler: add `POST /integrations/plaid/webhook` endpoint that handles `TRANSACTIONS_SYNC_UPDATES_AVAILABLE` and `ITEM_LOGIN_REQUIRED` Plaid webhook events
5. Webhook signature verification using `PLAID_WEBHOOK_SECRET`

**Key files:**
```
apps/api/app/services/ingestion/plaid_real.py    # link token, exchange, sync, disconnect, reauth
apps/api/app/services/ingestion/plaid_sync.py    # mock sync path (fixture-based)
apps/api/app/api/routes/integrations.py          # /plaid/* endpoints
apps/web/src/pages/OnboardingPage.tsx            # Plaid Link step
apps/web/src/context/AppContext.tsx              # integration state
```

**Input contract:**
- `PLAID_CLIENT_ID`, `PLAID_SECRET`, `PLAID_ENV` (sandbox/development/production) in env
- `MOCK_PLAID=true` bypasses real Plaid
- Plaid webhook events delivered to `POST /integrations/plaid/webhook`

**Output contract:**
- `plaid_items` row with encrypted `access_token_enc`, cursor
- `plaid_transactions` rows
- `user_features` rows with `source='plaid'`
- `user.plaid_synced_at` updated on sync

**Acceptance criteria:**
- `MOCK_PLAID=true`: sync writes `user_features` rows with `source='plaid'`
- Real path: link token created, public token exchanged, transactions sync writes features
- `ITEM_LOGIN_REQUIRED`: status set to `requires_reauth`, event emitted
- Disconnect: `plaid_items.status = 'disconnected'`, event emitted
- Webhook endpoint returns 200 for known event types, 400 for invalid signature
- Mock path never broken even when `MOCK_PLAID` is unset
- All existing tests pass

---

### Track 4: Autofill Agent

**Goal:** Productionize browser automation — handle more real form patterns, add artifact storage to S3 (or local volume), and add monitoring/alerting for blocked rate.

**Current state:**
- Worker polling loop: `apps/autofill-agent/autofill/worker.py`
  - `FOR UPDATE SKIP LOCKED` job claiming
  - Retry with exponential backoff (configurable `max_retries`, `retry_delay`)
  - States: `queued → running → done | blocked | failed`
- Browser automation: `apps/autofill-agent/autofill/browser.py`
  - `nodriver` (Chromium, bypasses Cloudflare Turnstile)
  - Vision-LLM loop: screenshot → Claude Haiku vision → JS execution → repeat
  - React-compatible form fill helpers injected as JS (`_setInputValue`, `_setSelectValue`, etc.)
  - Confirmation detection via text pattern matching
- DB tables: `autofill_jobs`, `autofill_job_steps`, `autofill_artifacts` (migration `0008`)
- API routes: `POST /autofill/jobs`, `GET /autofill/jobs`, `GET /autofill/jobs/{job_id}`
- Events: `autofill_job_queued`, `autofill_job_started`, `autofill_step_completed`, `autofill_job_done`, `autofill_job_blocked`, `autofill_job_failed`

**Remaining work:**
1. Real form detection improvements: expand JS helper patterns for multi-step wizards, iframe-embedded forms, and address autocomplete fields
2. Artifact storage backend: implement S3 upload in `browser.py` (or a post-step hook in `worker.py`) so screenshots persist beyond local container; fall back to local volume when `AUTOFILL_S3_BUCKET` is not set
3. Blocked rate monitoring: add an admin endpoint `GET /admin/autofill/stats` that returns `{total_jobs, done, blocked, failed, blocked_rate}` per time window; alert if `blocked_rate > 0.3`
4. Expose artifact download: add `GET /autofill/jobs/{job_id}/artifacts/{storage_key}` endpoint that serves local files or redirects to S3 presigned URL
5. Add `AUTOFILL_ENABLED` env flag — if false, `POST /autofill/jobs` returns 503 with a clear message so the feature can be toggled without a deploy

**Key files:**
```
apps/autofill-agent/autofill/worker.py      # polling loop, job lifecycle, step/artifact persistence
apps/autofill-agent/autofill/browser.py     # nodriver + Claude vision loop, form fill helpers
apps/autofill-agent/autofill/settings.py    # WorkerSettings (Pydantic settings)
apps/api/app/api/routes/autofill.py         # POST /autofill/jobs, GET /autofill/jobs/*
apps/api/app/services/autofill/service.py   # enqueue_job, get_job, list_jobs, list_steps
```

**Input contract:**
- `POST /autofill/jobs` body: `{settlement_id: UUID}`
- Settlement must have a non-null `claim_url`
- Worker reads user profile from `GET /admin/users/{user_id}` (internal API call)
- `ANTHROPIC_API_KEY` env var required by `browser.py`

**Output contract:**
- `autofill_jobs` row with terminal status `done | blocked | failed`
- `autofill_job_steps` rows: `navigate`, `fill_form`, `screenshot`, `submit` at minimum
- `autofill_artifacts` row for each screenshot with `storage_key` pointing to file path or S3 key
- On success: `submit.confirmed = true` in step output JSON

**Acceptance criteria:**
- `POST /autofill/jobs` with valid `settlement_id` creates a job in `queued` state
- Worker claims and transitions job through `running → done`
- Blocked job sets `status='blocked'`, records reason in `error_message`
- Failed job after max retries sets `status='failed'`
- `GET /autofill/jobs/{job_id}` returns steps and artifact keys
- No active duplicate jobs for the same `(user_id, settlement_id)` — 409 returned
- All existing tests pass

---

### Track 5: Attorney Gateway and Payout Flow

**Goal:** Replace mock payout simulation with real ACH bank transfers (Plaid Transfer API), add webhook confirmation handling, and add audit log export.

**Current state:**
- Attorney registration: `POST /gateway/register` → `AttorneyAccount` + hashed API key
- Settlement account linking: `POST /gateway/settlement-account` → `SettlementAccount` with encrypted `account_ref_enc`
- Claimant approval/rejection: `POST /gateway/approve`, `POST /gateway/reject`
- Payout batch create + execute: `POST /gateway/payout-batch`, `POST /gateway/payout-batch/{id}/execute`
- Mock execution: deterministic 90% success via SHA-256 hash of `idempotency_key`
- Real Plaid transfer path gated by `PLAID_PAYOUTS_ENABLED=true` env flag
- Reconciliation: `GET /gateway/payout-batch/{id}/reconciliation`
- Payout history: `GET /gateway/payout-history`
- Account balance: `GET /gateway/balance` (sandbox: fixed $100k)
- States: `matched → submitted → approved → paid_out`
- All writes are idempotent via `idempotency_key` on `payout_batches` and `payout_transfers`

**Remaining work:**
1. Real ACH integration: when `PLAID_PAYOUTS_ENABLED=true`, `_execute_plaid_transfer()` in `payout_service.py` already calls `/transfer/authorization/create` + `/transfer/create`; validate end-to-end in Plaid sandbox and add error handling for authorization declines
2. Webhook confirmation: add `POST /gateway/webhooks/plaid` endpoint that receives Plaid Transfer webhook events (`TRANSFER_EVENTS_UPDATE`) and updates `payout_transfers.status` from `processing → completed | failed`
3. Audit log export: add `GET /gateway/audit-log?settlement_id=&start=&end=` endpoint that returns a paginated, time-ordered list of all gateway events from the `events` table for attorney-owned settlements
4. Settlement Q&A UI polish: wire `apps/api/app/services/settlements/questions_service.py` to the frontend settlement detail page for the Q&A tab
5. Real balance: when `PLAID_PAYOUTS_ENABLED=true`, replace sandbox fixed balance with a real call to `/accounts/get` on the attorney's source account

**Key files:**
```
apps/api/app/services/gateway/attorney_service.py  # registration, account linking, approval/rejection
apps/api/app/services/gateway/payout_service.py    # batch create, execute, reconciliation, history
apps/api/app/api/routes/gateway.py                 # all /gateway/* endpoints
apps/api/app/models/entities.py                    # AttorneyAccount, SettlementAccount, ClaimApproval, PayoutBatch, PayoutTransfer
```

**Input contract:**
- Attorney JWT: user must have `role='attorney'` and an active `AttorneyAccount` record
- `POST /gateway/payout-batch/{id}/execute`: requires a queued `PayoutBatch` with `status='queued'`
- `PLAID_PAYOUTS_ENABLED=true` to activate real ACH path

**Output contract:**
- `payout_transfers` rows with terminal status `completed | failed`
- `claim_approvals.status` updated to `paid | failed`
- `user_settlement_preferences.claim_status` set to `paid_out` on successful transfer
- Events: `payout_batch_created`, `payout_transfer_completed`, `payout_transfer_failed`, `payout_batch_completed`

**Acceptance criteria:**
- Attorney can register, link a settlement account, approve claimants, and execute payouts in sequence
- Payout is idempotent: re-sending same `idempotency_key` returns existing batch without duplicate transfers
- On mock path (default): ~90% transfers succeed, ~10% fail, both recorded correctly
- `user_settlement_preferences.claim_status = 'paid_out'` after successful transfer
- Reconciliation report accurately reflects final counts and amounts
- Real Plaid path: `PLAID_PAYOUTS_ENABLED=true` attempts real sandbox transfer, handles authorization decline gracefully
- All existing tests in `test_managed_settlements.py` pass

---

## 4. Dependency Map

```
Track 1 (ML)
  depends on:
    Track 2 (Gmail)   — needs user_features rows (source='gmail') for meaningful training data
    Track 3 (Plaid)   — needs user_features rows (source='plaid') for feature diversity
    Track 5 (Gateway) — needs claim_status='paid_out' outcomes to generate positive labels

Track 4 (Autofill)
  depends on:
    Track 2/3         — user profile data enriched by integration features
    Track 5           — settlement must be in a state where a claim URL exists

Track 5 (Gateway)
  depends on:
    claim_status lifecycle being set by user-facing claim events (independent of other tracks)
    user.plaid_synced_at for real payout destination resolution (soft dependency on Track 3)

Track 2 (Gmail) <--> Track 3 (Plaid)
  These two tracks are independent of each other.
```

**Critical path for Track 1:**
Tracks 2 and 3 must produce `user_features` rows with real or mock data, and Track 5 must set at least some `claim_status='paid_out'` rows before Track 1 can generate a meaningful labeled dataset for training. The mock/seed path (large_test_user) can be used to bootstrap this without requiring production data.

---

## 5. Coordination Rules

### 5.1 Schema Changes

1. **All schema changes must go through Alembic.** Never alter table structure by editing `entities.py` alone.
   ```
   # Generate migration inside the api container
   docker compose exec api alembic revision --autogenerate -m "your_description"
   docker compose exec api alembic upgrade head
   ```
   Next migration number: `0013_*`

2. **`entities.py` is the single model file** — `apps/api/app/models/entities.py`. Changes to this file affect all tracks. Coordinate before modifying it:
   - Check the dependency map above before adding/removing columns
   - Add columns as nullable with a default to avoid breaking existing rows
   - Never rename columns directly — add the new column, migrate data, remove the old one

3. **`entities.py` ownership per session:** Designate one agent as the schema owner. Other agents must open a coordination message before modifying `entities.py`. Concurrent edits are not allowed.

### 5.2 Events Table

4. **Events table is append-only.** Never `UPDATE` or `DELETE` rows from the `events` table. New event types must be documented here:

   | Track | New Event Type | Payload Keys |
   |-------|---------------|--------------|
   | 1 | `ml_retrain_completed` | `promoted`, `weights_version`, `precision_at_5`, `sample_count` |
   | 2 | `gmail_data_accessed` | `user_id`, `messages_scanned`, `timestamp` |
   | 3 | `plaid_reauth_completed` | `user_id`, `item_id` |
   | 4 | (existing events sufficient) | — |
   | 5 | `payout_webhook_received` | `event_type`, `transfer_id`, `status` |

### 5.3 Test Isolation

5. **Tests use `payme_test` schema** in the same DB instance. Do not modify test fixtures without first reviewing all `apps/api/app/tests/test_*.py` files that use them.
   - Fixture files: `fixtures/gmail/sample_messages.json`, `fixtures/plaid/transactions.json`
   - Seed script: `scripts/seed_settlements.py`
   - If you update a fixture, run both backend and frontend tests immediately to confirm nothing breaks.

6. **Each test file uses isolated transactions** — rely on the existing test DB setup and do not introduce global state in tests.

### 5.4 Mock Fallback Preservation

7. **Mock modes (`MOCK_GMAIL`, `MOCK_PLAID`) must remain functional at all times.**
   - Never delete `gmail_sync.py` or `plaid_sync.py`
   - Never remove the `if MOCK_GMAIL` / `if MOCK_PLAID` branching in `integrations.py`
   - After any change to the real integration path, verify the mock path still works with `MOCK_GMAIL=true` / `MOCK_PLAID=true`

### 5.5 Security Rules

8. **Access tokens (Gmail OAuth, Plaid) must always be encrypted before storage.**
   Use `app.core.crypto.encrypt_token()` before any DB write and `decrypt_token()` before any API call.
   Never log decrypted token values.

9. **Payout operations must be idempotent.** Every `PayoutBatch` and `PayoutTransfer` write must check for an existing row by `idempotency_key` before inserting. The pattern is already established in `payout_service.py` — follow it for any new payout-adjacent writes.

### 5.6 Agent Team File Discipline

10. **One agent per track.** Each agent works primarily in the files listed under its track's "Key files" section.

11. **Agents must not modify another track's primary service files** without a coordination step. Shared files (`entities.py`, `integrations.py`, `events/service.py`) require explicit cross-track coordination.

12. **Write to separate feature branches per track.** Suggested naming: `track-1/ml-scheduled-export`, `track-2/gmail-consent-ux`, etc. Merge to `main` only after acceptance criteria pass.

---

## 6. Testing Requirements

### Backend Tests

All backend tests must pass before any track branch is merged.

```bash
docker compose exec -T api sh -lc 'cd /workspace/apps/api && pytest -q'
```

Key test files per track:

| Track | Primary Test File |
|-------|------------------|
| 1 | `apps/api/app/tests/test_matching.py` |
| 2 | `apps/api/app/tests/test_matching.py` (integration sync path) |
| 3 | `apps/api/app/tests/test_matching.py` (integration sync path) |
| 4 | (add `apps/api/app/tests/test_autofill.py` if not present) |
| 5 | `apps/api/app/tests/test_managed_settlements.py` |

All test files live in: `apps/api/app/tests/`

### Frontend Tests + Build

```bash
docker compose exec -T web sh -lc 'cd /workspace/apps/web && npm run test && npm run build'
```

Frontend tests must pass and the production build must succeed.

### Test Checklist Per Track Change

Before marking any sub-task done, verify:

- [ ] `pytest -q` exits 0
- [ ] `npm run test` exits 0
- [ ] `npm run build` exits 0
- [ ] New event types added to the events table list in Section 5.2
- [ ] Any new env vars documented in `.env.example`
- [ ] Any new DB columns added via Alembic migration (not raw DDL)
- [ ] Mock fallback (`MOCK_GMAIL`, `MOCK_PLAID`) still returns valid responses

---

## 7. Known Constraints

These constraints are hard guardrails — do not work around them.

1. **Tests use isolated schema (`payme_test`)** in the same DB instance as production. Tests must not write to the `public` schema and must clean up after themselves. Do not bypass the test schema isolation.

2. **Mock integrations must remain available.** While real Gmail/Plaid implementations are developed, `MOCK_GMAIL=true` and `MOCK_PLAID=true` must always function as a complete fallback for local/dev/test environments. The fixture-based sync paths (`gmail_sync.py`, `plaid_sync.py`) are permanent fixtures of the codebase.

3. **Do not scan raw Gmail/Plaid rows at request time.** Feature extraction runs during ingestion and writes to `user_features`. The matching engine reads only from `user_features` and `settlement_feature_index`. Adding joins to `gmail_messages` or `plaid_transactions` at match time is forbidden.

4. **All payout operations must be strongly idempotent and fully auditable.**
   - Every `PayoutBatch` insert: guarded by `idempotency_key` uniqueness check
   - Every `PayoutTransfer` insert: keyed as `transfer:{batch_id}:{approval_id}`
   - All state transitions emit events to the append-only `events` table
   - No payout-adjacent row may be deleted; terminal states are final

5. **Autofill browser workers must record deterministic progress and failure reasons.**
   Every step (navigate, fill_form, screenshot, submit) must produce an `autofill_job_steps` row with a non-null `status`. `BlockedError` must be caught and recorded as `status='blocked'` with `error_message` explaining the block reason.

6. **`entities.py` is the single model file.** Do not create additional model files or import models from anywhere other than `app.models.entities`. The autofill worker imports these same entities at runtime.

7. **Access token encryption is mandatory.** `encrypt_token()` before write, `decrypt_token()` before use. This applies to: Gmail OAuth tokens (`gmail_oauth_tokens`), Plaid access tokens (`plaid_items`), and settlement account references (`settlement_accounts`).

---

## 8. Quick Reference: Key Commands

```bash
# Start the stack
cp .env.example .env
docker compose up --build

# Start with alternate ports (e.g. avoid conflicts)
API_PORT=18000 WEB_PORT=15173 DB_PORT=15432 docker compose up --build

# Run backend tests
docker compose exec -T api sh -lc 'cd /workspace/apps/api && pytest -q'

# Run frontend tests + build
docker compose exec -T web sh -lc 'cd /workspace/apps/web && npm run test && npm run build'

# Generate a new Alembic migration
docker compose exec api alembic revision --autogenerate -m "0013_your_description"

# Apply migrations
docker compose exec api alembic upgrade head

# Seed the large test user
docker compose exec api python scripts/seed_settlements.py

# Train ranker manually
docker compose exec api python scripts/train_ranker.py

# Run a single test file
docker compose exec -T api sh -lc 'cd /workspace/apps/api && pytest -q app/tests/test_matching.py'

# Tail API logs
docker compose logs -f api

# Tail autofill worker logs
docker compose logs -f autofill-agent
```

### Large Test User
- Username: `large_test_user`
- Email: `large_test_user@example.com`
- Password: value of `MOCK_PROVISION_PASSWORD` in `.env`

---

## 9. Environment Variables Reference

Variables that must be set for each track's real (non-mock) path:

| Variable | Track | Purpose |
|----------|-------|---------|
| `GOOGLE_CLIENT_ID` | 2 | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | 2 | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | 2 | OAuth callback URL |
| `MOCK_GMAIL` | 2 | Set `true` to use fixture-based sync |
| `PLAID_CLIENT_ID` | 3 | Plaid API client ID |
| `PLAID_SECRET` | 3 | Plaid API secret |
| `PLAID_ENV` | 3 | `sandbox` / `development` / `production` |
| `MOCK_PLAID` | 3 | Set `true` to use fixture-based sync |
| `PLAID_PAYOUTS_ENABLED` | 5 | Set `true` to activate real Plaid ACH path |
| `ANTHROPIC_API_KEY` | 4 | Claude API key for vision-LLM in autofill worker |
| `AUTOFILL_S3_BUCKET` | 4 | Optional S3 bucket for screenshot artifacts |
| `GATEWAY_API_KEY_SALT` | 5 | Salt for attorney API key hashing |
| `SECRET_KEY` | all | App secret for JWT and token encryption |
| `MOCK_PROVISION_PASSWORD` | all | Password for seeded test users |

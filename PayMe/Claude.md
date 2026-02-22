# Claude Handoff: PayMe-Lite

## Project snapshot

PayMe-Lite is a mock-first settlement matching prototype.

Current user flow:
1. Sign up / log in
2. Complete onboarding
3. Connect Gmail and bank (or skip)
4. See ranked matches
5. Open claim forms, confirm submission, track claim progress

Key UX now live:
- Matches page has tabs: `Matches` and `Ongoing Claims`
- Single bottom CTA: `Find New Settlements` (reruns match)
- Settlement details include back button and claim progress block

---

## Tech and architecture

- Frontend: React + TypeScript + Vite
- Backend: FastAPI + Pydantic + SQLAlchemy
- DB: PostgreSQL (+ pgvector extension enabled)
- Infra: Docker Compose (`db`, `api`, `web`)
- Migrations: Alembic
- Tests: Pytest + Vitest/RTL

Architecture shape:
- routes -> services -> persistence
- request-time matching reads `user_features` + indices only
- ingestion jobs (Gmail/Plaid) update derived features asynchronously through API-triggered sync flows

---

## Implemented capabilities

### Auth and session
- JWT auth endpoints: `/auth/signup`, `/auth/login`, `/auth/me`
- Session persistence in frontend context (`AppContext`)

### Matching engine
- Deterministic experiment routing (`rules_only`, `rules_vector`, `rules_vector_ranker`)
- Persisted `match_runs` + `match_results`
- Pinned-first ordering, then score descending

### Integrations (currently mock-first)
- Gmail sync endpoint reads fixture and derives evidence/features
- Plaid sync endpoint reads fixture and derives transaction features

### Admin observability
- Admin endpoints for users, settlements, overview stats, per-user stats, events
- Frontend admin dashboard wired to those endpoints

### Claim tracking
- Endpoints:
  - `POST /settlements/{id}/claim/opened`
  - `POST /settlements/{id}/claim/submitted`
  - `POST /settlements/{id}/claim/outcome`
  - `GET /claims/ongoing`
- Event stream:
  - `claim_form_opened`
  - `claim_submitted`
  - `claim_paid_out`
  - `claim_not_paid_out`
- Match + settlement detail payloads include claim status timestamps

---

## Core data tables to know

- `users`
- `settlements`
- `settlement_feature_index`
- `user_features`
- `match_runs`
- `match_results`
- `user_settlement_preferences` (pin + claim lifecycle fields)
- `events`
- `experiment_exposures`
- `gmail_messages`, `gmail_evidence`
- `plaid_transactions`

Claim lifecycle fields live on `user_settlement_preferences`:
- `claim_status`
- `claim_submitted_at`
- `claim_outcome_at`
- `claim_feedback_json`

---

## Agent Team Session: Target Workstreams

The next phase is a multi-agent build. These are the primary tracks:

### Track 1: Matching ML feedback loop (productionized)
- Define training dataset contract from events + outcomes
- Add export endpoint/job for labeled samples (features + context + outcome)
- Add offline training pipeline and evaluation job (`precision@k`, calibration, drift)
- Add safe weight publish path and runtime rollout strategy
- Add tests for data integrity, reproducibility, and no-label leakage

### Track 2: Real Gmail integration
- OAuth flow + token storage + refresh handling
- Incremental sync strategy and ingestion jobs
- Feature extraction from real messages with privacy controls
- Consent UX, revoke/disconnect, and audit events
- Mock mode remains as fallback for local/dev/test

### Track 3: Real Plaid integration
- Link token, public token exchange, access token management
- Account + transaction sync (initial + incremental)
- Feature extraction into `user_features`
- Reconnect/reauth/error states + observability
- Preserve mock mode fallback for local/dev/test

### Track 4: New autofill agent service
- New service (queue worker) that consumes autofill jobs
- Reads user profile + settlement context from API/DB
- Uses browser automation to open claim sites and fill forms
- Logs progress and step-level outcomes (`queued`, `running`, `blocked`, `done`, `failed`)
- Writes execution artifacts and emits events for traceability

### Track 5: Settlement gateway + payout flow
- Attorney-facing workflow to link settlement bank account
- New approval pipeline/table for users approved by attorneys
- Payout execution workflow from attorney account to approved claimants
- Clear states: `matched -> submitted -> approved -> paid`
- Full reconciliation, audit logs, and idempotent payouts

---

## Suggested service additions (next)

- `apps/autofill-agent` (new worker service)
- Optional future:
  - `apps/gateway` (attorney/ops API boundary)
  - `apps/workers` (scheduled sync/training/export jobs)

Potential new tables:
- `autofill_jobs`, `autofill_job_steps`, `autofill_artifacts`
- `attorney_accounts`, `settlement_accounts`
- `claim_approvals`, `payout_batches`, `payout_transfers`
- `ml_feedback_samples` (or materialized export view)

---

## Runbook

### Start app
```bash
cp .env.example .env
docker compose up --build
```

If ports conflict:
```bash
API_PORT=18000 WEB_PORT=15173 DB_PORT=15432 docker compose up --build
```

### Large test user
- Username: `large_test_user`
- Email: `large_test_user@example.com`
- Password: from `.env` (`MOCK_PROVISION_PASSWORD`)

### Run tests
Backend:
```bash
docker compose exec -T api sh -lc 'cd /workspace/apps/api && pytest -q'
```

Frontend:
```bash
docker compose exec -T web sh -lc 'cd /workspace/apps/web && npm run test && npm run build'
```

---

## Known constraints and guardrails

1. Tests use isolated schema (`payme_test`) in same DB instance; do not bypass.
2. Keep mock integrations available while real Gmail/Plaid are developed.
3. Avoid scanning raw Gmail/Plaid rows at request-time; derive and consume `user_features`.
4. All payout-related operations must be strongly idempotent and fully auditable.
5. Any autofill browser worker must record deterministic progress and failure reasons.

---

## Recommended starting points for contributors

- Matching + claims:
  - `apps/api/app/services/matching/`
  - `apps/api/app/api/routes/matching.py`
- Integrations:
  - `apps/api/app/services/ingestion/gmail_sync.py`
  - `apps/api/app/services/ingestion/plaid_sync.py`
- Frontend orchestration:
  - `apps/web/src/context/AppContext.tsx`
  - `apps/web/src/pages/MatchesPage.tsx`
  - `apps/web/src/pages/SettlementDetailPage.tsx`

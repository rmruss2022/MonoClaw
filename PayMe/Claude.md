# Claude Handoff: PayMe-Lite

## What this app is

PayMe-Lite is a mock-first prototype that helps users find class-action settlements they are likely eligible for.

Core user flow:
1. Sign up / log in
2. Complete onboarding profile
3. Optionally connect Gmail + bank (mock integrations)
4. Run matching
5. Review ranked settlements, pin items, open claim forms

The app now also tracks claim feedback:
- Opening a claim form triggers an in-app confirmation modal
- If user confirms submission, the claim moves into ongoing claims
- Ongoing claims can be marked `paid_out` or `not_paid_out`
- Claim lifecycle emits events with match context for ML feedback signals

---

## Stack and architecture

- Frontend: React + TypeScript + Vite
- Backend: FastAPI + Pydantic + SQLAlchemy
- DB: PostgreSQL (pgvector enabled)
- Migrations: Alembic
- Infra: Docker Compose (`db`, `api`, `web`)
- Testing: Pytest (API), Vitest + RTL (web)

Backend is layered:
- routes -> services -> persistence/model layer
- request-time matching reads only `user_features` and settlement indices (not raw Gmail/Plaid rows)

---

## Important features currently implemented

### 1) Auth + session
- JWT auth (`/auth/signup`, `/auth/login`, `/auth/me`)
- Session persistence in frontend via context + local token hydration
- Route guards for public/protected pages

### 2) Onboarding + feature derivation
- Onboarding writes user profile and onboarding-derived `user_features`
- Brand selections create features like `merchant:amazon`

### 3) Mock Gmail + Plaid ingest
- `MOCK_GMAIL=true` and `MOCK_PLAID=true` read fixture files
- Dedupe inserts and derive evidence/features
- Sync updates user sync timestamps and feature set

### 4) Matching engine
- Match pipeline supports deterministic experiment variant routing
- Persists `match_runs` + `match_results`
- Results are ordered with pinned items first, then score
- UI shows summary, accuracy %, payout, deadline, states, claim links

### 5) Admin observability
- Admin APIs and frontend admin page for:
  - users
  - settlements
  - overview stats
  - user stats
  - events

### 6) Claim tracking + ML feedback loop
- New claim lifecycle endpoints:
  - `POST /settlements/{id}/claim/opened`
  - `POST /settlements/{id}/claim/submitted`
  - `POST /settlements/{id}/claim/outcome` (`paid_out` | `not_paid_out`)
  - `GET /claims/ongoing`
- Match results now include claim status fields
- Events emitted:
  - `claim_form_opened`
  - `claim_submitted`
  - `claim_paid_out`
  - `claim_not_paid_out`
- Event payload includes match context (`run_id`, `score`, `score_bucket`) for downstream training/analysis

---

## Data model notes (high-value tables)

- `users`
- `settlements`
- `settlement_feature_index`
- `user_features`
- `match_runs`
- `match_results`
- `user_settlement_preferences` (includes pinning + claim status fields)
- `events`
- `experiment_exposures`
- `gmail_messages` + `gmail_evidence`
- `plaid_transactions`

Claim tracking columns live in `user_settlement_preferences`:
- `claim_status`
- `claim_submitted_at`
- `claim_outcome_at`
- `claim_feedback_json`

Migration: `apps/api/alembic/versions/0004_claim_feedback.py`

---

## Frontend state model

App-wide state is centralized in:
- `apps/web/src/context/AppContext.tsx`

It handles:
- auth/session
- matches and sync actions
- admin data
- claim modal state
- ongoing claims and outcome updates

Global shell with nav + modal mount point:
- `apps/web/src/components/AppShell.tsx`

Claim confirmation modal:
- `apps/web/src/components/ClaimSubmissionModal.tsx`

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

### Default large test user
- Username: `large_test_user`
- Email: `large_test_user@example.com`
- Password comes from `.env` (`MOCK_PROVISION_PASSWORD`)

### Force migrations
```bash
docker compose exec -T api sh -lc 'cd /workspace/apps/api && alembic upgrade head'
```

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

## Operational gotchas

1. Backend tests are schema-isolated in the same Postgres instance (`TEST_DB_SCHEMA=payme_test`) to protect live dev data.
2. If frontend shows `Failed to fetch` after new DB fields are added, run Alembic migrations in the API container.
3. Claim flow relies on `window.open` + immediate in-app modal; popup blockers can affect the external tab behavior.
4. Fixture size affects sync payload volume for any user who runs sync (signup alone does not auto-ingest large fixtures).

---

## Where to start if continuing development

1. Read `README.md` for setup and feature-level docs.
2. Start from `apps/api/app/api/routes/matching.py` + `apps/api/app/services/matching/`.
3. In frontend, begin with `apps/web/src/context/AppContext.tsx` then `MatchesPage` and `SettlementCard`.
4. Validate quickly with:
   - log in as `large_test_user`
   - open claim form -> confirm submitted -> mark outcome
   - verify events in admin page.

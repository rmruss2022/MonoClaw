# PayMe-Lite

PayMe-Lite is a mock-first prototype that helps users discover class action settlements they likely qualify for.  
Core flow: sign up -> onboarding profile -> connect Gmail/Bank (or skip with warning) -> first match -> ranked settlements with grounded explanations.

## Stack

- Frontend: React + TypeScript + Vite
- Backend: FastAPI + Pydantic + SQLAlchemy
- DB: PostgreSQL (+ pgvector extension enabled in init script)
- Migrations: Alembic
- Infra: Docker Compose
- Tests: Pytest, Vitest + RTL

## Repo Layout

- `apps/api` - API, services, routes, models, tests, Alembic
- `apps/web` - React app pages/components/tests
- `docker/postgres/init.sql` - enables pgvector extension
- `fixtures/gmail` - mock Gmail fixture payloads
- `fixtures/plaid` - mock bank transaction fixtures
- `scripts` - seed, provisioning, backup, synthetic data generation, ranker training

## Quick Start

1. Create env file:

```bash
cp .env.example .env
```

2. Start all services:

```bash
docker compose up --build
```

If local ports are in use, override with env vars (example):

```bash
API_PORT=18000 WEB_PORT=15173 DB_PORT=15432 docker compose up --build
```

3. Open:
- Web: `http://localhost:5173`
- API: `http://localhost:8000`

Default seeded large test user (auto-provisioned on first boot):
- Username: `large_test_user`
- Email: `large_test_user@example.com`
- Password: `PayMe2026!` (or the value of `MOCK_PROVISION_PASSWORD`)

## API Flow

1. `POST /auth/signup` or `POST /auth/login`
2. `POST /onboarding` writes profile + onboarding-derived user features
3. Frontend onboarding sync step runs:
   - `POST /integrations/gmail/sync`
   - `POST /integrations/plaid/sync`
   - or user clicks Skip
4. `POST /match/run` persists `match_runs` + `match_results`
5. `GET /match/results` returns latest ranked list (pinned first)

## Matching Pipeline

Request-time matching reads only `user_features` and settlement indices (never raw Gmail rows):

1. **Rules candidate generation** (`settlement_feature_index` + predicates)
2. **Variant routing** (`rules_only`, `rules_vector`, `rules_vector_ranker`)
3. **Ranking** with weighted score (loads `artifacts/weights.json` when present)
4. Persist run/result rows for reproducibility and explainability

Each match returns:
- `reasons_json` (matched features + confidence breakdown)
- `missing_features_json`

## A/B Routing

Deterministic variant assignment:
- hash(`user_id:experiment_key`) % 3
- mapped to `rules_only`, `rules_vector`, `rules_vector_ranker`

Exposure is persisted once in `experiment_exposures` and event `experiment_exposed` is emitted.

## Mock vs Real Integrations

- `MOCK_GMAIL=true`: uses `fixtures/gmail/sample_messages.json`
  - inserts deduped `gmail_messages`
  - derives `gmail_evidence`
  - updates `user_features` (`source=gmail`)
- `MOCK_GMAIL=false`: explicit not-implemented boundary response (OAuth stub)
- `MOCK_PLAID=true`: uses `fixtures/plaid/transactions.json`
  - inserts deduped `plaid_transactions`
  - derives merchant/category/subscription features
  - updates `user_features` (`source=plaid`)
- `MOCK_PLAID=false`: explicit not-implemented boundary response (Plaid OAuth/link stub)

## Logging + Analytics

- Structured request logs to stdout + JSONL file (`LOG_FILE_PATH`, default `/tmp/payme-app.jsonl`)
- Request ID middleware sets `x-request-id` on every response
- Product events persisted in `events` table
- Admin endpoints:
  - `GET /admin/events?limit=&type=&user_id=`
  - `GET /admin/logs/tail?n=200` (only when `ADMIN_DEBUG=true`)
  - `GET /admin/users?limit=&offset=`
  - `GET /admin/users/{id}`
  - `GET /admin/settlements?limit=&offset=`
  - `GET /admin/settlements/{id}`
  - `GET /admin/stats/overview`
  - `GET /admin/stats/users/{id}`

Frontend admin panel:
- `http://localhost:5173/admin` (same env gate behavior)

## Tests

Backend:

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
```

Test isolation note:
- Backend tests use the same Postgres instance but force a dedicated schema (`TEST_DB_SCHEMA`, default `payme_test`).
- This keeps tests from touching live app data and drops the test schema at the end of the test session.

Frontend:

```bash
cd apps/web
npm install
npm run test
```

## Seeding Settlements

`scripts/seed_settlements.py` seeds 20 detailed mock settlements and refreshes feature index rows idempotently.

## Large Mock Data Provisioning

Generate large Gmail fixtures:

```bash
python scripts/generate_mock_gmail_fixtures.py --count 1000
```

Generate large Plaid fixtures:

```bash
python scripts/generate_mock_plaid_fixtures.py --count 1000
```

Provision/rebuild large test user data (on demand):

```bash
python scripts/provision_large_test_user.py --emails 1000 --transactions 1000
```

Auto-provision runs on container startup in `docker-compose.yml`.

Configure startup mock provisioning via `.env`:

```env
PROVISION_LARGE_TEST_USER=true
MOCK_PROVISION_USERNAME=large_test_user
MOCK_PROVISION_EMAIL=large_test_user@example.com
MOCK_PROVISION_PASSWORD=password123
MOCK_PROVISION_EMAILS=1000
MOCK_PROVISION_TRANSACTIONS=1000
```

Important behavior:
- Signup itself does **not** generate 1000 mock rows.
- The onboarding sync actions (`/integrations/gmail/sync`, `/integrations/plaid/sync`) ingest from fixture files.
- If fixture files are 1000-row fixtures, any user who runs sync can ingest up to that size.

## Backups and Restore

Create SQL backup:

```bash
scripts/backup_db.sh
```

Restore latest backup:

```bash
scripts/restore_db.sh
```

Restore specific backup:

```bash
scripts/restore_db.sh /absolute/path/to/backups/payme-YYYYMMDDTHHMMSSZ.sql
```

## Add New Settlement Rules

Add a `settlements` row with:
- `eligibility_predicates.states`
- `eligibility_predicates.required_features`

Then add corresponding rows in `settlement_feature_index` for each required feature key.

## Synthetic Training + Weights

Generate synthetic data:

```bash
python scripts/generate_synthetic_training_data.py
```

Train ranker weights:

```bash
python scripts/train_ranker.py
```

Outputs:
- `artifacts/weights.json`
- `artifacts/metrics.json`
- `artifacts/synthetic_training.{json,csv}`

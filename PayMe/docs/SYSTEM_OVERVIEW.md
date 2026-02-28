# PayMe — System Overview

This document is the top-level reference for the PayMe platform.
It describes every major subsystem, points to the detailed ASCII diagrams,
and maps how the pieces connect end-to-end.

---

## Document Index

| Document | What it covers |
|---|---|
| `MATCHING_ALGORITHM_ASCII.md` | User-feature ingestion, candidate scoring, experiment variants, result persistence |
| `ML_FEEDBACK_LOOP_ASCII.md` | Labeled-sample export, offline training, weight promotion gate |
| `GMAIL_INTEGRATION_ASCII.md` | Gmail OAuth flow, incremental history-based sync, feature extraction |
| `PLAID_INTEGRATION_ASCII.md` | Plaid Link flow, cursor-based transaction sync, bank feature extraction |
| `AUTOFILL_AGENT_ASCII.md` | Browser-automation worker, job lifecycle, step/artifact recording |
| `ATTORNEY_GATEWAY_ASCII.md` | Attorney auth, settlement account linking, approval pipeline, payout batches |
| `AGENT_TEAM_SESSION.md` | Multi-agent build playbook — track assignments, dependency map, coordination rules |
| `SYSTEM_OVERVIEW.md` | *This file* — top-level map of all subsystems |

---

## Architecture at a Glance

```
+-----------------------------------------------------------------------------------------------------+
|                                        PAYME PLATFORM                                               |
+-----------------------------------------------------------------------------------------------------+

  +------------------+        +-----------------------+        +---------------------------+
  |  User / Browser  |        |  FastAPI (apps/api)   |        |  PostgreSQL (+ pgvector)  |
  |------------------|        |-----------------------|        |---------------------------|
  | React + Vite SPA |<------>| /auth/*               |        | users                     |
  | (apps/web)       |        | /match/*              |        | settlements               |
  |                  |        | /integrations/*       |        | settlement_feature_index  |
  |  Onboarding      |        | /gateway/*            |        | user_features             |
  |  Match results   |        | /autofill/*           |        | match_runs / results      |
  |  Claim tracking  |        | /admin/*              |        | user_settlement_preferences|
  |  Attorney portal |        | /me / /onboarding     |        | events                    |
  +------------------+        +-----------+-----------+        | gmail_*                   |
                                          |                    | plaid_*                   |
                                          |                    | autofill_*                |
                                          |                    | attorney_accounts         |
                                          |                    | settlement_accounts       |
                                          |                    | claim_approvals           |
                                          |                    | payout_batches / transfers|
                                          |                    | ml_feedback_samples       |
                                          |                    +---------------------------+
                                          |
              +--------------------------++---------------------------+
              |                                                       |
              v                                                       v
  +------------------------+                           +---------------------------+
  | Autofill Worker        |                           | Offline Training          |
  | (apps/autofill-agent)  |                           | (scripts/train_ranker.py) |
  |------------------------|                           |---------------------------|
  | Polls autofill_jobs    |                           | Reads ml_feedback_samples |
  | Playwright browser     |                           | Fits logistic weights     |
  | Step + artifact record |                           | Promotes weights.json     |
  +------------------------+                           +---------------------------+
```

---

## User Journey (End-to-End)

```
+----------+    +------------+    +------------------+    +--------------------+    +--------------+
| Sign Up  |--->| Onboarding |--->| Connect Gmail /  |--->| Find Settlements   |--->| Track Claims |
| / Log In |    | (profile,  |    | Plaid (optional) |    | (match run, ranked |    | (ongoing     |
|          |    |  state,    |    |                  |    |  results, pinning) |    |  claims tab) |
|          |    |  DOB, etc.)|    |                  |    |                    |    |              |
+----------+    +------------+    +------------------+    +--------------------+    +--------------+
                                         |                          |                      |
                                         v                          v                      v
                               user_features updated       match_runs persisted    claim_status updated
                               (source=gmail/plaid)        match_results scored    events emitted
                                                           variant assigned        ML label created
```

---

## Subsystem Summaries

### 1. Authentication & Session
Routes: `/auth/signup`, `/auth/login`, `/auth/me`
- JWT-based, tokens carried as `Authorization: Bearer`
- User `role` field gates gateway access: `user` | `attorney` | `admin` | `super_user`
- Passwords hashed (bcrypt via passlib)
- Session state persisted in React `AppContext`

---

### 2. Matching Engine
*See `MATCHING_ALGORITHM_ASCII.md` for full diagram.*

```
user_features  +  settlement_feature_index
        |
        v
   run_match()
        |
   experiment variant (rules_only | rules_vector | rules_vector_ranker)
        |
   score each candidate (rules_confidence, similarity, recency, payout, urgency, ease)
        |
   persist match_run + match_results
        |
   /match/results → sorted: pinned first, then score desc
```

Key invariant: **matching never scans raw Gmail/Plaid rows** — only `user_features`.

---

### 3. Gmail Integration
*See `GMAIL_INTEGRATION_ASCII.md` for full diagram.*

```
/integrations/gmail/oauth/init   → Google OAuth authorization URL
/integrations/gmail/oauth/callback → exchange code → encrypt + store tokens
/integrations/gmail/sync         → dispatcher:
                                     connected user → real API (incremental via history.list)
                                     no connection  → mock fixture (MOCK_GMAIL=true)
                                   → upsert user_features (source=gmail)
```

Token security: access + refresh tokens encrypted at rest, never logged.

---

### 4. Plaid Integration
*See `PLAID_INTEGRATION_ASCII.md` for full diagram.*

```
/integrations/plaid/link-token   → Plaid link_token for frontend Link widget
/integrations/plaid/exchange     → public_token → access_token (encrypted, stored)
/integrations/plaid/sync         → dispatcher:
                                     active item → real API (cursor-based /transactions/sync)
                                     no item     → mock fixture (MOCK_PLAID=true)
                                   → upsert user_features (source=plaid)
/integrations/plaid/disconnect   → item/remove + status=disconnected
```

Re-auth flow: `ITEM_LOGIN_REQUIRED` error → `plaid_items.status = requires_reauth`.

---

### 5. ML Feedback Loop
*See `ML_FEEDBACK_LOOP_ASCII.md` for full diagram.*

```
claim outcomes (paid_out / not_paid_out)
        |
   export_labeled_samples() → ml_feedback_samples
        |
   scripts/train_ranker.py  → weights_vN.json + metrics_vN.json
        |
   compare precision@5: new > current?
        yes → promote to artifacts/weights.json
        no  → keep current active weights
        |
   next match run (rules_vector_ranker) uses promoted weights
```

---

### 6. Autofill Agent
*See `AUTOFILL_AGENT_ASCII.md` for full diagram.*

```
POST /autofill/jobs (claim_url, user_id, settlement_id)
        |
   autofill_jobs table (status=queued)
        |
   Worker polling loop (FOR UPDATE SKIP LOCKED)
        |
   run_autofill_job():
     navigate → detect_form → fill_fields → submit → screenshot → done
        |                          |
   AutofillJobStep records    BlockedError → status=blocked
   AutofillArtifact records   Exception   → retry or fail
```

Separate Docker service (`apps/autofill-agent/`) with its own polling loop.

---

### 7. Attorney Gateway & Payout Flow
*See `ATTORNEY_GATEWAY_ASCII.md` for full diagram.*

```
POST /gateway/attorneys              → register attorney account
POST /gateway/attorneys/{id}/settlement-accounts → link bank to settlement

Claim approval pipeline:
  user submits claim → claim_status=submitted
        |
  GET  /gateway/payouts/queue        → list all pending claimants
  POST /gateway/attorneys/{id}/approve/{sid}/{uid} → ClaimApproval status=approved
  POST /gateway/payouts/execute      → create batches + process (mock ~90% success)
        |
  PayoutTransfer status=completed → UserSettlementPreference.claim_status=paid_out
  PayoutTransfer status=failed    → ClaimApproval.status=failed
```

Full reconciliation: `GET /gateway/payouts/{batch_id}/reconcile`

---

## Data Flow: Features → Match → Claim → Payout

```
+----------------+     +------------------+     +-------------------+     +------------------+
| Gmail / Plaid  |     | Matching Engine  |     | Claim Lifecycle   |     | Attorney Gateway |
| Sync           |     |                  |     |                   |     |                  |
|----------------|     |------------------|     |-------------------|     |------------------|
| gmail_messages |---->| user_features    |---->| match_results     |---->| claim_approvals  |
| gmail_evidence |     | +feature_key     |     | +score            |     | +approved_amount |
| plaid_         |     | +confidence      |     | +reasons_json     |     |                  |
|  transactions  |     | +source          |     |                   |     | payout_batches   |
|                |     |                  |     | user_settlement_  |---->| payout_transfers |
|                |     | settlement_      |     | preferences       |     |                  |
|                |     | feature_index    |     | +claim_status     |     | UserSettlement   |
|                |     | (inverted index) |     | +claim_submitted  |     | Preference       |
|                |     |                  |     |   _at             |     | .claim_status=   |
|                |     |                  |     | +claim_outcome_at |     |   paid_out       |
+----------------+     +------------------+     +-------------------+     +------------------+
                                                         |
                                                         v
                                              +-------------------+
                                              | ML Feedback Loop  |
                                              |-------------------|
                                              | ml_feedback_      |
                                              | samples           |
                                              | +label (0/1/NULL) |
                                              | +feature snapshot |
                                              |                   |
                                              | → train_ranker.py |
                                              | → weights.json    |
                                              +-------------------+
```

---

## Core Tables Reference

| Table | Purpose |
|---|---|
| `users` | Auth, profile, sync timestamps, role |
| `settlements` | Settlement catalog with eligibility predicates |
| `settlement_feature_index` | Inverted index for fast candidate lookup |
| `user_features` | Derived features from Gmail + Plaid (source tagged) |
| `match_runs` | One row per match execution (variant, metadata) |
| `match_results` | Per-settlement scored results (reasons_json) |
| `user_settlement_preferences` | Pins, stars, full claim lifecycle fields |
| `events` | Append-only audit log of all system events |
| `experiment_exposures` | Stable variant assignment per user/experiment |
| `gmail_messages` | Raw Gmail message metadata |
| `gmail_evidence` | Derived merchant/subscription evidence from Gmail |
| `gmail_oauth_tokens` | Encrypted OAuth tokens + history_id |
| `plaid_transactions` | Raw Plaid transaction records |
| `plaid_items` | Plaid access token (encrypted), cursor, status |
| `ml_feedback_samples` | Labeled training dataset from outcomes |
| `autofill_jobs` | Browser automation jobs (status, retry state) |
| `autofill_job_steps` | Step-level progress within a job |
| `autofill_artifacts` | Screenshots, HTML, logs from browser runs |
| `attorney_accounts` | Attorney identity + hashed API key |
| `settlement_accounts` | Bank account linked to a settlement (encrypted) |
| `claim_approvals` | Attorney approval/rejection per claimant |
| `payout_batches` | Grouped payout execution per settlement |
| `payout_transfers` | Individual claimant transfer records |
| `settlement_questions` | Attorney-created Q&A for managed settlements |
| `claim_submissions` | User Q&A answers + evidence links |

---

## Event Taxonomy

| Event | Emitted by |
|---|---|
| `gmail_sync_started` / `completed` / `failed` | Gmail sync |
| `gmail_oauth_granted` / `revoked` | Gmail OAuth |
| `plaid_sync_started` / `completed` / `failed` | Plaid sync |
| `plaid_item_linked` / `disconnected` | Plaid link |
| `plaid_reauth_required` | Plaid sync (ITEM_LOGIN_REQUIRED) |
| `claim_form_opened` | Claim route |
| `claim_submitted` | Claim route |
| `claim_paid_out` / `claim_not_paid_out` | Claim outcome route |
| `autofill_job_started` / `done` / `blocked` / `failed` | Autofill worker |
| `autofill_step_completed` | Autofill worker |
| `attorney_registered` | Attorney service |
| `settlement_account_linked` | Attorney service |
| `claimant_approved` / `rejected` | Attorney service |
| `payout_batch_created` / `completed` | Payout service |
| `payout_transfer_completed` / `failed` | Payout service |

---

## Runtime Configuration

| Variable | Purpose |
|---|---|
| `MOCK_GMAIL` | Use fixture-based Gmail sync when true |
| `MOCK_PLAID` | Use fixture-based Plaid sync when true |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Real Gmail OAuth credentials |
| `GOOGLE_REDIRECT_URI` | Gmail OAuth callback URL |
| `PLAID_CLIENT_ID` / `PLAID_SECRET` | Real Plaid credentials |
| `PLAID_ENV` | sandbox \| development \| production |
| `MATCHING_VARIANT` | Force a specific matching variant (optional) |
| `RANKER_DEFAULT_*_WEIGHT` | Fallback weights when no artifacts/weights.json |
| `GATEWAY_API_KEY_SALT` | Salt for hashing attorney API keys |
| `TOKEN_ENCRYPTION_KEY` | Key for Fernet token encryption |

---

## Key Operational Invariants

1. **No raw-row scan at match time** — matching reads only `user_features` + `settlement_feature_index`.
2. **Mock modes are always a fallback, never disabled** — real integrations take priority when connected.
3. **All secrets encrypted at rest** — Gmail OAuth tokens, Plaid access tokens, bank account refs all use `crypto.encrypt_token`.
4. **Payout operations are fully idempotent** — every write path accepts an `idempotency_key`.
5. **Events are append-only** — the `events` table is a write-once audit log.
6. **Test isolation** — tests run in `payme_test` schema; fixture data must not bleed into production schema.
7. **Weight promotion is gated** — new ML weights only go live if `precision@5` strictly improves.
8. **Autofill BlockedError ≠ failure** — blocked jobs require human intervention and do not retry automatically.
9. **Migrations via Alembic** — all schema changes must have a versioned migration in `apps/api/alembic/versions/`.

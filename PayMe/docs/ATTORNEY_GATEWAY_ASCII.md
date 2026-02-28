# Attorney Gateway & Payout Flow (ASCII)

This is a high-detail, end-to-end system diagram of how PayMe's Attorney Gateway
authenticates settlement administrators, links bank accounts to settlements, manages
claimant approval queues, executes payout batches, and reconciles transfer outcomes
back into the user-visible claim lifecycle.

```
                       +--------------------------------------------------+
                       |            ATTORNEY / SETTLEMENT ADMIN           |
                       |--------------------------------------------------|
                       | JWT login with role="attorney"|"admin"|"super"   |
                       | Link settlement bank account                     |
                       | Review submitted claimants                       |
                       | Approve / reject, execute payouts                |
                       +------------------------+-------------------------+
                                                |
              +---------------------------------+---------------------------------+
              |                                 |                                 |
              v                                 v                                 v
+---------------------------+   +----------------------------+   +-------------------------------+
| POST /gateway/attorneys   |   | POST /gateway/attorneys/   |   | GET  /gateway/payouts/queue   |
| (upsert AttorneyAccount   |   |   {id}/settlement-accounts |   | POST /gateway/payouts/execute |
|  for current JWT user)    |   | (link settlement bank acct)|   | GET  /gateway/payouts/history |
+-------------+-------------+   +--------------+-------------+   +---------------+---------------+
              |                                |                                  |
              v                                v                                  v
+---------------------------+   +----------------------------+   +-------------------------------+
| get_attorney(db, user)    |   | link_settlement_account()  |   | execute_payouts()             |
| dependency / auth guard   |   |----------------------------|   |-------------------------------|
|---------------------------|   | 1) encrypt account_ref     |   | 1) approve each item          |
| checks role in:           |   |    with encrypt_token()    |   | 2) group by settlement_id     |
|   attorney | admin |      |   | 2) upsert settlement_      |   | 3) create + process one       |
|   super_user              |   |    accounts row            |   |    PayoutBatch per settlement |
| looks up AttorneyAccount  |   | 3) emit settlement_        |   | 4) return reconciliation      |
| status must = "active"    |   |    account_linked event    |   |    report per batch           |
| raises 403 if wrong role  |   +----------------------------+   | 5) fully idempotent via       |
| raises 404 if no account  |                                    |    derived batch keys         |
+---------------------------+                                    +-------------------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                              ATTORNEY AUTH + REGISTRATION                               |
+-----------------------------------------------------------------------------------------+

  POST /gateway/attorneys
              |
              v
  +-------------------------------+
  | register_attorney()           |
  | (or upsert for current user)  |
  |-------------------------------|
  | 1) create AttorneyAccount row |
  |    - user_id  (FK -> users)   |
  |    - name, email, firm_name   |
  |    - status = "active"        |
  | 2) generate random API key    |
  | 3) hash: SHA-256 of           |
  |    "{GATEWAY_API_KEY_SALT}    |
  |     :{raw_key}"               |
  | 4) store api_key_hash ONLY    |
  |    (raw key is NEVER stored)  |
  | 5) emit attorney_registered   |
  | 6) return (account, raw_key)  |
  |    raw key shown once only    |
  +-------------------------------+
              |
              v
  +-------------------------------+
  | attorney_accounts table       |
  |-------------------------------|
  | user_id      FK -> users      |
  | name                          |
  | email                         |
  | firm_name                     |
  | api_key_hash  (SHA-256 only)  |
  | status        active|suspended|
  +-------------------------------+

  Alternate lookup path (API key):
  +-------------------------------+
  | get_attorney_by_api_key()     |
  |-------------------------------|
  | 1) hash raw_key input         |
  | 2) look up by api_key_hash    |
  | 3) return AttorneyAccount     |
  +-------------------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                        SETTLEMENT ACCOUNT LINKING                                       |
+-----------------------------------------------------------------------------------------+

  POST /gateway/attorneys/{attorney_id}/settlement-accounts
              |
              v
  +-------------------------------+
  | link_settlement_account()     |
  |-------------------------------|
  | inputs:                       |
  |   attorney    (resolved dep)  |
  |   settlement_id               |
  |   bank_name                   |
  |   account_ref (raw routing/   |
  |     account string)           |
  +---------------+---------------+
                  |
                  v
  +-------------------------------+
  | encrypt_token(account_ref)    |
  | -> account_ref_enc            |
  | raw account_ref never stored  |
  +---------------+---------------+
                  |
                  v
  +-------------------------------+
  | upsert settlement_accounts    |
  |-------------------------------|
  | attorney_id                   |
  | settlement_id   (unique)      |
  | bank_name                     |
  | account_ref_enc  (encrypted)  |
  | status    active | closed     |
  | linked_at                     |
  +---------------+---------------+
                  |
                  v
  +-------------------------------+
  | emit settlement_account_linked|
  +-------------------------------+

  GUARD enforced downstream:
  +-------------------------------------------------+
  | approve_claimant() raises ValueError if no      |
  | active SettlementAccount exists for settlement  |
  | -> settlement must be linked before any         |
  |    approvals or payout batches can be created   |
  +-------------------------------------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                           CLAIMANT APPROVAL QUEUE                                       |
+-----------------------------------------------------------------------------------------+

  Claimants arrive via user-side claim submission flow:
  (user claim_status transitions: matched -> opened -> submitted)

  GET /gateway/payouts/queue
              |
              v
  +---------------------------------------------------+
  | list_all_submitted_claimants(db, attorney)        |
  |---------------------------------------------------|
  | query: user_settlement_preferences                |
  |   WHERE claim_status = "submitted"                |
  |   AND settlement managed by this attorney         |
  | joins ClaimApproval if present                    |
  | returns: user_id, settlement_id, submitted_at,    |
  |          approval status (if any)                 |
  +---------------------------------------------------+

              Approve path                   Reject path
              |                               |
              v                               v
  +---------------------------+   +---------------------------+
  | approve_claimant()        |   | reject_claimant()         |
  |---------------------------|   |---------------------------|
  | guard: active             |   | upsert ClaimApproval      |
  |   SettlementAccount must  |   |   status = "rejected"     |
  |   exist (raises ValueError|   | emit claimant_rejected    |
  |   if missing)             |   +---------------------------+
  | upsert ClaimApproval      |
  |   status = "approved"     |
  |   approved_amount_cents   |
  |   review_note             |
  | emit claimant_approved    |
  +---------------------------+

  +-------------------------------+
  | claim_approvals table         |
  |-------------------------------|
  | user_id                       |
  | settlement_id  (unique pair)  |
  | attorney_id                   |
  | approved_amount_cents         |
  | status:                       |
  |   pending | approved |        |
  |   rejected | paid | failed   |
  | review_note                   |
  | approved_at                   |
  | rejected_at                   |
  +-------------------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                          PAYOUT BATCH CREATION                                          |
+-----------------------------------------------------------------------------------------+

  create_payout_batch(db, attorney, settlement_id, idempotency_key)
              |
              v
  +-------------------------------------------+
  | idempotency guard                         |
  |-------------------------------------------|
  | if idempotency_key already exists in      |
  | payout_batches -> return existing batch   |
  | without mutation                          |
  +-------------------+-----------------------+
                      |  (new batch)
                      v
  +-------------------------------------------+
  | collect approved ClaimApprovals           |
  | for this settlement_id                    |
  +-------------------+-----------------------+
                      |
                      v
  +-------------------------------------------+
  | create PayoutBatch                        |
  |-------------------------------------------|
  | attorney_id                               |
  | settlement_id                             |
  | status = "queued"                         |
  | total_transfers  = count(approvals)       |
  | successful_transfers = 0                  |
  | failed_transfers     = 0                  |
  | total_amount_cents                        |
  | idempotency_key  (unique)                 |
  +-------------------+-----------------------+
                      |
                      v
  +-------------------------------------------+
  | create one PayoutTransfer per approval    |
  |-------------------------------------------|
  | batch_id                                  |
  | approval_id                               |
  | user_id                                   |
  | amount_cents:                             |
  |   ClaimApproval.approved_amount_cents     |
  |   ?? Settlement.payout_min_cents          |
  |   ?? 0                                    |
  | status = "pending"                        |
  | idempotency_key derived:                  |
  |   "transfer:{batch_id}:{approval_id}"     |
  +-------------------+-----------------------+
                      |
                      v
  +-------------------------------------------+
  | emit payout_batch_created                 |
  +-------------------------------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                       PAYOUT BATCH EXECUTION (process_payout_batch)                     |
+-----------------------------------------------------------------------------------------+

  For each pending PayoutTransfer in the batch:
              |
              v
  +-------------------------------------------+
  | set status = "processing"                 |
  | set initiated_at = now                    |
  +-------------------+-----------------------+
                      |
                      v
  +-------------------------------------------+
  | deterministic mock simulation             |
  |-------------------------------------------|
  | SHA-256 hash of transfer.idempotency_key  |
  | read last byte of digest (0-255)          |
  |                                           |
  |   byte < 230 (~90%)  -> SUCCESS           |
  |   byte >= 230 (~10%) -> FAILURE           |
  |                                           |
  | (deterministic: same key = same outcome;  |
  |  reproducible in tests without mocking)   |
  +--------+------------------+---------------+
           |                  |
     SUCCESS                FAILURE
           |                  |
           v                  v
  +------------------+  +------------------+
  | transfer:        |  | transfer:        |
  |  status=completed|  |  status=failed   |
  |  completed_at=now|  |  failure_reason  |
  |                  |  |                  |
  | ClaimApproval:   |  | ClaimApproval:   |
  |  status=paid     |  |  status=failed   |
  |                  |  |                  |
  | UserSettlement   |  | emit:            |
  |  Preference:     |  |  payout_transfer |
  |  claim_status=   |  |  _failed         |
  |  "paid_out"      |  +------------------+
  |                  |
  | emit:            |
  |  payout_transfer |
  |  _completed      |
  +------------------+

  After all transfers processed:

  +-------------------------------------------+
  | compute batch terminal status             |
  |-------------------------------------------|
  | all succeeded  -> status = "completed"    |
  | all failed     -> status = "failed"       |
  | zero transfers -> status = "failed"       |
  | mixed          -> status = "partial"      |
  +-------------------+-----------------------+
                      |
                      v
  +-------------------------------------------+
  | update PayoutBatch counts + status        |
  | emit payout_batch_completed               |
  +-------------------------------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                        EXECUTE PAYOUTS (COMBINED FLOW)                                  |
+-----------------------------------------------------------------------------------------+

  POST /gateway/payouts/execute
  body: { items: [{user_id, settlement_id, amount_cents}], idempotency_key }
              |
              v
  +-------------------------------------------+
  | execute_payouts(db, attorney, items,      |
  |                 idempotency_key)          |
  +-------------------+-----------------------+
                      |
         +------------+------------+
         |                         |
         v                         v
  for each item:           group by settlement_id
  +------------------+
  | approve_claimant |     for each settlement_id group:
  |  (skips if no    |     +-----------------------------------+
  |   active         |     | derive batch idempotency_key:     |
  |   SettlementAcct)|     |   "{idempotency_key}:{settlement_id}"
  +------------------+     | create_payout_batch()             |
                           | process_payout_batch()            |
                           +-----------------------------------+
                                         |
                                         v
                           +-----------------------------------+
                           | reconciliation report per batch  |
                           |-----------------------------------|
                           | batch_id                         |
                           | settlement_id                    |
                           | status                           |
                           | total transfers                  |
                           | successful transfers             |
                           | failed transfers                 |
                           | total_amount_cents               |
                           | transfers[] (detail per user)    |
                           +-----------------------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                          CLAIM STATE MACHINE                                            |
+-----------------------------------------------------------------------------------------+

  User-visible claim lifecycle (claim_status on user_settlement_preferences):

           USER SIDE                                    ATTORNEY SIDE
           ---------                                    -------------

  +-------------------+
  |     matched       |  <- /match/run assigns result
  +--------+----------+
           |
           | user opens claim form
           v
  +-------------------+
  |     opened        |  <- claim_form_opened event
  +--------+----------+
           |
           | user submits claim
           v
  +-------------------+
  |    submitted      |  <- claim_submitted event
  +--------+----------+
           |
           +-------------------------------> attorney sees in /gateway/payouts/queue
           |                                            |
           |                          +-----------------+-----------------+
           |                          |                                   |
           |                    approve_claimant()               reject_claimant()
           |                          |                                   |
           |                          v                                   v
           |                 +----------------+                  +----------------+
           |                 |   approved     |                  |    rejected    |
           |                 | (ClaimApproval)|                  | (ClaimApproval)|
           |                 +-------+--------+                  | no payout ever |
           |                         |                           +----------------+
           |                 payout batch created + processed
           |                         |
           |           +-------------+-------------+
           |           |                           |
           |     transfer succeeds           transfer fails
           |           |                           |
           v           v                           v
  +-------------------+                  +-------------------+
  |    paid_out       |                  |   not_paid_out    |
  | (claim_status on  |                  | (claim_status on  |
  |  UserSettlement   |                  |  UserSettlement   |
  |  Preference)      |                  |  Preference)      |
  | emit:             |                  | emit:             |
  |   claim_paid_out  |                  |  claim_not_paid_out|
  +-------------------+                  +-------------------+

  Full transition summary:
    matched -> opened -> submitted -> approved -> paid_out
                                   -> rejected
                                   -> approved -> (batch fails) -> not_paid_out
```

```
+-----------------------------------------------------------------------------------------+
|                        RECONCILIATION AND BALANCE                                       |
+-----------------------------------------------------------------------------------------+

  GET /gateway/payouts/history
              |
              v
  +-------------------------------------------+
  | list_payout_history(db, attorney)         |
  |-------------------------------------------|
  | all PayoutTransfers across all batches    |
  | belonging to this attorney's settlements  |
  +-------------------------------------------+

  GET /gateway/payouts/batches/{batch_id}/reconciliation
              |
              v
  +-------------------------------------------+
  | get_batch_reconciliation(db, batch_id)    |
  |-------------------------------------------|
  | batch_id                                  |
  | settlement_id                             |
  | status                                    |
  | total transfers                           |
  | successful transfers                      |
  | failed transfers                          |
  | total_amount_cents                        |
  | transfers[]:                              |
  |   user_id, amount_cents, status,          |
  |   initiated_at, completed_at,             |
  |   failure_reason                          |
  +-------------------------------------------+

  GET /gateway/payouts/balance
              |
              v
  +-------------------------------------------+
  | get_account_balance(db, attorney)         |
  |-------------------------------------------|
  | sandbox starting balance: $100,000        |
  | subtract: sum of completed transfers      |
  | report separately:                        |
  |   pending_amount_cents (approved but      |
  |   not yet in a batch or batch pending)    |
  | returns:                                  |
  |   available_balance_cents                 |
  |   pending_amount_cents                    |
  |   disbursed_amount_cents                  |
  +-------------------------------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                    MANAGED SETTLEMENTS: QUESTIONS + SUBMISSIONS                          |
+-----------------------------------------------------------------------------------------+

  Attorney creates custom intake questions per settlement:

  POST /gateway/settlements/{id}/questions
  GET  /gateway/settlements/{id}/questions
  PUT  /gateway/settlements/{id}/questions/{qid}
  DEL  /gateway/settlements/{id}/questions/{qid}
  POST /gateway/settlements/{id}/questions/seed  (bulk seed)
              |
              v
  +-------------------------------------------+
  | settlement_questions table                |
  |-------------------------------------------|
  | settlement_id                             |
  | attorney_id                               |
  | question_text                             |
  | question_type:                            |
  |   text | yes_no | date | amount | select  |
  | options_json  (for select type)           |
  | order_index   (display ordering)          |
  | required      (bool)                      |
  +-------------------------------------------+

  Users submit answers at claim time:

  +-------------------------------------------+
  | claim_submissions table                   |
  |-------------------------------------------|
  | user_id + settlement_id  (unique)         |
  | answers_json                              |
  |   (keyed by question_id)                  |
  | gmail_evidence_ids[]                      |
  |   (references to gmail_evidence rows)     |
  | plaid_evidence_ids[]                      |
  |   (references to plaid_transactions rows) |
  | auto_match_score                          |
  |   (computed at submission time)           |
  | auto_approved                             |
  |   (flag: skips manual review queue)       |
  +-------------------------------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                         DATABASE TABLES — FULL REFERENCE                                |
+-----------------------------------------------------------------------------------------+

  attorney_accounts
  +-----------------+--------+------------------------------------+
  | column          | type   | notes                              |
  +-----------------+--------+------------------------------------+
  | id              | uuid   | PK                                 |
  | user_id         | FK     | -> users                           |
  | name            | text   |                                    |
  | email           | text   |                                    |
  | firm_name       | text   |                                    |
  | api_key_hash    | text   | SHA-256 only, raw never stored     |
  | status          | enum   | active | suspended                 |
  +-----------------+--------+------------------------------------+

  settlement_accounts
  +-----------------+--------+------------------------------------+
  | column          | type   | notes                              |
  +-----------------+--------+------------------------------------+
  | id              | uuid   | PK                                 |
  | attorney_id     | FK     | -> attorney_accounts               |
  | settlement_id   | FK     | -> settlements (unique per sett.)  |
  | bank_name       | text   |                                    |
  | account_ref_enc | text   | encrypted at rest                  |
  | status          | enum   | active | closed                    |
  | linked_at       | ts     |                                    |
  +-----------------+--------+------------------------------------+

  claim_approvals
  +-----------------+--------+------------------------------------+
  | column          | type   | notes                              |
  +-----------------+--------+------------------------------------+
  | id              | uuid   | PK                                 |
  | user_id         | FK     | -> users                           |
  | settlement_id   | FK     | -> settlements                     |
  | attorney_id     | FK     | -> attorney_accounts               |
  | approved_amount | int    | cents                              |
  | status          | enum   | pending|approved|rejected|paid|    |
  |                 |        | failed                             |
  | review_note     | text   |                                    |
  | approved_at     | ts     |                                    |
  | rejected_at     | ts     |                                    |
  +-----------------+--------+------------------------------------+
  unique constraint: (user_id, settlement_id)

  payout_batches
  +-----------------+--------+------------------------------------+
  | column          | type   | notes                              |
  +-----------------+--------+------------------------------------+
  | id              | uuid   | PK                                 |
  | attorney_id     | FK     | -> attorney_accounts               |
  | settlement_id   | FK     | -> settlements                     |
  | status          | enum   | queued|processing|completed|       |
  |                 |        | partial|failed                     |
  | total_transfers | int    |                                    |
  | successful_t    | int    | successful_transfers               |
  | failed_t        | int    | failed_transfers                   |
  | total_amount    | int    | cents                              |
  | idempotency_key | text   | unique                             |
  +-----------------+--------+------------------------------------+

  payout_transfers
  +--------------------+--------+---------------------------------+
  | column             | type   | notes                           |
  +--------------------+--------+---------------------------------+
  | id                 | uuid   | PK                              |
  | batch_id           | FK     | -> payout_batches               |
  | approval_id        | FK     | -> claim_approvals              |
  | user_id            | FK     | -> users                        |
  | amount_cents       | int    |                                 |
  | status             | enum   | pending|processing|completed|   |
  |                    |        | failed                          |
  | idempotency_key    | text   | unique; derived from batch+appr |
  | provider_transfer_id| text  | sandbox reference               |
  | failure_reason     | text   |                                 |
  | initiated_at       | ts     |                                 |
  | completed_at       | ts     |                                 |
  +--------------------+--------+---------------------------------+

  settlement_questions
  +-----------------+--------+------------------------------------+
  | column          | type   | notes                              |
  +-----------------+--------+------------------------------------+
  | id              | uuid   | PK                                 |
  | settlement_id   | FK     | -> settlements                     |
  | attorney_id     | FK     | -> attorney_accounts               |
  | question_text   | text   |                                    |
  | question_type   | enum   | text|yes_no|date|amount|select     |
  | options_json    | json   | for select type                    |
  | order_index     | int    |                                    |
  | required        | bool   |                                    |
  +-----------------+--------+------------------------------------+

  claim_submissions
  +-----------------+--------+------------------------------------+
  | column          | type   | notes                              |
  +-----------------+--------+------------------------------------+
  | id              | uuid   | PK                                 |
  | user_id         | FK     | -> users                           |
  | settlement_id   | FK     | -> settlements                     |
  | answers_json    | json   | keyed by question_id               |
  | gmail_evidence  | json   | array of gmail_evidence ids        |
  | plaid_evidence  | json   | array of plaid_transactions ids    |
  | auto_match_score| float  |                                    |
  | auto_approved   | bool   |                                    |
  +-----------------+--------+------------------------------------+
  unique constraint: (user_id, settlement_id)
```

```
+-----------------------------------------------------------------------------------------+
|                              EVENTS EMITTED                                             |
+-----------------------------------------------------------------------------------------+

  attorney_registered
    -> when AttorneyAccount is created

  settlement_account_linked
    -> when settlement_accounts row is upserted

  claimant_approved
    -> when ClaimApproval status set to "approved"

  claimant_rejected
    -> when ClaimApproval status set to "rejected"

  payout_batch_created
    -> when PayoutBatch + PayoutTransfers are created

  payout_transfer_completed
    -> per transfer on mock success (last byte of SHA-256 < 230)

  payout_transfer_failed
    -> per transfer on mock failure (last byte of SHA-256 >= 230)

  payout_batch_completed
    -> when all transfers in a batch have been processed,
       regardless of individual outcomes

  All events write to the shared `events` table used across PayMe.
```

## Runtime Configuration Inputs

- Attorney API key security:
  - `GATEWAY_API_KEY_SALT` — prepended to raw key before SHA-256 hashing; raw key is never stored
- JWT auth:
  - Re-uses existing `JWT_SECRET` / `JWT_ALGORITHM` from core auth system
  - Roles checked: `attorney`, `admin`, `super_user`
- Bank account encryption:
  - `ENCRYPTION_KEY` (or equivalent) used by `encrypt_token()` for `account_ref_enc`

## Key Operational Notes

1. All payout operations are idempotent — passing the same `idempotency_key` to `create_payout_batch` or `execute_payouts` returns the existing record without mutation or double-execution.
2. A `SettlementAccount` with `status="active"` must exist for a settlement before any `ClaimApproval` can be created; `approve_claimant` raises `ValueError` if this guard fails.
3. Mock payout execution is deterministic: the SHA-256 hash of each transfer's `idempotency_key` is computed, the last byte is read, and `< 230` means success (~90%), `>= 230` means failure (~10%). The same key always produces the same outcome, making tests reproducible without patching.
4. Successful payout transfers sync back to the user layer: `ClaimApproval.status` is set to `"paid"` and `UserSettlementPreference.claim_status` is set to `"paid_out"`, closing the user-visible lifecycle loop.
5. `account_ref` (bank routing/account numbers) is always encrypted at rest via `encrypt_token()`; the plaintext value is never written to the database.
6. Batch terminal status is computed after all transfers complete: `"completed"` if all succeeded, `"failed"` if all failed or zero transfers existed, and `"partial"` for any mixed result.
7. The attorney approval queue (`/gateway/payouts/queue`) returns only users whose `claim_status = "submitted"`, joining any existing `ClaimApproval` row to show current review state.
8. Sandbox account balance starts at $100,000, subtracts all completed transfer amounts, and reports pending approved amounts separately so attorneys can see headroom before executing a batch.

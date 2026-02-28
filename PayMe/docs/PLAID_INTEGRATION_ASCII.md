# Plaid Bank Integration (ASCII)

This is a high-detail, end-to-end system diagram of how PayMe connects to Plaid, ingests
bank transactions, extracts user features, and handles real vs. mock paths, token lifecycle,
incremental cursor-based sync, and error recovery.

```
                                   +-----------------------------------------+
                                   |            USER / FRONTEND              |
                                   |-----------------------------------------|
                                   | Onboarding: "Connect your bank"         |
                                   | Plaid Link widget initialized            |
                                   | User selects institution, authenticates  |
                                   | Receives public_token from Plaid widget  |
                                   +-----------+-----------------------------++
                                               |
                     +-------------------------+--------------------------+
                     |                         |                          |
                     v                         v                          v
      +------------------------------+ +---------------------+ +---------------------+
      | POST /integrations/plaid/    | | POST /integrations/ | | POST /integrations/ |
      |   link-token                 | |   plaid/exchange    | |   plaid/sync        |
      |------------------------------| |---------------------| |---------------------|
      | create_link_token(user_id)   | | exchange_public_    | | sync_plaid          |
      | -> calls Plaid API           | |   token(...)        | |   dispatcher        |
      | -> returns {link_token,      | | -> stores encrypted | |                     |
      |      expiration}             | |      access token   | |                     |
      +------------------------------+ +---------------------+ +---------------------+
                                                |                          |
                                                v                          v
                                   +-----------------------+    +---------------------+
                                   | POST /integrations/   |    | sync_plaid          |
                                   |   plaid/disconnect    |    |   dispatcher        |
                                   |-----------------------|    |---------------------|
                                   | disconnect_item(...)  |    | (see dispatch tree  |
                                   | -> Plaid /item/remove |    |  diagram below)     |
                                   | -> status=disconnected|    +---------------------+
                                   +-----------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                            LINK FLOW (FIRST-TIME CONNECT)                               |
+-----------------------------------------------------------------------------------------+

  STEP 1: Frontend requests a link token
  ----------------------------------------

      +---------------------+         POST /integrations/plaid/link-token
      |   Frontend          |  ------------------------------------------------->  +-----------------------------+
      | (Plaid Link widget  |                                                       | create_link_token(user_id)  |
      |  not yet open)      |  <-------------------------------------------------  |-----------------------------|
      +---------------------+         {link_token, expiration}                     | Plaid /link/token/create    |
                                                                                    | products=["transactions"]   |
                                                                                    | user.client_user_id=user_id |
                                                                                    +-----------------------------+


  STEP 2: User completes Plaid Link widget in browser
  ----------------------------------------------------

      +---------------------+
      |   Plaid Link Widget |
      |---------------------|
      | Institution picker  |
      | Credential entry    |
      | MFA / OAuth screens |
      | -> returns          |
      |    public_token     |
      |    institution_id   |
      |    institution_name |
      +----------+----------+
                 |
                 v

  STEP 3: Frontend exchanges public token
  ----------------------------------------

      +---------------------+         POST /integrations/plaid/exchange
      |   Frontend          |  ------------------------------------------------->  +----------------------------------------+
      |   {public_token,    |                                                       | exchange_public_token(                 |
      |    institution_id,  |  <-------------------------------------------------  |   db, user,                            |
      |    institution_name}|         {status: "linked"}                            |   public_token,                        |
      +---------------------+                                                       |   institution_id,                      |
                                                                                    |   institution_name)                    |
                                                                                    |----------------------------------------|
                                                                                    | 1. POST /item/public_token/exchange    |
                                                                                    |    -> receives item_id, access_token   |
                                                                                    | 2. encrypt_token(access_token)         |
                                                                                    |    -> access_token_enc (never raw)     |
                                                                                    | 3. Upsert plaid_items row:             |
                                                                                    |    - user_id (unique)                  |
                                                                                    |    - item_id                           |
                                                                                    |    - access_token_enc                  |
                                                                                    |    - institution_id / name             |
                                                                                    |    - status = "active"                 |
                                                                                    |    - cursor = NULL (reset on update)   |
                                                                                    |    - linked_at = now()                 |
                                                                                    | 4. Emit event: plaid_item_linked       |
                                                                                    +----------------------------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                          SYNC DISPATCHER (sync_plaid)                                   |
+-----------------------------------------------------------------------------------------+

      +-------------------------------------------+
      | sync_plaid(db, user)                       |
      +-------------------------------------------+
                          |
                          v
           +--------------+--------------+
           |                             |
           | Query plaid_items           |
           | WHERE user_id = user.id     |
           |   AND status = "active"     |
           |                             |
           +-----------------------------+
                          |
              +-----------+-----------+
              |                       |
     [active item found]     [no active item found]
              |                       |
              v                       v
   +----------------------+    +---------------------+
   | sync_plaid_real      |    | Check MOCK_PLAID env |
   | (real API path)      |    +----------+----------+
   |                      |               |
   | see REAL SYNC        |    +----------+----------+
   | diagram below        |    |                     |
   +----------------------+  [MOCK_PLAID=true]  [MOCK_PLAID=false]
                                   |                  |
                                   v                  v
                        +-------------------+  +---------------------------+
                        | sync_plaid_mock   |  | return                    |
                        | (fixture path)    |  | {status: "not_connected"} |
                        |                   |  +---------------------------+
                        | see MOCK SYNC     |
                        | diagram below     |
                        +-------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                          MOCK SYNC PATH (sync_plaid_mock)                               |
+-----------------------------------------------------------------------------------------+

      +-------------------------------------------------------+
      | sync_plaid_mock(db, user)                             |
      +-------------------------------------------------------+
                              |
                              v
            +----------------------------------+
            | Emit event: plaid_sync_started   |
            +----------------------------------+
                              |
                              v
            +----------------------------------+
            | Read fixture file                |
            | /workspace/fixtures/plaid/       |
            |   transactions.json              |
            +----------------------------------+
                              |
                              v
            +------------------------------------------------------+
            | For each transaction in fixture:                     |
            |------------------------------------------------------|
            | Upsert plaid_transactions row:                       |
            |   - SKIP if provider_txn_id already exists           |
            |   - INSERT if new:                                    |
            |       user_id, provider_txn_id, posted_at,           |
            |       merchant_name, amount_cents, category,         |
            |       is_subscription, raw_json                      |
            +------------------------------------------------------+
                              |
                              v
            +------------------------------------------------------+
            | Feature extraction per transaction:                  |
            |------------------------------------------------------|
            |                                                      |
            |  merchant_name                                       |
            |     -> normalize: lowercase + non-alphanumeric -> _  |
            |     -> feature_key = "merchant:{normalized_token}"   |
            |                                                      |
            |  category                                            |
            |     -> normalize: lowercase + non-alphanumeric -> _  |
            |     -> feature_key = "category:{normalized_token}"   |
            |                                                      |
            |  is_subscription = True                              |
            |     -> feature_key = "subscription:active"           |
            |                                                      |
            +------------------------------------------------------+
                              |
                              v
            +------------------------------------------------------+
            | Confidence formula (per feature_key):                |
            |------------------------------------------------------|
            | count = number of transactions contributing          |
            |         this feature_key                             |
            |                                                      |
            | confidence = min(0.95, 0.75 + min(0.2, count*0.04)) |
            |                                                      |
            | count      confidence                                |
            | -----      ----------                                |
            |   1         0.79                                     |
            |   2         0.83                                     |
            |   3         0.87                                     |
            |   4         0.91                                     |
            |   5         0.95  (cap)                              |
            |   6+        0.95  (cap)                              |
            +------------------------------------------------------+
                              |
                              v
            +------------------------------------------------------+
            | If active PlaidItem exists:                          |
            |------------------------------------------------------|
            | Write mock balance onto plaid_items row:             |
            |   balance_available_cents = 24783  ($247.83)         |
            |   balance_current_cents   = 31247  ($312.47)         |
            +------------------------------------------------------+
                              |
                              v
            +------------------------------------------------------+
            | Upsert user_features (source = "plaid")              |
            | One row per distinct feature_key                     |
            | Stores: feature_key, confidence, last_seen_at        |
            +------------------------------------------------------+
                              |
                              v
            +----------------------------------+
            | Update user.plaid_synced_at      |
            +----------------------------------+
                              |
                              v
            +----------------------------------+
            | Emit event: plaid_sync_completed |
            +----------------------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                     REAL SYNC PATH (sync_plaid_real) — INCREMENTAL                      |
+-----------------------------------------------------------------------------------------+

      +-------------------------------------------------------+
      | sync_plaid_real(db, user)                             |
      +-------------------------------------------------------+
                              |
                              v
            +----------------------------------+
            | Load PlaidItem for user          |
            | Raise if missing or              |
            |   status != "active"             |
            +----------------------------------+
                              |
                              v
            +----------------------------------+
            | Decrypt access token             |
            | decrypt_token(access_token_enc)  |
            | (token never written to logs)    |
            +----------------------------------+
                              |
                              v
            +-------------------------------------------------------+
            | Determine Plaid API host from PLAID_ENV:              |
            |-------------------------------------------------------|
            |  "sandbox"     -> sandbox.plaid.com                   |
            |  "development" -> development.plaid.com               |
            |  "production"  -> production.plaid.com                |
            +-------------------------------------------------------+
                              |
                              v
            +----------------------------------------------------------+
            |              PAGINATED SYNC LOOP                         |
            |----------------------------------------------------------|
            |                                                          |
            |  cursor = plaid_items.cursor                             |
            |    NULL  -> first call -> full historical sync           |
            |    value -> incremental delta from last sync             |
            |                                                          |
            |  +-------------------------------------------------+     |
            |  | POST /transactions/sync                         |     |
            |  |   {access_token, cursor}                        |     |
            |  |-------------------------------------------------|     |
            |  | Response:                                       |     |
            |  |   added[]     - new transactions                |     |
            |  |   modified[]  - updated transactions            |     |
            |  |   removed[]   - deleted transaction IDs         |     |
            |  |   next_cursor - new cursor position             |     |
            |  |   has_more    - boolean: more pages pending     |     |
            |  +-------------------------------------------------+     |
            |                    |                                     |
            |        +-----------+-----------+                         |
            |        |           |           |                         |
            |        v           v           v                         |
            |   +--------+  +--------+  +--------+                    |
            |   | added  |  |modified|  |removed |                    |
            |   |--------|  |--------|  |--------|                    |
            |   | Upsert |  | Update |  | Delete |                    |
            |   | rows + |  | rows + |  | txn    |                    |
            |   | extract|  | re-    |  | rows   |                    |
            |   | feat.  |  | extract|  |        |                    |
            |   +--------+  +--------+  +--------+                    |
            |        |           |                                     |
            |        v           v                                     |
            |   cursor = next_cursor                                   |
            |                                                          |
            |   [has_more=true]  -> loop back to POST /sync           |
            |   [has_more=false] -> exit loop                         |
            |                                                          |
            +----------------------------------------------------------+
                              |
                              v
            +------------------------------------------------------+
            | Feature extraction (same logic, real data):          |
            |------------------------------------------------------|
            |                                                      |
            |  merchant_name                                       |
            |     -> normalize: lowercase + non-alphanumeric -> _  |
            |     -> feature_key = "merchant:{normalized_token}"   |
            |                                                      |
            |  personal_finance_category.primary                   |
            |     OR category[0] (fallback)                        |
            |     -> normalize: lowercase + non-alphanumeric -> _  |
            |     -> feature_key = "category:{normalized_token}"   |
            |                                                      |
            |  recurring_transaction_id IS NOT NULL                |
            |     OR is_subscription = True                        |
            |     -> feature_key = "subscription:active"           |
            |                                                      |
            +------------------------------------------------------+
                              |
                              v
            +------------------------------------------------------+
            | Confidence formula (same as mock):                   |
            | confidence = min(0.95, 0.75 + min(0.2, count*0.04)) |
            +------------------------------------------------------+
                              |
                              v
            +------------------------------------------------------+
            | Upsert user_features (source = "plaid")              |
            | One row per distinct feature_key, with confidence    |
            | and last_seen_at (used by matching recency signal)   |
            +------------------------------------------------------+
                              |
                              v
            +----------------------------------+
            | Persist updated cursor           |
            | plaid_items.cursor = next_cursor |
            +----------------------------------+
                              |
                              v
            +----------------------------------+
            | Update user.plaid_synced_at      |
            +----------------------------------+
                              |
                              v
            +----------------------------------+
            | Emit event: plaid_sync_completed |
            +----------------------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                         ERROR PATH: ITEM_LOGIN_REQUIRED                                  |
+-----------------------------------------------------------------------------------------+

      POST /transactions/sync
             |
             v
    +-------------------+
    | Plaid API error?  |
    +-------------------+
             |
     +-------+-------+
     |               |
    [no]            [yes]
     |               |
     |               v
     |   +-------------------------------+
     |   | error string contains         |
     |   | "ITEM_LOGIN_REQUIRED"?        |
     |   +-------------------------------+
     |               |
     |       +-------+-------+
     |       |               |
     |      [yes]           [no]
     |       |               |
     |       v               v
     |  +------------------+ +---------------------+
     |  | plaid_items      | | raise / propagate   |
     |  | .status =        | | other errors        |
     |  |  "requires_reauth"| +---------------------+
     |  |                  |
     |  | Emit event:      |
     |  | plaid_reauth_    |
     |  |   required       |
     |  |                  |
     |  | (frontend polls  |
     |  |  for this state  |
     |  |  and shows       |
     |  |  reconnect UX)   |
     |  +------------------+
     |
     v
  (happy path continues)
```

```
+-----------------------------------------------------------------------------------------+
|                            DISCONNECT FLOW                                               |
+-----------------------------------------------------------------------------------------+

      POST /integrations/plaid/disconnect
                   |
                   v
      +-------------------------------+
      | disconnect_item(db, user)     |
      +-------------------------------+
                   |
                   v
      +-------------------------------+
      | POST /item/remove             |
      | (best-effort — proceed even   |
      |  if Plaid API call fails)     |
      +-------------------------------+
                   |
                   v
      +-------------------------------+
      | plaid_items row update:       |
      |   status    = "disconnected"  |
      |   revoked_at = now()          |
      +-------------------------------+
                   |
                   v
      +-------------------------------+
      | Emit event:                   |
      | plaid_item_disconnected       |
      +-------------------------------+
                   |
                   v
      +-------------------------------+
      | Future sync_plaid calls:      |
      |   no active item found        |
      |   -> mock or not_connected    |
      +-------------------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                           DATABASE TABLE LAYOUT                                          |
+-----------------------------------------------------------------------------------------+

  plaid_items
  +-----------------------+-------------------------------------------------------------+
  | Column                | Notes                                                       |
  |-----------------------+-------------------------------------------------------------|
  | user_id               | unique — one item per user                                  |
  | item_id               | Plaid item identifier                                       |
  | access_token_enc      | encrypted at rest; never stored or logged in plaintext      |
  | institution_id        | from Plaid (e.g. "ins_3")                                   |
  | institution_name      | human-readable (e.g. "Chase")                               |
  | status                | active | requires_reauth | disconnected                     |
  | cursor                | /transactions/sync cursor; NULL = never synced              |
  | linked_at             | timestamp of exchange_public_token                          |
  | revoked_at            | timestamp of disconnect (NULL if active)                    |
  | balance_available_cents| last known available balance in cents                      |
  | balance_current_cents | last known current balance in cents                         |
  +-----------------------+-------------------------------------------------------------+

  plaid_transactions
  +-----------------------+-------------------------------------------------------------+
  | Column                | Notes                                                       |
  |-----------------------+-------------------------------------------------------------|
  | user_id               | FK to users                                                 |
  | provider_txn_id       | unique per user; Plaid transaction_id                       |
  | posted_at             | date transaction posted                                     |
  | merchant_name         | raw from Plaid                                              |
  | amount_cents          | integer cents; positive = debit, negative = credit          |
  | category              | raw category string from Plaid                              |
  | is_subscription       | boolean; set from Plaid recurring signals                   |
  | raw_json              | full Plaid transaction object; never scanned at match-time   |
  +-----------------------+-------------------------------------------------------------+

  user_features (plaid-sourced rows)
  +-----------------------+-------------------------------------------------------------+
  | Column                | Notes                                                       |
  |-----------------------+-------------------------------------------------------------|
  | user_id               | FK to users                                                 |
  | feature_key           | e.g. "merchant:amazon", "category:food", "subscription:active"|
  | source                | "plaid"                                                     |
  | confidence            | 0.75–0.95 per formula; consumed by matching engine          |
  | last_seen_at          | used by recency_signal in matching (<=7d, <=30d, etc.)      |
  +-----------------------+-------------------------------------------------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                    FEATURE KEY NORMALIZATION REFERENCE                                   |
+-----------------------------------------------------------------------------------------+

  Input (raw Plaid field)          Normalized token              Feature key stored
  -------------------------------- ----------------------------- --------------------------
  merchant_name = "Amazon.com"     "amazon_com"                  merchant:amazon_com
  merchant_name = "Netflix"        "netflix"                     merchant:netflix
  merchant_name = "Whole Foods"    "whole_foods"                 merchant:whole_foods
  category = "Food and Drink"      "food_and_drink"              category:food_and_drink
  category = "Travel"              "travel"                      category:travel
  personal_finance_category
    .primary = "ENTERTAINMENT"     "entertainment"               category:entertainment
  is_subscription = True           (no normalization needed)     subscription:active
  recurring_transaction_id != NULL (no normalization needed)     subscription:active

  Normalization rule:
    1. Lowercase entire string
    2. Replace any character that is NOT [a-z0-9] with underscore (_)
    3. Collapse consecutive underscores into one (implied)
```

```
+-----------------------------------------------------------------------------------------+
|                    FULL DATA FLOW COLUMN VIEW                                            |
+-----------------------------------------------------------------------------------------+

  PLAID API          PAYME API              DATABASE               MATCHING ENGINE
  -----------        ----------------       --------------------   --------------------
                     /plaid/link-token
  /link/token/  <--- create_link_token      (no write)
    create            returns {link_token}
      |
      v
  Plaid Link
  widget runs
  in browser
      |
      v
  public_token  ---> /plaid/exchange        plaid_items:
                     exchange_public_token    status=active
  /item/public/ <---                          cursor=NULL
    token/                                    access_token_enc
    exchange                                  linked_at=now()
      |                                     events: plaid_item_linked
      v
  access_token
  (encrypted)

                     /plaid/sync            plaid_transactions:    (not yet consumed;
                     sync_plaid               upsert rows           match reads
                       dispatcher                                    user_features only)
                       |
                 [active item?]
                  yes       no
                  |         |
                  v         v
              real sync  [MOCK_PLAID?]
                           yes     no
                            |       |
                            v       v
                         mock   not_connected
                         sync

  /transactions/ <--- sync_plaid_real       plaid_transactions:
    sync              or                      added / updated /
    (loop)            sync_plaid_mock          deleted rows
      |
      v                                     user_features:         feature_keys + confidence
  added[]                                     upsert source=plaid   -> candidate filter
  modified[]                                                         -> recency signal
  removed[]                                 plaid_items:            -> similarity score
                                              cursor updated         -> rules_confidence
                                              plaid_synced_at
                                            events: plaid_sync_completed
```

## Runtime Configuration

- Integration mode:
  - `MOCK_PLAID` — when `true` and no active PlaidItem, use fixture-based mock sync
- Plaid API credentials:
  - `PLAID_CLIENT_ID` — issued by Plaid dashboard
  - `PLAID_SECRET` — environment-scoped secret (sandbox / development / production)
- Plaid environment:
  - `PLAID_ENV` — `sandbox` | `development` | `production`
  - Maps to host: `sandbox.plaid.com` / `development.plaid.com` / `production.plaid.com`
- Token encryption:
  - Access tokens are encrypted via `encrypt_token` before any database write
  - Decrypted at sync time only; never logged or returned in API responses

## Key Operational Notes

1. Connected users (active PlaidItem with status="active") always execute the real sync path regardless of `MOCK_PLAID`. The env flag is only a fallback for users with no linked item.
2. Cursor-based incremental sync via `/transactions/sync` means only deltas are fetched after the initial full historical pull. The cursor is persisted to `plaid_items.cursor` after each completed sync loop.
3. `ITEM_LOGIN_REQUIRED` errors set `plaid_items.status="requires_reauth"` and emit `plaid_reauth_required` so the frontend can surface a reconnect prompt without losing existing transaction history.
4. Raw transaction JSON is stored in `plaid_transactions.raw_json` for auditability but is never scanned at match-time. The matching engine reads only `user_features` rows derived from that data.
5. The confidence formula (`min(0.95, 0.75 + min(0.2, count * 0.04))`) ensures a single-transaction observation yields 0.79 confidence while repeated signals converge to the 0.95 cap, producing graceful weighting rather than binary on/off features.
6. Disconnect is best-effort against the Plaid API: even if `/item/remove` fails, the local `plaid_items` row is set to `status="disconnected"` and `revoked_at` is stamped, ensuring no further sync attempts succeed.
7. The mock sync upserts (not replaces) fixture transactions, so running it repeatedly is idempotent — existing `provider_txn_id` rows are skipped.
8. Feature recency (`last_seen_at` on `user_features`) flows directly into the matching engine's recency signal buckets (<=7d: 1.0, <=30d: 0.85, <=90d: 0.65, <=180d: 0.45, else: 0.25), so stale Plaid data naturally degrades match confidence over time without requiring deletion.

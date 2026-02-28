# Gmail Integration and Sync Subsystem (ASCII)

This is a high-detail, end-to-end system diagram of how PayMe handles Gmail OAuth,
incremental message sync, brand token extraction, and feature derivation. The subsystem
is designed to be transparent to the matching engine: all outputs land in `user_features`
and the matching engine never touches raw Gmail rows at request time.

```
                                   +-----------------------------------------+
                                   |            USER / FRONTEND              |
                                   |-----------------------------------------|
                                   | Connect Gmail button (onboarding or     |
                                   | settings), Disconnect, manual re-sync   |
                                   +-------------------+---------------------+
                                                       |
                     +---------------------------------+---------------------------------+
                     |                                 |                                 |
                     v                                 v                                 v
      +-------------------------------+ +-------------------------------+ +-------------------------------+
      | GET /integrations/gmail/      | | GET /integrations/gmail/      | | POST /integrations/gmail/     |
      |     oauth/init                | |     oauth/callback            | |      oauth/revoke             |
      |-------------------------------| |-------------------------------| |-------------------------------|
      | Returns Google OAuth URL      | | code= + state= params         | | Marks token revoked_at=now()  |
      | Encodes user_id as state      | | Exchanges code for tokens     | | Calls Google revoke endpoint  |
      | Scopes: gmail.readonly        | | Fetches Gmail address via     | | Emits gmail_oauth_revoked     |
      +---------------+---------------+ |   userinfo endpoint           | +-------------------------------+
                      |                 | Encrypts + stores token row   |
                      |                 | Emits gmail_oauth_granted     |
                      |                 +---------------+---------------+
                      |                                 |
                      +---------------------------------+
                                        |
                                        v
                        +-------------------------------+
                        | POST /integrations/gmail/sync |
                        |-------------------------------|
                        | Calls sync_gmail(db, user)    |
                        +---------------+---------------+
                                        |
                                        v
```

```
+-----------------------------------------------------------------------------------------+
|                                  DISPATCHER LOGIC                                        |
|            sync_gmail(db, user)  in  gmail_sync.py                                      |
+-----------------------------------------------------------------------------------------+

                     +------------------------------------------------------------------+
                     | Does gmail_oauth_tokens contain a non-revoked row for this user? |
                     +------------------------------------------------------------------+
                                   |                       |
                          YES      |                       |      NO
                                   v                       v
                  +----------------------------+    +--------------------------------------+
                  | sync_gmail_real(db, user)  |    | Is MOCK_GMAIL=true in config?        |
                  | (real Google API path)     |    +--------------------------------------+
                  +----------------------------+             |              |
                                                    YES      |              |      NO
                                                             v              v
                                              +-------------------+  +----------------------------+
                                              | sync_gmail_mock   |  | return                     |
                                              | (db, user)        |  | {status: "not_connected"}  |
                                              | (fixture path)    |  +----------------------------+
                                              +-------------------+

  NOTE: Connected users always use the real path even when MOCK_GMAIL=true.
  The flag only governs unauthenticated users.
```

```
+-----------------------------------------------------------------------------------------+
|                                  MOCK SYNC PATH                                          |
|            sync_gmail_mock(db, user)                                                     |
+-----------------------------------------------------------------------------------------+

  Source file: /workspace/fixtures/gmail/sample_messages.json

  +----------------------------+
  | Load fixture JSON          |
  | (array of message objects) |
  +-------------+--------------+
                |
                v
  +----------------------------+     already exists?
  | For each message           +--------------------> SKIP (upsert guard on provider_msg_id)
  |   Upsert gmail_messages    |
  |   (provider_msg_id unique) |
  +-------------+--------------+
                |
                v
  +-----------------------------------------------------------------------+
  | _derive_token_counts(subject + snippet text)                          |
  |                                                                       |
  |   BRAND_MAP token extraction (case-insensitive substring match):      |
  |                                                                       |
  |   Input text keyword      ->   Emitted feature_key                    |
  |   -----------------------      ---------------------------------      |
  |   "amazon"                ->   merchant:amazon                        |
  |   "uber"                  ->   merchant:uber                          |
  |   "at&t"                  ->   merchant:at&t                          |
  |   "paramount"             ->   merchant:paramount                     |
  |   "walmart"               ->   merchant:walmart                       |
  |   "united airlines"       ->   merchant:united_airlines               |
  |   "mcdonald"              ->   merchant:mcdonald_s                    |
  |   "starbucks"             ->   merchant:starbucks                     |
  |   "kfc"                   ->   merchant:kfc                           |
  |   "prime"                 ->   subscription:prime                     |
  |   "paramount+"            ->   subscription:paramount_plus            |
  |   "casino" / "sportsbook" |                                           |
  |   "bet" / "gambling"      ->   category:gambling                      |
  |                                                                       |
  |   Returns: dict of {feature_key -> count}                             |
  +-----------------------------------------------------------------------+
                |
                v
  +-----------------------------------------------------------------------+
  | Confidence formula (per evidence row):                                |
  |   confidence = min(0.95, 0.7 + min(0.2, count * 0.05))               |
  |                                                                       |
  |   count=1 -> 0.75    count=4 -> 0.90    count>=6 -> 0.95 (cap)       |
  +-----------------------------------------------------------------------+
                |
                v
  +----------------------------+     +----------------------------+
  | Upsert gmail_evidence rows |     | Upsert user_features rows  |
  |   evidence_type="merchant" |     |   source="gmail"           |
  |   key = feature_key        |     |   feature_key = same key   |
  |   count (accumulated)      |     |   value_json = true        |
  |   confidence               |     |   confidence               |
  |   first_seen_at            |     |   first_seen_at            |
  |   last_seen_at = now()     |     |   last_seen_at = now()     |
  |   examples_json            |     +----------------------------+
  +----------------------------+
                |
                v
  +-----------------------------------------------------------------------+
  | Finalize                                                              |
  |   user.gmail_synced_at = now()                                        |
  |   Emit event: gmail_sync_started                                      |
  |   Emit event: gmail_sync_completed                                    |
  +-----------------------------------------------------------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                                  REAL OAuth FLOW                                         |
|            gmail_real.py                                                                 |
+-----------------------------------------------------------------------------------------+

  STEP 1: Authorization URL generation
  +-----------------------------------------------------------------------+
  | get_oauth_authorization_url(user_id)                                  |
  |   Scope: https://www.googleapis.com/auth/gmail.readonly               |
  |   state: base64-encoded user_id (roundtripped through callback)       |
  |   redirect_uri: GOOGLE_REDIRECT_URI                                   |
  |   Returns: (auth_url, state)                                          |
  +-----------------------------------------------------------------------+
                |
                | User redirected to Google consent screen
                v
  STEP 2: Callback — code exchange
  +-----------------------------------------------------------------------+
  | exchange_oauth_code(db, user, code, state)                            |
  |   1. POST to Google token endpoint with code                          |
  |   2. GET https://www.googleapis.com/oauth2/v1/userinfo                |
  |        -> captures gmail_address for the token row                    |
  |   3. Encrypt tokens:                                                  |
  |        access_token  -> crypto.encrypt_token -> access_token_enc      |
  |        refresh_token -> crypto.encrypt_token -> refresh_token_enc     |
  |   4. Upsert gmail_oauth_tokens row:                                   |
  |        user_id (unique), access_token_enc, refresh_token_enc,         |
  |        token_expiry, scopes, gmail_address, granted_at, revoked_at=NULL|
  |   5. Emit event: gmail_oauth_granted                                  |
  +-----------------------------------------------------------------------+
                |
                v
  STEP 3: Revocation (when user disconnects)
  +-----------------------------------------------------------------------+
  | revoke_gmail_access(db, user)                                         |
  |   POST https://oauth2.googleapis.com/revoke?token={access_token}      |
  |   token_row.revoked_at = now()                                        |
  |   Emit event: gmail_oauth_revoked                                     |
  +-----------------------------------------------------------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                              TOKEN REFRESH LOGIC                                         |
|            _build_credentials(db, token_row)  in  gmail_real.py                         |
+-----------------------------------------------------------------------------------------+

  +----------------------------+
  | Decrypt stored tokens      |
  |   crypto.decrypt_token(    |
  |     access_token_enc)      |
  |   crypto.decrypt_token(    |
  |     refresh_token_enc)     |
  +-------------+--------------+
                |
                v
  +-----------------------------------------------------------------------+
  | Normalize token_expiry timezone                                       |
  |   Strip tzinfo -> naive UTC (required for google-auth compatibility)  |
  +-----------------------------------------------------------------------+
                |
                v
  +-------------------------------------------------------+
  | Is token_expiry within 60 seconds of now?             |
  +-------------------------------------------------------+
            |                         |
     YES    |                         |     NO
            v                         v
  +------------------+      +---------------------------+
  | creds.refresh(   |      | Use existing credentials  |
  |   GoogleRequest) |      | as-is                     |
  +--------+---------+      +---------------------------+
           |
           v
  +-----------------------------------------------------------------------+
  | Re-normalize expiry (google-auth may re-attach tzinfo after refresh)  |
  | Persist refreshed tokens back to DB:                                  |
  |   access_token_enc  = encrypt_token(new access_token)                |
  |   refresh_token_enc = encrypt_token(new refresh_token)               |
  |   token_expiry      = new expiry (naive UTC)                          |
  |                                                                       |
  |   SECURITY: raw token values are NEVER written to logs               |
  +-----------------------------------------------------------------------+
                |
                v
  +----------------------------+
  | Return valid Credentials   |
  | object to caller           |
  +----------------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                           REAL SYNC — INCREMENTAL VS FULL PATH                          |
|            sync_gmail_real(db, user)  in  gmail_real.py                                  |
+-----------------------------------------------------------------------------------------+

  +----------------------------+
  | Load GmailOAuthToken row   |
  | for user                   |
  | Raise if missing/revoked   |
  +-------------+--------------+
                |
                v
  +----------------------------+
  | _build_credentials(        |
  |   db, token_row)           |
  | (decrypt + refresh if      |
  |  needed — see above)       |
  +-------------+--------------+
                |
                v
  +----------------------------+
  | Persist any refreshed      |
  | tokens back to DB          |
  +-------------+--------------+
                |
                v
  +----------------------------------------------------------+
  | Does token_row.gmail_history_id have a value?            |
  +----------------------------------------------------------+
            |                              |
     YES    |                              |    NO
     (incremental)                         (full fetch)
            v                              v
  +--------------------+       +------------------------------------+
  | history.list(      |       | Compute epoch = now - 90 days      |
  |   userId="me",     |       | messages.list(                     |
  |   startHistoryId=  |       |   userId="me",                     |
  |     history_id,    |       |   q="after:{epoch}",               |
  |   historyTypes=    |       |   maxResults=500)                  |
  |   ["messageAdded"] |       |                                    |
  | )                  |       | Follow nextPageToken until         |
  |                    |       | no more pages (paginated)          |
  | Returns only new   |       |                                    |
  | message IDs since  |       | Returns all message IDs in        |
  | last sync          |       | the 90-day window                  |
  +--------+-----------+       +----------------+-------------------+
           |                                    |
           +------------------------------------+
                              |
                              v
  +-----------------------------------------------------------------------+
  | For each message ID:                                                  |
  |   messages.get(userId="me", id=msg_id, format="metadata")             |
  |     -> fetch Subject and From headers                                 |
  |   _extract_message_fields(msg_raw)                                    |
  |     -> internal_date, from_domain, subject, snippet                   |
  |   Upsert gmail_messages row                                           |
  |     (provider_msg_id unique per user — skips if already present)      |
  +-----------------------------------------------------------------------+
                |
                v
  +-----------------------------------------------------------------------+
  | _derive_token_counts(subject, snippet)                                |
  |   Same BRAND_MAP extraction as mock path (identical logic)            |
  |   Returns: dict of {feature_key -> count}                             |
  +-----------------------------------------------------------------------+
                |
                v
  +-----------------------------------------------------------------------+
  | _upsert_features(db, user, token_counts, now)                         |
  |   Upsert gmail_evidence rows (evidence_type="merchant")               |
  |   Upsert user_features rows (source="gmail")                          |
  |   Confidence formula: min(0.95, 0.7 + min(0.2, count * 0.05))        |
  +-----------------------------------------------------------------------+
                |
                v
  +-----------------------------------------------------------------------+
  | Finalize                                                              |
  |   token_row.gmail_history_id = latest historyId from API response     |
  |   user.gmail_synced_at = now()                                        |
  |   Emit event: gmail_sync_completed                                    |
  +-----------------------------------------------------------------------+

  NOTE: The incremental path (history.list) avoids re-fetching messages that were
  already processed in prior syncs. The historyId persisted after each sync becomes
  the exclusive lower bound of the next sync window.
```

```
+-----------------------------------------------------------------------------------------+
|                              DATABASE TABLES                                             |
+-----------------------------------------------------------------------------------------+

  gmail_oauth_tokens
  +-------------------------+-----------------------------------------------------------+
  | Column                  | Notes                                                     |
  +-------------------------+-----------------------------------------------------------+
  | user_id (unique)        | FK to users; one token row per user                      |
  | access_token_enc        | Encrypted via crypto.encrypt_token                       |
  | refresh_token_enc       | Encrypted via crypto.encrypt_token                       |
  | token_expiry            | Stored as naive UTC datetime                              |
  | scopes                  | Space-separated scope string                              |
  | gmail_address           | Gmail address fetched from userinfo endpoint              |
  | gmail_history_id        | Latest historyId; NULL means next sync does full fetch   |
  | granted_at              | Timestamp of initial OAuth grant                         |
  | revoked_at              | NULL = active; non-NULL = revoked                        |
  +-------------------------+-----------------------------------------------------------+

  gmail_messages
  +-------------------------+-----------------------------------------------------------+
  | Column                  | Notes                                                     |
  +-------------------------+-----------------------------------------------------------+
  | user_id                 | FK to users                                               |
  | provider_msg_id         | Google message ID; unique per user (upsert guard)        |
  | internal_date           | Message epoch from Google                                 |
  | from_domain             | Parsed sender domain                                     |
  | subject                 | Raw subject line                                         |
  | snippet                 | Short text preview from Google                           |
  | raw_json                | Full metadata response stored as JSONB                   |
  +-------------------------+-----------------------------------------------------------+

  gmail_evidence
  +-------------------------+-----------------------------------------------------------+
  | Column                  | Notes                                                     |
  +-------------------------+-----------------------------------------------------------+
  | user_id                 | FK to users                                               |
  | evidence_type           | Always "merchant" in current implementation               |
  | key                     | Feature key, e.g. "merchant:amazon"                      |
  | first_seen_at           | Timestamp of first observation                            |
  | last_seen_at            | Updated on each sync that observes this key               |
  | count                   | Accumulated hit count across all synced messages          |
  | confidence              | min(0.95, 0.7 + min(0.2, count * 0.05))                  |
  | examples_json           | Sample subject lines that triggered this evidence        |
  +-------------------------+-----------------------------------------------------------+

  user_features  (source="gmail" rows)
  +-------------------------+-----------------------------------------------------------+
  | Column                  | Notes                                                     |
  +-------------------------+-----------------------------------------------------------+
  | user_id                 | FK to users                                               |
  | feature_key             | e.g. "merchant:amazon", "subscription:prime"             |
  | value_json              | Always true for Gmail-derived features                    |
  | confidence              | Carried from gmail_evidence confidence                   |
  | first_seen_at           | Timestamp of first observation                            |
  | last_seen_at            | Updated on each sync; drives recency_signal in matching  |
  | source                  | "gmail"                                                   |
  +-------------------------+-----------------------------------------------------------+

  NOTE: last_seen_at on user_features is the value consumed by the matching engine
  recency_signal (<=7d:1.0, <=30d:0.85, <=90d:0.65, <=180d:0.45, else:0.25).
  Stale Gmail features naturally decay in match score without any explicit TTL.
```

```
+-----------------------------------------------------------------------------------------+
|                             EVENT STREAM                                                 |
+-----------------------------------------------------------------------------------------+

  Event name               Emitted when
  -----------------------  ---------------------------------------------------------------
  gmail_oauth_granted      User completes consent screen; token row upserted successfully
  gmail_oauth_revoked      User disconnects; revoke endpoint called; revoked_at set
  gmail_sync_started       Dispatcher begins any sync (mock or real)
  gmail_sync_completed     Sync finished; user_features updated; gmail_synced_at stamped
  gmail_sync_failed        Exception raised during real sync (network, auth, parse errors)

  All events land in the shared `events` table and are visible in the admin dashboard
  per-user event stream.
```

```
+-----------------------------------------------------------------------------------------+
|                    FEATURE EXTRACTION — CONFIDENCE CURVE                                 |
+-----------------------------------------------------------------------------------------+

  count  confidence   formula: min(0.95,  0.7 + min(0.2, count * 0.05))
  -----  ----------
    1      0.750      0.7 + 0.05
    2      0.800      0.7 + 0.10
    3      0.850      0.7 + 0.15
    4      0.900      0.7 + 0.20   <- min(0.2,...) cap reached
    5      0.950      0.7 + 0.20 + rounding; hits outer cap at 0.95
    6+     0.950      capped

  The 0.7 floor means even a single message hit produces a confident signal.
  The 0.2 additive cap prevents count inflation from dominating; the 0.95 outer
  cap reserves headroom and avoids overconfident features feeding the ranker.
```

## Runtime Configuration

- `MOCK_GMAIL` — when `true` and the user has no OAuth token, mock fixture sync runs
  instead of returning `not_connected`; connected users are never redirected to mock
- `GOOGLE_CLIENT_ID` — OAuth 2.0 client ID from Google Cloud Console
- `GOOGLE_CLIENT_SECRET` — OAuth 2.0 client secret from Google Cloud Console
- `GOOGLE_REDIRECT_URI` — must match the redirect URI registered in Google Cloud Console;
  points to `GET /integrations/gmail/oauth/callback`

Token encryption keys are assumed to be in the environment and consumed by
`crypto.encrypt_token` / `crypto.decrypt_token`; raw values are never written to logs
or returned in API responses.

## Key Operational Notes

1. The dispatcher always prefers the real sync path. `MOCK_GMAIL=true` only activates
   the fixture path when no active token row exists for the user.
2. Brand token extraction (BRAND_MAP) is byte-for-byte identical between the mock and
   real paths, ensuring feature parity between local development and production.
3. Raw `gmail_messages` rows are never read at match time. The matching engine consumes
   only `user_features`; Gmail rows are staging storage for feature derivation only.
4. The `gmail_history_id` acts as a sync cursor. A NULL value forces a full 90-day
   fetch; a non-NULL value enables the incremental `history.list` path and avoids
   re-processing already-seen messages on every sync.
5. Token refresh is transparent to all callers. `_build_credentials` returns a valid
   Credentials object regardless of whether the access token was expired; the caller
   does not need to handle refresh errors or retry logic.
6. `last_seen_at` on `user_features` is updated on each sync that observes a feature.
   This timestamp is the direct input to the matching engine's recency_signal, so
   features from stale or disconnected Gmail accounts decay in score automatically
   without any explicit expiry or deletion job.
7. The `revoked_at` field is a soft delete. Once set, the dispatcher treats the token
   as absent and will route to mock (if enabled) or return `not_connected`. The
   historical token row and all derived `user_features` remain intact.

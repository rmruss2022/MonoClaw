# Matching Algorithm (ASCII)

This is a high-detail, end-to-end system diagram of how PayMe builds user features
from Gmail + Plaid data and turns them into ranked settlement matches.

```
                                   +-----------------------------------------+
                                   |            USER / FRONTEND              |
                                   |-----------------------------------------|
                                   | Onboarding, Connect Gmail/Plaid,        |
                                   | "Find New Settlements", Claim actions   |
                                   +-------------------+---------------------+
                                                       |
                     +---------------------------------+---------------------------------+
                     |                                                                   |
                     v                                                                   v
      +-------------------------------+                                   +-------------------------------+
      | /integrations/gmail/*         |                                   | /integrations/plaid/*         |
      |-------------------------------|                                   |-------------------------------|
      | oauth init/callback/revoke    |                                   | link-token / exchange / sync  |
      | manual sync endpoint          |                                   | disconnect / manual sync      |
      +---------------+---------------+                                   +---------------+---------------+
                      |                                                                   |
                      v                                                                   v
      +-------------------------------+                                   +-------------------------------+
      | Gmail dispatcher              |                                   | Plaid dispatcher              |
      | sync_gmail(db, user)          |                                   | sync_plaid(db, user)          |
      |-------------------------------|                                   |-------------------------------|
      | if active OAuth token -> real |                                   | if active Plaid item -> real  |
      | else if MOCK_GMAIL -> mock    |                                   | else if MOCK_PLAID -> mock    |
      +---------------+---------------+                                   +---------------+---------------+
                      |                                                                   |
                      v                                                                   v
      +-------------------------------+                                   +-------------------------------+
      | Gmail raw + evidence tables   |                                   | Plaid raw tables             |
      |-------------------------------|                                   |-------------------------------|
      | gmail_messages                |                                   | plaid_transactions           |
      | gmail_evidence                |                                   | plaid_items (balance/status) |
      +---------------+---------------+                                   +---------------+---------------+
                      |                                                                   |
                      +---------------------------+-------------------------------+-------+
                                                  |                               |
                                                  v                               v
                                    +-------------------------------+   +-------------------------------+
                                    | user_features                 |   | user row sync timestamps      |
                                    |-------------------------------|   |-------------------------------|
                                    | source=gmail / source=plaid   |   | gmail_synced_at / plaid_synced_at |
                                    | feature_key examples:         |   +-------------------------------+
                                    | - merchant:amazon             |
                                    | - category:streaming          |
                                    | - subscription:active         |
                                    +-------------------------------+

```

```
+-----------------------------------------------------------------------------------------+
|                                  MATCH COMPUTE PATH                                     |
+-----------------------------------------------------------------------------------------+

      +-------------------------------+        +------------------------------------------+
      | Settlement data               |        | Inverted index for fast candidate filter |
      |-------------------------------|        |------------------------------------------|
      | settlements                   |        | settlement_feature_index                 |
      | eligibility_predicates:       |------->| (feature_kind='required', feature_key)  |
      | - required_features[]         |        +-------------------+----------------------+
      | - states[]                    |                            |
      +-------------------------------+                            |
                                                                   v
      +-------------------------------+        +------------------------------------------+
      | /match/run                    |------->| run_match(db, user, top_n=20)           |
      +-------------------------------+        |------------------------------------------|
                                               | 1) Load user_features -> feature_keys    |
                                               | 2) Assign experiment variant             |
                                               | 3) Read ranker weights                   |
                                               | 4) Build candidate set                   |
                                               | 5) Score each candidate                  |
                                               | 6) Persist match_run + match_results     |
                                               +-------------------+----------------------+
                                                                   |
                                                                   v
                              +-------------------------------------------------------------------+
                              | Variant selection + scoring                                       |
                              |-------------------------------------------------------------------|
                              | Variant source:                                                   |
                              | - forced by MATCHING_VARIANT (optional)                          |
                              | - else deterministic hash assignment among:                      |
                              |   rules_only | rules_vector | rules_vector_ranker               |
                              |                                                                   |
                              | Signals per settlement:                                           |
                              | - rules_confidence = 0.4 + 0.4*(matched_required/required_total)|
                              |   + 0.2 if state is allowed                                      |
                              | - similarity      = min(1.0, 0.3 + 0.15*matched_required)        |
                              | - payout_signal   = min(1.0, payout_max_cents/10000)             |
                              | - urgency_signal  = 0.7 if deadline else 0.3                     |
                              | - ease_signal     = 0.8 if claim_url else 0.4                    |
                              |                                                                   |
                              | Score by variant:                                                 |
                              | - rules_only: score = rules_confidence                           |
                              | - rules_vector: score = 0.85*rules_confidence + 0.15*similarity |
                              | - rules_vector_ranker: weighted sum over 5 signals               |
                              |   using active artifacts/weights.json or env defaults            |
                              +-----------------------------------+-------------------------------+
                                                                  |
                                                                  v
                             +--------------------------------------------------------------------+
                             | Persistence + explanation payloads                                 |
                             |--------------------------------------------------------------------|
                             | match_runs metadata_json includes:                                  |
                             | - feature_count                                                     |
                             | - variant                                                           |
                             | - weights_version (from weights.json _version if present)          |
                             |                                                                    |
                             | match_results reasons_json includes:                                |
                             | - matched_features[]                                                |
                             | - predicate_passes.state                                            |
                             | - confidence_breakdown.rules (raw rules_confidence)                 |
                             | - similarity, payout, urgency, ease                                 |
                             | - score                                                             |
                             +-----------------------------------+--------------------------------+
                                                                 |
                                                                 v
                                 +---------------------------------------------------+
                                 | /match/results + /match/explain/{settlement_id}   |
                                 |---------------------------------------------------|
                                 | latest run rows returned to UI                    |
                                 | final response sorted by:                         |
                                 | 1) pinned first                                   |
                                 | 2) pinned_order asc                               |
                                 | 3) score desc                                     |
                                 +---------------------------------------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                               FEEDBACK + RETRAIN PATH                                   |
+-----------------------------------------------------------------------------------------+

 /settlements/{id}/claim/opened|submitted|outcome
             |
             v
 user_settlement_preferences.claim_status
   paid_out -> positive label
   not_paid_out -> negative label
   opened/submitted -> pending (NULL label)
   none -> ignored negative
             |
             v
 export_labeled_samples() -> ml_feedback_samples
             |
             v
 train_ranker.py
   -> writes weights_vN.json + metrics_vN.json
   -> promotes to active weights.json ONLY if precision@5 improves
             |
             v
 next /match/run in rules_vector_ranker uses promoted active weights
```

## Runtime Configuration Inputs

- Matching variant:
  - `MATCHING_VARIANT` (optional force override)
- Ranker fallback defaults (used only when `artifacts/weights.json` missing):
  - `RANKER_DEFAULT_RULES_CONFIDENCE_WEIGHT`
  - `RANKER_DEFAULT_SIMILARITY_WEIGHT`
  - `RANKER_DEFAULT_PAYOUT_WEIGHT`
  - `RANKER_DEFAULT_URGENCY_WEIGHT`
  - `RANKER_DEFAULT_EASE_WEIGHT`
- Integration mode toggles:
  - `MOCK_GMAIL`
  - `MOCK_PLAID`

## Key Operational Notes

1. Request-time matching reads `user_features` + `settlement_feature_index`; it does not scan raw Gmail/Plaid rows.
2. Gmail/Plaid sync updates `user_features` asynchronously via integration endpoints.
3. Pinned ordering is applied after score computation in result presentation.
4. Model retraining does not automatically activate every new candidate; promotion gate controls activation.

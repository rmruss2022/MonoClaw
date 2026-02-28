# ML Feedback Loop (ASCII)

This diagram explains how feedback data is generated, turned into training samples,
trained into candidate model weights, and conditionally promoted to active weights.

```
+---------------------------+            +---------------------------+
| User Interaction Layer    |            | Matching Engine           |
|---------------------------|            |---------------------------|
| - /match/run              |----------->| run_match()               |
| - Claim lifecycle events  |            | variant:                  |
|   opened/submitted/outcome|            |   rules_only              |
+---------------------------+            |   rules_vector            |
                                         |   rules_vector_ranker     |
                                         +-------------+-------------+
                                                       |
                                                       v
                                         +---------------------------+
                                         | match_results table       |
                                         |---------------------------|
                                         | reasons_json includes:    |
                                         | - rules_confidence        |
                                         | - similarity              |
                                         | - payout                  |
                                         | - urgency                 |
                                         | - ease                    |
                                         | - score                   |
                                         +-------------+-------------+
                                                       |
                                                       v
+---------------------------+            +---------------------------+
| user_settlement_preferences|           | Export Service            |
|---------------------------|            |---------------------------|
| claim_status:             |----------->| export_labeled_samples()  |
| - paid_out                |            | joins match + claim data  |
| - not_paid_out            |            | labels:                   |
| - submitted/opened        |            |   paid_out      -> 1      |
| - none                    |            |   not_paid_out  -> 0      |
+---------------------------+            |   submitted/opened -> NULL|
                                         |   none          -> 0      |
                                         +-------------+-------------+
                                                       |
                                                       v
                                         +---------------------------+
                                         | ml_feedback_samples table |
                                         | (materialized dataset)    |
                                         +-------------+-------------+
                                                       |
                                                       v
                                         +---------------------------+
                                         | Trainer                   |
                                         |---------------------------|
                                         | scripts/train_ranker.py   |
                                         | - load feedback_export    |
                                         | - fit logistic weights    |
                                         | - compute precision@k/AUC |
                                         +-------------+-------------+
                                                       |
                         +-----------------------------+-----------------------------+
                         |                                                           |
                         v                                                           v
           +-------------------------------+                            +------------------------------+
           | Versioned Candidate Artifacts |                            | Active Artifacts             |
           |-------------------------------|                            |------------------------------|
           | weights_vN.json               |                            | weights.json                 |
           | metrics_vN.json               |                            | metrics.json                 |
           +---------------+---------------+                            +---------------+--------------+
                           |                                                            ^
                           | compare new precision@5 to current precision@5             |
                           +--------------------------[ STRICTLY GREATER ? ]-------------+
                                                      | yes                   | no
                                                      v                       |
                                            promote candidate                 |
                                            copy current metrics -> prev      |
                                                                              |
                                                                              +-- keep current active
```

## Runtime Weight Selection

At match-time (for `rules_vector_ranker` variant):

1. Load `artifacts/weights.json` if it exists (active trained model).
2. Otherwise use env-configured defaults:
   - `RANKER_DEFAULT_RULES_CONFIDENCE_WEIGHT`
   - `RANKER_DEFAULT_SIMILARITY_WEIGHT`
   - `RANKER_DEFAULT_PAYOUT_WEIGHT`
   - `RANKER_DEFAULT_URGENCY_WEIGHT`
   - `RANKER_DEFAULT_EASE_WEIGHT`

## Promotion Rule (Important)

The trainer only updates live `weights.json` when:

`new_metrics.precision_at_5 > current_metrics.precision_at_5`

Equal performance does not promote. Worse performance does not promote.

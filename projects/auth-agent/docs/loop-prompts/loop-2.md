Read docs/ROADMAP.md Loop 2 and docs/DATA_STRATEGY.md section on Payer PA Requirements.

Build the payer requirements system:

1. **src/api/routes/payers.js** — GET /api/payers, GET /api/payers/:id/requirements/:cptCode
2. **src/fhir/coverMyMeds.js** — CoverMyMeds API client with sandbox mode
3. **src/data/payerRequirements.json** — Manually curated requirements for top 5 payers × top 20 CPT codes (from docs/ROADMAP.md Loop 2)
4. **src/api/services/payerService.js** — Business logic: look up requirements, check CoverMyMeds, fall back to local DB
5. **Redis caching** for payer API responses (15 min TTL)
6. **UI page: /payers** — Shows payer list with requirements per CPT code, searchable
7. **UI component: RequirementsChecklist.tsx** — Given a PA request, shows which requirements are met vs missing

The payerRequirements.json must include real clinical criteria for each payer/code combination. Research and use actual payer medical policies. For United Healthcare lumbar MRI (CPT 72148) for example:
- Requires documentation of conservative treatment (PT x 6 weeks minimum)
- Must document failed NSAIDs/medication
- Must have neurological symptoms or radiculopathy
- No prior MRI of same region within 6 months without new clinical findings

Include similar real criteria for all 20 CPT codes across 5 payers.

When done, update docs/ROADMAP.md Loop 2 status to ✅ and run:
openclaw system event --text "AuthAgent Loop 2 complete: payer requirements system built" --mode now

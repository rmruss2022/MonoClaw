Read docs/ROADMAP.md Loop 4 and docs/MVP_SCOPE.md section on Agent 3: scoreProbability.

Build the approval probability scoring system:

1. **src/agents/scoreProbability.js** — Complete rule-based scoring:
   - Base rates from CMS data (hardcode the top 20 CPT codes with realistic base rates)
   - Adjustment rules engine (see ROADMAP.md Loop 4 for full rules)
   - Returns: { probability: 0.87, confidence: 'high', factors: [...], recommendation: string }
   - Each factor must have: name, impact (+/-%), description, met (boolean)

2. **src/data/baseDenialRates.json** — Base denial rates by CPT code and payer type:
   Research and use realistic rates. For example:
   - 72148 (lumbar MRI): United 22%, Aetna 18%, Cigna 15%, commercial avg 19%
   - 27447 (total knee): United 31%, commercial avg 28%
   - J0274 (Ozempic obesity): United 65%, commercial avg 58% (high denial)
   - 90837 (psychotherapy): United 12%, commercial avg 14%
   Include all 20 CPT codes.

3. **src/data/riskFactors.json** — Rules for probability adjustments:
   - has_pt_records: +12% for lumbar spine codes
   - missing_imaging: -15% if payer requires prior imaging
   - diagnosis_matches_criteria: +18% if ICD-10 matches payer criteria
   - prior_denial_same_code: -8% (flag in clinical extract)
   - high_scrutiny_payer: -5% (United for certain codes)
   etc.

4. **UI component: ProbabilityGauge.tsx** — Visual gauge (arc/semicircle):
   - Color: red <50%, yellow 50-70%, green >70%
   - Shows percentage + confidence label
   - Expandable factor list: "✅ PT records present (+12%)" / "⚠️ Missing imaging report (-8%)"
   - Recommendation block: "Submit as-is" or "Gather these documents first: [list]"

5. **src/api/routes/pa.js** — Add probability score to PA create/update response

6. **Dashboard widget** — "Probability Distribution" chart: bar chart of pending PAs by probability bucket

When done, update docs/ROADMAP.md Loop 4 status to ✅ and run:
openclaw system event --text "AuthAgent Loop 4 complete: probability scoring live" --mode now

## Verification (run before marking complete)

After building, verify your work actually runs:

```bash
cd /Users/matthew/.openclaw/workspace/monoclaw/projects/auth-agent

# Start API if not running
cd packages/api && npm install --silent 2>/dev/null
node src/index.js &
API_PID=$!
sleep 3

# Quick smoke test
echo "Testing API health..."
curl -sf http://localhost:3011/api/health || echo "WARNING: API health check failed"

# Test the specific endpoint(s) you built this loop
curl -sf http://localhost:3011/api/payers 2>/dev/null && echo "Payers: OK" || echo "Payers: FAIL"

kill $API_PID 2>/dev/null
```

Fix any failures before marking the loop complete.

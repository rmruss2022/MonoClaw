Read docs/ROADMAP.md Loop 6.

Build the autonomous appeal system — this is the killer feature:

1. **src/data/carcStrategies.json** — Denial reason code counter-strategies for all 10 CARC codes from ROADMAP.md:
   Each entry must include:
   - code: CARC code (e.g. "CO-50")
   - name: human description
   - strategy: what argument to make
   - required_evidence: what to include in appeal
   - success_rate_estimate: % (based on industry data)
   - typical_resolution_days: number
   - escalation_path: what to do if first appeal fails

2. **src/agents/draftAppeal.js** — Appeal generation agent:
   - Takes: originalPA, denialReasonCode, denialReasonText, payerName
   - Loads CARC strategy from carcStrategies.json
   - Generates full appeal letter citing:
     * Original clinical justification (strengthened)
     * Clinical guidelines (MCG criteria by name, peer-reviewed studies)
     * Payer's own coverage policy language
     * Patient-specific clinical necessity
   - Returns: { appealLetter, appealType, escalationRecommended, deadlineDate }

3. **src/api/routes/pa.js** — Add:
   - POST /api/pa/:id/generate-appeal — generate appeal draft
   - POST /api/pa/:id/submit-appeal — submit the approved appeal
   - GET  /api/pa/:id/appeals — list all appeals for this PA

4. **pa_appeals table** — Already in schema, add:
   - deadline_date (30/60/90 days from denial, by payer rules)
   - days_remaining computed column
   - escalation_type (first_level|second_level|peer_to_peer|external_review)

5. **Deadline tracker** — Alert when appeal deadline < 7 days away:
   - Dashboard widget: "⚠️ 3 appeals need attention (deadline approaching)"
   - Sort appeals by urgency

6. **UI: Appeal flow**:
   - On denied PA detail page: prominent "Generate Appeal" button with denial reason displayed
   - Appeal draft page: split view (original PA left, appeal letter right)
   - Deadline countdown badge: "File by Apr 15 (12 days)"
   - Show CARC strategy tip: "CO-50 denials: cite clinical guidelines. 71% overturn rate with strong clinical evidence."
   - "Submit Appeal" with same confirmation flow as initial submission

7. **Payer Intelligence page update** — Add appeal stats:
   - Win rate by CARC code
   - Win rate by payer
   - Average days to overturn by payer
   - "Most winnable denials" ranking

When done, update docs/ROADMAP.md Loop 6 status to ✅ and run:
openclaw system event --text "AuthAgent Loop 6 complete: appeal automation working" --mode now

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

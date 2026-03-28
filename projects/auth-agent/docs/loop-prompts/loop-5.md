Read docs/ROADMAP.md Loop 5 and docs/MVP_SCOPE.md submission section.

Build the submission + tracking system:

1. **src/fhir/coverMyMeds.js** — Full CoverMyMeds sandbox API client:
   - submitPA(paData) → returns { paId, status, estimatedDecisionDate }
   - getStatus(paId) → returns current status
   - Sandbox mode: simulate responses for demo (no real API key needed in dev)
   - In DEMO_MODE: return realistic mock responses with simulated delays

2. **src/api/routes/pa.js** — Add endpoints:
   - POST /api/pa/:id/submit — human approves and triggers submission
   - GET  /api/pa/:id/status — check current payer status
   - POST /api/pa/:id/refresh — manually poll for status update

3. **Status state machine** — PA moves through states:
   draft → reviewed → submitted → pending_decision → approved|denied → (if denied) appeal_draft → appeal_submitted → appeal_decided → closed
   Add status_history JSONB column to pa_requests (append-only event log)

4. **Status polling job** — Background job that polls CoverMyMeds every 4 hours for pending PAs:
   - Simple setInterval in dev, could be cron in prod
   - Updates DB + sends notification when status changes

5. **Notifications** — When PA status changes:
   - Console log in dev
   - POST to openclaw system event (approved: celebrate, denied: action needed)
   - In prod: email/SMS to billing staff

6. **UI: Timeline component** — Shows PA lifecycle as a vertical timeline:
   - Each status change with timestamp and actor (system/staff name)
   - Current status highlighted
   - "Days pending" counter for submitted PAs

7. **UI: PA Detail page update** — Show submit button (only when status=reviewed):
   - Confirmation modal: "Submit to [Payer Name]? This will transmit patient information."
   - Post-submit: show CoverMyMeds PA reference number + expected decision date

8. **Demo mode simulation** — In DEMO_MODE:
   - Approvals come back in 2 minutes (simulated)
   - 25% of submissions get denied (realistic)
   - Show the status changing in real-time during demo

When done, update docs/ROADMAP.md Loop 5 status to ✅ and run:
openclaw system event --text "AuthAgent Loop 5 complete: submission and tracking working" --mode now

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

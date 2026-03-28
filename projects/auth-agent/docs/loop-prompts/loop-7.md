Read docs/ROADMAP.md Loop 7 and docs/DEMO_SCRIPT.md.

Polish the product for investor demo. This is the final loop before we show it to people.

1. **Demo mode (DEMO_MODE=true)**:
   - Banner at top: "DEMO MODE — No real patient data" (dismissable)
   - Pre-loaded: 20 PA scenarios in various states
   - Simulated real-time updates: PAs transition through states automatically in demo
   - All 5 demo scenarios from DEMO_SCRIPT.md working end-to-end

2. **Dashboard improvements**:
   - Hero stats: Total PAs (this month), Approval Rate %, Avg Processing Time, $ Recovered
   - Stats animated on load (count up from 0)
   - Recent activity feed: last 10 PA events with timestamps
   - Pending PAs sorted by urgency (deadline approaching > high value > standard)
   - "Time saved this month" widget: "47.3 hours saved vs manual process"

3. **New PA wizard — polished**:
   - Progress bar showing steps
   - Step 1: drag-and-drop file upload zone (accept PDF, show preview)
   - Step 2: CPT code autocomplete (search by code or description)
   - Step 3: AI analysis — animated skeleton loading → results with smooth transition
   - Step 4: Letter editor with word count, quality score badge
   - Step 5: Review & submit — summary card before confirming

4. **PA Detail page — comprehensive**:
   - Status timeline (vertical, with icons)
   - Probability gauge (animated arc)
   - Clinical extract expandable section
   - Letter diff view (original AI vs human-edited, show % changed)
   - Financial impact: procedure estimated value, days pending cost estimate

5. **Empty states** — every page needs a helpful empty state:
   - Dashboard: "No PAs yet. Start your first prior authorization →"
   - Each state filter: "No approved PAs this month" with context

6. **Performance**:
   - All pages load in < 1 second (no loading spinners for static data)
   - API responses cached appropriately
   - Skeleton loading states for async content (not spinners)

7. **PDF export**:
   - Export PA letter to clean PDF (use puppeteer or html-pdf)
   - Include: practice logo placeholder, patient ID, date, payer, CPT code, full letter
   - Export appeal letter similarly

8. **README update** — add Quick Start section:
   ```bash
   git clone [repo]
   cd auth-agent
   npm install
   cp .env.example .env  # add your Anthropic API key
   npm run docker:up
   npm run migrate
   npm run seed
   npm run dev
   # Open http://localhost:3010
   ```

9. **Final check** — run through docs/DEMO_SCRIPT.md step by step. Every step must work perfectly. Fix anything that breaks.

When done, update docs/ROADMAP.md Loop 7 status to ✅ and run:
openclaw system event --text "AuthAgent Loop 7 complete: DEMO READY. Open http://localhost:3010" --mode now

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

## Pre-install Playwright (for next loop)
At the end of this loop, install Playwright so it's ready for the test suite:
```bash
cd /Users/matthew/.openclaw/workspace/monoclaw/projects/auth-agent
npm install --save-dev @playwright/test
npx playwright install chromium --with-deps
```

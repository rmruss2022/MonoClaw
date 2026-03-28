Read docs/DEMO_SCRIPT.md and docs/MVP_SCOPE.md carefully.

Your job is to write and run comprehensive Playwright end-to-end tests that verify the entire AuthAgent MVP works correctly. Do NOT just write tests — actually RUN them and fix any failures you find.

## Setup

1. Install Playwright in the project:
```bash
cd /Users/matthew/.openclaw/workspace/monoclaw/projects/auth-agent
npm install --save-dev @playwright/test
npx playwright install chromium
```

2. Create `playwright.config.ts` at root:
```ts
import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60000,
  use: {
    baseURL: 'http://localhost:3010',
    headless: true,
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: [
    {
      command: 'npm run dev:api',
      port: 3011,
      reuseExistingServer: true,
    },
    {
      command: 'npm run dev:ui',
      port: 3010,
      reuseExistingServer: true,
    },
  ],
});
```

## Test Files to Write + Run

### tests/e2e/01-dashboard.spec.ts
- [ ] Dashboard loads at localhost:3010
- [ ] Shows stats: Total PAs, Approval Rate, Avg Processing Time, $ Recovered
- [ ] Stats have numeric values (not NaN or undefined)
- [ ] PA list table is visible and has rows
- [ ] "New PA Request" button is visible and clickable
- [ ] Navigation links work (Intelligence, Payers, Settings)

### tests/e2e/02-new-pa-wizard.spec.ts
- [ ] Click "New PA Request" → lands on /pa/new
- [ ] Step 1: Can select a payer from dropdown
- [ ] Step 1: Can enter a CPT code (type "72148" and see autocomplete)
- [ ] Step 1: Can select patient ID
- [ ] Step 2: File upload zone is visible
- [ ] Step 2: Upload a test PDF file (create a simple one in tests/fixtures/)
- [ ] Step 3: "Analyze" button triggers AI extraction
- [ ] Step 3: Clinical extract shows diagnosis, symptoms, duration fields
- [ ] Step 3: No "undefined" or empty values in extract
- [ ] Step 4: "Generate Justification" button works
- [ ] Step 4: Letter text appears (minimum 200 words)
- [ ] Step 4: Letter quality score is shown (number between 1-10)
- [ ] Step 5: Probability score gauge is visible (number between 0-100)
- [ ] Step 5: At least 3 probability factors listed
- [ ] Step 6: "Submit" button visible
- [ ] Full wizard completes without JavaScript errors

### tests/e2e/03-pa-detail.spec.ts
- [ ] Click a PA from dashboard → loads /pa/:id
- [ ] Status badge visible and has a valid value
- [ ] Clinical extract section expandable
- [ ] Justification letter section shows text
- [ ] Timeline section shows at least 1 event
- [ ] Probability gauge shows score
- [ ] For a denied PA: "Generate Appeal" button is visible
- [ ] Appeal generation: click button → letter appears in under 30 seconds
- [ ] Appeal letter has at least 150 words
- [ ] Appeal deadline badge visible

### tests/e2e/04-payer-intelligence.spec.ts
- [ ] /intelligence page loads
- [ ] Shows denial rate stats by payer
- [ ] Shows win rate by CARC code
- [ ] Charts render without errors (no blank canvases)

### tests/e2e/05-api-health.spec.ts
Direct API tests (not UI):
- [ ] GET /api/health → 200
- [ ] GET /api/payers → 200, returns array of 5 payers
- [ ] GET /api/pa?practice_id=demo → 200, returns array
- [ ] POST /api/pa/analyze with sample clinical text → returns clinical extract with diagnosis field
- [ ] POST /api/pa/:id/generate-justification → returns letter text
- [ ] GET /api/dashboard/stats → returns object with totalPAs, approvalRate, avgProcessingDays, totalRecovered

### tests/e2e/06-demo-flow.spec.ts
Run the exact demo from DEMO_SCRIPT.md end-to-end:
- [ ] Dashboard loads with pre-populated demo stats
- [ ] Navigate to a demo "approved" PA → shows approved status
- [ ] Navigate to a demo "denied" PA → shows denied status + appeal button
- [ ] Create new PA using demo patient + United Healthcare + CPT 72148
- [ ] Upload tests/fixtures/lumbar_notes_demo.txt (create this)
- [ ] Complete all wizard steps
- [ ] PA appears in dashboard list after creation
- [ ] All steps complete in under 3 minutes total

## Test Fixtures to Create

**tests/fixtures/lumbar_notes_demo.txt:**
```
OFFICE NOTE
Patient: Demo Patient (ID: DEMO-001)
Date: March 20, 2026
Provider: Dr. Sarah Johnson, MD - Tri-State Orthopedics

CHIEF COMPLAINT: Lower back pain with right leg radiation

HISTORY OF PRESENT ILLNESS:
Patient is a 52-year-old male presenting with an 8-week history of progressive lower back pain with radiation down the right leg to the knee. Pain rated 7/10. Patient has undergone 6 weeks of physical therapy with minimal improvement. NSAIDs (ibuprofen 600mg TID) have provided inadequate pain relief. Patient reports numbness in right L4-L5 distribution. No bowel or bladder dysfunction.

PHYSICAL EXAMINATION:
Positive straight leg raise on the right at 45 degrees. Decreased sensation in right L4-L5 dermatome. 4+/5 strength right EHL. Mild antalgic gait.

ASSESSMENT/PLAN:
1. Lumbar radiculopathy, right L4-L5 (M54.42)
2. Low back pain (M54.5)
Failed conservative treatment including 6 weeks PT and medication management.
Requesting MRI lumbar spine without contrast (CPT 72148) to evaluate for disc herniation or stenosis.

Physical Therapy Summary: 6 weeks, 18 sessions, minimal improvement per PT notes attached.
```

**tests/fixtures/test-upload.pdf:** Create programmatically in test setup using a simple PDF library.

## Running Tests

After writing all tests, run them:
```bash
cd /Users/matthew/.openclaw/workspace/monoclaw/projects/auth-agent

# Make sure services are running
npm run docker:up
sleep 5
npm run migrate
npm run seed

# Start services in background
npm run dev:api &
API_PID=$!
sleep 3
npm run dev:ui &
UI_PID=$!
sleep 5

# Run tests
npx playwright test --reporter=list 2>&1 | tee /tmp/playwright-results.txt

# Show results
echo "=== TEST RESULTS ==="
cat /tmp/playwright-results.txt | tail -20
```

## CRITICAL: Fix All Failures

If any test fails:
1. Read the failure message carefully
2. Fix the underlying code (not just the test)
3. Re-run that specific test: `npx playwright test tests/e2e/XX-name.spec.ts`
4. Do NOT mark a test as passing by skipping it or using `.skip`
5. Do NOT catch errors in tests just to make them pass — fix the actual bug

Keep iterating until ALL tests pass. A test suite with 1 failure is not acceptable.

## Final Report

Create `tests/TEST_RESULTS.md`:
```markdown
# AuthAgent Test Results
Date: [today]
Total Tests: XX
Passed: XX
Failed: 0

## Coverage
- Dashboard: ✅
- New PA Wizard: ✅
- PA Detail + Appeals: ✅
- Payer Intelligence: ✅
- API Health: ✅
- Full Demo Flow: ✅

## Known Limitations
[any edge cases not covered]
```

When ALL tests pass, run:
openclaw system event --text "AuthAgent ALL TESTS PASSING ✅ — MVP is demo-ready at localhost:3010" --mode now

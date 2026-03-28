Read docs/ROADMAP.md Loop 3 and docs/MVP_SCOPE.md section on Core AI Agent Logic.

Build the AI justification drafter — the core of the product:

1. **src/agents/buildJustification.js** — Complete implementation:
   - Takes: clinicalFacts (from extractClinical), payerRequirements, cptCode, payerName
   - Returns: structured PA letter with all sections
   - Uses Claude claude-sonnet-4-6 with a carefully engineered system prompt
   - Must generate ALL 8 letter sections from MVP_SCOPE.md
   - Must cite specific payer criteria in the letter
   - Must flag gaps: which requirements are missing documentation

2. **src/prompts/justification-system.txt** — Detailed system prompt for the justification agent:
   - Establishes it as a clinical documentation specialist
   - Instructions for each letter section
   - How to cite clinical guidelines
   - How to handle missing documentation
   - Tone: professional medical, not defensive or combative

3. **src/prompts/justification-templates/** — One template per specialty:
   - orthopedic.txt (knee/hip/spine procedures)
   - neurology.txt (MRI/nerve studies)
   - cardiology.txt (stress tests/echo)
   - behavioral-health.txt (psych medications/therapy)
   - general.txt (catchall)

4. **src/api/routes/pa.js** — Add POST /api/pa/:id/generate-justification endpoint

5. **UI update: app/pa/new/page.tsx** — Step to show/edit the generated justification:
   - Streaming display as letter generates (SSE or polling)
   - Rich text editor (use simple textarea with markdown support)
   - "Regenerate" button
   - Track edit percentage (original vs final) — store in DB

6. **Quality check** — After generating, run a second Claude prompt that:
   - Scores the letter (1-10) on: completeness, payer-specificity, clinical accuracy
   - Returns suggestions if score < 7
   - Show score in UI as "Letter Quality: 8.5/10"

Test with all 10 synthetic clinical note samples from data/samples/.
Each should produce a letter that addresses that payer's specific criteria.

When done, update docs/ROADMAP.md Loop 3 status to ✅ and run:
openclaw system event --text "AuthAgent Loop 3 complete: AI justification drafter working" --mode now

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

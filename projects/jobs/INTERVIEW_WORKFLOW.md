# Interview Sync Workflow

## Automatic Process

Whenever Matthew asks to:
- "Check my calendar"
- "Sync calendar interviews"
- "Update job tracker from calendar"
- Or any variation of calendar/interview syncing

**Automatically perform these steps:**

1. **Fetch calendar events** using gcalcli for the relevant date range
2. **Match calendar events to companies** in the job tracker
3. **Extract interviewer names** from event titles (patterns: "Call with X", "Interview with X", etc.)
4. **Research new interviewers** (only if not already researched):
   - Search LinkedIn: `"{Name}" {Company} site:linkedin.com/in`
   - Pull profile data (title, background, experience)
   - Create summary paragraph
5. **Add to job tracker** under the interview record as:
   ```json
   "interviewer": {
     "name": "Full Name",
     "title": "Their Title",
     "linkedin": "https://linkedin.com/in/profile" or null,
     "summary": "Multi-line background summary with LinkedIn link at bottom"
   }
   ```
6. **Update dashboard** (data.json is auto-synced, dashboard refreshes every 30s)

## Interviewer Summary Format

```
**{Name}** - {Title} at {Company}

{Background paragraph with role details, experience, what they work on}

{Optional: Note about why LinkedIn not found if applicable}

🔗 {LinkedIn URL if found}
```

## Tracking Already-Researched

Keep track in `/Users/matthew/.openclaw/workspace/jobs/processed-interviewers.json`:
```json
{
  "interviewers": {
    "Company Name:Interviewer Name": true
  }
}
```

## When LinkedIn Not Found

Valid reasons to note in summary:
- "LinkedIn profile not found (common for engineers who keep profiles private)"
- "LinkedIn profile not found under this spelling - may use different name professionally"
- "LinkedIn profile not found (last name unknown)"
- "LinkedIn profile not found - may use different name or spelling"

## Important Notes

- **Always fix spelling** based on Matthew's corrections (e.g., Sean → Shaan)
- **Search variations** if first search fails (full name, first name only, different spellings)
- **Include context** from interview notes in the summary
- **Don't duplicate** - check processed-interviewers.json first
- **Quality over speed** - Better to have good summaries than fast bad ones

This process happens automatically. Matthew should never have to ask "research the interviewers" separately.

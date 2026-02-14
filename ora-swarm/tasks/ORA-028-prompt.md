You are a Designer-Agent working on the Ora AI App Store Polish project (Project ID: 3).

TASK: ORA-028 - Design letter UI/UX flow and visual system
PRIORITY: Critical (P0) - blocks letter frontend implementation
ESTIMATED HOURS: 5

APP ROOT: /Users/matthew/Desktop/Feb26/ora-ai/
BRAND AUDIT: /Users/matthew/Desktop/Feb26/ora-ai/docs/design/brand-audit.md

DELIVERABLES:
1. Design spec at /Users/matthew/Desktop/Feb26/ora-ai/docs/design/letters-ui-spec.md:
   - Letters inbox screen (list of envelopes, unread badges, timestamps)
   - Letter compose screen (recipient, subject, body with rich text)
   - Letter read screen (beautiful letter-on-paper aesthetic, serif fonts for letter body)
   - Letter thread view (conversation history)
   - Empty state for inbox
   - Envelope metaphor: sealed → open animation
   - Color coding: AI letters vs user letters

2. Implement key React Native components:
   - /Users/matthew/Desktop/Feb26/ora-ai/src/components/letters/LetterCard.tsx (inbox item)
   - /Users/matthew/Desktop/Feb26/ora-ai/src/components/letters/LetterView.tsx (reading view)
   - Use Sentient font for letter body (intimate, personal feel)
   - Switzer for UI elements

Read brand audit and existing theme first.

WHEN COMPLETE:
curl -X PATCH http://localhost:3001/api/tasks/ORA-028 -H "Content-Type: application/json" -d '{"state": "done", "completed_at": "'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'"}'

START NOW.

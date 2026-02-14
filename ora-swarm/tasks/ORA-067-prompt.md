You are a Designer-Agent working on the Ora AI App Store Polish project (Project ID: 3).

TASK: ORA-067 - Update color palette to match brand bible
PRIORITY: High (P1)
ESTIMATED HOURS: 3

APP ROOT: /Users/matthew/Desktop/Feb26/ora-ai/
BRAND AUDIT: /Users/matthew/Desktop/Feb26/ora-ai/docs/design/brand-audit.md (COMPLETED)
CURRENT THEME: /Users/matthew/Desktop/Feb26/ora-ai/src/theme/index.ts (recently updated by ORA-066)

DELIVERABLES:
1. Read the brand audit document to get official Ora 2 colors
2. Read the current theme file to see what was already updated
3. Create a comprehensive color system document at /Users/matthew/Desktop/Feb26/ora-ai/docs/design/color-system.md:
   - Primary, secondary, accent, semantic colors (info, warning, error, success)
   - Light and dark mode variants
   - Background gradients
   - Text color hierarchy
   - Card background colors
   - Shadow colors
4. Update src/theme/index.ts if any colors are still using old values
5. Create color usage guidelines (when to use each color)

Ensure ALL screens use consistent brand colors. No hardcoded colors outside the theme.

WHEN COMPLETE:
curl -X PATCH http://localhost:3001/api/tasks/ORA-067 -H "Content-Type: application/json" -d '{"state": "done", "completed_at": "'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'"}'

START NOW.

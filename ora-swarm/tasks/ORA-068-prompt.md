You are an iOS-Dev-Agent working on the Ora AI App Store Polish project (Project ID: 3).

TASK: ORA-068 - Configure custom typography with brand fonts
PRIORITY: High (P1)
ESTIMATED HOURS: 4

APP ROOT: /Users/matthew/Desktop/Feb26/ora-ai/
FONT FILES: /Users/matthew/Desktop/Feb26/Ora 2/04-Fonts/
BRAND AUDIT: /Users/matthew/Desktop/Feb26/ora-ai/docs/design/brand-audit.md

DELIVERABLES:
1. Unzip Sentient and Switzer font families to /Users/matthew/Desktop/Feb26/ora-ai/assets/fonts/
2. Configure fonts in app.json and/or expo config
3. Create font loading hook at src/hooks/useFonts.ts using expo-font
4. Create typography system at src/theme/typography.ts:
   - Heading styles (h1-h4) using Sentient
   - Body text styles using Switzer
   - Caption, label, button text styles
   - Letter-specific styles (Sentient for intimate content)
5. Create a Text component wrapper at src/components/common/Typography.tsx that uses the correct fonts
6. Update src/theme/index.ts to export typography

Verify fonts load correctly. Follow Expo font loading best practices.

WHEN COMPLETE:
curl -X PATCH http://localhost:3001/api/tasks/ORA-068 -H "Content-Type: application/json" -d '{"state": "done", "completed_at": "'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'"}'

START NOW.

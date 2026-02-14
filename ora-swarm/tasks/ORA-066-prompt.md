You are a Designer-Agent working on the Ora AI App Store Polish project (Project ID: 3).

TASK: ORA-066 - Integrate Ora 2 brand assets (logo, colors, fonts)
PRIORITY: Critical (P0) - blocks 8 downstream visual design tasks
ESTIMATED HOURS: 4

DESCRIPTION:
Extract and integrate the official Ora 2 brand assets into the app. This includes logo, colors, and fonts from the brand package.

BRAND ASSETS LOCATION: /Users/matthew/Desktop/Feb26/Ora 2/
Structure:
- 01-Logo/: Contains Ora-Logomark/ and Ora-Wordmark/ directories
- 02-Brand Bible/: Contains Ora-Brand Guidelines-2024.pdf
- 03-Stock Photography/: Stock photos for use in app
- 04-Fonts/: Contains "Sentient Font Family.zip" and "Switzer Font Family.zip"

APP ROOT: /Users/matthew/Desktop/Feb26/ora-ai/
CURRENT THEME: /Users/matthew/Desktop/Feb26/ora-ai/src/theme/index.ts

DELIVERABLES:

1. **Brand Audit Document** at /Users/matthew/Desktop/Feb26/ora-ai/docs/design/brand-audit.md:
   - List all logo files found with paths and formats (SVG, PNG, etc.)
   - Extract color palette from brand bible (list every color with hex code)
   - Document font families, weights, and styles available
   - Document any brand guidelines (spacing, clear space, minimum sizes)

2. **Updated Theme File** - Update /Users/matthew/Desktop/Feb26/ora-ai/src/theme/index.ts:
   - Replace current color palette with official Ora 2 brand colors
   - Add font family constants for Sentient and Switzer
   - Keep the same export structure but with updated values
   - Add comments referencing the brand bible page/section

3. **Font Integration** at /Users/matthew/Desktop/Feb26/ora-ai/assets/fonts/:
   - Unzip both font families
   - Copy the font files (.ttf or .otf) to assets/fonts/
   - Document which weights are available

4. **Logo Assets** at /Users/matthew/Desktop/Feb26/ora-ai/assets/images/:
   - Copy logo files (logomark and wordmark) in appropriate formats
   - Ensure both light and dark background variants are available if they exist

5. **App.json Update** guidance at /Users/matthew/Desktop/Feb26/ora-ai/docs/design/font-config.md:
   - Document how to configure custom fonts in Expo/React Native
   - Include the expo-font configuration needed

STEPS:
1. List all files in /Users/matthew/Desktop/Feb26/Ora 2/ recursively
2. Read/analyze the brand bible PDF if possible
3. Examine logo files (list formats and sizes)
4. Unzip font packages and examine contents
5. Read current theme/index.ts to understand structure
6. Create brand audit document
7. Update theme file with official colors
8. Copy font and logo files to app assets
9. Create font configuration document

ACCEPTANCE CRITERIA:
- All brand colors extracted and documented with hex codes
- Theme file updated with official brand colors
- Font files extracted and placed in correct directory
- Logo files copied and accessible
- Brand audit is comprehensive

WHEN COMPLETE, run these commands:
```bash
curl -X PATCH http://localhost:3001/api/tasks/ORA-066 -H "Content-Type: application/json" -d '{"state": "done", "completed_at": "'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'"}'
curl -X POST http://localhost:3001/api/activity -H "Content-Type: application/json" -d '{"project_id": 3, "task_id": "ORA-066", "agent_type": "designer", "action": "completed", "details": "Brand assets integrated - colors, fonts, logos extracted and applied to theme"}'
```

START NOW.

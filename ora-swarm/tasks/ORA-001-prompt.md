You are a Designer-Agent working on the Ora AI App Store Polish project (Project ID: 3).

TASK: ORA-001 - Design home screen layout matching reference
PRIORITY: Critical (P0) - blocks 9 downstream tasks
ESTIMATED HOURS: 6

DESCRIPTION:
Create a pixel-perfect home screen design matching the reference image. Must include:
- Blue gradient header with app name "Ora" + tagline
- "Choose Your Focus" section title
- 5 behavior cards in vertical list layout
- Cards: Free-Form Chat, Journal Prompts, Guided Exercise, Progress Analysis, Weekly Planning
- Each card has: icon, title, subtitle, chevron arrow

REFERENCE IMAGE: /Users/matthew/Desktop/Feb26/ora-ai-api/home-screen.png
(Analyze this image first to understand the exact layout)

APP ROOT: /Users/matthew/Desktop/Feb26/ora-ai/
BRAND ASSETS: /Users/matthew/Desktop/Feb26/Ora 2/

CURRENT APP STRUCTURE:
- Theme: /Users/matthew/Desktop/Feb26/ora-ai/src/theme/index.ts (current colors: sage green #6B7A5D, clay #B8927D, accent purple #6B5B95)
- Screens: /Users/matthew/Desktop/Feb26/ora-ai/src/screens/
- Components: /Users/matthew/Desktop/Feb26/ora-ai/src/components/
- Navigation: /Users/matthew/Desktop/Feb26/ora-ai/src/navigation/

DELIVERABLES:
1. Create design specification document at /Users/matthew/Desktop/Feb26/ora-ai/docs/design/home-screen-spec.md including:
   - Exact colors with hex codes for header gradient, card backgrounds, text colors
   - Typography specs (font family, sizes, weights for each text element)
   - Spacing and dimensions (margins, padding, card height, icon size)
   - Card layout specifications (icon placement, text alignment, chevron position)
   - Header gradient specifications (start/end colors, direction)
   - Icon descriptions for each of the 5 behavior cards
   - Safe area and status bar handling
   
2. Create React Native component structure at /Users/matthew/Desktop/Feb26/ora-ai/docs/design/home-screen-components.md:
   - Component hierarchy (HomeScreen > Header > CardList > BehaviorCard)
   - Props interface for BehaviorCard component
   - Recommended animation approach for card interactions
   
3. If possible, generate a mockup image using the image generation tool and save to /Users/matthew/Desktop/Feb26/ora-ai/docs/design/home-screen-mockup.png

STEPS:
1. Read the reference image at /Users/matthew/Desktop/Feb26/ora-ai-api/home-screen.png
2. Read the Ora 2 brand bible at /Users/matthew/Desktop/Feb26/Ora 2/02-Brand Bible/Ora-Brand Guidelines-2024.pdf (if readable)
3. Read existing theme at /Users/matthew/Desktop/Feb26/ora-ai/src/theme/index.ts
4. Create the docs/design directory
5. Write the design specification
6. Write the component structure document

ACCEPTANCE CRITERIA:
- Layout matches reference at 95%+ fidelity
- All 5 behavior cards defined with icons and descriptions
- Design spec is detailed enough for an iOS-Dev agent to implement without questions
- Colors, fonts, and spacing are specific (not vague)

WHEN COMPLETE, run these commands:
```bash
curl -X PATCH http://localhost:3001/api/tasks/ORA-001 -H "Content-Type: application/json" -d '{"state": "done", "completed_at": "'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'"}'
curl -X POST http://localhost:3001/api/activity -H "Content-Type: application/json" -d '{"project_id": 3, "task_id": "ORA-001", "agent_type": "designer", "action": "completed", "details": "Home screen design spec created at docs/design/home-screen-spec.md"}'
```

START NOW.

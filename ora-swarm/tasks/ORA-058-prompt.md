You are an iOS-Dev-Agent working on the Ora AI App Store Polish project (Project ID: 3).

TASK: ORA-058 - Redesign meditation timer with circular progress
PRIORITY: High (P1)
ESTIMATED HOURS: 5

APP ROOT: /Users/matthew/Desktop/Feb26/ora-ai/
EXISTING: /Users/matthew/Desktop/Feb26/ora-ai/src/screens/MeditationScreen.tsx

DELIVERABLES:
1. Redesign MeditationScreen.tsx with:
   - Beautiful circular progress timer (SVG-based with react-native-svg)
   - Gradient ring that fills as time progresses
   - Timer display in center (mm:ss format)
   - Play/Pause button with smooth animation
   - Stop button to end early
   - Duration selector (5, 10, 15, 20, 30 minutes)
   - Ambient background gradient that shifts during session

2. Create src/components/meditation/CircularTimer.tsx:
   - Animated SVG circle
   - Smooth countdown
   - Pulse animation on complete
   - Configurable colors, stroke width

3. Create src/components/meditation/DurationPicker.tsx:
   - Horizontal pill selector
   - Smooth selection animation

4. Completion celebration:
   - Haptic feedback
   - "Well done" message
   - Session stats (duration, date)
   - Option to log mood after

Read existing MeditationScreen first. Follow existing theme/patterns. Make it Calm/Headspace quality.

WHEN COMPLETE:
curl -X PATCH http://localhost:3001/api/tasks/ORA-058 -H "Content-Type: application/json" -d '{"state": "done", "completed_at": "'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'"}'

START NOW.

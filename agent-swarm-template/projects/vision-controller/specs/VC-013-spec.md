# VC-013: Custom Gesture Training UI
**Agent Type:** backend-dev
**Dependencies:** VC-010

Add training mode for recording custom gestures.

## Deliverables
- Frontend: Add "Train Gesture" button in app.js that enters training mode
- Training mode captures 30 frames of landmarks via WebSocket
- Backend: Add POST /api/train-gesture endpoint in main.py
- Accepts { name: string, samples: landmark_frames[] }
- Saves to /Users/matthew/Desktop/vision-controller/config/custom_gestures.json
- Update gesture_classifier.py to load and match custom gestures

## When Complete
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE tasks SET state='done', completed_at=datetime('now') WHERE id='VC-013';"

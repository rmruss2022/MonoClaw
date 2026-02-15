# VC-007: Electron Shell + Camera Preview

**Agent Type:** UI-Dev  
**Priority:** High  
**Estimated:** 40 minutes  
**Dependencies:** None

## Objective
Create Electron desktop app with live camera preview and WebSocket connection to backend.

## Project Context
- **Frontend Root:** `/Users/matthew/Desktop/vision-controller/frontend/`
- **Tech Stack:** Electron, camera APIs, WebSocket client

## Deliverables

### 1. `/Users/matthew/Desktop/vision-controller/frontend/package.json`
```json
{
  "name": "vision-controller-frontend",
  "version": "1.0.0",
  "main": "main.js",
  "scripts": {
    "start": "electron .",
    "dev": "electron . --inspect"
  },
  "dependencies": {
    "electron": "^27.1.0"
  }
}
```

### 2. `/Users/matthew/Desktop/vision-controller/frontend/main.js`
Electron main process that creates window with camera permissions.

### 3. `/Users/matthew/Desktop/vision-controller/frontend/index.html`
HTML with video element for camera preview and status display.

### 4. `/Users/matthew/Desktop/vision-controller/frontend/app.js`
Camera access + WebSocket connection to backend.

## Technical Requirements
- Electron 27+ (latest stable)
- Camera access via `getUserMedia` API
- WebSocket client connecting to `ws://127.0.0.1:8765/ws/gestures`
- Auto-reconnect on WebSocket disconnect
- Video preview at 640x480 resolution
- Development tools enabled for debugging

## Success Criteria
- [ ] Electron app launches successfully
- [ ] Camera preview shows live feed
- [ ] WebSocket connects to backend (port 8765)
- [ ] Status indicator shows connection state
- [ ] Gesture display updates from WebSocket messages
- [ ] Clean UI with dark theme

## Installation & Testing
```bash
cd /Users/matthew/Desktop/vision-controller/frontend
npm install
npm start
```

**Expected behavior:**
1. Window opens showing camera feed
2. Status shows "Backend: Disconnected" (backend not running yet)
3. When backend starts, status changes to "Backend: Connected"

## References
- Electron Quick Start: https://www.electronjs.org/docs/latest/tutorial/quick-start
- getUserMedia API: https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia
- WebSocket API: https://developer.mozilla.org/en-US/docs/Web/API/WebSocket

## Database Update on Completion
When complete, run:
```bash
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE tasks SET state='done', completed_at=datetime('now') WHERE id='VC-007';"
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE agents SET status='completed', completed_at=datetime('now'), result='SUMMARY: Electron app with camera preview at frontend/, WebSocket client ready' WHERE agent_id='agent-VC-007';"
```

Complete all deliverables above and report back.

# VC-007: Electron Shell + Camera Preview
**Agent Type:** UI-Dev
**Priority:** High
**Estimated:** 40 minutes
**Dependencies:** None

## Objective
Create Electron desktop app with live camera preview and WebSocket connection to backend.

## Project Context
- **Frontend Root:** `/Users/matthew/Desktop/vision-controller/frontend/`
- **Tech Stack:** Electron, React, camera APIs, WebSocket client

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
Electron main process:
- Create 800x600 window
- Enable camera permissions
- Load `index.html`

```javascript
const { app, BrowserWindow } = require('electron');
const path = require('path');

function createWindow() {
  const win = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });
  
  win.loadFile('index.html');
  win.webContents.openDevTools(); // For development
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
```

### 3. `/Users/matthew/Desktop/vision-controller/frontend/index.html`
```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Vision Controller</title>
  <style>
    body {
      margin: 0;
      padding: 20px;
      font-family: -apple-system, system-ui, sans-serif;
      background: #1a1a1a;
      color: #fff;
    }
    #container {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 20px;
    }
    video {
      width: 640px;
      height: 480px;
      background: #000;
      border-radius: 8px;
    }
    #status {
      padding: 10px 20px;
      border-radius: 6px;
      background: #333;
    }
    .connected { color: #4caf50; }
    .disconnected { color: #f44336; }
  </style>
</head>
<body>
  <div id="container">
    <h1>🤚 Vision Controller</h1>
    <video id="camera" autoplay playsinline></video>
    <div id="status" class="disconnected">Backend: Disconnected</div>
    <div id="gesture">Gesture: <span id="gesture-name">—</span></div>
  </div>
  
  <script src="app.js"></script>
</body>
</html>
```

### 4. `/Users/matthew/Desktop/vision-controller/frontend/app.js`
Camera access + WebSocket connection:

```javascript
const video = document.getElementById('camera');
const statusEl = document.getElementById('status');
const gestureNameEl = document.getElementById('gesture-name');

let ws = null;

// Request camera access
async function initCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: 640, height: 480 }
    });
    video.srcObject = stream;
    console.log('Camera initialized');
  } catch (err) {
    console.error('Camera error:', err);
    alert('Failed to access camera: ' + err.message);
  }
}

// Connect to backend WebSocket
function connectWebSocket() {
  ws = new WebSocket('ws://127.0.0.1:8765/ws/gestures');
  
  ws.onopen = () => {
    console.log('WebSocket connected');
    statusEl.textContent = 'Backend: Connected';
    statusEl.className = 'connected';
  };
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'gesture_detected') {
      gestureNameEl.textContent = `${data.gesture} (${(data.confidence * 100).toFixed(0)}%)`;
    }
  };
  
  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
  };
  
  ws.onclose = () => {
    console.log('WebSocket disconnected');
    statusEl.textContent = 'Backend: Disconnected';
    statusEl.className = 'disconnected';
    
    // Reconnect after 3 seconds
    setTimeout(connectWebSocket, 3000);
  };
}

// Initialize
initCamera();
connectWebSocket();
```

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
```bash
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE tasks SET state='done', completed_at=datetime('now') WHERE id='VC-007';"
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE agents SET status='completed', completed_at=datetime('now'), result='SUMMARY: Electron app with camera preview at frontend/, WebSocket client ready' WHERE agent_id='agent-VC-007';"
```

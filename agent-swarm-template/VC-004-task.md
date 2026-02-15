# VC-004: FastAPI Server with WebSocket

**Agent Type:** Backend-Dev  
**Priority:** High  
**Estimated:** 30 minutes  
**Dependencies:** None

## Objective
Create FastAPI backend server with WebSocket endpoint for real-time gesture streaming.

## Project Context
- **Backend Root:** `/Users/matthew/Desktop/vision-controller/backend/`
- **Tech Stack:** Python, FastAPI, WebSocket, uvicorn

## Deliverables

### 1. `/Users/matthew/Desktop/vision-controller/backend/api/main.py`
FastAPI application with:
- Health check endpoint: `GET /health`
- WebSocket endpoint: `WS /ws/gestures`
- CORS enabled for Electron frontend

```python
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import json

app = FastAPI(title="Vision Controller API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow Electron app
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.websocket("/ws/gestures")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    # TODO: Connect to gesture recognition pipeline
    # For now, echo back messages
    while True:
        data = await websocket.receive_json()
        # Process gesture data
        await websocket.send_json({"type": "gesture_detected", "gesture": "test"})
```

### 2. `/Users/matthew/Desktop/vision-controller/backend/api/__init__.py`
Empty file (Python package marker)

### 3. `/Users/matthew/Desktop/vision-controller/backend/requirements.txt`
Add dependencies:
```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
websockets==12.0
python-multipart==0.0.6
```

### 4. `/Users/matthew/Desktop/vision-controller/backend/run.sh`
Launch script:
```bash
#!/bin/bash
cd "$(dirname "$0")"
uvicorn api.main:app --host 127.0.0.1 --port 8765 --reload
```

## API Specification

### WebSocket `/ws/gestures`

**Client → Server:**
```json
{
  "type": "video_frame",
  "frame": "<base64 encoded image>",
  "timestamp": 1234567890
}
```

**Server → Client:**
```json
{
  "type": "gesture_detected",
  "gesture": "peace",
  "confidence": 0.95,
  "hand": "right",
  "timestamp": 1234567890
}
```

## Technical Requirements
- WebSocket connection stays alive during session
- Handle connection drops gracefully
- Support multiple simultaneous clients (optional)
- JSON message format
- Port: 8765 (or configurable via env var)

## Success Criteria
- [ ] FastAPI server starts successfully
- [ ] Health check returns `{"status": "ok"}`
- [ ] WebSocket accepts connections
- [ ] Can send/receive JSON messages
- [ ] Server runs with `--reload` for development
- [ ] No CORS errors from Electron frontend

## Testing
```bash
# Start server
cd /Users/matthew/Desktop/vision-controller/backend
bash run.sh

# Test health check (in another terminal)
curl http://127.0.0.1:8765/health

# Test WebSocket (using websocat or browser DevTools)
websocat ws://127.0.0.1:8765/ws/gestures
```

## References
- FastAPI WebSocket: https://fastapi.tiangolo.com/advanced/websockets/
- uvicorn: https://www.uvicorn.org/

## Database Update on Completion
When complete, run:
```bash
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE tasks SET state='done', completed_at=datetime('now') WHERE id='VC-004';"
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE agents SET status='completed', completed_at=datetime('now'), result='SUMMARY: FastAPI server with WebSocket at backend/api/main.py, running on port 8765' WHERE agent_id='agent-VC-004';"
```

Complete all deliverables above and report back.

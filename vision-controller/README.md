# Vision Controller

Real-time hand gesture recognition service for OpenClaw.

## Quick Start

```bash
cd ~/.openclaw/workspace/vision-controller
node server.js
```

Open: http://127.0.0.1:18799

## Features

- **5 Built-in Gestures:** peace, thumbs_up, fist, point, stop
- **Real-time Detection:** MediaPipe hand tracking with WebSocket streaming
- **Auto-restart:** Supervisor keeps backend running
- **~150-200ms Latency:** Optimized for real-time interaction

## Architecture

- **Frontend:** http://127.0.0.1:18799 (Node.js static server)
- **Backend:** http://127.0.0.1:9000 (Python FastAPI)
- **WebSocket:** ws://localhost:9000/ws/gestures

## Configuration

Edit `config/gestures.json` to map gestures to actions.

## Logs

- `backend/logs/backend.log` - All detections
- `backend/logs/backend.error.log` - Errors only
- `backend/logs/supervisor.log` - Restart events

## Health Check

```bash
curl http://127.0.0.1:18799/health
```

## Requirements

- Python 3.14+ with venv
- Node.js
- MediaPipe (installed in venv)
- FastAPI/Uvicorn (installed in venv)

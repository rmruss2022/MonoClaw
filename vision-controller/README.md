# Vision Controller

Real-time hand gesture recognition for OpenClaw using MediaPipe and FastAPI.

## Quick Start

```bash
cd ~/.openclaw/workspace/vision-controller
node server.js
```

Then open: http://127.0.0.1:18799

## Architecture

- **Frontend:** Vanilla JS, WebSocket client (port 18799)
- **Backend:** Python FastAPI + MediaPipe (port 9000)
- **WebSocket:** Real-time gesture detection stream

## Supported Gestures

- **peace** - Index + middle fingers extended
- **thumbs_up** - Thumb up
- **fist** - All fingers closed
- **point** - Index finger extended
- **stop** - All fingers extended (open palm)

## Configuration

Edit `config/gestures.json` to map gestures to actions.

## Logs

Backend logs in: `backend/logs/`
- `backend.log` - All detections
- `backend.error.log` - Errors only
- `supervisor.log` - Restart events

## Performance

- Latency: ~150-200ms average
- Frame rate: 15 FPS
- Resolution: 320x240 (downscaled)

## Requirements

- Python 3.14+ with venv
- Node.js
- MediaPipe
- FastAPI/Uvicorn

See `backend/requirements.txt` for Python dependencies.

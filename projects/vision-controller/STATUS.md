# Vision Controller - System Status

## ✅ Currently Running

**Backend (with auto-restart supervisor):**
- URL: http://127.0.0.1:9000
- WebSocket: ws://127.0.0.1:9000/ws/gestures
- Supervisor: `/Users/matthew/Desktop/vision-controller/backend/supervisor.sh`
- Auto-restarts on crash (max 10 attempts, resets after 5min uptime)

**Frontend:**
- URL: http://127.0.0.1:18799
- Serves from: `/Users/matthew/Desktop/vision-controller/frontend/`

## 📋 Log Files

All logs in: `/Users/matthew/Desktop/vision-controller/backend/logs/`

- **supervisor.log** - Supervisor start/stop/restart events
- **backend.log** - Backend stdout (gesture detections, processing times)
- **backend.error.log** - Backend errors only

**To check logs:**
```bash
# Supervisor status
tail -f ~/Desktop/vision-controller/backend/logs/supervisor.log

# Backend detections
tail -f ~/Desktop/vision-controller/backend/logs/backend.log

# Errors only
tail -f ~/Desktop/vision-controller/backend/logs/backend.error.log
```

## 🔄 Redundancy Features

1. **Auto-restart** - Backend restarts automatically on crash
2. **Restart limiting** - Max 10 restarts to prevent infinite loops
3. **Smart reset** - Restart counter resets after 5 minutes uptime
4. **Full logging** - All stdout and stderr captured
5. **Timestamp tracking** - Know exactly when crashes happen

## 🚀 Starting/Stopping

**Start backend:**
```bash
/Users/matthew/Desktop/vision-controller/backend/supervisor.sh &
```

**Stop backend:**
```bash
pkill -f supervisor.sh
pkill -f "uvicorn.*9000"
```

**Start frontend:**
```bash
python3 -m http.server 18799 --directory ~/Desktop/vision-controller/frontend &
```

## 🐛 Debugging

**Check if running:**
```bash
curl http://127.0.0.1:9000/health
curl http://127.0.0.1:18799/
```

**Watch live detections:**
```bash
tail -f ~/Desktop/vision-controller/backend/logs/backend.log | grep CHANGE
```

**Count crashes:**
```bash
grep "Backend exited" ~/Desktop/vision-controller/backend/logs/supervisor.log
```

## ⚡ Performance

Current performance (from logs):
- Decode: 0-3ms
- Hand detection: 125-320ms (MediaPipe)
- Classification: 0-2ms
- WebSocket send: 0-1ms
- **Total: ~150-200ms average**

## 🎯 Current Configuration

- **Change detection:** DISABLED (sends every detection)
- **Confidence threshold:** 70%
- **Frame rate:** 15 FPS (66ms interval)
- **Resolution:** 320x240 (downscaled from 640x480)
- **JPEG quality:** 0.5

## 🔧 Known Issues

- Backend log file grows large (181MB) - consider log rotation
- MediaPipe warnings about NORM_RECT (non-critical)

## 📝 Next Steps

1. Add log rotation to prevent disk fill
2. Re-enable smart change detection once stability confirmed
3. Integrate into OpenClaw service manager
4. Add gesture → action mapping UI

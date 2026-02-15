# Vision Controller - Project Setup Plan
**Created:** 2026-02-14 22:52 EST
**Orchestrator Model:** nvidia/moonshotai/kimi-k2.5
**Duration:** 4 hours persistent run

## 🎯 Project Overview

**Name:** Vision Controller - Hand Sign Recognition System
**Description:** Real-time hand sign recognition with programmable action triggers
**Goal:** OpenCV/MediaPipe hand tracking → recognize gestures → trigger macOS/OpenClaw actions

## 📋 Tech Stack

```json
{
  "frontend": "Electron (for UI/preview)",
  "backend": "Python FastAPI",
  "ml": ["OpenCV", "MediaPipe Hands", "TensorFlow Lite"],
  "integration": ["AppleScript", "OpenClaw RPC", "keyboard/mouse control"],
  "deployment": "Desktop app (macOS initially)"
}
```

## 🧠 Agent Specializations Needed

1. **CV-Engineer** (Computer Vision)
   - MediaPipe Hands integration
   - Hand landmark detection
   - Gesture classification model
   - Real-time video processing

2. **Backend-Dev** (Python/FastAPI)
   - API server for gesture → action mapping
   - WebSocket for real-time gesture stream
   - Configuration management
   - Action dispatcher (AppleScript, OpenClaw RPC)

3. **UI-Dev** (Electron/React)
   - Camera preview window
   - Gesture configuration UI
   - Visual feedback overlay
   - Action library browser

4. **ML-Engineer** (Training/Optimization)
   - Custom gesture dataset collection
   - Fine-tune gesture classifier
   - Optimize for low-latency inference
   - False positive reduction

## 📁 Project File Structure

```
/Users/matthew/Desktop/vision-controller/
├── backend/
│   ├── api/
│   │   ├── main.py              # FastAPI app
│   │   ├── gesture_handler.py   # Gesture recognition
│   │   └── action_dispatcher.py # Trigger actions
│   ├── ml/
│   │   ├── hand_detector.py     # MediaPipe wrapper
│   │   ├── gesture_classifier.py
│   │   └── models/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Main UI
│   │   ├── CameraPreview.jsx    # Live feed
│   │   ├── GestureConfig.jsx    # Gesture → action mapping
│   │   └── ActionLibrary.jsx    # Browse available actions
│   └── package.json
├── config/
│   └── gestures.json            # Gesture definitions
└── scripts/
    └── install.sh               # Setup script
```

## 🔢 Task Breakdown (Estimated)

### Phase 1: Core CV Pipeline (90 min)
- **VC-001** [CV-Engineer, 30min] - Set up MediaPipe Hands detection
- **VC-002** [CV-Engineer, 40min] - Implement basic gesture recognition (5 gestures: peace, thumbs up, fist, point, stop)
- **VC-003** [CV-Engineer, 20min] - Add gesture confidence scoring

### Phase 2: Backend API (60 min)
- **VC-004** [Backend-Dev, 30min] - FastAPI server with WebSocket
- **VC-005** [Backend-Dev, 20min] - Action dispatcher (AppleScript + OpenClaw RPC)
- **VC-006** [Backend-Dev, 10min] - Configuration system (load/save gesture mappings)

### Phase 3: Frontend UI (90 min)
- **VC-007** [UI-Dev, 40min] - Electron shell + camera preview
- **VC-008** [UI-Dev, 30min] - Gesture config UI (map gestures → actions)
- **VC-009** [UI-Dev, 20min] - Visual feedback overlay (show detected gesture)

### Phase 4: Integration & Testing (40 min)
- **VC-010** [Backend-Dev, 20min] - Wire frontend ↔ backend WebSocket
- **VC-011** [CV-Engineer, 20min] - Latency optimization & calibration

**Total:** 4 hours 20 minutes (with buffer for 4-hour orchestrator run)

## 🎨 Initial Gesture → Action Mappings

| Gesture | Action Example |
|---------|---------------|
| ✌️ Peace | Open OpenClaw dashboard |
| 👍 Thumbs Up | Send "approve" message to Signal |
| ✊ Fist | Lock screen |
| 👉 Point Right | Next browser tab |
| ✋ Stop | Pause/play media |

## 🚀 Orchestrator Configuration

```javascript
{
  "project_id": 4, // Next available ID
  "model": "nvidia/moonshotai/kimi-k2.5",
  "max_active_agents": 3,
  "check_interval_ms": 300000, // 5 min
  "duration_hours": 4,
  "auto_spawn": true,
  "priority_order": ["VC-001", "VC-004", "VC-007", "..."]
}
```

## 📝 Orchestrator Spawn Command

```bash
# 1. Insert project into swarm database
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db <<EOF
INSERT INTO projects (name, description, reference, status, created_at, configuration_json)
VALUES (
  'Vision Controller',
  'Real-time hand sign recognition with programmable action triggers',
  '/Users/matthew/Desktop/vision-controller/',
  'not-started',
  datetime('now'),
  '{"tech_stack": {"frontend": "Electron", "backend": "Python FastAPI", "ml": ["OpenCV", "MediaPipe", "TensorFlow Lite"]}, "orchestrator_docs_path": "/Users/matthew/.openclaw/workspace/agent-swarm-template/projects/vision-controller"}'
);
EOF

# 2. Insert tasks (VC-001 through VC-011)
# ... (task insertion SQL)

# 3. Create orchestrator.js for Vision Controller
cp /Users/matthew/.openclaw/workspace/agent-swarm-template/orchestrator.js \
   /Users/matthew/.openclaw/workspace/agent-swarm-template/vision-orchestrator.js

# Edit: PROJECT_ID = 4, MODEL = 'nvidia/moonshotai/kimi-k2.5'

# 4. Start persistent orchestrator (4-hour run)
nohup node /Users/matthew/.openclaw/workspace/agent-swarm-template/vision-orchestrator.js > vision-orchestrator.log 2>&1 &

# 5. Monitor via dashboard
open http://localhost:5173
```

## 📊 Success Criteria

- [ ] MediaPipe Hands detecting 21 landmarks in real-time
- [ ] 5 basic gestures recognized with >90% accuracy
- [ ] <100ms latency from gesture → action
- [ ] Electron UI showing live camera feed + overlay
- [ ] 3 working action integrations (OpenClaw, AppleScript, keyboard)
- [ ] Configuration persists across restarts

## 🎯 Next Steps

1. **Create database entries** - Insert project + 11 tasks
2. **Set up project directory** - `/Users/matthew/Desktop/vision-controller/`
3. **Copy orchestrator template** - Customize for Vision Controller (project_id=4, kimi model)
4. **Start orchestrator** - 4-hour persistent run
5. **Monitor dashboard** - Watch agents spawn and complete tasks at http://localhost:5173

---

**Ready to execute?** Say the word and I'll:
1. Insert the project into the swarm database
2. Create all 11 tasks with dependencies
3. Set up the orchestrator config
4. Start the 4-hour Kimmy-powered orchestrator run

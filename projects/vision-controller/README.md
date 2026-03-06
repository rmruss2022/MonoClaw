# Vision Controller

Real-time hand gesture recognition service for OpenClaw, with a **gesture-driven window manager** for macOS.

## Quick Start

### Headless Window Manager (no browser needed)

```bash
cd ~/.openclaw/workspace/vision-controller/backend
python3 -u run_headless.py
```

This opens your webcam directly, detects hand gestures, and snaps windows. A preview window shows what the camera sees. Press `q` to quit.

To run without the preview window:

```bash
HEADLESS_NO_PREVIEW=1 python3 -u run_headless.py
```

### Browser-Based Mode (original)

```bash
cd ~/.openclaw/workspace/vision-controller
node server.js  # frontend on http://127.0.0.1:18799
cd backend
python3 -m uvicorn api.main:app --host 127.0.0.1 --port 9000
```

## Gesture Window Manager

Control macOS windows with hand gestures detected via webcam. Finger count determines layout, hand position determines which monitor and zone.

### Gestures

| Gesture | Fingers | Action |
|---------|---------|--------|
| **Point** | Index finger only | Select frontmost window, snap **full screen** on the monitor your hand points at |
| **Peace** | Index + middle | Snap to **half screen** — move hand left/right to choose which half |
| **Four fingers** | All except thumb | Snap to **quarter screen** — hand position picks the quadrant |
| **Open palm (stop)** | All five fingers | **Deselect** window, return to idle |
| **Fist** | None | No-op (safe idle pose) |
| **Thumbs up** | Thumb only | No-op |

### How It Works

1. **Camera** captures frames at ~15 FPS via OpenCV
2. **MediaPipe HandLandmarker** extracts 21 hand landmarks (wrist, finger joints, fingertips)
3. **GestureClassifier** determines which gesture based on finger extension patterns (tip-to-base distance + vertical checks)
4. **PositionTracker** maps the hand's normalized (x,y) position to screen coordinates across all monitors using `Quartz.CGDisplayBounds`
5. **WindowModeStateMachine** tracks state (idle → selected → snapping) with 350ms debounce
6. **WindowManager** uses the macOS Accessibility API (`AXUIElement`) to move and resize the selected window

### Display Layout Detection

The system auto-detects all connected monitors via Quartz and sorts them left-to-right. The camera image is mirrored (webcam convention), so moving your hand left in the camera moves the target zone to the right on screen.

### Testing Window Snaps

Interactive test tool (no camera needed):

```bash
cd ~/.openclaw/workspace/vision-controller/backend
python3 test_snap.py
```

This prints all 14 snap zones across your monitors. Click on a window, come back to the terminal, type a zone number to snap it.

## macOS Permissions Required

- **Camera**: Grant to Terminal.app (or whichever app runs the script) in System Settings > Privacy & Security > Camera
- **Accessibility**: Grant to Terminal.app in System Settings > Privacy & Security > Accessibility (required for moving/resizing windows)

## Architecture

```
backend/
  run_headless.py              # Headless entry point (camera + gestures + window mgmt)
  test_snap.py                 # Interactive snap testing tool
  ml/
    hand_detector.py           # MediaPipe hand landmark detection
    gesture_classifier.py      # Rule-based gesture classification (6 gestures)
    position_tracker.py        # Hand position → screen coordinates across monitors
    combo_detector.py          # Gesture sequence detection (unused currently)
  api/
    main.py                    # FastAPI server + WebSocket handler
    window_manager.py          # Quartz/Accessibility window enumeration + snap/resize
    window_mode_state_machine.py  # Gesture → window action state machine
    action_dispatcher.py       # Keyboard/AppleScript/RPC action execution
    config_manager.py          # Gesture config loader
config/
  gestures.json                # Gesture → action mappings
frontend/
  index.html                   # Browser-based webcam UI (optional)
  app.js                       # Frontend WebSocket client
server.js                      # Node.js static file server for frontend
```

## API Endpoints (when running FastAPI server)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/window-mode/status` | GET | Current window mode state (enabled, selected window) |
| `/api/window-mode/toggle` | POST | Enable/disable window management mode |
| `/api/actions/recent` | GET | Recent action execution log |
| `/api/config/gestures` | GET | Current gesture config |
| `/ws/gestures` | WebSocket | Real-time gesture detection stream |

## Dependencies

```
mediapipe==0.10.32
opencv-python==4.8.1.78
numpy==1.24.3
fastapi==0.104.1
uvicorn[standard]==0.24.0
websockets==12.0
python-multipart==0.0.6
pyobjc-framework-Quartz
pyobjc-framework-ApplicationServices
```

Install:

```bash
pip install -r backend/requirements.txt
```

## Original Features

- **6 Built-in Gestures:** peace, thumbs_up, fist, point, stop, four_fingers
- **Custom Gesture Training:** POST samples to `/api/train-gesture`
- **Real-time Detection:** MediaPipe hand tracking (~100-200ms latency)
- **Action Dispatch:** Keyboard shortcuts, AppleScript, OpenClaw RPC
- **Peace → Wispr Flow:** Default mapping triggers Ctrl+Space on peace gesture

# VC-001: Set up MediaPipe Hands Detection

**Agent Type:** CV-Engineer  
**Priority:** High  
**Estimated:** 30 minutes  
**Dependencies:** None

## Objective
Install MediaPipe library and create a Python wrapper for real-time hand detection.

## Project Context
- **Backend Root:** `/Users/matthew/Desktop/vision-controller/backend/`
- **ML Directory:** `/Users/matthew/Desktop/vision-controller/backend/ml/`
- **Tech Stack:** Python, OpenCV, MediaPipe Hands

## Deliverables

### 1. `/Users/matthew/Desktop/vision-controller/backend/requirements.txt`
```txt
mediapipe==0.10.9
opencv-python==4.8.1.78
numpy==1.24.3
```

### 2. `/Users/matthew/Desktop/vision-controller/backend/ml/hand_detector.py`
Create `HandDetector` class with:
- `__init__(min_detection_confidence=0.7, min_tracking_confidence=0.5)` - Initialize MediaPipe Hands
- `detect(frame)` - Takes BGR image, returns list of hands with 21 landmarks each
- `close()` - Clean up resources

**Expected output format:**
```python
[
  {
    "handedness": "Left" or "Right",
    "landmarks": [
      {"x": 0.5, "y": 0.3, "z": 0.01},  # Wrist (0)
      {"x": 0.52, "y": 0.28, "z": 0.02},  # Thumb CMC (1)
      # ... 21 landmarks total
    ],
    "confidence": 0.95
  }
]
```

### 3. `/Users/matthew/Desktop/vision-controller/backend/ml/test_hand_detector.py`
Test script that:
- Captures webcam (OpenCV)
- Detects hands in each frame
- Prints FPS and landmark count
- Press 'q' to quit

## Technical Requirements
- MediaPipe Hands solution (multi-hand tracking)
- Real-time processing: >30 FPS on webcam feed
- Return normalized coordinates (0-1 range)
- Include z-depth for 3D gestures (optional but recommended)

## Success Criteria
- [ ] MediaPipe Hands initialized successfully
- [ ] `detect()` method returns 21 landmarks per hand
- [ ] FPS > 30 on 720p webcam feed
- [ ] Test script runs without errors
- [ ] Code is well-documented with docstrings

## References
- MediaPipe Hands: https://google.github.io/mediapipe/solutions/hands.html
- Hand landmark diagram: 21 points (WRIST, THUMB_*, INDEX_*, etc.)
- MediaPipe Python API: `mediapipe.solutions.hands`

## Database Update on Completion
When complete, run:
```bash
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE tasks SET state='done', completed_at=datetime('now') WHERE id='VC-001';"
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE agents SET status='completed', completed_at=datetime('now'), result='SUMMARY: MediaPipe Hands wrapper created at backend/ml/hand_detector.py, test script validated >30 FPS' WHERE agent_id='agent-VC-001';"
```

Complete all deliverables above and report back.

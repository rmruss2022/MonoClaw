# VC-002: Implement Basic Gesture Recognition
**Agent Type:** CV-Engineer
**Priority:** High
**Estimated:** 40 minutes
**Dependencies:** VC-001

## Objective
Recognize 5 basic gestures from hand landmarks: peace ✌️, thumbs up 👍, fist ✊, point 👉, stop ✋

## Deliverables

### `/Users/matthew/Desktop/vision-controller/backend/ml/gesture_classifier.py`
Create `GestureClassifier` class with:
- `classify(landmarks)` - Takes 21 landmarks, returns gesture name + confidence
- Support for 5 gestures using geometric rules

**Gesture detection rules:**
- **Peace:** Index and middle fingers extended, others closed
- **Thumbs Up:** Thumb extended up, others closed
- **Fist:** All fingers closed
- **Point:** Index finger extended, others closed
- **Stop:** All fingers extended, palm forward

Output format:
```python
{
  "gesture": "peace",
  "confidence": 0.92,
  "hand": "right"
}
```

### Test script
`test_gesture_classifier.py` - Test with webcam + overlay showing detected gesture

## Success Criteria
- [ ] 5 gestures recognized with >85% accuracy
- [ ] Confidence scoring (0-1 range)
- [ ] Works with both left and right hands
- [ ] Real-time performance (>30 FPS)

## Database Update
```bash
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE tasks SET state='done', completed_at=datetime('now') WHERE id='VC-002';"
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE agents SET status='completed', completed_at=datetime('now'), result='SUMMARY: Gesture classifier with 5 gestures at backend/ml/gesture_classifier.py' WHERE agent_id='agent-VC-002';"
```

# VC-016: Unit Test Suite
**Agent Type:** backend-dev
**Dependencies:** none

Write pytest unit tests for core backend modules.

## Deliverables
- Create /Users/matthew/Desktop/vision-controller/backend/tests/
- test_gesture_classifier.py: Test all 5 gestures with synthetic landmarks, edge cases, unknown gestures
- test_hand_detector.py: Test initialization, mock MediaPipe results
- test_action_dispatcher.py: Test action dispatch for each action type
- test_config_manager.py: Test load/save/update config operations
- Create conftest.py with shared fixtures (sample landmarks for each gesture)
- Minimum: 15 test functions total

## When Complete
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE tasks SET state='done', completed_at=datetime('now') WHERE id='VC-016';"

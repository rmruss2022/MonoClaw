# VC-015: Multi-Gesture Combos
**Agent Type:** backend-dev
**Dependencies:** VC-002, VC-010

Implement gesture combo/sequence detection.

## Deliverables
- Create /Users/matthew/Desktop/vision-controller/backend/ml/combo_detector.py
- ComboDetector class tracks gesture sequence within configurable time window (default 2s)
- Combos defined in gestures.json under "combos" key: { "name": "special", "sequence": ["peace", "fist"], "action": "..." }
- Integrate into WebSocket handler in main.py: after gesture classification, check for combos
- Return combo matches alongside individual gesture results

## When Complete
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE tasks SET state='done', completed_at=datetime('now') WHERE id='VC-015';"

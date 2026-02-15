# VC-003: Add Gesture Confidence Scoring
**Agent Type:** CV-Engineer
**Priority:** Medium
**Estimated:** 20 minutes
**Dependencies:** VC-002

## Objective
Add confidence thresholds and false positive filtering.

## Deliverables
- Confidence threshold (default 0.7)
- Temporal smoothing (3-frame window)
- Filter out ambiguous gestures

## Success Criteria
- [ ] <5% false positive rate
- [ ] Smooth gesture transitions

## Database Update
```bash
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE tasks SET state='done', completed_at=datetime('now') WHERE id='VC-003';"
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE agents SET status='completed', completed_at=datetime('now'), result='SUMMARY: Confidence scoring added to gesture_classifier.py' WHERE agent_id='agent-VC-003';"
```

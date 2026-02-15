# VC-009: Visual Feedback Overlay
**Agent Type:** UI-Dev
**Priority:** Medium
**Estimated:** 20 minutes
**Dependencies:** VC-007

## Objective
Add overlay showing detected gesture + confidence in real-time.

## Deliverables
- Canvas overlay on video element
- Display gesture name + confidence %
- Color-coded by confidence (green >80%, yellow 60-80%, red <60%)

## Success Criteria
- [ ] Overlay updates <100ms latency
- [ ] Smooth animations

## Database Update
```bash
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE tasks SET state='done', completed_at=datetime('now') WHERE id='VC-009';"
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE agents SET status='completed', completed_at=datetime('now'), result='SUMMARY: Visual overlay added to frontend/app.js' WHERE agent_id='agent-VC-009';"
```

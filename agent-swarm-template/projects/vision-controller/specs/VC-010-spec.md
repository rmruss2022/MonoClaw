# VC-010: Frontend-Backend WebSocket Integration
**Agent Type:** Backend-Dev
**Priority:** High
**Estimated:** 20 minutes
**Dependencies:** VC-002, VC-004, VC-007

## Objective
Wire frontend camera feed → backend gesture recognition via WebSocket.

## Deliverables
- Capture video frames in frontend (10 FPS)
- Send frames to backend via WebSocket
- Backend processes with HandDetector + GestureClassifier
- Return gesture results to frontend

## Success Criteria
- [ ] End-to-end gesture detection working
- [ ] <100ms latency
- [ ] No frame drops

## Database Update
```bash
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE tasks SET state='done', completed_at=datetime('now') WHERE id='VC-010';"
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE agents SET status='completed', completed_at=datetime('now'), result='SUMMARY: WebSocket integration complete, gesture detection working end-to-end' WHERE agent_id='agent-VC-010';"
```

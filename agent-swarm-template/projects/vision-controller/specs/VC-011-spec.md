# VC-011: Latency Optimization
**Agent Type:** CV-Engineer
**Priority:** Medium
**Estimated:** 20 minutes
**Dependencies:** VC-010

## Objective
Optimize for <100ms gesture → action latency.

## Deliverables
- Profile bottlenecks
- Reduce frame processing time
- Add calibration UI for confidence thresholds
- Performance metrics dashboard

## Success Criteria
- [ ] <100ms end-to-end latency
- [ ] 30+ FPS processing

## Database Update
```bash
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE tasks SET state='done', completed_at=datetime('now') WHERE id='VC-011';"
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE agents SET status='completed', completed_at=datetime('now'), result='SUMMARY: Latency optimized to <100ms, calibration UI added' WHERE agent_id='agent-VC-011';"
```

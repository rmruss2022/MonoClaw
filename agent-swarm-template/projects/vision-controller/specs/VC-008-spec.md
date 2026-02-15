# VC-008: Gesture Config UI
**Agent Type:** UI-Dev
**Priority:** Medium
**Estimated:** 30 minutes
**Dependencies:** VC-007

## Objective
Build UI for mapping gestures to actions.

## Deliverables
- Settings panel in Electron app
- Drag-and-drop action library
- Save/load from config/gestures.json

## Success Criteria
- [ ] Can edit gesture mappings
- [ ] Changes persist across restarts

## Database Update
```bash
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE tasks SET state='done', completed_at=datetime('now') WHERE id='VC-008';"
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE agents SET status='completed', completed_at=datetime('now'), result='SUMMARY: Config UI added to frontend/index.html' WHERE agent_id='agent-VC-008';"
```

# VC-006: Configuration System
**Agent Type:** Backend-Dev
**Priority:** Medium
**Estimated:** 10 minutes
**Dependencies:** VC-004

## Objective
Load/save gesture → action mappings in JSON config.

## Deliverables
`/Users/matthew/Desktop/vision-controller/config/gestures.json`:
```json
{
  "peace": {"action": "applescript", "script": "tell application \"System Events\" to keystroke \"d\" using command down"},
  "thumbs_up": {"action": "openclaw_rpc", "method": "/api/message", "params": {"text": "👍"}}
}
```

## Database Update
```bash
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE tasks SET state='done', completed_at=datetime('now') WHERE id='VC-006';"
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE agents SET status='completed', completed_at=datetime('now'), result='SUMMARY: Config system at config/gestures.json' WHERE agent_id='agent-VC-006';"
```

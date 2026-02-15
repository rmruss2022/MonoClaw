# VC-005: Action Dispatcher
**Agent Type:** Backend-Dev
**Priority:** High
**Estimated:** 20 minutes
**Dependencies:** VC-004

## Objective
Build action dispatcher that triggers AppleScript, OpenClaw RPC, and keyboard/mouse control.

## Deliverables

### `/Users/matthew/Desktop/vision-controller/backend/api/action_dispatcher.py`
```python
class ActionDispatcher:
    def execute(self, action_type, params):
        """Execute an action based on type"""
        if action_type == "applescript":
            return self._run_applescript(params['script'])
        elif action_type == "openclaw_rpc":
            return self._openclaw_rpc(params['method'], params['args'])
        elif action_type == "keyboard":
            return self._keyboard_action(params['keys'])
```

**Supported actions:**
- AppleScript (using `osascript` command)
- OpenClaw RPC (HTTP calls to localhost:18795)
- Keyboard shortcuts (using `pynput` library)

### Update requirements.txt
```txt
pynput==1.7.6
requests==2.31.0
```

## Success Criteria
- [ ] Can trigger AppleScript commands
- [ ] Can call OpenClaw RPC endpoints
- [ ] Can send keyboard shortcuts
- [ ] Error handling for failed actions

## Database Update
```bash
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE tasks SET state='done', completed_at=datetime('now') WHERE id='VC-005';"
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "UPDATE agents SET status='completed', completed_at=datetime('now'), result='SUMMARY: Action dispatcher at backend/api/action_dispatcher.py' WHERE agent_id='agent-VC-005';"
```

# Orchestrator Usage

## Architecture

The orchestrator is a **lightweight Node.js daemon** that:
- Polls database every 5 minutes
- Spawns agents for ready tasks (max 8 concurrent)
- Processes completed agents
- Maintains <50K token context
- Self-contained (no OpenClaw sub-agent bloat)

**Key principle:** Agents are isolated. Orchestrator only sees summaries.

## Start Orchestrator

```bash
cd /Users/matthew/.openclaw/workspace/agent-swarm-template

# Start in foreground (for testing)
node orchestrator.js

# Start in background
nohup node orchestrator.js > orchestrator.log 2>&1 &

# Check if running
ps aux | grep "node orchestrator.js" | grep -v grep

# View logs
tail -f orchestrator.log

# Stop
pkill -f "node orchestrator.js"
```

## Monitor Progress

### Check active agents
```bash
sqlite3 swarm.db "SELECT agent_id, task_id, status FROM agents WHERE project_id = 3 AND status = 'running';"
```

### Check completed tasks
```bash
sqlite3 swarm.db "SELECT COUNT(*), state FROM tasks WHERE project_id = 3 GROUP BY state;"
```

### View activity log
```bash
sqlite3 swarm.db "SELECT timestamp, event_type, task_id, message FROM activity_log WHERE project_id = 3 ORDER BY id DESC LIMIT 20;"
```

### Check orchestrator state
```bash
cat orchestrator-state.json
```

## How Agents Work

Each agent:
1. Gets spawned via `openclaw sessions send`
2. Runs in isolated session `agent:swarm:{AGENT_ID}`
3. Reads spec file if exists
4. Completes work
5. Updates database with summary (<500 chars)
6. Session cleaned up after timeout/completion

**Agents never communicate with orchestrator directly.**
Orchestrator polls database for results.

## Troubleshooting

### Agent stuck in "running"
```bash
# Check if agent session exists
openclaw sessions list | grep "agent:swarm"

# If not, mark as timeout
sqlite3 swarm.db "UPDATE agents SET status='timeout', completed_at=datetime('now') WHERE agent_id='agent-ORA-XXX';"
sqlite3 swarm.db "UPDATE tasks SET state='todo', assigned_to=NULL WHERE id='ORA-XXX';"
```

### Orchestrator using too much memory
- Should stay under 100MB
- Restarts automatically if >150K tokens (future enhancement)
- Logs to activity_log table, not in-memory

### No agents spawning
- Check ready tasks: `sqlite3 swarm.db "SELECT COUNT(*) FROM tasks WHERE project_id = 3 AND state = 'todo';"`
- Check active count: `sqlite3 swarm.db "SELECT COUNT(*) FROM agents WHERE project_id = 3 AND status = 'running';"`
- View orchestrator logs: `tail -f orchestrator.log`

## Clean Slate Restart

```bash
# Stop orchestrator
pkill -f "node orchestrator.js"

# Reset all in-progress tasks
sqlite3 swarm.db "UPDATE tasks SET state='todo', assigned_to=NULL, started_at=NULL WHERE project_id = 3 AND state = 'in_progress';"

# Clean up stale agents
sqlite3 swarm.db "UPDATE agents SET status='timeout' WHERE project_id = 3 AND status = 'running';"

# Remove state file
rm orchestrator-state.json

# Restart
nohup node orchestrator.js > orchestrator.log 2>&1 &
```

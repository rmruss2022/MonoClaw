# Agent Swarm Orchestrator Architecture

## Core Principles

### 1. Isolated Agent Sessions
- Each agent spawned via `sessions_spawn` gets a fresh, isolated session
- Agents never share context with orchestrator or each other
- Agent sessions auto-cleanup after completion or timeout

### 2. Summarized Results Only
- Orchestrator receives **summary** of agent work, NOT full context
- Agent reports: task ID, status (done/failed), deliverable locations, key findings
- Max 500 chars per agent result
- Full agent transcripts archived, not loaded into orchestrator

### 3. Token Management
- Orchestrator maintains **lightweight state**:
  - Current wave of active agents (IDs only)
  - Last 10 completed task summaries
  - Next 10 ready tasks to spawn
- Total orchestrator context: <50K tokens target
- No reading large files (specs, docs) - agents read those

### 4. Session Pruning
- Delete completed agent sessions after result captured
- Orchestrator self-restarts every 100 tasks or 200K tokens
- Archive activity log to database, not in-memory

## Orchestrator Loop

```
LOOP (every 5 minutes):
  1. Query DB for completed agents (status='completed')
  2. For each completed:
     - Read result summary (from agents.result column, max 500 chars)
     - Update task state to 'done' or 'failed'
     - Mark agent as processed
     - Log to activity table
     - Delete agent session (cleanup)
  
  3. Query DB for ready tasks (state='todo', no dependencies, limit 10)
  4. Count active agents
  5. If active < 8 AND ready tasks available:
     - Spawn agents for next tasks (up to 8 total)
     - Each spawn:
       * sessions_spawn with isolated session
       * Agent instructed to write summary to agents.result
       * Agent given 1-hour timeout
       * Label: "agent-{TASK-ID}"
  
  6. Sleep 5 minutes
  7. Check orchestrator token count - if >150K, self-restart
```

## Agent Task Template

Each agent receives minimal prompt:

```
Task: {TASK_ID} - {TITLE}

Spec: {SPEC_FILE_PATH if exists, else "No spec - use description"}

Deliverables: {PROJECT_ROOT}

Instructions:
1. Read spec file if provided
2. Complete the task
3. Write files to deliverables location
4. Update database:
   - Mark task done: UPDATE tasks SET state='done', completed_at=now() WHERE id='{TASK_ID}'
   - Log result: UPDATE agents SET result='Summary: {what you built, where files are}' WHERE agent_id='{AGENT_ID}'
5. Keep result summary <500 chars

Model: nvidia/moonshotai/kimi-k2.5
Timeout: 3600s
```

## Database Schema

```sql
-- agents.result column stores summary
ALTER TABLE agents ADD COLUMN result TEXT;

-- Activity log table (instead of in-memory)
CREATE TABLE activity_log (
  id INTEGER PRIMARY KEY,
  project_id INTEGER,
  timestamp TEXT,
  agent_id TEXT,
  task_id TEXT,
  event_type TEXT, -- spawned, completed, failed, timeout
  message TEXT
);
```

## Orchestrator State File

Instead of holding state in memory, use lightweight state file:

```json
{
  "lastCheck": "2026-02-13T23:59:00Z",
  "activeAgents": ["agent-ORA-052", "agent-ORA-088"],
  "completedSinceRestart": 15,
  "tokenUsage": 45000
}
```

## Benefits

- ✅ Orchestrator never exceeds 50K tokens
- ✅ Agents work independently with full 256K context
- ✅ Scales to 100+ agents without orchestrator bloat
- ✅ Self-healing: orchestrator restarts don't lose state (all in DB)
- ✅ Fast: no loading large files into orchestrator
- ✅ Clean: old agent sessions auto-pruned

## Implementation

Use `sessions_spawn` with these patterns:

1. **Delivery mode: "none"** - Agent doesn't announce to channels
2. **Cleanup: "delete"** - Session auto-deleted on completion
3. **Agent writes summary to DB** - Not returned via delivery
4. **Orchestrator polls DB** - Not waiting for agent responses

This decouples orchestrator from agent lifecycles completely.

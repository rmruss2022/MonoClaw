# Per-Project Orchestrator Guide

## Overview

Each project gets its own dedicated orchestrator agent that:
- Runs in its own isolated session
- Manages only that project's worker agents
- Updates heartbeat to show live status in dashboard
- Works in project-specific workspace
- Can be spawned/stopped independently

## Architecture

```
Project 1 → Orchestrator Agent 1 → Worker Agents (1a, 1b, 1c...)
Project 2 → Orchestrator Agent 2 → Worker Agents (2a, 2b, 2c...)
Project 3 → Orchestrator Agent 3 → Worker Agents (3a, 3b, 3c...)
```

**No global daemon** - each orchestrator is a long-running OpenClaw sub-agent session.

## How to Spawn an Orchestrator

### Step 1: Prepare the Orchestrator Prompt

```bash
cd /Users/matthew/.openclaw/workspace/agent-swarm-template
node spawn-project-orchestrator.js <project-id>
```

This generates `orchestrator-<project-id>.md` with project-specific context.

### Step 2: Spawn the Agent

From your main OpenClaw session, run:

```typescript
const fs = require('fs');
const orchestratorPrompt = fs.readFileSync(
  '/Users/matthew/.openclaw/workspace/agent-swarm-template/orchestrator-4.md', 
  'utf-8'
);

await sessions_spawn({
  task: orchestratorPrompt,
  label: 'orchestrator-project-4',
  model: 'kimi-k2.5',
  runTimeoutSeconds: 14400,  // 4 hours
  cleanup: 'keep'
});
```

Or simply ask the main agent:

> "Spawn an orchestrator for project 4 using the template at orchestrator-4.md. Label it 'orchestrator-project-4' and give it a 4-hour timeout."

### Step 3: Monitor Progress

The dashboard will show:
- ✅ **Running** - orchestrator is active (heartbeat < 10 min old)
- ⚠️ **Stale** - orchestrator hasn't checked in (10-60 min)
- 🛑 **Stopped** - no recent heartbeat (>1 hour)

## What the Orchestrator Does

1. **Reads all task specs** from the project's specs directory
2. **Builds dependency graph** to determine task order
3. **Spawns Wave 1 agents** (tasks with no dependencies)
4. **Monitors completion** every 5 minutes
5. **Spawns subsequent waves** as dependencies are satisfied
6. **Updates heartbeat** so dashboard shows live status
7. **Exits when done** (all tasks complete)

## Database Heartbeat

The orchestrator updates this table every 5 minutes:

```sql
CREATE TABLE orchestrator_heartbeat (
  project_id INTEGER,
  session_key TEXT,
  updated_at TEXT,
  state_json TEXT
);
```

**Dashboard queries:** `GET /api/projects/:id/orchestrator`

## Worker Agent Flow

Each worker agent gets injected with:
- ✅ Full project context (tech stack, paths, specializations)
- ✅ Complete task spec from `specs/<task-id>-spec.md`
- ✅ Database update commands (mark task done, register completion)
- ✅ Success criteria
- ✅ 1-hour timeout

When a worker completes:

```bash
# Worker runs this automatically
sqlite3 swarm.db "
UPDATE tasks SET state='done', completed_at=datetime('now') WHERE id='VC-001';
UPDATE agents SET status='completed', completed_at=datetime('now') WHERE agent_id='agent-VC-001';
INSERT INTO activity_log (...) VALUES (...);
"
```

## Manual Control

### Check Orchestrator Status

```bash
# Via API
curl http://localhost:3001/api/projects/4/orchestrator | jq

# Via database
sqlite3 swarm.db "SELECT * FROM orchestrator_heartbeat WHERE project_id=4;"
```

### Spawn Missing Workers Manually

If an orchestrator dies, you can spawn workers directly:

```typescript
const spec = await read('/path/to/specs/VC-005-spec.md');
const prompt = `
You are working on: Vision Controller

**Your Task:** VC-005 - Action Dispatcher

${spec}

[Include full project context + database update commands]
`;

await sessions_spawn({
  task: prompt,
  label: 'agent-VC-005',
  model: 'kimi-k2.5',
  runTimeoutSeconds: 3600,
  cleanup: 'keep'
});
```

### Stop an Orchestrator

Orchestrators run until:
- All tasks complete (natural exit)
- Timeout expires (4 hours default)
- Manual kill via sessions tool

To stop manually, find the session key and send an abort:

```bash
# Find session
openclaw sessions list | grep orchestrator-project-4

# Abort (if supported)
# Or just wait for timeout
```

## Best Practices

1. **One orchestrator per project** - don't run multiple orchestrators for the same project
2. **Set reasonable timeouts** - 4 hours is usually enough for small projects
3. **Monitor heartbeat** - if orchestrator goes stale, respawn it
4. **Let orchestrator die naturally** - when all tasks complete, it will exit
5. **Keep database updated** - workers must mark themselves done
6. **Use spawn helper** - `spawn-project-orchestrator.js` handles template substitution

## Troubleshooting

### Dashboard shows "Stopped" but agents are running

The orchestrator died but workers continued. Check active agents:

```bash
sqlite3 swarm.db "SELECT * FROM agents WHERE project_id=4 AND status='running';"
```

Manually update their status when they complete.

### Worker completed but task still "in_progress"

Worker didn't update database. Fix manually:

```bash
sqlite3 swarm.db "
UPDATE tasks SET state='done', completed_at=datetime('now') WHERE id='VC-XXX';
UPDATE agents SET status='completed' WHERE agent_id='agent-VC-XXX';
"
```

### Orchestrator spawned same agent twice

Orchestrator didn't check database before spawning. This shouldn't happen if using the template correctly. Kill duplicate agents.

### How do I restart an orchestrator?

1. Let old one die (timeout or manual kill)
2. Run `node spawn-project-orchestrator.js <project-id>` to refresh template
3. Spawn new orchestrator with fresh session

## Template Customization

Edit `orchestrator-template.md` to change default behavior:
- Polling frequency (default: 5 minutes)
- Spawn strategy (parallel vs sequential)
- Worker timeout (default: 1 hour)
- Heartbeat format
- Exit conditions

Per-project customizations go in the instantiated `orchestrator-<id>.md` file.

---

**🎯 Summary:** Per-project orchestrators give you fine-grained control, better isolation, and accurate dashboard status. No more global daemon!

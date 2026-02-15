# Agent Swarm Architecture Changes - Per-Project Orchestrators

**Date:** 2026-02-14  
**Status:** ✅ Implemented

## What Changed

### Before: Global Orchestrator Daemon ❌
- Single `orchestrator.js` Node.js daemon process
- Managed all projects from one process
- Used `openclaw sessions spawn` CLI (unreliable)
- State stored in `orchestrator-state.json`
- Dashboard checked for running process via `ps aux | grep`
- **Problem:** Brittle, no isolation, CLI spawn doesn't work from scripts

### After: Per-Project Orchestrator Agents ✅
- Each project gets its own orchestrator agent (OpenClaw sub-agent session)
- Orchestrators use `sessions_spawn` tool (reliable)
- Each orchestrator runs independently with 4-hour timeout
- Heartbeat stored in `orchestrator_heartbeat` database table
- Dashboard queries per-project status via `/api/projects/:id/orchestrator`
- **Benefits:** Better isolation, accurate status, independent lifecycle

## New Components

### 1. Orchestrator Template (`orchestrator-template.md`)
Reusable template with placeholders for:
- `{{PROJECT_NAME}}`, `{{PROJECT_ID}}`
- `{{DATABASE_PATH}}`, `{{OUTPUT_PATH}}`, `{{SPECS_PATH}}`
- `{{TECH_STACK}}`, `{{AGENT_SPECIALIZATIONS}}`
- `{{DEPENDENCY_GRAPH}}`

Contains instructions for:
- Checking for ready tasks (dependencies satisfied)
- Spawning worker agents with full context
- Monitoring progress (5-minute polling)
- Updating heartbeat
- Exiting when complete

### 2. Spawn Helper (`spawn-project-orchestrator.js`)
Node.js script that:
- Reads project from database
- Loads orchestrator template
- Substitutes project-specific values
- Generates `orchestrator-<project-id>.md`
- Outputs instructions for spawning via `sessions_spawn`

**Usage:**
```bash
node spawn-project-orchestrator.js <project-id>
```

### 3. Database Schema Addition
New table: `orchestrator_heartbeat`
```sql
CREATE TABLE orchestrator_heartbeat (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL,
  session_key TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  state_json TEXT,
  FOREIGN KEY (project_id) REFERENCES projects(id)
);
```

Orchestrators update this every 5 minutes with:
- Current timestamp
- Session key
- State JSON (tasks count, active agents, next wave)

### 4. Updated API Endpoints

#### New: `GET /api/projects/:id/orchestrator`
Returns per-project orchestrator status:
```json
{
  "status": "running|stale|stopped",
  "isRunning": true,
  "isHealthy": true,
  "lastPoll": "2026-02-15T03:00:00Z",
  "timeSinceLastPoll": 120000,
  "sessionKey": "agent:main:subagent:abc123",
  "activeAgents": [
    {
      "agentId": "agent-VC-002",
      "taskId": "VC-002",
      "taskTitle": "Gesture recognition",
      "spawnedAt": "2026-02-15T02:30:00Z",
      "sessionKey": "agent:main:subagent:xyz789"
    }
  ],
  "completedCount": 3,
  "state": {
    "tasksTotal": 11,
    "tasksCompleted": 3,
    "tasksInProgress": 2,
    "tasksTodo": 6,
    "nextWave": ["agent-VC-010"]
  }
}
```

**Status logic:**
- `running`: heartbeat < 10 minutes old
- `stale`: heartbeat 10-60 minutes old
- `stopped`: heartbeat > 1 hour old or no heartbeat

#### Deprecated: `GET /api/orchestrator/status`
Now returns:
```json
{
  "deprecated": true,
  "message": "Use /api/projects/:id/orchestrator instead",
  "status": "stopped"
}
```

### 5. Dashboard Updates (`dashboard/src/App.jsx`)
Changed from:
```javascript
const orchResponse = await fetch('/api/orchestrator/status');
```

To:
```javascript
const orchResponse = await fetch(`/api/projects/${selectedProject}/orchestrator`);
```

Now queries per-project orchestrator status based on selected project.

### 6. Documentation

Created comprehensive guides:
- `PER_PROJECT_ORCHESTRATOR_GUIDE.md` - How to use per-project orchestrators
- `ARCHITECTURE_CHANGES.md` - This document
- Updated `orchestrator-template.md` - Template with heartbeat instructions

## Migration Path

### For Existing Projects

If you have a project using the old global daemon:

1. **Stop the daemon:**
   ```bash
   pkill -f orchestrator.js
   ```

2. **Generate project-specific orchestrator:**
   ```bash
   cd /Users/matthew/.openclaw/workspace/agent-swarm-template
   node spawn-project-orchestrator.js <project-id>
   ```

3. **Spawn the orchestrator:**
   Ask your main OpenClaw agent:
   > "Spawn an orchestrator for project <id> using orchestrator-<id>.md. Label it 'orchestrator-project-<id>' with a 4-hour timeout."

4. **Verify in dashboard:**
   The Orchestrator Status section should show "Running" within 5 minutes.

### For New Projects

When creating a new project:

1. Create project in database (via API or directly)
2. Add task specs to `projects/<project-name>/specs/`
3. Run `node spawn-project-orchestrator.js <project-id>`
4. Spawn the orchestrator agent
5. Watch progress in dashboard

## Benefits of New Architecture

### Isolation
- Each orchestrator manages only its project
- Failure in one orchestrator doesn't affect others
- Independent timeouts and cleanup

### Reliability
- Uses `sessions_spawn` tool instead of CLI
- Runs as native OpenClaw sub-agent
- Better error handling and context

### Visibility
- Real-time status via heartbeat
- Per-project orchestrator status in dashboard
- Clear distinction between orchestrator and workers

### Scalability
- Run multiple projects simultaneously
- Each orchestrator can have different models/strategies
- No global bottleneck

### Flexibility
- Easy to customize orchestrator behavior per project
- Can spawn orchestrators on-demand
- Natural lifecycle (spawn → work → exit)

## Implementation Details

### Heartbeat Mechanism

Orchestrators execute this every 5 minutes:

```bash
sqlite3 swarm.db "
INSERT OR REPLACE INTO orchestrator_heartbeat (project_id, session_key, updated_at, state_json)
VALUES (4, 'agent:main:subagent:abc123', datetime('now'), '{\"tasksTotal\":11,...}');
"
```

Dashboard polls `GET /api/projects/4/orchestrator` which:
1. Queries `orchestrator_heartbeat` for latest entry
2. Calculates time since last heartbeat
3. Queries `agents` table for active workers
4. Returns combined status

### Worker Agent Context Injection

Each worker agent prompt includes:

```markdown
**Your Task:** VC-001 - MediaPipe Hands Setup

[Full spec content from VC-001-spec.md]

**Project Context:**
- Tech Stack: Python FastAPI, OpenCV, MediaPipe
- Output: /Users/matthew/Desktop/vision-controller/backend/ml/
- Database: /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db

**CRITICAL: Mark yourself done:**
```sql
UPDATE tasks SET state='done', completed_at=datetime('now') WHERE id='VC-001';
UPDATE agents SET status='completed' WHERE agent_id='agent-VC-001';
```

**Success Criteria:**
✅ hand_detector.py created with HandDetector class
✅ Returns 21 hand landmarks
✅ Includes confidence scoring
✅ Database marked as done
```

This ensures workers:
- Know exactly what to build
- Have all necessary context
- Update the database when done
- Include success verification

## Testing

### Verify Database Schema
```bash
sqlite3 swarm.db ".schema orchestrator_heartbeat"
```

### Test API Endpoint
```bash
curl http://localhost:3001/api/projects/4/orchestrator | jq
```

### Check Orchestrator Heartbeat
```bash
sqlite3 swarm.db "SELECT * FROM orchestrator_heartbeat WHERE project_id=4;"
```

### Monitor Active Agents
```bash
sqlite3 swarm.db "SELECT agent_id, task_id, status, spawned_at FROM agents WHERE project_id=4;"
```

## Next Steps

1. ✅ Architecture implemented
2. ✅ Database schema updated
3. ✅ API endpoints created
4. ✅ Dashboard updated
5. ✅ Documentation written
6. ⏭️ **Next:** Spawn orchestrator for Vision Controller project
7. ⏭️ Test full workflow (orchestrator → workers → completion)
8. ⏭️ Monitor in dashboard
9. ⏭️ Verify heartbeat updates
10. ⏭️ Confirm project completion

## Files Modified

- ✏️ `server.js` - Added `orchestrator_heartbeat` table, new endpoint
- ✏️ `dashboard/src/App.jsx` - Updated to use per-project endpoint
- ✨ `orchestrator-template.md` - New reusable template
- ✨ `spawn-project-orchestrator.js` - New helper script
- ✨ `PER_PROJECT_ORCHESTRATOR_GUIDE.md` - New user guide
- ✨ `ARCHITECTURE_CHANGES.md` - This document

## Cleanup

Old files no longer needed (can archive):
- `orchestrator.js` - Old global daemon
- `orchestrator-state.json` - Old state file
- `orchestrator-prompt-template.md` - Old template (replaced by new one)
- `spawn-orchestrator.js` - Old spawn script (CLI-based)

These can be moved to `_archive/` or deleted.

---

**Status:** ✅ Ready to use! Generate an orchestrator for your project and spawn it.

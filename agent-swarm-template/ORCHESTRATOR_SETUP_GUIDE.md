# Orchestrator Setup Guide
**Updated:** 2026-02-14 22:54 EST

## The Problem (Old Approach)

**Old:** `orchestrator.js` = Standalone Node.js daemon
- ❌ Uses shell exec to call `openclaw sessions send`
- ❌ Brittle CLI parsing, no error handling
- ❌ Minimal context injection (just task title + spec path)
- ❌ Doesn't inject tech_stack, file_paths, agent_requirements from database
- ❌ No proper permission model
- ❌ Hard to monitor/debug

## The Solution (New Approach)

**New:** Orchestrator = Persistent Sub-Agent
- ✅ Uses `sessions_spawn` tool (proper API)
- ✅ Full context injection from database
- ✅ Clean permission model (isolated session with spawn rights)
- ✅ Easy to monitor via `sessions_list` and dashboard
- ✅ Proper error handling and retry logic

---

## How It Works

### 1. Orchestrator as Sub-Agent

```
Main Session (you)
    │
    └─▶ Spawn Orchestrator Sub-Agent
            │  (Isolated session, 4-hour timeout)
            │  (Has sessions_spawn permission)
            │
            ├─▶ Spawns Agent 1 (CV-Engineer)
            ├─▶ Spawns Agent 2 (Backend-Dev)
            └─▶ Spawns Agent 3 (UI-Dev)
```

### 2. Permission Model

**Orchestrator sub-agent has:**
- `sessions_spawn` - Can create new isolated sessions (worker agents)
- `exec` - Can run sqlite3 commands to check task status
- `read` - Can read spec files from project directory
- `write` - Can write logs and state files

**Worker agents have:**
- `read/write` - Access to project files
- `exec` - Run build/test commands
- NO `sessions_spawn` - Workers can't spawn more agents

### 3. Context Injection Flow

```
spawn-orchestrator.js
    │
    ├─▶ Read project from database
    │   └─ configuration_json (tech_stack, file_paths, agent_requirements)
    │
    ├─▶ Load orchestrator-prompt-template.md
    │
    ├─▶ Replace template variables with project context
    │   ├─ {{PROJECT_NAME}} → "Vision Controller"
    │   ├─ {{TECH_STACK_JSON}} → {"frontend": "Electron", ...}
    │   ├─ {{FILE_PATHS_JSON}} → {"backend": "/path/to/backend", ...}
    │   └─ {{AGENT_REQUIREMENTS_JSON}} → {"CV-Engineer": [...], ...}
    │
    └─▶ Spawn orchestrator sub-agent with full context
            │
            └─▶ Orchestrator spawns workers with FULL context:
                  - Task spec (read from specs/VC-001-spec.md)
                  - Tech stack details
                  - File paths
                  - Agent specialization skills
                  - Reference materials
                  - Database update commands
```

---

## Quick Start

### Step 1: Create Project in Database

```bash
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db <<EOF
INSERT INTO projects (name, description, reference, status, created_at, configuration_json)
VALUES (
  'Vision Controller',
  'Real-time hand sign recognition with programmable action triggers',
  '/Users/matthew/Desktop/vision-controller/',
  'not-started',
  datetime('now'),
  '{
    "tech_stack": {
      "frontend": "Electron",
      "backend": "Python FastAPI",
      "ml": ["OpenCV", "MediaPipe", "TensorFlow Lite"]
    },
    "file_paths": {
      "backend": "/Users/matthew/Desktop/vision-controller/backend/",
      "frontend": "/Users/matthew/Desktop/vision-controller/frontend/"
    },
    "agent_requirements": {
      "CV-Engineer": ["OpenCV", "MediaPipe", "hand tracking"],
      "Backend-Dev": ["Python", "FastAPI", "WebSocket"],
      "UI-Dev": ["Electron", "React", "camera APIs"]
    },
    "reference_materials": [],
    "max_active_agents": 3,
    "orchestrator_docs_path": "/Users/matthew/.openclaw/workspace/agent-swarm-template/projects/vision-controller"
  }'
);
EOF
```

### Step 2: Create Tasks

```bash
# Insert VC-001, VC-002, etc. (see VISION_CONTROLLER_PLAN.md for full task list)
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db <<EOF
INSERT INTO tasks (project_id, id, title, description, type, state, priority, estimated_hours, dependencies_json)
VALUES
  (4, 'VC-001', 'Set up MediaPipe Hands detection', 'Install MediaPipe, create hand detector wrapper', 'CV-Engineer', 'todo', 'high', 0.5, '[]'),
  (4, 'VC-002', 'Implement basic gesture recognition', 'Recognize 5 gestures from hand landmarks', 'CV-Engineer', 'todo', 'high', 0.67, '["VC-001"]'),
  (4, 'VC-004', 'FastAPI server with WebSocket', 'Create backend API for gesture stream', 'Backend-Dev', 'todo', 'high', 0.5, '[]'),
  (4, 'VC-007', 'Electron shell + camera preview', 'Build Electron app with live camera feed', 'UI-Dev', 'todo', 'high', 0.67, '[]');
  -- ... more tasks
EOF
```

### Step 3: Create Spec Files

```bash
mkdir -p /Users/matthew/.openclaw/workspace/agent-swarm-template/projects/vision-controller/specs

# Create VC-001-spec.md, VC-002-spec.md, etc.
cat > /Users/matthew/.openclaw/workspace/agent-swarm-template/projects/vision-controller/specs/VC-001-spec.md <<'EOF'
# VC-001: Set up MediaPipe Hands Detection
**Type:** CV-Engineer
**Priority:** High
**Estimated:** 30 minutes

## Objective
Install MediaPipe library and create a Python wrapper for hand detection.

## Deliverables
1. `/Users/matthew/Desktop/vision-controller/backend/ml/hand_detector.py`
   - Class: `HandDetector`
   - Method: `detect(frame)` → returns hand landmarks (21 points)
   - Real-time processing (>30 FPS)

2. `/Users/matthew/Desktop/vision-controller/backend/requirements.txt`
   - Add: mediapipe, opencv-python, numpy

3. Test script: `test_hand_detector.py`
   - Capture webcam frame
   - Detect hands
   - Print landmark coordinates

## Success Criteria
- [ ] MediaPipe Hands initialized
- [ ] detect() method returns 21 landmarks per hand
- [ ] FPS > 30 on webcam feed
- [ ] Test script runs without errors

## References
- MediaPipe Hands: https://google.github.io/mediapipe/solutions/hands.html
- Landmark diagram: 21 points (thumb, index, middle, ring, pinky)
EOF
```

### Step 4: Launch Orchestrator

```bash
cd /Users/matthew/.openclaw/workspace/agent-swarm-template

# Spawn orchestrator for project ID 4 (Vision Controller)
node spawn-orchestrator.js 4
```

**Output:**
```
🦞 Spawning Orchestrator for Project 4
────────────────────────────────────────────────────────────
✅ Loaded project: Vision Controller
✅ Built orchestrator prompt (6843 chars)
✅ Prompt saved to: /tmp/orchestrator-prompt-project-4.txt

🚀 Spawning orchestrator sub-agent...
   Agent ID: orchestrator-vision-controller
   Label: Vision Controller Orchestrator
   Model: nvidia/moonshotai/kimi-k2.5
   Timeout: 4 hours (14400 seconds)

📤 Executing spawn command...

✅ Orchestrator spawned successfully!

📊 Monitor orchestrator:
   Dashboard: http://localhost:5173
   Sessions: openclaw sessions list --kinds isolated
   Logs: openclaw sessions history --sessionKey orchestrator-vision-controller
```

### Step 5: Monitor Progress

**Via Dashboard:**
```
open http://localhost:5173
```

**Via CLI:**
```bash
# List all isolated sessions (orchestrator + workers)
openclaw sessions list --kinds isolated

# Check orchestrator logs
openclaw sessions history --sessionKey orchestrator-vision-controller --limit 100

# Check database status
sqlite3 /Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db "SELECT id, title, state, assigned_to FROM tasks WHERE project_id = 4;"
```

---

## Context Injection Checklist

For EVERY worker agent spawned by the orchestrator, inject:

- ✅ **Task spec** - Full content from `specs/{{TASK_ID}}-spec.md`
- ✅ **Tech stack** - From `configuration_json.tech_stack`
- ✅ **File paths** - From `configuration_json.file_paths`
- ✅ **Agent skills** - From `configuration_json.agent_requirements[agent_type]`
- ✅ **Reference materials** - From `configuration_json.reference_materials`
- ✅ **Database commands** - SQL to update task status on completion
- ✅ **Success criteria** - What defines "done"

## Troubleshooting

### "Permission denied" when spawning workers
- **Cause:** Orchestrator doesn't have `sessions_spawn` tool
- **Fix:** Ensure orchestrator is spawned as isolated session (not main session)

### Workers not getting full context
- **Cause:** Orchestrator not reading from database
- **Fix:** Check `configuration_json` in projects table has all fields

### Orchestrator stops after 1 hour
- **Cause:** Default timeout
- **Fix:** Spawn with `--runTimeoutSeconds 14400` (4 hours)

### Tasks stay in "running" forever
- **Cause:** Worker crashed without updating database
- **Fix:** Orchestrator should check for stale tasks (>60min with no updates)

---

## Comparison: Old vs New

| Feature | Old (Standalone Daemon) | New (Sub-Agent) |
|---------|------------------------|-----------------|
| Spawning | CLI `openclaw sessions send` | `sessions_spawn` tool |
| Context Injection | Minimal (title + spec path) | Full (tech, files, skills, refs) |
| Permissions | None (uses shell exec) | Isolated session with spawn rights |
| Monitoring | Check log file | `sessions_list`, dashboard |
| Error Handling | Crashes silently | Proper retries, escalation |
| Database Access | Direct sqlite3 | Via exec tool |

---

## Ready to Go!

You now have:
1. ✅ Full context injection template
2. ✅ Orchestrator spawn script
3. ✅ Proper permission model (sub-agent with sessions_spawn)
4. ✅ Vision Controller project plan

**Next:** Insert Vision Controller project + tasks into database, then run:
```bash
node spawn-orchestrator.js 4
```

The orchestrator will run for 4 hours, spawning agents with FULL context as tasks become ready. 🚀

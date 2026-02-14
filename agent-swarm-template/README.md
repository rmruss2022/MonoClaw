# Agent Swarm Dashboard - Database-Backed Edition

Production-ready React dashboard with **Node.js + Express + SQLite** backend for managing OpenClaw agent swarm projects.

## ✨ Features

- **RESTful API**: Full CRUD operations for projects, tasks, and agents
- **SQLite Database**: Fast, embedded, zero-config database
- **Real-time Updates**: Auto-refresh dashboard with live data
- **Kanban Board**: Visual task management across 5 states
- **Agent Tracking**: Monitor active and completed agents
- **Activity Log**: Complete audit trail of all actions
- **Migration Tools**: Import existing kanban.json files
- **Scalable**: Production-ready architecture

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd agent-swarm-template
npm install
```

### 2. Import Demo Data

```bash
# Import the demo iOS Banking App project
node migrate.js kanban-demo.json
```

### 3. Start Server

```bash
node server.js
```

Server will start on `http://localhost:3001`

### 4. Open Dashboard

Visit: **http://localhost:3001/dashboard.html**

The dashboard will automatically connect to the API and display your project!

## 📊 API Endpoints

### Projects

#### GET /api/projects/:id
Get complete project data including tasks, agents, stats, and activity log.

**Response:**
```json
{
  "project": { "id": 1, "name": "iOS Banking App", ... },
  "stats": { "total_tasks": 12, "completed": 3, ... },
  "tasks": [...],
  "agents": { "active": [...], "completed": [...] },
  "activity_log": [...]
}
```

#### POST /api/projects
Create a new project.

**Request:**
```json
{
  "name": "My Project",
  "description": "Project description",
  "reference": "https://example.com",
  "status": "not-started",
  "target_completion": "2026-03-01T00:00:00Z"
}
```

### Tasks

#### POST /api/tasks
Create a new task.

**Request:**
```json
{
  "id": "task-1",
  "project_id": 1,
  "title": "User Authentication",
  "description": "Login/register flows",
  "state": "todo",
  "priority": "high",
  "estimated_hours": 4,
  "tags": ["auth", "ui"],
  "dependencies": [],
  "code_files": []
}
```

#### PATCH /api/tasks/:id
Update task properties.

**Request:**
```json
{
  "state": "in-progress",
  "assigned_to": "dev-agent-1",
  "actual_hours": 1.5
}
```

### Agents

#### POST /api/agents/assign
Assign an agent to a task.

**Request:**
```json
{
  "project_id": 1,
  "agent_id": "dev-agent-1",
  "session_key": "agent:dev:subagent:abc123",
  "task_id": "task-1"
}
```

#### POST /api/agents/complete
Mark agent as completed.

**Request:**
```json
{
  "agent_id": "dev-agent-1",
  "session_key": "agent:dev:subagent:abc123",
  "result": "Authentication complete ✅"
}
```

### Stats

#### GET /api/stats/:project_id
Get project statistics.

**Response:**
```json
{
  "total_tasks": 12,
  "completed": 3,
  "in_progress": 2,
  "ready": 2,
  "qa": 1,
  "blocked": 0,
  "estimated_hours_remaining": 45
}
```

## 🗄️ Database Schema

### projects
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key (auto-increment) |
| name | TEXT | Project name |
| description | TEXT | Project description |
| reference | TEXT | Reference URL |
| status | TEXT | not-started, in-progress, paused, completed, blocked |
| created_at | TEXT | ISO timestamp |
| target_completion | TEXT | Target completion date (ISO) |

### tasks
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Primary key (e.g., "task-1") |
| project_id | INTEGER | Foreign key to projects |
| title | TEXT | Task title |
| description | TEXT | Task description |
| state | TEXT | todo, in-progress, ready, qa, complete, blocked |
| priority | TEXT | low, medium, high, critical |
| estimated_hours | REAL | Estimated time |
| actual_hours | REAL | Actual time spent |
| assigned_to | TEXT | Agent ID |
| agent_session_key | TEXT | Agent session key |
| started_at | TEXT | When task started (ISO) |
| completed_at | TEXT | When task completed (ISO) |
| spec_file | TEXT | Path to specification file |
| dependencies_json | TEXT | JSON array of task IDs |
| tags_json | TEXT | JSON array of tags |
| code_files_json | TEXT | JSON array of file paths |

### agents
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key (auto-increment) |
| project_id | INTEGER | Foreign key to projects |
| agent_id | TEXT | Agent identifier |
| session_key | TEXT | OpenClaw session key |
| task_id | TEXT | Foreign key to tasks (nullable) |
| spawned_at | TEXT | When agent started (ISO) |
| completed_at | TEXT | When agent finished (ISO) |
| status | TEXT | running, completed, failed |
| result | TEXT | Agent completion message |

### activity_log
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key (auto-increment) |
| project_id | INTEGER | Foreign key to projects |
| timestamp | TEXT | When event occurred (ISO) |
| agent | TEXT | Agent that performed action |
| task_id | TEXT | Related task ID (nullable) |
| message | TEXT | Log message |
| type | TEXT | info, spawn, completion, error, update |

## 🔄 Migration

### Import Existing kanban.json

```bash
# Import from kanban.json (default)
node migrate.js

# Import from custom file
node migrate.js my-project.json

# Import the demo data
node migrate.js kanban-demo.json
```

The migration script will:
1. Create database tables if they don't exist
2. Import project details
3. Import all tasks with full metadata
4. Import active and completed agents
5. Import activity log
6. Display summary statistics

### Migration Output

```
🔄 Starting migration...

🔧 Ensuring database schema exists...
✅ Database schema ready

📂 Loading kanban-demo.json...
📊 Inserting project...
✅ Project created with ID: 1

📋 Inserting 12 tasks...
✅ 12 tasks inserted

🤖 Inserting 3 active agents...
✅ 3 active agents inserted

✅ Inserting 3 completed agents...
✅ 3 completed agents inserted

📝 Inserting 10 activity log entries...
✅ 10 activity log entries inserted

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎉 Migration completed successfully!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Project ID: 1
🌐 View dashboard: http://localhost:3001/dashboard.html
📡 API endpoint: http://localhost:3001/api/projects/1
```

## 🛠️ Using the API in Your Agent

### Example: Agent Orchestrator

```javascript
const fetch = require('node-fetch');

const API_BASE = 'http://localhost:3001/api';

// Create a new project
async function createProject(name, description) {
  const response = await fetch(`${API_BASE}/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name,
      description,
      status: 'in-progress',
      created_at: new Date().toISOString()
    })
  });
  return await response.json();
}

// Add a task
async function addTask(projectId, title, description, priority = 'medium') {
  const taskId = `task-${Date.now()}`;
  const response = await fetch(`${API_BASE}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      id: taskId,
      project_id: projectId,
      title,
      description,
      state: 'todo',
      priority,
      estimated_hours: 4,
      tags: [],
      dependencies: []
    })
  });
  return await response.json();
}

// Assign agent to task
async function assignAgent(projectId, agentId, sessionKey, taskId) {
  const response = await fetch(`${API_BASE}/agents/assign`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_id: projectId,
      agent_id: agentId,
      session_key: sessionKey,
      task_id: taskId
    })
  });
  return await response.json();
}

// Update task state
async function updateTaskState(taskId, state) {
  const response = await fetch(`${API_BASE}/tasks/${taskId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ state })
  });
  return await response.json();
}

// Mark agent complete
async function completeAgent(agentId, sessionKey, result) {
  const response = await fetch(`${API_BASE}/agents/complete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      agent_id: agentId,
      session_key: sessionKey,
      result
    })
  });
  return await response.json();
}
```

### Example: Python Client

```python
import requests
import json

API_BASE = 'http://localhost:3001/api'

def create_project(name, description):
    response = requests.post(f'{API_BASE}/projects', json={
        'name': name,
        'description': description,
        'status': 'in-progress',
        'created_at': datetime.now().isoformat()
    })
    return response.json()

def add_task(project_id, title, description, priority='medium'):
    task_id = f'task-{int(time.time() * 1000)}'
    response = requests.post(f'{API_BASE}/tasks', json={
        'id': task_id,
        'project_id': project_id,
        'title': title,
        'description': description,
        'state': 'todo',
        'priority': priority,
        'estimated_hours': 4,
        'tags': [],
        'dependencies': []
    })
    return response.json()

def update_task_state(task_id, state):
    response = requests.patch(f'{API_BASE}/tasks/{task_id}', json={
        'state': state
    })
    return response.json()
```

## 📁 Project Structure

```
agent-swarm-template/
├── server.js              # Express API server
├── migrate.js             # Migration script
├── package.json           # Node.js dependencies
├── database.db            # SQLite database (created on first run)
├── dashboard.html         # React dashboard UI
├── kanban.json            # Legacy file-based storage (optional)
├── kanban-demo.json       # Demo project data
├── kanban_manager.py      # Python helper (legacy support)
├── README.md              # This file
└── ORCHESTRATOR_EXAMPLE.md # Orchestration guide
```

## 🎯 Dashboard Features

### Project Overview
- **Project name and description** with reference link
- **Status indicator**: color-coded project status
- **Last update timestamp** with manual refresh button
- **Target completion date** (if set)

### Statistics Panel
- **Total tasks** across all states
- **In Progress** - actively being worked on
- **Ready** - specifications complete, ready for dev
- **In QA** - code complete, awaiting testing
- **Completed** - fully done and verified
- **Progress bar** - visual completion percentage
- **Estimated hours remaining** - calculated from incomplete tasks

### Kanban Board
Five-column board with drag-and-drop (visual only):
- **To Do** - awaiting specification or dependencies
- **In Progress** - agent actively working
- **Ready** - spec done, ready for implementation
- **QA** - code complete, needs testing
- **Complete** - fully done ✅

Each task card shows:
- Title and description
- Priority badge (low/medium/high/critical)
- Estimated hours
- Assigned agent
- Tags

### Active Agents Panel
Live monitoring of running agents:
- Agent ID and status
- Assigned task
- Runtime in minutes
- Session key (for debugging)

### Activity Log
Real-time event stream showing:
- Timestamp of each event
- Agent that performed action
- Related task (if applicable)
- Event type icon (spawn 🚀, completion ✅, error ❌, etc.)
- Descriptive message

### Auto-Refresh
Dashboard automatically refreshes every 5 seconds to show latest data.

## 🔧 Configuration

### Change Server Port

Edit `server.js`:
```javascript
const PORT = process.env.PORT || 3001;
```

Or set environment variable:
```bash
PORT=8080 node server.js
```

### Database Location

By default, `database.db` is created in the project directory. To change:

Edit `server.js`:
```javascript
const db = new Database('path/to/database.db');
```

### CORS Settings

To allow access from different origins, edit `server.js`:
```javascript
app.use(cors({
  origin: 'http://yourdomain.com',
  credentials: true
}));
```

## 🐛 Troubleshooting

### Port Already in Use

```
Error: listen EADDRINUSE: address already in use :::3001
```

**Solution:** Kill the process using port 3001 or use a different port:
```bash
PORT=3002 node server.js
```

### Database Locked

```
Error: database is locked
```

**Solution:** Close other connections to the database, or restart the server.

### Migration Fails

```
Error: no such table: projects
```

**Solution:** The migration script now creates tables automatically. If you still see this, delete `database.db` and run migration again:
```bash
rm database.db
node migrate.js kanban-demo.json
```

### Dashboard Shows Error

```
API error: Failed to fetch
```

**Solution:** Ensure server is running:
```bash
node server.js
```

Check that dashboard is using correct port in `dashboard.html`:
```javascript
const apiUrl = 'http://localhost:3001/api/projects/1';
```

### Better-sqlite3 Build Issues

If you get native module errors:

```bash
npm rebuild better-sqlite3
```

Or reinstall:
```bash
rm -rf node_modules
npm install
```

## 📚 Architecture

### Backend Stack
- **Node.js**: JavaScript runtime
- **Express**: Web framework for REST API
- **better-sqlite3**: Fast, synchronous SQLite bindings
- **CORS**: Cross-origin resource sharing

### Frontend Stack
- **React**: UI framework (via CDN)
- **Tailwind CSS**: Utility-first CSS framework
- **Fetch API**: HTTP client for API calls

### Database
- **SQLite**: Embedded, serverless database
- **WAL mode**: Write-Ahead Logging for better concurrency
- **Foreign keys**: Relational integrity
- **JSON columns**: Flexible storage for arrays/objects

### Why This Stack?

✅ **Zero configuration** - No database server to install
✅ **Fast** - SQLite is incredibly fast for read-heavy workloads
✅ **Portable** - Single file database, easy to backup
✅ **Scalable** - Handles thousands of tasks/agents easily
✅ **Simple** - Synchronous API makes code easier to reason about
✅ **Production-ready** - Used by major companies (Apple, Adobe, etc.)

## 🎓 Next Steps

1. **Test with demo data**: Already done! Visit http://localhost:3001/dashboard.html
2. **Integrate with your orchestrator**: Use the API endpoints in your agent logic
3. **Add custom fields**: Extend the database schema as needed
4. **Build additional views**: Create project list, analytics pages, etc.
5. **Add authentication**: Secure the API with JWT or session auth
6. **Deploy to production**: Host on a VPS, use nginx for reverse proxy

## 🦞 Questions?

Ask OpenClaw! This system was built by an agent and can help you extend it.

## 📝 License

MIT - Feel free to use and modify for your projects!

---

**Built with ❤️ by OpenClaw Agent Swarm**

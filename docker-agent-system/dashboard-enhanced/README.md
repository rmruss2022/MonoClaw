# OpenClaw Enhanced Dashboard

Modern dashboard that displays **all OpenClaw sessions** (local + Docker agents) with hierarchical relationships and Docker integration.

## Features

### Session Management
- **Unified View**: Shows all OpenClaw sessions (main + sub-agents)
- **Hierarchical Tree**: Parent-child session relationships
- **Real-time Updates**: Auto-refresh every 10 seconds
- **Dual Views**: Tree view (hierarchical) and Grid view (card-based)

### Docker Integration
- **Container Details**: CPU, memory, network stats
- **Visual Indicators**: Docker badge and color-coding
- **Container Metrics**: Real-time resource monitoring
- **Labels & Metadata**: Profile, model, resource limits

### Display Information

#### For All Sessions:
- Session label/name
- Current model (e.g., `kimi-k2.5`, `claude-sonnet-4-5`)
- Status (active/idle/stopped)
- Parent session (if sub-agent)
- Runtime duration
- Token usage

#### For Docker-Hosted Sessions:
- Container ID (short)
- Container state and status
- CPU usage %
- Memory usage %
- Network info
- Container labels (profile, resources)

## Installation

```bash
cd ~/.openclaw/workspace/docker-agent-system/dashboard-enhanced
npm install
```

## Usage

### Start Dashboard

```bash
npm start
```

Dashboard will be available at: **http://localhost:9092**

### Configuration

Environment variables:

```bash
PORT=9092                          # Dashboard port
GATEWAY_URL=http://localhost:18787 # OpenClaw gateway URL
```

### With PM2

```bash
pm2 start server.js --name openclaw-dashboard
pm2 save
```

## Architecture

```
┌─────────────────────────────────────────────┐
│           Browser (Dashboard UI)            │
│  - Tree/Grid view toggle                    │
│  - Filters (Docker/Local/Status)            │
│  - Auto-refresh                             │
└─────────────────┬───────────────────────────┘
                  │ HTTP/REST
┌─────────────────▼───────────────────────────┐
│         Enhanced Dashboard Server           │
│  - Express API                              │
│  - Session data merger                      │
│  - Tree builder                             │
└──────┬─────────────────────────────┬────────┘
       │                             │
       │ HTTP                        │ Docker API
       │                             │
┌──────▼──────────┐          ┌──────▼──────────┐
│ OpenClaw Gateway│          │  Docker Daemon  │
│  /api/sessions  │          │   Dockerode     │
└─────────────────┘          └─────────────────┘
```

## API Endpoints

### `GET /api/health`
Health check

**Response:**
```json
{
  "status": "healthy",
  "timestamp": 1234567890,
  "gateway": "http://localhost:18787"
}
```

### `GET /api/sessions`
Get all sessions with Docker integration

**Response:**
```json
{
  "sessions": [
    {
      "id": "main",
      "label": "agent:main:main",
      "model": "anthropic/claude-sonnet-4-5",
      "status": "active",
      "parent": null,
      "isDocker": false,
      "docker": null,
      "tokenUsage": { "input": 15000, "output": 3000 }
    },
    {
      "id": "abc123",
      "label": "docker-agent-builder",
      "model": "nvidia/moonshotai/kimi-k2.5",
      "status": "active",
      "parent": "main",
      "isDocker": true,
      "docker": {
        "id": "abc123def456",
        "name": "openclaw-agent-builder",
        "state": "running",
        "cpu": 45.2,
        "memory": 68.5
      }
    }
  ],
  "tree": [ /* hierarchical structure */ ],
  "stats": {
    "total": 2,
    "docker": 1,
    "active": 2
  }
}
```

### `GET /api/docker/containers`
Get Docker containers only

### `GET /api/docker/container/:id`
Get specific container details

## UI Features

### Views

**Tree View** (Default)
- Hierarchical display showing parent-child relationships
- Expandable/collapsible nodes
- Visual indentation for depth
- Border connectors showing relationships

**Grid View**
- Card-based layout
- Responsive grid
- Compact information display

### Filters

- **Show Docker**: Toggle Docker-hosted sessions
- **Show Local**: Toggle local sessions
- **Show Inactive**: Toggle stopped/idle sessions

### Session Details

Click any session to see full details in a modal:
- Complete session information
- Docker container details (if applicable)
- Raw JSON data

### Keyboard Shortcuts

- `Ctrl+R`: Refresh data
- `Esc`: Close modal

## Integration with OpenClaw Docker Agents

### When you create a Docker agent:

```bash
./provisioning/create-agent-openclaw.sh my-agent --profile builder
```

The agent will:
1. Connect to OpenClaw gateway as a new session
2. Appear in dashboard with label `docker-agent-my-agent`
3. Show Docker badge and container metrics
4. Display model, status, and parent session

### Session Hierarchy Example:

```
👤 agent:main:main
  └─ 🤖 subagent-task-runner
      └─ 🐳 docker-agent-builder (Docker)
  └─ 🐳 docker-agent-tester (Docker)
```

## Development

### Running in Development

```bash
npm install
npm run dev  # Uses nodemon for auto-restart
```

### Mock Data

If gateway is unavailable, dashboard falls back to mock data for testing UI.

### Debugging

```bash
# Enable verbose logging
DEBUG=* npm start

# Check API directly
curl http://localhost:9092/api/sessions | jq .
curl http://localhost:9092/api/docker/containers | jq .
```

## Troubleshooting

### Dashboard shows no sessions

**Check gateway connection:**
```bash
curl http://localhost:18787/api/sessions
```

**Check if gateway is running:**
```bash
ps aux | grep openclaw-gateway
```

### Docker containers not showing

**Check Docker daemon:**
```bash
docker ps
```

**Check container labels:**
```bash
docker inspect openclaw-agent-* | grep Labels -A 10
```

### High CPU usage

Dashboard refreshes every 10s by default. Disable auto-refresh if needed.

## Future Enhancements

- [ ] WebSocket for real-time updates
- [ ] Session management (pause/resume/terminate)
- [ ] Historical metrics and graphs
- [ ] Container logs in dashboard
- [ ] Multi-gateway support
- [ ] Export data (CSV/JSON)
- [ ] Search and advanced filtering
- [ ] Dark/light theme toggle

## Related Documentation

- [QUICKSTART.md](../QUICKSTART.md) - Quick start guide
- [README.md](../README.md) - System overview
- [Docker Agent Creation](../provisioning/create-agent-openclaw.sh)

## Support

Report issues or suggestions in the project repository.

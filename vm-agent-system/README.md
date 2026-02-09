# VM Agent System for OpenClaw

A production-ready system for spawning and managing isolated agent instances in VMs using Multipass. Agents run in isolated virtual machines and communicate with a central hub for task delegation and monitoring.

## 🎯 Features

- **Isolated Execution**: Each agent runs in its own VM with dedicated resources
- **Central Hub**: WebSocket + HTTP API for agent communication and management
- **Task Delegation**: Send tasks to agents and receive results
- **Health Monitoring**: Real-time CPU, memory, and disk usage tracking
- **Auto-Reconnection**: Agents automatically reconnect with exponential backoff
- **Message Queuing**: Offline agents receive queued messages on reconnection
- **CLI Management**: Comprehensive CLI for agent lifecycle management
- **Web Dashboard**: Real-time monitoring dashboard
- **Snapshots**: Create and restore VM snapshots for rollback
- **Auto-Start**: Hub server starts automatically on boot

## 📦 Installation

### Prerequisites

1. **Node.js** (v18 or higher)
2. **Multipass** - [Install from here](https://multipass.run/)

### Install Dependencies

```bash
cd ~/.openclaw/workspace/vm-agent-system

# Install hub dependencies
cd hub && npm install

# Install agent runtime dependencies
cd ../agent-runtime && npm install

# Install CLI dependencies
cd ../cli && npm install

# Return to root
cd ..
```

### Setup LaunchAgent (Optional - Auto-start Hub)

```bash
# Copy LaunchAgent plist
cp LaunchAgents/com.openclaw.vm-hub.plist ~/Library/LaunchAgents/

# Load it
launchctl load ~/Library/LaunchAgents/com.openclaw.vm-hub.plist

# Check status
launchctl list | grep vm-hub
```

## 🚀 Quick Start

### 1. Start the Hub Server

```bash
cd hub
npm start
```

Or start both hub and dashboard:

```bash
# Terminal 1: Hub server
npm run hub

# Terminal 2: Dashboard server
npm run dashboard
```

### 2. Create an Agent

```bash
# Using the provisioning script
./provisioning/create-agent.sh \
  --name agent-builder \
  --type builder \
  --cpu 2 \
  --memory 4G \
  --disk 20G \
  --capabilities build,docker,deploy

# Or using the CLI
cd cli
./vm-agent create agent-builder --type builder --cpu 2 --memory 4G
```

### 3. List Agents

```bash
./vm-agent list
```

### 4. Check Agent Status

```bash
./vm-agent status agent-builder

# Or watch continuously
./vm-agent status agent-builder --watch
```

### 5. Send a Task

```bash
./vm-agent task agent-builder '{"type":"exec","command":"echo Hello from VM"}'
```

### 6. View Dashboard

Open in your browser:
```
http://localhost:9092
```

## 📚 CLI Reference

```bash
# Create agent
vm-agent create <name> [options]
  --type <type>          Agent type (builder|tester|researcher)
  --cpu <count>          CPU cores (default: 2)
  --memory <size>        Memory size (default: 4G)
  --disk <size>          Disk size (default: 20G)
  --capabilities <list>  Comma-separated capabilities

# List agents
vm-agent list
  --status <status>      Filter by status (online|offline)
  --type <type>          Filter by type

# Get agent status
vm-agent status <name>
  --watch                Watch status continuously

# Execute command in VM
vm-agent exec <name> <command>
  --sudo                 Run with sudo
  --timeout <ms>         Timeout in milliseconds

# View logs
vm-agent logs <name>
  --follow               Follow log output
  --lines <count>        Number of lines to show

# Create snapshot
vm-agent snapshot <name> [snapshot-name]

# Restore from snapshot
vm-agent restore <name> <snapshot-name>

# Start/stop VM
vm-agent start <name>
vm-agent stop <name>

# Open shell
vm-agent shell <name>

# Destroy agent
vm-agent destroy <name>
  --force                Skip confirmation
```

## 🔌 Hub API Reference

### HTTP API (Port 9091)

#### Register Agent
```http
POST /agents/register
Content-Type: application/json

{
  "agentId": "agent-1",
  "metadata": {
    "type": "builder",
    "capabilities": ["build", "docker"],
    "cpu": 2,
    "memory": "4G"
  }
}

Response:
{
  "agent": { ... },
  "token": "auth-token",
  "wsUrl": "ws://localhost:9090/agent/agent-1/auth-token"
}
```

#### List Agents
```http
GET /agents

Response:
{
  "agents": [...]
}
```

#### Get Agent Status
```http
GET /agents/:id/status

Response:
{
  "agent": { ... }
}
```

#### Send Task to Agent
```http
POST /agents/:id/task
Content-Type: application/json

{
  "type": "exec",
  "command": "ls -la",
  "timeout": 30000
}

Response:
{
  "taskId": "task-uuid",
  "status": "sent"
}
```

#### Deregister Agent
```http
DELETE /agents/:id
```

### WebSocket API (Port 9090)

Connect to: `ws://localhost:9090/agent/:agentId/:token`

#### Message Format
```json
{
  "id": "message-uuid",
  "from": "sender-id",
  "to": "recipient-id",
  "type": "task|response|health|log",
  "timestamp": 1234567890,
  "payload": {}
}
```

## 🔧 Task Types

### Execute Command
```json
{
  "type": "exec",
  "command": "ls -la",
  "cwd": "/path/to/dir",
  "timeout": 30000,
  "sudo": false
}
```

### Run Node.js Script
```json
{
  "type": "script",
  "script": "console.log('Hello')",
  "args": ["arg1", "arg2"],
  "cwd": "/path/to/dir"
}
```

### File Operations
```json
{
  "type": "file:read",
  "filePath": "/path/to/file"
}

{
  "type": "file:write",
  "filePath": "/path/to/file",
  "content": "file content"
}
```

### Git Operations
```json
{
  "type": "git:clone",
  "repo": "https://github.com/user/repo",
  "destination": "/path/to/clone",
  "branch": "main"
}

{
  "type": "git:pull",
  "repoPath": "/path/to/repo"
}

{
  "type": "git:push",
  "repoPath": "/path/to/repo",
  "remote": "origin",
  "branch": "main"
}
```

### Build & Test
```json
{
  "type": "build",
  "command": "npm run build",
  "cwd": "/path/to/project"
}

{
  "type": "test",
  "command": "npm test",
  "cwd": "/path/to/project"
}
```

## 🏗️ Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed architecture documentation.

## 🔐 Security

- Token-based authentication for all WebSocket connections
- VMs run on private network
- No sudo access by default (requires explicit flag)
- Audit logging of all commands
- Isolated VM environments

## 📊 Monitoring

### Prometheus Metrics
Available at `http://localhost:9091/metrics`

- `vm_hub_messages_total` - Total messages routed
- `vm_hub_agents` - Number of agents by status
- `vm_hub_active_tasks` - Number of active tasks

### Health Checks
- Hub: `http://localhost:9091/health`
- Agents send health data every 30 seconds

## 🐛 Troubleshooting

### Hub won't start
```bash
# Check if ports are available
lsof -i :9090
lsof -i :9091

# Check logs
tail -f ~/.openclaw/workspace/vm-agent-system/logs/hub-stdout.log
```

### Agent won't connect
```bash
# Check agent logs
multipass exec <agent-name> -- sudo journalctl -u vm-agent -f

# Check agent service status
multipass exec <agent-name> -- sudo systemctl status vm-agent

# Restart agent service
multipass exec <agent-name> -- sudo systemctl restart vm-agent
```

### VM creation fails
```bash
# Check Multipass status
multipass version
multipass list

# Clean up and retry
multipass delete <agent-name>
multipass purge
```

## 🤝 Contributing

This is part of the OpenClaw project. See main repository for contribution guidelines.

## 📄 License

MIT License - See LICENSE file for details.

## 🔗 Links

- [OpenClaw](https://github.com/your-org/openclaw)
- [Multipass](https://multipass.run/)
- [Architecture Documentation](./ARCHITECTURE.md)

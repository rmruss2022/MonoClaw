# VM Agent System Architecture

## Overview

The VM Agent System provides isolated, delegatable compute environments for OpenClaw. Each agent runs in its own virtual machine and communicates with a central hub for task coordination and monitoring.

## System Components

```
┌─────────────────────────────────────────────────────────────┐
│                         Host System                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Hub Server │    │   Dashboard  │    │   CLI Tool   │  │
│  │              │    │              │    │              │  │
│  │  WS: 9090    │    │  HTTP: 9092  │    │  vm-agent    │  │
│  │  HTTP: 9091  │    │              │    │              │  │
│  └──────┬───────┘    └──────────────┘    └──────────────┘  │
│         │                                                    │
│         │ WebSocket + HTTP                                  │
│         │                                                    │
└─────────┼────────────────────────────────────────────────────┘
          │
          │ Network Bridge (10.0.2.2)
          │
┌─────────┼────────────────────────────────────────────────────┐
│         │              Virtual Machines                      │
├─────────┼────────────────────────────────────────────────────┤
│         │                                                    │
│  ┌──────▼────────┐   ┌──────────────┐   ┌──────────────┐  │
│  │   Agent VM 1  │   │   Agent VM 2 │   │   Agent VM N │  │
│  │               │   │              │   │              │  │
│  │  - Runtime    │   │  - Runtime   │   │  - Runtime   │  │
│  │  - Client     │   │  - Client    │   │  - Client    │  │
│  │  - Executor   │   │  - Executor  │   │  - Executor  │  │
│  │  - Monitor    │   │  - Monitor   │   │  - Monitor   │  │
│  │               │   │              │   │              │  │
│  └───────────────┘   └──────────────┘   └──────────────┘  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Hub Server

**Location:** `hub/server.js`

The central coordination point for all agents. Provides:

- **WebSocket Server (Port 9090)**: Real-time bidirectional communication with agents
- **HTTP API (Port 9091)**: RESTful API for agent management
- **Agent Registry**: Tracks all registered agents and their state
- **Message Router**: Routes messages between host and agents
- **Authentication**: Token-based auth for secure connections
- **Metrics**: Prometheus metrics endpoint

**Key Modules:**

- `auth.js` - Token generation and validation
- `agent-registry.js` - Agent state management
- `router.js` - Message routing and queuing

**Message Flow:**
```
Client → HTTP API → Router → WebSocket → Agent
Agent → WebSocket → Router → Message Handler → Response
```

### 2. Agent Runtime

**Location:** `agent-runtime/`

Code that runs inside each VM. Components:

- **client.js**: WebSocket client that connects to hub
- **task-executor.js**: Executes delegated tasks
- **health-monitor.js**: Monitors and reports system health

**Connection Lifecycle:**
```
1. VM boots
2. systemd starts vm-agent service
3. Client reads /etc/vm-agent/config.json
4. Client connects to hub via WebSocket
5. Authentication with token
6. Registration confirmed
7. Client starts health monitoring
8. Ready to receive tasks
```

**Task Execution Flow:**
```
1. Task message received
2. Validate task type
3. Execute task with timeout
4. Capture stdout/stderr
5. Send response to hub
6. Update task stats
```

### 3. Message Protocol

All messages follow this structure:

```typescript
interface Message {
  id: string;           // Unique message ID (UUID)
  from: string;         // Sender ID (agent-id or "host")
  to: string;          // Recipient ID (agent-id or "host" or "broadcast")
  type: MessageType;    // Message type
  timestamp: number;    // Unix timestamp
  payload: any;        // Type-specific payload
}

type MessageType = 
  | "task"      // Task delegation
  | "response"  // Task response
  | "health"    // Health check data
  | "log"       // Log message
  | "status"    // Status update
  | "error";    // Error message
```

### 4. Task Types

#### Exec Task
Execute shell commands with optional sudo.

```typescript
interface ExecTask {
  type: "exec";
  command: string;
  cwd?: string;
  env?: Record<string, string>;
  timeout?: number;
  sudo?: boolean;
  allowSudo?: boolean;
}
```

#### Script Task
Run Node.js scripts.

```typescript
interface ScriptTask {
  type: "script";
  script: string;
  args?: string[];
  cwd?: string;
  timeout?: number;
}
```

#### File Operations
```typescript
interface FileReadTask {
  type: "file:read";
  filePath: string;
  encoding?: string;
}

interface FileWriteTask {
  type: "file:write";
  filePath: string;
  content: string;
  encoding?: string;
}
```

#### Git Operations
```typescript
interface GitCloneTask {
  type: "git:clone";
  repo: string;
  destination: string;
  branch?: string;
}
```

### 5. Agent Registry

Tracks agent state:

```typescript
interface Agent {
  id: string;
  status: "online" | "offline";
  registeredAt: number;
  lastSeen: number | null;
  lastHealthCheck: number | null;
  
  metadata: {
    type: string;
    capabilities: string[];
    cpu: number;
    memory: string;
    disk: string;
    vmIp?: string;
  };
  
  stats: {
    tasksReceived: number;
    tasksCompleted: number;
    tasksFailed: number;
    messagesReceived: number;
    messagesSent: number;
  };
  
  health: {
    cpu: number | null;
    memory: MemoryStats | null;
    disk: DiskStats | null;
    uptime: number | null;
  };
  
  currentTasks: Task[];
}
```

### 6. Network Architecture

**Host to VM Communication:**
- Multipass creates a bridge network
- Host is accessible at `10.0.2.2` from VMs
- VMs get dynamic IPs in `10.0.2.0/24` range
- WebSocket connections from VM to host

**Security:**
- Token-based authentication for all connections
- Tokens stored in VM at `/etc/vm-agent/config.json`
- No incoming connections to VMs required
- All communication initiated by agents

### 7. VM Provisioning

**Process:**
```
1. Create VM with Multipass
   - Allocate CPU, memory, disk
   - Apply cloud-init config
   
2. Cloud-init setup
   - Update packages
   - Install Node.js
   - Create directories
   - Setup systemd service
   
3. Copy agent runtime
   - Transfer files to VM
   - Install dependencies
   - Set permissions
   
4. Register with hub
   - Call HTTP API
   - Get auth token
   
5. Configure agent
   - Write config.json
   - Start systemd service
   
6. Verification
   - Check connection status
   - Create initial snapshot
```

### 8. Health Monitoring

**Agent Side:**
- Collects CPU, memory, disk stats every 30s
- Sends health message to hub
- Includes active task count

**Hub Side:**
- Updates agent health in registry
- Detects stale agents (no health check in 2 min)
- Marks stale agents as offline
- Exposes metrics for Prometheus

### 9. Reliability Features

**Message Queuing:**
- Messages to offline agents are queued
- Queue persisted in memory (up to 1000 messages)
- Flushed when agent reconnects

**Dead Letter Queue:**
- Failed message deliveries stored
- Can be inspected via API
- Helps debug issues

**Auto-Reconnection:**
- Exponential backoff (1s to 60s)
- Up to 10 reconnection attempts
- Maintains connection state

**Graceful Shutdown:**
- Hub closes all connections cleanly
- Agents receive shutdown notification
- 10-second grace period before force exit

### 10. Monitoring & Observability

**Prometheus Metrics:**
```
vm_hub_messages_total{type, status}     # Message counter
vm_hub_agents{status}                   # Agent count gauge
vm_hub_active_tasks                     # Active task count
```

**Structured Logging:**
- JSON format for machine parsing
- Log levels: info, warn, error
- Includes timestamps and context

**Dashboard:**
- Real-time agent status
- Resource usage visualization
- Active task monitoring
- System logs

### 11. Scalability

**Current Limits:**
- Hub: Single instance (can be clustered)
- Agents: Limited by host resources
- Messages: In-memory (can add Redis)
- Metrics: Prometheus scraping

**Scaling Strategies:**

1. **Vertical**: Increase host resources
2. **Horizontal**: Multiple hub instances with load balancer
3. **Storage**: Add Redis for message queue persistence
4. **Monitoring**: Centralized logging (ELK stack)

### 12. Security Model

**Threat Model:**
- Trusted agents (you control the VMs)
- Untrusted tasks (user-provided code)
- Network isolation (VMs can't talk to each other directly)

**Security Measures:**
- Token authentication
- No sudo by default
- Audit logging
- VM isolation
- Task timeouts
- Resource limits

### 13. Future Enhancements

**Planned:**
- [ ] Agent-to-agent communication
- [ ] Persistent message queue (Redis)
- [ ] Task scheduling and cron
- [ ] Multi-hub clustering
- [ ] Advanced resource limits
- [ ] GPU support
- [ ] Custom VM images
- [ ] Task result storage
- [ ] Webhook notifications
- [ ] Rate limiting

## Design Decisions

### Why Multipass?

- **Cross-platform**: Works on macOS, Linux, Windows
- **Lightweight**: Faster than full VMs
- **Simple**: Easy CLI and API
- **Snapshots**: Built-in rollback support
- **Cloud-init**: Standard provisioning

### Why WebSocket?

- **Real-time**: Bidirectional communication
- **Efficient**: Less overhead than HTTP polling
- **Reliable**: Automatic reconnection
- **Standard**: Well-supported in Node.js

### Why Node.js?

- **Consistency**: Same runtime everywhere
- **Async**: Natural fit for I/O-heavy tasks
- **Ecosystem**: Rich package ecosystem
- **Integration**: Easy OpenClaw integration

### Why In-Memory State?

- **Simplicity**: No external dependencies
- **Performance**: Fast lookups
- **Prototyping**: Easy to iterate
- **Trade-off**: Limited by memory (can add persistence later)

## Deployment

### Development
```bash
# Hub
cd hub && npm start

# Dashboard
node hub/dashboard-server.js
```

### Production
```bash
# LaunchAgent (macOS)
launchctl load ~/Library/LaunchAgents/com.openclaw.vm-hub.plist

# systemd (Linux)
systemctl enable --user vm-hub
systemctl start --user vm-hub
```

### Docker (Future)
```bash
docker-compose up -d
```

## Maintenance

### Backup
- Export agent list: `curl http://localhost:9091/agents > agents.json`
- VM snapshots: `multipass snapshot <name>`
- Hub logs: `~/.openclaw/workspace/vm-agent-system/logs/`

### Updates
- Pull latest code
- Stop hub
- Install dependencies
- Restart hub
- Agents auto-reconnect

### Cleanup
```bash
# Delete all agents
multipass list | grep agent- | awk '{print $1}' | xargs -n1 multipass delete
multipass purge
```

## Performance

**Typical Load:**
- Hub: ~10MB RAM per agent
- Agent: ~50MB RAM + task overhead
- Network: ~1KB/message
- Health checks: 30-second intervals

**Benchmarks:**
- Message latency: <10ms
- Task startup: <100ms
- VM creation: ~60s
- Agent connection: <5s

## Troubleshooting Guide

See README.md for common issues and solutions.

# Docker Agent System Architecture

Detailed architecture documentation for the OpenClaw Docker Agent System.

## Overview

The Docker Agent System is a lightweight, production-ready alternative to the VM-based agent system. It uses Docker containers instead of full VMs to provide isolated compute environments for OpenClaw agents.

## Design Goals

1. **Fast startup**: <5 seconds vs ~60s for VMs
2. **Lightweight**: ~50MB RAM per agent vs ~512MB for VMs
3. **Compatible**: Same hub, dashboard, and API as VM system
4. **Scalable**: Support 20+ agents on laptop, 100+ on server
5. **Production-ready**: Monitoring, logging, health checks built-in

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Host System                              │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Shared Components                      │  │
│  │        (Reused from vm-agent-system)                     │  │
│  │                                                            │  │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐          │  │
│  │  │   Hub    │    │ Dashboard│    │  Metrics │          │  │
│  │  │ WS:9090  │───▶│ HTTP:9092│───▶│Prometheus│          │  │
│  │  │HTTP:9091 │    │          │    │          │          │  │
│  │  └────┬─────┘    └──────────┘    └──────────┘          │  │
│  └───────┼──────────────────────────────────────────────────┘  │
│          │                                                       │
│          │ Docker API                                           │
│          │                                                       │
│  ┌───────▼──────────────────────────────────────────────────┐  │
│  │           Docker Engine                                   │  │
│  │                                                            │  │
│  │  ┌─────────────────────────────────────────────────────┐ │  │
│  │  │         openclaw-agents Network (bridge)            │ │  │
│  │  │                                                       │ │  │
│  │  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐│ │  │
│  │  │  │ Agent 1 │  │ Agent 2 │  │ Agent 3 │  │ Agent N ││ │  │
│  │  │  │builder  │  │ tester  │  │deployer │  │  ...    ││ │  │
│  │  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘│ │  │
│  │  │       │            │            │            │      │ │  │
│  │  │  ┌────▼────┐  ┌────▼────┐  ┌────▼────┐  ┌────▼───┐│ │  │
│  │  │  │ Volume  │  │ Volume  │  │ Volume  │  │ Volume ││ │  │
│  │  │  │   /ws   │  │   /ws   │  │   /ws   │  │   /ws  ││ │  │
│  │  │  └─────────┘  └─────────┘  └─────────┘  └────────┘│ │  │
│  │  └─────────────────────────────────────────────────────┘ │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                Docker Agent CLI                           │  │
│  │  create | list | status | exec | shell | logs            │  │
│  │  start | stop | destroy | task                           │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Shared Components (from VM System)

#### Hub Server
**Location:** `../vm-agent-system/hub/` (symlinked)

Central coordination point:
- **WebSocket Server (9090)**: Real-time agent communication
- **HTTP API (9091)**: RESTful management API
- **Agent Registry**: Tracks agent state and health
- **Message Router**: Routes messages between host and agents

#### Dashboard
**Location:** `../vm-agent-system/dashboard/` (symlinked)

Web-based monitoring UI:
- Real-time agent status
- Resource usage graphs
- Task monitoring
- Log viewer

### 2. Docker-Specific Components

#### Agent Runtime
**Location:** `agent-runtime/`

Node.js application running in each container:

**Files:**
- `client.js`: WebSocket client for hub communication
- `task-executor.js`: Executes delegated tasks
- `health-monitor.js`: Monitors and reports system health
- `Dockerfile`: Container image definition
- `package.json`: Dependencies (ws, uuid)

**Responsibilities:**
- Connect to hub via WebSocket
- Execute tasks (exec, script, file ops, git ops)
- Report health metrics
- Handle reconnection with exponential backoff
- Graceful shutdown

#### CLI Tool
**Location:** `cli/`

Command-line interface for agent management:

**Commands:**
- `create`: Create new agent with profile
- `list`: List all agents
- `status`: Get detailed agent status
- `exec`: Execute command in agent
- `shell`: Open interactive shell
- `logs`: View agent logs
- `start/stop`: Control agent lifecycle
- `destroy`: Remove agent and optionally volumes
- `task`: Send JSON task to agent

**Implementation:**
- Built with Commander.js
- Uses Docker CLI under the hood
- Colorized output with chalk
- Progress indicators with ora
- Tables with cli-table3

#### Provisioning Scripts
**Location:** `provisioning/`

Shell scripts for container creation:

**create-agent.sh:**
- Registers agent with hub (gets token)
- Creates Docker volume for persistence
- Builds profile-specific image if needed
- Creates and starts container
- Applies profile configuration

**Features:**
- Profile-based image layering
- Automatic network creation
- Volume management
- Token-based authentication

#### Profiles
**Location:** `profiles/`

Pre-configured agent templates:

**Available:**
- `builder.json`: Node.js builds, deployments
- `tester.json`: Test runners, browsers
- `deployer.json`: Cloud deployments
- `researcher.json`: Python, data science
- `docker-host.json`: Docker-in-Docker

**Format:**
```json
{
  "name": "string",
  "description": "string",
  "resources": { "cpus": "string", "memory": "string", "disk": "string" },
  "environment": { "KEY": "value" },
  "files": [{ "path": "string", "content": "string" }],
  "packages": ["string"],
  "setup_tasks": [{ "type": "exec", "command": "string", "description": "string" }]
}
```

## Networking

### Docker Bridge Network

**Name:** `openclaw-agents`

**Configuration:**
- Driver: bridge
- Subnet: Auto-assigned by Docker
- Gateway: Auto-assigned
- DNS: Docker embedded DNS

**Access:**
- Agents → Hub: `host.docker.internal:9090`
- Agents → Internet: Via NAT (default)
- Agent → Agent: Isolated (no direct communication)

**Host Access:**

On macOS/Windows (Docker Desktop):
```
host.docker.internal → Host machine
```

On Linux:
```
--add-host host.docker.internal:host-gateway
```

### Container Networking

Each agent container:
- Gets unique IP in bridge network
- Can reach host via `host.docker.internal`
- Cannot reach other agents directly (isolation)
- Full internet access by default

## Storage

### Volume Strategy

**Named volumes per agent:**
```
openclaw-agent-<name> → /workspace
```

**Why volumes?**
- Persist data across container restarts
- Faster than bind mounts
- Managed by Docker (backup, migration)
- OS-independent paths

**Alternative: Bind mounts** (for development)
```bash
docker run -v $(pwd)/workspace:/workspace ...
```

### Data Layout

Inside agent container:
```
/app/               # Agent runtime (read-only)
  client.js
  task-executor.js
  health-monitor.js
  node_modules/

/workspace/         # Persistent volume (read-write)
  # User data here

/etc/agent/         # Configuration
  config.json       # Agent ID and token

/tmp/               # Ephemeral temp storage
```

## Resource Management

### CPU Limits

Specified in profile or CLI:
```json
"cpus": "2"      // 2 cores
"cpus": "0.5"    // 50% of 1 core
```

Enforced by Docker using CPU shares and quotas.

### Memory Limits

Specified in profile or CLI:
```json
"memory": "4g"   // 4GB hard limit
```

Enforced by Docker using cgroups. Container killed if exceeded.

### Disk Limits

Specified in profile (not strictly enforced):
```json
"disk": "30g"
```

Actual limit depends on:
- Docker storage driver
- Host filesystem
- Volume configuration

## Security Model

### Container Isolation

**Namespaces:**
- PID: Isolated process tree
- NET: Isolated network stack
- MNT: Isolated filesystem mounts
- UTS: Isolated hostname
- IPC: Isolated inter-process communication

**Cgroups:**
- CPU limits
- Memory limits
- Device access control

**Filesystem:**
- Overlay FS: Copy-on-write layers
- Volume mounts: Controlled access
- Read-only root: Optional (not default)

### User Isolation

Agents run as non-root user:
- User: `agent`
- UID: 1000
- GID: 1000
- Home: `/home/agent`
- Workspace: `/workspace` (owned by agent)

Root access via `docker exec -u root` if needed (avoid in production).

### Authentication

**Hub authentication:**
- Token-based
- Token obtained during agent registration
- Stored in container environment
- Sent with WebSocket connection

**No additional auth required** (trusted environment assumption).

### Trust Model

**Assumptions:**
- Host system is secure
- Hub is trusted
- Agents are trusted (you control them)
- Tasks may be untrusted (user-provided code)

**Mitigations:**
- Resource limits prevent DoS
- Process isolation prevents escape
- Volume isolation prevents data leakage
- Audit logging for accountability

## Message Protocol

### WebSocket Communication

**Connection:**
```
ws://host.docker.internal:9090/agent/<id>/<token>
```

**Message Format:**
```typescript
{
  id: string;         // UUID
  from: string;       // Sender ID
  to: string;        // Recipient ID or "host"
  type: string;      // Message type
  timestamp: number; // Unix timestamp
  payload: any;      // Type-specific data
}
```

**Message Types:**
- `task`: Execute task
- `response`: Task result
- `health`: Health check data
- `log`: Log message
- `status`: Status update
- `metadata`: Agent metadata
- `ping/pong`: Keep-alive

### Task Execution Flow

```
1. Hub → Agent: task message
   {
     type: "task",
     payload: {
       taskId: "uuid",
       type: "exec",
       command: "npm test"
     }
   }

2. Agent executes task via TaskExecutor

3. Agent → Hub: response message
   {
     type: "response",
     payload: {
       taskId: "uuid",
       success: true,
       result: { stdout: "...", stderr: "", exitCode: 0 }
     }
   }
```

### Health Monitoring

**Frequency:** Every 30 seconds

**Data collected:**
- CPU usage (%)
- Memory usage (MB, %)
- Disk usage (MB, %)
- Uptime (seconds)
- Load average
- Active tasks

**Health message:**
```typescript
{
  type: "health",
  payload: {
    cpu: 15.3,
    memory: { total: 8192, used: 1024, free: 7168, usagePercent: 12.5 },
    disk: { total: 30720, used: 5120, free: 25600, usagePercent: 16.7 },
    uptime: 3600,
    systemUptime: 86400,
    loadAverage: [0.5, 0.6, 0.7],
    timestamp: 1234567890
  }
}
```

## Lifecycle Management

### Agent Creation

```
1. CLI: docker-agent create myagent --profile builder
2. Provisioning: Register with hub → get token
3. Provisioning: Create Docker volume
4. Provisioning: Build profile image (if needed)
5. Provisioning: Create container with token
6. Provisioning: Start container
7. Agent runtime: Connect to hub
8. Hub: Register agent as online
9. Dashboard: Show agent
```

### Agent Lifecycle States

```
Created → Starting → Running → Stopping → Stopped
                      ↓
                    Failed
```

**Created:** Container exists but not started
**Starting:** Container starting, not yet connected to hub
**Running:** Container running, connected to hub
**Stopping:** Graceful shutdown in progress
**Stopped:** Container stopped
**Failed:** Container exited with error

### Reconnection Behavior

Agent disconnects:
- Attempt 1: Reconnect after 1 second
- Attempt 2: Reconnect after 2 seconds
- Attempt 3: Reconnect after 4 seconds
- ...
- Attempt 10: Give up, exit (container restarts if policy allows)

### Graceful Shutdown

```
1. Receive SIGTERM
2. Stop health monitoring
3. Close WebSocket connection
4. Wait up to 10 seconds for in-flight tasks
5. Exit with code 0
```

## Performance Characteristics

### Startup Time

- Container creation: ~1 second
- Container start: ~2 seconds
- Agent connection: ~1 second
- **Total: <5 seconds** (vs ~60s for VMs)

### Resource Usage

**Per agent (idle):**
- CPU: <1%
- Memory: ~50MB (Node.js runtime + agent code)
- Disk: ~500MB (base image + profile additions)

**Per agent (active):**
- CPU: Depends on task
- Memory: Depends on task (+ 50MB base)
- Disk: Depends on task data

**Host overhead:**
- Docker daemon: ~100MB RAM
- Network: Minimal (<1MB)
- No hypervisor overhead (vs VMs)

### Scalability

**Laptop (8GB RAM, 4 cores):**
- 20+ idle agents
- 5-10 active agents

**Server (32GB RAM, 16 cores):**
- 100+ idle agents
- 30-50 active agents

**Limits:**
- Docker daemon file descriptors
- Host network connections
- Host disk I/O
- Hub WebSocket connections

## Monitoring and Observability

### Health Checks

**Docker health check:**
```dockerfile
HEALTHCHECK --interval=30s --timeout=3s \
  CMD node -e "console.log('healthy')" || exit 1
```

**Agent health monitoring:**
- Reports to hub every 30s
- Hub marks stale agents offline after 2 min

### Logging

**Agent logs:**
```bash
docker logs openclaw-agent-<name>
```

**Log format:**
```
[DOCKER-AGENT] timestamp message
```

**Log drivers:**
- json-file (default)
- syslog
- journald
- fluentd
- splunk

### Metrics

**Via Hub:**
- Agent count by status
- Task count by type
- Message count
- Health metrics per agent

**Via Docker:**
```bash
docker stats openclaw-agent-<name>
```

**Via cAdvisor/Prometheus:**
- CPU usage time series
- Memory usage time series
- Network I/O
- Disk I/O

## Comparison with VM System

| Aspect | Docker | VM (Multipass) |
|--------|--------|----------------|
| **Startup time** | <5s | ~60s |
| **Memory per agent** | ~50MB | ~512MB |
| **Disk per agent** | ~500MB | ~2GB+ |
| **Isolation level** | Container | Full VM |
| **Kernel** | Shared | Isolated |
| **Performance** | Native | Virtualized |
| **Portability** | Very high | Medium |
| **Snapshot speed** | <1s | ~10s |
| **Max agents (laptop)** | 20+ | 5-10 |
| **Security** | Good | Excellent |
| **Best for** | Trusted code, scale | Untrusted code, isolation |

## Trade-offs

### Advantages

✓ Fast startup and restart
✓ Low resource overhead
✓ High density (many agents per host)
✓ Fast snapshots (layer commits)
✓ Portable images
✓ Rich tooling ecosystem
✓ Easy orchestration (Compose, Swarm, K8s)

### Disadvantages

✗ Less isolation than VMs
✗ Shared kernel
✗ No kernel-level separation
✗ Limited Windows container support (macOS/Linux host needed)
✗ Requires Docker daemon (another dependency)

### When to Use Docker

- Fast iteration required
- Running many agents
- Limited host resources
- Trusted workloads
- Need portability
- Orchestration desired

### When to Use VMs

- Maximum isolation required
- Untrusted workloads
- Kernel modifications needed
- Full OS simulation required
- No shared kernel allowed
- Security > performance

## Future Enhancements

### Short-term
- [ ] Docker Compose templates
- [ ] Custom Dockerfile per profile
- [ ] Health check improvements
- [ ] Resource usage alerts
- [ ] Automated backups

### Medium-term
- [ ] Kubernetes operator
- [ ] GPU support
- [ ] Multi-host orchestration
- [ ] Advanced networking (overlay)
- [ ] Secret management
- [ ] Registry integration

### Long-term
- [ ] Agent-to-agent communication
- [ ] Task queuing and scheduling
- [ ] Auto-scaling
- [ ] Multi-region support
- [ ] Hybrid VM+Docker deployments

## References

- [Docker Documentation](https://docs.docker.com/)
- [Container Networking](https://docs.docker.com/network/)
- [Docker Security](https://docs.docker.com/engine/security/)
- [VM Agent System](../../vm-agent-system/ARCHITECTURE.md)

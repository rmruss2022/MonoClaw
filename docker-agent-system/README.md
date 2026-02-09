# Docker Agent System

Production-ready Docker-based agent system for OpenClaw - a fast, lightweight alternative to the VM-based system.

## Overview

The Docker Agent System provides isolated, delegatable compute environments using Docker containers instead of VMs. Each agent runs in its own container and communicates with the central hub for task coordination and monitoring.

## Key Benefits

- **⚡ Fast Startup**: Containers boot in seconds vs minutes for VMs
- **💨 Lightweight**: ~50MB RAM per agent vs ~512MB+ for VMs  
- **🔄 Instant Snapshots**: Container commits in milliseconds
- **🎯 Same Architecture**: Hub-and-spoke model, reuses existing hub
- **🔌 Drop-in Replacement**: Compatible CLI and API
- **🚀 Production Ready**: Built for scale and reliability

## Quick Start

### Prerequisites

- Docker installed and running
- Node.js 18+ (for CLI)
- Hub running on localhost:9090 (from vm-agent-system)

### Installation

```bash
cd ~/.openclaw/workspace/docker-agent-system
npm install
npm link

# Make CLI available globally
chmod +x cli/docker-agent
```

### Create Your First Agent

```bash
# Create agent with builder profile
docker-agent create my-builder --profile builder

# Check status
docker-agent list
docker-agent status my-builder

# Send a task
docker-agent exec my-builder "npm --version"

# View logs
docker-agent logs my-builder

# Interactive shell
docker-agent shell my-builder

# Clean up
docker-agent destroy my-builder
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Host System                          │
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Hub (VM)   │    │  Dashboard   │    │     CLI      │  │
│  │  WS: 9090    │    │ HTTP: 9092   │    │ docker-agent │  │
│  │  HTTP: 9091  │    │              │    │              │  │
│  └──────┬───────┘    └──────────────┘    └──────────────┘  │
│         │                                                    │
│         │ Docker Bridge Network                             │
│         │                                                    │
│  ┌──────▼────────────────────────────────────────────────┐ │
│  │           Docker Container Network                     │ │
│  │                                                        │ │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐         │ │
│  │  │ Agent 1  │   │ Agent 2  │   │ Agent N  │         │ │
│  │  │ Runtime  │   │ Runtime  │   │ Runtime  │         │ │
│  │  └──────────┘   └──────────┘   └──────────┘         │ │
│  │                                                        │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Agent Runtime
Node.js application that runs inside each container:
- WebSocket client connecting to hub
- Task executor with timeout and error handling  
- Health monitor reporting system stats
- Automatic reconnection with exponential backoff

### 2. CLI
Command-line tool for managing agents:
- Create, list, start, stop, destroy agents
- Execute commands and tasks
- View logs and status
- Interactive shell access

### 3. Profiles
Pre-configured templates for different use cases:
- **builder**: Node.js, yarn, pnpm, build tools
- **tester**: Testing frameworks, browsers
- **deployer**: Deployment tools, cloud CLIs
- **researcher**: Python, data science tools
- **docker-host**: Docker-in-Docker for nested containers

### 4. Provisioning
Scripts for container creation and configuration:
- Build optimized Docker images
- Apply profiles via Dockerfile layers
- Configure networking and volumes
- Register with hub

## CLI Reference

### Agent Lifecycle

```bash
# Create agent
docker-agent create <name> [--profile <profile>]

# List agents
docker-agent list

# Get status
docker-agent status <name>

# Start/stop
docker-agent start <name>
docker-agent stop <name>

# Destroy agent
docker-agent destroy <name>
```

### Task Execution

```bash
# Execute command
docker-agent exec <name> <command>

# Send JSON task
docker-agent task <name> '{"type":"exec","command":"pwd"}'

# Interactive shell
docker-agent shell <name>
```

### Monitoring

```bash
# View logs
docker-agent logs <name> [--follow] [--tail N]

# Get detailed status
docker-agent status <name>
```

## Profiles

Profiles define the agent environment. Each profile includes:

- **packages**: System packages to install
- **environment**: Environment variables
- **files**: Files to create in the container
- **setup_tasks**: Commands to run during setup

Example profile:

```json
{
  "name": "builder",
  "description": "Build agent for Node.js projects",
  "resources": {
    "cpus": "2",
    "memory": "4g"
  },
  "environment": {
    "NODE_ENV": "production",
    "CI": "true"
  },
  "packages": ["git", "curl", "build-essential"],
  "setup_tasks": [
    {
      "type": "exec",
      "command": "npm install -g yarn pnpm",
      "description": "Install package managers"
    }
  ]
}
```

## Hub Integration

The Docker system reuses the existing hub from vm-agent-system:

- **WebSocket**: `ws://host.docker.internal:9090`
- **HTTP API**: `http://host.docker.internal:9091`
- **Dashboard**: `http://localhost:9092`

Agents connect using the same protocol and authentication as VM agents.

## Docker Network

Agents run on a custom bridge network:

```bash
docker network create openclaw-agents
```

Configuration:
- Network: `openclaw-agents`
- Hub accessible via `host.docker.internal`
- Container-to-container isolation (default)

## Volumes

Each agent has a persistent volume for data:

```bash
# Volume naming: openclaw-agent-<name>
docker volume create openclaw-agent-mybuilder
```

Mounted at `/workspace` in the container.

## Performance

Typical resource usage:

- **Container**: ~50MB RAM base + task overhead
- **Startup**: <5 seconds (vs ~60s for VMs)
- **Disk**: ~500MB per container (vs ~2GB+ for VMs)
- **CPU**: Minimal when idle

Scaling:
- 20+ agents on laptop (8GB RAM)
- 100+ agents on server (32GB RAM)

## Comparison: Docker vs VM

| Feature | Docker | VM (Multipass) |
|---------|--------|----------------|
| Startup time | <5s | ~60s |
| Memory per agent | ~50MB | ~512MB |
| Disk per agent | ~500MB | ~2GB |
| Snapshot speed | <1s | ~10s |
| Max agents (laptop) | 20+ | 5-10 |
| Isolation | Container | Full VM |
| Networking | Bridge | NAT |

## Security

Docker agents are more lightweight but less isolated than VMs:

- **Process isolation**: Yes (namespaces, cgroups)
- **Filesystem isolation**: Yes (overlay FS)
- **Network isolation**: Yes (bridge network)
- **Kernel isolation**: No (shared kernel)

For sensitive workloads, use VM agents or add security layers:
- AppArmor/SELinux profiles
- Seccomp filters
- Read-only root filesystem
- Non-root user

## Troubleshooting

### Agent won't connect to hub

```bash
# Check hub is running
curl http://localhost:9091/health

# Check container can reach host
docker-agent exec <name> "ping -c 3 host.docker.internal"

# Check logs
docker-agent logs <name>
```

### Container exits immediately

```bash
# Check Docker logs
docker logs openclaw-agent-<name>

# Inspect container
docker inspect openclaw-agent-<name>

# Try running with shell
docker run -it openclaw-agent-base /bin/bash
```

### Profile installation fails

```bash
# Check provisioning logs
cat ~/.openclaw/workspace/docker-agent-system/logs/provision-<name>.log

# Manually apply profile
cd provisioning
./apply-profile.sh <name> ../profiles/<profile>.json
```

## Development

### Building base image

```bash
cd agent-runtime
docker build -t openclaw-agent-base .
```

### Testing changes

```bash
# Rebuild and test
docker-agent destroy test-agent
docker-agent create test-agent --profile builder

# Check it works
docker-agent exec test-agent "node --version"
```

### Adding new profiles

1. Create profile JSON in `profiles/`
2. Follow existing profile structure
3. Test with new agent
4. Document capabilities

## Production Deployment

### Docker Compose

```yaml
version: '3.8'
services:
  agent-builder-1:
    image: openclaw-agent-base
    environment:
      - AGENT_ID=builder-1
      - AGENT_TOKEN=${BUILDER_TOKEN}
    networks:
      - openclaw
networks:
  openclaw:
    driver: bridge
```

### Kubernetes

See `docs/kubernetes.md` for deployment examples.

### Monitoring

The existing dashboard shows Docker agents automatically:
- Real-time status
- Resource usage
- Task metrics
- Health checks

## Roadmap

- [ ] GPU support for ML workloads
- [ ] Multi-host agent orchestration
- [ ] Kubernetes operator
- [ ] Advanced resource limits
- [ ] Custom base images per profile
- [ ] Agent-to-agent networking
- [ ] Persistent task queue

## Links

- [Architecture Details](docs/ARCHITECTURE.md)
- [Docker-Specific Guide](docs/DOCKER.md)
- [Profile Migration Guide](docs/PROFILE_MIGRATION.md)
- [VM Agent System](../vm-agent-system/)

## License

MIT

# Quick Start Guide - OpenClaw Native

Get up and running with OpenClaw-native Docker agents in 5 minutes.

## What's New in v2.0

**OpenClaw Native Runtime:**
- Agents use `openclaw` npm package directly (no custom WebSocket client)
- Connect to OpenClaw gateway instead of custom hub
- Sessions appear in unified dashboard alongside other OpenClaw sessions
- Full integration with OpenClaw session management

**Enhanced Dashboard:**
- Shows **ALL** OpenClaw sessions (local + Docker agents)
- Hierarchical tree view showing parent-child relationships
- Real-time Docker metrics (CPU, memory, network)
- Model, status, token usage for each session

## Prerequisites

- Docker installed and running
- OpenClaw gateway running (`openclaw-gateway` process)
- Node.js 18+ and npm
- API keys configured in `~/.openclaw/api-keys.yml`

## Installation

### 1. Build the OpenClaw Agent Image

```bash
cd ~/.openclaw/workspace/docker-agent-system
docker build -t openclaw-agent-openclaw -f agent-runtime/Dockerfile.openclaw agent-runtime/
```

### 2. Start the Enhanced Dashboard

```bash
cd dashboard-enhanced
npm install
npm start
```

Dashboard will be available at: **http://localhost:9092**

## Create Your First Agent

### Using the New Script

```bash
cd ~/.openclaw/workspace/docker-agent-system
./provisioning/create-agent-openclaw.sh my-builder \
  --profile builder \
  --model "nvidia/moonshotai/kimi-k2.5" \
  --cpus 2 \
  --memory 4g
```

This creates an agent that:
- Runs OpenClaw natively in Docker
- Connects to gateway at `http://host.docker.internal:18787`
- Uses kimi-k2.5 model by default
- Appears in dashboard as `docker-agent-my-builder`

### Verify in Dashboard

Open http://localhost:9092 and you should see:

```
👤 agent:main:main (Claude Sonnet 4-5)
  └─ 🐳 docker-agent-my-builder (Kimi K2.5) [Docker]
      CPU: 12.5% | Memory: 45.3% | Status: Active
```

### Check Container Logs

```bash
docker logs -f openclaw-agent-my-builder
```

You should see:
```
==========================================
OpenClaw Docker Agent
==========================================
Agent Name: my-builder
Gateway URL: http://host.docker.internal:18787
Default Model: nvidia/moonshotai/kimi-k2.5
==========================================

Starting OpenClaw session...
Session label: docker-agent-my-builder

[OpenClaw] Connected to gateway
[OpenClaw] Session ready: docker-agent-my-builder
```

## Interacting with Agents

### Via OpenClaw Main Session

Since Docker agents are now full OpenClaw sessions, you can interact with them like any sub-agent:

```bash
# In your main OpenClaw session (Telegram, webchat, etc.)
"Spawn a task on docker-agent-my-builder to check Node.js version"
```

### Via Docker Exec (Direct)

```bash
docker exec openclaw-agent-my-builder node --version
```

### Via Dashboard

Click on the agent in the dashboard to see:
- Full session details
- Docker container metrics
- Model and configuration
- Parent-child relationships

## Dashboard Features

### Tree View (Default)

Shows hierarchical session relationships:

```
👤 Main Session
  ├─ 🤖 Sub-agent: task-runner
  │   └─ 🐳 docker-agent-worker-1 (Docker)
  └─ 🐳 docker-agent-builder (Docker)
```

### Grid View

Card-based layout with all sessions side-by-side.

### Filters

- **Show Docker**: Toggle Docker-hosted sessions
- **Show Local**: Toggle local sessions
- **Show Inactive**: Toggle stopped/idle sessions

### Real-time Metrics

For Docker agents, see:
- CPU usage %
- Memory usage %
- Network I/O
- Container state

## Example Workflows

### 1. Multi-Agent Build Pipeline

```bash
# Create specialized agents
./provisioning/create-agent-openclaw.sh builder --profile builder
./provisioning/create-agent-openclaw.sh tester --profile tester
./provisioning/create-agent-openclaw.sh deployer --profile deployer

# View in dashboard - all three appear as Docker agents
# Assign tasks via main OpenClaw session
```

### 2. Isolated Research Environment

```bash
# Create Python research agent
./provisioning/create-agent-openclaw.sh research \
  --profile researcher \
  --model "nvidia/moonshotai/kimi-k2.5" \
  --memory 8g

# Agent has Jupyter, Python, data science tools
# Appears in dashboard with kimi model
```

### 3. Docker-in-Docker Builder

```bash
# Create Docker host agent
./provisioning/create-agent-openclaw.sh docker-host \
  --profile docker-host \
  --cpus 4 \
  --memory 8g

# Can build Docker images inside container
# Full Docker API access
```

## Models

### Supported Models

Any model configured in OpenClaw gateway can be used:

```bash
# Use GPT-4
./provisioning/create-agent-openclaw.sh agent1 --model "openai/gpt-4"

# Use Claude
./provisioning/create-agent-openclaw.sh agent2 --model "anthropic/claude-3-opus"

# Use Kimi (default)
./provisioning/create-agent-openclaw.sh agent3 --model "nvidia/moonshotai/kimi-k2.5"
```

Each agent's model is displayed in the dashboard.

## Profiles

Profiles define pre-installed tools and environment:

- **builder**: Node.js, npm, yarn, pnpm, git, build tools
- **tester**: Test runners, browsers, linters
- **deployer**: Deployment tools, SSH, cloud CLIs
- **researcher**: Python, Jupyter, pandas, numpy, scipy
- **docker-host**: Docker-in-Docker for building containers

See `profiles/README.md` for details.

## Resource Management

### Set CPU and Memory

```bash
./provisioning/create-agent-openclaw.sh my-agent \
  --cpus 4 \
  --memory 8g
```

Dashboard shows resource usage in real-time.

### Monitor Resources

```bash
# Via Docker
docker stats openclaw-agent-my-agent

# Via Dashboard
# Real-time CPU/memory bars for each Docker agent
```

## Session Hierarchy

### Understanding the Tree

**Main Session** (You)
- Root of the tree
- Direct chat with OpenClaw

**Sub-agents** (Local)
- Spawned by main session
- Run on host machine
- Show as children of main session

**Docker Agents** (Containers)
- Also show as children of main session
- Marked with 🐳 Docker badge
- Show container metrics

### Example Hierarchy

```
👤 agent:main:main
  ├─ 🤖 subagent:task-executor
  ├─ 🤖 subagent:researcher
  └─ 🐳 docker-agent-builder
      └─ 🤖 subagent:build-helper (spawned by Docker agent)
```

## Troubleshooting

### Agent won't start

```bash
# Check Docker
docker ps -a | grep openclaw-agent

# Check logs
docker logs openclaw-agent-<name>

# Check gateway connection
docker exec openclaw-agent-<name> ping -c 3 host.docker.internal
```

### Agent not in dashboard

**Check gateway:**
```bash
curl http://localhost:18787/api/sessions | jq .
```

**Check dashboard logs:**
```bash
# In dashboard-enhanced directory
npm start
# Watch for errors
```

**Check container is running:**
```bash
docker ps | grep openclaw-agent
```

### API keys not working

API keys must be accessible to Docker containers.

**Option 1: Volume mount** (default in script)
```bash
# Script automatically mounts:
# ~/.openclaw/api-keys.yml -> /etc/openclaw/api-keys.yml
```

**Option 2: Environment variables**
```bash
docker run \
  -e OPENAI_API_KEY="..." \
  -e ANTHROPIC_API_KEY="..." \
  openclaw-agent-openclaw
```

### Gateway not reachable from container

```bash
# Test connectivity
docker exec openclaw-agent-<name> curl http://host.docker.internal:18787/health

# If fails, check gateway is running
ps aux | grep openclaw-gateway

# Check port
lsof -i :18787
```

## Comparing v1.0 vs v2.0

### v1.0 (Custom Hub)
```
Docker Agent → Custom WebSocket → Hub Server
                                   ↓
                            Dashboard (shows agents only)
```

- Custom client code
- Separate hub infrastructure
- Dashboard shows only Docker agents
- Manual message routing

### v2.0 (OpenClaw Native)
```
Docker Agent → OpenClaw Gateway ← Main Session
                     ↓
        Enhanced Dashboard (shows all sessions)
```

- Native OpenClaw integration
- Unified session management
- Dashboard shows everything
- Automatic hierarchy
- Standard OpenClaw features

## Next Steps

- **Read** [Dashboard README](dashboard-enhanced/README.md) for dashboard features
- **Explore** Profiles in `profiles/` directory
- **Create** Custom profiles for your workflows
- **Monitor** Sessions in dashboard
- **Scale** Add more agents as needed

## Advanced Usage

### API Keys via Volume Mount

```bash
# Create dedicated API keys for Docker agents
cat > /path/to/docker-api-keys.yml <<EOF
apiKeys:
  openai: sk-...
  anthropic: sk-...
  moonshot: sk-...
EOF

# Mount in container creation
docker run \
  -v /path/to/docker-api-keys.yml:/etc/openclaw/api-keys.yml:ro \
  openclaw-agent-openclaw
```

### Custom Gateway URL

```bash
# If gateway runs on different host/port
export GATEWAY_URL="http://192.168.1.100:18787"
./provisioning/create-agent-openclaw.sh my-agent
```

### Different Thinking Levels

```bash
# Low thinking (fast, cheaper)
./provisioning/create-agent-openclaw.sh fast-agent --thinking low

# High thinking (slower, more thorough)
./provisioning/create-agent-openclaw.sh smart-agent --thinking high
```

### Networking

All agents join the `openclaw-agents` network by default:

```bash
# Agents can communicate with each other
docker exec agent1 ping agent2

# Inspect network
docker network inspect openclaw-agents
```

## Tips & Best Practices

1. **Name clearly**: Use descriptive agent names like `builder-frontend`, `tester-api`
2. **Use profiles**: Don't start from scratch, customize existing profiles
3. **Monitor resources**: Check dashboard for resource usage
4. **Set appropriate limits**: Don't over-allocate CPU/memory
5. **Use /workspace**: Mount volumes to persist data
6. **Check logs regularly**: `docker logs -f <container>`
7. **Clean up**: Stop/remove unused agents
8. **Test locally first**: Before production deployment
9. **Use labels**: Leverage Docker labels for metadata
10. **Dashboard filters**: Use filters to focus on specific agents

## Getting Help

- Check logs: `docker logs openclaw-agent-<name>`
- Inspect container: `docker inspect openclaw-agent-<name>`
- Test image: `docker run -it openclaw-agent-openclaw /bin/bash`
- Dashboard API: `curl http://localhost:9092/api/sessions | jq .`
- Gateway health: `curl http://localhost:18787/health`

Happy building! 🚀

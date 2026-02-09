# Quick Start Guide

Get up and running with Docker agents in 5 minutes.

## Prerequisites

- Docker installed and running
- Node.js 18+ and npm
- Hub running (from vm-agent-system)

## Installation

### 1. Run Setup

```bash
cd ~/.openclaw/workspace/docker-agent-system
./setup.sh
```

This will:
- Install dependencies
- Build the base Docker image
- Create Docker network
- Link the CLI globally

### 2. Verify Installation

```bash
docker-agent --version
docker image ls | grep openclaw-agent-base
docker network ls | grep openclaw-agents
```

## Create Your First Agent

### Builder Agent

For building Node.js applications:

```bash
docker-agent create my-builder --profile builder
```

This creates an agent with:
- Node.js 18+ with npm, yarn, pnpm
- Build tools (git, make, g++)
- Vercel CLI for deployments
- 4 CPU cores, 8GB RAM

### Check Status

```bash
docker-agent status my-builder
```

You should see:
- Status: Running
- Profile: builder
- Network and volume info

## Run Your First Command

```bash
# Check Node.js version
docker-agent exec my-builder "node --version"

# Install dependencies
docker-agent exec my-builder "cd /workspace && npm install"

# Run build
docker-agent exec my-builder "cd /workspace && npm run build"
```

## Interactive Shell

For more complex tasks:

```bash
docker-agent shell my-builder
```

You're now in a bash shell inside the agent. Try:

```bash
pwd                    # You're in /app
cd /workspace          # Your persistent workspace
ls -la                 # Check what's here
node --version         # Verify Node.js
npm install -g vercel  # Already installed!
exit                   # Return to host
```

## View Logs

```bash
# Tail logs
docker-agent logs my-builder --follow

# Last 50 lines
docker-agent logs my-builder --tail 50
```

## Multiple Agents

Create different agents for different tasks:

```bash
# Builder for Node.js apps
docker-agent create builder-1 --profile builder

# Tester for running tests
docker-agent create tester-1 --profile tester

# Deployer for deployments
docker-agent create deployer-1 --profile deployer

# List all
docker-agent list
```

## Example Workflow

### Build and Test a Node.js App

```bash
# Create agents
docker-agent create build-agent --profile builder
docker-agent create test-agent --profile tester

# Clone repo (in builder)
docker-agent exec build-agent "
  cd /workspace && \
  git clone https://github.com/user/my-app.git && \
  cd my-app && \
  npm install && \
  npm run build
"

# Run tests (in tester)
docker-agent exec test-agent "
  cd /workspace/my-app && \
  npm test
"

# Deploy (if tests pass)
docker-agent exec build-agent "
  cd /workspace/my-app && \
  vercel --prod
"
```

## Send Structured Tasks

For complex tasks, send JSON:

```bash
docker-agent task build-agent '{
  "type": "exec",
  "command": "npm run build",
  "cwd": "/workspace/my-app",
  "timeout": 300000
}'
```

## Stop and Start Agents

```bash
# Stop when not in use
docker-agent stop my-builder

# Start again when needed
docker-agent start my-builder
```

Data in `/workspace` persists between stops/starts.

## Clean Up

When done with an agent:

```bash
# Remove container (keeps data)
docker-agent destroy my-builder

# Remove container and data
docker-agent destroy my-builder --volumes
```

## Profiles

Available profiles:

- **builder**: Node.js builds, deployments
- **tester**: Test runners, browsers, linters
- **deployer**: Cloud deployments, SSH
- **researcher**: Python, data science, Jupyter
- **docker-host**: Docker-in-Docker for building containers

See `profiles/README.md` for details.

## Common Commands

```bash
# Create
docker-agent create <name> --profile <profile>

# List all
docker-agent list

# Status
docker-agent status <name>

# Execute command
docker-agent exec <name> <command>

# Shell
docker-agent shell <name>

# Logs
docker-agent logs <name> [--follow] [--tail N]

# Stop/Start
docker-agent stop <name>
docker-agent start <name>

# Destroy
docker-agent destroy <name> [--volumes]
```

## Hub Integration

Agents automatically connect to hub at `ws://host.docker.internal:9090`.

Verify connection:

```bash
# Check hub
curl http://localhost:9091/agents

# Check agent logs
docker-agent logs my-builder | grep "Connected to hub"
```

## Troubleshooting

### Agent won't start

```bash
# Check Docker
docker ps -a | grep openclaw-agent

# Check logs
docker logs openclaw-agent-<name>

# Check network
docker network inspect openclaw-agents
```

### Can't reach hub

```bash
# Test connectivity from container
docker-agent exec <name> "ping -c 3 host.docker.internal"

# Check hub is running
curl http://localhost:9091/health
```

### Out of resources

```bash
# Clean up stopped containers
docker container prune

# Clean up unused images
docker image prune

# Clean up volumes
docker volume prune
```

## Next Steps

- Read [README.md](README.md) for architecture details
- See [DOCKER.md](docs/DOCKER.md) for Docker-specific features
- Check [profiles/README.md](profiles/README.md) for profile details
- Read [PROFILE_MIGRATION.md](docs/PROFILE_MIGRATION.md) to create custom profiles

## Getting Help

- Check logs: `docker-agent logs <name>`
- Inspect container: `docker inspect openclaw-agent-<name>`
- Test manually: `docker run -it openclaw-agent-base /bin/bash`

## Tips

1. **Use profiles** - Don't start from scratch
2. **Use /workspace** - For persistent data
3. **Stop when idle** - Save resources
4. **Name agents clearly** - `project-builder`, not `agent1`
5. **Monitor resources** - `docker stats`
6. **Clean up regularly** - `docker system prune`
7. **Test locally first** - Before production
8. **Use docker-compose** - For multi-agent setups
9. **Pin versions** - Tag your images
10. **Read the docs** - They're comprehensive!

Happy building! 🚀

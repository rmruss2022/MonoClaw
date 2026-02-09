# Quick Start Guide

Get up and running with VM Agent System in 5 minutes.

## Prerequisites

1. **Node.js v18+** - Check with `node --version`
2. **Multipass** - Install from [multipass.run](https://multipass.run/)

## Installation

```bash
cd ~/.openclaw/workspace/vm-agent-system

# Install dependencies
cd hub && npm install && cd ..
cd cli && npm install && cd ..
cd agent-runtime && npm install && cd ..
```

## Start the Hub

```bash
# Terminal 1: Start hub server
cd hub
npm start

# You should see:
# ============================================================
# VM Agent Hub Server
# ============================================================
# HTTP API: http://localhost:9091
# WebSocket: ws://localhost:9090
# Metrics: http://localhost:9091/metrics
# ============================================================
```

## Start the Dashboard (Optional)

```bash
# Terminal 2: Start dashboard
cd hub
node dashboard-server.js

# Open in browser: http://localhost:9092
```

## Create Your First Agent

```bash
# Terminal 3: Create an agent
cd cli

# Basic agent (takes ~60 seconds)
./vm-agent create my-first-agent

# Or with custom resources
./vm-agent create builder \
  --type builder \
  --cpu 4 \
  --memory 8G \
  --disk 40G

# Check creation progress
# You'll see:
# - Creating VM with Multipass
# - Installing Node.js and dependencies
# - Registering with hub
# - Starting agent service
# - Agent is online and connected!
```

## Verify Agent is Running

```bash
# List all agents
./vm-agent list

# Output:
# ┌──────────────────┬────────┬─────────┬──────┬────────┬───────┬────────┐
# │ Name             │ Status │ Type    │ CPU  │ Memory │ Tasks │ Uptime │
# ├──────────────────┼────────┼─────────┼──────┼────────┼───────┼────────┤
# │ my-first-agent   │ online │ generic │ 2.5% │ 15.2%  │ 0     │ 1m     │
# └──────────────────┴────────┴─────────┴──────┴────────┴───────┴────────┘

# Check detailed status
./vm-agent status my-first-agent
```

## Run Your First Task

```bash
# Simple command
./vm-agent exec my-first-agent "echo 'Hello from VM!'"

# Output:
# Executing in my-first-agent: echo 'Hello from VM!'
# Hello from VM!

# Check system info
./vm-agent exec my-first-agent "uname -a"
./vm-agent exec my-first-agent "df -h"
./vm-agent exec my-first-agent "free -h"
```

## Send a Task via API

```bash
# Send a task
curl -X POST http://localhost:9091/agents/my-first-agent/task \
  -H "Content-Type: application/json" \
  -d '{
    "type": "exec",
    "command": "ls -la /tmp"
  }'

# Response:
# {"taskId":"abc123...","status":"sent"}
```

## View Agent Logs

```bash
# View recent logs
./vm-agent logs my-first-agent

# Follow logs in real-time
./vm-agent logs my-first-agent --follow

# Press Ctrl+C to stop following
```

## Create a Snapshot

```bash
# Create a snapshot for backup
./vm-agent snapshot my-first-agent backup-1

# List snapshots
multipass info my-first-agent

# Restore from snapshot (if needed)
./vm-agent restore my-first-agent backup-1
```

## Open Interactive Shell

```bash
# SSH into the VM
./vm-agent shell my-first-agent

# You're now in the VM!
# ubuntu@my-first-agent:~$

# Explore
ls -la
cat /etc/vm-agent/config.json
sudo systemctl status vm-agent

# Exit
exit
```

## Try Some Examples

### Clone and Build a Project

```bash
./vm-agent exec my-first-agent \
  "git clone https://github.com/user/repo /tmp/repo"

./vm-agent exec my-first-agent \
  "cd /tmp/repo && npm install && npm test"
```

### File Operations

```bash
# Create a file
./vm-agent exec my-first-agent \
  "echo 'Hello World' > /tmp/test.txt"

# Read it
./vm-agent exec my-first-agent \
  "cat /tmp/test.txt"

# Transfer to host
multipass transfer my-first-agent:/tmp/test.txt ./test.txt
```

### Install Software

```bash
# Install Python
./vm-agent exec my-first-agent \
  "sudo apt update && sudo apt install -y python3 python3-pip"

# Verify
./vm-agent exec my-first-agent \
  "python3 --version"
```

## Monitor in Dashboard

1. Open http://localhost:9092
2. See real-time agent status
3. Watch resource usage graphs
4. Monitor active tasks
5. View system logs

## Run Integration Tests

```bash
# Make sure hub is running, then:
cd test
node integration-test.js

# You should see:
# ============================================================
# VM Agent System Integration Test
# ============================================================
# ✓ Hub server is running
#
# [TEST] Hub server health check ... ✓ PASS
# [TEST] Register test agent ... ✓ PASS
# [TEST] List agents ... ✓ PASS
# [TEST] Get agent status ... ✓ PASS
# [TEST] Send task to offline agent ... ✓ PASS
# [TEST] Get routing statistics ... ✓ PASS
# [TEST] Prometheus metrics endpoint ... ✓ PASS
# [TEST] Deregister agent ... ✓ PASS
#
# ============================================================
# Test Summary
# ============================================================
# Passed: 8
# Failed: 0
# Total:  8
# ============================================================
#
# ✅ All tests passed!
```

## Cleanup

```bash
# Stop an agent
./vm-agent stop my-first-agent

# Start it again
./vm-agent start my-first-agent

# Destroy when done (WARNING: deletes all data)
./vm-agent destroy my-first-agent --force

# List remaining VMs
multipass list
```

## Auto-Start Hub on Boot (Optional)

```bash
# Copy LaunchAgent
cp LaunchAgents/com.openclaw.vm-hub.plist ~/Library/LaunchAgents/

# Load it
launchctl load ~/Library/LaunchAgents/com.openclaw.vm-hub.plist

# Hub will now start automatically on login

# To stop auto-start:
# launchctl unload ~/Library/LaunchAgents/com.openclaw.vm-hub.plist
```

## Common Issues

### "Hub server is not running"
```bash
# Start the hub in one terminal
cd hub
npm start

# Then try your command in another terminal
```

### "Multipass is not installed"
```bash
# macOS
brew install --cask multipass

# Ubuntu
sudo snap install multipass

# Windows
# Download from https://multipass.run/
```

### "Agent won't connect"
```bash
# Check agent logs
./vm-agent logs my-agent --follow

# Check agent service
multipass exec my-agent -- sudo systemctl status vm-agent

# Restart agent service
multipass exec my-agent -- sudo systemctl restart vm-agent
```

### "Port already in use"
```bash
# Check what's using the port
lsof -i :9090
lsof -i :9091

# Kill the process or use different ports
# export WS_PORT=9093
# export HTTP_PORT=9094
# npm start
```

## Next Steps

1. **Read the full [README.md](README.md)** for detailed documentation
2. **Check [ARCHITECTURE.md](ARCHITECTURE.md)** to understand how it works
3. **Try [example workflows](examples/workflows.md)** for real-world use cases
4. **Explore [VM Agents skill](../skills/vm-agents/SKILL.md)** for OpenClaw integration
5. **Create custom workflows** for your specific needs

## Getting Help

- Check logs: `~/.openclaw/workspace/vm-agent-system/logs/`
- Hub health: `curl http://localhost:9091/health`
- Agent status: `./vm-agent status <name>`
- System stats: `curl http://localhost:9091/admin/stats`

## Example: Complete Workflow

Here's a complete example from start to finish:

```bash
# 1. Start hub (if not running)
cd hub && npm start &

# 2. Create builder agent
cd ../cli
./vm-agent create builder --type builder --cpu 4 --memory 8G

# 3. Clone and build a project
./vm-agent exec builder \
  "git clone https://github.com/nodejs/node-addon-examples /tmp/project"

./vm-agent exec builder \
  "cd /tmp/project && npm install"

./vm-agent exec builder \
  "cd /tmp/project && npm test"

# 4. Get build artifacts
multipass transfer builder:/tmp/project/build ./build

# 5. Create snapshot for future use
./vm-agent snapshot builder clean-build

# 6. Cleanup
./vm-agent destroy builder --force

echo "Done! Build artifacts in ./build"
```

Congratulations! You now have a working VM agent system. 🎉

Check out the examples and documentation to learn more.

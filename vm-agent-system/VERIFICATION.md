# System Verification Checklist

Use this checklist to verify the VM Agent System is fully functional.

## Prerequisites ✅

- [ ] Node.js v18+ installed (`node --version`)
- [ ] Multipass installed (`multipass version`)
- [ ] All dependencies installed (`./setup.sh`)

## Hub Server ✅

### Start Hub
```bash
cd hub
npm start
```

- [ ] Server starts without errors
- [ ] WebSocket listening on port 9090
- [ ] HTTP API listening on port 9091
- [ ] No crash or warnings

### Health Check
```bash
curl http://localhost:9091/health
```

Expected response:
```json
{
  "status": "healthy",
  "uptime": <number>,
  "timestamp": <timestamp>,
  "agents": {
    "total": 0,
    "online": 0
  }
}
```

- [ ] Returns 200 OK
- [ ] JSON format is correct
- [ ] Status is "healthy"

### Metrics
```bash
curl http://localhost:9091/metrics
```

- [ ] Returns Prometheus format metrics
- [ ] Includes `vm_hub_` metrics
- [ ] No errors

## Dashboard ✅

### Start Dashboard
```bash
cd hub
node dashboard-server.js
```

- [ ] Server starts on port 9092
- [ ] Open http://localhost:9092
- [ ] Page loads without errors
- [ ] Dark theme displays correctly
- [ ] Shows "0 agents" initially

## CLI Tool ✅

### Help Command
```bash
cd cli
./vm-agent --help
```

- [ ] Shows help text
- [ ] Lists all commands
- [ ] No errors

### List Command (Empty)
```bash
./vm-agent list
```

- [ ] Shows "No agents registered" or empty table
- [ ] No errors

## Agent Creation ✅

### Create Test Agent
```bash
./vm-agent create test-agent
```

Watch for:
- [ ] "Creating VM with Multipass..." message
- [ ] VM creation completes (~60 seconds)
- [ ] Node.js installation
- [ ] Agent runtime copied
- [ ] Hub registration succeeds
- [ ] Agent token generated
- [ ] Agent service starts
- [ ] "Agent is online and connected!" message
- [ ] Initial snapshot created

### Verify VM
```bash
multipass list
```

- [ ] Shows `test-agent` VM
- [ ] Status is "Running"
- [ ] Has IP address

### Verify Registration
```bash
curl http://localhost:9091/agents
```

- [ ] Returns agent list with `test-agent`
- [ ] Agent status is "online"

### Check Dashboard
- [ ] Refresh dashboard (http://localhost:9092)
- [ ] Shows 1 agent
- [ ] Agent card displays
- [ ] Status is "online"
- [ ] Resource stats showing

## Agent Operations ✅

### Status Command
```bash
./vm-agent status test-agent
```

- [ ] Shows agent details
- [ ] Status: online
- [ ] Resource usage displayed
- [ ] No errors

### Execute Command
```bash
./vm-agent exec test-agent "echo 'Hello from VM'"
```

- [ ] Command executes
- [ ] Output shows "Hello from VM"
- [ ] No errors

### System Commands
```bash
./vm-agent exec test-agent "uname -a"
./vm-agent exec test-agent "df -h"
./vm-agent exec test-agent "free -h"
```

- [ ] All commands succeed
- [ ] Output is reasonable

### Logs
```bash
./vm-agent logs test-agent --lines 20
```

- [ ] Shows systemd logs
- [ ] Contains agent startup messages
- [ ] No critical errors

### Shell Access
```bash
./vm-agent shell test-agent
```

- [ ] Opens SSH session
- [ ] Prompt appears
- [ ] Can execute commands
- [ ] `exit` closes session

## Task Execution ✅

### Send Task via CLI
```bash
./vm-agent task test-agent '{"type":"exec","command":"date"}'
```

- [ ] Task accepted
- [ ] Returns task ID
- [ ] No errors

### Send Task via API
```bash
curl -X POST http://localhost:9091/agents/test-agent/task \
  -H "Content-Type: application/json" \
  -d '{"type":"exec","command":"hostname"}'
```

Expected response:
```json
{
  "taskId": "<uuid>",
  "status": "sent"
}
```

- [ ] Returns 200 OK
- [ ] Contains taskId
- [ ] Status is "sent"

### Verify Task in Dashboard
- [ ] Refresh dashboard
- [ ] Check agent stats
- [ ] Tasks received count increased

## Snapshots ✅

### Create Snapshot
```bash
./vm-agent snapshot test-agent test-snapshot-1
```

- [ ] Snapshot created successfully
- [ ] No errors

### Verify Snapshot
```bash
multipass info test-agent
```

- [ ] Shows snapshot in list
- [ ] Snapshot name appears

### Restore Snapshot
```bash
./vm-agent restore test-agent test-snapshot-1
```

- [ ] Restore completes
- [ ] Agent service restarts
- [ ] Agent reconnects

## VM Management ✅

### Stop VM
```bash
./vm-agent stop test-agent
```

- [ ] VM stops
- [ ] Dashboard shows agent offline
- [ ] No errors

### Start VM
```bash
./vm-agent start test-agent
```

- [ ] VM starts
- [ ] Agent service auto-starts
- [ ] Agent reconnects to hub
- [ ] Dashboard shows online

## Integration Test ✅

### Run Test Suite
```bash
cd test
node integration-test.js
```

- [ ] All 8 tests pass
- [ ] No failures
- [ ] Summary shows 100% pass rate

## Cleanup ✅

### Destroy Agent
```bash
./vm-agent destroy test-agent --force
```

- [ ] Agent deregistered from hub
- [ ] VM deleted
- [ ] `multipass list` shows no test-agent
- [ ] Dashboard shows 0 agents

## Advanced Features ✅

### Health Monitoring
```bash
# Create agent and wait 1 minute
./vm-agent create monitor-test
sleep 60
./vm-agent status monitor-test
```

- [ ] Shows CPU usage
- [ ] Shows memory usage
- [ ] Shows disk usage
- [ ] Uptime increases

### Auto-Reconnection
```bash
# Create agent
./vm-agent create reconnect-test

# Stop agent service
multipass exec reconnect-test -- sudo systemctl stop vm-agent

# Wait 30 seconds, check hub
curl http://localhost:9091/agents/reconnect-test/status

# Start service
multipass exec reconnect-test -- sudo systemctl start vm-agent

# Wait 10 seconds, check again
sleep 10
curl http://localhost:9091/agents/reconnect-test/status
```

- [ ] Agent shows offline when service stopped
- [ ] Agent reconnects when service started
- [ ] No manual intervention needed

### Message Queuing
```bash
# Stop agent
./vm-agent stop test-queue

# Send task while offline
curl -X POST http://localhost:9091/agents/test-queue/task \
  -H "Content-Type: application/json" \
  -d '{"type":"exec","command":"echo queued"}'

# Start agent
./vm-agent start test-queue

# Check logs - should see queued message
./vm-agent logs test-queue --lines 50 | grep queued
```

- [ ] Task queued while offline
- [ ] Task delivered on reconnect
- [ ] Task executes

## Performance ✅

### Resource Usage
```bash
# Check hub memory
ps aux | grep "node.*server.js"

# Check agent memory
./vm-agent exec test-agent "free -h"
```

- [ ] Hub uses <100MB RAM
- [ ] Agent uses <200MB RAM
- [ ] CPU usage is reasonable

### Message Latency
```bash
time curl -X POST http://localhost:9091/agents/test-agent/task \
  -H "Content-Type: application/json" \
  -d '{"type":"exec","command":"echo test"}'
```

- [ ] Response time <100ms
- [ ] No timeouts

## Documentation ✅

- [ ] README.md is complete
- [ ] ARCHITECTURE.md explains system
- [ ] QUICKSTART.md provides guide
- [ ] examples/workflows.md has examples
- [ ] skills/vm-agents/SKILL.md exists
- [ ] All code is commented

## Final Checks ✅

- [ ] All files have correct permissions
- [ ] No sensitive data in configs
- [ ] Logs directory exists
- [ ] LaunchAgent plist is valid
- [ ] .gitignore is comprehensive
- [ ] LICENSE file present

## Success Criteria

All checkboxes should be checked ✅

If any fail, review the relevant section in the documentation.

---

**Total Checks:** ~80+

**Required Pass Rate:** 100%

**Status:** Complete when all boxes checked

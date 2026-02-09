# VM Agents Skill

Manage VM-based agent instances for delegated task execution.

## Overview

The VM Agent system allows you to spawn isolated virtual machine instances that can execute tasks independently. Each agent runs in its own VM with dedicated resources and communicates with a central hub.

## Components

- **Hub Server**: Central coordination service (ports 9090, 9091)
- **Agent Runtime**: Code running in each VM
- **CLI Tool**: Command-line management interface
- **Dashboard**: Web-based monitoring (port 9092)

## Common Commands

### Start Hub Server

```bash
cd ~/.openclaw/workspace/vm-agent-system/hub
npm start
```

### Create an Agent

```bash
cd ~/.openclaw/workspace/vm-agent-system/cli

# Basic agent
./vm-agent create my-agent

# Builder agent with custom resources
./vm-agent create builder-1 \
  --type builder \
  --cpu 4 \
  --memory 8G \
  --disk 40G \
  --capabilities "build,docker,deploy"
```

### List Agents

```bash
./vm-agent list

# Filter by status
./vm-agent list --status online

# Filter by type
./vm-agent list --type builder
```

### Check Agent Status

```bash
./vm-agent status my-agent

# Watch continuously
./vm-agent status my-agent --watch
```

### Execute Commands

```bash
# Simple command
./vm-agent exec my-agent "ls -la"

# With sudo
./vm-agent exec my-agent "apt update" --sudo

# Complex command
./vm-agent exec my-agent "cd /tmp && git clone https://github.com/user/repo"
```

### Send Tasks via API

```javascript
// Using curl
curl -X POST http://localhost:9091/agents/my-agent/task \
  -H "Content-Type: application/json" \
  -d '{
    "type": "exec",
    "command": "npm install && npm test",
    "cwd": "/opt/project",
    "timeout": 300000
  }'

// Using Node.js
const response = await fetch('http://localhost:9091/agents/my-agent/task', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    type: 'build',
    command: 'npm run build',
    cwd: '/opt/project'
  })
});

const { taskId } = await response.json();
```

### View Logs

```bash
# View recent logs
./vm-agent logs my-agent

# Follow logs
./vm-agent logs my-agent --follow

# Show last 50 lines
./vm-agent logs my-agent --lines 50
```

### Snapshots

```bash
# Create snapshot
./vm-agent snapshot my-agent backup-before-update

# Restore from snapshot
./vm-agent restore my-agent backup-before-update
```

### VM Management

```bash
# Start/stop VM
./vm-agent start my-agent
./vm-agent stop my-agent

# Open shell
./vm-agent shell my-agent

# Destroy agent
./vm-agent destroy my-agent --force
```

## Task Types

### Execute Shell Command

```json
{
  "type": "exec",
  "command": "ls -la /tmp",
  "cwd": "/path/to/dir",
  "timeout": 30000
}
```

### Run Node.js Script

```json
{
  "type": "script",
  "script": "console.log('Hello from VM')",
  "args": ["arg1", "arg2"]
}
```

### Clone Git Repository

```json
{
  "type": "git:clone",
  "repo": "https://github.com/user/repo",
  "destination": "/opt/repo",
  "branch": "main"
}
```

### Build Project

```json
{
  "type": "build",
  "command": "npm run build",
  "cwd": "/opt/project"
}
```

### Run Tests

```json
{
  "type": "test",
  "command": "npm test",
  "cwd": "/opt/project"
}
```

## Use Cases

### 1. Isolated Build Environment

```bash
# Create builder agent
./vm-agent create builder --type builder --cpu 4 --memory 8G

# Clone and build project
./vm-agent exec builder "git clone https://github.com/user/repo /opt/repo"
./vm-agent exec builder "cd /opt/repo && npm install && npm run build"

# Get build artifacts
multipass transfer builder:/opt/repo/dist ./dist
```

### 2. Parallel Test Execution

```bash
# Create multiple test agents
for i in {1..3}; do
  ./vm-agent create test-$i --type tester --cpu 2 --memory 4G
done

# Distribute tests
./vm-agent exec test-1 "cd /opt/tests && npm test -- --shard=1/3"
./vm-agent exec test-2 "cd /opt/tests && npm test -- --shard=2/3"
./vm-agent exec test-3 "cd /opt/tests && npm test -- --shard=3/3"
```

### 3. Long-Running Jobs

```bash
# Create agent for long job
./vm-agent create job-runner --type worker

# Send task
curl -X POST http://localhost:9091/agents/job-runner/task \
  -H "Content-Type: application/json" \
  -d '{
    "type": "exec",
    "command": "python train_model.py",
    "cwd": "/opt/ml",
    "timeout": 7200000
  }'

# Monitor progress
./vm-agent logs job-runner --follow
```

### 4. Disposable Research Environment

```bash
# Create research agent
./vm-agent create researcher --type researcher

# Install tools
./vm-agent exec researcher "apt update && apt install -y python3-pip" --sudo
./vm-agent exec researcher "pip3 install pandas numpy jupyter"

# Open shell for interactive work
./vm-agent shell researcher

# When done, destroy
./vm-agent destroy researcher --force
```

## Integration Examples

### From OpenClaw Agent

```javascript
// Spawn a VM agent for a task
async function delegateToVM(task) {
  const agentName = `task-${Date.now()}`;
  
  // Create agent
  await exec(`vm-agent create ${agentName} --type worker`);
  
  // Send task
  const response = await fetch(`http://localhost:9091/agents/${agentName}/task`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(task)
  });
  
  const { taskId } = await response.json();
  
  // Wait for completion (simplified)
  // In production, use WebSocket to listen for response
  
  return taskId;
}
```

### Workflow Example

```javascript
// Multi-stage build workflow
async function buildPipeline(repo) {
  // Create agent
  const agent = 'pipeline-agent';
  await exec(`vm-agent create ${agent} --type builder`);
  
  // Stage 1: Clone
  await sendTask(agent, {
    type: 'git:clone',
    repo,
    destination: '/opt/repo'
  });
  
  // Stage 2: Install deps
  await sendTask(agent, {
    type: 'exec',
    command: 'npm install',
    cwd: '/opt/repo'
  });
  
  // Stage 3: Build
  await sendTask(agent, {
    type: 'build',
    command: 'npm run build',
    cwd: '/opt/repo'
  });
  
  // Stage 4: Test
  await sendTask(agent, {
    type: 'test',
    command: 'npm test',
    cwd: '/opt/repo'
  });
  
  // Cleanup
  await exec(`vm-agent destroy ${agent} --force`);
}
```

## Monitoring

### Dashboard

Access the web dashboard at:
```
http://localhost:9092
```

Features:
- Real-time agent status
- Resource usage graphs
- Active task monitoring
- System logs

### API Health Check

```bash
curl http://localhost:9091/health
```

### Agent Health

```bash
curl http://localhost:9091/agents/my-agent/status
```

## Troubleshooting

### Hub won't start

```bash
# Check if ports are in use
lsof -i :9090
lsof -i :9091

# View logs
tail -f ~/.openclaw/workspace/vm-agent-system/logs/hub-stdout.log
```

### Agent offline

```bash
# Check VM status
multipass list

# Check agent service
multipass exec my-agent -- sudo systemctl status vm-agent

# Restart service
multipass exec my-agent -- sudo systemctl restart vm-agent

# View agent logs
./vm-agent logs my-agent --follow
```

### Task timeout

Tasks have a default 30-minute timeout. Increase for long-running tasks:

```json
{
  "type": "exec",
  "command": "long-running-command",
  "timeout": 7200000  // 2 hours in ms
}
```

## Best Practices

1. **Resource Allocation**: Start small, scale as needed
2. **Snapshots**: Create before risky operations
3. **Cleanup**: Destroy agents when done to free resources
4. **Monitoring**: Use dashboard to watch resource usage
5. **Error Handling**: Always handle task failures
6. **Timeouts**: Set appropriate timeouts for tasks
7. **Logging**: Enable verbose logging for debugging

## Advanced Configuration

### Custom VM Image

```bash
# Create custom image with pre-installed tools
# (Future feature - currently uses cloud-init)
```

### Agent Capabilities

Use capabilities to tag agents with specific skills:

```bash
./vm-agent create gpu-agent \
  --capabilities "gpu,tensorflow,pytorch"
```

Then query by capability when delegating tasks.

## Files & Paths

- **Hub**: `~/.openclaw/workspace/vm-agent-system/hub/`
- **CLI**: `~/.openclaw/workspace/vm-agent-system/cli/vm-agent`
- **Dashboard**: `http://localhost:9092`
- **Logs**: `~/.openclaw/workspace/vm-agent-system/logs/`
- **LaunchAgent**: `~/Library/LaunchAgents/com.openclaw.vm-hub.plist`

## Related Skills

- **Command Hub**: Central command routing
- **GitHub Integration**: Auto-deploy to VM agents
- **Discord Bot**: Get agent status via Discord

## Documentation

- [README.md](../../vm-agent-system/README.md)
- [ARCHITECTURE.md](../../vm-agent-system/ARCHITECTURE.md)

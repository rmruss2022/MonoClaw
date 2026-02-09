# VM Agent Workflows

Example workflows for common use cases.

## 1. Automated Build Pipeline

```bash
#!/bin/bash
# build-pipeline.sh

AGENT_NAME="builder-$(date +%s)"
REPO_URL="https://github.com/your-org/your-project"

# Create builder agent
./cli/vm-agent create $AGENT_NAME \
  --type builder \
  --cpu 4 \
  --memory 8G \
  --disk 40G

# Clone repository
./cli/vm-agent exec $AGENT_NAME \
  "git clone $REPO_URL /opt/project"

# Install dependencies
./cli/vm-agent exec $AGENT_NAME \
  "cd /opt/project && npm install"

# Run tests
./cli/vm-agent exec $AGENT_NAME \
  "cd /opt/project && npm test"

# Build
./cli/vm-agent exec $AGENT_NAME \
  "cd /opt/project && npm run build"

# Get artifacts
multipass transfer $AGENT_NAME:/opt/project/dist ./dist

# Cleanup
./cli/vm-agent destroy $AGENT_NAME --force

echo "Build complete! Artifacts in ./dist"
```

## 2. Parallel Test Execution

```javascript
// parallel-tests.js

const { spawn } = require('child_process');

async function exec(command) {
  return new Promise((resolve, reject) => {
    const proc = spawn('bash', ['-c', command]);
    proc.on('close', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`Exit code ${code}`));
    });
  });
}

async function runParallelTests(testShards = 3) {
  const agents = [];

  // Create test agents
  console.log(`Creating ${testShards} test agents...`);
  for (let i = 1; i <= testShards; i++) {
    const name = `test-agent-${i}`;
    await exec(`./cli/vm-agent create ${name} --type tester --cpu 2 --memory 4G`);
    agents.push(name);
  }

  // Setup project on each agent
  console.log('Setting up project on agents...');
  await Promise.all(agents.map(agent =>
    exec(`./cli/vm-agent exec ${agent} "git clone https://github.com/user/repo /opt/tests"`)
  ));

  // Run tests in parallel
  console.log('Running tests in parallel...');
  const testPromises = agents.map((agent, i) =>
    exec(`./cli/vm-agent exec ${agent} "cd /opt/tests && npm test -- --shard=${i + 1}/${testShards}"`)
  );

  try {
    await Promise.all(testPromises);
    console.log('All tests passed!');
  } catch (error) {
    console.error('Some tests failed');
    throw error;
  } finally {
    // Cleanup
    console.log('Cleaning up...');
    await Promise.all(agents.map(agent =>
      exec(`./cli/vm-agent destroy ${agent} --force`)
    ));
  }
}

runParallelTests(3).catch(console.error);
```

## 3. Continuous Deployment

```javascript
// deploy-workflow.js

const http = require('http');

async function sendTask(agentId, task) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(task);
    const options = {
      hostname: 'localhost',
      port: 9091,
      path: `/agents/${agentId}/task`,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': data.length
      }
    };

    const req = http.request(options, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => resolve(JSON.parse(body)));
    });

    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

async function deployApp(repo, branch = 'main') {
  const agentId = 'deploy-agent';

  console.log('1. Cloning repository...');
  await sendTask(agentId, {
    type: 'git:clone',
    repo,
    destination: '/opt/deploy',
    branch
  });

  console.log('2. Installing dependencies...');
  await sendTask(agentId, {
    type: 'exec',
    command: 'npm install --production',
    cwd: '/opt/deploy'
  });

  console.log('3. Building application...');
  await sendTask(agentId, {
    type: 'build',
    command: 'npm run build',
    cwd: '/opt/deploy'
  });

  console.log('4. Running tests...');
  await sendTask(agentId, {
    type: 'test',
    command: 'npm test',
    cwd: '/opt/deploy',
    timeout: 600000
  });

  console.log('5. Deploying to production...');
  await sendTask(agentId, {
    type: 'exec',
    command: './deploy.sh production',
    cwd: '/opt/deploy',
    timeout: 300000
  });

  console.log('✅ Deployment complete!');
}

// Usage
deployApp('https://github.com/user/app', 'main')
  .catch(console.error);
```

## 4. Data Processing Pipeline

```javascript
// data-pipeline.js

async function processDataPipeline(dataFiles) {
  const workers = 3;
  const agents = Array.from({ length: workers }, (_, i) => `worker-${i + 1}`);

  // Create worker agents
  console.log('Creating worker agents...');
  for (const agent of agents) {
    await exec(`./cli/vm-agent create ${agent} --type worker --cpu 2 --memory 4G`);
  }

  // Distribute work
  console.log('Processing data...');
  const chunkSize = Math.ceil(dataFiles.length / workers);
  
  const tasks = agents.map(async (agent, i) => {
    const start = i * chunkSize;
    const end = Math.min(start + chunkSize, dataFiles.length);
    const files = dataFiles.slice(start, end);

    for (const file of files) {
      await sendTask(agent, {
        type: 'exec',
        command: `python3 process.py ${file}`,
        cwd: '/opt/pipeline',
        timeout: 600000
      });
    }
  });

  await Promise.all(tasks);

  // Aggregate results
  console.log('Aggregating results...');
  await sendTask(agents[0], {
    type: 'exec',
    command: 'python3 aggregate.py',
    cwd: '/opt/pipeline'
  });

  // Cleanup
  console.log('Cleaning up...');
  for (const agent of agents) {
    await exec(`./cli/vm-agent destroy ${agent} --force`);
  }

  console.log('✅ Pipeline complete!');
}
```

## 5. Disposable Development Environment

```bash
#!/bin/bash
# dev-env.sh

ENV_NAME="dev-$(date +%s)"

# Create dev environment
./cli/vm-agent create $ENV_NAME \
  --type developer \
  --cpu 2 \
  --memory 4G \
  --disk 30G

# Install development tools
./cli/vm-agent exec $ENV_NAME \
  "sudo apt update && sudo apt install -y \
    git curl wget \
    python3 python3-pip \
    nodejs npm \
    docker.io"

# Setup project
./cli/vm-agent exec $ENV_NAME \
  "git clone https://github.com/user/project /home/ubuntu/project"

# Install project dependencies
./cli/vm-agent exec $ENV_NAME \
  "cd /home/ubuntu/project && npm install"

# Open shell
echo "Development environment ready!"
echo "Connect with: ./cli/vm-agent shell $ENV_NAME"
./cli/vm-agent shell $ENV_NAME

# After exiting shell
read -p "Destroy environment? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  ./cli/vm-agent destroy $ENV_NAME --force
fi
```

## 6. Scheduled Tasks with Cron

```javascript
// scheduled-tasks.js

const cron = require('node-cron');

// Daily backup task at 2 AM
cron.schedule('0 2 * * *', async () => {
  console.log('Running daily backup...');
  
  const agentId = 'backup-agent';
  
  await sendTask(agentId, {
    type: 'exec',
    command: './backup.sh',
    cwd: '/opt/scripts',
    timeout: 3600000 // 1 hour
  });
  
  console.log('Backup complete');
});

// Weekly report generation on Sundays at 8 AM
cron.schedule('0 8 * * 0', async () => {
  console.log('Generating weekly report...');
  
  const agentId = 'report-agent';
  
  await sendTask(agentId, {
    type: 'exec',
    command: 'python3 generate_report.py --week',
    cwd: '/opt/reports',
    timeout: 1800000 // 30 minutes
  });
  
  console.log('Report generated');
});
```

## 7. Multi-Stage Build with Snapshots

```bash
#!/bin/bash
# multi-stage-build.sh

AGENT_NAME="builder"

# Create agent
./cli/vm-agent create $AGENT_NAME --type builder --cpu 4 --memory 8G

# Stage 1: Setup
./cli/vm-agent exec $AGENT_NAME "sudo apt update && sudo apt install -y build-essential"
./cli/vm-agent snapshot $AGENT_NAME stage-1-setup

# Stage 2: Dependencies
./cli/vm-agent exec $AGENT_NAME "git clone https://github.com/user/project /opt/project"
./cli/vm-agent exec $AGENT_NAME "cd /opt/project && npm install"
./cli/vm-agent snapshot $AGENT_NAME stage-2-deps

# Stage 3: Build
./cli/vm-agent exec $AGENT_NAME "cd /opt/project && npm run build"

if [ $? -eq 0 ]; then
  echo "Build successful!"
  ./cli/vm-agent snapshot $AGENT_NAME stage-3-built
else
  echo "Build failed, restoring to stage-2..."
  ./cli/vm-agent restore $AGENT_NAME stage-2-deps
  exit 1
fi

# Get artifacts
multipass transfer $AGENT_NAME:/opt/project/dist ./dist

# Cleanup
./cli/vm-agent destroy $AGENT_NAME --force
```

## 8. Load Testing

```javascript
// load-test.js

async function loadTest(targetUrl, concurrency = 10, duration = 60) {
  const agents = [];

  // Create load testing agents
  console.log(`Creating ${concurrency} load testers...`);
  for (let i = 1; i <= concurrency; i++) {
    const name = `load-${i}`;
    await exec(`./cli/vm-agent create ${name} --type tester --cpu 1 --memory 2G`);
    agents.push(name);
  }

  // Install load testing tools
  console.log('Installing tools...');
  await Promise.all(agents.map(agent =>
    exec(`./cli/vm-agent exec ${agent} "sudo apt install -y apache2-utils"`)
  ));

  // Run load test
  console.log(`Starting ${duration}s load test against ${targetUrl}...`);
  const testPromises = agents.map(agent =>
    sendTask(agent, {
      type: 'exec',
      command: `ab -t ${duration} -c 10 ${targetUrl}`,
      timeout: (duration + 10) * 1000
    })
  );

  const results = await Promise.all(testPromises);

  // Aggregate results
  console.log('Load test complete!');
  console.log('Results:', results);

  // Cleanup
  console.log('Cleaning up...');
  await Promise.all(agents.map(agent =>
    exec(`./cli/vm-agent destroy ${agent} --force`)
  ));
}

loadTest('http://example.com/', 10, 60);
```

## 9. Machine Learning Training

```javascript
// ml-training.js

async function trainModel(dataset, modelConfig) {
  const agentId = 'ml-trainer';

  // Send training task
  console.log('Starting model training...');
  const result = await sendTask(agentId, {
    type: 'exec',
    command: `python3 train.py --dataset ${dataset} --config ${modelConfig}`,
    cwd: '/opt/ml',
    timeout: 7200000 // 2 hours
  });

  console.log('Training complete!');
  
  // Get model artifacts
  console.log('Downloading model...');
  await exec(`multipass transfer ${agentId}:/opt/ml/models/trained.pkl ./trained.pkl`);

  return result;
}
```

## 10. Security Scanning

```bash
#!/bin/bash
# security-scan.sh

AGENT_NAME="security-scanner"

# Create isolated scanner
./cli/vm-agent create $AGENT_NAME --type scanner --cpu 2 --memory 4G

# Install security tools
./cli/vm-agent exec $AGENT_NAME \
  "sudo apt update && sudo apt install -y \
    nmap \
    nikto \
    sqlmap \
    metasploit-framework"

# Run scans
./cli/vm-agent exec $AGENT_NAME "nmap -A target.com > /tmp/nmap-results.txt"
./cli/vm-agent exec $AGENT_NAME "nikto -h target.com > /tmp/nikto-results.txt"

# Get results
multipass transfer $AGENT_NAME:/tmp/nmap-results.txt ./scan-results/
multipass transfer $AGENT_NAME:/tmp/nikto-results.txt ./scan-results/

# Destroy (security tools can be sensitive)
./cli/vm-agent destroy $AGENT_NAME --force

echo "Security scan complete. Results in ./scan-results/"
```

## Tips

1. **Resource Management**: Monitor resource usage via dashboard
2. **Snapshots**: Create snapshots before risky operations
3. **Error Handling**: Always include try/catch for task execution
4. **Cleanup**: Destroy agents when done to free resources
5. **Logging**: Use `--follow` flag to watch long-running tasks
6. **Timeouts**: Set appropriate timeouts for long tasks
7. **Parallel Execution**: Use Promise.all() for concurrent tasks

## Next Steps

- Integrate with CI/CD pipelines
- Add webhook triggers
- Create agent templates
- Build custom task types
- Add result persistence

# Profile Usage Examples

Real-world examples of using agent profiles for common workflows.

## Example 1: Build MonoClaw Blog

```bash
# 1. Create a builder agent
cd cli
./vm-agent create blog-builder --profile builder

# Wait for agent to come online (~60 seconds)

# 2. Clone the repository
./vm-agent task blog-builder '{
  "type": "git:clone",
  "repo": "https://github.com/rmruss2022/MonoClaw",
  "destination": "/home/ubuntu/MonoClaw"
}'

# 3. Build the blog
./vm-agent task blog-builder '{
  "type": "build",
  "cwd": "/home/ubuntu/MonoClaw/matts-claw-blog",
  "command": "npm install && npm run build"
}'

# 4. Check the build output
./vm-agent exec blog-builder "ls -la /home/ubuntu/MonoClaw/matts-claw-blog/.next"

# 5. Optionally snapshot the build environment
./vm-agent snapshot blog-builder blog-ready

# 6. Cleanup when done
./vm-agent destroy blog-builder --force
```

## Example 2: Run E2E Tests

```bash
# 1. Create tester agent
./vm-agent create test-runner --profile tester

# 2. Clone and setup
./vm-agent task test-runner '{
  "type": "git:clone",
  "repo": "https://github.com/user/webapp",
  "destination": "/home/ubuntu/webapp"
}'

./vm-agent exec test-runner "cd webapp && npm install"

# 3. Run Playwright tests
./vm-agent task test-runner '{
  "type": "test",
  "cwd": "/home/ubuntu/webapp",
  "command": "npx playwright test --reporter=html"
}'

# 4. Fetch test report
./vm-agent task test-runner '{
  "type": "file:read",
  "filePath": "/home/ubuntu/webapp/playwright-report/index.html"
}' > test-report.html

# 5. Check status
./vm-agent status test-runner

# 6. View logs if tests failed
./vm-agent logs test-runner --lines 100
```

## Example 3: Deploy to Vercel

```bash
# 1. Create deployer agent
./vm-agent create my-deployer --profile deployer

# 2. Send the built artifacts (or build in the deployer)
./vm-agent task my-deployer '{
  "type": "git:clone",
  "repo": "https://github.com/user/app",
  "destination": "/home/ubuntu/app"
}'

./vm-agent exec my-deployer "cd app && npm install"

# 3. Deploy with credentials
./vm-agent task my-deployer '{
  "type": "deploy",
  "cwd": "/home/ubuntu/app",
  "command": "vercel --prod --token $VERCEL_TOKEN",
  "env": {
    "VERCEL_TOKEN": "your-vercel-token-here"
  },
  "timeout": 600000
}'

# 4. Get deployment URL from logs
./vm-agent logs my-deployer --lines 50 | grep "https://"
```

## Example 4: Web Scraping Research

```bash
# 1. Create researcher agent
./vm-agent create scraper --profile researcher

# 2. Send scraping script
./vm-agent task scraper '{
  "type": "file:write",
  "filePath": "/home/ubuntu/scraper.js",
  "content": "const puppeteer = require(\"puppeteer\"); (async () => { const browser = await puppeteer.launch({headless: true}); const page = await browser.newPage(); await page.goto(\"https://example.com\"); const title = await page.title(); console.log(title); await browser.close(); })();"
}'

# 3. Run the scraper
./vm-agent task scraper '{
  "type": "exec",
  "command": "node scraper.js",
  "cwd": "/home/ubuntu",
  "timeout": 120000
}'

# 4. Collect results
./vm-agent task scraper '{
  "type": "file:read",
  "filePath": "/home/ubuntu/scraper-results.json"
}'
```

## Example 5: Docker Container Management

```bash
# 1. Create Docker host
./vm-agent create docker-host-1 --profile docker-host

# 2. Build a Docker image
./vm-agent task docker-host-1 '{
  "type": "file:write",
  "filePath": "/home/ubuntu/Dockerfile",
  "content": "FROM node:18-alpine\\nWORKDIR /app\\nCOPY package.json .\\nRUN npm install\\nCOPY . .\\nCMD [\"node\", \"server.js\"]"
}'

./vm-agent exec docker-host-1 "cd /home/ubuntu && docker build -t myapp:latest ."

# 3. Run the container
./vm-agent task docker-host-1 '{
  "type": "exec",
  "command": "docker run -d -p 3000:3000 --name myapp myapp:latest"
}'

# 4. Check container status
./vm-agent exec docker-host-1 "docker ps"

# 5. View container logs
./vm-agent exec docker-host-1 "docker logs myapp"

# 6. Stop and remove
./vm-agent exec docker-host-1 "docker stop myapp && docker rm myapp"
```

## Example 6: Parallel Testing with Multiple Agents

```bash
# Create multiple test agents
for i in {1..3}; do
  ./vm-agent create test-runner-$i --profile tester &
done
wait

# Distribute test suites
./vm-agent task test-runner-1 '{
  "type": "test",
  "command": "npm test -- --shard=1/3"
}'

./vm-agent task test-runner-2 '{
  "type": "test",
  "command": "npm test -- --shard=2/3"
}'

./vm-agent task test-runner-3 '{
  "type": "test",
  "command": "npm test -- --shard=3/3"
}'

# Monitor all agents
./vm-agent list
```

## Example 7: Custom Profile for Specific Project

Create `myproject-profile.json`:
```json
{
  "name": "myproject",
  "description": "Custom build environment for MyProject",
  "resources": {
    "cpu": 4,
    "memory": "8G",
    "disk": "30G"
  },
  "environment": {
    "NODE_ENV": "production",
    "PROJECT_NAME": "MyProject",
    "BUILD_DIR": "/home/ubuntu/builds"
  },
  "files": [
    {
      "path": "/home/ubuntu/.npmrc",
      "content": "//registry.npmjs.org/:_authToken=your-token"
    },
    {
      "path": "/home/ubuntu/build-instructions.md",
      "content": "# MyProject Build Instructions\\n\\n1. Clone repo\\n2. npm install\\n3. npm run build:prod\\n4. Deploy to S3"
    }
  ],
  "packages": [
    "git",
    "curl",
    "awscli"
  ],
  "repositories": [
    {
      "url": "https://github.com/user/myproject",
      "destination": "/home/ubuntu/myproject",
      "branch": "main"
    }
  ],
  "setup_tasks": [
    {
      "type": "exec",
      "command": "npm install -g @myorg/cli-tools",
      "description": "Install company CLI tools"
    },
    {
      "type": "exec",
      "command": "mkdir -p /home/ubuntu/builds /home/ubuntu/artifacts",
      "description": "Create working directories"
    }
  ]
}
```

Use it:
```bash
# Create the profile
./vm-agent-profiles create myproject --from-file myproject-profile.json

# Create agent with the profile
./vm-agent create myproject-builder --profile myproject

# Repository is already cloned! Just build
./vm-agent exec myproject-builder "cd myproject && npm install && npm run build:prod"
```

## Example 8: Continuous Integration Pipeline

```bash
#!/bin/bash
# ci-pipeline.sh - Full CI/CD using VM agents

set -e

REPO="https://github.com/user/app"
BRANCH="$1"

# 1. Create builder
echo "Creating builder..."
./vm-agent create ci-builder-$BRANCH --profile builder

# 2. Clone and build
echo "Cloning $REPO @ $BRANCH..."
./vm-agent task ci-builder-$BRANCH "{
  \"type\": \"git:clone\",
  \"repo\": \"$REPO\",
  \"branch\": \"$BRANCH\",
  \"destination\": \"/home/ubuntu/app\"
}"

echo "Building..."
./vm-agent task ci-builder-$BRANCH '{
  "type": "build",
  "cwd": "/home/ubuntu/app",
  "command": "npm install && npm run build"
}'

# 3. Create tester and run tests
echo "Creating tester..."
./vm-agent create ci-tester-$BRANCH --profile tester

./vm-agent task ci-tester-$BRANCH "{
  \"type\": \"git:clone\",
  \"repo\": \"$REPO\",
  \"branch\": \"$BRANCH\",
  \"destination\": \"/home/ubuntu/app\"
}"

echo "Running tests..."
./vm-agent task ci-tester-$BRANCH '{
  "type": "test",
  "cwd": "/home/ubuntu/app",
  "command": "npm install && npm test"
}'

# 4. If tests pass, deploy
echo "Creating deployer..."
./vm-agent create ci-deployer-$BRANCH --profile deployer

# Copy build artifacts from builder to deployer
# (simplified - in reality you'd use file:read and file:write)

./vm-agent task ci-deployer-$BRANCH '{
  "type": "deploy",
  "command": "vercel --prod",
  "env": {"VERCEL_TOKEN": "xxx"}
}'

# 5. Cleanup
echo "Cleaning up..."
./vm-agent destroy ci-builder-$BRANCH --force
./vm-agent destroy ci-tester-$BRANCH --force
./vm-agent destroy ci-deployer-$BRANCH --force

echo "Pipeline complete!"
```

## Tips

1. **Profile Reuse:** Create profiles for your common workflows and reuse them across projects

2. **Resource Tuning:** Start with default resources, then adjust based on actual usage

3. **Snapshots:** Take snapshots after profile application for faster agent creation

4. **Credentials:** Never hard-code secrets in profiles - pass via task env vars

5. **Testing:** Test profiles on throwaway agents before using in production

6. **Monitoring:** Use `./vm-agent status <name> --watch` to monitor agent health

7. **Logs:** Always check logs after tasks: `./vm-agent logs <name> --lines 50`

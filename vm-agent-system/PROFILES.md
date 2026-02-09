# Agent Profiles & Project Templates

Agent profiles provide pre-configured contexts for specific use cases, making it easy to spin up specialized agents with all the right tools and configurations.

## Quick Start

### List Available Profiles
```bash
cd cli
./vm-agent-profiles list
```

### Create Agent from Profile
```bash
# Use built-in profile
./vm-agent create my-builder --profile builder

# Override profile resources
./vm-agent create my-builder --profile builder --cpu 8 --memory 16G
```

### View Profile Details
```bash
./vm-agent-profiles show builder
```

## Built-in Profiles

### 🏗️ Builder
**Purpose:** Build Node.js, React, and Next.js projects

**Pre-installed:**
- Node.js 18+ with npm, yarn, pnpm
- Vercel CLI
- PM2 process manager
- Git and build tools

**Use Cases:**
- Build Next.js applications
- Deploy to Vercel
- Create production bundles
- Run CI/CD pipelines

**Example:**
```bash
./vm-agent create my-builder --profile builder

# Clone and build
./vm-agent task my-builder '{
  "type": "git:clone",
  "repo": "https://github.com/user/project",
  "destination": "/home/ubuntu/workspace"
}'

./vm-agent task my-builder '{
  "type": "build",
  "cwd": "/home/ubuntu/workspace",
  "command": "npm install && npm run build"
}'
```

---

### 🧪 Tester
**Purpose:** Run automated tests (unit, E2E, API)

**Pre-installed:**
- Jest, Vitest test runners
- Playwright with browsers
- Chrome/Firefox headless
- Test reporting tools

**Use Cases:**
- Run test suites
- E2E testing with Playwright
- API testing
- Generate test reports

**Example:**
```bash
./vm-agent create my-tester --profile tester

# Run tests
./vm-agent task my-tester '{
  "type": "test",
  "cwd": "/home/ubuntu/project",
  "command": "npm test"
}'
```

---

### 🚀 Deployer
**Purpose:** Deploy applications to various platforms

**Pre-installed:**
- Vercel CLI
- AWS CLI
- Docker
- SSH tools

**Use Cases:**
- Deploy to Vercel
- Upload to S3/CloudFront
- Build and push Docker images
- SSH deployments

**Example:**
```bash
./vm-agent create my-deployer --profile deployer

# Deploy to Vercel
./vm-agent task my-deployer '{
  "type": "deploy",
  "cwd": "/home/ubuntu/app",
  "command": "vercel --prod --token $VERCEL_TOKEN",
  "env": {"VERCEL_TOKEN": "your-token"}
}'
```

---

### 🔍 Researcher
**Purpose:** Web scraping, data collection, analysis

**Pre-installed:**
- Puppeteer, Playwright
- Python with pandas, requests, BeautifulSoup
- Chrome headless
- Data processing tools

**Use Cases:**
- Scrape websites
- Collect data from APIs
- Process and analyze data
- Generate reports

**Example:**
```bash
./vm-agent create my-researcher --profile researcher

# Scrape data
./vm-agent task my-researcher '{
  "type": "script",
  "script": "const puppeteer = require(\"puppeteer\"); ...",
  "timeout": 600000
}'
```

---

### 🐳 Docker Host
**Purpose:** Run and manage Docker containers

**Pre-installed:**
- Docker Engine
- Docker Compose
- Container management tools

**Use Cases:**
- Build Docker images
- Run containers
- Docker Compose orchestration
- Container networking

**Example:**
```bash
./vm-agent create my-docker --profile docker-host

# Build and run container
./vm-agent task my-docker '{
  "type": "exec",
  "command": "docker build -t myapp . && docker run -p 3000:3000 myapp",
  "cwd": "/home/ubuntu/app"
}'
```

## Creating Custom Profiles

### From Scratch
```bash
./vm-agent-profiles create myprofile \
  --description "My custom agent" \
  --cpu 4 \
  --memory 8G \
  --disk 30G
```

### From JSON File
```json
{
  "name": "myprofile",
  "description": "Custom agent for X",
  "resources": {
    "cpu": 4,
    "memory": "8G",
    "disk": "30G"
  },
  "environment": {
    "API_KEY": "xxx",
    "ENV": "production"
  },
  "files": [
    {
      "path": "/home/ubuntu/config.json",
      "content": "{\"key\":\"value\"}"
    }
  ],
  "packages": ["git", "curl", "jq"],
  "setup_tasks": [
    {
      "type": "exec",
      "command": "npm install -g mypackage",
      "description": "Install global tools"
    }
  ]
}
```

```bash
./vm-agent-profiles create myprofile --from-file myprofile.json
```

## Profile Management

### Show Profile Details
```bash
./vm-agent-profiles show builder
```

Output:
```
📦 Profile: builder

Description: Agent optimized for building Node.js, React, and Next.js projects

Resources:
  CPU: 4
  Memory: 8G
  Disk: 30G

Environment Variables:
  NODE_ENV=production
  CI=true

System Packages:
  - git
  - curl
  - build-essential

Files to Create:
  - /home/ubuntu/.npmrc
  - /home/ubuntu/BUILD_INSTRUCTIONS.md

Setup Tasks:
  1. Install global Node.js tools
  2. Create working directories
```

### Delete Profile
```bash
./vm-agent-profiles delete myprofile --force
```

## Profile Structure Reference

```json
{
  "name": "string",          // Profile identifier
  "description": "string",   // Human-readable description
  
  "resources": {
    "cpu": "number",         // CPU cores
    "memory": "string",      // e.g., "4G", "8G"
    "disk": "string"         // e.g., "20G", "50G"
  },
  
  "environment": {
    "KEY": "value"           // Environment variables
  },
  
  "files": [
    {
      "path": "string",      // Absolute file path
      "content": "string"    // File contents
    }
  ],
  
  "packages": [
    "string"                 // apt package names
  ],
  
  "repositories": [
    {
      "url": "string",       // Git URL
      "destination": "string", // Clone destination
      "branch": "string"     // Optional branch
    }
  ],
  
  "setup_tasks": [
    {
      "type": "exec",        // Task type
      "command": "string",   // Command to run
      "description": "string" // Task description
    }
  ]
}
```

## Tips & Best Practices

1. **Resource Sizing:**
   - Builder: 4 CPU, 8GB RAM minimum
   - Tester: 2 CPU, 4GB RAM (browsers are memory-heavy)
   - Deployer: 2 CPU, 4GB RAM
   - Docker Host: 4 CPU, 8GB RAM + large disk

2. **Environment Variables:**
   - Store secrets in env vars, not files
   - Pass sensitive data via task payloads
   - Use .bashrc for persistent vars

3. **Setup Tasks:**
   - Order matters! Dependencies first
   - Add error handling (|| true)
   - Keep tasks idempotent

4. **File Paths:**
   - Use absolute paths
   - Create parent directories first
   - Set proper permissions

5. **Packages:**
   - Only install what's needed
   - Consider startup time vs. convenience
   - Test on fresh VM before adding to profile

## Example Workflows

### MonoClaw Blog Build
```bash
# Create builder agent
./vm-agent create blog-builder --profile builder

# Clone MonoClaw
./vm-agent task blog-builder '{
  "type": "git:clone",
  "repo": "https://github.com/rmruss2022/MonoClaw",
  "destination": "/home/ubuntu/MonoClaw"
}'

# Build blog
./vm-agent task blog-builder '{
  "type": "build",
  "cwd": "/home/ubuntu/MonoClaw/matts-claw-blog",
  "command": "npm install && npm run build"
}'

# Deploy
./vm-agent task blog-builder '{
  "type": "deploy",
  "cwd": "/home/ubuntu/MonoClaw/matts-claw-blog",
  "command": "vercel --prod",
  "env": {"VERCEL_TOKEN": "your-token"}
}'
```

### E2E Testing Pipeline
```bash
# Create tester agent
./vm-agent create e2e-tester --profile tester

# Clone project
./vm-agent task e2e-tester '{
  "type": "git:clone",
  "repo": "https://github.com/user/app",
  "destination": "/home/ubuntu/app"
}'

# Install dependencies
./vm-agent exec e2e-tester "cd app && npm install"

# Run Playwright tests
./vm-agent task e2e-tester '{
  "type": "test",
  "cwd": "/home/ubuntu/app",
  "command": "npx playwright test"
}'

# Get test results
./vm-agent task e2e-tester '{
  "type": "file:read",
  "filePath": "/home/ubuntu/app/test-results/report.html"
}'
```

---

**Need help?** Check the main README or open an issue on GitHub.

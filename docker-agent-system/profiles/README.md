# Agent Profiles

Pre-configured templates for different agent types. Each profile defines packages, environment variables, files, and setup tasks.

## Available Profiles

### builder
**Purpose:** Build Node.js, React, and Next.js projects

**Includes:**
- Node.js 18+ with npm, yarn, pnpm
- Git, build-essential
- Vercel CLI
- PM2 process manager

**Resources:** 4 CPU, 8G RAM, 30G disk

**Use for:** Building web applications, creating deployments, running builds

### tester
**Purpose:** Run automated tests and quality checks

**Includes:**
- Node.js 18+
- Jest, Mocha test frameworks
- Playwright for E2E testing
- ESLint, Prettier
- Chromium browser

**Resources:** 2 CPU, 4G RAM, 20G disk

**Use for:** Running test suites, E2E testing, code quality checks

### deployer
**Purpose:** Deploy applications to cloud platforms

**Includes:**
- Node.js 18+
- Vercel CLI
- SSH client
- rsync for file transfers

**Resources:** 2 CPU, 4G RAM, 20G disk

**Use for:** Deploying to Vercel, SSH deployments, artifact uploads

### researcher
**Purpose:** Data analysis and research tasks

**Includes:**
- Python 3.10+
- Jupyter Lab
- pandas, numpy, scipy
- matplotlib, seaborn
- scikit-learn
- Web scraping tools (requests, beautifulsoup4)

**Resources:** 4 CPU, 8G RAM, 40G disk

**Use for:** Data analysis, machine learning experiments, research

### docker-host
**Purpose:** Build and manage Docker containers (Docker-in-Docker)

**Includes:**
- Docker Engine
- Docker Compose
- Docker BuildKit

**Resources:** 4 CPU, 8G RAM, 50G disk

**Use for:** Building Docker images, running Docker Compose, container operations

**Note:** Requires privileged mode for Docker-in-Docker

## Profile Format

```json
{
  "name": "profile-name",
  "description": "What this profile is for",
  "resources": {
    "cpus": "2",
    "memory": "4g",
    "disk": "20g"
  },
  "environment": {
    "KEY": "value"
  },
  "files": [
    {
      "path": "/workspace/file.txt",
      "content": "File content here"
    }
  ],
  "packages": [
    "package1",
    "package2"
  ],
  "setup_tasks": [
    {
      "type": "exec",
      "command": "npm install -g some-tool",
      "description": "Install some tool"
    }
  ]
}
```

## Creating Custom Profiles

1. Copy an existing profile as template
2. Modify resources, packages, and setup tasks
3. Save as `<name>.json` in this directory
4. Test with: `docker-agent create test-agent --profile <name>`

### Example: Custom Python Data Science Profile

```json
{
  "name": "datascience",
  "description": "Advanced data science environment",
  "resources": {
    "cpus": "8",
    "memory": "16g",
    "disk": "100g"
  },
  "environment": {
    "PYTHONUNBUFFERED": "1"
  },
  "packages": [
    "python3",
    "python3-pip",
    "python3-dev",
    "build-essential"
  ],
  "setup_tasks": [
    {
      "type": "exec",
      "command": "pip3 install torch tensorflow keras transformers",
      "description": "Install ML frameworks"
    },
    {
      "type": "exec",
      "command": "pip3 install jupyterlab pandas numpy scipy matplotlib seaborn",
      "description": "Install data science tools"
    }
  ]
}
```

## Best Practices

1. **Start minimal**: Only include what you need
2. **Use volumes**: Store data in `/workspace`
3. **Pin versions**: Specify exact package versions for reproducibility
4. **Test thoroughly**: Create test agent before production use
5. **Document capabilities**: Add clear descriptions
6. **Set resource limits**: Prevent resource exhaustion
7. **Handle failures**: Use `|| true` for optional setup tasks
8. **Clean up**: Remove build artifacts in setup tasks

## Profile Tips

### For build agents
- Increase memory for large builds
- Include common build tools (make, g++, python)
- Add caching directories

### For test agents
- Include browsers for E2E tests
- Set CI environment variable
- Increase timeout for slow tests

### For data agents
- Increase disk for datasets
- Include scientific libraries
- Set Python unbuffered for real-time logs

### For deployment agents
- Include cloud CLIs (AWS, GCP, Azure)
- Add SSH keys via volumes
- Set deployment credentials via environment

## Troubleshooting

### Profile won't apply
```bash
# Check profile syntax
cat profiles/myprofile.json | jq

# Check provisioning logs
cat logs/provision-myagent.log
```

### Packages fail to install
```bash
# Test manually
docker run -it openclaw-agent-base /bin/bash
apt-get update && apt-get install -y <package>
```

### Setup task fails
```bash
# Check logs in container
docker logs openclaw-agent-myagent

# Run task manually
docker exec openclaw-agent-myagent <command>
```

## Resources

- [Profile Migration Guide](../docs/PROFILE_MIGRATION.md)
- [Docker Guide](../docs/DOCKER.md)
- [VM Profiles](../../vm-agent-system/profiles/)

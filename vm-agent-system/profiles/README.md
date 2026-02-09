# Agent Profiles & Project Templates

Profiles define pre-configured contexts for agents, including:
- Environment variables
- Files to create
- Repositories to clone
- Dependencies to install
- Initial setup tasks

## Profile Structure

```json
{
  "name": "builder",
  "description": "Agent configured for building Node.js/React projects",
  "resources": {
    "cpu": 4,
    "memory": "8G",
    "disk": "20G"
  },
  "environment": {
    "NODE_ENV": "production",
    "CI": "true"
  },
  "repositories": [
    {
      "url": "https://github.com/user/project",
      "destination": "/home/ubuntu/workspace",
      "branch": "main"
    }
  ],
  "files": [
    {
      "path": "/home/ubuntu/.npmrc",
      "content": "registry=https://registry.npmjs.org/"
    }
  ],
  "packages": [
    "git",
    "curl",
    "docker.io"
  ],
  "setup_tasks": [
    {
      "type": "exec",
      "command": "npm install -g vercel pm2"
    }
  ]
}
```

## Usage

```bash
# Create agent from profile
./vm-agent create my-builder --profile builder

# List available profiles
./vm-agent profiles list

# Create custom profile
./vm-agent profiles create myprofile --from-file profile.json

# Use profile with overrides
./vm-agent create my-agent --profile builder --cpu 8 --memory 16G
```

## Built-in Profiles

- **builder** - Node.js/React builds
- **tester** - Test automation
- **deployer** - Deployment operations
- **researcher** - Web scraping and data analysis
- **docker-host** - Docker container management

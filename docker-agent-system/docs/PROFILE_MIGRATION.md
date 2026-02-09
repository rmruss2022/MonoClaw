# Profile Migration Guide

Guide for migrating profiles from the VM-based system to Docker.

## Key Differences

### VM Profiles
- Use cloud-init for provisioning
- Full OS with systemd
- Persistent VMs
- SSH access
- ~2GB disk minimum

### Docker Profiles
- Use Dockerfile layers
- Minimal container runtime
- Ephemeral containers (data in volumes)
- Docker exec access
- ~500MB disk typical

## Migration Process

### 1. Analyze VM Profile

Example VM profile:
```json
{
  "name": "builder",
  "resources": {
    "cpu": 4,
    "memory": "8G",
    "disk": "30G"
  },
  "packages": ["git", "build-essential"],
  "setup_tasks": [
    {
      "type": "exec",
      "command": "npm install -g yarn",
      "description": "Install yarn"
    }
  ]
}
```

### 2. Create Docker Profile

Docker equivalent:
```json
{
  "name": "builder",
  "resources": {
    "cpus": "4",
    "memory": "8g",
    "disk": "30g"
  },
  "packages": ["git", "build-essential"],
  "setup_tasks": [
    {
      "type": "exec",
      "command": "npm install -g yarn",
      "description": "Install yarn"
    }
  ]
}
```

### 3. Handle Differences

**Systemd services → Container entrypoint:**
```json
// VM: systemd service
{
  "setup_tasks": [
    {
      "command": "systemctl enable myservice",
      "description": "Enable service"
    }
  ]
}

// Docker: Include in base image or use supervisor
{
  "setup_tasks": [
    {
      "command": "npm install -g pm2",
      "description": "Install process manager"
    }
  ]
}
```

**Persistent state:**
```json
// VM: Any location
{
  "files": [
    {
      "path": "/home/ubuntu/data/config.json",
      "content": "{...}"
    }
  ]
}

// Docker: Use /workspace for persistence
{
  "files": [
    {
      "path": "/workspace/config.json",
      "content": "{...}"
    }
  ]
}
```

## Common Patterns

### Database Agent

**VM approach:**
```json
{
  "packages": ["postgresql-14"],
  "setup_tasks": [
    {
      "command": "systemctl enable postgresql",
      "description": "Enable PostgreSQL"
    },
    {
      "command": "sudo -u postgres createdb mydb",
      "description": "Create database"
    }
  ]
}
```

**Docker approach:**
```json
{
  "packages": ["postgresql-client"],
  "setup_tasks": [
    {
      "command": "echo 'Use official postgres image or docker-compose'",
      "description": "Note: Use docker-compose for databases"
    }
  ]
}
```

Better: Use Docker Compose with official postgres image.

### Web Server Agent

**VM approach:**
```json
{
  "packages": ["nginx"],
  "setup_tasks": [
    {
      "command": "systemctl enable nginx",
      "description": "Enable nginx"
    }
  ]
}
```

**Docker approach:**
```dockerfile
# Extend base image
FROM openclaw-agent-base
RUN apt-get update && apt-get install -y nginx
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### Build Agent

**Works similarly in both:**
```json
{
  "name": "builder",
  "packages": ["git", "build-essential"],
  "setup_tasks": [
    {
      "command": "npm install -g yarn pnpm",
      "description": "Install package managers"
    }
  ]
}
```

## Dockerfile Optimization

For complex profiles, create a custom Dockerfile:

**profiles/builder.Dockerfile:**
```dockerfile
FROM openclaw-agent-base

# Install build tools
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    python3 \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js tools
RUN npm install -g yarn pnpm vercel pm2

# Create directories
RUN mkdir -p /workspace/builds /workspace/artifacts && \
    chown -R agent:agent /workspace

USER agent
```

Then update provisioning to use custom Dockerfile:
```bash
docker build -f profiles/builder.Dockerfile -t openclaw-agent-builder .
```

## Testing Migration

### 1. Create Test Agent

```bash
# VM version
vm-agent create test-vm --profile myprofile

# Docker version
docker-agent create test-docker --profile myprofile
```

### 2. Compare Capabilities

```bash
# VM
vm-agent exec test-vm "which node && node --version"
vm-agent exec test-vm "npm ls -g --depth=0"

# Docker
docker-agent exec test-docker "which node && node --version"
docker-agent exec test-docker "npm ls -g --depth=0"
```

### 3. Run Sample Task

```bash
# Both should produce same output
docker-agent task test-docker '{"type":"exec","command":"npm --version"}'
```

### 4. Check Resources

```bash
# VM
multipass info test-vm

# Docker
docker stats --no-stream openclaw-agent-test-docker
```

## Migration Checklist

- [ ] Identify all VM profiles to migrate
- [ ] Review packages and setup tasks
- [ ] Handle systemd services (convert to foreground processes)
- [ ] Move persistent data paths to /workspace
- [ ] Test each profile in Docker
- [ ] Verify hub connectivity
- [ ] Run sample tasks
- [ ] Check resource usage
- [ ] Update documentation
- [ ] Create custom Dockerfiles if needed

## Profile Compatibility Matrix

| Feature | VM | Docker | Notes |
|---------|----|----|-------|
| Packages | ✓ | ✓ | Same package names |
| Environment | ✓ | ✓ | Same format |
| Files | ✓ | ✓ | Use /workspace for persistence |
| Setup tasks | ✓ | ✓ | Same format |
| Systemd | ✓ | ✗ | Use process managers |
| SSH | ✓ | ✗ | Use docker exec |
| Snapshots | ✓ | ✓ | Different mechanism |
| GPU | ✓ | ✓ | Requires nvidia-docker |
| Nested virt | ✓ | ✗ | Use Docker-in-Docker |

## Examples

### Simple Profile (Works as-is)

```json
{
  "name": "nodejs",
  "packages": ["git", "curl"],
  "setup_tasks": [
    {
      "command": "npm install -g typescript",
      "description": "Install TypeScript"
    }
  ]
}
```

### Complex Profile (Needs Adaptation)

**VM version:**
```json
{
  "name": "database",
  "packages": ["postgresql-14", "redis-server"],
  "setup_tasks": [
    {
      "command": "systemctl enable postgresql redis",
      "description": "Enable services"
    }
  ]
}
```

**Docker version:**
Use docker-compose:
```yaml
services:
  agent:
    image: openclaw-agent-base
    depends_on:
      - postgres
      - redis
  
  postgres:
    image: postgres:14
    volumes:
      - pgdata:/var/lib/postgresql/data
  
  redis:
    image: redis:7
    volumes:
      - redisdata:/data
```

## Tips

1. **Start simple**: Migrate stateless profiles first
2. **Use official images**: Don't install databases in agent containers
3. **Leverage Docker Compose**: For multi-container setups
4. **Test thoroughly**: Docker behavior differs from VMs
5. **Document changes**: Note any behavioral differences
6. **Keep profiles DRY**: Use base images for common setups
7. **Version images**: Tag images with version numbers
8. **Monitor resources**: Docker agents use less memory but still need limits

## Troubleshooting

### Profile installation fails

```bash
# Check provisioning logs
cat ~/.openclaw/workspace/docker-agent-system/logs/provision-<name>.log

# Try manual installation
docker exec -it openclaw-agent-<name> /bin/bash
apt-get update && apt-get install -y <package>
```

### Missing system dependencies

```bash
# Add to profile packages
{
  "packages": ["build-essential", "python3", "make"]
}
```

### Setup task fails

```bash
# Add error handling
{
  "setup_tasks": [
    {
      "command": "npm install -g yarn || true",
      "description": "Install yarn (continue on failure)"
    }
  ]
}
```

## Resources

- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Dockerfile Reference](https://docs.docker.com/engine/reference/builder/)
- [VM Agent Profiles](../../vm-agent-system/profiles/)
- [Docker Agent Profiles](../profiles/)

# Docker-Specific Guide

This guide covers Docker-specific features, optimizations, and best practices for the OpenClaw Docker Agent System.

## Architecture

### Base Image Strategy

The system uses a layered approach:

1. **Base Image** (`openclaw-agent-base`): Minimal Node.js runtime
2. **Profile Images** (`openclaw-agent-<profile>`): Base + profile packages
3. **Agent Containers**: Profile image + specific configuration

This maximizes Docker layer caching for fast builds.

### Networking

**Host Access:**
- Agents connect to hub via `host.docker.internal`
- Works on Docker Desktop (Mac/Windows)
- Linux: requires `--add-host host.docker.internal:host-gateway`

**Custom Network:**
- Network: `openclaw-agents`
- Type: Bridge
- Isolation: Agents can't talk to each other by default
- Hub accessible from all agents

**External Access:**
- Agents can access internet by default
- Restrict with `--network none` for sensitive tasks

### Volumes

**Data Persistence:**
```bash
# Named volume per agent
openclaw-agent-<name>

# Mounted at /workspace in container
docker volume inspect openclaw-agent-myagent
```

**Volume Strategies:**

1. **Named volumes** (default): Managed by Docker
2. **Bind mounts**: For development
   ```bash
   docker run -v $(pwd):/workspace ...
   ```
3. **tmpfs**: For ephemeral data
   ```bash
   docker run --tmpfs /tmp:rw,noexec,nosuid,size=1g ...
   ```

### Resource Limits

**CPU:**
```bash
--cpus="2.0"          # 2 cores
--cpus="0.5"          # 50% of 1 core
--cpu-shares=1024     # Relative weight
```

**Memory:**
```bash
--memory="4g"         # 4GB limit
--memory-swap="6g"    # Swap limit (total)
--memory-reservation="2g"  # Soft limit
```

**Disk:**
```bash
--storage-opt size=30g     # Requires overlay2 driver
```

### Security

**User Isolation:**
- Agents run as non-root user (`agent`, UID 1000)
- Workspace owned by agent user
- Root access via sudo if needed (disable for production)

**Capabilities:**
```bash
# Drop all, add specific
--cap-drop=ALL
--cap-add=NET_BIND_SERVICE
--cap-add=SYS_TIME
```

**Read-only Filesystem:**
```bash
--read-only
--tmpfs /tmp:rw,noexec,nosuid,size=100m
--tmpfs /var/run:rw,noexec,nosuid,size=10m
```

**AppArmor/SELinux:**
```bash
--security-opt apparmor=docker-default
--security-opt label=type:container_runtime_t
```

## Docker Compose

Example `docker-compose.yml`:

```yaml
version: '3.8'

services:
  builder-1:
    image: openclaw-agent-builder
    container_name: openclaw-agent-builder-1
    networks:
      - openclaw
    volumes:
      - builder-1-data:/workspace
    environment:
      - AGENT_ID=builder-1
      - AGENT_TOKEN=${BUILDER_1_TOKEN}
      - HUB_URL=ws://host.docker.internal:9090
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G
    restart: unless-stopped
    
  tester-1:
    image: openclaw-agent-tester
    container_name: openclaw-agent-tester-1
    networks:
      - openclaw
    volumes:
      - tester-1-data:/workspace
    environment:
      - AGENT_ID=tester-1
      - AGENT_TOKEN=${TESTER_1_TOKEN}
      - HUB_URL=ws://host.docker.internal:9090
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
    restart: unless-stopped

networks:
  openclaw:
    driver: bridge

volumes:
  builder-1-data:
  tester-1-data:
```

## BuildKit

Enable BuildKit for faster builds:

```bash
export DOCKER_BUILDKIT=1
docker build --build-arg BUILDKIT_INLINE_CACHE=1 ...
```

**Multi-stage builds:**

```dockerfile
# Build stage
FROM openclaw-agent-base as builder
WORKDIR /build
RUN npm install production-deps

# Runtime stage
FROM openclaw-agent-base
COPY --from=builder /build/node_modules /app/node_modules
```

## Image Optimization

**Layer Caching:**
```dockerfile
# Bad: changes invalidate all subsequent layers
COPY . .
RUN npm install

# Good: dependencies cached separately
COPY package*.json ./
RUN npm install
COPY . .
```

**Multi-platform:**
```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t openclaw-agent-base .
```

**Squash layers:**
```bash
docker build --squash -t openclaw-agent-base .
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker logs openclaw-agent-<name>

# Inspect container
docker inspect openclaw-agent-<name>

# Try running manually
docker run -it --rm openclaw-agent-base /bin/bash
```

### Can't reach hub

```bash
# Test host connectivity
docker run --rm openclaw-agent-base \
  ping -c 3 host.docker.internal

# Check network
docker network inspect openclaw-agents

# Verify hub is running
curl http://localhost:9091/health
```

### Out of disk space

```bash
# Clean up unused resources
docker system prune -a --volumes

# Check disk usage
docker system df

# Remove specific volumes
docker volume rm openclaw-agent-<name>
```

### Permission issues

```bash
# Check volume ownership
docker exec openclaw-agent-<name> ls -la /workspace

# Fix permissions
docker exec -u root openclaw-agent-<name> \
  chown -R agent:agent /workspace
```

## Performance Tuning

### Build Speed

**Use BuildKit:**
```bash
export DOCKER_BUILDKIT=1
```

**Parallel builds:**
```bash
docker-compose build --parallel
```

**Local registry:**
```bash
docker run -d -p 5000:5000 --name registry registry:2
docker tag openclaw-agent-base localhost:5000/openclaw-agent-base
docker push localhost:5000/openclaw-agent-base
```

### Runtime Performance

**Adjust Docker daemon:**
```json
{
  "max-concurrent-downloads": 10,
  "max-concurrent-uploads": 10,
  "default-shm-size": "1G",
  "storage-driver": "overlay2"
}
```

**Use tmpfs for temp files:**
```bash
docker run --tmpfs /tmp:rw,noexec,nosuid,size=1g ...
```

**Pin to specific CPUs:**
```bash
docker run --cpuset-cpus="0-3" ...
```

## Production Deployment

### Swarm Mode

```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml openclaw

# Scale agents
docker service scale openclaw_builder=3

# Update service
docker service update --image openclaw-agent-base:v2 openclaw_builder
```

### Health Checks

Built into Dockerfile:
```dockerfile
HEALTHCHECK --interval=30s --timeout=3s \
  CMD node -e "console.log('healthy')" || exit 1
```

Check health:
```bash
docker inspect --format='{{.State.Health.Status}}' openclaw-agent-<name>
```

### Logging

**JSON logs:**
```bash
docker run --log-driver=json-file \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  ...
```

**External logging:**
```bash
# Fluentd
docker run --log-driver=fluentd \
  --log-opt fluentd-address=localhost:24224 \
  ...

# Syslog
docker run --log-driver=syslog \
  --log-opt syslog-address=tcp://192.168.1.1:514 \
  ...
```

### Monitoring

**Prometheus metrics:**
- Hub exposes metrics on port 9091
- Agents report health via hub
- Use Grafana for visualization

**cAdvisor:**
```bash
docker run -d \
  --name=cadvisor \
  --volume=/:/rootfs:ro \
  --volume=/var/run:/var/run:ro \
  --volume=/sys:/sys:ro \
  --volume=/var/lib/docker/:/var/lib/docker:ro \
  --publish=8080:8080 \
  google/cadvisor:latest
```

## Docker vs VM Comparison

| Aspect | Docker | VM (Multipass) |
|--------|--------|----------------|
| Startup | <5s | ~60s |
| Memory overhead | ~50MB | ~512MB |
| Disk overhead | ~500MB | ~2GB |
| Isolation | Process + namespace | Full VM |
| Kernel | Shared | Isolated |
| Networking | Bridge/overlay | NAT |
| Snapshots | Layer commits | Full disk |
| Portability | Very high | Medium |
| Security | Good | Excellent |

**When to use Docker:**
- Fast iteration needed
- Running many agents
- Limited resources
- Trusted code

**When to use VMs:**
- Maximum isolation required
- Untrusted code
- Kernel-level changes needed
- Full OS simulation

## Advanced Topics

### GPU Support

```bash
# Requires nvidia-docker2
docker run --gpus all openclaw-agent-base nvidia-smi
```

### Custom Networks

```bash
# Create isolated network
docker network create \
  --driver bridge \
  --subnet 172.20.0.0/16 \
  --gateway 172.20.0.1 \
  openclaw-isolated

# Connect container
docker network connect openclaw-isolated openclaw-agent-<name>
```

### Secrets Management

```bash
# Docker secrets (swarm mode)
echo "secret-token" | docker secret create agent_token -

# Use in service
docker service create \
  --secret agent_token \
  openclaw-agent-base
```

### Resource Monitoring

```bash
# Real-time stats
docker stats openclaw-agent-<name>

# Historical data
docker inspect openclaw-agent-<name> \
  | jq '.[0].State.Stats'
```

## Best Practices

1. **Always use named volumes** for data persistence
2. **Pin base image versions** for reproducibility
3. **Run as non-root user** for security
4. **Use health checks** for reliability
5. **Set resource limits** to prevent resource exhaustion
6. **Enable BuildKit** for faster builds
7. **Use multi-stage builds** to reduce image size
8. **Clean up regularly** with `docker system prune`
9. **Monitor container metrics** for optimization
10. **Test with limited resources** before production

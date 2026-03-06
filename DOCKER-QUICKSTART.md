# Docker-Compose Quick Start

## 🚀 Start All Services

```bash
cd ~/.openclaw/workspace
docker-compose up -d
```

## 📊 View Status

```bash
# View all running containers
docker-compose ps

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f command-hub-api
```

## 🔄 Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart command-hub-api
```

## 🛑 Stop Services

```bash
# Stop all
docker-compose down

# Stop but keep containers
docker-compose stop
```

## 🔧 Rebuild After Changes

```bash
docker-compose down
docker-compose build
docker-compose up -d
```

## 🌐 Access from iPhone

With Tailscale running, access via:

```
http://openclaw-hub:3001/api/health    # Backend API
http://openclaw-hub:3000/              # Frontend (when built)
http://openclaw-hub:18795/             # Mission Control
http://openclaw-hub:18796/             # Activity Hub
http://openclaw-hub:18802/             # MonoClaw
http://openclaw-hub:3003/              # Jobs
http://openclaw-hub:3004/              # Raves
```

## 📱 iPhone ACL (Already Applied)

Your iPhone (`100.104.4.13` / `matthew-iphone`) is whitelisted for:
- Ports 18790-18802
- Ports 3000-3005

## ⚙️ Tailscale Commands

```bash
# Check status
tailscale status

# Test iPhone connection
tailscale ping matthew-iphone

# Get your IP
tailscale ip -4

# View ACLs
tailscale configure acls get
```

## 🐛 Troubleshooting

### Service won't start
```bash
docker-compose logs service-name
```

### Can't connect from iPhone
```bash
# Verify Tailscale is running
tailscale status

# Test from MacBook
curl http://100.107.120.47:3001/api/health

# Check ACL
cat ~/.openclaw/workspace/tailscale-acl-fixed.json
```

### Need to restart everything
```bash
docker-compose down
docker-compose up -d
docker-compose logs -f
```

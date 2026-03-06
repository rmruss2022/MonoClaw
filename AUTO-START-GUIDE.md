# OpenClaw Auto-Start Setup

## ✅ Docker-Compose Auto-Start Configured

### What Was Created

**LaunchAgent:** `~/Library/LaunchAgents/com.openclaw.docker-compose.plist`

This runs `docker-compose up -d` automatically when your MacBook boots.

### Status Check

```bash
# Check if LaunchAgent is loaded
launchctl list | grep docker-compose

# View logs
tail -f ~/.openclaw/logs/docker-compose.log
tail -f ~/.openclaw/logs/docker-compose.err.log
```

### Manual Control

```bash
# Unload (disable auto-start)
launchctl unload ~/Library/LaunchAgents/com.openclaw.docker-compose.plist

# Load (enable auto-start)
launchctl load ~/Library/LaunchAgents/com.openclaw.docker-compose.plist

# Restart
launchctl unload ~/Library/LaunchAgents/com.openclaw.docker-compose.plist
launchctl load ~/Library/LaunchAgents/com.openclaw.docker-compose.plist
```

---

## 🌐 Command Hub Integration

### Main Hub URL

**Mission Control:** http://localhost:18795/hub

All services are now integrated into the hub dashboard!

### New Services Added

1. **Command Hub API** (Port 3001)
   - Backend API for service monitoring
   - Real-time SSE updates
   - Link: http://openclaw-hub:3001/api/health

2. **Jobs Dashboard** (Port 3003)
   - Job application tracking
   - Link: http://openclaw-hub:3003

3. **Raves Dashboard** (Port 3004)
   - NYC events and raves
   - Link: http://openclaw-hub:3004

4. **Arbitrage Scanner** (Port 3005)
   - Prediction market arbitrage detection
   - Link: http://openclaw-hub:3005/dashboard.html

### Existing Services

- Voice Server (18790)
- Token Tracker (18791)
- Context Manager (18792/18800)
- Mission Control (18795)
- Activity Hub (18796)
- MonoClaw Dashboard (18802)
- Agent Swarm Dashboard (18798)
- Vision Controller (18799)

---

## 🚀 Boot Sequence

When your MacBook starts:

1. ✅ **macOS boots** → System loads
2. ✅ **Tailscale starts** (via its own LaunchAgent)
3. ✅ **OpenClaw Gateway starts** (via com.openclaw.gateway LaunchAgent)
4. ✅ **Docker-Compose starts** (via com.openclaw.docker-compose LaunchAgent)
   - Starts all dashboard containers
   - Backend API
   - Frontend (when ready)
5. ✅ **Mission Control starts** (via LaunchAgent)
6. ✅ **Other services start** (Voice, Activity Hub, etc.)

### Check Boot Status

```bash
# View all OpenClaw LaunchAgents
launchctl list | grep openclaw

# Expected output:
# com.openclaw.gateway
# com.openclaw.docker-compose
# com.openclaw.mission-control
# com.openclaw.voice-server
# ... etc
```

---

## 📱 Access from iPhone

Once everything boots, access via Tailscale:

```
http://openclaw-hub:18795/hub     ← Main hub with all services
http://openclaw-hub:3001/api/health
http://openclaw-hub:3003/
http://openclaw-hub:3004/
```

---

## 🐳 Docker Services (Auto-Started)

The following run via Docker:

- command-hub-api (Port 3001)
- command-hub-ui (Port 3000) - when UI is built
- mission-control (Port 18795)
- activity-hub (Port 18796)
- monoclaw (Port 18802)
- raves (Port 3004)
- jobs (Port 3003)

### Docker Commands

```bash
# View running containers
docker-compose ps

# View logs
docker-compose logs -f

# Restart all
docker-compose restart

# Stop all
docker-compose down

# Start all
docker-compose up -d
```

---

## 🛠️ Troubleshooting

### Docker-Compose Not Starting

```bash
# Check LaunchAgent logs
tail -50 ~/.openclaw/logs/docker-compose.err.log

# Manually run to see errors
cd ~/.openclaw/workspace
docker-compose up
```

### Services Not Showing in Hub

```bash
# Restart Mission Control
pkill -f mission-control
cd ~/.openclaw/workspace/mission-control
node server.js &
```

### Can't Access from iPhone

```bash
# Verify Tailscale
tailscale status

# Test locally first
curl http://localhost:18795/hub

# Test via Tailscale IP
curl http://100.107.120.47:18795/hub
```

---

## 📊 Complete Service Map

| Service | Port | Status | Access |
|---------|------|--------|--------|
| OpenClaw Gateway | 18789 | Native | System |
| Voice Server | 18790 | Native | http://openclaw-hub:18790 |
| Token Tracker | 18791 | Native | http://openclaw-hub:18791 |
| Context Manager | 18792 | Native | http://openclaw-hub:18792 |
| Mission Control | 18795 | Docker | http://openclaw-hub:18795 |
| Activity Hub | 18796 | Docker | http://openclaw-hub:18796 |
| MonoClaw | 18802 | Docker | http://openclaw-hub:18802 |
| Command Hub API | 3001 | Docker | http://openclaw-hub:3001 |
| Jobs Dashboard | 3003 | Docker | http://openclaw-hub:3003 |
| Raves Dashboard | 3004 | Docker | http://openclaw-hub:3004 |
| Arbitrage Scanner | 3005 | Native | http://openclaw-hub:3005 |

**Native** = Runs via LaunchAgent (always on)  
**Docker** = Runs via docker-compose (starts on boot)

---

## ✨ Summary

**You now have:**
- ✅ Docker-compose auto-starts on boot
- ✅ All services integrated into Mission Control hub
- ✅ Tailscale remote access from iPhone
- ✅ Single command to manage all services
- ✅ Automatic database backups (daily 2 AM)

**Access Everything:**
```
http://openclaw-hub:18795/hub
```

**Manage Services:**
```bash
docker-compose ps              # View status
docker-compose logs -f         # View logs
docker-compose restart service # Restart one
```

**Next:** Build React dashboard UI for http://openclaw-hub:3000

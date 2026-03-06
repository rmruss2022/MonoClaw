# OpenClaw Services Status

## ✅ Native Services Running (LaunchAgents)

These are **already running** via macOS LaunchAgents:

```
✅ OpenClaw Gateway (ai.openclaw.gateway)
✅ Voice Server (18790) - com.openclaw.voice-server
✅ Mission Control (18795) - com.openclaw.mission-control
✅ Token Tracker (18791) - com.openclaw.token-tracker
✅ Job Dashboard (18791) - com.openclaw.job-dashboard
✅ Raves Dashboard (18793) - com.openclaw.raves-dashboard
✅ Activity Hub (18796) - com.openclaw.activity-hub
✅ MonoClaw Dashboard (18802) - com.openclaw.monoclaw-dashboard
✅ Moltbook Dashboard - com.openclaw.moltbook-dashboard
✅ Context Manager - com.openclaw.context-manager
✅ Activity Tracker - com.openclaw.activity-tracker
✅ Database Backup - com.openclaw.database-backup
```

**Test them:**
```bash
curl http://localhost:18790/health   # Voice ✅
curl http://localhost:18795/         # Mission Control ✅
curl http://localhost:3001/api/health # Command Hub API ✅
```

**From iPhone:**
```
http://openclaw-hub:18790/health
http://openclaw-hub:18795/hub
http://openclaw-hub:3001/api/health
```

---

## 🐳 Docker Compose Status

**Currently:** Pulling images (first time setup, takes 2-5 min)

Docker containers are **optional** - everything already works via LaunchAgents!

### Why Use Docker?

**Pros:**
- Easy to manage with one command
- Consistent environment
- Easy to restart/rebuild

**Cons:**
- Requires Docker Desktop running
- Takes more resources
- Longer startup time

**Your Choice:** Since LaunchAgents are working, you can:

1. **Keep using LaunchAgents** (current, working)
2. **Use Docker** (optional, still setting up)
3. **Use both** (mix and match)

---

## 🎯 Recommended: Keep LaunchAgents

**Why:**
- ✅ Already configured and running
- ✅ Start on boot automatically
- ✅ Lower resource usage
- ✅ No Docker Desktop needed
- ✅ Faster startup

**Docker-compose is optional** - you already have everything working!

---

## 📱 Access Everything Now

**From MacBook:**
```
http://localhost:18795/hub    # Mission Control
```

**From iPhone:**
```
http://openclaw-hub:18795/hub
```

All services are accessible via Tailscale right now! 🎉

# ⚠️ IMPORTANT: Docker Setup Required

## Docker Desktop Not Running

The auto-start LaunchAgent is configured, but **Docker Desktop needs to be running** for containers to start.

### Quick Fix

**Option 1: Start Docker Desktop Now**
```bash
open -a "Docker"
```

Wait 30 seconds for Docker to fully start, then:
```bash
cd ~/.openclaw/workspace
docker compose up -d
```

**Option 2: Set Docker Desktop to Auto-Start**

1. Open Docker Desktop
2. Go to **Settings** → **General**
3. Check ✅ **Start Docker Desktop when you log in**
4. Click **Apply & Restart**

Now Docker will start automatically on boot!

---

## Verify Everything Works

After Docker starts:

```bash
# Check Docker is running
docker ps

# Start services
cd ~/.openclaw/workspace
docker compose up -d

# Check status
docker compose ps

# Test from iPhone
# Open Safari: http://openclaw-hub:18795/hub
```

---

## Alternative: Use Native Services Only

If you prefer not to use Docker, all services can run natively via LaunchAgents.

They're already configured and running:
- Voice Server (18790) ✅
- Mission Control (18795) ✅
- Token Tracker (18791) ✅
- Activity Hub (18796) ✅
- etc.

The Docker setup is **optional** - everything works without it.

---

## Summary

**With Docker (Recommended):**
- ✅ Easy to manage (one command)
- ✅ Consistent environment
- ✅ Easy to restart/rebuild

**Without Docker (Current):**
- ✅ Already running via LaunchAgents
- ✅ No Docker Desktop needed
- ✅ Lower resource usage

**Your choice!** Both work fine.

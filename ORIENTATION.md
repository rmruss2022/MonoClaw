# 🦞 Welcome to Ora Health

**Your AI-Powered Wellness Command Center**

This workspace powers **Ora Health** - a locally-hosted AI wellness platform.

---

## Quick Links

| Resource | Location |
|----------|----------|
| **Command Hub** | http://localhost:18795/hub |
| **Mission Control** | http://localhost:18795 |
| **Documentation** | `/Users/matthew/Desktop/Feb26/ORA-HEALTH.md` |

---

## Dashboards

- 🎯 **Job Tracker** - http://localhost:18791
- 🎵 **NYC Raves** - http://localhost:18793  
- 🚀 **Mission Control** - http://localhost:18795
- 🔊 **Voice Server** - http://localhost:18790/status

---

## Daily Use

### Morning Check-In
```
📅 Calendar (gcalcli)
🏃 Health check (auto-runs every 5 min)
🎯 Job status
💬 Pending messages
```

### Voice Commands
All responses automatically speak via Edge TTS at `127.0.0.1:18790`

### Model Management
Current: `nvidia/moonshotai/kimi-k2.5`
Switch at: http://localhost:18795

---

## File Organization

```
workspace/
├── mission-control/    # System dashboard
├── jobs/              # Job search tracker
├── raves/             # Event recommendations
├── skills/            # Custom OpenClaw skills
└── memory/            # Daily notes & logs
```

---

## Key Files

- `AGENTS.md` - Agent rules & heartbeat tasks
- `SOUL.md` - AI personality & boundaries
- `TOOLS.md` - Voice server config
- `MEMORY.md` - Long-term notes (main session only)

---

**Start here:** http://localhost:18795/hub

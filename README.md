# Matt's Claw Workspace 🦞

**Monorepo for all OpenClaw projects, dashboards, and automation systems.**

## 🏗️ Projects

### Dashboards
- **`jobs/`** - Job search tracker (port 18791)
- **`raves/`** - NYC rave events dashboard (port 18793)
- **`tokens/`** - Token usage tracker with charts (port 18794)
- **`mission-control/`** - Command Hub system monitor (port 18795)
- **`activity-hub/`** - Activity feed & search (port 18796)
- **`moltbook-dashboard/`** - Moltbook social feed (port 18797)

### Sites
- **`matts-claw-blog/`** - Next.js blog deployed to Vercel
  - Live at: https://matts-claw-blog.vercel.app
  - Daily automated posts at 11:59 PM EST

### Core Files
- **`AGENTS.md`** - Agent system instructions
- **`SOUL.md`** - Personality and behavior guidelines
- **`USER.md`** - User context and preferences
- **`TOOLS.md`** - Local configuration notes
- **`IDENTITY.md`** - Who I am
- **`HEARTBEAT.md`** - Periodic task checklist
- **`DAY3-PLAN.md`** - Current day's objectives

### Scripts
- **`health-check.sh`** - Centralized service health monitoring (cron every 5 min)
- **`memory/`** - Daily memory files (YYYY-MM-DD.md)
- **`skills/`** - Custom OpenClaw skills

## 🤖 Services

All services run via LaunchAgents and auto-start on boot:

| Service | Port | LaunchAgent |
|---------|------|-------------|
| Gateway | 18789 | com.openclaw.gateway |
| Voice Server | 18790 | com.openclaw.voice-server |
| Job Dashboard | 18791 | com.openclaw.job-dashboard |
| Raves | 18793 | com.openclaw.raves-dashboard |
| Token Tracker | 18794 | com.openclaw.token-tracker |
| Mission Control | 18795 | com.openclaw.mission-control |
| Activity Hub | 18796 | com.openclaw.activity-hub |
| Moltbook | 18797 | com.openclaw.moltbook-dashboard |

## 🔄 Automation

**Cron Jobs:**
- 8:00 AM - Morning news briefing (Telegram + TTS)
- 9:00 AM - Daily security audit (Kimi K2.5)
- Hourly - Token usage data collection
- Every 5 min - Centralized health check
- 11:59 PM - Blog post generation & deployment

## 🛠️ Tech Stack

- **Runtime:** Node.js v22.22.0
- **Language:** JavaScript/TypeScript
- **Frameworks:** Next.js 14, Express
- **Databases:** JSON files, Convex (Activity Hub)
- **Deployment:** Vercel (blog), Local (dashboards)
- **Monitoring:** Custom health checks + LaunchAgents

## 📦 Setup

```bash
# Install dependencies for all projects
npm install --prefix jobs
npm install --prefix raves
npm install --prefix tokens
npm install --prefix mission-control
npm install --prefix activity-hub
npm install --prefix moltbook-dashboard
npm install --prefix matts-claw-blog
```

## 🚀 Development

Each dashboard runs independently:

```bash
# Job tracker
cd jobs && node server.js

# Raves dashboard
cd raves && node server.js

# Token tracker
cd tokens && node server.js

# Mission Control
cd mission-control && node server.js

# Activity Hub
cd activity-hub && npm run dev

# Moltbook
cd moltbook-dashboard && node server.js

# Blog (dev)
cd matts-claw-blog && npm run dev
```

## 📝 Daily Workflow

1. **8:00 AM** - Automated news briefing arrives via Telegram
2. **9:00 AM** - Security audit runs (Kimi K2.5)
3. **Throughout day** - Work on projects, track in memory files
4. **11:59 PM** - Blog post auto-generated from daily memories
5. **Continuous** - Health checks keep all services running

## 🦞 About

Built by **Claw** (AI assistant) and **Matthew** starting Feb 6, 2026.

This workspace represents 3 days of autonomous development: system monitoring, automation, dashboards, security audits, and self-documentation.

---

**Live Blog:** [matts-claw-blog.vercel.app](https://matts-claw-blog.vercel.app)  
**Created:** 2026-02-06  
**Updated:** 2026-02-07

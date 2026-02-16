# OpenClaw Plugin Announcements

## ActivityClaw - Real-time Activity Tracking

🦞 **Introducing ActivityClaw** - Real-time activity tracking and visualization for OpenClaw agents!

**What it does:**
- 📊 Tracks all agent activities in real-time (file ops, commands, web, messages)
- 🎨 Beautiful dashboard with live activity feed
- 🤖 Multi-agent support (main + sub-agents)
- 🔍 Filter by activity type
- 📈 Activity statistics and trends
- ⚡ Event-driven (no polling lag)

**Installation:**
```bash
npm install -g @rmruss2022/activityclaw
openclaw plugins install @rmruss2022/activityclaw
openclaw activityclaw dashboard
```

**Dashboard:** http://localhost:18796

**Links:**
- GitHub: https://github.com/rmruss2022/ActivityClaw
- npm: https://www.npmjs.com/package/@rmruss2022/activityclaw

**Features:**
- Real-time tracking via `tool_result_persist` hook
- Color-coded activities by type
- Auto-refresh dashboard (5s intervals)
- SQLite storage (all local, privacy-first)
- Full CLI suite

Perfect for monitoring what your agent is doing, debugging workflows, and tracking activity history!

---

## ContextClaw - Session & Context Management

🦞 **Introducing ContextClaw** - Session analysis, context management, and storage optimization for OpenClaw!

**What it does:**
- 📊 Deep session analysis (messages, tokens, storage per session)
- 🧹 Smart pruning of old sessions (age-based, type-aware)
- 🗑️ Orphan cleanup (removes sessions not in sessions.json)
- 📈 Visual dashboard with size distribution charts
- 🔍 Find largest/oldest sessions
- 📉 Track and reduce context window usage

**Installation:**
```bash
npm install -g @rmruss2022/contextclaw
openclaw plugins install @rmruss2022/contextclaw
openclaw contextclaw analyze
```

**Dashboard:** http://localhost:18797

**Links:**
- GitHub: https://github.com/rmruss2022/ContextClaw
- npm: https://www.npmjs.com/package/@rmruss2022/contextclaw

**Features:**
- Comprehensive session analysis with tables
- Safe pruning (dry-run first, protects main/cron)
- Orphaned session detection
- Token estimation per session
- Bar charts and visualizations
- CLI + web dashboard

Perfect for keeping your OpenClaw workspace clean, optimizing storage, and managing context consumption!

---

## Combined Announcement

🦞 **Two New OpenClaw Plugins Released!**

I've built and published two complementary plugins for the OpenClaw community:

**🎯 ActivityClaw** - Real-time activity tracking
Track every file operation, command, web search, and message your agent performs. Beautiful dashboard with live feed and filtering.

**🧹 ContextClaw** - Session and context management
Analyze session storage, prune old sessions, clean orphaned files, and visualize token usage. Keep your workspace lean and efficient.

Both plugins are:
- ✅ Production-ready
- ✅ MIT licensed
- ✅ Full CLI + web dashboards
- ✅ Privacy-first (all local)
- ✅ Open source on GitHub

**Install:**
```bash
# ActivityClaw (port 18796)
npm install -g @rmruss2022/activityclaw
openclaw plugins install @rmruss2022/activityclaw

# ContextClaw (port 18797)
npm install -g @rmruss2022/contextclaw
openclaw plugins install @rmruss2022/contextclaw
```

**GitHub:**
- https://github.com/rmruss2022/ActivityClaw
- https://github.com/rmruss2022/ContextClaw

**Companion skills** for teaching agents how to use these plugins will be published to ClawHub soon!

Feedback and contributions welcome! 🦞

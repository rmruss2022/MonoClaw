# 🦞 Activity Hub

**Real-time activity tracking, cron calendar, and workspace search for OpenClaw**

Activity Hub is a comprehensive dashboard that tracks every action in your OpenClaw workspace, displays your cron job schedule, and provides fast search across all your files.

## Features

### 📊 Activity Feed
- Real-time logging of all workspace activities
- Activity types: file, command, build, system, cron, message
- Filterable by type and date range
- Live updates via API polling (Convex real-time coming soon)

### 📅 Calendar View
- Visual display of all cron jobs
- Shows schedule, status, and next run time
- Syncs with OpenClaw Gateway
- Status indicators: active, scheduled, disabled

### 🔍 Global Search
- Fast full-text search across workspace
- Searches: MEMORY.md, daily memories, workspace docs, activities
- Context snippets with highlighted matches
- Filter by source and type

## Quick Start

### Development
```bash
npm run dev
# Opens on http://localhost:18796
```

### Production
```bash
npm run build
npm start
# Runs as production server on port 18796
```

### LaunchAgent (Auto-start on boot)
```bash
# LaunchAgent already created at:
# ~/Library/LaunchAgents/com.openclaw.activity-hub.plist

launchctl load ~/Library/LaunchAgents/com.openclaw.activity-hub.plist
launchctl start com.openclaw.activity-hub
```

## API Endpoints

### Activity Logging
```bash
# Log an activity
curl -X POST http://localhost:18796/api/activity/log \
  -H "Content-Type: application/json" \
  -d '{
    "action": "Created new dashboard",
    "type": "system",
    "metadata": {
      "path": "/dashboard.html",
      "status": "complete"
    }
  }'

# Or use the helper script
./scripts/log-activity.js "action" "type" '{"key":"value"}'
```

### Cron Jobs
```bash
# List all cron jobs
curl http://localhost:18796/api/cron/list

# Sync cron jobs from OpenClaw Gateway
node scripts/sync-cron-jobs.js
```

### Search
```bash
# Search workspace
curl "http://localhost:18796/api/search/query?q=activity+hub"
```

## Integration

### Auto-logging Activities

To automatically log activities from your workspace:

#### From shell scripts:
```bash
#!/bin/bash
node /Users/matthew/.openclaw/workspace/activity-hub/scripts/log-activity.js \
  "Health check completed" "system" '{"services": 5, "status": "ok"}'
```

#### From OpenClaw cron jobs:
Add logging to your cron job payloads:
```javascript
{
  "kind": "agentTurn",
  "message": "Run task... then log: node /path/to/log-activity.js 'Task completed' 'cron'"
}
```

#### From Node.js:
```javascript
const { logActivity } = require('./scripts/log-activity');
await logActivity('Built new feature', 'build', { loc: 500 });
```

## Tech Stack

- **Frontend:** Next.js 14, TypeScript, Tailwind CSS
- **Database:** Convex (coming soon for real-time sync)
- **APIs:** Next.js API routes
- **Integration:** OpenClaw Gateway API
- **Port:** 18796

## File Structure

```
activity-hub/
├── app/
│   ├── api/
│   │   ├── activity/
│   │   │   └── log/route.ts       # Activity logging endpoint
│   │   ├── cron/
│   │   │   └── list/route.ts      # Cron jobs API
│   │   └── search/
│   │       └── query/route.ts     # Search endpoint
│   ├── globals.css
│   ├── layout.tsx
│   └── page.tsx                   # Main UI (Feed, Calendar, Search)
├── convex/
│   ├── schema.ts                  # Convex database schemas
│   ├── activities.ts              # Activity mutations/queries
│   ├── cronJobs.ts                # Cron job sync
│   └── search.ts                  # Search functions
├── data/
│   └── cron-jobs.json             # Cached cron data
├── scripts/
│   ├── log-activity.js            # Activity logging helper
│   └── sync-cron-jobs.js          # Cron sync script
└── README.md
```

## Activity Types

| Type | Description | Examples |
|------|-------------|----------|
| `file` | File system operations | Created, modified, deleted files |
| `command` | Shell commands | exec calls, scripts run |
| `build` | Build/deployment | npm build, service restart |
| `system` | System events | Health checks, service status |
| `cron` | Cron job executions | Scheduled tasks run |
| `message` | Messages sent | Telegram, Discord, etc. |

## Roadmap

- [x] Activity feed with mock data
- [x] Calendar view with real cron jobs
- [x] Global search across workspace
- [x] Activity logging API
- [x] LaunchAgent for production
- [ ] Convex real-time database
- [ ] Live activity updates
- [ ] Weekly calendar grid view
- [ ] Activity statistics and charts
- [ ] Export/backup features
- [ ] Integration with more OpenClaw events

## Maintenance

### Sync Cron Jobs
Run periodically to keep cron data fresh:
```bash
node scripts/sync-cron-jobs.js
```

### Clear Old Activities
When Convex is set up, old activities can be cleaned:
```bash
# Keep last 30 days
# (function available in convex/activities.ts)
```

### Logs
- **stdout:** `activity-hub.log`
- **stderr:** `activity-hub-error.log`

## Integration with Command Hub

Add Activity Hub to Command Hub services section:

```html
<div class="service-card" style="--service-color: #a29bfe;">
  <a href="http://localhost:18796" target="_blank">
    <div class="service-icon">🦞</div>
    <div class="service-name">Activity Hub</div>
    <div class="service-status" data-url="http://localhost:18796/api/cron/list"></div>
  </a>
</div>
```

---

**Built with 🦞 by Matt's Claw**

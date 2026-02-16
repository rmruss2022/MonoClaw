# Activity Tracker OpenClaw Plugin

## Overview
Ship Activity Hub as an installable OpenClaw plugin that provides real-time monitoring and visualization of agent activities across all sessions.

## Repository Structure

```
ActivityClaw/
├── package.json              # Plugin metadata + openclaw extensions
├── tsconfig.json            # TypeScript config
├── openclaw.plugin.json     # Optional plugin manifest
├── README.md                # Installation & usage
├── LICENSE                  # MIT
├── src/
│   ├── index.ts            # Main plugin entry (registers hooks, tools, commands)
│   ├── tracker.ts          # Core tracking logic (transcript polling)
│   ├── server.ts           # Dashboard API server
│   ├── cli/
│   │   ├── setup.ts        # Interactive setup wizard
│   │   ├── status.ts       # Show tracker status
│   │   └── start.ts        # Start/stop commands
│   └── hooks/
│       └── activity.ts     # Hook registration for tool_result_persist
├── dashboard/
│   ├── public/
│   │   ├── index.html      # Dashboard UI (standalone HTML/JS)
│   │   ├── app.js          # Frontend logic
│   │   └── styles.css      # Styling
│   └── server/
│       └── api.js          # Express server for activity logging
├── skills/
│   └── SKILL.md            # Optional: Activity analysis skill
└── dist/                   # Compiled output (gitignored)
```

## Plugin Entry Point (src/index.ts)

```typescript
import { Plugin, PluginContext } from '@openclaw/types';
import { registerActivityHook } from './hooks/activity';
import { setupCommand } from './cli/setup';
import { statusCommand } from './cli/status';
import { startCommand, stopCommand } from './cli/start';

export default function ActivityClawPlugin(context: PluginContext): Plugin {
  return {
    name: 'activityclaw',
    version: '1.0.0',
    
    // Register hooks
    hooks: {
      'tool_result_persist': registerActivityHook(context)
    },
    
    // Register CLI commands
    commands: {
      'setup': setupCommand,
      'status': statusCommand,
      'start': startCommand,
      'stop': stopCommand,
    },
    
    // Optional: Register tools
    tools: {
      'activity_search': {
        description: 'Search recent agent activities',
        parameters: {
          query: { type: 'string', description: 'Search query' },
          limit: { type: 'number', default: 10 }
        },
        handler: async (params) => {
          // Query SQLite database for activities
        }
      }
    }
  };
}
```

## Package.json

```json
{
  "name": "@rmruss2022/activityclaw",
  "version": "1.0.0",
  "description": "Real-time activity tracking and visualization for OpenClaw agents",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "bin": {
    "activityclaw": "./dist/cli/index.js"
  },
  "files": [
    "dist",
    "dashboard",
    "skills",
    "openclaw.plugin.json"
  ],
  "scripts": {
    "build": "tsc",
    "dev": "tsc --watch",
    "prepublishOnly": "npm run build"
  },
  "openclaw": {
    "extensions": [
      "./dist/index.js"
    ]
  },
  "keywords": [
    "openclaw",
    "activity",
    "monitoring",
    "dashboard",
    "visualization"
  ],
  "author": "Matthew Russell",
  "license": "MIT",
  "repository": {
    "type": "git",
    "url": "https://github.com/rmruss2022/ActivityClaw"
  },
  "dependencies": {
    "express": "^4.18.2",
    "better-sqlite3": "^9.3.0",
    "chalk": "^5.3.0",
    "inquirer": "^9.2.12"
  },
  "devDependencies": {
    "@types/node": "^20.10.0",
    "@types/express": "^4.17.21",
    "typescript": "^5.3.3"
  }
}
```

## Installation Flow

```bash
# From npm (after publishing)
npm install -g @rmruss2022/activityclaw
openclaw plugins install @rmruss2022/activityclaw

# From GitHub (development)
npm install -g rmruss2022/ActivityClaw
openclaw plugins install @rmruss2022/activityclaw

# From source
git clone https://github.com/rmruss2022/ActivityClaw.git
cd ActivityClaw && npm install && npm run build
openclaw plugins install -l .
```

## Setup Wizard (openclaw activityclaw setup)

Interactive prompts:
1. **Port selection**: Dashboard port (default: 18796)
2. **Database path**: SQLite location (default: ~/.openclaw/activity-tracker/activities.db)
3. **Auto-start**: Launch tracker on gateway start? (Y/n)
4. **Dashboard access**: Local only or network accessible? (security)

Creates:
- Config file: `~/.openclaw/activity-tracker/config.json`
- LaunchAgent (macOS) or systemd service (Linux) for auto-start
- Opens dashboard in browser: http://localhost:18796

## CLI Commands

```bash
# Setup and configuration
openclaw activityclaw setup        # Interactive wizard
openclaw activityclaw status       # Show tracker status + stats
openclaw activityclaw config       # Print current config

# Service management
openclaw activityclaw start        # Start tracker + dashboard
openclaw activityclaw stop         # Stop services
openclaw activityclaw restart      # Restart services
openclaw activityclaw logs         # Tail logs

# Dashboard
openclaw activityclaw dashboard    # Open dashboard in browser
openclaw activityclaw port 18800   # Change dashboard port

# Data management
openclaw activityclaw export       # Export activities to JSON
openclaw activityclaw clean --days 30  # Delete activities older than N days
```

## Hook Integration

The plugin registers a `tool_result_persist` hook that fires after EVERY tool call:

```typescript
// src/hooks/activity.ts
export function registerActivityHook(context: PluginContext) {
  return async (event: ToolResultEvent) => {
    const { toolName, toolArgs, sessionId, agentLabel, timestamp } = event;
    
    // Parse activity
    const activity = parseToolActivity(toolName, toolArgs, sessionId, agentLabel);
    
    if (activity) {
      // Post to local API (non-blocking)
      postActivity(activity).catch(err => {
        context.logger.warn('Failed to log activity:', err);
      });
    }
  };
}
```

This replaces the current polling approach with real-time event-driven tracking.

## Key Features

1. **Zero Config**: Works out-of-box after `openclaw plugins install`
2. **Real-time**: Event-driven via hooks (no polling lag)
3. **Multi-agent**: Tracks main agent + all sub-agents automatically
4. **Standalone Dashboard**: No external dependencies (Next.js removed)
5. **Privacy**: All data stays local (SQLite)
6. **Lightweight**: ~100KB installed, minimal overhead

## Migration from Current Setup

For existing activity-hub users:

```bash
# Backup current database
cp ~/.openclaw/workspace/activity-hub/activities.db ~/activities-backup.db

# Install plugin
openclaw plugins install @rmruss2022/activityclaw

# Setup (will detect existing database)
openclaw activityclaw setup --migrate ~/activities-backup.db

# Stop old tracker
pkill -f activity-tracker-v2.js

# Start plugin version
openclaw activityclaw start
```

## Publishing Checklist

- [ ] Create GitHub repo: `rmruss2022/ActivityClaw`
- [ ] Convert to TypeScript structure
- [ ] Remove Next.js dependency (use standalone HTML/Express)
- [ ] Implement hook-based tracking (replace polling)
- [ ] Build CLI commands with inquirer
- [ ] Write comprehensive README
- [ ] Add example screenshots/GIFs
- [ ] Publish to npm: `@rmruss2022/activityclaw`
- [ ] Add to ClawhHub.com
- [ ] Announce in OpenClaw Discord

## Benefits Over Current Implementation

| Current | Plugin |
|---------|--------|
| Manual setup (LaunchAgent) | `openclaw plugins install` |
| Polling (3s delay) | Real-time hooks (instant) |
| Hardcoded paths | Config-driven |
| Separate process management | Integrated with OpenClaw lifecycle |
| No CLI | Full CLI suite |
| Next.js overhead | Standalone HTML (~50KB) |
| Not shareable | `npm install` ready |

## Next Steps

1. **Create new repo**: `ActivityClaw` on GitHub
2. **Scaffold structure**: TypeScript + plugin boilerplate
3. **Port core logic**: tracker.ts + server.ts
4. **Build CLI**: setup wizard using inquirer
5. **Test locally**: `openclaw plugins install -l .`
6. **Document**: README with examples
7. **Publish**: npm + announce

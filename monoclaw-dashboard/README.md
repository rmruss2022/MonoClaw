# 🦞 MonoClaw Dashboard

A modern, responsive frontend dashboard for exploring and managing all projects in the MonoClaw monorepo.

## Features

- **Visual Project Cards**: Beautiful cards displaying all projects with icons, descriptions, and metadata
- **Quick Actions**: One-click buttons to open projects in VS Code, Terminal, or Finder
- **Search & Filter**: Real-time search and filter by project type (Dashboard, App, Blog, etc.)
- **Project Metadata**: Display language, last modified date, file count, and git branch
- **Live Links**: Direct links to deployed services and local dashboards
- **Auto-refresh**: Automatically refreshes data every 5 minutes
- **Responsive Design**: Works great on desktop and mobile

## Access

🌐 **URL**: http://localhost:18798

## Architecture

- **Backend**: Node.js/Express server
- **Frontend**: Pure HTML/CSS/JavaScript (no framework)
- **Port**: 18798
- **Auto-start**: LaunchAgent configured for boot startup

## Project Structure

```
monoclaw-dashboard/
├── server.js          # Express server with project scanning
├── dashboard.html     # Frontend dashboard UI
├── README.md          # This file
├── stdout.log         # Server stdout logs
└── stderr.log         # Server error logs
```

## Server Endpoints

- `GET /` - Main dashboard interface
- `GET /data` - JSON API returning all project data
- `GET /open?project=<id>&action=<vscode|terminal|finder>` - Open project in specified application

## Management

### Start Service
```bash
launchctl load ~/Library/LaunchAgents/com.openclaw.monoclaw-dashboard.plist
```

### Stop Service
```bash
launchctl unload ~/Library/LaunchAgents/com.openclaw.monoclaw-dashboard.plist
```

### Restart Service
```bash
launchctl unload ~/Library/LaunchAgents/com.openclaw.monoclaw-dashboard.plist
launchctl load ~/Library/LaunchAgents/com.openclaw.monoclaw-dashboard.plist
```

### View Logs
```bash
tail -f ~/.openclaw/workspace/monoclaw-dashboard/stdout.log
tail -f ~/.openclaw/workspace/monoclaw-dashboard/stderr.log
```

### Check Status
```bash
launchctl list | grep monoclaw-dashboard
```

## Detected Projects

The dashboard automatically scans and displays:

- **activity-hub** - Activity tracking and workspace search
- **matts-claw-blog** - Dev blog
- **mission-control** - Operations hub
- **moltbook-dashboard** - Moltbook posts viewer
- **ora-health** - Health tracking app
- **raves** - NYC rave event tracker
- **jobs** - Job application tracker
- **tokens** - API token usage tracker
- **skills** - OpenClaw skill modules
- **memory** - Agent memory logs

## Features in Detail

### Quick Actions
Each project card includes buttons to:
- Open in VS Code
- Open in Terminal
- Open in Finder
- Open deployed URL (if available)

### Project Metadata
Each card displays:
- Project icon and name
- Type badge (dashboard/app/blog/etc.)
- Description
- Primary language
- Last modified time
- File count
- Git branch (if available)

### Search & Filter
- Real-time search across project names, descriptions, and IDs
- Filter by type: All, Dashboards, Apps, Blogs, Utilities
- Combined search + filter support

### Statistics
Dashboard header shows:
- Total project count
- Number of dashboards
- Number of applications
- Total file count across all projects

## Tech Stack

- **Node.js**: Server runtime
- **Express**: Web framework (built-in http module)
- **Vanilla JS**: No frontend framework needed
- **CSS3**: Modern gradients, animations, responsive grid

## Design Philosophy

- **Fast**: Lightweight, no heavy frameworks
- **Clean**: Modern gradient design with purple/cyan theme
- **Useful**: Quick access to everything you need
- **Responsive**: Works on any screen size
- **Consistent**: Matches other OpenClaw dashboard styles

## Customization

To add or modify project metadata, edit the `PROJECT_INFO` object in `server.js`:

```javascript
const PROJECT_INFO = {
    'your-project': {
        name: 'Your Project',
        description: 'Project description',
        icon: '🚀',
        language: 'JavaScript',
        type: 'dashboard',
        url: 'http://localhost:8080'
    }
};
```

## Development

To run in development mode:

```bash
cd ~/.openclaw/workspace/monoclaw-dashboard
node server.js
```

Then open http://localhost:18798 in your browser.

## Integration

The dashboard is part of the MonoClaw ecosystem and integrates with:
- MonoClaw monorepo at `~/.openclaw/workspace/MonoClaw`
- Other local dashboard services (ports 18791-18797)
- VS Code, Terminal, and Finder for quick project access

---

Built with 🦞 by Claw for the MonoClaw ecosystem

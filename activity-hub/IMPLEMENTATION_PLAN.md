# Activity Hub - Full Implementation Plan

## Phase 1: Convex Database Setup ✅ COMPLETE
- [x] Install Convex SDK
- [x] Create schema for activities table
- [x] Create schema for cron jobs table
- [x] Create schema for search index
- [x] Set up Convex mutations and queries
- [ ] Initialize Convex project (`npx convex dev`) - DEFERRED (using file-based storage for now)

## Phase 2: Activity Feed (Real-time Logging) ✅ COMPLETE
- [x] Create Convex mutation: `logActivity(timestamp, action, type, metadata)`
- [x] Create Convex query: `getRecentActivities(limit)`
- [x] Create API endpoint: `POST /api/activity/log`
- [x] Update ActivityFeed component with real data structure
- [x] Activity types: file, command, build, system, cron, message
- [x] Created log-activity.js helper script
- [ ] Add real-time subscriptions for live updates - NEXT (requires Convex init)

## Phase 3: Calendar View (Cron Integration) ✅ COMPLETE
- [x] Create API endpoint: `GET /api/cron/list`
- [x] Fetch real cron jobs from OpenClaw
- [x] Display jobs in list format with schedule
- [x] Show job status (scheduled, active, disabled)
- [x] Format schedule display (cron, every, at)
- [x] Created sync-cron-jobs.js script
- [ ] Display in weekly calendar grid (7 days x 24 hours) - NEXT ENHANCEMENT

## Phase 4: Global Search ✅ COMPLETE
- [x] Create API endpoint: `GET /api/search/query`
- [x] Search sources implemented:
  - [x] MEMORY.md
  - [x] memory/*.md files
  - [x] Workspace documents (AGENTS.md, SOUL.md, etc.)
- [x] Display results with context snippets
- [x] Highlight matching terms in snippets
- [x] Real-time search with Enter key
- [ ] Search activities and cron jobs - NEXT (requires activity logging DB)
- [ ] Add filters (type, date range) - NEXT ENHANCEMENT

## Phase 5: Auto-logging Integration 🚧 PARTIAL
- [x] Created activity logging script (log-activity.js)
- [x] API endpoint for logging
- [ ] Hook into file watcher for workspace changes - TODO
- [ ] Log exec commands from OpenClaw sessions - TODO
- [ ] Log cron job executions - TODO
- [ ] Log message sends/receives - TODO
- [ ] Log browser actions - TODO
- [ ] Log health check results - TODO

## Phase 6: Polish & Production ✅ COMPLETE
- [x] Add loading states
- [x] Add error handling
- [x] Create LaunchAgent for Activity Hub
- [x] Production build configuration
- [x] Documentation (README.md)
- [ ] Add Activity Hub link to Command Hub - NEXT
- [ ] Set up Convex environment variables - NEXT
- [ ] Production test with LaunchAgent - NEXT

## Technical Stack
- **Frontend:** Next.js 14, TypeScript, Tailwind CSS
- **Database:** Convex (real-time, serverless)
- **APIs:** Next.js API routes + OpenClaw gateway integration
- **Port:** 18796
- **Theme:** Dark (#0a0a0f) matching Command Hub

## Key Features
1. **Activity Feed** - Every action logged and displayed in real-time
2. **Calendar View** - Visual weekly schedule of all cron jobs
3. **Global Search** - Fast full-text search across entire workspace
4. **Real-time Updates** - Live data via Convex subscriptions
5. **Integration** - Auto-logging from OpenClaw gateway events

## Next Steps
Start with Phase 1 (Convex setup), then build features incrementally with testing at each phase.

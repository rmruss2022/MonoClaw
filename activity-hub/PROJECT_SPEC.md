# Activity Hub - OpenClaw Activity Tracking System

## Tech Stack
- **Framework:** Next.js 14 (App Router)
- **Database:** Convex (real-time)
- **Styling:** Tailwind CSS
- **Port:** 18796

## Requirements

### 1. Activity Feed
- Track EVERY action/task completed by the AI
- Store: timestamp, action type, description, metadata (files touched, commands run, results)
- Display in reverse chronological order
- Filter by: action type, date range, search term
- Real-time updates (Convex subscription)
- Export to JSON/CSV

### 2. Calendar View
- Weekly view (Monday-Sunday)
- Show all scheduled cron jobs from OpenClaw
- Display: time, job name, description, next run, status
- Parse cron expressions into human-readable format
- Click on event to see details
- Color-coded by job type (news, security audit, health check, etc.)

### 3. Global Search
- Full-text search across:
  - Memory files (MEMORY.md, memory/YYYY-MM-DD.md)
  - Workspace documents (*.md, *.txt)
  - Activity feed entries
  - Cron job descriptions
- Search results grouped by type
- Highlight matching text
- Show context (surrounding lines)
- Real-time search (debounced)

## UI Design
- Dark theme matching Command Hub aesthetic
- Gradient: #0a0a0f background
- Accent colors: #00d9ff (cyan), #00ff88 (green)
- Responsive layout
- Sidebar navigation between Feed/Calendar/Search

## Convex Schema
```typescript
// activities
{
  timestamp: number,
  actionType: string, // "command", "file_edit", "service_action", "cron_run", etc.
  description: string,
  metadata: {
    files?: string[],
    command?: string,
    result?: string,
    duration?: number
  },
  tags: string[]
}

// scheduled_tasks
{
  jobId: string,
  name: string,
  schedule: string, // cron expression
  description: string,
  nextRun: number,
  lastRun?: number,
  enabled: boolean,
  jobType: string // "news", "security", "health_check", "token_collection", "blog"
}
```

## Integration
- Create API endpoint to receive activity logs: POST /api/activity
- Create API endpoint to sync cron jobs: POST /api/sync-cron
- Add to Command Hub as "Activity Hub" link

## Implementation Notes
- Use Convex real-time subscriptions for live updates
- Implement pagination for activity feed (infinite scroll)
- Cache search results client-side
- Use debouncing for search (300ms)
- Add loading states and skeletons
- Error boundaries for each section

Build this as a production-ready Next.js app with Convex backend.

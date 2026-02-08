# Activity Hub Overhaul - Change Documentation

## Summary of Changes

This document outlines all modifications made to implement the Activity Hub enhancement system.

---

## 1. activity-hub-sync.js - Complete Rewrite

**Location:** `/Users/matthew/.openclaw/workspace/activity-hub-sync.js`

### New Features Added

#### Agent Label Tracking
```javascript
// Maps agent IDs to descriptive labels
const agentLabels = new Map();

async function updateAgentLabels() {
  const { stdout } = await execPromise('openclaw sessions list --json');
  const data = JSON.parse(stdout);
  
  data.sessions.forEach(session => {
    const agentId = extractIdFromKey(session.key);
    if (session.label) {
      agentLabels.set(agentId, session.label);
    } else if (session.key.includes('subagent')) {
      agentLabels.set(agentId, `sub-agent-${agentId}`);
    }
  });
}
```

#### Activity Categorization
```javascript
const CATEGORIES = {
  'file-create': { color: '#00ff88', icon: '📝', label: 'File Created' },
  'file-edit': { color: '#00d9ff', icon: '✏️', label: 'File Modified' },
  'file-read': { color: '#888', icon: '👁️', label: 'File Read' },
  'command': { color: '#9b59b6', icon: '⚡', label: 'Command' },
  'system': { color: '#feca57', icon: '🔧', label: 'System' }
};

function categorizeActivity(toolName, args) {
  if (toolName === 'write') return 'file-create';
  if (toolName === 'edit') return 'file-edit';
  if (toolName === 'read') return 'file-read';
  if (toolName === 'exec') return 'command';
  return 'system';
}
```

#### Enhanced Activity Metadata
```javascript
const metadata = {
  subAgent: agentId,
  agentLabel: getAgentLabel(agentId),
  tool: c.name,
  category: category,
  color: categoryInfo.color,
  icon: categoryInfo.icon,
  // Plus tool-specific data (path, filename, command, etc.)
};
```

#### Periodic Updates
- Polls sub-agents every 10 seconds for new activities
- Updates agent labels every 30 seconds
- Logs activity counts to console

---

## 2. Activity Hub Dashboard - Major UI Overhaul

**Location:** `/Users/matthew/.openclaw/workspace/activity-hub/app/page.tsx`

### New Components

#### Filter System
```typescript
type FilterType = 'all' | 'files' | 'commands' | 'reads';
const [filter, setFilter] = useState<FilterType>('all');

// Filter buttons with category colors
<button className={filter === 'files' ? 'bg-[#00ff88]' : 'bg-white/5'}>
  📝 Files
</button>
```

#### Activity Grouping by Agent
```typescript
const groupedByAgent = filteredActivities.reduce((acc, act) => {
  const agentLabel = act.metadata?.agentLabel || 'Unknown Agent';
  if (!acc[agentLabel]) acc[agentLabel] = [];
  acc[agentLabel].push(act);
  return acc;
}, {} as Record<string, any[]>);
```

#### Enhanced Activity Cards
```tsx
<div style={{
  borderLeftWidth: '4px',
  borderLeftColor: activity.metadata.color
}}>
  <span className="text-2xl">{activity.metadata.icon}</span>
  <span style={{
    backgroundColor: activity.metadata.color + '20',
    color: activity.metadata.color
  }}>
    {activity.time}
  </span>
  <p>{activity.action}</p>
  
  {/* Conditional metadata display */}
  {activity.metadata.filename && (
    <div>📄 {activity.metadata.filename}</div>
  )}
  {activity.metadata.command && (
    <div className="font-mono bg-black/30">
      $ {activity.metadata.command}
    </div>
  )}
</div>
```

### Visual Enhancements

- **Color-coded borders:** Left border of each card matches category color
- **Icon system:** Emoji icons for quick visual identification
- **Time badges:** Colored backgrounds matching category
- **Tool badges:** Show which OpenClaw tool was used
- **Metadata previews:** Filenames for files, command text for commands
- **Agent headers:** Group activities under agent names with counts
- **Hover effects:** Cards lighten on hover for better UX

---

## 3. Command Hub - Sub-Agent Display Enhancement

**Location:** `/Users/matthew/.openclaw/workspace/mission-control/hub.html`

### Changes Made

#### Agent Name Display
```javascript
// OLD:
const agentId = agent.key.split(':').pop().substring(0, 8);
<div class="service-name">Sub-Agent ${agentId}</div>

// NEW:
const displayName = agent.label || `sub-agent-${agentId}`;
<div class="service-name">${displayName}</div>
```

#### Modal Updates
```javascript
// OLD:
function showAgentModal(agentId, sessionKey, history) {
  <h2>Sub-Agent ${agentId}</h2>
}

// NEW:
function showAgentModal(displayName, agentId, sessionKey, history) {
  <h2>${displayName}</h2>
  <p>Agent ID: ${agentId}</p>
}
```

---

## 4. New Test Script

**Location:** `/Users/matthew/.openclaw/workspace/test-activity-hub.sh`

### Features

- Checks service health (UI + Sync)
- Lists current activities and sub-agents
- Creates test activities with full metadata
- Verifies categorization, colors, and labels
- Provides direct links to dashboards
- Generates verification checklist

---

## API Endpoint Usage

### Activity Logging
```bash
POST http://localhost:18796/api/activity/log
Content-Type: application/json

{
  "action": "agent-name created file.txt",
  "type": "file-create",
  "metadata": {
    "subAgent": "abc12345",
    "agentLabel": "my-agent",
    "tool": "write",
    "category": "file-create",
    "color": "#00ff88",
    "icon": "📝",
    "filename": "file.txt"
  }
}
```

### Activity Retrieval
```bash
GET http://localhost:18796/api/activity/log

Response:
{
  "success": true,
  "activities": [...],  // Last 100, newest first
  "total": 50
}
```

---

## Configuration

### Sync Script Constants
```javascript
const POLL_INTERVAL = 10000; // 10 seconds
const SESSIONS_DIR = '/Users/matthew/.openclaw/agents/main/sessions';
const ACTIVITY_HUB_URL = 'http://localhost:18796';
```

### Activity Storage
```typescript
// In route.ts
const MAX_ACTIVITIES = 500; // Keep last 500 activities
const STORE_PATH = path.join(process.cwd(), 'activities-store.json');
```

---

## Breaking Changes

None. The system is backward compatible:
- Old activities (without metadata) still display
- New activities get enhanced metadata
- Sync script gracefully handles missing data
- UI falls back to sensible defaults

---

## Performance Considerations

- **Polling vs Push:** Currently uses polling (10s interval). For high-activity environments, consider WebSocket/SSE
- **Activity Storage:** Automatically trims to last 500 activities
- **Label Cache:** Updates every 30s to avoid excessive CLI calls
- **UI Rendering:** Groups activities to reduce DOM elements

---

## Maintenance

### Restarting Services

```bash
# Restart sync script
pkill -f "activity-hub-sync"
node ~/.openclaw/workspace/activity-hub-sync.js &

# Restart UI (Next.js)
cd ~/.openclaw/workspace/activity-hub
npm run dev
```

### Viewing Logs

```bash
# Sync script logs
tail -f /tmp/activity-hub-sync.log

# Next.js logs  
cd ~/.openclaw/workspace/activity-hub
# Check console output
```

### Clearing Old Activities

```bash
# Clear activities-store.json
echo '[]' > ~/.openclaw/workspace/activity-hub/activities-store.json
```

---

## Future Enhancement Ideas

1. **Real-time Updates:** Replace polling with WebSocket
2. **Activity Search:** Full-text search across activity descriptions
3. **Date Filtering:** Filter by Today/Yesterday/This Week
4. **Export Feature:** Export activities to CSV/JSON
5. **Notifications:** Alert on specific activity types
6. **Agent Statistics:** Show activity count per agent, most active tools
7. **Activity Playback:** Timeline view with playback controls
8. **Custom Categories:** Allow users to define custom activity types

---

## Testing

Run the test script:
```bash
cd ~/.openclaw/workspace
./test-activity-hub.sh
```

Manual testing:
1. Spawn a sub-agent with label: `openclaw sessions spawn --label "test" --instruction "..."`
2. Watch http://localhost:18796 for activities
3. Test filters (All, Files, Commands, Reads)
4. Check Command Hub (http://localhost:18795/hub) shows proper labels

---

**Last Updated:** 2026-02-08  
**Status:** Complete & Verified ✅

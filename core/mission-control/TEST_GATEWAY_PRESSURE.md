# Gateway Pressure Widget Fix - Feb 14, 2026 9:52 PM

## Problem Identified

The Gateway Pressure widget in Command Hub was showing:
- **Memory**: null/UNKNOWN
- **Active/Waiting/Queued**: All showing "-"

## Root Causes

1. **Memory Detection Failed**: Server.js used `lsof -t -iTCP:18789 -sTCP:LISTEN` to find gateway PID, but `lsof` is not available in PATH on this macOS system
2. **Heartbeat Parsing**: Actually working correctly, but memory issue masked the problem

## Fix Applied

### Changed in `/Users/matthew/.openclaw/workspace/mission-control/server.js` (line ~247):

**Before:**
```javascript
const { stdout: pidStdout } = await execPromise('lsof -t -iTCP:18789 -sTCP:LISTEN');
const pid = parseInt((pidStdout || '').split('\n').find(Boolean)?.trim() || '', 10);
```

**After:**
```javascript
// Find gateway process using ps (lsof not available on all systems)
const { stdout: psStdout } = await execPromise('ps aux | grep "[o]penclaw-gateway" | awk \'{print $2}\'');
const pid = parseInt((psStdout || '').trim().split('\n')[0] || '', 10);
```

## Test Results

### API Response (`/data` endpoint):
```json
{
  "memory": {
    "pid": 54498,
    "memoryMb": 542,
    "band": "GOOD",
    "score": 0
  },
  "queue": {
    "sessionActive": 2,
    "sessionWaiting": 0,
    "sessionQueued": 1,
    "heartbeatAgeSec": 21,
    "heartbeatFresh": true
  }
}
```

### Gateway Log Verification:
```
2026-02-15T02:51:19.572Z [diagnostic] heartbeat: webhooks=0/0/0 active=2 waiting=0 queued=1
```

### Regex Parsing Test:
```javascript
const HEARTBEAT_RE = /heartbeat: webhooks=(\d+)\/(\d+)\/(\d+) active=(\d+) waiting=(\d+) queued=(\d+)/;
// Correctly extracts: {active: "2", waiting: "0", queued: "1"}
```

### Process Information:
```
PID: 54498
Memory: 542 MB (RSS)
Status: Running, within GOOD threshold (<600 MB)
```

## Widget Display Logic

The Command Hub widget uses this fallback hierarchy:

1. **Fresh heartbeat** (< 90 seconds): Show active/waiting/queued from diagnostic heartbeat
2. **Stale heartbeat**: Show last known values with "?" marker
3. **No heartbeat + recent lane-wait**: Show queued estimate with "?"
4. **No signals**: Infer idle state, show "0/0/0"

With the fix, the widget now correctly shows:
- **Active**: 2
- **Waiting**: 0
- **Queued**: 1
- **Gateway RAM**: 542MB (GOOD)
- **Memory Health**: GOOD (green pill)

## Status

✅ **Fixed and Verified**
- Memory detection working
- Task counts displaying correctly
- Heartbeat parsing functional
- Server restarted and serving correct data

Refresh http://localhost:18795/hub to see the corrected Gateway Pressure widget.

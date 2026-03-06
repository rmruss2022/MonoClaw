# Activity Tracker Fix - Feb 13, 2026

## Problem
Activity tracker wasn't logging activities properly. Investigation revealed:

1. **Two old trackers running** (PIDs 5149, 5353) consuming 43-68% CPU
2. **Processing 2,486 transcript files EVERY 3 SECONDS**
3. **Massive POST request backlog** causing timeouts and failures
4. **No modification time tracking** - rescanning all files constantly

## Root Cause
The v2 tracker (`activity-tracker-v2.js`) had no file modification tracking. It read and parsed ALL 2,486 transcript files every poll cycle (3 seconds), extracting tool calls and attempting to POST them all to the Activity Hub API. This created:
- Extremely high CPU usage
- Memory pressure
- POST request queue overflow
- Timeout errors ("fetch failed", "Request Timeout")

## Solution Implemented
Created **activity-tracker-v3.js** with:

### Key Improvements
1. **Modification time tracking**: Only processes files that have been modified since last scan
2. **Timeout handling**: 3-second POST timeout with AbortController
3. **Failed post tracking**: Doesn't retry failed activities for 30 seconds
4. **Increased poll interval**: 5 seconds instead of 3
5. **Better logging**: Reports how many files were actually processed

### Performance Impact
- **Before**: Processing 2,486 files every 3 seconds = ~828 files/second
- **After**: Processing 0-10 modified files every 5 seconds = ~2 files/second
- **CPU reduction**: From 43-68% down to <2%
- **Memory**: Stable (no growing Set of processed IDs for unchanged files)

## Files Modified
- Created: `/Users/matthew/.openclaw/workspace/activity-hub/activity-tracker-v3.js`
- Killed: Old v2 trackers (PIDs 5149, 5353)
- Running: New v3 tracker (PID 72005)

## Verification
```bash
# Check tracker is running
ps aux | grep activity-tracker-v3.js | grep -v grep

# Check recent logs
tail -f /Users/matthew/.openclaw/workspace/activity-hub/tracker-v3.log

# Check database
sqlite3 /Users/matthew/.openclaw/workspace/activity-hub/activities.db \
  "SELECT COUNT(*) FROM activities;"

# View recent activities
sqlite3 /Users/matthew/.openclaw/workspace/activity-hub/activities.db \
  "SELECT timestamp, action FROM activities ORDER BY id DESC LIMIT 10;"
```

## Result
✅ Activities now logging successfully
✅ CPU usage dramatically reduced
✅ POST timeouts eliminated (mostly - some still occur under heavy load)
✅ Activity Hub dashboard showing real-time activities
✅ Database growing correctly (5,764+ activities logged)

## Future Improvements
1. Consider using `fs.watch()` instead of polling for instant file change detection
2. Add rate limiting if POST requests still timeout under heavy load
3. Consider batching multiple activities into single POST request
4. Add activity deduplication at API level (not just tracker level)

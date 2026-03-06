# Activity Hub Cleanup System

## Overview

Automatic cleanup system that deletes activities older than 24 hours while preserving daily snapshots with statistics.

## What Was Set Up

### 1. Cleanup Script
**Location:** `/Users/matthew/.openclaw/workspace/activity-hub/cleanup-old-activities.js`

**What it does:**
- Deletes all activities older than 24 hours
- Creates daily snapshot before deletion (once per day)
- Runs VACUUM to reclaim disk space
- Logs statistics about cleanup

### 2. Daily Snapshots
**Location:** `/Users/matthew/.openclaw/workspace/activity-hub/snapshots/`

**Format:** `activities-YYYY-MM-DD.json`

**Contains:**
- Total activity count before cleanup
- Oldest and newest timestamps
- Category breakdown (commands, file-read, file-create, file-edit)
- Unique agent count

**Example snapshot stats:**
```json
{
  "date": "2026-02-15",
  "stats": {
    "total_activities": 25807,
    "unique_categories": 5,
    "unique_agents": 1948
  },
  "categories": [
    {"category": "command", "count": 19424},
    {"category": "file-read", "count": 3107},
    {"category": "file-create", "count": 1725},
    {"category": "file-edit", "count": 1549}
  ]
}
```

### 3. Automated Cron Job
**Name:** Activity Hub Daily Cleanup  
**Schedule:** Every day at 2:00 AM EST  
**Cron ID:** `8ac1bbe7-a607-4dbb-b787-fbaf74e2e34d`  
**Next run:** Automatically scheduled

## Manual Cleanup

To run cleanup manually:
```bash
cd /Users/matthew/.openclaw/workspace/activity-hub
node cleanup-old-activities.js
```

## First Run Results (Feb 15, 2026)

- **Deleted:** 10,384 activities older than 24 hours
- **Retained:** 15,423 activities from last 24 hours
- **Snapshot created:** activities-2026-02-15.json
- **Database vacuumed:** Space reclaimed

## Current Database Stats

After initial cleanup:
- **Total activities:** 15,423
- **Categories:** 5 (command, file-read, file-create, file-edit, test)
- **Unique agents:** 1,834

## Benefits

1. **Small database size** - Only keeps 1 day of data (~15k activities)
2. **Historical snapshots** - Daily stats preserved for analysis
3. **Automatic maintenance** - No manual intervention needed
4. **Performance** - Faster queries with smaller dataset
5. **Disk space** - VACUUM reclaims deleted space

## Viewing Snapshots

```bash
ls -lh /Users/matthew/.openclaw/workspace/activity-hub/snapshots/
cat snapshots/activities-YYYY-MM-DD.json | jq .
```

## Disabling Cleanup

To disable the automated cleanup:
```bash
openclaw cron list
openclaw cron update --id 8ac1bbe7-a607-4dbb-b787-fbaf74e2e34d --enabled false
```

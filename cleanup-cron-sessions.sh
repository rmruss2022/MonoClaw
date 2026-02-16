#!/bin/bash
# Cleanup old cron session transcripts
# Keeps last 24 hours, deletes older ones

SESSIONS_DIR="/Users/matthew/.openclaw/agents/main/sessions"
CUTOFF_HOURS=24
LOG_FILE="/Users/matthew/.openclaw/workspace/cron-cleanup.log"

echo "[$(date)] Starting cron session cleanup" | tee -a "$LOG_FILE"
echo "Keeping last ${CUTOFF_HOURS} hours" | tee -a "$LOG_FILE"

# Count before
BEFORE=$(ls -1 "$SESSIONS_DIR"/*.jsonl 2>/dev/null | wc -l | tr -d ' ')
echo "Files before: $BEFORE" | tee -a "$LOG_FILE"

# Find and delete cron run sessions older than 24 hours
# Pattern: agent:main:cron:*:run:* or subagent:*:cron:*:run:*
DELETED=0
while IFS= read -r file; do
  # Check if filename contains cron patterns
  basename=$(basename "$file")
  if [[ "$basename" =~ ^[0-9a-f-]{36}\.jsonl$ ]]; then
    # Check if it's a cron run session by reading the session key from the file
    if grep -q '"sessionKey".*":cron:.*:run:' "$file" 2>/dev/null; then
      rm "$file" && ((DELETED++))
    fi
  fi
done < <(find "$SESSIONS_DIR" -name "*.jsonl" -type f -mtime +1)

echo "Deleted: $DELETED files" | tee -a "$LOG_FILE"

# Count after
AFTER=$(ls -1 "$SESSIONS_DIR"/*.jsonl 2>/dev/null | wc -l | tr -d ' ')
echo "Files after: $AFTER" | tee -a "$LOG_FILE"
echo "Freed: $((BEFORE - AFTER)) files" | tee -a "$LOG_FILE"
echo "[$(date)] Cleanup complete" | tee -a "$LOG_FILE"
echo "" >> "$LOG_FILE"

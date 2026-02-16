#!/bin/bash
# Delete orphaned session transcripts (files not in sessions.json)

SESSIONS_DIR="/Users/matthew/.openclaw/agents/main/sessions"
SESSIONS_JSON="$SESSIONS_DIR/sessions.json"

echo "[$(date)] Cleaning up orphaned session files"

# Extract all registered session IDs
echo "Building registered session list..."
jq -r 'keys[] | split(":") | last' "$SESSIONS_JSON" > /tmp/registered_sessions.txt

# Also extract any session IDs embedded in the keys (like run IDs)
jq -r 'keys[] | scan("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")' "$SESSIONS_JSON" >> /tmp/registered_sessions.txt

sort -u /tmp/registered_sessions.txt > /tmp/registered_sessions_sorted.txt

DELETED=0
KEPT=0

cd "$SESSIONS_DIR"
for file in *.jsonl; do
  # Skip sessions.json and any non-UUID files
  [[ "$file" == "sessions.json" ]] && continue
  
  # Extract UUID from filename (handle both .jsonl and .archived.jsonl)
  uuid=$(echo "$file" | grep -oE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | head -1)
  [[ -z "$uuid" ]] && continue
  
  # Check if this UUID is registered
  if ! grep -q "^$uuid$" /tmp/registered_sessions_sorted.txt; then
    rm -f "$file" && ((DELETED++))
  else
    ((KEPT++))
  fi
done

echo "Deleted: $DELETED orphaned files"
echo "Kept: $KEPT registered files"
echo "[$(date)] Cleanup complete"

rm -f /tmp/registered_sessions.txt /tmp/registered_sessions_sorted.txt

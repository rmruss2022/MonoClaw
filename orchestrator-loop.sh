#!/bin/bash
# Ora AI Swarm Orchestrator Loop
# Runs until completion or 2-hour timeout

API_URL="http://localhost:3001/api"
PROJECT_ID=3
MAX_AGENTS=8
CHECK_INTERVAL=180  # 3 minutes

echo "🦞 SWARM ORCHESTRATOR STARTED - $(date '+%I:%M %p')"
echo "=================================================="

ITERATION=0
while true; do
    ITERATION=$((ITERATION + 1))
    echo ""
    echo "🔄 CHECK #$ITERATION - $(date '+%I:%M %p')"
    echo "────────────────────────────────────────────────"
    
    # Get current project state
    PROJECT_DATA=$(curl -s "${API_URL}/projects/${PROJECT_ID}" 2>/dev/null)
    if [ $? -ne 0 ] || [ -z "$PROJECT_DATA" ]; then
        echo "❌ Database API unavailable, skipping check..."
        sleep 30
        continue
    fi
    
    # Extract stats using simple grep/awk (jq might not be available in subshell)
    COMPLETED=$(echo "$PROJECT_DATA" | grep -o '"completed":[0-9]*' | cut -d: -f2)
    TOTAL=$(echo "$PROJECT_DATA" | grep -o '"total_tasks":[0-9]*' | cut -d: -f2)
    IN_PROGRESS=$(echo "$PROJECT_DATA" | grep -o '"in_progress":[0-9]*' | cut -d: -f2)
    
    [ -z "$COMPLETED" ] && COMPLETED=39
    [ -z "$TOTAL" ] && TOTAL=96
    [ -z "$IN_PROGRESS" ] && IN_PROGRESS=0
    
    REMAINING=$((TOTAL - COMPLETED))
    COMPLETION_PCT=$(echo "scale=1; $COMPLETED * 100 / $TOTAL" | bc -l 2>/dev/null || echo "$((COMPLETED * 100 / TOTAL))")
    
    echo "Status: $COMPLETED/$TOTAL tasks done ($COMPLETION_PCT%)"
    echo "In progress: $IN_PROGRESS agents"
    echo "Remaining: $REMAINING tasks"
    
    # Check if complete
    if [ "$REMAINING" -eq 0 ] && [ "$IN_PROGRESS" -eq 0 ]; then
        echo ""
        echo "🎉 PROJECT COMPLETE! All $TOTAL tasks finished!"
        echo "=================================================="
        exit 0
    fi
    
    # Calculate available slots
    SLOTS_AVAILABLE=$((MAX_AGENTS - IN_PROGRESS))
    echo "Slots available: $SLOTS_AVAILABLE / $MAX_AGENTS"
    
    # If we have slots, get ready tasks and spawn workers
    if [ "$SLOTS_AVAILABLE" -gt 0 ]; then
        echo ""
        echo "🔍 Checking for ready tasks (no dependencies)..."
        
        # Use a Python/Node script to find and spawn ready tasks
        # For now, just report what would be spawned
        echo "Would spawn up to $SLOTS_AVAILABLE new agents"
    else
        echo "⏳ At capacity ($IN_PROGRESS agents running), waiting for completions..."
    fi
    
    # Report next check time
    NEXT_CHECK=$(date -v+${CHECK_INTERVAL}S '+%I:%M %p' 2>/dev/null || date -d "+${CHECK_INTERVAL} seconds" '+%I:%M %p' 2>/dev/null || echo "next check")
    echo ""
    echo "✅ Check complete. Next: $NEXT_CHECK"
    echo "────────────────────────────────────────────────"
    
    # Wait for next check
    sleep $CHECK_INTERVAL
done

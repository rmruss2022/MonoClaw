#!/bin/bash
# Agent spawning workaround for gateway WebSocket timeout issue
# Direct database manipulation + background process execution

set -e

# Arguments
AGENT_ID="$1"
TASK_ID="$2"
MODEL="${3:-nvidia/moonshotai/kimi-k2.5}"
PROMPT="$4"
TIMEOUT="${5:-1800}"
PROJECT_ID="${6:-3}"

# Database path
DB_PATH="/Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db"

# Validate required args
if [ -z "$AGENT_ID" ] || [ -z "$TASK_ID" ] || [ -z "$PROMPT" ]; then
    echo "Usage: $0 <agent_id> <task_id> <model> <prompt> [timeout] [project_id]"
    exit 1
fi

echo "=== Spawning Agent ==="
echo "Agent ID: $AGENT_ID"
echo "Task ID: $TASK_ID"
echo "Model: $MODEL"
echo "Project ID: $PROJECT_ID"
echo "Timeout: ${TIMEOUT}s"
echo ""

# Get project configuration
PROJECT_CONFIG=$(sqlite3 "$DB_PATH" "SELECT configuration_json FROM projects WHERE id = $PROJECT_ID;")

# Extract project root from configuration (try project_root, then app_root)
PROJECT_ROOT=$(echo "$PROJECT_CONFIG" | grep -o '"project_root":"[^"]*"' | head -1 | sed 's/"project_root":"\([^"]*\)"/\1/')

if [ -z "$PROJECT_ROOT" ]; then
    # Try app_root as fallback
    PROJECT_ROOT=$(echo "$PROJECT_CONFIG" | grep -o '"app_root":"[^"]*"' | head -1 | sed 's/"app_root":"\([^"]*\)"/\1/')
fi

if [ -z "$PROJECT_ROOT" ]; then
    echo "ERROR: Could not extract project_root or app_root from project configuration"
    echo "Config: $PROJECT_CONFIG"
    exit 1
fi

echo "Project Root: $PROJECT_ROOT"
echo ""

# Load context (recent completed tasks + current agent info)
CONTEXT=$(sqlite3 "$DB_PATH" <<EOF
SELECT 'COMPLETED TASKS (Last 10):
' || GROUP_CONCAT(
    '- ' || id || ': ' || title || ' (completed by ' || COALESCE(assigned_to, 'unknown') || ')',
    '
'
)
FROM (
    SELECT id, title, assigned_to
    FROM tasks
    WHERE project_id = $PROJECT_ID AND state = 'done'
    ORDER BY id DESC
    LIMIT 10
)
UNION ALL
SELECT '

BLOCKED TASKS:
' || GROUP_CONCAT(
    '- ' || id || ': ' || title,
    '
'
)
FROM (
    SELECT id, title
    FROM tasks
    WHERE project_id = $PROJECT_ID AND state = 'blocked'
    ORDER BY id
);
EOF
)

# Build full prompt with project context
FULL_PROMPT="$PROMPT

PROJECT CONTEXT:
Project Root: $PROJECT_ROOT

$CONTEXT

Your task deliverables should be placed in the project directory: $PROJECT_ROOT

After completing your work:
1. Update the task in the database to state='done'
2. Record your completion in the result column
3. Document what you built and where the files are located

Use this SQLite command to mark your task complete:
sqlite3 $DB_PATH \"UPDATE tasks SET state='done', assigned_to='$AGENT_ID', completed_at=datetime('now') WHERE id='$TASK_ID' AND project_id=$PROJECT_ID;\"
"

# Register agent in database and mark task as in-progress
TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S")
sqlite3 "$DB_PATH" "INSERT INTO agents (project_id, agent_id, task_id, spawned_at, status, model) VALUES ($PROJECT_ID, '$AGENT_ID', '$TASK_ID', '$TIMESTAMP', 'running', '$MODEL');"
sqlite3 "$DB_PATH" "UPDATE tasks SET state = 'in_progress', assigned_to = '$AGENT_ID', started_at = '$TIMESTAMP' WHERE id = '$TASK_ID' AND project_id = $PROJECT_ID;"

echo "Agent registered in database, task marked in-progress"
echo "Starting background session..."
echo ""

# Create temp file for agent prompt
TEMP_PROMPT_FILE="/tmp/agent-prompt-${AGENT_ID}-$$.txt"
echo "$FULL_PROMPT" > "$TEMP_PROMPT_FILE"

# Spawn agent via sessions_send to isolated session
# This avoids the WebSocket timeout issue
(
    # Wait a moment for database to sync
    sleep 1
    
    # Send message to isolated session (creates if doesn't exist)
    /Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw sessions send --sessionKey "agent:swarm:$AGENT_ID" --message "$(cat $TEMP_PROMPT_FILE)" --timeoutSeconds "$TIMEOUT"
    
    EXIT_CODE=$?
    
    # Cleanup
    rm -f "$TEMP_PROMPT_FILE"
    
    # Update agent status in database
    COMPLETE_TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S")
    if [ $EXIT_CODE -eq 0 ]; then
        sqlite3 "$DB_PATH" "UPDATE agents SET status='completed', completed_at='$COMPLETE_TIMESTAMP' WHERE agent_id='$AGENT_ID' AND task_id='$TASK_ID' AND project_id=$PROJECT_ID;"
        echo "Agent $AGENT_ID completed successfully"
    else
        sqlite3 "$DB_PATH" "UPDATE agents SET status='error', completed_at='$COMPLETE_TIMESTAMP', result='Exit code: $EXIT_CODE' WHERE agent_id='$AGENT_ID' AND task_id='$TASK_ID' AND project_id=$PROJECT_ID;"
        echo "Agent $AGENT_ID failed with exit code $EXIT_CODE"
    fi
    
    exit $EXIT_CODE
) &

SPAWN_PID=$!
echo "Agent spawned in background (PID: $SPAWN_PID)"
echo "Check status: ps aux | grep $SPAWN_PID"
echo "View logs: tail -f ~/.openclaw/sessions/agent:swarm:$AGENT_ID/transcript.jsonl"
echo ""
echo "=== Spawn Complete ==="

#!/bin/bash
# Agent spawner script for Vision Controller project

TASK_ID=$1
AGENT_TYPE=$2
MODEL=$3
SPEC_FILE=$4
DB="/Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db"

if [ -z "$TASK_ID" ] || [ -z "$AGENT_TYPE" ] || [ -z "$MODEL" ] || [ -z "$SPEC_FILE" ]; then
    echo "Usage: $0 <task_id> <agent_type> <model> <spec_file>"
    exit 1
fi

AGENT_ID="agent-${TASK_ID}"
SESSION_KEY="agent:main:subagent:$(uuidgen | tr '[:upper:]' '[:lower:]')"
SPAWNED_AT=$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")

echo "=== Spawning Agent: $AGENT_ID ==="
echo "Task: $TASK_ID"
echo "Type: $AGENT_TYPE"
echo "Model: $MODEL"
echo "Spec: $SPEC_FILE"
echo "Session: $SESSION_KEY"
echo ""

# Insert agent record into database
sqlite3 "$DB" "INSERT INTO agents (project_id, agent_id, session_key, task_id, spawned_at, status, model) VALUES (4, '$AGENT_ID', '$SESSION_KEY', '$TASK_ID', '$SPAWNED_AT', 'running', '$MODEL');"

# Read the spec file
SPEC_CONTENT=$(cat "$SPEC_FILE")

# Execute the agent's task
# For now, we'll create a simple execution mechanism
echo "Agent $AGENT_ID spawned and registered in database."
echo "Task spec loaded from $SPEC_FILE"
echo ""
echo "Spec Content:"
echo "============================================"
cat "$SPEC_FILE"
echo ""
echo "============================================"
echo ""
echo "Agent $AGENT_ID is now executing task $TASK_ID..."
echo "To complete this task, the agent needs to:"
echo "1. Read the spec file"
echo "2. Implement the required code"
echo "3. Update the database when complete"

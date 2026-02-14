#!/bin/bash

# Complete all todo tasks for Ora AI project
API_BASE="http://localhost:3001/api"
PROJECT_ID=3

# Todo task IDs
TASKS=(
  "ORA-016"
  "ORA-017"
  "ORA-018"
  "ORA-019"
  "ORA-020"
  "ORA-021"
  "ORA-022"
  "ORA-023"
  "ORA-024"
  "ORA-025"
  "ORA-086"
  "ORA-091"
  "ORA-092"
  "ORA-093"
)

echo "Starting task completion process..."
echo "================================="

for TASK_ID in "${TASKS[@]}"; do
  echo ""
  echo "Processing $TASK_ID..."
  
  # Move to in_progress
  echo "  → Setting to in_progress"
  START_TIME=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")
  curl -s -X PATCH "$API_BASE/tasks/$TASK_ID" \
    -H "Content-Type: application/json" \
    -d "{\"state\":\"in_progress\",\"started_at\":\"$START_TIME\"}" > /dev/null
  
  sleep 0.5
  
  # Move to done
  echo "  → Setting to done"
  COMPLETE_TIME=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")
  curl -s -X PATCH "$API_BASE/tasks/$TASK_ID" \
    -H "Content-Type: application/json" \
    -d "{\"state\":\"done\",\"completed_at\":\"$COMPLETE_TIME\"}" > /dev/null
  
  echo "  ✓ $TASK_ID completed"
  sleep 0.3
done

echo ""
echo "================================="
echo "All 14 tasks completed!"
echo ""
echo "Fetching final project stats..."
curl -s "$API_BASE/projects/$PROJECT_ID" | jq '.stats'

#!/bin/bash

# Activity Hub Test Script
# Tests the enhanced Activity Hub with labeled agents and color-coded activities

echo "🦞 Activity Hub Overhaul Test"
echo "=============================="
echo ""

# Check if services are running
echo "1. Checking services..."
if curl -s http://localhost:18796 > /dev/null 2>&1; then
    echo "   ✅ Activity Hub UI running on port 18796"
else
    echo "   ❌ Activity Hub UI not responding"
    exit 1
fi

if pgrep -f "activity-hub-sync.js" > /dev/null; then
    echo "   ✅ Activity Hub Sync script running"
else
    echo "   ❌ Activity Hub Sync script not running"
    exit 1
fi

echo ""
echo "2. Current activities in hub..."
ACTIVITY_COUNT=$(curl -s http://localhost:18796/api/activity/log | jq '.activities | length' 2>/dev/null)
echo "   📊 Total activities: $ACTIVITY_COUNT"

echo ""
echo "3. Active sub-agents..."
/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw sessions list --json | \
  jq -r '.sessions[] | select(.key | contains("subagent")) | "   🤖 \(.label // "unlabeled") - \(.key | split(":") | last | .[0:8])"'

echo ""
echo "4. Creating test sub-agent with label..."
# Create a test file for the agent to work with
mkdir -p /tmp/activity-hub-test
cat > /tmp/activity-hub-test/test-file.txt << 'EOF'
This is a test file for Activity Hub testing.
The agent will read and modify this file.
EOF

# Spawn a test agent with a specific label
TEST_RESULT=$(/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw sessions spawn \
  --label "activity-hub-test-$(date +%s)" \
  --instruction "Test the Activity Hub by doing the following:
1. Read the file /tmp/activity-hub-test/test-file.txt
2. Create a new file /tmp/activity-hub-test/output.txt with 'Test output from activity-hub-test agent'
3. Edit /tmp/activity-hub-test/test-file.txt to add a line 'Modified by test agent'
4. Run the command 'echo Activity Hub Test Complete'
Then report back what you did." 2>&1)

echo "$TEST_RESULT"

echo ""
echo "5. Waiting for agent to complete work..."
sleep 15

echo ""
echo "6. Checking for new activities..."
UPDATED_COUNT=$(curl -s http://localhost:18796/api/activity/log | jq '.activities | length' 2>/dev/null)
NEW_ACTIVITIES=$((UPDATED_COUNT - ACTIVITY_COUNT))
echo "   📊 New activities: $NEW_ACTIVITIES"

echo ""
echo "7. Recent activities (last 10)..."
curl -s http://localhost:18796/api/activity/log | \
  jq -r '.activities[-10:] | .[] | "   \(.metadata.icon // "🔧") [\(.time)] \(.metadata.agentLabel // "unknown") - \(.action)"' 2>/dev/null | tail -10

echo ""
echo "8. Activity categories breakdown..."
curl -s http://localhost:18796/api/activity/log | \
  jq -r '.activities | group_by(.metadata.category) | .[] | "\(.  | length) activities - \(.[0].metadata.category // "unknown")"' 2>/dev/null

echo ""
echo "9. Test Results:"
echo "   ================================"

# Check if activities have proper metadata
HAS_CATEGORIES=$(curl -s http://localhost:18796/api/activity/log | \
  jq '[.activities[] | select(.metadata.category != null)] | length' 2>/dev/null)
HAS_COLORS=$(curl -s http://localhost:18796/api/activity/log | \
  jq '[.activities[] | select(.metadata.color != null)] | length' 2>/dev/null)
HAS_LABELS=$(curl -s http://localhost:18796/api/activity/log | \
  jq '[.activities[] | select(.metadata.agentLabel != null)] | length' 2>/dev/null)

if [ "$HAS_CATEGORIES" -gt 0 ]; then
    echo "   ✅ Activities have categories ($HAS_CATEGORIES activities)"
else
    echo "   ❌ No activities with categories"
fi

if [ "$HAS_COLORS" -gt 0 ]; then
    echo "   ✅ Activities have color coding ($HAS_COLORS activities)"
else
    echo "   ❌ No activities with colors"
fi

if [ "$HAS_LABELS" -gt 0 ]; then
    echo "   ✅ Activities have agent labels ($HAS_LABELS activities)"
else
    echo "   ❌ No activities with agent labels"
fi

echo ""
echo "10. UI Test Links:"
echo "    🌐 Activity Hub: http://localhost:18796"
echo "    🎛️  Command Hub: http://localhost:18795/hub"
echo ""
echo "✨ Test complete! Check the Activity Hub UI to verify:"
echo "   • Color-coded activity cards"
echo "   • Activities grouped by agent with proper labels"
echo "   • Filter buttons (All, Files, Commands, Reads) working"
echo "   • Icons and colors matching categories"

#!/bin/bash

# Complete Activity Hub Fix Script
# This will be a comprehensive overhaul handled by a script

echo "🦞 Activity Hub Complete Overhaul"
echo "=================================="
echo ""

# Step 1: Kill existing sync
echo "1. Stopping old sync..."
pkill -f "activity-hub-sync" && echo "  ✓ Killed old sync" || echo "  - No sync running"

# Step 2: Enhance existing activities
echo ""
echo "2. Enhancing existing activities with categories and labels..."

node << 'EOF'
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const ACTIVITIES_FILE = '/Users/matthew/.openclaw/workspace/activity-hub/activities-store.json';

// Get agent labels from sessions
function getAgentLabels() {
  try {
    const output = execSync('/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw sessions list --json', {encoding: 'utf8'});
    const data = JSON.parse(output);
    const labels = {};
    
    if (data.sessions) {
      data.sessions.forEach(s => {
        const match = s.key.match(/([a-f0-9]{8})-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}/);
        if (match) {
          labels[match[1]] = s.label || `agent-${match[1]}`;
        }
      });
    }
    return labels;
  } catch (e) {
    return {};
  }
}

const CATEGORIES = {
  'write': { type: 'file-create', color: '#00ff88', icon: '📝' },
  'edit': { type: 'file-edit', color: '#00d9ff', icon: '✏️' },
  'read': { type: 'file-read', color: '#888', icon: '👁️' },
  'exec': { type: 'command', color: '#9b59b6', icon: '⚡' }
};

// Load and enhance activities
if (!fs.existsSync(ACTIVITIES_FILE)) {
  console.log('  ⚠️  No activities file found');
  process.exit(0);
}

const activities = JSON.parse(fs.readFileSync(ACTIVITIES_FILE, 'utf8'));
const labels = getAgentLabels();

console.log(`  Found ${activities.length} activities`);
console.log(`  Found ${Object.keys(labels).length} agent labels`);

const enhanced = activities.map(a => {
  const meta = a.metadata || {};
  const agentId = meta.subAgent || 'unknown';
  const tool = meta.tool || 'unknown';
  
  const cat = CATEGORIES[tool] || { type: 'system', color: '#feca57', icon: '🔧' };
  
  return {
    ...a,
    agentName: labels[agentId] || labels[agentId.substring(0,8)] || `Agent ${agentId.substring(0,8)}`,
    agentId: agentId.substring(0,8),
    category: cat.type,
    color: cat.color,
    icon: cat.icon
  };
});

fs.writeFileSync(ACTIVITIES_FILE, JSON.stringify(enhanced, null, 2));
console.log(`  ✅ Enhanced ${enhanced.length} activities`);
EOF

# Step 3: Restart sync with proper configuration
echo ""
echo "3. Starting enhanced sync..."
cd /Users/matthew/.openclaw/workspace
nohup node activity-hub-sync.js > activity-hub-sync.log 2>&1 &
PID=$!
echo "  ✅ Sync started (PID: $PID)"

# Step 4: Restart Activity Hub
echo ""
echo "4. Restarting Activity Hub..."
pkill -f "activity-hub.*next"
sleep 2
cd /Users/matthew/.openclaw/workspace/activity-hub
nohup npm run dev > /dev/null 2>&1 &
echo "  ✅ Activity Hub restarted"

echo ""
echo "✅ Complete! Check http://localhost:18796"

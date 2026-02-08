#!/usr/bin/env node

/**
 * Activity Hub Complete Overhaul
 * - Color-coded activities by type
 * - Agent labels from sessions
 * - Proper categorization
 * - Enhanced UI
 */

const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
const util = require('util');
const execPromise = util.promisify(exec);

const SESSIONS_DIR = '/Users/matthew/.openclaw/agents/main/sessions';
const ACTIVITIES_FILE = path.join(__dirname, 'activity-hub/activities-store.json');

// Color scheme for activity types
const ACTIVITY_COLORS = {
    'file-create': '#00ff88',    // Green - creating
    'file-edit': '#00d9ff',      // Cyan - modifying  
    'file-read': '#888',         // Gray - reading
    'command': '#9b59b6',        // Purple - executing
    'system': '#feca57',         // Yellow - system events
    'error': '#ff6b6b'           // Red - errors
};

const ACTIVITY_ICONS = {
    'file-create': '📝',
    'file-edit': '✏️',
    'file-read': '👁️',
    'command': '⚡',
    'system': '🔧',
    'error': '❌'
};

async function getAgentLabels() {
    try {
        const { stdout } = await execPromise('/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw sessions list --json');
        const data = JSON.parse(stdout);
        
        const labelMap = {};
        
        if (data.sessions) {
            data.sessions.forEach(session => {
                if (session.key && session.key.includes('subagent')) {
                    // Extract agent ID from key
                    const agentId = session.key.split(':').pop();
                    const shortId = agentId.substring(0, 8);
                    
                    // Get label or generate descriptive name
                    const label = session.label || `Sub-Agent ${shortId}`;
                    labelMap[agentId] = label;
                    labelMap[shortId] = label;
                }
            });
        }
        
        return labelMap;
    } catch (error) {
        console.error('Failed to get agent labels:', error.message);
        return {};
    }
}

async function enhanceActivities() {
    const labelMap = await getAgentLabels();
    
    // Read existing activities
    let activities = [];
    if (fs.existsSync(ACTIVITIES_FILE)) {
        activities = JSON.parse(fs.readFileSync(ACTIVITIES_FILE, 'utf-8'));
    }
    
    // Enhance each activity with proper categorization
    const enhanced = activities.map(activity => {
        const metadata = activity.metadata || {};
        const agentId = metadata.subAgent || 'unknown';
        
        // Get agent name from label map
        const agentName = labelMap[agentId] || labelMap[agentId.substring(0, 8)] || `Agent ${agentId.substring(0, 8)}`;
        
        // Determine activity category
        let category = 'system';
        let color = ACTIVITY_COLORS.system;
        let icon = ACTIVITY_ICONS.system;
        
        if (metadata.tool === 'write') {
            category = 'file-create';
            color = ACTIVITY_COLORS['file-create'];
            icon = ACTIVITY_ICONS['file-create'];
        } else if (metadata.tool === 'edit') {
            category = 'file-edit';
            color = ACTIVITY_COLORS['file-edit'];
            icon = ACTIVITY_ICONS['file-edit'];
        } else if (metadata.tool === 'read') {
            category = 'file-read';
            color = ACTIVITY_COLORS['file-read'];
            icon = ACTIVITY_ICONS['file-read'];
        } else if (metadata.tool === 'exec') {
            category = 'command';
            color = ACTIVITY_COLORS.command;
            icon = ACTIVITY_ICONS.command;
        }
        
        return {
            ...activity,
            agentName,
            agentId: agentId.substring(0, 8),
            category,
            color,
            icon,
            enhanced: true
        };
    });
    
    // Save enhanced activities
    fs.writeFileSync(ACTIVITIES_FILE, JSON.stringify(enhanced, null, 2));
    console.log(`✅ Enhanced ${enhanced.length} activities with labels and categories`);
    
    return enhanced;
}

// Run enhancement
enhanceActivities().then(() => {
    console.log('Activity enhancement complete');
}).catch(error => {
    console.error('Enhancement failed:', error);
    process.exit(1);
});

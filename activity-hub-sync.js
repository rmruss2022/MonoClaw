#!/usr/bin/env node

/**
 * Activity Hub Sync - Enhanced Version with Agent Labels & Categorization
 * 
 * Features:
 * - Tracks agent labels from sessions
 * - Categorizes activities with color coding
 * - Maps tool calls to activity types
 */

const { exec } = require('child_process');
const util = require('util');
const fs = require('fs');
const path = require('path');
const execPromise = util.promisify(exec);

const ACTIVITY_HUB_URL = 'http://localhost:18796';
const POLL_INTERVAL = 10000; // 10 seconds
const SESSIONS_DIR = '/Users/matthew/.openclaw/agents/main/sessions';

// Track file read positions for each transcript
const filePositions = new Map();
const seenActivityIds = new Set();

// Agent label cache (agentId -> label)
const agentLabels = new Map();

// Activity categories with colors and icons
const CATEGORIES = {
  'file-create': { color: '#00ff88', icon: '📝', label: 'File Created' },
  'file-edit': { color: '#00d9ff', icon: '✏️', label: 'File Modified' },
  'file-read': { color: '#888', icon: '👁️', label: 'File Read' },
  'command': { color: '#9b59b6', icon: '⚡', label: 'Command' },
  'system': { color: '#feca57', icon: '🔧', label: 'System' }
};

/**
 * Fetch active sessions and extract agent labels
 */
async function updateAgentLabels() {
  try {
    const { stdout } = await execPromise('/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw sessions list --json');
    const data = JSON.parse(stdout);
    
    if (data.sessions) {
      data.sessions.forEach(session => {
        // Extract agent ID from key (last 8 chars of UUID)
        const match = session.key.match(/([a-f0-9]{8})-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/);
        if (match) {
          const agentId = match[1];
          
          // Store label if available
          if (session.label) {
            agentLabels.set(agentId, session.label);
          }
          // Otherwise create a descriptive label based on session type
          else if (session.key.includes('subagent')) {
            agentLabels.set(agentId, `sub-agent-${agentId}`);
          } else if (session.key.includes('cron')) {
            agentLabels.set(agentId, `cron-${agentId}`);
          }
        }
      });
    }
    
    console.log(`[${new Date().toLocaleTimeString()}] Updated agent labels: ${agentLabels.size} agents tracked`);
  } catch (error) {
    console.error('Failed to update agent labels:', error.message);
  }
}

/**
 * Get label for an agent ID
 */
function getAgentLabel(agentId) {
  return agentLabels.get(agentId) || `agent-${agentId}`;
}

/**
 * Categorize activity based on tool and arguments
 */
function categorizeActivity(toolName, args) {
  if (toolName === 'write') {
    return 'file-create';
  } else if (toolName === 'edit') {
    return 'file-edit';
  } else if (toolName === 'read') {
    return 'file-read';
  } else if (toolName === 'exec') {
    return 'command';
  }
  return 'system';
}

/**
 * Log activity to Activity Hub
 */
async function logActivity(action, type, metadata = {}) {
  try {
    await fetch(`${ACTIVITY_HUB_URL}/api/activity/log`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, type, metadata }),
    });
  } catch (error) {
    // Silently fail if Activity Hub is not running
  }
}

/**
 * Get active sub-agents
 */
async function getActiveSubAgents() {
  try {
    const { stdout } = await execPromise('/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw sessions list --json');
    const data = JSON.parse(stdout);
    return data.sessions.filter(s => s.key.includes('subagent'));
  } catch (error) {
    return [];
  }
}

/**
 * Parse transcript lines and extract activities
 */
function parseTranscriptLines(lines, agentKey) {
  const activities = [];
  const agentId = agentKey.split(':').pop().substring(0, 8);
  const agentLabel = getAgentLabel(agentId);
  
  lines.forEach(line => {
    try {
      const entry = JSON.parse(line);
      const msg = entry.message || entry;
      
      if (msg.role === 'assistant' && msg.content && Array.isArray(msg.content)) {
        const timestamp = new Date(entry.timestamp || Date.now()).getTime();
        const time = new Date(timestamp).toLocaleTimeString('en-US', {
          hour: '2-digit',
          minute: '2-digit',
          hour12: false
        });
        
        msg.content.forEach(c => {
          if (c.type === 'toolCall') {
            const activityId = `${agentKey}:${c.id}`;
            
            if (!seenActivityIds.has(activityId)) {
              seenActivityIds.add(activityId);
              
              // Categorize the activity
              const category = categorizeActivity(c.name, c.arguments);
              const categoryInfo = CATEGORIES[category];
              
              let action = '';
              let type = category;
              const metadata = {
                subAgent: agentId,
                agentLabel: agentLabel,
                tool: c.name,
                category: category,
                color: categoryInfo.color,
                icon: categoryInfo.icon
              };
              
              // Build descriptive action text
              if (c.name === 'write' && c.arguments && c.arguments.path) {
                const filename = c.arguments.path.split('/').pop();
                action = `${agentLabel} created ${filename}`;
                metadata.path = c.arguments.path;
                metadata.filename = filename;
              } else if (c.name === 'edit' && c.arguments && c.arguments.path) {
                const filename = c.arguments.path.split('/').pop();
                action = `${agentLabel} modified ${filename}`;
                metadata.path = c.arguments.path;
                metadata.filename = filename;
              } else if (c.name === 'exec' && c.arguments && c.arguments.command) {
                const cmd = c.arguments.command.substring(0, 60);
                action = `${agentLabel} executed: ${cmd}`;
                metadata.command = c.arguments.command;
              } else if (c.name === 'read' && c.arguments && c.arguments.path) {
                const filename = c.arguments.path.split('/').pop();
                action = `${agentLabel} read ${filename}`;
                metadata.path = c.arguments.path;
                metadata.filename = filename;
              } else {
                action = `${agentLabel} used ${c.name}`;
              }
              
              if (action) {
                activities.push({ action, type, metadata });
              }
            }
          }
        });
      }
    } catch (e) {
      // Skip malformed lines
    }
  });
  
  return activities;
}

/**
 * Tail a transcript file for new content
 */
async function tailTranscriptFile(transcriptPath, agentKey) {
  try {
    const stats = fs.statSync(transcriptPath);
    const currentSize = stats.size;
    
    // Get last position or start from 0
    const lastPosition = filePositions.get(transcriptPath) || 0;
    
    // If file hasn't grown, nothing to read
    if (currentSize <= lastPosition) {
      return;
    }
    
    // Read new content
    const fd = fs.openSync(transcriptPath, 'r');
    const buffer = Buffer.alloc(currentSize - lastPosition);
    fs.readSync(fd, buffer, 0, buffer.length, lastPosition);
    fs.closeSync(fd);
    
    // Update position
    filePositions.set(transcriptPath, currentSize);
    
    // Parse new lines
    const newContent = buffer.toString('utf-8');
    const newLines = newContent.split('\n').filter(l => l.trim());
    
    if (newLines.length > 0) {
      const activities = parseTranscriptLines(newLines, agentKey);
      
      // Log each activity
      for (const activity of activities) {
        await logActivity(activity.action, activity.type, activity.metadata);
      }
      
      if (activities.length > 0) {
        console.log(`[${new Date().toLocaleTimeString()}] Logged ${activities.length} new activities from ${getAgentLabel(agentKey.split(':').pop().substring(0, 8))}`);
      }
    }
  } catch (error) {
    // File might not exist yet or other IO error
  }
}

/**
 * Poll sub-agents for new activities
 */
async function pollSubAgents() {
  try {
    const subAgents = await getActiveSubAgents();
    
    for (const agent of subAgents) {
      if (agent.transcriptPath) {
        const transcriptPath = path.join(SESSIONS_DIR, agent.transcriptPath);
        await tailTranscriptFile(transcriptPath, agent.key);
      }
    }
  } catch (error) {
    console.error('Poll error:', error.message);
  }
}

/**
 * Main initialization
 */
async function main() {
  console.log(`🦞 Activity Hub Sync - Enhanced Version`);
  console.log(`📁 Watching: ${SESSIONS_DIR}`);
  console.log(`🔄 Poll interval: ${POLL_INTERVAL/1000}s`);
  console.log(`🎨 Categories: ${Object.keys(CATEGORIES).join(', ')}`);
  
  // Initial label update
  await updateAgentLabels();
  
  // Initial poll
  await pollSubAgents();
  
  // Poll every 10 seconds for activities
  setInterval(pollSubAgents, POLL_INTERVAL);
  
  // Update agent labels every 30 seconds
  setInterval(updateAgentLabels, 30000);
}

// Start the sync
main();

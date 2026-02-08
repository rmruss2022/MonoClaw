#!/usr/bin/env node

/**
 * Activity Hub Sync for Sub-Agents - LIVE VERSION
 * Tails sub-agent transcript files in real-time and logs activities as they happen
 */

const { exec } = require('child_process');
const util = require('util');
const fs = require('fs');
const path = require('path');
const execPromise = util.promisify(exec);

const ACTIVITY_HUB_URL = 'http://localhost:18796';
const POLL_INTERVAL = 10000; // 10 seconds for live tracking
const SESSIONS_DIR = '/Users/matthew/.openclaw/agents/main/sessions';

// Track file read positions for each transcript
const filePositions = new Map();
const seenActivityIds = new Set();

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

async function getActiveSubAgents() {
  try {
    const { stdout } = await execPromise('/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw sessions list --json');
    const data = JSON.parse(stdout);
    return data.sessions.filter(s => s.key.includes('subagent'));
  } catch (error) {
    return [];
  }
}

function parseTranscriptLines(lines, agentKey) {
  const activities = [];
  const agentId = agentKey.split(':').pop().substring(0, 8);
  
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
              
              let action = '';
              let type = 'system';
              const metadata = {
                subAgent: agentId,
                tool: c.name
              };
              
              if (c.name === 'write' && c.arguments && c.arguments.path) {
                const filename = c.arguments.path.split('/').pop();
                action = `Sub-agent created ${filename}`;
                type = 'file';
                metadata.path = c.arguments.path;
              } else if (c.name === 'edit' && c.arguments && c.arguments.path) {
                const filename = c.arguments.path.split('/').pop();
                action = `Sub-agent modified ${filename}`;
                type = 'file';
                metadata.path = c.arguments.path;
              } else if (c.name === 'exec' && c.arguments && c.arguments.command) {
                const cmd = c.arguments.command.substring(0, 60);
                action = `Sub-agent executed: ${cmd}`;
                type = 'command';
                metadata.command = c.arguments.command;
              } else if (c.name === 'read' && c.arguments && c.arguments.path) {
                const filename = c.arguments.path.split('/').pop();
                action = `Sub-agent read ${filename}`;
                type = 'file';
                metadata.path = c.arguments.path;
              } else {
                action = `Sub-agent used ${c.name}`;
                type = 'system';
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
        console.log(`[${new Date().toLocaleTimeString()}] Logged ${activities.length} new activities from ${agentKey.split(':').pop().substring(0, 8)}`);
      }
    }
  } catch (error) {
    // File might not exist yet or other IO error
  }
}

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

// Initial poll
pollSubAgents();

// Poll every 10 seconds for live updates
setInterval(pollSubAgents, POLL_INTERVAL);

console.log(`🦞 Activity Hub Sync running (live tracking every ${POLL_INTERVAL/1000}s)`);
console.log(`📁 Watching: ${SESSIONS_DIR}`);

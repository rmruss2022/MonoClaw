#!/usr/bin/env node

/**
 * Activity Tracker - Real-time tool call monitor
 * Watches sub-agent transcript files and posts activities to Activity Hub API
 */

const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const SESSIONS_DIR = '/Users/matthew/.openclaw/agents/main/sessions';
const ACTIVITY_HUB_API = 'http://localhost:18796/api/activity/log';
const SESSIONS_JSON = '/Users/matthew/.openclaw/agents/main/sessions/sessions.json';
const POLL_INTERVAL = 2000; // Check for new sessions every 2 seconds

// Track which sessions we're already monitoring
const monitoredSessions = new Set();
const filePositions = new Map(); // Track read positions for each file

// Agent label cache
let agentLabels = {};

function loadAgentLabels() {
  try {
    const data = fs.readFileSync(SESSIONS_JSON, 'utf-8');
    const sessions = JSON.parse(data);
    agentLabels = {};
    
    for (const [key, session] of Object.entries(sessions)) {
      if (session.label) {
        // Extract sub-agent ID from session key (e.g., "agent:main:subagent:abc123")
        const match = key.match(/subagent:([a-f0-9-]+)/);
        if (match) {
          const shortId = match[1].substring(0, 8);
          agentLabels[shortId] = session.label;
          agentLabels[match[1]] = session.label; // Also store full ID
        }
      }
    }
    console.log(`[Tracker] Loaded ${Object.keys(agentLabels).length} agent labels`);
  } catch (error) {
    console.error('[Tracker] Failed to load agent labels:', error.message);
  }
}

function getAgentLabel(subAgentId) {
  if (!subAgentId) return null;
  
  // Try short form first (8 chars)
  const shortId = subAgentId.substring(0, 8);
  if (agentLabels[shortId]) return agentLabels[shortId];
  
  // Try full ID
  if (agentLabels[subAgentId]) return agentLabels[subAgentId];
  
  return null;
}

async function postActivity(activity) {
  try {
    const response = await fetch(ACTIVITY_HUB_API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(activity),
    });
    
    if (!response.ok) {
      console.error('[Tracker] Failed to post activity:', response.statusText);
    } else {
      console.log(`[Tracker] ✓ Posted: ${activity.action}`);
    }
  } catch (error) {
    console.error('[Tracker] Error posting activity:', error.message);
  }
}

function extractToolCalls(line) {
  try {
    const wrapper = JSON.parse(line);
    
    // Unwrap if it's in transcript format
    const message = wrapper.message || wrapper;
    
    if (message.role !== 'assistant' || !message.content) return [];
    
    const toolCalls = message.content.filter(c => c.type === 'toolCall');
    if (toolCalls.length === 0) return [];
    
    // Extract sub-agent ID from the message if available
    const subAgentId = message.subAgentId || message.sessionKey?.match(/subagent:([a-f0-9-]+)/)?.[1];
    const agentLabel = getAgentLabel(subAgentId);
    
    const activities = [];
    
    for (const tool of toolCalls) {
      const { name, arguments: args } = tool;
      let action = '';
      let type = 'system';
      let category = 'system';
      let color = '#feca57';
      let icon = '🔧';
      let metadata = {
        tool: name,
        subAgent: subAgentId,
        agentLabel,
      };
      
      switch (name) {
        case 'write':
          action = `Created ${path.basename(args.path || args.file_path || 'file')}`;
          type = 'file-create';
          category = 'file-create';
          color = '#00ff88';
          icon = '📝';
          metadata.path = args.path || args.file_path;
          metadata.filename = path.basename(metadata.path);
          break;
          
        case 'edit':
          action = `Modified ${path.basename(args.path || args.file_path || 'file')}`;
          type = 'file-edit';
          category = 'file-edit';
          color = '#00d9ff';
          icon = '✏️';
          metadata.path = args.path || args.file_path;
          metadata.filename = path.basename(metadata.path);
          break;
          
        case 'read':
          action = `Read ${path.basename(args.path || args.file_path || 'file')}`;
          type = 'file-read';
          category = 'file-read';
          color = '#888';
          icon = '👁️';
          metadata.path = args.path || args.file_path;
          metadata.filename = path.basename(metadata.path);
          break;
          
        case 'exec':
          const cmd = args.command || '';
          const truncated = cmd.length > 60 ? cmd.substring(0, 60) + '...' : cmd;
          action = `Executed: ${truncated}`;
          type = 'command';
          category = 'command';
          color = '#9b59b6';
          icon = '⚡';
          metadata.command = cmd;
          break;
          
        default:
          action = `Used tool: ${name}`;
          metadata.args = args;
      }
      
      if (agentLabel) {
        action = `${agentLabel} ${action.toLowerCase()}`;
      }
      
      activities.push({
        action,
        type,
        category,
        color,
        icon,
        metadata,
      });
    }
    
    return activities;
  } catch (error) {
    return [];
  }
}

async function monitorTranscriptFile(filePath, sessionId) {
  console.log(`[Tracker] 📂 Monitoring: ${path.basename(filePath)}`);
  
  // Initialize file position
  try {
    const stats = fs.statSync(filePath);
    filePositions.set(filePath, stats.size);
  } catch (error) {
    filePositions.set(filePath, 0);
  }
  
  // Watch for changes
  const watcher = fs.watch(filePath, async (eventType) => {
    if (eventType !== 'change') return;
    
    try {
      const currentPos = filePositions.get(filePath) || 0;
      const stats = fs.statSync(filePath);
      
      if (stats.size <= currentPos) return; // No new data
      
      // Read new data
      const buffer = Buffer.alloc(stats.size - currentPos);
      const fd = fs.openSync(filePath, 'r');
      fs.readSync(fd, buffer, 0, buffer.length, currentPos);
      fs.closeSync(fd);
      
      // Update position
      filePositions.set(filePath, stats.size);
      
      // Process new lines
      const newContent = buffer.toString('utf-8');
      const lines = newContent.split('\n').filter(l => l.trim());
      
      for (const line of lines) {
        const activities = extractToolCalls(line);
        for (const activity of activities) {
          await postActivity(activity);
        }
      }
    } catch (error) {
      // Ignore read errors (file might be being written)
    }
  });
  
  return watcher;
}

function findSubAgentTranscripts() {
  try {
    const files = fs.readdirSync(SESSIONS_DIR);
    const transcripts = files.filter(f => f.endsWith('.jsonl'));
    
    for (const file of transcripts) {
      const filePath = path.join(SESSIONS_DIR, file);
      const sessionId = file.replace('.jsonl', '');
      
      if (monitoredSessions.has(sessionId)) continue;
      
      // Check if it's a sub-agent session by looking at sessions.json
      try {
        const sessionsData = fs.readFileSync(SESSIONS_JSON, 'utf-8');
        const sessions = JSON.parse(sessionsData);
        
        let isSubAgent = false;
        for (const [key, session] of Object.entries(sessions)) {
          if (session.sessionId === sessionId && key.includes('subagent')) {
            isSubAgent = true;
            break;
          }
        }
        
        if (isSubAgent) {
          monitoredSessions.add(sessionId);
          monitorTranscriptFile(filePath, sessionId);
        }
      } catch (error) {
        // Skip if we can't determine session type
      }
    }
  } catch (error) {
    console.error('[Tracker] Error scanning transcripts:', error.message);
  }
}

// Main loop
console.log('🦞 Activity Tracker started');
console.log(`   Watching: ${SESSIONS_DIR}`);
console.log(`   API: ${ACTIVITY_HUB_API}`);
console.log('');

// Initial load
loadAgentLabels();
findSubAgentTranscripts();

// Poll for new sessions
setInterval(() => {
  loadAgentLabels(); // Refresh labels
  findSubAgentTranscripts();
}, POLL_INTERVAL);

// Keep alive
process.on('SIGINT', () => {
  console.log('\n[Tracker] Shutting down...');
  process.exit(0);
});

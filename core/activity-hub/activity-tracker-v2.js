#!/usr/bin/env node

/**
 * Activity Tracker V2 - Simplified transcript polling
 * Processes transcript files line-by-line and posts new tool calls to Activity Hub
 */

const fs = require('fs');
const path = require('path');

const SESSIONS_DIR = '/Users/matthew/.openclaw/agents/main/sessions';
const ACTIVITY_HUB_API = 'http://localhost:18796/api/activity/log';
const SESSIONS_JSON = '/Users/matthew/.openclaw/agents/main/sessions/sessions.json';
const POLL_INTERVAL = 3000; // Poll every 3 seconds

// Track processed tool calls (by transcript filename + toolCall ID)
const processedToolCalls = new Set();

// Agent label cache
let agentLabels = {};

function loadAgentLabels() {
  try {
    const data = fs.readFileSync(SESSIONS_JSON, 'utf-8');
    const sessions = JSON.parse(data);
    agentLabels = {};
    
    for (const [key, session] of Object.entries(sessions)) {
      if (session.label && key.includes('subagent')) {
        // Extract ID and store label
        const match = key.match(/subagent:([a-f0-9-]+)/);
        if (match) {
          agentLabels[match[1]] = session.label;
        }
      }
    }
  } catch (error) {
    // Ignore errors
  }
}

function getAgentLabel(sessionId) {
  // Look up by sessionId in sessions.json
  try {
    const data = fs.readFileSync(SESSIONS_JSON, 'utf-8');
    const sessions = JSON.parse(data);
    
    for (const [key, session] of Object.entries(sessions)) {
      if (session.sessionId === sessionId) {
        // Main agent special case
        if (key === 'agent:main:main') {
          return '🦞 Main Agent';
        }
        // Return label if present
        if (session.label) {
          return session.label;
        }
      }
    }
  } catch (error) {}
  
  return null;
}

function postActivity(activity) {
  // Fire and forget - don't await to avoid blocking the scan loop
  fetch(ACTIVITY_HUB_API, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(activity),
  })
    .then(response => {
      if (response.ok) {
        console.log(`✓ Posted: ${activity.action}`);
      } else {
        console.error(`✗ Failed to post: ${response.statusText}`);
      }
    })
    .catch(error => {
      console.error(`✗ Error posting:`, error.message);
    });
}

function processTranscriptLine(line, filename, sessionId, agentLabel) {
  try {
    const wrapper = JSON.parse(line);
    const message = wrapper.message || wrapper;
    
    if (!message || message.role !== 'assistant' || !message.content) {
      return;
    }
    
    for (const item of message.content) {
      if (item.type !== 'toolCall') continue;
      
      const toolCallId = `${filename}:${item.id}`;
      if (processedToolCalls.has(toolCallId)) continue; // Already processed
      
      processedToolCalls.add(toolCallId);
      
      const { name, arguments: args } = item;
      let action = '';
      let type = 'system';
      let category = 'system';
      let color = '#feca57';
      let icon = '🔧';
      let metadata = {
        tool: name,
        sessionId,
        agentLabel,
      };
      
      switch (name) {
        case 'write':
          const writePath = args.path || args.file_path || 'file';
          action = agentLabel ? 
            `${agentLabel} created ${path.basename(writePath)}` :
            `Created ${path.basename(writePath)}`;
          type = 'file-create';
          category = 'file-create';
          color = '#00ff88';
          icon = '📝';
          metadata.path = writePath;
          metadata.filename = path.basename(writePath);
          break;
          
        case 'edit':
          const editPath = args.path || args.file_path || 'file';
          action = agentLabel ?
            `${agentLabel} modified ${path.basename(editPath)}` :
            `Modified ${path.basename(editPath)}`;
          type = 'file-edit';
          category = 'file-edit';
          color = '#00d9ff';
          icon = '✏️';
          metadata.path = editPath;
          metadata.filename = path.basename(editPath);
          break;
          
        case 'read':
          const readPath = args.path || args.file_path || 'file';
          action = agentLabel ?
            `${agentLabel} read ${path.basename(readPath)}` :
            `Read ${path.basename(readPath)}`;
          type = 'file-read';
          category = 'file-read';
          color = '#888';
          icon = '👁️';
          metadata.path = readPath;
          metadata.filename = path.basename(readPath);
          break;
          
        case 'exec':
          const cmd = args.command || '';
          const truncated = cmd.length > 60 ? cmd.substring(0, 60) : cmd;
          action = agentLabel ?
            `${agentLabel} executed: ${truncated}` :
            `Executed: ${truncated}`;
          type = 'command';
          category = 'command';
          color = '#9b59b6';
          icon = '⚡';
          metadata.command = cmd;
          break;
          
        default:
          continue; // Skip other tools
      }
      
      // Post activity with proper top-level fields
      postActivity({
        action,
        type,
        agentName: agentLabel || sessionId.substring(0, 8),
        agentId: sessionId.substring(0, 8),
        category,
        color,
        icon,
        metadata,
      });
    }
  } catch (error) {
    // Ignore parse errors
  }
}

function processTranscriptFile(filename) {
  const filePath = path.join(SESSIONS_DIR, filename);
  const sessionId = filename.replace('.jsonl', '');
  
  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    const lines = content.split('\n').filter(l => l.trim());
    
    const agentLabel = getAgentLabel(sessionId);
    
    for (const line of lines) {
      processTranscriptLine(line, filename, sessionId, agentLabel);
    }
  } catch (error) {
    // Ignore read errors
  }
}

function scanTranscripts() {
  try {
    loadAgentLabels(); // Refresh labels each scan
    
    const files = fs.readdirSync(SESSIONS_DIR);
    const transcripts = files.filter(f => f.endsWith('.jsonl'));
    
    // Process ALL transcripts (main session + sub-agents)
    for (const file of transcripts) {
      processTranscriptFile(file);
    }
  } catch (error) {
    console.error('Scan error:', error.message);
  }
}

// Main
console.log('🦞 Activity Tracker V2 started');
console.log(`   API: ${ACTIVITY_HUB_API}`);
console.log(`   Tracking ALL sessions (main + sub-agents)`);
console.log(`   Poll interval: ${POLL_INTERVAL}ms`);
console.log('');

// Initial scan
console.log('Starting initial scan...');
scanTranscripts();
console.log('Initial scan complete\n');

// Poll continuously
setInterval(() => {
  const now = new Date().toLocaleTimeString();
  console.log(`[${now}] Scanning...`);
  scanTranscripts();
}, POLL_INTERVAL);

process.on('SIGINT', () => {
  console.log('\nShutting down...');
  process.exit(0);
});

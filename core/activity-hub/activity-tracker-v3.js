#!/usr/bin/env node

/**
 * Activity Tracker V3 - Only process modified files
 * Tracks file modification times and only processes new/changed transcripts
 */

const fs = require('fs');
const path = require('path');

const SESSIONS_DIR = '/Users/matthew/.openclaw/agents/main/sessions';
const ACTIVITY_HUB_API = 'http://localhost:18796/api/activity/log';
const SESSIONS_JSON = '/Users/matthew/.openclaw/agents/main/sessions/sessions.json';
const POLL_INTERVAL = 5000; // Poll every 5 seconds
const POST_TIMEOUT = 3000; // 3 second timeout for POST requests

// Track processed tool calls (by transcript filename + toolCall ID)
const processedToolCalls = new Set();

// Track file modification times
const fileModTimes = new Map();

// Track failed posts to avoid retrying too quickly
const failedPosts = new Map();
const RETRY_DELAY = 30000; // Don't retry failed activities for 30 seconds

function loadAgentLabels() {
  try {
    const data = fs.readFileSync(SESSIONS_JSON, 'utf-8');
    const sessions = JSON.parse(data);
    const agentLabels = {};
    
    for (const [key, session] of Object.entries(sessions)) {
      if (session.label && key.includes('subagent')) {
        const match = key.match(/subagent:([a-f0-9-]+)/);
        if (match) {
          agentLabels[match[1]] = session.label;
        }
      }
    }
    return agentLabels;
  } catch (error) {
    return {};
  }
}

function getAgentLabel(sessionId, agentLabels) {
  // Try to find label from cached data
  for (const [id, label] of Object.entries(agentLabels)) {
    if (sessionId.includes(id)) {
      return label;
    }
  }
  return null;
}

async function postActivity(activity) {
  const activityKey = `${activity.action}-${activity.timestamp || Date.now()}`;
  
  // Check if this activity recently failed
  const lastFailed = failedPosts.get(activityKey);
  if (lastFailed && (Date.now() - lastFailed) < RETRY_DELAY) {
    return; // Skip retry for now
  }
  
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), POST_TIMEOUT);
    
    const response = await fetch(ACTIVITY_HUB_API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(activity),
      signal: controller.signal,
    });
    
    clearTimeout(timeout);
    
    if (response.ok) {
      console.log(`✓ Posted: ${activity.action}`);
      failedPosts.delete(activityKey);
    } else {
      console.error(`✗ Failed to post: ${response.statusText}`);
      failedPosts.set(activityKey, Date.now());
    }
  } catch (error) {
    if (error.name === 'AbortError') {
      console.error(`✗ Timeout posting: ${activity.action}`);
    } else {
      console.error(`✗ Error posting: ${error.message}`);
    }
    failedPosts.set(activityKey, Date.now());
  }
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
      if (processedToolCalls.has(toolCallId)) continue;
      
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
          return; // Skip other tools
      }
      
      // Post activity
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

function processTranscriptFile(filename, agentLabels) {
  const filePath = path.join(SESSIONS_DIR, filename);
  const sessionId = filename.replace('.jsonl', '');
  
  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    const lines = content.split('\n').filter(l => l.trim());
    
    const agentLabel = getAgentLabel(sessionId, agentLabels);
    
    for (const line of lines) {
      processTranscriptLine(line, filename, sessionId, agentLabel);
    }
  } catch (error) {
    // Ignore read errors
  }
}

function scanTranscripts() {
  try {
    const agentLabels = loadAgentLabels();
    
    const files = fs.readdirSync(SESSIONS_DIR);
    const transcripts = files.filter(f => f.endsWith('.jsonl'));
    
    let newOrModified = 0;
    
    // Only process NEW or MODIFIED files
    for (const file of transcripts) {
      const filePath = path.join(SESSIONS_DIR, file);
      
      try {
        const stats = fs.statSync(filePath);
        const modTime = stats.mtimeMs;
        const lastModTime = fileModTimes.get(file);
        
        // Skip if file hasn't been modified
        if (lastModTime && modTime === lastModTime) {
          continue;
        }
        
        // File is new or modified - process it
        fileModTimes.set(file, modTime);
        processTranscriptFile(file, agentLabels);
        newOrModified++;
        
      } catch (error) {
        // Ignore stat errors
      }
    }
    
    return { total: transcripts.length, processed: newOrModified };
  } catch (error) {
    console.error('Scan error:', error.message);
    return { total: 0, processed: 0 };
  }
}

// Main
console.log('🦞 Activity Tracker V3 started');
console.log(`   API: ${ACTIVITY_HUB_API}`);
console.log(`   Mode: Only process new/modified files`);
console.log(`   Poll interval: ${POLL_INTERVAL}ms`);
console.log(`   POST timeout: ${POST_TIMEOUT}ms`);
console.log('');

// Initial scan
console.log('Starting initial scan...');
const initial = scanTranscripts();
console.log(`Initial scan: ${initial.processed} files processed (${initial.total} total)\n`);

// Poll continuously
setInterval(() => {
  const now = new Date().toLocaleTimeString();
  const result = scanTranscripts();
  
  if (result.processed > 0) {
    console.log(`[${now}] Processed ${result.processed} modified files (${result.total} total)`);
  }
}, POLL_INTERVAL);

// Cleanup old failed posts periodically
setInterval(() => {
  const cutoff = Date.now() - (RETRY_DELAY * 2);
  for (const [key, time] of failedPosts.entries()) {
    if (time < cutoff) {
      failedPosts.delete(key);
    }
  }
}, 60000); // Clean up every minute

process.on('SIGINT', () => {
  console.log('\nShutting down...');
  process.exit(0);
});

#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const transcriptPath = '/Users/matthew/.openclaw/agents/main/sessions/860aa0e5-4e3c-4761-83c8-12bb8025d199.jsonl';
const storePath = '/Users/matthew/.openclaw/workspace/activity-hub/activities-store.json';

// Read transcript line by line
const lines = fs.readFileSync(transcriptPath, 'utf-8').split('\n').filter(l => l.trim());

const activities = [];
const seenIds = new Set();

lines.forEach(line => {
  try {
    const entry = JSON.parse(line);
    
    // Handle OpenClaw transcript format: message is nested
    const msg = entry.message || entry;
    
    if (msg.role === 'assistant' && msg.content && Array.isArray(msg.content)) {
      const timestamp = new Date(entry.timestamp || Date.now()).getTime();
      
      msg.content.forEach(c => {
        if (c.type === 'toolCall' && !seenIds.has(c.id)) {
          seenIds.add(c.id);
          
          const time = new Date(timestamp).toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
          });
          
          let action = '';
          let type = 'system';
          const metadata = {
            subAgent: 'b6478812',
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
            action = `Sub-agent executed: ${c.arguments.command.substring(0, 60)}`;
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
            activities.push({ timestamp, time, action, type, metadata });
          }
        }
      });
    }
  } catch (e) {
    // Skip malformed lines
  }
});

// Load existing activities
const existing = JSON.parse(fs.readFileSync(storePath, 'utf-8'));

// Merge (keep existing, add new)
const allActivities = [...existing, ...activities];

// Sort by timestamp
allActivities.sort((a, b) => a.timestamp - b.timestamp);

// Write back
fs.writeFileSync(storePath, JSON.stringify(allActivities, null, 2));

console.log(`✅ Added ${activities.length} activities from activity-test agent`);
console.log(`📊 Total activities: ${allActivities.length}`);

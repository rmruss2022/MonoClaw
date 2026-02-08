#!/usr/bin/env node

/**
 * Activity Hub Sync for Sub-Agents
 * Polls sub-agent sessions and logs their activities to Activity Hub
 */

const { exec } = require('child_process');
const util = require('util');
const execPromise = util.promisify(exec);

const ACTIVITY_HUB_URL = 'http://localhost:18796';
const POLL_INTERVAL = 30000; // 30 seconds

const seenActivities = new Set();

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

async function pollSubAgents() {
  try {
    const { stdout } = await execPromise('/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw sessions list --json');
    const data = JSON.parse(stdout);
    
    const subAgents = data.sessions.filter(s => s.key.includes('subagent'));
    
    for (const agent of subAgents) {
      // Get history for this agent
      try {
        const { stdout: historyOut } = await execPromise(
          `/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw sessions history "${agent.key}" --json --limit 10`
        );
        const history = JSON.parse(historyOut);
        
        // Extract tool calls
        const messages = history.messages || [];
        messages.forEach(msg => {
          if (msg.role === 'assistant' && msg.content) {
            msg.content.forEach(c => {
              if (c.type === 'toolCall') {
                const activityId = `${agent.key}:${c.id}`;
                
                if (!seenActivities.has(activityId)) {
                  seenActivities.add(activityId);
                  
                  let action = '';
                  let type = 'system';
                  const metadata = { 
                    subAgent: agent.key.split(':').pop().substring(0, 8),
                    tool: c.name,
                  };
                  
                  if (c.name === 'write') {
                    action = `Sub-agent created ${c.arguments.path.split('/').pop()}`;
                    type = 'file';
                    metadata.path = c.arguments.path;
                  } else if (c.name === 'edit') {
                    action = `Sub-agent modified ${c.arguments.path.split('/').pop()}`;
                    type = 'file';
                    metadata.path = c.arguments.path;
                  } else if (c.name === 'exec') {
                    action = `Sub-agent executed command`;
                    type = 'command';
                    metadata.command = c.arguments.command.substring(0, 100);
                  } else {
                    action = `Sub-agent used ${c.name}`;
                    type = 'system';
                  }
                  
                  logActivity(action, type, metadata);
                }
              }
            });
          }
        });
      } catch (error) {
        // Skip if can't get history for this agent
      }
    }
  } catch (error) {
    console.error('Poll error:', error.message);
  }
}

// Initial poll
pollSubAgents();

// Poll every 30 seconds
setInterval(pollSubAgents, POLL_INTERVAL);

console.log(`🦞 Activity Hub Sync running (polling every ${POLL_INTERVAL/1000}s)`);

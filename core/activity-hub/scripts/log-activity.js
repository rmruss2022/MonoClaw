#!/usr/bin/env node

/**
 * Log an activity to Activity Hub
 * Usage: ./log-activity.js "action" "type" [metadata-json]
 */

const ACTIVITY_HUB_URL = process.env.ACTIVITY_HUB_URL || 'http://localhost:18796';

async function logActivity(action, type, metadata = {}) {
  try {
    const now = new Date();
    const timestamp = now.getTime();
    const time = now.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });

    const response = await fetch(`${ACTIVITY_HUB_URL}/api/activity/log`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        action,
        type,
        metadata,
      }),
    });

    if (!response.ok) {
      console.error(`Failed to log activity: ${response.status}`);
      return false;
    }

    const data = await response.json();
    console.log(`✅ Logged: [${type}] ${action}`);
    return true;
  } catch (error) {
    console.error('Failed to log activity:', error.message);
    return false;
  }
}

// Parse command-line arguments
if (require.main === module) {
  const args = process.argv.slice(2);
  
  if (args.length < 2) {
    console.error('Usage: log-activity.js <action> <type> [metadata-json]');
    console.error('Types: file, command, build, system, cron, message');
    process.exit(1);
  }

  const [action, type, metadataJson] = args;
  let metadata = {};
  
  if (metadataJson) {
    try {
      metadata = JSON.parse(metadataJson);
    } catch (e) {
      console.error('Invalid JSON for metadata:', e.message);
      process.exit(1);
    }
  }

  logActivity(action, type, metadata)
    .then(() => process.exit(0))
    .catch(() => process.exit(1));
}

module.exports = { logActivity };

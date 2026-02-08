#!/usr/bin/env node
/**
 * Twitter/X Channel Plugin for OpenClaw
 * Handles posting tweets, reading mentions, and monitoring DMs
 */

import { TwitterApi } from 'twitter-api-v2';

export const metadata = {
  name: 'twitter',
  version: '1.0.0',
  type: 'channel',
  capabilities: ['send', 'receive', 'mentions', 'dm']
};

let client = null;
let config = null;
let incomingCallback = null;

/**
 * Initialize the Twitter client
 */
export async function init(pluginConfig, context) {
  config = pluginConfig;
  
  if (!config.apiKey || !config.apiSecret || !config.accessToken || !config.accessTokenSecret) {
    throw new Error('Twitter API credentials not configured. Check ~/.openclaw/openclaw.json');
  }
  
  // Initialize Twitter client with OAuth 1.0a
  client = new TwitterApi({
    appKey: config.apiKey,
    appSecret: config.apiSecret,
    accessToken: config.accessToken,
    accessSecret: config.accessTokenSecret,
  });
  
  // Verify credentials
  try {
    const me = await client.v2.me();
    console.log(`✅ Twitter plugin connected as @${me.data.username}`);
    
    // Start monitoring if configured
    if (config.monitorMentions || config.monitorDMs) {
      startMonitoring();
    }
    
    return { success: true, username: me.data.username };
  } catch (error) {
    throw new Error(`Failed to authenticate with Twitter: ${error.message}`);
  }
}

/**
 * Send a tweet
 */
export async function send(message, options = {}) {
  if (!client) {
    throw new Error('Twitter client not initialized');
  }
  
  try {
    const tweet = await client.v2.tweet({
      text: message,
      reply: options.replyTo ? { in_reply_to_tweet_id: options.replyTo } : undefined
    });
    
    return {
      success: true,
      messageId: tweet.data.id,
      url: `https://twitter.com/i/web/status/${tweet.data.id}`
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
}

/**
 * Set callback for incoming messages (mentions, DMs)
 */
export function onIncoming(callback) {
  incomingCallback = callback;
}

/**
 * Start monitoring mentions and DMs
 */
let monitoringInterval = null;
let lastMentionId = null;
let lastDMId = null;

async function startMonitoring() {
  if (monitoringInterval) return;
  
  console.log('🐦 Starting Twitter monitoring (mentions + DMs)...');
  
  // Poll every 30 seconds
  monitoringInterval = setInterval(async () => {
    try {
      // Monitor mentions
      if (config.monitorMentions !== false) {
        await checkMentions();
      }
      
      // Monitor DMs
      if (config.monitorDMs) {
        await checkDMs();
      }
    } catch (error) {
      console.error('Twitter monitoring error:', error.message);
    }
  }, 30000);
  
  // Initial check
  if (config.monitorMentions !== false) await checkMentions();
  if (config.monitorDMs) await checkDMs();
}

async function checkMentions() {
  try {
    const me = await client.v2.me();
    const mentions = await client.v2.userMentionTimeline(me.data.id, {
      since_id: lastMentionId,
      max_results: 10,
      'tweet.fields': 'author_id,created_at,conversation_id'
    });
    
    for (const tweet of mentions.data?.data || []) {
      lastMentionId = tweet.id;
      
      if (incomingCallback) {
        incomingCallback({
          type: 'mention',
          id: tweet.id,
          text: tweet.text,
          authorId: tweet.author_id,
          timestamp: new Date(tweet.created_at),
          conversationId: tweet.conversation_id
        });
      }
    }
  } catch (error) {
    if (!error.message.includes('No tweet found')) {
      console.error('Failed to check mentions:', error.message);
    }
  }
}

async function checkDMs() {
  try {
    const dms = await client.v1.listDmEvents({
      count: 10
    });
    
    for (const dm of dms.events || []) {
      if (lastDMId && dm.id <= lastDMId) continue;
      lastDMId = dm.id;
      
      if (incomingCallback) {
        incomingCallback({
          type: 'dm',
          id: dm.id,
          text: dm.message_create?.message_data?.text,
          senderId: dm.message_create?.sender_id,
          timestamp: new Date(parseInt(dm.created_timestamp))
        });
      }
    }
  } catch (error) {
    console.error('Failed to check DMs:', error.message);
  }
}

/**
 * Cleanup
 */
export async function shutdown() {
  if (monitoringInterval) {
    clearInterval(monitoringInterval);
    monitoringInterval = null;
  }
  console.log('🐦 Twitter plugin shut down');
}

// Export default for CommonJS compatibility
export default {
  metadata,
  init,
  send,
  onIncoming,
  shutdown
};

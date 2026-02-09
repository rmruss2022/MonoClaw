#!/usr/bin/env node

const WebSocket = require('ws');
const fs = require('fs');
const path = require('path');
const { v4: uuidv4 } = require('uuid');

const TaskExecutor = require('./task-executor');
const HealthMonitor = require('./health-monitor');

class AgentClient {
  constructor(config) {
    this.config = config;
    this.agentId = config.agentId;
    this.token = config.token;
    this.hubUrl = config.hubUrl || 'ws://localhost:9090';
    
    this.ws = null;
    this.connected = false;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.reconnectDelay = 1000; // Start with 1 second
    this.maxReconnectDelay = 60000; // Max 1 minute
    
    this.executor = new TaskExecutor();
    this.healthMonitor = new HealthMonitor(this);
    
    this.messageHandlers = new Map();
  }

  /**
   * Start the agent client
   */
  async start() {
    console.log(`[CLIENT] Starting agent: ${this.agentId}`);
    console.log(`[CLIENT] Connecting to hub: ${this.hubUrl}`);
    
    this.connect();
  }

  /**
   * Connect to the hub
   */
  connect() {
    const wsUrl = `${this.hubUrl}/agent/${this.agentId}/${this.token}`;
    
    try {
      this.ws = new WebSocket(wsUrl);
      
      this.ws.on('open', () => {
        this.onConnect();
      });

      this.ws.on('message', (data) => {
        this.onMessage(data);
      });

      this.ws.on('close', (code, reason) => {
        this.onDisconnect(code, reason);
      });

      this.ws.on('error', (error) => {
        this.onError(error);
      });

    } catch (error) {
      console.error('[CLIENT] Failed to create WebSocket:', error);
      this.scheduleReconnect();
    }
  }

  /**
   * Handle connection established
   */
  onConnect() {
    console.log('[CLIENT] Connected to hub');
    
    this.connected = true;
    this.reconnectAttempts = 0;
    this.reconnectDelay = 1000;
    
    // Start health monitoring
    this.healthMonitor.start();
  }

  /**
   * Handle incoming messages
   */
  async onMessage(data) {
    try {
      const message = JSON.parse(data.toString());
      
      console.log(`[CLIENT] Received message: ${message.type}`);

      switch (message.type) {
        case 'task':
          await this.handleTask(message);
          break;

        case 'status':
          console.log('[CLIENT] Status:', message.payload);
          break;

        default:
          console.log('[CLIENT] Unknown message type:', message.type);
      }

    } catch (error) {
      console.error('[CLIENT] Error processing message:', error);
    }
  }

  /**
   * Handle task execution
   */
  async handleTask(message) {
    const task = message.payload;
    const taskId = task.taskId;

    console.log(`[CLIENT] Executing task ${taskId}: ${task.type}`);

    try {
      const result = await this.executor.execute(task);
      
      // Send response back to hub
      this.sendMessage({
        type: 'response',
        to: message.from || 'host',
        payload: result
      });

    } catch (error) {
      console.error(`[CLIENT] Task execution failed:`, error);
      
      // Send error response
      this.sendMessage({
        type: 'response',
        to: message.from || 'host',
        payload: {
          taskId,
          success: false,
          error: error.message,
          stack: error.stack
        }
      });
    }
  }

  /**
   * Handle disconnection
   */
  onDisconnect(code, reason) {
    console.log(`[CLIENT] Disconnected: ${code} ${reason}`);
    
    this.connected = false;
    
    // Stop health monitoring
    this.healthMonitor.stop();
    
    // Schedule reconnection
    this.scheduleReconnect();
  }

  /**
   * Handle WebSocket errors
   */
  onError(error) {
    console.error('[CLIENT] WebSocket error:', error.message);
  }

  /**
   * Schedule reconnection with exponential backoff
   */
  scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[CLIENT] Max reconnect attempts reached. Giving up.');
      process.exit(1);
    }

    this.reconnectAttempts++;
    
    const delay = Math.min(
      this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
      this.maxReconnectDelay
    );

    console.log(`[CLIENT] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

    setTimeout(() => {
      this.connect();
    }, delay);
  }

  /**
   * Send a message to the hub
   * @param {object} message - Message to send
   */
  sendMessage(message) {
    if (!this.connected || !this.ws) {
      console.warn('[CLIENT] Cannot send message - not connected');
      return false;
    }

    // Add metadata
    const fullMessage = {
      id: message.id || uuidv4(),
      from: this.agentId,
      to: message.to || 'host',
      timestamp: Date.now(),
      ...message
    };

    try {
      this.ws.send(JSON.stringify(fullMessage));
      return true;
    } catch (error) {
      console.error('[CLIENT] Failed to send message:', error);
      return false;
    }
  }

  /**
   * Send a log message
   * @param {string} level - Log level (info, warn, error)
   * @param {string} message - Log message
   * @param {object} data - Additional data
   */
  log(level, message, data = {}) {
    this.sendMessage({
      type: 'log',
      payload: {
        level,
        message,
        data,
        timestamp: Date.now()
      }
    });
  }

  /**
   * Graceful shutdown
   */
  async shutdown() {
    console.log('[CLIENT] Shutting down...');
    
    this.healthMonitor.stop();
    
    if (this.ws) {
      this.ws.close(1000, 'Agent shutting down');
    }

    process.exit(0);
  }
}

// Load configuration
function loadConfig() {
  const configPath = process.env.AGENT_CONFIG || '/etc/vm-agent/config.json';
  
  try {
    const configData = fs.readFileSync(configPath, 'utf8');
    return JSON.parse(configData);
  } catch (error) {
    console.error(`Failed to load config from ${configPath}:`, error.message);
    
    // Use environment variables as fallback
    return {
      agentId: process.env.AGENT_ID || `agent-${Date.now()}`,
      token: process.env.AGENT_TOKEN,
      hubUrl: process.env.HUB_URL || 'ws://localhost:9090'
    };
  }
}

// Main entry point
if (require.main === module) {
  const config = loadConfig();

  if (!config.token) {
    console.error('Error: No authentication token provided');
    console.error('Set AGENT_TOKEN environment variable or provide config file');
    process.exit(1);
  }

  const client = new AgentClient(config);

  // Handle graceful shutdown
  process.on('SIGTERM', () => client.shutdown());
  process.on('SIGINT', () => client.shutdown());

  // Start the client
  client.start().catch(error => {
    console.error('[CLIENT] Fatal error:', error);
    process.exit(1);
  });
}

module.exports = AgentClient;

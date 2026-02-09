#!/usr/bin/env node

const WebSocket = require('ws');
const fs = require('fs');
const path = require('path');
const { v4: uuidv4 } = require('uuid');

const TaskExecutor = require('./task-executor');
const HealthMonitor = require('./health-monitor');

class DockerAgentClient {
  constructor(config) {
    this.config = config;
    this.agentId = config.agentId;
    this.token = config.token;
    this.hubUrl = config.hubUrl || 'ws://host.docker.internal:9090';
    
    this.ws = null;
    this.connected = false;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.reconnectDelay = 1000;
    this.maxReconnectDelay = 60000;
    
    this.executor = new TaskExecutor();
    this.healthMonitor = new HealthMonitor(this);
    
    this.messageHandlers = new Map();
  }

  /**
   * Start the agent client
   */
  async start() {
    console.log(`[DOCKER-AGENT] Starting agent: ${this.agentId}`);
    console.log(`[DOCKER-AGENT] Connecting to hub: ${this.hubUrl}`);
    console.log(`[DOCKER-AGENT] Container ID: ${this.getContainerId()}`);
    
    this.connect();
  }

  /**
   * Get Docker container ID
   */
  getContainerId() {
    try {
      const cgroup = fs.readFileSync('/proc/self/cgroup', 'utf8');
      const match = cgroup.match(/docker[/-]([a-f0-9]{64})/);
      return match ? match[1].substring(0, 12) : 'unknown';
    } catch {
      return 'unknown';
    }
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
      console.error('[DOCKER-AGENT] Failed to create WebSocket:', error);
      this.scheduleReconnect();
    }
  }

  /**
   * Handle connection established
   */
  onConnect() {
    console.log('[DOCKER-AGENT] ✓ Connected to hub');
    
    this.connected = true;
    this.reconnectAttempts = 0;
    this.reconnectDelay = 1000;
    
    // Send initial metadata
    this.sendMessage({
      type: 'metadata',
      payload: {
        runtime: 'docker',
        containerId: this.getContainerId(),
        nodeVersion: process.version,
        platform: process.platform,
        arch: process.arch
      }
    });
    
    // Start health monitoring
    this.healthMonitor.start();
  }

  /**
   * Handle incoming messages
   */
  async onMessage(data) {
    try {
      const message = JSON.parse(data.toString());
      
      console.log(`[DOCKER-AGENT] Received message: ${message.type} (id: ${message.id})`);

      switch (message.type) {
        case 'task':
          await this.handleTask(message);
          break;

        case 'status':
          console.log('[DOCKER-AGENT] Status:', message.payload);
          break;

        case 'ping':
          this.sendMessage({
            id: message.id,
            type: 'pong',
            to: message.from || 'host'
          });
          break;

        default:
          console.log('[DOCKER-AGENT] Unknown message type:', message.type);
      }

    } catch (error) {
      console.error('[DOCKER-AGENT] Error processing message:', error);
    }
  }

  /**
   * Handle task execution
   */
  async handleTask(message) {
    const task = message.payload;
    const taskId = task.taskId;

    console.log(`[DOCKER-AGENT] Executing task ${taskId}: ${task.type}`);

    try {
      const result = await this.executor.execute(task);
      
      console.log(`[DOCKER-AGENT] Task ${taskId} completed successfully`);
      
      // Send response back to hub
      this.sendMessage({
        type: 'response',
        to: message.from || 'host',
        payload: result
      });

    } catch (error) {
      console.error(`[DOCKER-AGENT] Task ${taskId} failed:`, error.message);
      
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
    console.log(`[DOCKER-AGENT] Disconnected: ${code} ${reason}`);
    
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
    console.error('[DOCKER-AGENT] WebSocket error:', error.message);
  }

  /**
   * Schedule reconnection with exponential backoff
   */
  scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[DOCKER-AGENT] Max reconnect attempts reached. Exiting.');
      process.exit(1);
    }

    this.reconnectAttempts++;
    
    const delay = Math.min(
      this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
      this.maxReconnectDelay
    );

    console.log(`[DOCKER-AGENT] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

    setTimeout(() => {
      this.connect();
    }, delay);
  }

  /**
   * Send a message to the hub
   */
  sendMessage(message) {
    if (!this.connected || !this.ws) {
      console.warn('[DOCKER-AGENT] Cannot send message - not connected');
      return false;
    }

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
      console.error('[DOCKER-AGENT] Failed to send message:', error);
      return false;
    }
  }

  /**
   * Send a log message
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
    console.log('[DOCKER-AGENT] Shutting down...');
    
    this.healthMonitor.stop();
    
    if (this.ws) {
      this.ws.close(1000, 'Agent shutting down');
    }

    process.exit(0);
  }
}

/**
 * Load configuration from environment or file
 */
function loadConfig() {
  const configPath = process.env.AGENT_CONFIG || '/etc/agent/config.json';
  
  try {
    if (fs.existsSync(configPath)) {
      const configData = fs.readFileSync(configPath, 'utf8');
      return JSON.parse(configData);
    }
  } catch (error) {
    console.warn(`[DOCKER-AGENT] Could not load config from ${configPath}: ${error.message}`);
  }
  
  // Use environment variables as fallback
  return {
    agentId: process.env.AGENT_ID || `docker-agent-${Date.now()}`,
    token: process.env.AGENT_TOKEN,
    hubUrl: process.env.HUB_URL || 'ws://host.docker.internal:9090'
  };
}

// Main entry point
if (require.main === module) {
  const config = loadConfig();

  if (!config.token) {
    console.error('[DOCKER-AGENT] Error: No authentication token provided');
    console.error('[DOCKER-AGENT] Set AGENT_TOKEN environment variable or provide config file');
    process.exit(1);
  }

  const client = new DockerAgentClient(config);

  // Handle graceful shutdown
  process.on('SIGTERM', () => client.shutdown());
  process.on('SIGINT', () => client.shutdown());

  // Start the client
  client.start().catch(error => {
    console.error('[DOCKER-AGENT] Fatal error:', error);
    process.exit(1);
  });
}

module.exports = DockerAgentClient;

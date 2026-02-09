const { EventEmitter } = require('events');

class AgentRegistry extends EventEmitter {
  constructor() {
    super();
    this.agents = new Map(); // agentId -> agent data
    this.connections = new Map(); // agentId -> WebSocket connection
    this.messageQueue = new Map(); // agentId -> queued messages
  }

  /**
   * Register a new agent
   * @param {string} agentId - Agent identifier
   * @param {object} metadata - Agent metadata
   * @returns {object} Registered agent data
   */
  register(agentId, metadata = {}) {
    const agent = {
      id: agentId,
      status: 'offline',
      registeredAt: Date.now(),
      lastSeen: null,
      lastHealthCheck: null,
      metadata: {
        type: metadata.type || 'generic',
        capabilities: metadata.capabilities || [],
        cpu: metadata.cpu,
        memory: metadata.memory,
        disk: metadata.disk,
        ...metadata
      },
      stats: {
        tasksReceived: 0,
        tasksCompleted: 0,
        tasksFailed: 0,
        messagesReceived: 0,
        messagesSent: 0
      },
      health: {
        cpu: null,
        memory: null,
        disk: null,
        uptime: null
      },
      currentTasks: []
    };

    this.agents.set(agentId, agent);
    this.messageQueue.set(agentId, []);
    
    this.emit('agent:registered', agent);
    
    return agent;
  }

  /**
   * Deregister an agent
   * @param {string} agentId - Agent identifier
   * @returns {boolean} True if deregistered, false if not found
   */
  deregister(agentId) {
    const agent = this.agents.get(agentId);
    if (!agent) {
      return false;
    }

    this.disconnect(agentId);
    this.agents.delete(agentId);
    this.messageQueue.delete(agentId);
    
    this.emit('agent:deregistered', agent);
    
    return true;
  }

  /**
   * Mark agent as connected
   * @param {string} agentId - Agent identifier
   * @param {WebSocket} ws - WebSocket connection
   */
  connect(agentId, ws) {
    const agent = this.agents.get(agentId);
    if (!agent) {
      throw new Error(`Agent ${agentId} not registered`);
    }

    agent.status = 'online';
    agent.lastSeen = Date.now();
    this.connections.set(agentId, ws);
    
    this.emit('agent:connected', agent);
    
    // Send queued messages
    this.flushMessageQueue(agentId);
  }

  /**
   * Mark agent as disconnected
   * @param {string} agentId - Agent identifier
   */
  disconnect(agentId) {
    const agent = this.agents.get(agentId);
    if (agent) {
      agent.status = 'offline';
      agent.lastSeen = Date.now();
      this.emit('agent:disconnected', agent);
    }
    
    this.connections.delete(agentId);
  }

  /**
   * Get agent by ID
   * @param {string} agentId - Agent identifier
   * @returns {object|null} Agent data or null
   */
  get(agentId) {
    return this.agents.get(agentId) || null;
  }

  /**
   * Get all agents
   * @returns {Array} Array of agent data
   */
  getAll() {
    return Array.from(this.agents.values());
  }

  /**
   * Get online agents
   * @returns {Array} Array of online agents
   */
  getOnline() {
    return this.getAll().filter(a => a.status === 'online');
  }

  /**
   * Update agent health data
   * @param {string} agentId - Agent identifier
   * @param {object} health - Health data
   */
  updateHealth(agentId, health) {
    const agent = this.agents.get(agentId);
    if (!agent) {
      return;
    }

    agent.health = { ...agent.health, ...health };
    agent.lastHealthCheck = Date.now();
    agent.lastSeen = Date.now();
    
    this.emit('agent:health', agent);
  }

  /**
   * Add a task to agent's current tasks
   * @param {string} agentId - Agent identifier
   * @param {object} task - Task data
   */
  addTask(agentId, task) {
    const agent = this.agents.get(agentId);
    if (!agent) {
      return;
    }

    agent.currentTasks.push(task);
    agent.stats.tasksReceived++;
  }

  /**
   * Remove a task from agent's current tasks
   * @param {string} agentId - Agent identifier
   * @param {string} taskId - Task ID
   * @param {boolean} success - Whether task succeeded
   */
  removeTask(agentId, taskId, success = true) {
    const agent = this.agents.get(agentId);
    if (!agent) {
      return;
    }

    agent.currentTasks = agent.currentTasks.filter(t => t.id !== taskId);
    
    if (success) {
      agent.stats.tasksCompleted++;
    } else {
      agent.stats.tasksFailed++;
    }
  }

  /**
   * Queue a message for offline agent
   * @param {string} agentId - Agent identifier
   * @param {object} message - Message to queue
   */
  queueMessage(agentId, message) {
    const queue = this.messageQueue.get(agentId);
    if (queue) {
      queue.push(message);
    }
  }

  /**
   * Flush message queue for an agent
   * @param {string} agentId - Agent identifier
   */
  flushMessageQueue(agentId) {
    const queue = this.messageQueue.get(agentId);
    const ws = this.connections.get(agentId);
    
    if (!queue || !ws || queue.length === 0) {
      return;
    }

    while (queue.length > 0) {
      const message = queue.shift();
      try {
        ws.send(JSON.stringify(message));
      } catch (error) {
        console.error(`Failed to send queued message to ${agentId}:`, error);
        // Put it back in the queue
        queue.unshift(message);
        break;
      }
    }
  }

  /**
   * Get WebSocket connection for agent
   * @param {string} agentId - Agent identifier
   * @returns {WebSocket|null} WebSocket connection or null
   */
  getConnection(agentId) {
    return this.connections.get(agentId) || null;
  }

  /**
   * Check for stale agents (no health check in timeout period)
   * @param {number} timeout - Timeout in milliseconds
   * @returns {Array} Array of stale agent IDs
   */
  getStaleAgents(timeout = 2 * 60 * 1000) { // Default 2 minutes
    const now = Date.now();
    const stale = [];

    for (const [agentId, agent] of this.agents) {
      if (agent.status === 'online' && agent.lastHealthCheck) {
        if (now - agent.lastHealthCheck > timeout) {
          stale.push(agentId);
        }
      }
    }

    return stale;
  }
}

module.exports = AgentRegistry;

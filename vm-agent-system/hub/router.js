const { v4: uuidv4 } = require('uuid');

class MessageRouter {
  constructor(registry) {
    this.registry = registry;
    this.deadLetterQueue = [];
    this.messageHistory = new Map(); // messageId -> message (for tracking)
    this.maxHistorySize = 1000;
  }

  /**
   * Route a message from sender to recipient
   * @param {object} message - Message to route
   * @returns {boolean} True if delivered or queued, false if failed
   */
  route(message) {
    // Validate message
    if (!this.validateMessage(message)) {
      console.error('Invalid message format:', message);
      return false;
    }

    // Ensure message has an ID
    if (!message.id) {
      message.id = uuidv4();
    }

    // Add timestamp if not present
    if (!message.timestamp) {
      message.timestamp = Date.now();
    }

    // Store in history
    this.addToHistory(message);

    // Handle broadcast
    if (message.to === 'broadcast' || message.to === '*') {
      return this.broadcast(message);
    }

    // Route to specific recipient
    const recipient = message.to;
    const connection = this.registry.getConnection(recipient);

    if (connection && connection.readyState === 1) { // WebSocket.OPEN
      try {
        connection.send(JSON.stringify(message));
        
        // Update stats
        const agent = this.registry.get(recipient);
        if (agent) {
          agent.stats.messagesReceived++;
        }
        
        return true;
      } catch (error) {
        console.error(`Failed to send message to ${recipient}:`, error);
        this.handleFailedDelivery(message, error);
        return false;
      }
    } else {
      // Agent is offline, queue the message
      this.registry.queueMessage(recipient, message);
      return true;
    }
  }

  /**
   * Broadcast a message to all connected agents
   * @param {object} message - Message to broadcast
   * @returns {boolean} True if sent to at least one agent
   */
  broadcast(message) {
    const onlineAgents = this.registry.getOnline();
    let sentCount = 0;

    for (const agent of onlineAgents) {
      // Don't send to the sender
      if (agent.id === message.from) {
        continue;
      }

      const connection = this.registry.getConnection(agent.id);
      if (connection && connection.readyState === 1) {
        try {
          connection.send(JSON.stringify(message));
          agent.stats.messagesReceived++;
          sentCount++;
        } catch (error) {
          console.error(`Failed to broadcast to ${agent.id}:`, error);
        }
      }
    }

    return sentCount > 0;
  }

  /**
   * Send a task to an agent
   * @param {string} agentId - Target agent ID
   * @param {object} task - Task payload
   * @param {string} from - Sender ID (default: 'host')
   * @returns {string} Task ID
   */
  sendTask(agentId, task, from = 'host') {
    const taskId = task.id || uuidv4();
    
    const message = {
      id: uuidv4(),
      from,
      to: agentId,
      type: 'task',
      timestamp: Date.now(),
      payload: {
        taskId,
        ...task
      }
    };

    // Track task in registry
    this.registry.addTask(agentId, {
      id: taskId,
      type: task.type,
      startedAt: Date.now(),
      payload: task
    });

    this.route(message);
    
    return taskId;
  }

  /**
   * Validate message format
   * @param {object} message - Message to validate
   * @returns {boolean} True if valid
   */
  validateMessage(message) {
    if (!message || typeof message !== 'object') {
      return false;
    }

    // Required fields
    if (!message.from || !message.to || !message.type) {
      return false;
    }

    // Valid types
    const validTypes = ['task', 'response', 'health', 'log', 'status', 'error'];
    if (!validTypes.includes(message.type)) {
      return false;
    }

    return true;
  }

  /**
   * Handle failed message delivery
   * @param {object} message - Failed message
   * @param {Error} error - Error that occurred
   */
  handleFailedDelivery(message, error) {
    this.deadLetterQueue.push({
      message,
      error: error.message,
      timestamp: Date.now()
    });

    // Limit dead letter queue size
    if (this.deadLetterQueue.length > 1000) {
      this.deadLetterQueue.shift();
    }
  }

  /**
   * Add message to history
   * @param {object} message - Message to add
   */
  addToHistory(message) {
    this.messageHistory.set(message.id, message);

    // Limit history size
    if (this.messageHistory.size > this.maxHistorySize) {
      const firstKey = this.messageHistory.keys().next().value;
      this.messageHistory.delete(firstKey);
    }
  }

  /**
   * Get message from history
   * @param {string} messageId - Message ID
   * @returns {object|null} Message or null
   */
  getFromHistory(messageId) {
    return this.messageHistory.get(messageId) || null;
  }

  /**
   * Get dead letter queue
   * @returns {Array} Dead letter queue
   */
  getDeadLetterQueue() {
    return [...this.deadLetterQueue];
  }

  /**
   * Clear dead letter queue
   */
  clearDeadLetterQueue() {
    this.deadLetterQueue = [];
  }

  /**
   * Get routing statistics
   * @returns {object} Statistics
   */
  getStats() {
    return {
      historySize: this.messageHistory.size,
      deadLetterQueueSize: this.deadLetterQueue.length,
      totalAgents: this.registry.getAll().length,
      onlineAgents: this.registry.getOnline().length
    };
  }
}

module.exports = MessageRouter;

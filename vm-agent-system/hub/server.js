#!/usr/bin/env node

const http = require('http');
const express = require('express');
const WebSocket = require('ws');
const { v4: uuidv4 } = require('uuid');
const promClient = require('prom-client');
const path = require('path');
const fs = require('fs');

const AuthManager = require('./auth');
const AgentRegistry = require('./agent-registry');
const MessageRouter = require('./router');

// Configuration
const WS_PORT = process.env.WS_PORT || 9090;
const HTTP_PORT = process.env.HTTP_PORT || 9091;
const HEALTH_CHECK_INTERVAL = 30000; // 30 seconds
const STALE_AGENT_TIMEOUT = 120000; // 2 minutes

// Initialize components
const auth = new AuthManager();
const registry = new AgentRegistry();
const router = new MessageRouter(registry);

// Prometheus metrics
const promRegister = new promClient.Registry();
promClient.collectDefaultMetrics({ register: promRegister });

const messageCounter = new promClient.Counter({
  name: 'vm_hub_messages_total',
  help: 'Total number of messages routed',
  labelNames: ['type', 'status'],
  registers: [promRegister]
});

const agentGauge = new promClient.Gauge({
  name: 'vm_hub_agents',
  help: 'Number of agents by status',
  labelNames: ['status'],
  registers: [promRegister]
});

const taskGauge = new promClient.Gauge({
  name: 'vm_hub_active_tasks',
  help: 'Number of active tasks',
  registers: [promRegister]
});

// Express app for HTTP API
const app = express();
app.use(express.json());

// CORS middleware
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  if (req.method === 'OPTIONS') {
    return res.sendStatus(200);
  }
  next();
});

// Logging middleware
app.use((req, res, next) => {
  console.log(`[HTTP] ${req.method} ${req.path}`);
  next();
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    uptime: process.uptime(),
    timestamp: Date.now(),
    agents: {
      total: registry.getAll().length,
      online: registry.getOnline().length
    }
  });
});

// Metrics endpoint
app.get('/metrics', async (req, res) => {
  res.set('Content-Type', promRegister.contentType);
  res.end(await promRegister.metrics());
});

// Register new agent
app.post('/agents/register', (req, res) => {
  const { agentId, metadata } = req.body;

  if (!agentId) {
    return res.status(400).json({ error: 'agentId is required' });
  }

  try {
    const agent = registry.register(agentId, metadata);
    const token = auth.generateToken(agentId);

    console.log(`[REGISTRY] Registered agent: ${agentId}`);

    res.json({
      agent,
      token,
      wsUrl: `ws://localhost:${WS_PORT}/agent/${agentId}/${token}`
    });
  } catch (error) {
    console.error(`[REGISTRY] Failed to register agent ${agentId}:`, error);
    res.status(500).json({ error: error.message });
  }
});

// List all agents
app.get('/agents', (req, res) => {
  const agents = registry.getAll();
  res.json({ agents });
});

// Get agent status
app.get('/agents/:id/status', (req, res) => {
  const agent = registry.get(req.params.id);
  
  if (!agent) {
    return res.status(404).json({ error: 'Agent not found' });
  }

  res.json({ agent });
});

// Send task to agent
app.post('/agents/:id/task', (req, res) => {
  const agentId = req.params.id;
  const task = req.body;

  const agent = registry.get(agentId);
  if (!agent) {
    return res.status(404).json({ error: 'Agent not found' });
  }

  try {
    const taskId = router.sendTask(agentId, task);
    console.log(`[TASK] Sent task ${taskId} to agent ${agentId}`);
    
    res.json({ taskId, status: 'sent' });
  } catch (error) {
    console.error(`[TASK] Failed to send task to ${agentId}:`, error);
    res.status(500).json({ error: error.message });
  }
});

// Deregister agent
app.delete('/agents/:id', (req, res) => {
  const agentId = req.params.id;
  
  if (registry.deregister(agentId)) {
    auth.revokeAgentTokens(agentId);
    console.log(`[REGISTRY] Deregistered agent: ${agentId}`);
    res.json({ status: 'deregistered' });
  } else {
    res.status(404).json({ error: 'Agent not found' });
  }
});

// Get dead letter queue
app.get('/admin/dlq', (req, res) => {
  res.json({ deadLetterQueue: router.getDeadLetterQueue() });
});

// Clear dead letter queue
app.delete('/admin/dlq', (req, res) => {
  router.clearDeadLetterQueue();
  res.json({ status: 'cleared' });
});

// Get routing stats
app.get('/admin/stats', (req, res) => {
  res.json({
    router: router.getStats(),
    agents: registry.getAll().map(a => ({
      id: a.id,
      status: a.status,
      stats: a.stats,
      currentTasks: a.currentTasks.length
    }))
  });
});

// Create HTTP server
const httpServer = http.createServer(app);

// Create WebSocket server
const wss = new WebSocket.Server({ noServer: true });

// Handle WebSocket upgrade
httpServer.on('upgrade', (request, socket, head) => {
  const url = new URL(request.url, `ws://localhost:${WS_PORT}`);
  const pathParts = url.pathname.split('/');

  if (pathParts[1] === 'agent' && pathParts.length === 4) {
    const agentId = pathParts[2];
    const token = pathParts[3];

    // Authenticate
    const tokenData = auth.validateToken(token);
    if (!tokenData || tokenData.agentId !== agentId) {
      socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n');
      socket.destroy();
      return;
    }

    wss.handleUpgrade(request, socket, head, (ws) => {
      wss.emit('connection', ws, request, agentId);
    });
  } else {
    socket.write('HTTP/1.1 404 Not Found\r\n\r\n');
    socket.destroy();
  }
});

// Handle WebSocket connections
wss.on('connection', (ws, request, agentId) => {
  console.log(`[WS] Agent connected: ${agentId}`);
  
  registry.connect(agentId, ws);

  ws.on('message', (data) => {
    try {
      const message = JSON.parse(data.toString());
      
      console.log(`[WS] Message from ${agentId}:`, message.type);

      // Update message stats
      messageCounter.inc({ type: message.type, status: 'received' });

      // Handle different message types
      switch (message.type) {
        case 'health':
          registry.updateHealth(agentId, message.payload);
          break;

        case 'response':
          // Task response
          if (message.payload.taskId) {
            const success = message.payload.success !== false;
            registry.removeTask(agentId, message.payload.taskId, success);
          }
          router.route(message);
          break;

        case 'log':
          // Just route the log message
          router.route(message);
          break;

        default:
          // Route other messages
          router.route(message);
      }

      // Update agent stats
      const agent = registry.get(agentId);
      if (agent) {
        agent.stats.messagesSent++;
      }

    } catch (error) {
      console.error(`[WS] Error processing message from ${agentId}:`, error);
      messageCounter.inc({ type: 'unknown', status: 'error' });
    }
  });

  ws.on('close', () => {
    console.log(`[WS] Agent disconnected: ${agentId}`);
    registry.disconnect(agentId);
  });

  ws.on('error', (error) => {
    console.error(`[WS] WebSocket error for ${agentId}:`, error);
  });

  // Send welcome message
  ws.send(JSON.stringify({
    type: 'status',
    from: 'host',
    to: agentId,
    timestamp: Date.now(),
    payload: {
      status: 'connected',
      message: 'Welcome to VM Hub'
    }
  }));
});

// Start HTTP server
httpServer.listen(HTTP_PORT, () => {
  console.log(`[HTTP] API server listening on port ${HTTP_PORT}`);
  console.log(`[WS] WebSocket server listening on port ${WS_PORT}`);
});

// Start WebSocket server (shares port with HTTP for upgrade)
const wsServer = http.createServer();
wss.on('connection', (ws) => {
  console.log('[WS] New WebSocket connection');
});

wsServer.on('upgrade', (request, socket, head) => {
  httpServer.emit('upgrade', request, socket, head);
});

wsServer.listen(WS_PORT, () => {
  console.log(`[WS] WebSocket port ${WS_PORT} ready`);
});

// Periodic tasks
setInterval(() => {
  // Clean up expired tokens
  const cleaned = auth.cleanupExpired();
  if (cleaned > 0) {
    console.log(`[AUTH] Cleaned up ${cleaned} expired tokens`);
  }

  // Check for stale agents
  const stale = registry.getStaleAgents(STALE_AGENT_TIMEOUT);
  if (stale.length > 0) {
    console.log(`[HEALTH] Found ${stale.length} stale agents:`, stale);
    stale.forEach(agentId => {
      registry.disconnect(agentId);
    });
  }

  // Update metrics
  const agents = registry.getAll();
  const onlineCount = agents.filter(a => a.status === 'online').length;
  const offlineCount = agents.length - onlineCount;
  
  agentGauge.set({ status: 'online' }, onlineCount);
  agentGauge.set({ status: 'offline' }, offlineCount);

  const totalTasks = agents.reduce((sum, a) => sum + a.currentTasks.length, 0);
  taskGauge.set(totalTasks);

}, HEALTH_CHECK_INTERVAL);

// Graceful shutdown
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);

function shutdown() {
  console.log('\n[SHUTDOWN] Gracefully shutting down...');
  
  // Close all WebSocket connections
  wss.clients.forEach(ws => {
    ws.close(1000, 'Server shutting down');
  });

  // Close servers
  httpServer.close(() => {
    console.log('[SHUTDOWN] HTTP server closed');
  });

  wsServer.close(() => {
    console.log('[SHUTDOWN] WebSocket server closed');
    process.exit(0);
  });

  // Force exit after 10 seconds
  setTimeout(() => {
    console.log('[SHUTDOWN] Forcing exit');
    process.exit(1);
  }, 10000);
}

console.log('='.repeat(60));
console.log('VM Agent Hub Server');
console.log('='.repeat(60));
console.log(`HTTP API: http://localhost:${HTTP_PORT}`);
console.log(`WebSocket: ws://localhost:${WS_PORT}`);
console.log(`Metrics: http://localhost:${HTTP_PORT}/metrics`);
console.log('='.repeat(60));

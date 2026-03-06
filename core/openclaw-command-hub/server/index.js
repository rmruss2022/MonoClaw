#!/usr/bin/env node
/**
 * OpenClaw Command Hub - Express Backend API
 * Provides REST API + SSE for real-time service monitoring
 */

const express = require('express');
const cors = require('cors');
const { exec } = require('child_process');
const { promisify } = require('util');
const fs = require('fs').promises;
const path = require('path');

const execAsync = promisify(exec);

const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(cors());
app.use(express.json());

// Service definitions
const SERVICES = [
  { id: 'voice-server', name: 'Voice Server', port: 18790, path: '/.openclaw/voice-server' },
  { id: 'token-tracker', name: 'Token Tracker', port: 18791, path: '/.openclaw/workspace/MonoClaw/tokens' },
  { id: 'context-manager', name: 'Context Manager', port: 18792, path: '/.openclaw/workspace' },
  { id: 'token-api', name: 'Token API', port: 18794, path: '/.openclaw/workspace/MonoClaw/tokens' },
  { id: 'mission-control', name: 'Mission Control', port: 18795, path: '/.openclaw/workspace/mission-control' },
  { id: 'activity-hub', name: 'Activity Hub', port: 18796, path: '/.openclaw/workspace/activity-hub' },
  { id: 'agent-swarm', name: 'Agent Swarm', port: 18798, path: '/.openclaw/workspace/agent-swarm-template' },
  { id: 'monoclaw', name: 'MonoClaw', port: 18802, path: '/.openclaw/workspace/MonoClaw' },
  { id: 'jobs-dashboard', name: 'Jobs Dashboard', port: 3003, path: '/.openclaw/workspace/jobs' },
  { id: 'raves-dashboard', name: 'Raves Dashboard', port: 3004, path: '/.openclaw/workspace/raves' },
  { id: 'arbitrage-scanner', name: 'Arbitrage Scanner', port: 3005, path: '/.openclaw/workspace/arbitrage-scanner' },
];

// Check if a service is running
async function checkServiceStatus(port) {
  try {
    const { stdout } = await execAsync(`lsof -iTCP:${port} -sTCP:LISTEN -t`);
    return stdout.trim() ? 'running' : 'stopped';
  } catch (error) {
    return 'stopped';
  }
}

// Get service health
async function getServiceHealth(port) {
  try {
    const response = await fetch(`http://localhost:${port}/health`, { 
      signal: AbortSignal.timeout(2000) 
    });
    return response.ok ? 'healthy' : 'degraded';
  } catch {
    return 'unhealthy';
  }
}

// Get service PID
async function getServicePID(port) {
  try {
    const { stdout } = await execAsync(`lsof -iTCP:${port} -sTCP:LISTEN -t`);
    return parseInt(stdout.trim()) || null;
  } catch {
    return null;
  }
}

// GET /api/services - List all services with status
app.get('/api/services', async (req, res) => {
  try {
    const services = await Promise.all(
      SERVICES.map(async (service) => {
        const status = await checkServiceStatus(service.port);
        const health = status === 'running' ? await getServiceHealth(service.port) : 'stopped';
        const pid = status === 'running' ? await getServicePID(service.port) : null;

        return {
          ...service,
          status,
          health,
          pid,
          lastCheck: new Date().toISOString(),
        };
      })
    );

    res.json({ services });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// GET /api/services/:id - Get single service details
app.get('/api/services/:id', async (req, res) => {
  const service = SERVICES.find(s => s.id === req.params.id);
  if (!service) {
    return res.status(404).json({ error: 'Service not found' });
  }

  try {
    const status = await checkServiceStatus(service.port);
    const health = status === 'running' ? await getServiceHealth(service.port) : 'stopped';
    const pid = status === 'running' ? await getServicePID(service.port) : null;

    res.json({
      ...service,
      status,
      health,
      pid,
      lastCheck: new Date().toISOString(),
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// POST /api/services/:id/restart - Restart a service
app.post('/api/services/:id/restart', async (req, res) => {
  const service = SERVICES.find(s => s.id === req.params.id);
  if (!service) {
    return res.status(404).json({ error: 'Service not found' });
  }

  try {
    // This is a placeholder - actual implementation would use LaunchAgent controls
    res.json({ 
      success: true, 
      message: `Restart command sent for ${service.name}`,
      note: 'Actual restart logic needs LaunchAgent integration'
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// GET /api/health - Overall system health
app.get('/api/health', async (req, res) => {
  try {
    const statuses = await Promise.all(
      SERVICES.map(s => checkServiceStatus(s.port))
    );

    const healthy = statuses.filter(s => s === 'running').length;
    const total = SERVICES.length;

    res.json({
      status: healthy === total ? 'healthy' : healthy > 0 ? 'degraded' : 'unhealthy',
      services: {
        healthy,
        unhealthy: total - healthy,
        total,
      },
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// GET /api/events - SSE endpoint for real-time updates
app.get('/api/events', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  // Send initial connection event
  res.write(`data: ${JSON.stringify({ type: 'connected', timestamp: Date.now() })}\n\n`);

  // Poll services every 5 seconds
  const interval = setInterval(async () => {
    try {
      const services = await Promise.all(
        SERVICES.map(async (service) => {
          const status = await checkServiceStatus(service.port);
          return { id: service.id, status };
        })
      );

      res.write(`data: ${JSON.stringify({ type: 'service-status', services, timestamp: Date.now() })}\n\n`);
    } catch (error) {
      console.error('SSE error:', error);
    }
  }, 5000);

  req.on('close', () => {
    clearInterval(interval);
  });
});

// GET /api/tokens - Token usage data (mock for now)
app.get('/api/tokens', async (req, res) => {
  try {
    // Read from token-costs.db if available
    const dbPath = path.join(process.env.HOME, '.openclaw/workspace/MonoClaw/tokens/token-costs.db');
    
    // Mock data for now
    res.json({
      timeRange: '24h',
      dataPoints: [
        { timestamp: new Date(Date.now() - 3600000).toISOString(), total: 3579, cost: 0.10 },
        { timestamp: new Date().toISOString(), total: 4123, cost: 0.12 },
      ],
      summary: {
        total: 125000,
        cost: 34.25,
      },
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Start server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`✅ OpenClaw Command Hub API running on http://localhost:${PORT}`);
  console.log(`📊 Health: http://localhost:${PORT}/api/health`);
  console.log(`🔄 SSE: http://localhost:${PORT}/api/events`);
});

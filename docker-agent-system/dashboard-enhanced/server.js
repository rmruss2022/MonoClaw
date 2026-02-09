#!/usr/bin/env node

const express = require('express');
const cors = require('cors');
const Docker = require('dockerode');
const http = require('http');
const https = require('https');
const path = require('path');
const fs = require('fs');

// Configuration
const PORT = process.env.PORT || 9092;
const GATEWAY_URL = process.env.GATEWAY_URL || 'http://localhost:18787';

const app = express();
const docker = new Docker();

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Logging
app.use((req, res, next) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
  next();
});

/**
 * Fetch OpenClaw sessions from gateway
 * Note: This is a placeholder - actual gateway API may differ
 */
async function fetchOpenClawSessions() {
  return new Promise((resolve, reject) => {
    const url = new URL('/api/sessions', GATEWAY_URL);
    const client = url.protocol === 'https:' ? https : http;

    const req = client.get(url.toString(), (res) => {
      let data = '';
      
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        if (res.statusCode === 200) {
          try {
            resolve(JSON.parse(data));
          } catch (err) {
            console.error('[GATEWAY] Failed to parse sessions:', err);
            resolve({ sessions: [] });
          }
        } else {
          console.warn(`[GATEWAY] API returned ${res.statusCode}, using mock data`);
          // Return mock data if API not available
          resolve(getMockSessions());
        }
      });
    });

    req.on('error', (err) => {
      console.error('[GATEWAY] Failed to fetch sessions:', err.message);
      // Return mock data on error
      resolve(getMockSessions());
    });

    req.setTimeout(5000, () => {
      req.destroy();
      resolve(getMockSessions());
    });
  });
}

/**
 * Mock sessions data for development/fallback
 */
function getMockSessions() {
  return {
    sessions: [
      {
        id: 'main',
        label: 'agent:main:main',
        model: 'anthropic/claude-sonnet-4-5',
        status: 'active',
        parent: null,
        created: Date.now() - 3600000,
        tokenUsage: { input: 15000, output: 3000 }
      }
    ]
  };
}

/**
 * Fetch Docker containers
 */
async function fetchDockerContainers() {
  try {
    const containers = await docker.listContainers({ all: true });
    
    // Filter for OpenClaw agent containers
    const agentContainers = containers.filter(c => 
      c.Names.some(n => n.includes('openclaw-agent')) ||
      (c.Labels && c.Labels['openclaw.agent'] === 'true')
    );

    // Get detailed info for each container
    const details = await Promise.all(
      agentContainers.map(async (c) => {
        try {
          const container = docker.getContainer(c.Id);
          const inspect = await container.inspect();
          const stats = await container.stats({ stream: false });

          return {
            id: c.Id.substring(0, 12),
            fullId: c.Id,
            name: c.Names[0].replace(/^\//, ''),
            state: c.State,
            status: c.Status,
            image: c.Image,
            created: c.Created,
            labels: c.Labels || {},
            ports: c.Ports,
            mounts: inspect.Mounts,
            network: Object.keys(inspect.NetworkSettings.Networks),
            // Resource usage
            cpu: calculateCPUPercent(stats),
            memory: calculateMemoryPercent(stats),
            networkIO: stats.networks ? calculateNetworkIO(stats.networks) : null
          };
        } catch (err) {
          console.error(`[DOCKER] Failed to get details for ${c.Id}:`, err.message);
          return {
            id: c.Id.substring(0, 12),
            name: c.Names[0].replace(/^\//, ''),
            state: c.State,
            status: c.Status,
            error: err.message
          };
        }
      })
    );

    return details;
  } catch (err) {
    console.error('[DOCKER] Failed to list containers:', err.message);
    return [];
  }
}

/**
 * Calculate CPU percentage from Docker stats
 */
function calculateCPUPercent(stats) {
  if (!stats.cpu_stats || !stats.precpu_stats) return 0;

  const cpuDelta = stats.cpu_stats.cpu_usage.total_usage - 
                   stats.precpu_stats.cpu_usage.total_usage;
  const systemDelta = stats.cpu_stats.system_cpu_usage - 
                      stats.precpu_stats.system_cpu_usage;
  const numCPUs = stats.cpu_stats.online_cpus || 1;

  if (systemDelta > 0 && cpuDelta > 0) {
    return (cpuDelta / systemDelta) * numCPUs * 100;
  }
  return 0;
}

/**
 * Calculate memory percentage from Docker stats
 */
function calculateMemoryPercent(stats) {
  if (!stats.memory_stats || !stats.memory_stats.limit) return 0;
  
  const used = stats.memory_stats.usage || 0;
  const limit = stats.memory_stats.limit;
  
  return (used / limit) * 100;
}

/**
 * Calculate network I/O
 */
function calculateNetworkIO(networks) {
  let rxBytes = 0;
  let txBytes = 0;

  Object.values(networks).forEach(net => {
    rxBytes += net.rx_bytes || 0;
    txBytes += net.tx_bytes || 0;
  });

  return { rx: rxBytes, tx: txBytes };
}

/**
 * Merge OpenClaw sessions with Docker container data
 */
function mergeSessionsAndContainers(sessions, containers) {
  const merged = [];

  // Add all sessions
  sessions.forEach(session => {
    const sessionData = {
      ...session,
      type: 'session',
      isDocker: false,
      docker: null
    };

    // Check if this session has a corresponding Docker container
    const dockerMatch = containers.find(c => 
      c.labels['openclaw.session'] === session.label ||
      c.name.includes(session.label) ||
      (session.label.includes('docker-agent') && c.name.includes(session.label.replace('docker-agent-', '')))
    );

    if (dockerMatch) {
      sessionData.isDocker = true;
      sessionData.docker = dockerMatch;
    }

    merged.push(sessionData);
  });

  // Add Docker containers that don't have a session match
  containers.forEach(container => {
    const alreadyMatched = merged.some(s => 
      s.docker && s.docker.id === container.id
    );

    if (!alreadyMatched) {
      merged.push({
        id: container.id,
        label: container.name,
        type: 'docker-only',
        isDocker: true,
        docker: container,
        status: container.state === 'running' ? 'active' : 'stopped'
      });
    }
  });

  return merged;
}

/**
 * Build session hierarchy tree
 */
function buildSessionTree(sessions) {
  const sessionMap = new Map();
  const roots = [];

  // Create map of all sessions
  sessions.forEach(s => sessionMap.set(s.id || s.label, s));

  // Build tree structure
  sessions.forEach(session => {
    if (!session.parent || session.parent === null) {
      // Root session
      session.children = [];
      roots.push(session);
    } else {
      // Child session
      const parent = sessionMap.get(session.parent);
      if (parent) {
        if (!parent.children) parent.children = [];
        parent.children.push(session);
      } else {
        // Parent not found, treat as root
        session.children = [];
        roots.push(session);
      }
    }
  });

  return roots;
}

// ============================================================================
// API Endpoints
// ============================================================================

/**
 * GET /api/health - Health check
 */
app.get('/api/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: Date.now(),
    gateway: GATEWAY_URL
  });
});

/**
 * GET /api/sessions - Get all sessions with Docker integration
 */
app.get('/api/sessions', async (req, res) => {
  try {
    const [sessionsData, containers] = await Promise.all([
      fetchOpenClawSessions(),
      fetchDockerContainers()
    ]);

    const sessions = sessionsData.sessions || [];
    const merged = mergeSessionsAndContainers(sessions, containers);
    const tree = buildSessionTree(merged);

    res.json({
      sessions: merged,
      tree,
      stats: {
        total: merged.length,
        docker: containers.length,
        active: merged.filter(s => s.status === 'active').length
      }
    });
  } catch (err) {
    console.error('[API] Failed to fetch sessions:', err);
    res.status(500).json({ error: err.message });
  }
});

/**
 * GET /api/docker/containers - Get Docker containers only
 */
app.get('/api/docker/containers', async (req, res) => {
  try {
    const containers = await fetchDockerContainers();
    res.json({ containers });
  } catch (err) {
    console.error('[API] Failed to fetch containers:', err);
    res.status(500).json({ error: err.message });
  }
});

/**
 * GET /api/docker/container/:id - Get specific container details
 */
app.get('/api/docker/container/:id', async (req, res) => {
  try {
    const container = docker.getContainer(req.params.id);
    const inspect = await container.inspect();
    res.json({ container: inspect });
  } catch (err) {
    console.error('[API] Failed to inspect container:', err);
    res.status(404).json({ error: 'Container not found' });
  }
});

// ============================================================================
// Start Server
// ============================================================================

app.listen(PORT, () => {
  console.log('='.repeat(60));
  console.log('OpenClaw Enhanced Dashboard');
  console.log('='.repeat(60));
  console.log(`Dashboard: http://localhost:${PORT}`);
  console.log(`API: http://localhost:${PORT}/api/sessions`);
  console.log(`Gateway: ${GATEWAY_URL}`);
  console.log('='.repeat(60));
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('\n[SHUTDOWN] Shutting down...');
  process.exit(0);
});

process.on('SIGINT', () => {
  console.log('\n[SHUTDOWN] Shutting down...');
  process.exit(0);
});

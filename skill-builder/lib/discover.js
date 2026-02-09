/**
 * Service Discovery Module
 * Discovers running services and their metadata
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const WORKSPACE = process.env.WORKSPACE || path.join(process.env.HOME, '.openclaw/workspace');
const LAUNCH_AGENTS = path.join(process.env.HOME, 'Library/LaunchAgents');

const KNOWN_SERVICES = {
  'voice-server': { port: 18790, type: 'http-api', healthPath: '/health' },
  'job-dashboard': { port: 18791, type: 'http-api' },
  'jobs': { port: 18791, type: 'http-api', alias: 'job-tracker' },
  'activity-hub': { port: 18796, type: 'http-api' },
  'raves': { port: 18800, type: 'nextjs-app' },
  'docker-agent-system': { port: null, type: 'docker-system' },
  'vm-agent-system': { port: null, type: 'vm-system' },
  'matts-claw-blog': { port: null, type: 'blog' },
  'token-collector': { port: null, type: 'background-service' },
  'token-tracker': { port: null, type: 'background-service' }
};

async function discoverServices() {
  const services = [];
  
  // Discover via LaunchAgents
  const launchAgentServices = discoverFromLaunchAgents();
  services.push(...launchAgentServices);
  
  // Discover via package.json files
  const packageServices = discoverFromPackages();
  services.push(...packageServices);
  
  // Check service status
  const servicesWithStatus = await checkServiceStatus(services);
  
  // Remove duplicates by name
  const unique = new Map();
  servicesWithStatus.forEach(s => {
    if (!unique.has(s.name) || s.status === 'running') {
      unique.set(s.name, s);
    }
  });
  
  return Array.from(unique.values());
}

function discoverFromLaunchAgents() {
  const services = [];
  
  try {
    const files = fs.readdirSync(LAUNCH_AGENTS)
      .filter(f => f.startsWith('com.openclaw.'));
    
    for (const file of files) {
      const name = file.replace('com.openclaw.', '').replace('.plist', '');
      const plistPath = path.join(LAUNCH_AGENTS, file);
      
      try {
        const plistContent = fs.readFileSync(plistPath, 'utf8');
        const programMatch = plistContent.match(/<string>([^<]+server[^<]*\.js|[^<]*index[^<]*\.js)<\/string>/i);
        const portMatch = plistContent.match(/port[=:](\d+)/);
        
        const metadata = KNOWN_SERVICES[name] || {};
        
        services.push({
          name,
          type: metadata.type || 'background-service',
          port: metadata.port || (portMatch ? parseInt(portMatch[1]) : null),
          source: 'launch-agent',
          plistPath,
          discoveredAt: new Date().toISOString()
        });
      } catch (e) {
        // Skip malformed plist
      }
    }
  } catch (e) {
    // LaunchAgents directory might not exist
  }
  
  return services;
}

function discoverFromPackages() {
  const services = [];
  
  try {
    const entries = fs.readdirSync(WORKSPACE, { withFileTypes: true });
    
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      
      const dirPath = path.join(WORKSPACE, entry.name);
      const packagePath = path.join(dirPath, 'package.json');
      const readmePath = path.join(dirPath, 'README.md');
      const serverPath = path.join(dirPath, 'server.js');
      
      if (!fs.existsSync(packagePath)) continue;
      
      try {
        const pkg = JSON.parse(fs.readFileSync(packagePath, 'utf8'));
        const metadata = KNOWN_SERVICES[entry.name] || {};
        
        const service = {
          name: entry.name,
          type: metadata.type || detectType(pkg),
          port: metadata.port || detectPort(pkg) || null,
          source: 'package.json',
          path: dirPath,
          hasReadme: fs.existsSync(readmePath),
          hasServer: fs.existsSync(serverPath),
          scripts: Object.keys(pkg.scripts || {}),
          dependencies: Object.keys(pkg.dependencies || {}),
          discoveredAt: new Date().toISOString()
        };
        
        services.push(service);
      } catch (e) {
        // Skip malformed package.json
      }
    }
  } catch (e) {
    // Workspace might not exist
  }
  
  return services;
}

function detectType(pkg) {
  const deps = { ...pkg.dependencies, ...pkg.devDependencies };
  
  if (deps['express'] || deps['fastify'] || deps['koa']) return 'http-api';
  if (deps['next'] || deps['react']) return 'nextjs-app';
  if (deps['dockerode'] || deps['ssh2']) return 'docker-system';
  if (deps['electron']) return 'electron-app';
  if (pkg.bin || pkg.main?.includes('cli')) return 'cli-tool';
  
  return 'node-package';
}

function detectPort(pkg) {
  // Look for port in scripts
  const scripts = JSON.stringify(pkg.scripts || {});
  const match = scripts.match(/port[=:](\d{4,5})/);
  return match ? parseInt(match[1]) : null;
}

async function checkServiceStatus(services) {
  const results = [];
  
  for (const service of services) {
    const result = { ...service };
    
    if (service.port) {
      result.status = await checkPortStatus(service.port);
    } else if (service.plistPath) {
      result.status = checkLaunchAgentStatus(service.plistPath);
    } else {
      result.status = 'unknown';
    }
    
    results.push(result);
  }
  
  return results;
}

async function checkPortStatus(port) {
  return new Promise((resolve) => {
    const net = require('net');
    const socket = new net.Socket();
    
    socket.setTimeout(2000);
    socket.once('connect', () => {
      socket.destroy();
      resolve('running');
    });
    socket.once('error', () => resolve('stopped'));
    socket.once('timeout', () => resolve('stopped'));
    
    socket.connect(port, '127.0.0.1');
  });
}

function checkLaunchAgentStatus(plistPath) {
  try {
    const label = path.basename(plistPath, '.plist');
    const output = execSync(`launchctl print gui/$(id - u)/${label} 2>&1`, { encoding: 'utf8', timeout: 5000 });
    return output.includes('state = running') ? 'running' : 'stopped';
  } catch (e) {
    return 'unknown';
  }
}

module.exports = {
  discoverServices,
  checkPortStatus,
  KNOWN_SERVICES
};

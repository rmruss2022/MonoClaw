#!/usr/bin/env node
/**
 * Vision Controller Service
 * Real-time hand gesture recognition for OpenClaw
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const PORT = 18799;
const BACKEND_PORT = 9000;
const BACKEND_DIR = path.join(__dirname, 'backend');
const FRONTEND_DIR = path.join(__dirname, 'frontend');

let backendProcess = null;
let restartCount = 0;
const MAX_RESTARTS = 10;

// Start Python backend with supervisor
function startBackend() {
  console.log('[Backend] Starting...');
  
  backendProcess = spawn('bash', ['-c', `cd ${BACKEND_DIR} && source venv/bin/activate && python3 -m uvicorn api.main:app --host 127.0.0.1 --port ${BACKEND_PORT}`], {
    stdio: ['ignore', 'pipe', 'pipe']
  });
  
  backendProcess.stdout.on('data', (data) => {
    const lines = data.toString().trim().split('\n');
    lines.forEach(line => {
      if (line.includes('CHANGE') || line.includes('ERROR') || line.includes('Application startup')) {
        console.log(`[Backend] ${line}`);
      }
    });
  });
  
  backendProcess.stderr.on('data', (data) => {
    const err = data.toString().trim();
    if (!err.includes('INFO:') && !err.includes('W0000')) {
      console.error(`[Backend] ${err}`);
    }
  });
  
  backendProcess.on('exit', (code) => {
    console.log(`[Backend] Process exited with code ${code}`);
    restartCount++;
    
    if (restartCount < MAX_RESTARTS) {
      console.log(`[Backend] Restarting in 3s (attempt ${restartCount}/${MAX_RESTARTS})...`);
      setTimeout(startBackend, 3000);
    } else {
      console.error(`[Backend] Max restarts reached, giving up`);
    }
  });
}

// MIME types
const mimeTypes = {
  '.html': 'text/html',
  '.js': 'text/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg'
};

// HTTP server for frontend
const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  
  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }
  
  const cleanUrl = req.url.split('?')[0];
  
  // Health check
  if (cleanUrl === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: 'ok',
      service: 'Vision Controller',
      backend: `http://127.0.0.1:${BACKEND_PORT}`,
      websocket: `ws://localhost:${BACKEND_PORT}/ws/gestures`
    }));
    return;
  }
  
  // Serve static files
  let filePath;
  if (cleanUrl === '/') {
    filePath = path.join(FRONTEND_DIR, 'index.html');
  } else if (cleanUrl.startsWith('/config/')) {
    filePath = path.join(__dirname, cleanUrl);
  } else {
    filePath = path.join(FRONTEND_DIR, cleanUrl);
  }
  
  const extname = path.extname(filePath);
  const contentType = mimeTypes[extname] || 'application/octet-stream';
  
  fs.readFile(filePath, (err, content) => {
    if (err) {
      if (err.code === 'ENOENT') {
        res.writeHead(404, { 'Content-Type': 'text/plain' });
        res.end('404 Not Found');
      } else {
        res.writeHead(500, { 'Content-Type': 'text/plain' });
        res.end('500 Internal Server Error');
      }
    } else {
      res.writeHead(200, { 'Content-Type': contentType });
      res.end(content);
    }
  });
});

// Start servers
startBackend();

server.listen(PORT, '127.0.0.1', () => {
  console.log(`[Frontend] Vision Controller running on http://127.0.0.1:${PORT}`);
  console.log(`[Frontend] Backend WebSocket: ws://localhost:${BACKEND_PORT}/ws/gestures`);
});

// Cleanup on exit
process.on('SIGINT', () => {
  console.log('\n[Shutdown] Stopping servers...');
  if (backendProcess) {
    backendProcess.kill();
  }
  process.exit(0);
});

process.on('SIGTERM', () => {
  if (backendProcess) {
    backendProcess.kill();
  }
  process.exit(0);
});

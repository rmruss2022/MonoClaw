#!/usr/bin/env node
/**
 * Job Dashboard Server
 * Serves the job search dashboard on localhost:18791
 * NOW WITH SQLITE PERSISTENCE
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const db = require('./lib/db');

const PORT = 18791;
const DIR = __dirname;

const MIME_TYPES = {
  '.html': 'text/html',
  '.css': 'text/css',
  '.js': 'application/javascript',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml'
};

const server = http.createServer((req, res) => {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  
  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }
  
  const cleanUrl = req.url.split('?')[0];
  
  // API endpoints
  if (cleanUrl === '/api/executions' && req.method === 'GET') {
    db.getRecentExecutions(100, (err, rows) => {
      if (err) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: err.message }));
        return;
      }
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: true, executions: rows }));
    });
    return;
  }
  
  if (cleanUrl === '/api/stats' && req.method === 'GET') {
    db.getJobStats((err, stats) => {
      if (err) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: err.message }));
        return;
      }
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: true, stats }));
    });
    return;
  }
  
  if (cleanUrl === '/api/log' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        const execution = JSON.parse(body);
        db.logExecution(execution, (err, id) => {
          if (err) {
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: err.message }));
            return;
          }
          res.writeHead(201, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ success: true, id }));
        });
      } catch (err) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Invalid JSON' }));
      }
    });
    return;
  }
  
  // Serve static files
  let filePath = req.url === '/' ? '/dashboard.html' : cleanUrl;
  const fullPath = path.join(DIR, filePath);
  const ext = path.extname(filePath);
  
  // Security: only serve files from this directory
  if (!fullPath.startsWith(DIR)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }
  
  fs.readFile(fullPath, (err, data) => {
    if (err) {
      res.writeHead(404);
      res.end('Not found');
      return;
    }
    
    res.writeHead(200, {
      'Content-Type': MIME_TYPES[ext] || 'text/plain',
      'Cache-Control': 'no-cache'
    });
    res.end(data);
  });
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`📊 Job Dashboard running at http://127.0.0.1:${PORT}`);
  console.log(`✅ SQLite persistence enabled`);
});

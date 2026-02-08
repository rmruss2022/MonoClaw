#!/usr/bin/env node
/**
 * NYC Raves Dashboard Server
 * NOW WITH SQLITE PERSISTENCE
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const os = require('os');
const db = require('./lib/db');

const PORT = 18793;
const ROOT_DIR = __dirname;
const START_TIME = Date.now();

// Request logging
const requestLog = [];
const MAX_LOG_SIZE = 50;

const mimeTypes = {
  '.html': 'text/html',
  '.json': 'application/json',
  '.js': 'text/javascript',
  '.css': 'text/css'
};

const server = http.createServer((req, res) => {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  
  // Handle OPTIONS preflight
  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }
  
  const cleanUrl = req.url.split('?')[0];
  
  // API endpoints
  if (cleanUrl === '/api/events' && req.method === 'GET') {
    db.getRecentEvents(100, (err, events) => {
      if (err) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: err.message }));
        return;
      }
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: true, events }));
    });
    return;
  }
  
  if (cleanUrl === '/api/events' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        const event = JSON.parse(body);
        db.insertEvent(event, (err, id) => {
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
  let filePath = path.join(ROOT_DIR, cleanUrl === '/' ? 'dashboard.html' : cleanUrl);
  const extname = path.extname(filePath);
  const contentType = mimeTypes[extname] || 'application/octet-stream';
  
  console.log(`[${new Date().toISOString()}] Request: ${req.url} -> ${filePath}`);
  
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
      res.writeHead(200, { 
        'Content-Type': contentType,
        'Access-Control-Allow-Origin': '*'
      });
      res.end(content);
    }
  });
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`🎵 NYC Raves Dashboard running at http://127.0.0.1:${PORT}`);
  console.log(`✅ SQLite persistence enabled`);
  console.log(`   Uptime: ${Math.floor((Date.now() - START_TIME) / 1000)}s`);
});

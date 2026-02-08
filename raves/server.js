#!/usr/bin/env node
/**
 * NYC Raves Dashboard Server
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const os = require('os');

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
  // Clean up query parameters from URL
  const cleanUrl = req.url.split('?')[0];
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
  console.log(`🎵 NYC Raves Dashboard running on http://localhost:${PORT}`);
});

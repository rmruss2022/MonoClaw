#!/usr/bin/env node
/**
 * Job Dashboard Server
 * Serves the job search dashboard on localhost:18791
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

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
  let filePath = req.url === '/' ? '/dashboard.html' : req.url;
  filePath = filePath.split('?')[0]; // Remove query string
  
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
});

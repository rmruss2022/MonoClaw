#!/usr/bin/env node
/**
 * NYC Raves Dashboard Server
 * SQLite persistence with week-based grouping
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const { getAllEvents, getEventsByWeek, getAllWeeks, getEventsGroupedByWeek } = require('./lib/db');

const PORT = 3004;
const ROOT_DIR = __dirname;
const START_TIME = Date.now();

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
  
  // API: Get all events
  if (cleanUrl === '/api/events' && req.method === 'GET') {
    try {
      const events = getAllEvents();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: true, events }));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }
  
  // API: Get events grouped by week
  if (cleanUrl === '/api/events/by-week' && req.method === 'GET') {
    try {
      const grouped = getEventsGroupedByWeek();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: true, weeks: grouped }));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }
  
  // API: Get all week start dates
  if (cleanUrl === '/api/weeks' && req.method === 'GET') {
    try {
      const weeks = getAllWeeks();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: true, weeks }));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }
  
  // API: Get events for a specific week
  if (cleanUrl.startsWith('/api/events/week/') && req.method === 'GET') {
    try {
      const weekStart = cleanUrl.replace('/api/events/week/', '');
      const events = getEventsByWeek(weekStart);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: true, weekStart, events }));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }
  
  // Serve static files
  let filePath = path.join(ROOT_DIR, cleanUrl === '/' ? 'dashboard.html' : cleanUrl);
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
  console.log(`📅 Week-based grouping active`);
  console.log(`   Uptime: ${Math.floor((Date.now() - START_TIME) / 1000)}s`);
});

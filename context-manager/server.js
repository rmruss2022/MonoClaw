#!/usr/bin/env node

const http = require('http');
const fs = require('fs');
const path = require('path');
const ContextManagerService = require('./context-manager-service');

const PORT = Number(process.env.CONTEXT_MANAGER_PORT || 18800);
const HOST = '127.0.0.1';
const service = new ContextManagerService();

function readRequestBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', (chunk) => body += chunk);
    req.on('end', () => resolve(body));
    req.on('error', reject);
  });
}

function writeJson(res, status, body) {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(body));
}

function handleError(res, error) {
  const code = error?.mapped?.code || error?.code || 'INTERNAL_ERROR';
  const status = code === 'VALIDATION_ERROR' ? 400 : 500;
  writeJson(res, status, {
    ok: false,
    requestId: error?.requestId || null,
    durationMs: error?.durationMs || 0,
    error: error?.mapped || { code, message: error?.message || 'Unknown error' },
  });
}

const server = http.createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }

  try {
    if (req.url === '/' || req.url === '/context' || req.url === '/context.html') {
      const html = fs.readFileSync(path.join(__dirname, 'context.html'), 'utf-8');
      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end(html);
      return;
    }

    if (req.url.startsWith('/api/context/report') && req.method === 'GET') {
      const url = new URL(req.url, `http://${req.headers.host}`);
      const agentId = url.searchParams.get('agent') || 'main';
      const result = await service.getReport(agentId);
      writeJson(res, 200, result);
      return;
    }

    if (req.url === '/api/context/prune' && req.method === 'POST') {
      const body = await readRequestBody(req);
      const payload = JSON.parse(body || '{}');
      const result = await service.runPrune({
        agentId: payload.agentId || 'main',
        olderThanMinutes: payload.olderThanMinutes ?? 60,
        apply: !!payload.apply,
      });
      writeJson(res, 200, result);
      return;
    }

    if (req.url === '/api/context/gateway-status' && req.method === 'GET') {
      const result = await service.getGatewayStatus();
      writeJson(res, 200, result);
      return;
    }

    if (req.url === '/api/context/diagnostics' && req.method === 'GET') {
      const result = await service.getDiagnostics();
      writeJson(res, 200, result);
      return;
    }

    if (req.url.startsWith('/api/context/trends') && req.method === 'GET') {
      const url = new URL(req.url, `http://${req.headers.host}`);
      const agentId = url.searchParams.get('agent') || 'main';
      const range = url.searchParams.get('range') || '7d';
      const result = service.getTrends(agentId, range);
      writeJson(res, 200, result);
      return;
    }

    if (req.url === '/api/context/maintenance/compact' && req.method === 'POST') {
      const result = service.compactStorage();
      writeJson(res, 200, result);
      return;
    }

    if (req.url.startsWith('/api/context/inspect') && req.method === 'GET') {
      const url = new URL(req.url, `http://${req.headers.host}`);
      const agentId = url.searchParams.get('agent') || 'main';
      const result = await service.getContextInspection(agentId);
      writeJson(res, 200, result);
      return;
    }

    if (req.url === '/api/context/agents' && req.method === 'GET') {
      const result = await service.getActiveAgents();
      writeJson(res, 200, result);
      return;
    }

    res.writeHead(404);
    res.end('Not found');
  } catch (error) {
    handleError(res, error);
  }
});

server.listen(PORT, HOST, () => {
  console.log(`Context Manager service running at http://${HOST}:${PORT}`);
});

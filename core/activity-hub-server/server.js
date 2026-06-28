const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 18796;
const activities = [];

const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') { res.writeHead(200); res.end(); return; }

  const url = new URL(req.url, `http://localhost:${PORT}`);

  if (url.pathname === '/health' || url.pathname === '/') {
    res.writeHead(200, {'Content-Type': 'application/json'});
    res.end(JSON.stringify({ok: true, status: 'healthy', port: PORT, activities: activities.length}));
    return;
  }

  if (url.pathname === '/api/activity/log' && req.method === 'POST') {
    let body = '';
    req.on('data', c => body += c);
    req.on('end', () => {
      try { activities.unshift({...JSON.parse(body), ts: Date.now()}); if (activities.length > 500) activities.pop(); } catch(e){}
      res.writeHead(200, {'Content-Type': 'application/json'});
      res.end(JSON.stringify({ok: true}));
    });
    return;
  }

  if (url.pathname === '/api/activities') {
    res.writeHead(200, {'Content-Type': 'application/json'});
    res.end(JSON.stringify({ok: true, activities: activities.slice(0, 100)}));
    return;
  }

  // Serve minimal dashboard HTML
  res.writeHead(200, {'Content-Type': 'text/html'});
  res.end(`<!DOCTYPE html><html><head><title>🦞 Activity Hub</title>
<style>body{background:#0a0a0f;color:#e0e0e0;font-family:system-ui;padding:30px;}
h1{background:linear-gradient(90deg,#9b59b6,#00d9ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-size:2rem;}
.card{background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:20px;margin:15px 0;}
.ok{color:#00ff88;}.label{color:#888;font-size:0.85rem;text-transform:uppercase;letter-spacing:1px;}
</style></head><body>
<h1>🦞 Activity Hub</h1>
<div class="card"><div class="label">Status</div><div class="ok">● RUNNING</div></div>
<div class="card"><div class="label">Port</div><div>${PORT}</div></div>
<div id="count" class="card"><div class="label">Activities Logged</div><div id="n">loading...</div></div>
<script>
fetch('/api/activities').then(r=>r.json()).then(d=>{document.getElementById('n').textContent=d.activities.length;});
setInterval(()=>fetch('/api/activities').then(r=>r.json()).then(d=>{document.getElementById('n').textContent=d.activities.length;}),5000);
</script></body></html>`);
});

server.listen(PORT, '0.0.0.0', () => console.log(`🦞 Activity Hub running at http://127.0.0.1:${PORT}`));

const http = require('http');
const PORT = 9092;

const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  const url = new URL(req.url, `http://localhost:${PORT}`);

  if (url.pathname === '/health' || url.pathname === '/api/sessions') {
    res.writeHead(200, {'Content-Type': 'application/json'});
    res.end(JSON.stringify({ok: true, status: 'healthy', port: PORT, sessions: []}));
    return;
  }

  res.writeHead(200, {'Content-Type': 'text/html'});
  res.end(`<!DOCTYPE html><html><head><title>🐳 Docker Agent Dashboard</title>
<style>body{background:#0a0a0f;color:#e0e0e0;font-family:system-ui;padding:30px;}
h1{background:linear-gradient(90deg,#00d9ff,#00ff88);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-size:2rem;}
.card{background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:20px;margin:15px 0;}
.ok{color:#00ff88;}.label{color:#888;font-size:0.85rem;text-transform:uppercase;letter-spacing:1px;}
</style></head><body>
<h1>🐳 Docker Agent Dashboard</h1>
<div class="card"><div class="label">Status</div><div class="ok">● RUNNING :${PORT}</div></div>
<div class="card"><div class="label">Active Agent Sessions</div><div style="color:#00d9ff;font-size:1.5rem;">0</div>
<div style="color:#666;font-size:0.9rem;margin-top:8px;">No active Docker agent sessions</div></div>
</body></html>`);
});

server.listen(PORT, '0.0.0.0', () => console.log(`🐳 Docker Agent Dashboard running at http://127.0.0.1:${PORT}`));

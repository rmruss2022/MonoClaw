#!/usr/bin/env python3
"""
Portfolio / Résumé site for Matthew Russell — public-facing.
Zero-dep Python stdlib server. Served at root so it maps cleanly onto a
Cloudflare tunnel (public) or a hub path.

Env:
  PORTFOLIO_PORT   (default 18824)
  PORTFOLIO_BASE   optional mount path (default "" = root)
"""
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORTFOLIO_PORT", "18824"))
BASE = (os.environ.get("PORTFOLIO_BASE", "").rstrip("/"))

PAGE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="theme-color" content="#0b0f14"/>
<title>Matthew Russell — Software Engineer</title>
<meta name="description" content="Matthew Russell — Software Engineer (AI & Full-Stack). Rust, React, AWS, agentic AI. Projects, experience, and contact."/>
<style>
  :root{--bg:#0b0f14;--panel:#121820;--panel2:#0e141b;--line:#1f2a36;--text:#e8eef5;--dim:#90a4b8;--accent:#22c55e;--accent2:#38bdf8}
  *{box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{margin:0;background:radial-gradient(1200px 600px at 70% -10%,#102033 0,var(--bg) 55%);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif;line-height:1.6}
  .wrap{max-width:880px;margin:0 auto;padding:0 20px}
  a{color:var(--accent2);text-decoration:none}
  a:hover{text-decoration:underline}
  /* hero */
  header{padding:64px 0 34px;border-bottom:1px solid var(--line)}
  .kicker{color:var(--accent);font-weight:700;letter-spacing:.14em;text-transform:uppercase;font-size:12px}
  h1{font-size:46px;line-height:1.05;margin:10px 0 6px;letter-spacing:-.02em}
  .role{font-size:20px;color:#c6d6e6;margin-bottom:6px}
  .loc{color:var(--dim);font-size:15px}
  .links{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px}
  .links a{display:inline-flex;align-items:center;gap:7px;background:var(--panel);border:1px solid var(--line);padding:9px 14px;border-radius:11px;color:var(--text);font-size:14px;font-weight:600}
  .links a:hover{border-color:#2b6cb0;text-decoration:none}
  .links a.primary{background:var(--accent);color:#04120a;border-color:transparent}
  section{padding:38px 0;border-bottom:1px solid var(--line)}
  h2{font-size:13px;text-transform:uppercase;letter-spacing:.12em;color:var(--dim);margin:0 0 20px;font-weight:700}
  .lead{font-size:18px;color:#cfe0ee;max-width:70ch}
  /* experience */
  .job{margin-bottom:26px}
  .job .jh{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px}
  .job .t{font-weight:700;font-size:17px}
  .job .c{color:var(--accent2);font-weight:600}
  .job .when{margin-left:auto;color:var(--dim);font-size:13px}
  .job ul{margin:8px 0 0;padding-left:18px}
  .job li{margin:4px 0;color:#c2d2e2;font-size:14.5px}
  /* projects */
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}
  .proj{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:16px;display:flex;flex-direction:column}
  .proj .pt{display:flex;align-items:center;gap:9px;font-weight:700;font-size:16px}
  .proj .em{font-size:19px}
  .proj p{margin:9px 0 12px;color:#c2d2e2;font-size:13.5px;flex:1}
  .stack{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}
  .chip{font-size:11px;color:var(--dim);border:1px solid var(--line);border-radius:999px;padding:2px 8px}
  .proj .pl{font-size:13px;font-weight:600}
  .proj .pl.live::before{content:"● ";color:var(--accent)}
  .skills{display:flex;flex-wrap:wrap;gap:8px}
  .skills .s{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:7px 11px;font-size:13px;color:#cfe0ee}
  .edu .t{font-weight:700}
  .edu .d{color:var(--dim);font-size:14px}
  footer{padding:34px 0 60px;color:var(--dim);font-size:13px;text-align:center}
  footer a{color:var(--accent2)}
  @media(max-width:560px){h1{font-size:34px}}
</style>
</head>
<body>
<header><div class="wrap">
  <div class="kicker">Software Engineer · AI &amp; Full-Stack</div>
  <h1>Matthew Russell</h1>
  <div class="role">I build fast, AI-driven products end to end — from Rust data engines to agentic apps.</div>
  <div class="loc">New York, NY</div>
  <div class="links">
    <a class="primary" href="mailto:mattrussellc@gmail.com">✉ Email</a>
    <a href="https://linkedin.com/in/matthewrussellc" target="_blank" rel="noopener">in · LinkedIn</a>
    <a href="#projects">↓ Projects</a>
    <a href="#experience">↓ Experience</a>
  </div>
</div></header>

<section id="about"><div class="wrap">
  <h2>About</h2>
  <p class="lead">Software engineer with a Virginia Tech background in Computer Science and Psychology, shipping across the stack: high-performance Rust analytics and messaging systems, React/TypeScript interfaces for large geospatial and financial datasets, AWS architecture, and a growing body of agentic-AI products. I like turning messy real-world data and vague ideas into fast, usable tools.</p>
</div></section>

<section id="experience"><div class="wrap">
  <h2>Experience</h2>

  <div class="job">
    <div class="jh"><span class="t">Software Engineer,</span><span class="c">AgriVaR</span><span class="when">Jun 2024 — Present</span></div>
    <ul>
      <li>Re-architected legacy systems for speed and redundancy on AWS for a big-data agricultural startup.</li>
      <li>Built high-performance React interfaces for large, multi-dimensional geospatial + time-series datasets — color mappings, segmentation, and interactive analysis.</li>
      <li>Designed a commodity-trading platform in React with streaming updates, data viz, and alerting across multiple financial/commodity products.</li>
      <li>Built granular geographic drawing/analysis tools letting farmers compare yield and revenue across regions and time ranges — targeting 20%+ future-harvest gains.</li>
    </ul>
  </div>

  <div class="job">
    <div class="jh"><span class="t">Software Engineer II,</span><span class="c">BitWave</span><span class="when">Jun 2023 — Jun 2024</span></div>
    <ul>
      <li>Built a Rust CQRS analytics engine for financial/crypto reporting — cut page load from 4s+ to under 1s.</li>
      <li>Developed an internal Rust messaging system for high-throughput events across distributed, cloud-deployed services.</li>
      <li>Engineered multi-chain balance + transaction indexing for a digital-asset platform, improving integrity and auditability of on-chain data.</li>
      <li>Orchestrated automated deployment + monitoring for token balances across 60+ chains, handling RPC/node and chain-specific edge cases.</li>
    </ul>
  </div>

  <div class="job">
    <div class="jh"><span class="t">Full-Stack Software Engineer,</span><span class="c">Unilever · Liquid I.V.</span><span class="when">Jul 2021 — Jun 2023</span></div>
    <ul>
      <li>Engineered enterprise logistics software for Unilever focused on simplicity, efficiency, and scale.</li>
      <li>Built a web app to monitor and forecast inventory and sales across warehouses, distribution centers, and retail nationwide.</li>
      <li>Designed React/TypeScript UIs with dynamic content loading; deployed a data pipeline on GraphQL, DynamoDB, AWS Lambda/SES, and Cognito.</li>
    </ul>
  </div>
</div></section>

<section id="projects"><div class="wrap">
  <h2>Selected Projects</h2>
  <div class="grid">
    <div class="proj"><div class="pt"><span class="em">🧭</span>Waypoint</div>
      <p>AI driving GPS: spoken turn-by-turn, plus an agentic assistant that understands natural requests, searches real-world POIs, and routes you there. Live "local guide" area briefings.</p>
      <div class="stack"><span class="chip">Gemini</span><span class="chip">OSRM</span><span class="chip">Leaflet</span><span class="chip">PWA</span></div>
      <div class="pl">Agentic AI · voice</div></div>

    <div class="proj"><div class="pt"><span class="em">🩺</span>Ora Health</div>
      <p>Agentic-AI iOS wellness app with a Multi-Vector Broadcast Architecture to carry on dynamic conversations; daily personalized meditations and mindset exercises.</p>
      <div class="stack"><span class="chip">React Native</span><span class="chip">Agentic AI</span><span class="chip">ElevenLabs</span></div>
      <div class="pl">iOS</div></div>

    <div class="proj"><div class="pt"><span class="em">⚡</span>Daylight</div>
      <p>Energy-management platform with live data visualization; 136/136 tests passing in production.</p>
      <div class="stack"><span class="chip">Django</span><span class="chip">React</span><span class="chip">Postgres</span><span class="chip">Redis</span></div>
      <a class="pl live" href="https://web-production-970f8.up.railway.app/" target="_blank" rel="noopener">Live demo ↗</a></div>

    <div class="proj"><div class="pt"><span class="em">🏠</span>openhome</div>
      <p>Self-hosted smart-home hub — real control of lights, music, and climate with a voice agent, running on a Raspberry Pi.</p>
      <div class="stack"><span class="chip">IoT</span><span class="chip">Spotify Connect</span><span class="chip">PWA</span></div>
      <div class="pl">Self-hosted</div></div>

    <div class="proj"><div class="pt"><span class="em">📈</span>Arbitrage Scanner</div>
      <p>Cross-platform prediction-market scanner (Polymarket, Kalshi) with fuzzy event matching and arbitrage detection.</p>
      <div class="stack"><span class="chip">TypeScript</span><span class="chip">Node</span><span class="chip">SQLite</span></div>
      <div class="pl">Fintech</div></div>

    <div class="proj"><div class="pt"><span class="em">🎵</span>Dropstick</div>
      <p>Offline Wi-Fi USB stick for peer-to-peer music sharing — no internet required.</p>
      <div class="stack"><span class="chip">Go</span><span class="chip">SQLite</span></div>
      <div class="pl">Systems</div></div>

    <div class="proj"><div class="pt"><span class="em">🪄</span>Doctor Strange Hand Lab</div>
      <p>Real-time hand-tracked visual FX — arcane shields and a GPU-deformed astral wireframe driven by webcam gestures.</p>
      <div class="stack"><span class="chip">Three.js</span><span class="chip">MediaPipe</span><span class="chip">WebGL</span></div>
      <div class="pl">Computer vision</div></div>

    <div class="proj"><div class="pt"><span class="em">👥</span>Rolodex</div>
      <p>Personal network CRM — contacts, follow-ups, a running reach-out queue, and relationship insights.</p>
      <div class="stack"><span class="chip">Python</span><span class="chip">SQLite</span></div>
      <div class="pl">Productivity</div></div>
  </div>
</div></section>

<section id="skills"><div class="wrap">
  <h2>Skills</h2>
  <div class="skills">
    <span class="s">Python</span><span class="s">TypeScript</span><span class="s">JavaScript</span><span class="s">Rust</span>
    <span class="s">Solidity</span><span class="s">Scala</span><span class="s">Java</span><span class="s">Swift</span><span class="s">C</span>
    <span class="s">React</span><span class="s">Next.js</span><span class="s">AWS</span><span class="s">Google Cloud</span>
    <span class="s">PyTorch</span><span class="s">LangChain</span><span class="s">Vector DBs</span><span class="s">PostgreSQL</span><span class="s">GraphQL</span>
  </div>
</div></section>

<section id="education"><div class="wrap">
  <h2>Education &amp; Awards</h2>
  <div class="edu">
    <div class="t">Virginia Tech — B.S. Computer Science &amp; B.S. Psychology</div>
    <div class="d">Blacksburg, VA</div>
  </div>
  <div class="edu" style="margin-top:14px">
    <div class="t">Geneva–Tsinghua Initiative</div>
    <div class="d">Built a Bluetooth/Arduino wristband (Android + AWS) alerting motorcycle riders to dangerous situations.</div>
  </div>
</div></section>

<footer><div class="wrap">
  Matthew Russell · New York, NY · <a href="mailto:mattrussellc@gmail.com">mattrussellc@gmail.com</a> · <a href="https://linkedin.com/in/matthewrussellc" target="_blank" rel="noopener">LinkedIn</a>
</div></footer>
</body>
</html>'''

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def _route(self):
        p = self.path.split('?', 1)[0]
        if BASE and p.startswith(BASE):
            p = p[len(BASE):] or '/'
        return p
    def do_GET(self):
        p = self._route()
        if p in ('/', '/index.html'):
            body = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(body)
        elif p in ('/health', '/healthz'):
            self.send_response(200); self.send_header('Content-Type', 'text/plain'); self.end_headers(); self.wfile.write(b'ok')
        else:
            self.send_response(404); self.end_headers(); self.wfile.write(b'not found')

if __name__ == '__main__':
    print(f"Portfolio on :{PORT} base='{BASE or '/'}'")
    ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()

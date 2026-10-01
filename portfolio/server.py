#!/usr/bin/env python3
"""
Public App Hub for Matthew — a single public landing page linking to all his apps.
Zero-dep Python stdlib server, served at root for a Cloudflare tunnel.

Links use each app's real URL. Apps that hold private data or an API key stay on
the tailnet (they open for Matthew from anywhere, but not for strangers); only
genuinely public apps get a public link.

Env:
  PORTFOLIO_PORT   (default 18824)
  PORTFOLIO_BASE   optional mount path (default "" = root)
"""
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORTFOLIO_PORT", "18824"))
BASE = (os.environ.get("PORTFOLIO_BASE", "").rstrip("/"))
HUB = "https://bushwick.tail9d821f.ts.net"

# (emoji, name, url, description, access)  access: "public" | "private"
APPS = [
    ("🧭", "Waypoint", HUB + "/waypoint/",
     "AI driving GPS — spoken turn-by-turn, agentic “ask &amp; route,” and live local-area briefings.", "private"),
    ("🧳", "Travelog", HUB + "/travelog/",
     "AI travel journal — place &amp; history briefings, reflective journaling, and AI photo collages.", "private"),
    ("⚡", "Daylight", "https://web-production-970f8.up.railway.app/",
     "Energy-management dashboard with live visualizations. Django · React · Postgres.", "public"),
    ("🏠", "openhome", "https://pi.tail9d821f.ts.net/",
     "Self-hosted smart-home hub — lights, music, and climate with a voice agent.", "private"),
    ("👥", "Rolodex", HUB + "/rolodex/",
     "Personal network CRM — contacts, follow-ups, reach-out queue, insights.", "private"),
    ("📄", "Reports &amp; Voice", HUB + "/reports/",
     "Daily briefing archive with inline voice notes.", "private"),
    ("🛰️", "Command Hub", HUB + "/",
     "Central control hub — scheduler dashboard + links to everything.", "private"),
]

# Showcase-only (built, not hosted)
MORE = [
    ("🎵", "Dropstick", "Offline Wi-Fi USB music-sharing stick. Go · SQLite."),
    ("📈", "Arbitrage Scanner", "Prediction-market arbitrage detection. TypeScript · SQLite."),
    ("🩺", "Ora Health", "Agentic-AI iOS wellness app. React Native · ElevenLabs."),
    ("🪄", "Doctor Strange Lab", "Hand-tracked arcane FX. Three.js · MediaPipe."),
    ("🐔", "Coupe", "Dating app with Elo matchmaking."),
    ("🤝", "Favorly", "Microfavors + Helping Hands."),
    ("🐝", "Agent Swarm", "Kanban board for multi-agent orchestration."),
    ("🎉", "Raves", "Events &amp; outings tracker."),
]

def app_card(emoji, name, url, desc, access):
    badge = ('<span class="badge pub">● public</span>' if access == "public"
             else '<span class="badge priv">🔒 private</span>')
    return (f'<a class="card" href="{url}" target="_blank" rel="noopener">'
            f'<div class="top"><span class="em">{emoji}</span><span class="nm">{name}</span>'
            f'<span class="arrow">↗</span></div>'
            f'<p>{desc}</p>{badge}</a>')

def more_card(emoji, name, desc):
    return (f'<div class="mcard"><span class="em">{emoji}</span>'
            f'<div><div class="nm">{name}</div><div class="md">{desc}</div></div></div>')

def render():
    apps = "\n".join(app_card(*a) for a in APPS)
    more = "\n".join(more_card(*m) for m in MORE)
    return PAGE.replace("__APPS__", apps).replace("__MORE__", more)

PAGE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="theme-color" content="#0b0f14"/>
<title>Matthew's Apps</title>
<meta name="description" content="A hub of apps Matthew has built — GPS, smart home, dashboards, and more."/>
<style>
  :root{--bg:#0b0f14;--panel:#121820;--panel2:#0e141b;--line:#1f2a36;--text:#e8eef5;--dim:#90a4b8;--accent:#22c55e;--accent2:#38bdf8}
  *{box-sizing:border-box}
  body{margin:0;background:radial-gradient(1100px 560px at 72% -12%,#102033 0,var(--bg) 55%);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif;line-height:1.6}
  .wrap{max-width:900px;margin:0 auto;padding:0 20px}
  a{color:inherit;text-decoration:none}
  header{padding:60px 0 30px}
  .kicker{color:var(--accent);font-weight:700;letter-spacing:.14em;text-transform:uppercase;font-size:12px}
  h1{font-size:44px;line-height:1.05;margin:10px 0 8px;letter-spacing:-.02em}
  .sub{color:#c6d6e6;font-size:18px;max-width:60ch}
  .legend{color:var(--dim);font-size:13px;margin-top:14px}
  h2{font-size:13px;text-transform:uppercase;letter-spacing:.12em;color:var(--dim);margin:34px 0 14px;font-weight:700}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}
  .card{display:flex;flex-direction:column;background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:16px;transition:border-color .15s,transform .1s}
  .card:hover{border-color:#2b6cb0}
  .card:active{transform:scale(.99)}
  .top{display:flex;align-items:center;gap:9px}
  .em{font-size:20px}
  .nm{font-weight:700;font-size:16px}
  .arrow{margin-left:auto;color:var(--accent2)}
  .card p{margin:9px 0 12px;color:#c2d2e2;font-size:13.5px;flex:1}
  .badge{align-self:flex-start;font-size:11px;border-radius:999px;padding:2px 9px}
  .badge.pub{color:var(--accent);border:1px solid #1f6f3f;background:#0f2a1a}
  .badge.priv{color:#e0b43a;border:1px solid #5a4a1a;background:#2a230f}
  .more{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:8px}
  .mcard{display:flex;gap:11px;align-items:flex-start;background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:11px 13px}
  .mcard .nm{font-size:14px}
  .mcard .md{color:var(--dim);font-size:12px;margin-top:2px;line-height:1.45}
  footer{padding:30px 0 56px;color:var(--dim);font-size:13px}
  footer a{color:var(--accent2)}
</style>
</head>
<body>
<header><div class="wrap">
  <div class="kicker">Built by Matthew Russell</div>
  <h1>🗂️ Matthew's Apps</h1>
  <div class="sub">A hub of everything I've built — driving GPS, a smart-home system, dashboards, and more. Tap any to open.</div>
  <div class="legend">● public = open to anyone · 🔒 private = opens on my own devices (holds personal data)</div>
</div></header>

<section><div class="wrap">
  <h2>Apps</h2>
  <div class="grid">__APPS__</div>

  <h2>More projects</h2>
  <div class="more">__MORE__</div>
</div></section>

<footer><div class="wrap">
  Built with OpenClaw · <a href="https://web-production-970f8.up.railway.app/" target="_blank" rel="noopener">try Daylight (public)</a>
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
            body = render().encode('utf-8')
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
    print(f"App Hub on :{PORT} base='{BASE or '/'}'")
    ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()

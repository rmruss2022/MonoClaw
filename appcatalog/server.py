#!/usr/bin/env python3
"""
App Catalog — a single bookmarkable index of everything Matthew has built.
Zero-dep Python stdlib server, mounted under the command hub at /apps.

Env:
  CATALOG_PORT   (default 18823)
  CATALOG_BASE   base path when mounted under the hub, e.g. "/apps"
"""
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("CATALOG_PORT", "18823"))
BASE = (os.environ.get("CATALOG_BASE", "").rstrip("/"))
HUB = "https://bushwick.tail9d821f.ts.net"

# (name, emoji, url_or_None, description, tag)
LIVE_HUB = [
    ("Command Hub",        "🛰️", HUB + "/",         "Central control hub — cron/scheduler dashboard + links to everything.", "hub"),
    ("Reports & Voice",    "📄", HUB + "/reports",  "Daily NYC digests archive with inline mp3 voice notes.", "hub"),
    ("Rolodex",            "👥", HUB + "/rolodex",  "Personal network CRM — contacts, follow-ups, reach-out list, insights.", "hub"),
    ("Waypoint",           "🧭", HUB + "/waypoint", "AI driving GPS — turn-by-turn, spoken area briefings, agentic Ask.", "hub"),
    ("Travelog",           "🧳", HUB + "/travelog", "Travel journal with an AI companion — place/history briefings, reflective journaling, and AI photo collages.", "hub"),
]
LIVE_OTHER = [
    ("openhome",   "🏠", "https://home.bedrock.casa/", "Smart-home hub — lights, music, climate, voice agent. Runs on the Pi (login-gated).", "pi"),
    ("Daylight",   "⚡", "https://web-production-970f8.up.railway.app/", "Energy-management dashboard — Django + React + Postgres on Railway.", "cloud"),
]
# Claw apps — permanent public URLs on bedrock.casa
CLAW_APPS = [
    ("Daily Reports & News", "📰", "https://reports.bedrock.casa/", "Daily NYC news digests + archive, with inline mp3 voice notes.", "claw"),
]
BUILT = [
    ("Recilia",              "🌙", "Tinnitus relief — CBT/ACT lessons + a research-grade sound engine (fractal/notched, walk-around open-ear enrichment), a painted progress garden, and Vera the journey companion. React Native; on TestFlight."),
    ("Coupe",                "🐔", "Chicken-coop themed dating app with HTN Elo rating. (workspace/coupe)"),
    ("Favorly",              "🤝", "Microfavors + Helping Hands app — MVP backend built."),
    ("Dropstick",            "🎵", "P2P music sharing for DJs — swap tracks/crates device-to-device over local Wi-Fi, no internet. Go + SQLite."),
    ("Arbitrage Scanner",    "📈", "Prediction-market arbitrage detection (Polymarket/Kalshi)."),
    ("Ora Health",           "🩺", "Community health app + Life OS redesign (React Native)."),
    ("Daily Blog",           "✍️", "Auto-generated daily blog → GitHub → Vercel."),
    ("Agent Swarm",          "🐝", "Kanban board for multi-agent orchestration."),
    ("Jobs Dashboard",       "💼", "Job-application tracking pipeline."),
    ("Raves Dashboard",      "🎉", "Events / social outings tracker."),
    ("Vision Controller",    "✋", "Webcam gesture → window manager (Mac)."),
    ("Doctor Strange Lab",   "🪄", "Hand-tracked arcane shields + astral wireframe (Mac, Three.js)."),
]

def card(name, emoji, url, desc, tag=None):
    badge = f'<span class="badge {tag}">{tag}</span>' if tag else ''
    inner = (f'<div class="top"><span class="em">{emoji}</span><span class="nm">{name}</span>{badge}'
             f'<span class="arrow">{"↗" if url else ""}</span></div>'
             f'<p>{desc}</p>')
    if url:
        return f'<a class="card" href="{url}" target="_blank" rel="noopener">{inner}</a>'
    return f'<div class="card dim">{inner}</div>'

def built_row(name, emoji, desc):
    return (f'<div class="brow"><span class="em">{emoji}</span>'
            f'<div><div class="nm">{name}</div><div class="bd">{desc}</div></div></div>')

def render():
    live = "\n".join(card(*c) for c in LIVE_HUB)
    other = "\n".join(card(*c) for c in LIVE_OTHER)
    claw = "\n".join(card(*c) for c in CLAW_APPS)
    built = "\n".join(built_row(*b) for b in BUILT)
    return (PAGE.replace("__LIVE__", live).replace("__OTHER__", other)
                .replace("__CLAW__", claw).replace("__BUILT__", built))

PAGE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
<meta name="theme-color" content="#0b0f14"/>
<title>My Apps — Catalog</title>
<style>
  :root{--bg:#0b0f14;--panel:#121820;--panel2:#0e141b;--line:#1e2833;--text:#e8eef5;--dim:#8aa0b4;--accent:#22c55e;--accent2:#38bdf8}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;padding:max(env(safe-area-inset-top),16px) 16px 40px}
  .wrap{max-width:860px;margin:0 auto}
  h1{font-size:26px;margin:8px 0 2px}
  .sub{color:var(--dim);font-size:14px;margin-bottom:22px}
  h2{font-size:14px;text-transform:uppercase;letter-spacing:.08em;color:var(--dim);margin:26px 0 12px;font-weight:700}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
  .card{display:block;text-decoration:none;color:inherit;background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:15px;transition:border-color .15s,transform .1s}
  .card:active{transform:scale(.99)}
  a.card:hover{border-color:#2b6cb0}
  .card.dim{opacity:.72}
  .top{display:flex;align-items:center;gap:9px}
  .em{font-size:20px}
  .nm{font-weight:700;font-size:16px}
  .arrow{margin-left:auto;color:var(--accent2);font-size:16px}
  .card p{margin:9px 0 0;color:#cfe0ee;font-size:13px;line-height:1.5}
  .badge{font-size:10px;text-transform:uppercase;letter-spacing:.05em;border-radius:999px;padding:2px 7px;color:var(--accent);border:1px solid #1f6f3f;background:#0f2a1a}
  .badge.pi{color:#e0b43a;border-color:#5a4a1a;background:#2a230f}
  .badge.cloud{color:var(--accent2);border-color:#24425a;background:#0d2233}
  .badge.claw{color:#c084fc;border-color:#4a2a6a;background:#1e1230}
  .built{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:8px}
  .brow{display:flex;gap:11px;align-items:flex-start;background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:11px 13px}
  .brow .nm{font-size:14px}
  .brow .bd{color:var(--dim);font-size:12px;margin-top:2px;line-height:1.45}
  .foot{color:var(--dim);font-size:12px;margin-top:28px;line-height:1.6;border-top:1px solid var(--line);padding-top:16px}
</style>
</head>
<body>
<div class="wrap">
  <h1>🗂️ My Apps</h1>
  <div class="sub">Everything you've built — one place. Tap a live card to open it. (Links need Tailscale on.)</div>

  <h2>Live · on your command hub</h2>
  <div class="grid">__LIVE__</div>

  <h2>Live · elsewhere</h2>
  <div class="grid">__OTHER__</div>

  <h2>Claw Apps</h2>
  <div class="grid">__CLAW__</div>

  <h2>Built · not currently hosted</h2>
  <div class="built">__BUILT__</div>

  <div class="foot">
    Hub home: <a href="https://bushwick.tail9d821f.ts.net/" style="color:var(--accent2)">bushwick.tail9d821f.ts.net</a> ·
    This catalog lives at <b>/apps</b> on the hub — bookmark it.
  </div>
</div>
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
    print(f"App Catalog on :{PORT} base='{BASE or '/'}'")
    ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()

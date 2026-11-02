#!/usr/bin/env python3
"""
Admin Hub — one place to reach every app's admin panel, admin tools and docs.

Sibling to the App Catalog (/apps), but admin-facing: where the catalog is for
browsing what exists, this is for running it. Zero-dep Python stdlib, mounts
under the command hub at /admin.

Env:
  ADMIN_PORT   (default 18824)
  ADMIN_BASE   base path when mounted under the hub, e.g. "/admin"
"""
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("ADMIN_PORT", "18824"))
BASE = os.environ.get("ADMIN_BASE", "").rstrip("/")
HUB = "https://bushwick.tail9d821f.ts.net"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # MonoClaw/

# ---------------------------------------------------------------- registry
# (name, emoji, admin_url_or_None, description, status, docs_url_or_None)
#   status: "live" (hosted) · "hub" (served here) · "source" (code, not hosted)
APP_PANELS = [
    ("Ora", "🧘", "https://ora-backend-production.up.railway.app/admin",
     "Meditation / community app. Live token-gated admin — the 'Volume Browser': browse generated meditation volumes, files and DB records. Served by the Ora backend on Railway.",
     "live", None),
    ("Recilia", "🌙", BASE + "/app/recilia",
     "Tinnitus relief — grove, sound tools, and Vera the journey companion. Admin panel includes Vera's context graph.",
     "hub", BASE + "/app/recilia/doc/spec"),
    ("Favorly", "🤝", None,
     "Microfavors / Helping Hands. NestJS admin module (favorly/apps/api/src/admin).",
     "source", None),
]

OPS = [
    ("Command Hub", "🛰️", HUB + "/", "Central control — cron/scheduler dashboard + links to everything.", "live", None),
    ("App Catalog", "🗂️", "https://apps.bedrock.casa", "The user-facing index of every app you've built.", "live", None),
    ("MonoClaw Dashboard", "📊", HUB + ":18802/", "Workspace/services dashboard (monoclaw-dashboard).", "live", None),
    ("Mission Control", "🎛️", HUB + ":18795/", "Agent/ops mission control.", "live", None),
    ("Agent Swarm", "🐝", HUB + ":18798/", "Multi-agent orchestration kanban.", "live", None),
    ("Token Tracker", "🔢", HUB + ":18794/", "Model token / spend tracking.", "live", None),
    ("Activity Hub", "📿", HUB + ":18796/", "Activity tracking hub.", "live", None),
    ("Vision Controller", "✋", HUB + ":18799/", "Webcam gesture → window manager.", "live", None),
    ("Skill Builder", "🛠️", HUB + ":18803/", "Skill authoring dashboard (manual start).", "live", None),
]

DOCS = [
    ("Recilia · journey-agent", "🧭", BASE + "/app/recilia/doc/spec", "Vera persona, journey states, tools, context graph."),
    ("Recilia · Vera graph", "✦", BASE + "/app/recilia/doc/graph", "The rendered companion context graph."),
    ("Open Home · docs", "🏠", None, "open-home/docs (source)."),
    ("Port map", "🗺️", None, "PORT-MAP.md — every service and its port (source)."),
]

# Files this server is allowed to read and serve — explicit whitelist, no traversal.
SERVE = {
    "/app/recilia":          (os.path.join(ROOT, "recilia/admin/index.html"), "text/html; charset=utf-8", True),
    "/app/recilia/doc/graph":(os.path.join(ROOT, "recilia/docs/journey-agent.html"), "text/html; charset=utf-8", False),
    "/app/recilia/doc/spec": (os.path.join(ROOT, "recilia/docs/journey-agent.md"), "text/plain; charset=utf-8", False),
    "/app/recilia/doc/readme":(os.path.join(ROOT, "recilia/README.md"), "text/plain; charset=utf-8", False),
    "/app/recilia/doc/listing":(os.path.join(ROOT, "recilia/store/LISTING.md"), "text/plain; charset=utf-8", False),
}
# When serving the Recilia admin page through the hub, point its relative links
# at the whitelisted hub routes above (they would otherwise 404 under /admin).
RECILIA_LINK_FIX = {
    'href="../docs/journey-agent.html"': f'href="{BASE}/app/recilia/doc/graph"',
    'href="../docs/journey-agent.md"':   f'href="{BASE}/app/recilia/doc/spec"',
    'href="../README.md"':               f'href="{BASE}/app/recilia/doc/readme"',
    'href="../store/LISTING.md"':        f'href="{BASE}/app/recilia/doc/listing"',
}

def card(name, emoji, url, desc, status, docs):
    badge = f'<span class="badge {status}">{status}</span>'
    arrow = "↗" if url else ""
    inner = (f'<div class="top"><span class="em">{emoji}</span><span class="nm">{name}</span>{badge}'
             f'<span class="arrow">{arrow}</span></div><p>{desc}</p>')
    # A docs sub-link means the whole-card link can't be a plain <a> (no nested
    # anchors): use an overlay link for the card, with the docs link on top.
    if url and docs:
        return (f'<div class="card"><a class="card-open" href="{url}" aria-label="{name}"></a>'
                f'{inner}<a class="doc" href="{docs}">docs ›</a></div>')
    if url:
        return f'<a class="card" href="{url}">{inner}</a>'
    doclink = f'<a class="doc" href="{docs}">docs ›</a>' if docs else ""
    return f'<div class="card dim">{inner}{doclink}</div>'

def doc_card(name, emoji, url, desc):
    inner = (f'<div class="top"><span class="em">{emoji}</span><span class="nm">{name}</span>'
             f'<span class="arrow">{"↗" if url else ""}</span></div><p>{desc}</p>')
    return f'<a class="card" href="{url}">{inner}</a>' if url else f'<div class="card dim">{inner}</div>'

def render():
    panels = "\n".join(card(*c) for c in APP_PANELS)
    ops = "\n".join(card(*c) for c in OPS)
    docs = "\n".join(doc_card(*d) for d in DOCS)
    return (PAGE.replace("__PANELS__", panels).replace("__OPS__", ops)
                .replace("__DOCS__", docs).replace("__BASE__", BASE or ""))

PAGE = r'''<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/>
<meta name="theme-color" content="#070a16"/><title>Admin Hub</title>
<style>
  :root{--bg:#070a16;--panel:#0e1426;--panel2:#0c111f;--line:#26304a;--text:#e7ecff;--dim:#9fb0d6;--cyan:#7fe3ff;--gold:#f5c977}
  *{box-sizing:border-box}
  body{margin:0;background:radial-gradient(120% 90% at 70% 0%,#121a33,#070a16);color:var(--text);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;padding:max(env(safe-area-inset-top),20px) 18px 48px}
  .wrap{max-width:900px;margin:0 auto}
  .head{display:flex;align-items:center;gap:13px}
  .mark{width:42px;height:42px;border-radius:13px;display:grid;place-items:center;font-size:21px;
    background:radial-gradient(circle at 50% 40%,rgba(245,201,119,.9),rgba(245,201,119,.08));box-shadow:0 0 26px rgba(245,201,119,.4)}
  h1{font-size:25px;margin:0} h1 b{color:var(--gold)}
  .sub{color:var(--dim);font-size:13.5px;margin:3px 0 22px}
  h2{font-size:13px;text-transform:uppercase;letter-spacing:.09em;color:var(--dim);margin:26px 0 12px;font-weight:700}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
  .card{display:block;text-decoration:none;color:inherit;background:var(--panel);border:1px solid var(--line);border-radius:15px;padding:14px;transition:border-color .15s,transform .1s;position:relative}
  a.card:hover,.card:has(.card-open:hover){border-color:var(--cyan)} .card:active{transform:scale(.99)} .card.dim{opacity:.68}
  .card-open{position:absolute;inset:0;z-index:1;border-radius:15px}
  .card:has(.card-open) .top,.card:has(.card-open)>p{pointer-events:none}
  .top{display:flex;align-items:center;gap:9px} .em{font-size:19px} .nm{font-weight:700;font-size:15px}
  .arrow{margin-left:auto;color:var(--cyan);font-size:15px}
  .card p{margin:8px 0 0;color:#cfe0ee;font-size:12.5px;line-height:1.5}
  .doc{position:relative;z-index:2;display:inline-block;margin-top:8px;color:var(--gold);font-size:12px;text-decoration:none}
  .doc:hover{text-decoration:underline}
  .badge{font-size:9.5px;text-transform:uppercase;letter-spacing:.05em;border-radius:999px;padding:2px 7px}
  .badge.live{color:#8affc1;border:1px solid #1f6f4a;background:#0f2a1f}
  .badge.hub{color:var(--cyan);border:1px solid #244a5a;background:#0d2230}
  .badge.source{color:#c8b3ff;border:1px solid #3a2f6a;background:#161230}
  .foot{color:var(--dim);font-size:12px;margin-top:30px;border-top:1px solid var(--line);padding-top:15px;line-height:1.6}
  code{background:#0c111f;border:1px solid var(--line);border-radius:5px;padding:1px 5px;font-size:12px}
</style></head><body><div class="wrap">
  <div class="head"><div class="mark">⚙️</div><div>
    <h1><b>Admin Hub</b></h1><div class="sub">Every app's real admin dashboard, tools, and docs — one place.</div></div></div>

  <h2>App admin dashboards</h2>
  <div class="grid">__PANELS__</div>

  <h2>Ops dashboards · OpenClaw</h2>
  <div class="grid">__OPS__</div>

  <h2>Documentation</h2>
  <div class="grid">__DOCS__</div>

  <div class="foot">Live at <code>admin.bedrock.casa</code>, beside the catalog at <code>apps.bedrock.casa</code>.
    <code>live</code> = hosted · <code>hub</code> = served here · <code>source</code> = in the repo, not yet hosted.
    Add an app by editing <code>admin-hub/server.py</code>.</div>
</div></body></html>'''

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def _route(self):
        p = self.path.split('?', 1)[0]
        if BASE and p.startswith(BASE):
            p = p[len(BASE):] or '/'
        return p
    def _send(self, code, body, ctype='text/html; charset=utf-8'):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        p = self._route()
        if p in ('/', '/index.html'):
            return self._send(200, render())
        if p in ('/health', '/healthz'):
            return self._send(200, 'ok', 'text/plain')
        if p in SERVE:
            path, ctype, is_recilia_admin = SERVE[p]
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = f.read()
            except OSError:
                return self._send(404, 'not found', 'text/plain')
            if is_recilia_admin:
                for k, v in RECILIA_LINK_FIX.items():
                    data = data.replace(k, v)
            return self._send(200, data, ctype)
        return self._send(404, 'not found', 'text/plain')

if __name__ == '__main__':
    print(f"Admin Hub on :{PORT} base='{BASE or '/'}' root='{ROOT}'")
    ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()

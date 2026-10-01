#!/usr/bin/env python3
"""
Public App Hub for Matthew — branded landing page linking to his main apps.
Zero-dep Python stdlib server, served at root for a Cloudflare tunnel.

Custom SVG app-icon set + monogram brand mark. Apps that hold private data or an
API key stay on the tailnet (open for Matthew from anywhere, not for strangers).

Env:
  PORTFOLIO_PORT   (default 18824)
  PORTFOLIO_BASE   optional mount path (default "" = root)
"""
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORTFOLIO_PORT", "18824"))
BASE = (os.environ.get("PORTFOLIO_BASE", "").rstrip("/"))
HUB = "https://bushwick.tail9d821f.ts.net"

# ---- branded SVG app icons (rounded tiles, unique gradient + white glyph) ----
ICONS = {
 "waypoint": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_wp" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#3b82f6"/><stop offset="1" stop-color="#06b6d4"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_wp)"/><path d="M26 13l9.5 27-9.5-6.3-9.5 6.3z" fill="#fff"/></svg>',
 "travelog": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_tl" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f59e0b"/><stop offset="1" stop-color="#ef4444"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_tl)"/><path d="M26 12a9 9 0 0 0-9 9c0 6.6 9 18 9 18s9-11.4 9-18a9 9 0 0 0-9-9zm0 12.4a3.4 3.4 0 1 1 0-6.8 3.4 3.4 0 0 1 0 6.8z" fill="#fff"/></svg>',
 "openhome": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_oh" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#34d399"/><stop offset="1" stop-color="#059669"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_oh)"/><path d="M26 14l12.5 10.5h-3.2V39H30v-8.5h-8V39h-5.3V24.5h-3.2z" fill="#fff"/></svg>',
 "rolodex": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_rx" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#6366f1"/><stop offset="1" stop-color="#8b5cf6"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_rx)"/><rect x="14" y="16" width="24" height="19" rx="3.5" fill="#fff"/><circle cx="22" cy="24" r="2.8" fill="#6d5ff0"/><path d="M17.5 31.5c0-2.7 2-4.3 4.5-4.3s4.5 1.6 4.5 4.3z" fill="#6d5ff0"/><rect x="29" y="22" width="6.5" height="2" rx="1" fill="#cdd0f8"/><rect x="29" y="27" width="6.5" height="2" rx="1" fill="#cdd0f8"/></svg>',
 "ora": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_or" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2dd4bf"/><stop offset="1" stop-color="#10b981"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_or)"/><path d="M35 15c-13 0-19 6.5-19 15.5 0 1.8.4 3.5.4 3.5s1.7.4 3.6.4C29 34 37 27 37 16c0-.4-2-1-2-1z" fill="#fff"/><path d="M20 35c3.5-8 9-11.5 12.5-13" stroke="#10b981" stroke-width="2" fill="none" stroke-linecap="round"/></svg>',
 "favorly": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_fv" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fb7185"/><stop offset="1" stop-color="#ec4899"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_fv)"/><path d="M26 38s-11.5-6.8-11.5-14.4A6.5 6.5 0 0 1 26 19.3a6.5 6.5 0 0 1 11.5 4.3C37.5 31.2 26 38 26 38z" fill="#fff"/></svg>',
 "dropstick": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_ds" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8b5cf6"/><stop offset="1" stop-color="#d946ef"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_ds)"/><path d="M34 14l-13 3.2v16.1a4.3 4.3 0 1 0 2 3.6V22.2l9-2.2v8.9a4.3 4.3 0 1 0 2 3.6V14z" fill="#fff"/></svg>',
}

# (icon_key, name, url_or_None, description, status)  status: public | private | wip
APPS = [
    ("waypoint", "Waypoint", HUB + "/waypoint/",
     "AI driving GPS — spoken turn-by-turn, an agentic “ask &amp; route” assistant, and live local-area briefings.", "private"),
    ("travelog", "Travelog", HUB + "/travelog/",
     "AI travel journal — place &amp; history briefings, reflective journaling, and AI photo collages.", "private"),
    ("openhome", "openhome", "https://pi.tail9d821f.ts.net/",
     "Self-hosted smart-home hub — lights, music, and climate with a voice agent.", "private"),
    ("rolodex", "Rolodex", HUB + "/rolodex/",
     "Personal network CRM — contacts, follow-ups, a reach-out queue, and insights.", "private"),
    ("ora", "Ora Health", None,
     "Agentic-AI iOS wellness app — dynamic conversations, daily meditations &amp; mindset work. React Native · ElevenLabs.", "wip"),
    ("favorly", "Favorly", None,
     "Microfavors &amp; Helping Hands — a community favor-exchange app. MVP backend built.", "wip"),
    ("dropstick", "Dropstick", None,
     "Offline Wi-Fi USB stick for peer-to-peer music sharing — no internet needed. Go · SQLite.", "wip"),
]

TAGS = {
    "public":  '<span class="tag pub">Public</span>',
    "private": '<span class="tag priv">Private</span>',
    "wip":     '<span class="tag wip">In&nbsp;progress</span>',
}

FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
           '<defs><linearGradient id="m" x1="0" y1="0" x2="1" y2="1">'
           '<stop offset="0" stop-color="#4f46e5"/><stop offset="1" stop-color="#7c3aed"/></linearGradient></defs>'
           '<rect width="64" height="64" rx="16" fill="url(#m)"/>'
           '<text x="32" y="44" text-anchor="middle" font-family="Georgia,serif" font-weight="700" font-size="34" fill="#fff">M</text></svg>')

def app_card(key, name, url, desc, status):
    tag = TAGS.get(status, "")
    icon = ICONS.get(key, "")
    inner = (f'{icon}'
             f'<div class="cmain"><div class="crow"><span class="nm">{name}</span>{tag}</div>'
             f'<p>{desc}</p></div>')
    if url:
        return (f'<a class="card" href="{url}" target="_blank" rel="noopener">{inner}'
                f'<span class="go" aria-hidden="true">&rarr;</span></a>')
    return f'<div class="card wipcard">{inner}</div>'

def render():
    apps = "\n".join(app_card(*a) for a in APPS)
    return PAGE.replace("__APPS__", apps).replace("__N__", str(len(APPS)))

PAGE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="theme-color" content="#f5f4f1"/>
<title>Matthew Russell — Apps</title>
<meta name="description" content="A hub of apps built by Matthew Russell — AI driving GPS, a smart-home system, a travel journal, and more."/>
<link rel="icon" href="favicon.svg" type="image/svg+xml"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet"/>
<style>
  :root{
    --bg:#f5f4f1; --ink:#15171c; --muted:#656f7d; --card:#ffffff;
    --line:#e9e8e3; --accent:#4f46e5; --accent-soft:#eef0fd;
    --shadow:0 1px 2px rgba(20,23,30,.04), 0 10px 28px rgba(20,23,30,.06);
    --shadow-h:0 2px 8px rgba(20,23,30,.06), 0 22px 50px rgba(20,23,30,.13);
  }
  *{box-sizing:border-box}
  html{-webkit-text-size-adjust:100%}
  body{margin:0;background:
       radial-gradient(900px 500px at 80% -10%, #ffffff 0, rgba(255,255,255,0) 60%),
       radial-gradient(700px 400px at 0% 0%, #efeef8 0, rgba(239,238,248,0) 55%),
       var(--bg);
       color:var(--ink);font-family:'Inter',-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
       -webkit-font-smoothing:antialiased;line-height:1.6}
  .wrap{max-width:980px;margin:0 auto;padding:0 24px}
  a{color:inherit;text-decoration:none}

  /* brand bar */
  .bar{display:flex;align-items:center;gap:11px;padding:24px 0 0}
  .brandtile{width:32px;height:32px;border-radius:9px;background:linear-gradient(135deg,#4f46e5,#7c3aed);
             display:flex;align-items:center;justify-content:center;color:#fff;
             font-family:'Fraunces',Georgia,serif;font-weight:600;font-size:18px;box-shadow:var(--shadow)}
  .brandname{font-weight:600;font-size:15px;letter-spacing:-.01em}
  .brandname span{color:var(--muted);font-weight:500}

  header{padding:52px 0 40px;text-align:center}
  .kick{font-size:12px;letter-spacing:.2em;text-transform:uppercase;color:var(--muted);font-weight:600}
  h1{font-family:'Fraunces',Georgia,serif;font-weight:600;font-size:clamp(42px,8.5vw,72px);line-height:1.02;letter-spacing:-.02em;margin:16px 0 16px}
  .sub{color:var(--muted);font-size:18px;max-width:50ch;margin:0 auto}
  .legend{display:inline-flex;gap:18px;margin-top:24px;font-size:12.5px;color:var(--muted);align-items:center}
  .legend b{font-weight:600;color:var(--ink)}
  .dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px;vertical-align:middle}
  .dot.a{background:#caa43a}.dot.n{background:#9aa1ac}

  h2{font-size:12px;text-transform:uppercase;letter-spacing:.14em;color:var(--muted);font-weight:700;margin:40px 0 18px}
  .cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:16px}
  .card{position:relative;display:flex;align-items:flex-start;gap:14px;background:var(--card);
        border:1px solid var(--line);border-radius:18px;padding:18px 18px 19px;box-shadow:var(--shadow);
        transition:transform .2s cubic-bezier(.2,.7,.2,1), box-shadow .2s}
  .card:hover{transform:translateY(-3px);box-shadow:var(--shadow-h)}
  .ai{width:50px;height:50px;flex:0 0 auto;display:block;border-radius:13px;box-shadow:0 2px 7px rgba(20,23,30,.14)}
  .cmain{flex:1;min-width:0}
  .crow{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
  .nm{font-weight:600;font-size:16.5px;letter-spacing:-.01em}
  .tag{font-size:10.5px;font-weight:600;padding:2px 8px;border-radius:999px;letter-spacing:.02em}
  .tag.pub{color:#0a7d49;background:#e4f6ec}
  .tag.priv{color:#8a6d1a;background:#f7eecf}
  .tag.wip{color:#5b6472;background:#edeef1}
  .card p{margin:5px 0 0;color:var(--muted);font-size:14px;line-height:1.52}
  .go{position:absolute;top:17px;right:18px;color:#cdd0d7;font-size:17px;transition:transform .2s, color .2s}
  .card:hover .go{color:var(--accent);transform:translate(3px,-3px)}
  .card.wipcard{cursor:default}
  .card.wipcard:hover{transform:none;box-shadow:var(--shadow)}

  footer{text-align:center;color:var(--muted);font-size:13px;padding:56px 0 72px}
  footer a{color:var(--accent);font-weight:500}
  @media (max-width:560px){header{padding:36px 0 28px}.legend{flex-direction:column;gap:8px}}
</style>
</head>
<body>
<div class="wrap">
  <div class="bar">
    <div class="brandtile">M</div>
    <div class="brandname">Matthew Russell <span>· Apps</span></div>
  </div>
</div>

<header><div class="wrap">
  <div class="kick">Software Engineer</div>
  <h1>Things I've built.</h1>
  <p class="sub">A living hub of the __N__ apps I'm building — an AI driving companion, a smart home, a travel journal, and more.</p>
  <div class="legend">
    <span><span class="dot a"></span><b>Private</b> — opens on my devices</span>
    <span><span class="dot n"></span><b>In progress</b> — building</span>
  </div>
</div></header>

<main class="wrap">
  <h2>Apps</h2>
  <div class="cards">__APPS__</div>
</main>

<footer><div class="wrap">Designed &amp; built by Matthew Russell</div></footer>
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
    def _send(self, body, ctype):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        p = self._route()
        if p in ('/', '/index.html'):
            self._send(render(), 'text/html; charset=utf-8')
        elif p == '/favicon.svg':
            self._send(FAVICON, 'image/svg+xml')
        elif p in ('/health', '/healthz'):
            self._send('ok', 'text/plain')
        else:
            self.send_response(404); self.end_headers(); self.wfile.write(b'not found')

if __name__ == '__main__':
    print(f"App Hub on :{PORT} base='{BASE or '/'}'")
    ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()

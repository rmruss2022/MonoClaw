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

# Title font (Fraunces) inlined as base64 @font-face so it can't fail to load / revert.
try:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts.css")) as _f:
        FONTS_CSS = _f.read()
except OSError:
    FONTS_CSS = ""

# ---- branded SVG app icons (rounded tiles, unique gradient + white glyph) ----
ICONS = {
 "waypoint": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_wp" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#3b82f6"/><stop offset="1" stop-color="#06b6d4"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_wp)"/><path d="M26 13l9.5 27-9.5-6.3-9.5 6.3z" fill="#fff"/></svg>',
 "travelog": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_tl" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f59e0b"/><stop offset="1" stop-color="#ef4444"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_tl)"/><path d="M26 12a9 9 0 0 0-9 9c0 6.6 9 18 9 18s9-11.4 9-18a9 9 0 0 0-9-9zm0 12.4a3.4 3.4 0 1 1 0-6.8 3.4 3.4 0 0 1 0 6.8z" fill="#fff"/></svg>',
 "openhome": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_oh" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#34d399"/><stop offset="1" stop-color="#059669"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_oh)"/><path d="M26 14l12.5 10.5h-3.2V39H30v-8.5h-8V39h-5.3V24.5h-3.2z" fill="#fff"/></svg>',
 "rolodex": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_rx" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#6366f1"/><stop offset="1" stop-color="#8b5cf6"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_rx)"/><rect x="14" y="16" width="24" height="19" rx="3.5" fill="#fff"/><circle cx="22" cy="24" r="2.8" fill="#6d5ff0"/><path d="M17.5 31.5c0-2.7 2-4.3 4.5-4.3s4.5 1.6 4.5 4.3z" fill="#6d5ff0"/><rect x="29" y="22" width="6.5" height="2" rx="1" fill="#cdd0f8"/><rect x="29" y="27" width="6.5" height="2" rx="1" fill="#cdd0f8"/></svg>',
 "ora": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_or" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2dd4bf"/><stop offset="1" stop-color="#10b981"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_or)"/><path d="M35 15c-13 0-19 6.5-19 15.5 0 1.8.4 3.5.4 3.5s1.7.4 3.6.4C29 34 37 27 37 16c0-.4-2-1-2-1z" fill="#fff"/><path d="M20 35c3.5-8 9-11.5 12.5-13" stroke="#10b981" stroke-width="2" fill="none" stroke-linecap="round"/></svg>',
 "favorly": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_fv" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fb7185"/><stop offset="1" stop-color="#ec4899"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_fv)"/><path d="M26 38s-11.5-6.8-11.5-14.4A6.5 6.5 0 0 1 26 19.3a6.5 6.5 0 0 1 11.5 4.3C37.5 31.2 26 38 26 38z" fill="#fff"/></svg>',
 "dropstick": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_ds" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8b5cf6"/><stop offset="1" stop-color="#d946ef"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_ds)"/><path d="M34 14l-13 3.2v16.1a4.3 4.3 0 1 0 2 3.6V22.2l9-2.2v8.9a4.3 4.3 0 1 0 2 3.6V14z" fill="#fff"/></svg>',
 "inkling": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_ik" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#e0b063"/><stop offset="1" stop-color="#b8863a"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_ik)"/><rect x="15" y="11" width="22" height="30" rx="3" fill="none" stroke="#fff" stroke-width="2.4"/><line x1="26" y1="12.5" x2="26" y2="39.5" stroke="#fff" stroke-width="2"/><path d="M33 16l5-2.2-1.1 5.2-15 15-4.4.9.9-4.4z" fill="#fff"/></svg>',
 "croppa": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_cr" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#6366f1"/><stop offset="1" stop-color="#8b5cf6"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_cr)"/><path d="M18 11v23a2 2 0 0 0 2 2h23" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round"/><path d="M11 18h23a2 2 0 0 1 2 2v23" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round"/></svg>',
 "chase": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_ch" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f59e0b"/><stop offset="1" stop-color="#ef4444"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_ch)"/><circle cx="26" cy="26" r="11" fill="none" stroke="#fff" stroke-width="3"/><circle cx="26" cy="26" r="3" fill="#fff"/><path d="M26 9v6M26 37v6M9 26h6M37 26h6" stroke="#fff" stroke-width="3" stroke-linecap="round"/></svg>',
}

# (icon_key, name, url_or_None, description, status)  status: public | private | wip
APPS = [
    ("ora", "Ora Health", None,
     "Agentic-AI iOS wellness app — dynamic conversations, daily meditations &amp; mindset work. React Native · ElevenLabs.", "wip"),
    ("favorly", "Favorly", None,
     "Microfavors &amp; Helping Hands — a community favor-exchange app. MVP backend built.", "wip"),
    ("inkling", "Inkling", "__INKLING__",
     "Voice-first writing room — speak, and an AI librarian co-writes your book in your voice, tending your ideas like rare books.", "public"),
    ("waypoint", "Waypoint", HUB + "/waypoint/",
     "AI driving GPS — spoken turn-by-turn, an agentic “ask &amp; route” assistant, and live local-area briefings.", "private"),
    ("travelog", "Travelog", HUB + "/travelog/",
     "AI travel journal — place &amp; history briefings, reflective journaling, and AI photo collages.", "private"),
    ("openhome", "openhome", "https://pi.tail9d821f.ts.net/",
     "Self-hosted smart-home hub — lights, music, and climate with a voice agent.", "private"),
    ("rolodex", "Rolodex", HUB + "/rolodex/",
     "Personal network CRM — contacts, follow-ups, a reach-out queue, and insights.", "private"),
    ("croppa", "Croppa", HUB + "/crop/",
     "AI photo auto-crop — detects the subject and frames it, with one-tap ratios and full manual control.", "private"),
    ("chase", "Slipstream", HUB + "/track/",
     "AI video follow-cam — lock onto a car or object and it stays centered as it moves. Built for race footage.", "private"),
    ("dropstick", "Dropstick", None,
     "Peer-to-peer music sharing for DJs — swap tracks &amp; crates device-to-device over local Wi-Fi, no internet. Go · SQLite.", "wip"),
]

TAGS = {
    "public":  '<span class="tag pub">Public</span>',
    "private": '<span class="tag priv">Private</span>',
    "wip":     '<span class="tag wip">In&nbsp;progress</span>',
}

# Dash mark: a dashboard gauge / speedometer — unique and on-theme for "Dash"
MARK_INNER = (
    '<path d="M15 39 A17 17 0 0 1 49 39" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round"/>'
    '<circle cx="18.5" cy="35" r="1.6" fill="#fff" opacity="0.85"/>'
    '<circle cx="32" cy="24.2" r="1.6" fill="#fff" opacity="0.85"/>'
    '<circle cx="45.5" cy="35" r="1.6" fill="#fff" opacity="0.85"/>'
    '<line x1="32" y1="39" x2="41" y2="28.5" stroke="#fff" stroke-width="3.6" stroke-linecap="round"/>'
    '<circle cx="32" cy="39" r="3.9" fill="#fff"/>')

FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
           '<defs><linearGradient id="m" x1="0" y1="0" x2="1" y2="1">'
           '<stop offset="0" stop-color="#4f46e5"/><stop offset="1" stop-color="#7c3aed"/></linearGradient></defs>'
           '<rect width="64" height="64" rx="16" fill="url(#m)"/>' + MARK_INNER + '</svg>')

# brand glyph for the header tile (sits on the gradient tile; no bg rect)
BRANDMARK = '<svg class="bmk" viewBox="0 0 64 64">' + MARK_INNER + '</svg>'

def app_card(key, name, url, desc, status):
    tag = TAGS.get(status, "")
    icon = ICONS.get(key, "")
    inner = (f'{icon}'
             f'<div class="cmain"><span class="nm">{name}</span>'
             f'<p>{desc}</p></div>')
    if url:
        return f'<a class="card" href="{url}" target="_blank" rel="noopener">{inner}</a>'
    return f'<div class="card wipcard">{inner}</div>'

def inkling_url():
    """Resolve Inkling's live public (quick-tunnel) URL, which rotates on restart."""
    try:
        u = open("/root/MonoClaw/inkling/data/public_url.txt").read().strip()
        if u.startswith("http"):
            return u
    except OSError:
        pass
    return None

def live_url(app, suffix=""):
    """Resolve an app's live public (quick-tunnel) URL, which rotates on restart."""
    try:
        u = open(f"/root/MonoClaw/{app}/data/public_url.txt").read().strip()
        if u.startswith("http"):
            return u + suffix
    except OSError:
        pass
    return None

def render():
    seen = set()
    rows = []
    for a in APPS:
        if a[0] in seen:          # guard against duplicate catalog entries
            continue
        seen.add(a[0])
        if a[0] == "inkling":
            u = inkling_url()
            a = (a[0], a[1], u, a[3], "public" if u else "wip")
        elif a[0] == "travelog":
            u = live_url("travelog", "/travelog/")
            a = (a[0], a[1], u or (HUB + "/travelog/"), a[3], "public" if u else "private")
        elif a[0] == "rolodex":
            u = live_url("rolodex", "/")   # public instance is served at root, login-gated
            a = (a[0], a[1], u or (HUB + "/rolodex/"), a[3], "public" if u else "private")
        elif a[0] == "croppa":
            u = live_url("croppa", "/")    # public, login-gated
            a = (a[0], a[1], u or (HUB + "/crop/"), a[3], "public" if u else "private")
        elif a[0] == "chase":
            u = live_url("chase", "/")     # public, login-gated
            a = (a[0], a[1], u or (HUB + "/track/"), a[3], "public" if u else "private")
        rows.append(app_card(*a))
    apps = "\n".join(rows)
    return (PAGE.replace("__APPS__", apps)
                .replace("__N__", str(len(APPS)))
                .replace("__MARK__", BRANDMARK)
                .replace("/*__FONTS__*/", FONTS_CSS))

PAGE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="theme-color" content="#f5f4f1"/>
<title>Dash</title>
<meta name="description" content="Dash — Matthew's personal hub of apps: AI driving GPS, a smart-home system, a travel journal, and more."/>
<link rel="icon" href="favicon.svg" type="image/svg+xml"/>
<link rel="apple-touch-icon" href="apple-touch-icon.png"/>
<link rel="manifest" href="manifest.webmanifest"/>
<meta name="apple-mobile-web-app-capable" content="yes"/>
<meta name="mobile-web-app-capable" content="yes"/>
<meta name="apple-mobile-web-app-status-bar-style" content="default"/>
<meta name="apple-mobile-web-app-title" content="Dash"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet"/>
<style>
/*__FONTS__*/
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
             display:flex;align-items:center;justify-content:center;box-shadow:var(--shadow)}
  .bmk{width:18px;height:18px;display:block}
  .brandname{font-weight:600;font-size:15px;letter-spacing:-.01em}
  .brandname span{color:var(--muted);font-weight:500}

  header{position:relative;padding:58px 0 48px;text-align:center;overflow:hidden}
  .blob{position:absolute;top:-80px;left:50%;transform:translateX(-50%);width:460px;max-width:128vw;height:320px;
        background:radial-gradient(closest-side, rgba(124,58,237,.22), rgba(79,70,229,.10), transparent 72%);
        filter:blur(20px);pointer-events:none;z-index:0}
  .eyebrow{position:relative;z-index:1;display:inline-flex;align-items:center;gap:12px;color:var(--muted);
           font-size:12px;letter-spacing:.26em;text-transform:uppercase;font-weight:600}
  .eyebrow::before,.eyebrow::after{content:"";width:28px;height:1px}
  .eyebrow::before{background:linear-gradient(90deg,transparent,#c9bce8)}
  .eyebrow::after{background:linear-gradient(90deg,#c9bce8,transparent)}
  h1{position:relative;z-index:1;font-family:'Fraunces',Georgia,serif;font-weight:600;
     font-size:clamp(56px,13.5vw,96px);line-height:.96;letter-spacing:-.03em;margin:20px 0 16px;
     background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 48%,#db2777 100%);
     -webkit-background-clip:text;background-clip:text;color:transparent}
  .sub{position:relative;z-index:1;color:var(--muted);font-size:18px;max-width:44ch;margin:0 auto}
  .sub em{font-family:'Fraunces',Georgia,serif;font-style:italic;color:var(--ink);font-weight:500}

  h2{font-size:12px;text-transform:uppercase;letter-spacing:.14em;color:var(--muted);font-weight:700;margin:40px 0 18px}
  .cards{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
  @media (min-width:680px){.cards{grid-template-columns:repeat(3,1fr);gap:14px}}
  @media (min-width:920px){.cards{grid-template-columns:repeat(4,1fr)}}
  .card{position:relative;display:flex;flex-direction:column;align-items:flex-start;gap:12px;background:var(--card);
        border:1px solid var(--line);border-radius:20px;padding:16px;box-shadow:var(--shadow);
        transition:transform .2s cubic-bezier(.2,.7,.2,1), box-shadow .2s}
  .card:hover{transform:translateY(-3px);box-shadow:var(--shadow-h)}
  .card:active{transform:scale(.98)}
  .ai{width:56px;height:56px;flex:0 0 auto;display:block;border-radius:15px;box-shadow:0 3px 9px rgba(20,23,30,.16)}
  .cmain{min-width:0}
  .nm{font-weight:600;font-size:15.5px;letter-spacing:-.01em;display:block}
  .card p{margin:5px 0 0;color:var(--muted);font-size:12.5px;line-height:1.46}
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
    <div class="brandtile">__MARK__</div>
    <div class="brandname">Dash <span>· by Matthew</span></div>
  </div>
</div>

<header>
  <div class="blob"></div>
  <div class="wrap">
    <div class="eyebrow">Personal app hub</div>
    <h1>Dash</h1>
    <p class="sub">All my apps, <em>one tap away.</em></p>
  </div>
</header>

<main class="wrap">
  <h2>Apps</h2>
  <div class="cards">__APPS__</div>
</main>

<footer><div class="wrap">Designed &amp; built by Matthew Russell</div></footer>
</body>
</html>'''

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = ('{"name":"Dash","short_name":"Dash","start_url":"./",'
            '"display":"standalone","background_color":"#f5f4f1","theme_color":"#f5f4f1",'
            '"icons":[{"src":"icon-192.png","sizes":"192x192","type":"image/png","purpose":"any"},'
            '{"src":"icon-512.png","sizes":"512x512","type":"image/png","purpose":"any maskable"}]}')


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
        elif p == '/manifest.webmanifest':
            self._send(MANIFEST, 'application/manifest+json')
        elif p in ('/apple-touch-icon.png', '/icon-192.png', '/icon-512.png'):
            try:
                with open(os.path.join(HERE, p.lstrip('/')), 'rb') as f:
                    self._send(f.read(), 'image/png')
            except OSError:
                self.send_response(404); self.end_headers(); self.wfile.write(b'not found')
        elif p in ('/health', '/healthz'):
            self._send('ok', 'text/plain')
        else:
            self.send_response(404); self.end_headers(); self.wfile.write(b'not found')

if __name__ == '__main__':
    print(f"App Hub on :{PORT} base='{BASE or '/'}'")
    ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()

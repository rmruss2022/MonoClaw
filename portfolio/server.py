#!/usr/bin/env python3
"""
Public App Hub for Matthew — a polished public landing page linking to all his apps.
Zero-dep Python stdlib server, served at root for a Cloudflare tunnel.

Links use each app's real URL. Apps that hold private data or an API key stay on
the tailnet (open for Matthew from anywhere, not for strangers); only genuinely
public apps get a public link.

Env:
  PORTFOLIO_PORT   (default 18824)
  PORTFOLIO_BASE   optional mount path (default "" = root)
"""
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORTFOLIO_PORT", "18824"))
BASE = (os.environ.get("PORTFOLIO_BASE", "").rstrip("/"))
HUB = "https://bushwick.tail9d821f.ts.net"

# (emoji, name, url_or_None, description, status)  status: "public" | "private" | "wip"
APPS = [
    ("🧭", "Waypoint", HUB + "/waypoint/",
     "AI driving GPS — spoken turn-by-turn, an agentic “ask &amp; route” assistant, and live local-area briefings.", "private"),
    ("🧳", "Travelog", HUB + "/travelog/",
     "AI travel journal — place &amp; history briefings, reflective journaling, and AI photo collages.", "private"),
    ("🏠", "openhome", "https://pi.tail9d821f.ts.net/",
     "Self-hosted smart-home hub — lights, music, and climate with a voice agent.", "private"),
    ("👥", "Rolodex", HUB + "/rolodex/",
     "Personal network CRM — contacts, follow-ups, a reach-out queue, and insights.", "private"),
    ("🩺", "Ora Health", None,
     "Agentic-AI iOS wellness app — dynamic conversations, daily meditations &amp; mindset work. React Native · ElevenLabs.", "wip"),
    ("🤝", "Favorly", None,
     "Microfavors &amp; Helping Hands — a community favor-exchange app. MVP backend built.", "wip"),
    ("🎵", "Dropstick", None,
     "Offline Wi-Fi USB stick for peer-to-peer music sharing — no internet needed. Go · SQLite.", "wip"),
]

TAGS = {
    "public":  '<span class="tag pub">Public</span>',
    "private": '<span class="tag priv">Private</span>',
    "wip":     '<span class="tag wip">In&nbsp;progress</span>',
}

def app_card(emoji, name, url, desc, status):
    tag = TAGS.get(status, "")
    inner = (f'<div class="ico">{emoji}</div>'
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
<meta name="description" content="A hub of apps built by Matthew Russell — AI driving GPS, a smart-home system, dashboards, and more."/>
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

  header{padding:88px 0 40px;text-align:center}
  .kick{font-size:12px;letter-spacing:.2em;text-transform:uppercase;color:var(--muted);font-weight:600}
  h1{font-family:'Fraunces',Georgia,serif;font-weight:600;font-size:clamp(42px,8.5vw,72px);line-height:1.02;letter-spacing:-.02em;margin:18px 0 16px}
  .sub{color:var(--muted);font-size:18px;max-width:50ch;margin:0 auto}
  .legend{display:inline-flex;gap:18px;margin-top:24px;font-size:12.5px;color:var(--muted);align-items:center}
  .legend b{font-weight:600;color:var(--ink)}
  .dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px;vertical-align:middle}
  .dot.g{background:#12a25a}.dot.a{background:#caa43a}.dot.n{background:#9aa1ac}

  h2{font-size:12px;text-transform:uppercase;letter-spacing:.14em;color:var(--muted);font-weight:700;margin:56px 0 18px}
  .cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:16px}
  .card{position:relative;display:flex;align-items:flex-start;gap:14px;background:var(--card);
        border:1px solid var(--line);border-radius:18px;padding:18px 18px 19px;box-shadow:var(--shadow);
        transition:transform .2s cubic-bezier(.2,.7,.2,1), box-shadow .2s}
  .card:hover{transform:translateY(-3px);box-shadow:var(--shadow-h)}
  .ico{width:46px;height:46px;flex:0 0 auto;border-radius:13px;background:var(--accent-soft);
       display:flex;align-items:center;justify-content:center;font-size:22px}
  .cmain{flex:1;min-width:0}
  .crow{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
  .nm{font-weight:600;font-size:16.5px;letter-spacing:-.01em}
  .tag{font-size:10.5px;font-weight:600;padding:2px 8px;border-radius:999px;letter-spacing:.02em}
  .tag.pub{color:#0a7d49;background:#e4f6ec}
  .tag.priv{color:#8a6d1a;background:#f7eecf}
  .tag.wip{color:#5b6472;background:#edeef1}
  .card.wipcard{cursor:default}
  .card.wipcard:hover{transform:none;box-shadow:var(--shadow)}
  .card p{margin:5px 0 0;color:var(--muted);font-size:14px;line-height:1.52}
  .go{position:absolute;top:17px;right:18px;color:#cdd0d7;font-size:17px;transition:transform .2s, color .2s}
  .card:hover .go{color:var(--accent);transform:translate(3px,-3px)}

  .minis{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:11px}
  .mini{display:flex;gap:12px;align-items:flex-start;padding:14px 15px;border-radius:14px;background:rgba(255,255,255,.6);border:1px solid var(--line)}
  .mi{font-size:18px;line-height:1.4}
  .mn{font-weight:600;font-size:14.5px}
  .md{color:var(--muted);font-size:12.5px;margin-top:2px;line-height:1.45}

  footer{text-align:center;color:var(--muted);font-size:13px;padding:60px 0 72px}
  footer a{color:var(--accent);font-weight:500}
  @media (max-width:560px){header{padding:60px 0 28px}.legend{flex-direction:column;gap:8px}}
</style>
</head>
<body>
<header><div class="wrap">
  <div class="kick">Matthew Russell · Software Engineer</div>
  <h1>Things I've built.</h1>
  <p class="sub">A living hub of __N__ apps and projects — an AI driving companion, a smart home, dashboards, and more.</p>
  <div class="legend">
    <span><span class="dot a"></span><b>Private</b> — opens on my devices</span>
    <span><span class="dot n"></span><b>In progress</b> — building</span>
  </div>
</div></header>

<main class="wrap">
  <h2>Apps</h2>
  <div class="cards">__APPS__</div>
</main>

<footer><div class="wrap">
  Designed &amp; built by Matthew Russell · <a href="https://web-production-970f8.up.railway.app/" target="_blank" rel="noopener">Daylight</a> is public to try
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

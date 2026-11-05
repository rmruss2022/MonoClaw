#!/usr/bin/env python3
"""
OpenClaw command-hub portal — Matthew's daily reports + voice-note (mp3) archive.

- Reports come from portal/reports/*.json  (each: {date, title, text, audio?})
- Voice notes are auto-discovered from the TTS output dir (mp3/ogg), newest first.
- Access is locked at the network layer (Tailscale-only `tailscale serve`), with an
  optional shared token as defense-in-depth (PORTAL_TOKEN env; blank = no token gate).

Zero third-party deps — stdlib http.server only, so it's reboot-safe and light.
"""
import json, os, re, html, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone

PORT      = int(os.environ.get("PORTAL_PORT", "18820"))
TOKEN     = os.environ.get("PORTAL_TOKEN", "").strip()
BASE_HREF = (os.environ.get("PORTAL_BASE", "").rstrip("/") + "/") or "/"  # e.g. "/reports/" when mounted under the command hub
BASE      = "/root/.openclaw/workspace"
REPORTS   = os.path.join(BASE, "portal", "reports")
# scan every place voice notes can land (manual edge-tts + native tts tool)
TTS_DIRS  = [os.path.join(BASE, "media", "tts"), "/root/.openclaw/tts-out"]
TTS_DIR   = TTS_DIRS[0]  # default write/lookup dir for /audio serving fallback
AUDIO_EXT = (".mp3", ".ogg", ".m4a", ".wav")
WEBAPP    = os.path.join(BASE, "portal", "webapp")  # new single-page app
STATIC_CT = {".html":"text/html; charset=utf-8",".webmanifest":"application/manifest+json",
             ".svg":"image/svg+xml",".js":"application/javascript",".css":"text/css",
             ".png":"image/png",".ico":"image/x-icon"}

def list_reports():
    out = []
    if os.path.isdir(REPORTS):
        for fn in os.listdir(REPORTS):
            if not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(REPORTS, fn)) as f:
                    r = json.load(f)
                r["_id"] = fn[:-5]
                r["category"] = ("nightsweep"
                                 if r["_id"].endswith("-nightsweep")
                                 or "night sweep" in str(r.get("title", "")).lower()
                                 else "nyc")
                out.append(r)
            except Exception:
                pass
    # newest first by date string (ISO) then id
    out.sort(key=lambda r: (str(r.get("date", "")), r.get("_id", "")), reverse=True)
    return out

def resolve_audio(name):
    """Find an audio file by basename across all TTS dirs."""
    for d in TTS_DIRS:
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p
    return None

def list_audio():
    rows = []
    for d in TTS_DIRS:
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if fn.lower().endswith(AUDIO_EXT):
                rows.append((fn, os.path.join(d, fn)))
    rows.sort(key=lambda r: os.path.getmtime(r[1]), reverse=True)
    out, seen = [], set()
    for fn, p in rows:
        stem = os.path.splitext(fn)[0]
        if stem in seen:
            continue
        seen.add(stem)
        # prefer an mp3 sibling as the primary playable
        primary = fn
        if not fn.lower().endswith(".mp3"):
            mp3 = resolve_audio(stem + ".mp3")
            if mp3:
                primary, p = os.path.basename(mp3), mp3
        out.append({
            "name": stem.replace("-", " ").replace("_", " "),
            "file": primary,
            "size": os.path.getsize(p),
            "mtime": datetime.fromtimestamp(os.path.getmtime(p), timezone.utc).isoformat(),
        })
    return out

def human_size(n):
    for u in ("B", "KB", "MB"):
        if n < 1024:
            return f"{n:.0f} {u}"
        n /= 1024
    return f"{n:.1f} GB"

def rel_time(iso):
    try:
        t = datetime.fromisoformat(iso)
        d = datetime.now(timezone.utc) - t
        s = int(d.total_seconds())
        if s < 3600:  return f"{s//60}m ago"
        if s < 86400: return f"{s//3600}h ago"
        return f"{s//86400}d ago"
    except Exception:
        return ""

PAGE = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<base href="{base}">
<title>OpenClaw · Reports</title>
<style>
:root{{--bg:#0e1014;--panel:#171a21;--panel2:#1e222b;--line:#272c37;--text:#e7ebf3;--muted:#8b93a7;--accent:#3ddc97;--r:14px}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}}
header{{padding:calc(env(safe-area-inset-top,0) + 18px) 20px 14px;border-bottom:1px solid var(--line);background:linear-gradient(180deg,#141821,var(--bg));position:sticky;top:0;z-index:5}}
h1{{margin:0;font-size:19px;font-weight:800;letter-spacing:-.02em}}h1 span{{color:var(--accent)}}
.sub{{color:var(--muted);font-size:12.5px;margin-top:2px}}
main{{max-width:820px;margin:0 auto;padding:18px 16px calc(40px + env(safe-area-inset-bottom,0))}}
.tabs{{display:flex;gap:8px;margin-bottom:16px}}
.tab{{flex:1;text-align:center;padding:10px;border:1px solid var(--line);border-radius:12px;background:var(--panel);color:var(--muted);font-weight:700;cursor:pointer;font-size:13px}}
.tab.on{{color:var(--accent);border-color:var(--accent);background:rgba(61,220,151,.08)}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:15px 17px;margin-bottom:12px}}
.card h2{{margin:0 0 3px;font-size:16px}}.card .when{{color:var(--muted);font-size:12px;margin-bottom:10px}}
.card pre{{white-space:pre-wrap;word-wrap:break-word;font:inherit;margin:0;color:#d5dbe8}}
.audio{{display:flex;flex-direction:column;gap:6px}}
.audio .row{{display:flex;justify-content:space-between;align-items:baseline;gap:10px}}
.audio .nm{{font-weight:700;text-transform:capitalize}}.audio .meta{{color:var(--muted);font-size:12px;white-space:nowrap}}
audio{{width:100%;margin-top:4px;height:38px}}
.empty{{color:var(--muted);text-align:center;padding:40px 0}}
.hidden{{display:none}}
a.dl{{color:var(--accent);text-decoration:none;font-size:12px}}
</style></head><body>
<header><h1>Open<span>Claw</span> · Reports</h1><div class="sub">Daily reports &amp; voice notes · private to your devices</div></header>
<main>
  <div class="tabs">
    <div class="tab on" id="tabR" onclick="show('r')">📄 Reports</div>
    <div class="tab" id="tabA" onclick="show('a')">🎙️ Voice notes</div>
  </div>
  <div id="reports">{reports}</div>
  <div id="audio" class="hidden">{audio}</div>
</main>
<script>
function show(w){{
  document.getElementById('reports').classList.toggle('hidden', w!=='r');
  document.getElementById('audio').classList.toggle('hidden', w!=='a');
  document.getElementById('tabR').classList.toggle('on', w==='r');
  document.getElementById('tabA').classList.toggle('on', w==='a');
}}
</script></body></html>"""

def render_reports(reports, q):
    if not reports:
        return '<div class="empty">No reports yet — your next daily digest will appear here.</div>'
    out = []
    for r in reports:
        title = html.escape(str(r.get("title", "Report")))
        date  = html.escape(str(r.get("date", r.get("_id", ""))))
        text  = html.escape(str(r.get("text", "")))
        audio = r.get("audio")
        aud = ""
        if audio:
            src = "audio/" + urllib.parse.quote(audio) + q
            aud = f'<audio controls preload="none" src="{src}"></audio>'
        out.append(f'<div class="card"><h2>{title}</h2><div class="when">{date}</div><pre>{text}</pre>{aud}</div>')
    return "\n".join(out)

def render_audio(items, q):
    if not items:
        return '<div class="empty">No voice notes yet.</div>'
    out = []
    for a in items:
        nm = html.escape(a["name"]); meta = f'{human_size(a["size"])} · {rel_time(a["mtime"])}'
        src = "audio/" + urllib.parse.quote(a["file"]) + q
        dl  = "audio/" + urllib.parse.quote(a["file"]) + q + ("&" if q else "?") + "dl=1"
        out.append(f'<div class="card audio"><div class="row"><span class="nm">{nm}</span>'
                   f'<span class="meta">{html.escape(meta)} · <a class="dl" href="{dl}">download</a></span></div>'
                   f'<audio controls preload="none" src="{src}"></audio></div>')
    return "\n".join(out)

class H(BaseHTTPRequestHandler):
    def _tok_ok(self, qs):
        if not TOKEN:
            return True
        return qs.get("token", [""])[0] == TOKEN or self.headers.get("X-Portal-Token") == TOKEN

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(u.query)
        if not self._tok_ok(qs):
            self.send_response(403); self.end_headers(); self.wfile.write(b"forbidden"); return
        q = ("?token=" + urllib.parse.quote(TOKEN)) if TOKEN else ""

        # ---- new single-page app (served from portal/webapp) ----
        app_index = os.path.join(WEBAPP, "index.html")
        if (u.path == "/" or u.path == "/index.html") and os.path.isfile(app_index):
            with open(app_index, "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8"); return
        # serve static assets of the app (manifest, icon, etc.) by basename
        if u.path.startswith("/") and "/" not in u.path[1:] and u.path not in ("/api/reports",):
            name = urllib.parse.unquote(u.path[1:])
            cand = os.path.join(WEBAPP, name)
            if name and ".." not in name and os.path.isfile(cand):
                ext = os.path.splitext(name)[1].lower()
                with open(cand, "rb") as f:
                    self._send(200, f.read(), STATIC_CT.get(ext, "application/octet-stream")); return

        if u.path == "/legacy" or u.path == "/index.html":
            reports = list_reports(); audio = list_audio()
            body = PAGE.format(base=BASE_HREF, reports=render_reports(reports, q), audio=render_audio(audio, q))
            self._send(200, body.encode(), "text/html; charset=utf-8"); return

        if u.path == "/api/reports":
            self._send(200, json.dumps({"reports": list_reports(), "audio": list_audio()}).encode(),
                       "application/json"); return

        if u.path.startswith("/audio/"):
            name = urllib.parse.unquote(u.path[len("/audio/"):])
            if "/" in name or ".." in name:
                self.send_response(400); self.end_headers(); return
            p = resolve_audio(name)
            if not p:
                self.send_response(404); self.end_headers(); return
            ct = "audio/mpeg" if name.lower().endswith(".mp3") else \
                 "audio/ogg" if name.lower().endswith(".ogg") else "application/octet-stream"
            with open(p, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            if qs.get("dl"):
                self.send_header("Content-Disposition", f'attachment; filename="{name}"')
            self.end_headers(); self.wfile.write(data); return

        self.send_response(404); self.end_headers()

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(u.query)
        if u.path == "/api/ingest":
            # save a report: {date,title,text,audio?}. token required if configured.
            if not self._tok_ok(qs):
                self.send_response(403); self.end_headers(); return
            n = int(self.headers.get("Content-Length", 0))
            try:
                r = json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                self.send_response(400); self.end_headers(); return
            date = str(r.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"))
            rid  = re.sub(r"[^0-9A-Za-z_-]", "_", str(r.get("id") or date))[:64] or date
            with open(os.path.join(REPORTS, rid + ".json"), "w") as f:
                json.dump({"date": date, "title": r.get("title", "Report"),
                           "text": r.get("text", ""), "audio": r.get("audio")}, f, indent=1)
            self._send(200, b'{"ok":true}', "application/json"); return
        self.send_response(404); self.end_headers()

    def _send(self, code, body, ct):
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(body)

    def log_message(self, *a):  # quiet
        pass

if __name__ == "__main__":
    print(f"portal on :{PORT}  token={'set' if TOKEN else 'none'}  reports={REPORTS}")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()

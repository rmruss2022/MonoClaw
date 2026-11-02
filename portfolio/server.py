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
import os, json, sqlite3, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---- Foreman: live subagent activity, read from OpenClaw's state DB ----
STATE_DB = os.environ.get("OPENCLAW_STATE_DB", "/root/.openclaw/state/openclaw.sqlite")
PROJECT_NAMES = {
    "creator-cut": "Creator Cut", "recilia": "Nightbloom", "travelog": "Trip Sync",
    "open-home": "openhome", "rolodex": "Rolodex", "ora-health": "Ora",
    "foreman": "Foreman", "MonoClaw": "MonoClaw", "slipstream": "Slipstream",
    "chase": "Slipstream", "croppa": "Croppa", "inkling": "Inkling",
}
def _proj(wd):
    if not wd:
        return "—"
    return PROJECT_NAMES.get(os.path.basename(wd.rstrip("/")), os.path.basename(wd.rstrip("/")))

def foreman_data():
    """Snapshot of subagent runs from OpenClaw's state DB, newest first."""
    out = {"ts": int(time.time() * 1000), "jobs": [], "stats": {}}
    try:
        con = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True, timeout=1.5)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT run_id, child_session_key, requester_display_key, task, task_name, "
            "label, model, workspace_dir, spawn_mode, created_at, started_at, ended_at, "
            "ended_reason, outcome_json, frozen_result_text FROM subagent_runs "
            "ORDER BY created_at DESC LIMIT 50").fetchall()
        con.close()
    except Exception as e:
        out["error"] = str(e)
        return out
    now = out["ts"]
    counts = {"running": 0, "queued": 0, "done": 0, "failed": 0}
    for r in rows:
        d = dict(r)
        started, ended = d.get("started_at"), d.get("ended_at")
        status = "queued"
        if ended:
            status = "done"
            reason = (d.get("ended_reason") or "").lower()
            oj = {}
            try:
                oj = json.loads(d.get("outcome_json") or "{}")
            except Exception:
                pass
            if "error" in reason or "fail" in reason or oj.get("error") or oj.get("status") in ("error", "failed"):
                status = "failed"
        elif started:
            status = "running"
        counts[status] = counts.get(status, 0) + 1
        base = started or d.get("created_at") or now
        elapsed = max(0, int(((ended or now) - base) / 1000))
        task = (d.get("task") or d.get("task_name") or d.get("label") or "").strip().replace("\n", " ")
        if len(task) > 180:
            task = task[:177] + "…"
        result = None
        if status in ("done", "failed"):
            result = (d.get("frozen_result_text") or "")
            if not result:
                try:
                    oj = json.loads(d.get("outcome_json") or "{}")
                    result = oj.get("summary") or oj.get("result") or ""
                except Exception:
                    result = ""
            result = (result or "").strip().replace("\n", " ")
            if len(result) > 220:
                result = result[:217] + "…"
        # prefer the "project:jobid" label convention; fall back to the workspace dir
        lbl = (d.get("label") or "")
        if ":" in lbl:
            pfx = lbl.split(":", 1)[0]
            project = PROJECT_NAMES.get(pfx, pfx)
        else:
            project = _proj(d.get("workspace_dir"))
        out["jobs"].append({
            "id": d.get("run_id"), "project": project,
            "status": status, "task": task, "model": d.get("model") or "",
            "mode": d.get("spawn_mode") or "", "elapsed": elapsed,
            "label": d.get("label") or d.get("task_name") or "",
            "requester": d.get("requester_display_key") or "", "result": result,
            "created": d.get("created_at"), "started": started, "ended": ended,
        })
    out["stats"] = counts
    return out

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
 "chase": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_ch" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f59e0b"/><stop offset="1" stop-color="#ef4444"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_ch)"/><line x1="16" y1="12" x2="16" y2="41" stroke="#fff" stroke-width="3" stroke-linecap="round"/><g fill="#fff"><rect x="18" y="14" width="7" height="7"/><rect x="32" y="14" width="7" height="7"/><rect x="25" y="21" width="7" height="7"/><rect x="18" y="28" width="7" height="7"/><rect x="32" y="28" width="7" height="7"/></g></svg>',
 "lumen": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_lm" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f5c977"/><stop offset="1" stop-color="#8b5cf6"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_lm)"/><circle cx="26" cy="26" r="6.6" fill="#fff"/><g stroke="#fff" stroke-width="2.6" stroke-linecap="round"><line x1="26" y1="10" x2="26" y2="15"/><line x1="26" y1="37" x2="26" y2="42"/><line x1="10" y1="26" x2="15" y2="26"/><line x1="37" y1="26" x2="42" y2="26"/><line x1="15.5" y1="15.5" x2="19" y2="19"/><line x1="33" y1="33" x2="36.5" y2="36.5"/><line x1="36.5" y1="15.5" x2="33" y2="19"/><line x1="19" y1="33" x2="15.5" y2="36.5"/></g></svg>',
 "reports": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_rp" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#a855f7"/><stop offset="1" stop-color="#6366f1"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_rp)"/><rect x="13" y="14" width="26" height="24" rx="2.5" fill="#fff"/><rect x="16.5" y="18" width="10" height="7" rx="1" fill="#8b5cf6"/><g fill="#b9a7f0"><rect x="28.5" y="18" width="7" height="2" rx="1"/><rect x="28.5" y="22.5" width="7" height="2" rx="1"/><rect x="16.5" y="28" width="19" height="2" rx="1"/><rect x="16.5" y="32" width="19" height="2" rx="1"/></g></svg>',
 "recilia": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_rc" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#22d3ee"/><stop offset="1" stop-color="#6366f1"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_rc)"/><circle cx="18" cy="26" r="3.1" fill="#fff"/><g fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round"><path d="M24 20a9 9 0 0 1 0 12"/><path d="M29 16a16 16 0 0 1 0 20"/><path d="M34 12.5a23 23 0 0 1 0 27"/></g></svg>',
 "creatorcut": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_cc" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#b983ff"/><stop offset="1" stop-color="#7c4dff"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_cc)"/><rect x="12" y="15" width="28" height="22" rx="3" fill="#fff"/><g fill="#7c4dff"><rect x="15" y="18" width="3.4" height="3.4" rx="0.8"/><rect x="15" y="30.6" width="3.4" height="3.4" rx="0.8"/><rect x="33.6" y="18" width="3.4" height="3.4" rx="0.8"/><rect x="33.6" y="30.6" width="3.4" height="3.4" rx="0.8"/></g><path d="M23 21.5l8 4.5-8 4.5z" fill="#7c4dff"/></svg>',
}

# (icon_key, name, url_or_None, description, status)  status: public | private | wip
APPS = [
    ("favorly", "Favorly", "https://dist-pi-rouge-27.vercel.app",
     "Microfavors &amp; Helping Hands — a community favor-exchange app. MVP backend built.", "public"),
    ("ora", "Ora Health", "https://ora-health-26.vercel.app",
     "Agentic-AI wellness app — dynamic conversations, daily meditations &amp; mindset work. React Native · ElevenLabs.", "public"),
    ("lumen", "Lumen", "https://lumen-production-a8c6.up.railway.app/",
     "Gamified meditation — every sit lights up a living world map, earns Light, builds streaks, and climbs weekly leagues. Guided voice journeys &amp; a reflective journal.", "public"),
    ("recilia", "Nightbloom", "https://recilia.bedrock.casa/",
     "A tinnitus companion that turns practice into a living night-garden you grow. Research-grade sound engine, daily streaks, and a glowing garden that fills in as the ringing recedes. React Native · Expo (web preview).", "public"),
    ("inkling", "Inkling", "https://inkling.bedrock.casa/",
     "Voice-first writing room — speak, and an AI librarian co-writes your book in your voice, tending your ideas like rare books.", "public"),
    ("waypoint", "Waypoint", "https://waypoint.bedrock.casa/",
     "AI driving GPS — spoken turn-by-turn, an agentic “ask &amp; route” assistant, and live local-area briefings.", "private"),
    ("travelog", "Travelog", "https://travelog.bedrock.casa/",
     "AI travel journal — place &amp; history briefings, reflective journaling, and AI photo collages.", "private"),
    ("openhome", "openhome", "https://home.bedrock.casa/",
     "Self-hosted smart-home hub — lights, music, and climate with a voice agent.", "private"),
    ("rolodex", "Rolodex", "https://rolodex.bedrock.casa/",
     "Personal network CRM — contacts, follow-ups, a reach-out queue, and insights.", "private"),
    ("croppa", "Croppa", "https://croppa.bedrock.casa/",
     "AI photo auto-crop — detects the subject and frames it, with one-tap ratios and full manual control.", "private"),
    ("chase", "Slipstream", "https://slipstream.bedrock.casa/",
     "AI video follow-cam — lock onto a car or object and it stays centered as it moves. Built for race footage.", "private"),
    ("creatorcut", "Creator Cut", "https://creator-cut-production.up.railway.app/",
     "AI video editor that cuts your footage to the beat — a music video, or an ad with an AI-written script, voiceover &amp; on-screen text. Every cut lands on the downbeat. (Token required.)", "private"),
    ("dropstick", "Dropstick", None,
     "Peer-to-peer music sharing for DJs — swap tracks &amp; crates device-to-device over local Wi-Fi, no internet. Go · SQLite.", "wip"),
]

# Claw Apps — apps Claw runs for Matthew, on permanent bedrock.casa URLs
CLAW_APPS = [
    ("reports", "Daily Reports &amp; News", "https://reports.bedrock.casa/",
     "Daily NYC news digest &amp; archive — morning briefings with inline mp3 voice notes.", "public"),
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
    # All apps now live on permanent bedrock.casa URLs — no rotating-tunnel lookups needed.
    def rows_for(items):
        seen = set(); out = []
        for a in items:
            if a[0] in seen:          # guard against duplicate entries
                continue
            seen.add(a[0])
            out.append(app_card(*a))
        return "\n".join(out)
    apps = rows_for(APPS)
    claw = rows_for(CLAW_APPS)
    return (PAGE.replace("__APPS__", apps)
                .replace("__CLAW__", claw)
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
  /* Today — daily to-do mini app */
  .todo{position:relative;border-radius:20px;padding:22px;box-shadow:0 1px 2px rgba(20,23,30,.04),0 18px 44px -14px rgba(124,58,237,.22);max-width:720px;
    background:linear-gradient(#fff,#fff) padding-box, linear-gradient(135deg,#6366f1,#a855f7,#ec4899) border-box;border:1.5px solid transparent}
  .todo-head{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px}
  .todo-eyebrow{font-size:11px;font-weight:800;letter-spacing:.16em;text-transform:uppercase;
    background:linear-gradient(135deg,#6366f1,#ec4899);-webkit-background-clip:text;background-clip:text;color:transparent}
  .todo h2.todo-date{margin:3px 0 0;font-size:21px}
  .todo-count{font-size:13px;color:var(--muted);font-weight:600;white-space:nowrap}
  .todo-bar{height:7px;border-radius:5px;background:#eceaf4;overflow:hidden;margin:8px 0 16px}
  .todo-bar i{display:block;height:100%;border-radius:5px;background:linear-gradient(90deg,#6366f1,#a855f7,#ec4899);transition:width .35s ease;box-shadow:0 0 10px -2px #a855f7aa}
  .todo-add{display:flex;gap:10px;margin-bottom:14px}
  .todo-add input{flex:1;border:1px solid var(--line);border-radius:14px;padding:13px 15px;font-size:15px;background:#faf9fc;color:var(--ink);outline:none;transition:border-color .15s,box-shadow .15s}
  .todo-add input:focus{border-color:#a855f7;box-shadow:0 0 0 3px rgba(168,85,247,.14)}
  .todo-add button{width:48px;border:none;border-radius:14px;background:linear-gradient(135deg,#6366f1,#a855f7,#ec4899);color:#fff;font-size:24px;cursor:pointer;line-height:1;box-shadow:0 8px 18px -8px rgba(124,58,237,.6);transition:transform .1s,filter .15s}
  .todo-add button:hover{filter:brightness(1.07)} .todo-add button:active{transform:scale(.93)}
  .todo-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:7px}
  .todo-item{display:flex;align-items:center;gap:11px;padding:11px 12px;border-radius:14px;border:1px solid transparent;background:#fbfafe;cursor:pointer;transition:background .12s,border-color .12s,box-shadow .12s,transform .08s}
  .todo-item:hover{background:#fff;border-color:var(--line);box-shadow:0 6px 16px -10px rgba(67,56,202,.45)}
  .todo-item .moves{display:flex;flex-direction:column;gap:1px;flex:0 0 auto}
  .todo-item .mv{border:none;background:none;color:#c2c6d2;font-size:11px;line-height:.9;cursor:pointer;padding:1px 2px;border-radius:4px}
  .todo-item .mv:hover:not(:disabled){color:#7c3aed}
  .todo-item .mv:disabled{opacity:.25;cursor:default}
  .todo-item .box{width:23px;height:23px;border:2px solid #cfd2dc;border-radius:8px;cursor:pointer;flex:0 0 auto;display:flex;align-items:center;justify-content:center;color:#fff;font-size:14px;transition:border-color .12s,background .12s}
  .todo-item.done .box{border-color:transparent;background:linear-gradient(135deg,#6366f1,#ec4899)}
  .todo-item .txt{flex:1;font-size:15px;color:var(--ink);cursor:pointer}
  .todo-item.done .txt{color:var(--muted);text-decoration:line-through}
  .todo-item .del{border:none;background:none;color:#c6cad4;font-size:17px;cursor:pointer;opacity:0;transition:opacity .12s,color .12s}
  .todo-item:hover .del{opacity:1} .todo-item .del:hover{color:#ec4899}
  .todo-empty{color:var(--muted);font-size:14px;padding:10px 2px}
  .todo-foot{margin-top:14px;display:flex;justify-content:flex-end}
  .todo-clear{border:none;background:none;color:var(--muted);font-size:13px;cursor:pointer}
  .todo-clear:hover{color:#ec4899}
  /* Foreman — live subagent activity */
  .foreman{position:relative;border-radius:20px;padding:22px;max-width:720px;
    box-shadow:0 1px 2px rgba(20,23,30,.04),0 18px 44px -14px rgba(37,99,235,.22);
    background:linear-gradient(#fff,#fff) padding-box,linear-gradient(135deg,#2563eb,#06b6d4,#22d3ee) border-box;border:1.5px solid transparent}
  .fm-head{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px}
  .fm-eyebrow{font-size:11px;font-weight:800;letter-spacing:.16em;text-transform:uppercase;
    background:linear-gradient(135deg,#2563eb,#06b6d4);-webkit-background-clip:text;background-clip:text;color:transparent}
  .fm-title{margin:3px 0 0;font-size:21px}
  .fm-stats{font-size:12.5px;color:var(--muted);font-weight:600;white-space:nowrap}
  .fm-stats b{font-weight:800;color:var(--ink)}
  .fm-list{display:flex;flex-direction:column;gap:8px}
  .fm-empty{color:var(--muted);font-size:14px;padding:10px 2px}
  .fm-job{display:flex;align-items:flex-start;gap:11px;padding:11px 13px;border-radius:14px;background:#f7faff;border:1px solid #eaf0fb}
  .fm-dot{width:9px;height:9px;border-radius:50%;flex:0 0 auto;margin-top:5px}
  .fm-dot.running{background:#2563eb;animation:fmpulse 1.4s infinite}
  .fm-dot.queued{background:#f59e0b}.fm-dot.done{background:#10b981}.fm-dot.failed{background:#ef4444}
  @keyframes fmpulse{0%{box-shadow:0 0 0 0 rgba(37,99,235,.45)}70%{box-shadow:0 0 0 7px rgba(37,99,235,0)}100%{box-shadow:0 0 0 0 rgba(37,99,235,0)}}
  .fm-main{min-width:0;flex:1}
  .fm-row1{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  .fm-proj{font-weight:700;font-size:14px}
  .fm-badge{font-size:10px;font-weight:800;letter-spacing:.04em;text-transform:uppercase;padding:2px 7px;border-radius:999px}
  .fm-badge.running{background:#e8efff;color:#2563eb}.fm-badge.queued{background:#fef3e2;color:#b45309}
  .fm-badge.done{background:#e6f7ef;color:#047857}.fm-badge.failed{background:#fdeaea;color:#b91c1c}
  .fm-elapsed{margin-left:auto;font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}
  .fm-task{margin:3px 0 0;font-size:13px;color:#2b3340;line-height:1.45;word-break:break-word}
  .fm-result{margin:4px 0 0;font-size:12px;color:var(--muted);line-height:1.4}
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

<section class="wrap" style="margin-bottom:8px">
  <div class="todo">
    <div class="todo-head">
      <div>
        <div class="todo-eyebrow">Today</div>
        <h2 class="todo-date" id="todoDate">—</h2>
      </div>
      <span class="todo-count" id="todoCount"></span>
    </div>
    <div class="todo-bar"><i id="todoBar" style="width:0%"></i></div>
    <form id="todoForm" class="todo-add">
      <input id="todoInput" placeholder="Add a task for today…" autocomplete="off"/>
      <button type="submit" aria-label="Add task">+</button>
    </form>
    <ul id="todoList" class="todo-list"></ul>
    <div class="todo-foot"><button id="todoClear" class="todo-clear">Clear completed</button></div>
  </div>
</section>

<main class="wrap">
  <h2>Apps</h2>
  <div class="cards">__APPS__</div>

  <h2>Claw Apps</h2>
  <div class="cards">__CLAW__</div>
</main>

<section class="wrap" style="margin-top:14px">
  <div class="foreman">
    <div class="fm-head">
      <div>
        <div class="fm-eyebrow">Foreman · live</div>
        <h2 class="fm-title">Subagents at work</h2>
      </div>
      <span class="fm-stats" id="fmStats"></span>
    </div>
    <div id="fmList" class="fm-list"></div>
  </div>
</section>

<footer><div class="wrap">Designed &amp; built by Matthew Russell</div></footer>
<script>
(function(){
  var KEY='dash_todos_v1';
  var list=document.getElementById('todoList'),input=document.getElementById('todoInput'),
      form=document.getElementById('todoForm'),count=document.getElementById('todoCount'),
      dateEl=document.getElementById('todoDate'),clearBtn=document.getElementById('todoClear'),
      bar=document.getElementById('todoBar');
  dateEl.textContent=new Date().toLocaleDateString(undefined,{weekday:'long',month:'long',day:'numeric'});
  var todos=[];try{todos=JSON.parse(localStorage.getItem(KEY))||[];}catch(e){}
  function save(){try{localStorage.setItem(KEY,JSON.stringify(todos));}catch(e){}}
  function move(from,to){if(to<0||to>=todos.length)return;var m=todos.splice(from,1)[0];todos.splice(to,0,m);save();render();}
  function render(){
    list.innerHTML='';
    if(!todos.length){var e=document.createElement('li');e.className='todo-empty';e.textContent='Nothing yet — add your first task.';list.appendChild(e);}
    todos.forEach(function(t,i){
      var li=document.createElement('li');li.className='todo-item'+(t.done?' done':'');
      li.onclick=function(){t.done=!t.done;save();render();};   // whole row = one tap to check
      var mv=document.createElement('span');mv.className='moves';
      var up=document.createElement('button');up.className='mv';up.innerHTML='▴';up.title='Move up';up.disabled=(i===0);up.onclick=function(ev){ev.stopPropagation();move(i,i-1);};
      var dn=document.createElement('button');dn.className='mv';dn.innerHTML='▾';dn.title='Move down';dn.disabled=(i===todos.length-1);dn.onclick=function(ev){ev.stopPropagation();move(i,i+1);};
      mv.appendChild(up);mv.appendChild(dn);
      var box=document.createElement('span');box.className='box';box.textContent=t.done?'✓':'';
      var txt=document.createElement('span');txt.className='txt';txt.textContent=t.text;
      var del=document.createElement('button');del.className='del';del.innerHTML='✕';del.title='Delete';del.onclick=function(ev){ev.stopPropagation();todos.splice(i,1);save();render();};
      li.appendChild(mv);li.appendChild(box);li.appendChild(txt);li.appendChild(del);
      list.appendChild(li);
    });
    var done=todos.filter(function(t){return t.done;}).length;
    count.textContent=todos.length?(done+' of '+todos.length+' done'):'';
    bar.style.width=(todos.length?Math.round(100*done/todos.length):0)+'%';
  }
  form.onsubmit=function(ev){ev.preventDefault();var v=input.value.trim();if(!v)return;todos.push({text:v,done:false});input.value='';save();render();};
  clearBtn.onclick=function(){todos=todos.filter(function(t){return !t.done;});save();render();};
  render();
})();
// ---- Foreman live panel: poll subagent activity ----
(function(){
  var listEl=document.getElementById('fmList'),statsEl=document.getElementById('fmStats');
  if(!listEl)return;
  var order={running:0,queued:1,failed:2,done:3};
  function fmt(s){s=s||0;if(s<60)return s+'s';var m=Math.floor(s/60);if(m<60)return m+'m '+(s%60)+'s';var h=Math.floor(m/60);return h+'h '+(m%60)+'m';}
  function esc(s){return (s||'').replace(/[&<>]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;'}[c];});}
  function draw(d){
    var jobs=(d.jobs||[]).slice().sort(function(a,b){return (order[a.status]-order[b.status])||((b.created||0)-(a.created||0));});
    var s=d.stats||{};
    statsEl.innerHTML='<b>'+(s.running||0)+'</b> running · '+(s.queued||0)+' queued · '+(s.done||0)+' done'+((s.failed||0)?' · <b style="color:#ef4444">'+s.failed+' failed</b>':'');
    if(!jobs.length){listEl.innerHTML='<div class="fm-empty">No subagents yet — send a task in Telegram and watch them light up here.</div>';return;}
    listEl.innerHTML=jobs.map(function(j){
      var el=(j.status==='running')?fmt(j.elapsed):((j.status==='done'||j.status==='failed')?('took '+fmt(j.elapsed)):'');
      return '<div class="fm-job"><span class="fm-dot '+j.status+'"></span>'
        +'<div class="fm-main"><div class="fm-row1">'
        +'<span class="fm-proj">'+esc(j.project)+'</span>'
        +'<span class="fm-badge '+j.status+'">'+j.status+'</span>'
        +'<span class="fm-elapsed">'+el+'</span></div>'
        +'<div class="fm-task">'+esc(j.task||j.label||'(no task)')+'</div>'
        +(j.result?'<div class="fm-result">↳ '+esc(j.result)+'</div>':'')
        +'</div></div>';
    }).join('');
  }
  function tick(){fetch('api/foreman',{cache:'no-store'}).then(function(r){return r.json();}).then(draw).catch(function(){});}
  tick();setInterval(tick,2500);
})();
</script>
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
        elif p == '/api/foreman':
            self._send(json.dumps(foreman_data()), 'application/json; charset=utf-8')
        elif p in ('/health', '/healthz'):
            self._send('ok', 'text/plain')
        else:
            self.send_response(404); self.end_headers(); self.wfile.write(b'not found')

if __name__ == '__main__':
    print(f"App Hub on :{PORT} base='{BASE or '/'}'")
    ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()

#!/usr/bin/env python3
"""Claw Systems Map — a live architecture view of the whole OpenClaw estate.

Single-file stdlib server. The APP roster is read live from Foreman's
projects.json so it stays current; agents / edge / hosts / external layers are
curated below. Served at map.bedrock.casa.
"""
import json, os, html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("CLAWMAP_PORT", "18847"))
PROJECTS = "/root/MonoClaw/foreman/projects.json"

# host/port + grouping overlay for apps (keyed by foreman slug)
APP_META = {
    "marquee":     {"host": "droplet", "port": 18852, "group": "Consumer apps"},
    "recilia":     {"host": "droplet", "port": 18845, "group": "Consumer apps"},
    "lumen":       {"host": "railway", "port": None,  "group": "Consumer apps"},
    "ora-health":  {"host": "vercel",  "port": None,  "group": "Consumer apps"},
    "inkling":     {"host": "droplet", "port": 18826, "group": "Consumer apps"},
    "croppa":      {"host": "droplet", "port": 18842, "group": "Consumer apps"},
    "favorly":     {"host": "vercel",  "port": None,  "group": "Consumer apps"},
    "travelog":    {"host": "droplet", "port": 18825, "group": "Utility apps"},
    "rolodex":     {"host": "droplet", "port": 18831, "group": "Utility apps"},
    "chase":       {"host": "droplet", "port": 18843, "group": "Utility apps"},
    "contentforge":{"host": "droplet", "port": 18851, "group": "Internal tools"},
    "creator-cut": {"host": "railway", "port": None,  "group": "Consumer apps"},
    "open-home":   {"host": "pi",      "port": None,  "group": "Internal tools"},
    "recilia-api": {"host": "railway", "port": None,  "group": "Backends"},
    "foreman":     {"host": "droplet", "port": 18824, "group": "Agent infra"},
    "clawmap":     {"host": "droplet", "port": 18847, "group": "Agent infra"},
    "MonoClaw":    None,  # hide the meta-repo
}

AGENTS = [
    {"name": "Claw", "sub": "main agent — your direct line", "color": "#f5c977"},
    {"name": "Builder", "sub": "ships code & apps", "color": "#ff5c8a"},
    {"name": "Ora", "sub": "health / life-OS agent", "color": "#ec4899"},
    {"name": "Foreman", "sub": "job board + doctor/deploy orchestrator", "color": "#0ea5e9",
     "url": "https://dash.bedrock.casa/"},
    {"name": "Night Sweep", "sub": "nightly autonomous review → ship (3AM ET)", "color": "#8b5cf6"},
]

EDGE = [
    {"name": "bedrock.casa tunnel", "sub": "Cloudflare named tunnel → 17 subdomains (droplet)",
     "color": "#f59e0b"},
    {"name": "home.bedrock.casa", "sub": "separate Cloudflare tunnel on the Pi (openhome)",
     "color": "#f5c977"},
]

HOSTS = [
    {"name": "Droplet", "sub": "DigitalOcean — most app services + agents + SQLite state", "color": "#22c55e"},
    {"name": "Raspberry Pi", "sub": "openhome hub (home.bedrock.casa)", "color": "#14b8a6"},
    {"name": "Mac (voice)", "sub": "Edge-TTS voice server :18790", "color": "#06b6d4"},
    {"name": "ccut Claude gateway", "sub": "wraps signed-in Claude CLI as HTTP (ccut-llm.bedrock.casa)", "color": "#a855f7"},
    {"name": "Shared iOS creds", "sub": "/root/.openclaw/ios-creds — one Apple Dist cert → all apps", "color": "#64748b"},
]

EXTERNAL = [
    {"name": "Cloudflare", "sub": "DNS · tunnels · R2 storage"},
    {"name": "Railway", "sub": "hosts Lumen / Creator Cut / Recilia API"},
    {"name": "Vercel", "sub": "hosts Ora / Favorly"},
    {"name": "Expo / EAS", "sub": "iOS/Android cloud builds"},
    {"name": "App Store Connect", "sub": "TestFlight · App Store (shared ASC key)"},
    {"name": "Anthropic Claude", "sub": "agent brains + ccut gateway"},
    {"name": "Google Gemini", "sub": "Marquee discovery + grounding search"},
    {"name": "Firecrawl", "sub": "web scrape / content cache"},
]


def load_apps():
    try:
        data = json.load(open(PROJECTS))
    except Exception:
        return []
    out = []
    for p in data.get("projects", []):
        slug = p.get("slug")
        meta = APP_META.get(slug, {"host": "droplet", "port": None, "group": "Other"})
        if meta is None:
            continue
        out.append({
            "slug": slug, "name": p.get("name", slug), "color": p.get("color", "#64748b"),
            "url": p.get("url"), "host": meta.get("host"), "port": meta.get("port"),
            "group": meta.get("group", "Other"),
        })
    return out


def chip(name, sub, color="#64748b", url=None, port=None, host=None):
    dot = f'<span class="dot" style="background:{color}"></span>'
    title = html.escape(name)
    if url:
        title = f'<a href="{html.escape(url)}" target="_blank" rel="noopener">{title}</a>'
    meta = html.escape(sub or "")
    tags = ""
    if host:
        tags += f'<span class="tag">{html.escape(host)}</span>'
    if port:
        tags += f'<span class="tag mono">:{port}</span>'
    return (f'<div class="chip">{dot}<div class="chip-b"><div class="chip-t">{title}</div>'
            f'<div class="chip-s">{meta}</div>{("<div class=tags>"+tags+"</div>") if tags else ""}</div></div>')


def layer(label, desc, chips_html, accent):
    return (f'<section class="layer"><div class="lhead"><span class="lbar" style="background:{accent}"></span>'
            f'<div><div class="ltitle">{label}</div><div class="ldesc">{desc}</div></div></div>'
            f'<div class="grid">{chips_html}</div></section>'
            f'<div class="flow">▼</div>')


def render():
    apps = load_apps()
    groups = {}
    for a in apps:
        groups.setdefault(a["group"], []).append(a)
    group_order = ["Consumer apps", "Utility apps", "Internal tools", "Backends", "Agent infra", "Other"]

    agents_html = "".join(chip(a["name"], a["sub"], a["color"], a.get("url")) for a in AGENTS)
    edge_html = "".join(chip(e["name"], e["sub"], e["color"]) for e in EDGE)

    app_blocks = ""
    for g in group_order:
        if g not in groups:
            continue
        chips = "".join(chip(a["name"], f'{a["group"]}', a["color"], a.get("url"),
                             a.get("port"), a.get("host")) for a in sorted(groups[g], key=lambda x: x["name"]))
        app_blocks += f'<div class="subgroup"><div class="sgt">{html.escape(g)}</div><div class="grid">{chips}</div></div>'

    hosts_html = "".join(chip(h["name"], h["sub"], h["color"]) for h in HOSTS)
    ext_html = "".join(chip(e["name"], e["sub"], "#475569") for e in EXTERNAL)

    n_apps = len(apps)
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Claw Systems Map</title>
<style>
:root{{--bg:#0b0e14;--card:#141925;--line:#1e2636;--ink:#e6ebf5;--mut:#8b97ad;}}
*{{box-sizing:border-box}}
body{{margin:0;background:radial-gradient(1200px 600px at 20% -10%,#161d2e,transparent),var(--bg);
color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,sans-serif;padding:28px 18px 60px}}
.wrap{{max-width:1040px;margin:0 auto}}
h1{{font-size:26px;margin:0 0 2px;letter-spacing:-.4px}}
.sub{{color:var(--mut);margin:0 0 22px;font-size:14px}}
.sub b{{color:var(--ink)}}
.layer{{background:linear-gradient(180deg,var(--card),#0f141e);border:1px solid var(--line);
border-radius:16px;padding:16px 16px 10px;}}
.lhead{{display:flex;gap:12px;align-items:flex-start;margin-bottom:12px}}
.lbar{{width:5px;align-self:stretch;min-height:34px;border-radius:4px;flex:0 0 auto}}
.ltitle{{font-weight:700;font-size:15px;letter-spacing:.3px;text-transform:uppercase}}
.ldesc{{color:var(--mut);font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px}}
.subgroup{{margin-bottom:14px}}
.sgt{{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.6px;margin:4px 0 8px}}
.chip{{display:flex;gap:10px;background:#0e131d;border:1px solid var(--line);border-radius:12px;padding:10px 12px;align-items:flex-start}}
.dot{{width:10px;height:10px;border-radius:50%;margin-top:5px;flex:0 0 auto;box-shadow:0 0 10px currentColor}}
.chip-b{{min-width:0}}
.chip-t{{font-weight:600;font-size:14px}}
.chip-t a{{color:var(--ink);text-decoration:none;border-bottom:1px dotted #46506a}}
.chip-t a:hover{{color:#7cc4ff;border-color:#7cc4ff}}
.chip-s{{color:var(--mut);font-size:12px;margin-top:1px}}
.tags{{margin-top:5px;display:flex;gap:5px;flex-wrap:wrap}}
.tag{{font-size:11px;color:#aab6cc;background:#1a2232;border:1px solid var(--line);padding:1px 7px;border-radius:999px}}
.tag.mono{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}}
.flow{{text-align:center;color:#394763;font-size:15px;margin:7px 0;letter-spacing:4px}}
.foot{{color:var(--mut);font-size:12px;margin-top:18px;text-align:center}}
.foot code{{color:#aab6cc}}
</style></head><body><div class=wrap>
<h1>🔨 Claw Systems Map</h1>
<p class=sub><b>{n_apps}</b> apps · 5 agents · 1 edge tunnel · live from Foreman's roster. Click any linked node to open it.</p>
{layer("Agents", "The OpenClaw agents — brains that read/build/ship. Foreman orchestrates jobs; Night Sweep runs autonomously nightly.", agents_html, "#0ea5e9")}
{layer("Edge", "Public HTTPS. One Cloudflare named tunnel fronts every droplet app; openhome runs its own tunnel on the Pi.", edge_html, "#f59e0b")}
<section class="layer"><div class="lhead"><span class="lbar" style="background:#ff5c8a"></span>
<div><div class="ltitle">Apps &amp; services</div><div class="ldesc">The product surface — grouped by purpose, pulled live from <code>foreman/projects.json</code>.</div></div></div>
{app_blocks}</section>
<div class="flow">▼</div>
{layer("Hosts &amp; platform", "Where it all runs, plus shared building blocks (voice, Claude gateway, iOS signing).", hosts_html, "#22c55e")}
{layer("External services", "Third-party dependencies the estate rides on.", ext_html, "#475569")}
<p class=foot>Served by <code>clawmap/server.py</code> · roster auto-updates from Foreman · <a href="https://dash.bedrock.casa/" style="color:#7cc4ff">dash</a></p>
</div></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.rstrip("/") in ("", "/health") and self.path != "/":
            body = b'{"ok":true}'
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        body = render().encode()
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()

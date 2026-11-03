#!/usr/bin/env python3
"""Marquee — what's on in NYC. A live events calendar.

Keyless data: the server asks Gemini (with Google Search grounding) for real,
current NYC events and caches them. No ticketing API key needed — grounding
returns real listings with real links. Refreshes in the background when stale.

House stack: one file, Python stdlib http.server. Serves the SPA (month calendar
+ upcoming list + category filters) and a small JSON API. A compact /api/widget
feeds the Dash "What's on in NYC" widget.

Env:
  PORT                (default 18852)
  GEMINI_API_KEY      required for live refresh
  GEMINI_MODEL        default gemini-flash-latest
  MARQUEE_REFRESH_H   cache freshness hours (default 12)
  MARQUEE_DATA        data dir (default ./data)
"""
import json, os, re, threading, time, html, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", os.environ.get("MARQUEE_PORT", "18852")))
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
REFRESH_H = float(os.environ.get("MARQUEE_REFRESH_H", "12"))
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("MARQUEE_DATA", os.path.join(HERE, "data"))
STORE = os.path.join(DATA, "events.json")

CATEGORIES = ["Music", "Nightlife", "Arts", "Theater", "Comedy", "Sports",
              "Food", "Festival", "Family", "Film"]

_lock = threading.Lock()
_refreshing = {"on": False}


# ------------------------------------------------------------------- store
def load_store():
    try:
        with open(STORE) as f:
            return json.load(f)
    except Exception:
        return {"fetched_at": 0, "events": []}


def save_store(obj):
    os.makedirs(DATA, exist_ok=True)
    tmp = STORE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, STORE)


def is_stale(store):
    return (time.time() * 1000 - (store.get("fetched_at") or 0)) > REFRESH_H * 3600 * 1000


# --------------------------------------------------------------- gemini fetch
def _norm_cat(c):
    c = (c or "").strip().title()
    alias = {"Concert": "Music", "Concerts": "Music", "Show": "Theater",
             "Shows": "Theater", "Club": "Nightlife", "Dj": "Nightlife",
             "Exhibition": "Arts", "Art": "Arts", "Museum": "Arts",
             "Dance": "Nightlife", "Dining": "Food", "Kids": "Family"}
    c = alias.get(c, c)
    return c if c in CATEGORIES else "Arts"


def fetch_events():
    """Ask Gemini (grounded in Google Search) for real upcoming NYC events."""
    if not GEMINI_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")
    prompt = (
        "List 16 real, notable upcoming events in New York City over the next ~24 days, "
        "a diverse mix across music/concerts, nightlife, arts & museums, theater, comedy, "
        "sports, food, festivals, family, and film. Use Google Search for REAL current "
        "listings with REAL working links (official venue, ticketing, or org page). "
        "Spread them across different dates. Reply with ONLY a JSON array, no prose, no "
        "markdown fences. Each item: {\"title\",\"date\":\"YYYY-MM-DD\",\"time\",\"venue\","
        "\"neighborhood\",\"category\",\"price\",\"url\",\"blurb\"}. category is one of: "
        + ", ".join(CATEGORIES) + ". blurb <= 18 words, vivid and specific."
    )
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": {"temperature": 0.35, "maxOutputTokens": 6000}}
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}")
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    j = json.loads(urllib.request.urlopen(req, timeout=150).read())
    txt = "".join(p.get("text", "") for p in
                  ((j["candidates"][0].get("content") or {}).get("parts") or []))
    a, b = txt.find("["), txt.rfind("]")
    arr = json.loads(txt[a:b + 1]) if a >= 0 and b > a else []
    out = []
    for e in arr:
        if not isinstance(e, dict):
            continue
        d = (e.get("date") or "").strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
            continue
        title = (e.get("title") or "").strip()
        if not title:
            continue
        out.append({
            "title": title[:140], "date": d, "time": (e.get("time") or "").strip()[:40],
            "venue": (e.get("venue") or "").strip()[:120],
            "neighborhood": (e.get("neighborhood") or "").strip()[:80],
            "category": _norm_cat(e.get("category")),
            "price": (e.get("price") or "").strip()[:60],
            "url": (e.get("url") or "").strip()[:400],
            "blurb": (e.get("blurb") or "").strip()[:220],
        })
    # keep today-forward, sort by date then time
    today = time.strftime("%Y-%m-%d")
    out = [e for e in out if e["date"] >= today]
    out.sort(key=lambda e: (e["date"], e["time"]))
    return out


def refresh_async():
    if _refreshing["on"]:
        return
    _refreshing["on"] = True

    def work():
        try:
            events = fetch_events()
            if events:
                save_store({"fetched_at": int(time.time() * 1000), "events": events})
                print(f"[marquee] refreshed {len(events)} events", flush=True)
        except Exception as e:
            print("[marquee] refresh failed:", e, flush=True)
        finally:
            _refreshing["on"] = False
    threading.Thread(target=work, daemon=True).start()


def get_events(force=False):
    """Serve cached events; kick a background refresh when stale. Block once if
    there is no cache at all (first run)."""
    store = load_store()
    if force or (not store.get("events")):
        if not store.get("events"):
            with _lock:
                store = load_store()
                if not store.get("events"):
                    try:
                        events = fetch_events()
                        store = {"fetched_at": int(time.time() * 1000), "events": events}
                        save_store(store)
                    except Exception as e:
                        print("[marquee] initial fetch failed:", e, flush=True)
                        store = {"fetched_at": 0, "events": []}
        else:
            refresh_async()
    elif is_stale(store):
        refresh_async()
    return store


# ------------------------------------------------------------------- page
PAGE = r"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Marquee — What's on in NYC</title>
<meta name="description" content="Marquee — a live calendar of what's on in New York City: concerts, shows, nightlife, art, sports and more.">
<link rel="icon" href="/favicon.svg">
<style>
 :root{--bg:#0b0b12;--card:#15151f;--card2:#1b1b27;--ink:#f4f3f8;--mut:#9a98ad;--line:#262636;
   --accent:#ff5c8a;--accent2:#a855f7;--chip:#211f30}
 *{box-sizing:border-box}
 html,body{margin:0;background:
   radial-gradient(1100px 520px at 82% -8%,rgba(168,85,247,.22),transparent 60%),
   radial-gradient(900px 480px at 8% 4%,rgba(255,92,138,.18),transparent 58%),var(--bg);
   color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,system-ui,sans-serif;
   -webkit-font-smoothing:antialiased}
 a{color:inherit}
 .wrap{max-width:1040px;margin:0 auto;padding:26px 18px 60px}
 header{display:flex;align-items:center;gap:13px;margin-bottom:6px}
 .mk{width:44px;height:44px;flex:0 0 auto}
 h1{font-size:25px;margin:0;letter-spacing:-.02em;font-weight:800}
 .sub{color:var(--mut);font-size:13px;margin:2px 0 0;font-weight:500}
 .top{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:18px}
 .refresh{margin-left:auto;border:1px solid var(--line);background:var(--card);color:var(--mut);
   border-radius:10px;padding:8px 13px;font:inherit;font-size:12.5px;font-weight:600;cursor:pointer;display:inline-flex;gap:7px;align-items:center}
 .refresh:hover{color:var(--ink);border-color:#3a3a50}
 .refresh.spin svg{animation:spin 1s linear infinite}
 @keyframes spin{to{transform:rotate(360deg)}}
 .chips{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 18px}
 .chip{border:1px solid var(--line);background:var(--chip);color:var(--mut);border-radius:999px;
   padding:7px 14px;font-size:12.5px;font-weight:650;cursor:pointer;transition:.15s;letter-spacing:.01em}
 .chip:hover{color:var(--ink);border-color:#3a3a50}
 .chip.on{color:#fff;border-color:transparent;background:linear-gradient(135deg,var(--accent),var(--accent2));
   box-shadow:0 4px 16px -6px rgba(255,92,138,.6)}
 .views{display:inline-flex;gap:2px;padding:3px;border-radius:11px;background:var(--card);border:1px solid var(--line)}
 .views button{border:0;background:none;color:var(--mut);font:inherit;font-weight:650;font-size:12.5px;cursor:pointer;padding:6px 14px;border-radius:8px}
 .views button.on{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff}
 /* calendar */
 .cal{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:16px;margin-bottom:22px}
 .cal-head{display:flex;align-items:center;gap:12px;margin-bottom:12px}
 .cal-head b{font-size:16px;font-weight:750}
 .cal-nav{border:1px solid var(--line);background:var(--card2);color:var(--ink);width:32px;height:32px;border-radius:9px;cursor:pointer;font-size:15px}
 .cal-nav:hover{border-color:#3a3a50}
 .grid{display:grid;grid-template-columns:repeat(7,1fr);gap:6px}
 .dow{color:var(--mut);font-size:10.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;text-align:center;padding:4px 0}
 .cell{min-height:62px;border-radius:11px;background:var(--card2);border:1px solid transparent;padding:6px 7px;cursor:default;position:relative;transition:.12s}
 .cell.pad{background:transparent}
 .cell.has{cursor:pointer}.cell.has:hover{border-color:#3a3a50}
 .cell.today{box-shadow:inset 0 0 0 1.5px var(--accent)}
 .cell.sel{border-color:var(--accent);background:#241a26}
 .cell .d{font-size:12px;font-weight:650;color:var(--mut)}
 .cell.today .d{color:var(--accent)}
 .cell .dots{display:flex;gap:3px;flex-wrap:wrap;margin-top:6px}
 .dot{width:6px;height:6px;border-radius:50%}
 .cell .more{position:absolute;right:7px;bottom:5px;font-size:10px;color:var(--mut);font-weight:700}
 /* list */
 .day-h{font-size:13px;font-weight:750;color:var(--accent);margin:22px 2px 11px;letter-spacing:.01em;
   text-transform:uppercase;display:flex;align-items:center;gap:9px}
 .day-h .ln{flex:1;height:1px;background:var(--line)}
 .ev{display:flex;gap:14px;padding:14px 15px;border:1px solid var(--line);background:var(--card);border-radius:14px;margin-bottom:10px;transition:.15s;text-decoration:none}
 .ev:hover{border-color:#3a3a50;background:var(--card2);transform:translateY(-1px)}
 .ev .dte{flex:0 0 52px;text-align:center}
 .ev .dte .mo{font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}
 .ev .dte .dy{font-size:23px;font-weight:800;line-height:1.05}
 .ev .dte .wd{font-size:10px;color:var(--mut);font-weight:600}
 .ev .body{min-width:0;flex:1}
 .ev .t{font-size:15.5px;font-weight:700;letter-spacing:-.01em;margin:0 0 3px;line-height:1.3}
 .ev .meta{color:var(--mut);font-size:12.5px;display:flex;flex-wrap:wrap;gap:4px 10px;margin-bottom:5px}
 .ev .bl{color:#c8c6d6;font-size:12.5px;line-height:1.45;margin:0}
 .ev .cat{display:inline-block;font-size:9.5px;font-weight:800;letter-spacing:.05em;text-transform:uppercase;
   padding:3px 8px;border-radius:6px;color:#fff;background:linear-gradient(135deg,var(--accent),var(--accent2))}
 .ev .go{flex:0 0 auto;align-self:center;color:var(--mut);font-size:19px}
 .ev:hover .go{color:var(--accent)}
 .empty{color:var(--mut);padding:30px 4px;text-align:center;font-size:14px}
 .foot{color:var(--mut);font-size:11.5px;text-align:center;margin-top:34px}
 @media(max-width:560px){.cell{min-height:50px}.ev .bl{display:none}}
</style></head><body>
<div class="wrap">
 <div class="top">
  <header>
   <svg class="mk" viewBox="0 0 48 48" fill="none"><rect width="48" height="48" rx="12" fill="url(#mg)"/>
    <defs><linearGradient id="mg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff5c8a"/><stop offset="1" stop-color="#a855f7"/></linearGradient></defs>
    <rect x="11" y="15" width="26" height="20" rx="3" fill="#fff"/><rect x="11" y="15" width="26" height="6" rx="3" fill="#ffd7e4"/>
    <circle cx="16" cy="12" r="2" fill="#fff"/><circle cx="24" cy="11" r="2" fill="#fff"/><circle cx="32" cy="12" r="2" fill="#fff"/>
    <g fill="#a855f7"><circle cx="17" cy="27" r="2"/><circle cx="24" cy="27" r="2"/><circle cx="31" cy="27" r="2"/><circle cx="17" cy="32" r="2"/><circle cx="24" cy="32" r="2"/></g></svg>
   <div><h1>Marquee</h1><p class="sub">What's on in NYC — live</p></div>
  </header>
  <button class="refresh" id="refresh" title="Refresh events">
   <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round"><path d="M21 12a9 9 0 1 1-2.6-6.3M21 3v6h-6"/></svg>Refresh</button>
 </div>
 <div class="chips" id="chips"></div>
 <div style="margin-bottom:16px"><span class="views" id="views"><button data-v="list" class="on">Upcoming</button><button data-v="cal">Calendar</button></span></div>
 <div id="calWrap" class="cal" hidden>
  <div class="cal-head"><button class="cal-nav" id="pm">‹</button><b id="monLbl"></b><button class="cal-nav" id="nm">›</button></div>
  <div class="grid" id="dows"></div><div class="grid" id="cells" style="margin-top:6px"></div>
 </div>
 <div id="list"></div>
 <div class="foot" id="foot"></div>
</div>
<script>
var CATCOLOR={Music:'#ff5c8a',Nightlife:'#a855f7',Arts:'#38bdf8',Theater:'#f59e0b',Comedy:'#fbbf24',
  Sports:'#22c55e',Food:'#fb7185',Festival:'#ec4899',Family:'#2dd4bf',Film:'#818cf8'};
var CATS=['Music','Nightlife','Arts','Theater','Comedy','Sports','Food','Festival','Family','Film'];
var MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
var WD=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
var all=[],active=new Set(),view='list',curMonth=null,selDay=null;
function esc(s){return (s||'').replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function parseD(s){var p=(s||'').split('-');return new Date(+p[0],+p[1]-1,+p[2]);}
function filtered(){return all.filter(function(e){return !active.size||active.has(e.category);});}
function chips(){
 var c=document.getElementById('chips');
 c.innerHTML='<span class="chip'+(!active.size?' on':'')+'" data-c="">All</span>'+
  CATS.map(function(k){return '<span class="chip'+(active.has(k)?' on':'')+'" data-c="'+k+'" style="'+(active.has(k)?'':'')+'">'+k+'</span>';}).join('');
}
function evCard(e){
 var d=parseD(e.date);
 return '<a class="ev" href="'+esc(e.url||'#')+'" target="_blank" rel="noopener">'
  +'<div class="dte"><div class="mo">'+MON[d.getMonth()]+'</div><div class="dy">'+d.getDate()+'</div><div class="wd">'+WD[d.getDay()]+'</div></div>'
  +'<div class="body"><div class="t">'+esc(e.title)+'</div>'
  +'<div class="meta"><span class="cat" style="background:linear-gradient(135deg,'+(CATCOLOR[e.category]||'#ff5c8a')+',#a855f7)">'+esc(e.category)+'</span>'
  +(e.time?'<span>🕒 '+esc(e.time)+'</span>':'')
  +(e.venue?'<span>📍 '+esc(e.venue)+(e.neighborhood?', '+esc(e.neighborhood):'')+'</span>':'')
  +(e.price?'<span>🎟 '+esc(e.price)+'</span>':'')+'</div>'
  +(e.blurb?'<p class="bl">'+esc(e.blurb)+'</p>':'')+'</div>'
  +'<span class="go">↗</span></a>';
}
function renderList(){
 var evs=filtered(),box=document.getElementById('list');
 if(!evs.length){box.innerHTML='<div class="empty">No events in that filter yet.</div>';return;}
 var byDay={},order=[];
 evs.forEach(function(e){if(!byDay[e.date]){byDay[e.date]=[];order.push(e.date);}byDay[e.date].push(e);});
 box.innerHTML=order.map(function(dt){
  var d=parseD(dt),lbl=WD[d.getDay()]+', '+MON[d.getMonth()]+' '+d.getDate();
  return '<div class="day-h">'+lbl+'<span class="ln"></span></div>'+byDay[dt].map(evCard).join('');
 }).join('');
}
function ym(d){return d.getFullYear()+'-'+d.getMonth();}
function renderCal(){
 var dows=document.getElementById('dows');dows.innerHTML=WD.map(function(w){return '<div class="dow">'+w+'</div>';}).join('');
 if(!curMonth)curMonth=new Date();
 var y=curMonth.getFullYear(),m=curMonth.getMonth();
 document.getElementById('monLbl').textContent=['January','February','March','April','May','June','July','August','September','October','November','December'][m]+' '+y;
 var first=new Date(y,m,1).getDay(),days=new Date(y,m+1,0).getDate();
 var evs=filtered(),byDay={};
 evs.forEach(function(e){var p=e.date.split('-');if(+p[0]===y&&+p[1]-1===m){(byDay[+p[2]]=byDay[+p[2]]||[]).push(e);}});
 var today=new Date(),tKey=today.getFullYear()+'-'+today.getMonth()+'-'+today.getDate();
 var cells='';for(var i=0;i<first;i++)cells+='<div class="cell pad"></div>';
 for(var day=1;day<=days;day++){
  var ds=byDay[day]||[],isT=(y+'-'+m+'-'+day)===tKey,sel=(selDay===day);
  var dots=ds.slice(0,4).map(function(e){return '<span class="dot" style="background:'+(CATCOLOR[e.category]||'#ff5c8a')+'"></span>';}).join('');
  cells+='<div class="cell'+(ds.length?' has':'')+(isT?' today':'')+(sel?' sel':'')+'" data-day="'+day+'">'
   +'<div class="d">'+day+'</div><div class="dots">'+dots+'</div>'+(ds.length>4?'<span class="more">+'+(ds.length-4)+'</span>':'')+'</div>';
 }
 document.getElementById('cells').innerHTML=cells;
 // selected day's events under the calendar (reuse list area)
 if(selDay&&byDay[selDay]){
  document.getElementById('list').innerHTML='<div class="day-h">'+MON[m]+' '+selDay+'<span class="ln"></span></div>'+byDay[selDay].map(evCard).join('');
 }else{renderList();}
}
function render(){chips();document.getElementById('calWrap').hidden=(view!=='cal');if(view==='cal')renderCal();else renderList();}
function load(force){
 var r=document.getElementById('refresh');if(force)r.classList.add('spin');
 fetch('api/events'+(force?'?force=1':''),{cache:'no-store'}).then(function(x){return x.json();}).then(function(d){
  all=d.events||[];
  document.getElementById('foot').textContent=all.length+' events · updated '+(d.fetched_at?new Date(d.fetched_at).toLocaleString():'—')+' · tap any event for tickets';
  render();r.classList.remove('spin');
 }).catch(function(){r.classList.remove('spin');});
}
document.getElementById('chips').addEventListener('click',function(ev){
 var c=ev.target.closest('.chip');if(!c)return;var k=c.getAttribute('data-c');
 if(!k)active.clear();else{if(active.has(k))active.delete(k);else active.add(k);}render();
});
document.getElementById('views').addEventListener('click',function(ev){
 var b=ev.target.closest('button');if(!b)return;view=b.getAttribute('data-v');
 Array.prototype.forEach.call(this.children,function(x){x.classList.toggle('on',x===b);});
 selDay=null;render();
});
document.getElementById('cells').addEventListener('click',function(ev){
 var c=ev.target.closest('.cell.has');if(!c)return;var day=+c.getAttribute('data-day');
 selDay=(selDay===day)?null:day;renderCal();
});
document.getElementById('pm').onclick=function(){curMonth=new Date(curMonth.getFullYear(),curMonth.getMonth()-1,1);selDay=null;renderCal();};
document.getElementById('nm').onclick=function(){curMonth=new Date(curMonth.getFullYear(),curMonth.getMonth()+1,1);selDay=null;renderCal();};
document.getElementById('refresh').onclick=function(){load(true);};
load(false);setInterval(function(){load(false);},120000);
</script></body></html>"""

FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">'
           '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff5c8a"/>'
           '<stop offset="1" stop-color="#a855f7"/></linearGradient></defs><rect width="48" height="48" rx="12" fill="url(#g)"/>'
           '<rect x="11" y="15" width="26" height="20" rx="3" fill="#fff"/>'
           '<g fill="#a855f7"><circle cx="17" cy="27" r="2"/><circle cx="24" cy="27" r="2"/><circle cx="31" cy="27" r="2"/></g></svg>')


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, ctype="application/json; charset=utf-8", code=200):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = self.path.split("?", 1)[0]
        q = self.path.split("?", 1)[1] if "?" in self.path else ""
        if p in ("/", "/index.html"):
            self._send(PAGE, "text/html; charset=utf-8")
        elif p == "/favicon.svg":
            self._send(FAVICON, "image/svg+xml")
        elif p == "/api/events":
            store = get_events(force=("force=1" in q))
            self._send(json.dumps(store))
        elif p == "/api/widget":
            store = load_store()
            if is_stale(store) or not store.get("events"):
                get_events(force=False)
                store = load_store()
            evs = (store.get("events") or [])[:6]
            self._send(json.dumps({"events": evs, "fetched_at": store.get("fetched_at", 0)}))
        elif p in ("/health", "/healthz"):
            s = load_store()
            self._send(json.dumps({"ok": True, "events": len(s.get("events") or []),
                                   "fetched_at": s.get("fetched_at", 0)}))
        else:
            self._send("not found", "text/plain", 404)

    def do_POST(self):
        p = self.path.split("?", 1)[0]
        if p == "/api/refresh":
            refresh_async()
            self._send(json.dumps({"ok": True, "refreshing": True}))
        else:
            self._send("not found", "text/plain", 404)


def main():
    os.makedirs(DATA, exist_ok=True)
    print(f"Marquee on 127.0.0.1:{PORT} (data={DATA}, llm={'on' if GEMINI_KEY else 'off'})", flush=True)
    # warm the cache in the background on boot
    threading.Thread(target=lambda: get_events(force=False), daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()


if __name__ == "__main__":
    main()

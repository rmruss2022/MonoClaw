#!/usr/bin/env python3
"""
Rolodex — Matthew's personal network CRM.

A standalone app: SQLite + stdlib http.server (zero third-party deps, reboot-safe).
Tracks people you meet — details, category (tech/real estate/…), how & when you met,
follow-ups, and last-contacted — with search, network visualizations, and
"who should I reach out to" queries.

Env:
  ROLODEX_PORT   (default 18821)
  ROLODEX_BASE   base path when mounted under the command hub, e.g. "/rolodex"
  ROLODEX_DB     sqlite path (default ./data/rolodex.db)
"""
import json, os, re, sqlite3, urllib.parse, hashlib, hmac, secrets, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone, date

PORT = int(os.environ.get("ROLODEX_PORT", "18821"))
BASE = (os.environ.get("ROLODEX_BASE", "").rstrip("/") + "/") or "/"
DB   = os.environ.get("ROLODEX_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "rolodex.db"))

# ---------- auth (only enforced when ROLODEX_AUTH=1, i.e. the public instance) ----------
AUTH = os.environ.get("ROLODEX_AUTH") == "1"
USERS_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "users.json")
SESSION_TTL = 60 * 60 * 24 * 30
SESSIONS = {}  # token -> (email, expires_epoch)

def _users():
    try:
        return json.load(open(USERS_DB))
    except Exception:
        return {}

def _hash_pw(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200000).hex()

def verify_login(email, pw):
    u = _users().get((email or "").strip().lower())
    if not u:
        return False
    return hmac.compare_digest(_hash_pw(pw or "", u["salt"]), u["hash"])

def new_session(email):
    tok = secrets.token_urlsafe(32)
    SESSIONS[tok] = (email, time.time() + SESSION_TTL)
    return tok

def session_ok(tok):
    v = SESSIONS.get(tok)
    if not v:
        return False
    if v[1] < time.time():
        SESSIONS.pop(tok, None)
        return False
    return True

FIELDS = ["name","company","title","category","phone","email","location","instagram",
          "how_met","met_date","last_contacted","follow_up_date","follow_up_note",
          "priority","tags","notes"]

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS contacts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, company TEXT, title TEXT, category TEXT,
            phone TEXT, email TEXT, location TEXT,
            how_met TEXT, met_date TEXT, last_contacted TEXT,
            follow_up_date TEXT, follow_up_note TEXT,
            priority INTEGER DEFAULT 0, tags TEXT, notes TEXT,
            created_at TEXT, updated_at TEXT)""")
        # migrations: the curated "to reach out" running list
        existing = {r[1] for r in c.execute("PRAGMA table_info(contacts)")}
        for col, ddl in [("reach_out", "reach_out INTEGER DEFAULT 0"),
                         ("reach_out_reason", "reach_out_reason TEXT"),
                         ("reach_out_added", "reach_out_added TEXT"),
                         ("instagram", "instagram TEXT")]:
            if col not in existing:
                c.execute(f"ALTER TABLE contacts ADD COLUMN {ddl}")

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def today():
    return date.today().isoformat()

def days_since(iso):
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(iso.replace("Z","")).date() if "T" in iso or "-" in iso else None
        if d is None:
            return None
        return (date.today() - d).days
    except Exception:
        return None

# ---------- data ops ----------
def row_to_dict(r):
    d = dict(r)
    d["days_since_contact"] = days_since(d.get("last_contacted") or d.get("met_date"))
    return d

def list_contacts(q="", category="", flt=""):
    sql = "SELECT * FROM contacts"
    where, args = [], []
    if q:
        like = f"%{q.lower()}%"
        where.append("(lower(name) LIKE ? OR lower(company) LIKE ? OR lower(title) LIKE ? "
                     "OR lower(category) LIKE ? OR lower(tags) LIKE ? OR lower(notes) LIKE ? "
                     "OR lower(location) LIKE ? OR lower(how_met) LIKE ?)")
        args += [like]*8
    if category:
        where.append("lower(category)=?"); args.append(category.lower())
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY (last_contacted IS NULL), datetime(coalesce(last_contacted, met_date, created_at)) DESC"
    with db() as c:
        rows = [row_to_dict(r) for r in c.execute(sql, args).fetchall()]
    # python-side filters for the "reach out" queries
    if flt == "followups":
        t = today()
        rows = [r for r in rows if r.get("follow_up_date") and r["follow_up_date"] <= t]
    elif flt.startswith("stale"):
        n = int(flt.split(":")[1]) if ":" in flt else 30
        rows = [r for r in rows if (r["days_since_contact"] is not None and r["days_since_contact"] >= n)]
    elif flt == "priority":
        rows = [r for r in rows if (r.get("priority") or 0) >= 2]
    elif flt == "reachout":
        rows = [r for r in rows if r.get("reach_out")]
        rows.sort(key=lambda r: (r.get("reach_out_added") or ""))  # oldest on the list first
    elif flt == "recent":
        rows.sort(key=lambda r: (r.get("created_at") or ""), reverse=True)
        rows = rows[:10]
    return rows

def get_contact(cid):
    with db() as c:
        r = c.execute("SELECT * FROM contacts WHERE id=?", (cid,)).fetchone()
    return row_to_dict(r) if r else None

def upsert(data, cid=None):
    vals = {k: (data.get(k) or None) for k in FIELDS}
    if not vals["name"]:
        raise ValueError("name required")
    if vals.get("priority") in (None, ""):
        vals["priority"] = 0
    with db() as c:
        if cid:
            vals["updated_at"] = now_iso()
            sets = ", ".join(f"{k}=?" for k in FIELDS + ["updated_at"])
            c.execute(f"UPDATE contacts SET {sets} WHERE id=?",
                      [vals[k] for k in FIELDS] + [vals["updated_at"], cid])
            return cid
        vals["created_at"] = vals["updated_at"] = now_iso()
        if not vals.get("met_date"):
            vals["met_date"] = today()
        cols = FIELDS + ["created_at","updated_at"]
        cur = c.execute(f"INSERT INTO contacts({','.join(cols)}) VALUES ({','.join('?'*len(cols))})",
                        [vals[k] for k in cols])
        return cur.lastrowid

def log_touch(cid):
    with db() as c:
        c.execute("UPDATE contacts SET last_contacted=?, updated_at=? WHERE id=?",
                  (today(), now_iso(), cid))

def set_reachout(cid, on, reason=None):
    with db() as c:
        row = c.execute("SELECT reach_out_added FROM contacts WHERE id=?", (cid,)).fetchone()
        added = ((row["reach_out_added"] if (row and row["reach_out_added"]) else now_iso()) if on else None)
        c.execute("UPDATE contacts SET reach_out=?, reach_out_reason=?, reach_out_added=?, updated_at=? WHERE id=?",
                  (1 if on else 0, (reason if on else None), added, now_iso(), cid))

def delete_contact(cid):
    with db() as c:
        c.execute("DELETE FROM contacts WHERE id=?", (cid,))

def stats():
    with db() as c:
        rows = [row_to_dict(r) for r in c.execute("SELECT * FROM contacts").fetchall()]
    total = len(rows)
    cats = {}
    months = {}
    for r in rows:
        cat = (r.get("category") or "Uncategorized").strip() or "Uncategorized"
        cats[cat] = cats.get(cat, 0) + 1
        md = r.get("met_date") or (r.get("created_at") or "")[:10]
        if md and len(md) >= 7:
            months[md[:7]] = months.get(md[:7], 0) + 1
    cat_list = sorted([{"name": k, "count": v} for k, v in cats.items()], key=lambda x: -x["count"])
    month_list = [{"month": k, "count": months[k]} for k in sorted(months)][-12:]
    t = today()
    followups_due = sum(1 for r in rows if r.get("follow_up_date") and r["follow_up_date"] <= t)
    stale30 = sum(1 for r in rows if r["days_since_contact"] is not None and r["days_since_contact"] >= 30)
    to_reach_out = sum(1 for r in rows if r.get("reach_out"))
    return {"total": total, "categories": cat_list, "byMonth": month_list,
            "followupsDue": followups_due, "stale30": stale30, "toReachOut": to_reach_out}

# ---------- minimal vCard import ----------
def parse_vcards(text):
    out, cur = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if line == "BEGIN:VCARD":
            cur = {}
        elif line == "END:VCARD":
            if cur and cur.get("name"):
                out.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            key, val = line.split(":", 1)
            k = key.split(";")[0].upper()
            val = val.replace("\\,", ",").replace("\\n", " ").strip()
            if k == "FN": cur["name"] = val
            elif k == "ORG": cur["company"] = val.split(";")[0]
            elif k == "TITLE": cur["title"] = val
            elif k == "TEL" and not cur.get("phone"): cur["phone"] = val
            elif k == "EMAIL" and not cur.get("email"): cur["email"] = val
            elif k == "NOTE": cur["notes"] = val
            elif k == "CATEGORIES" and not cur.get("category"): cur["category"] = val.split(",")[0]
    return out

def import_vcards(text):
    added = 0
    for v in parse_vcards(text):
        with db() as c:
            dup = c.execute("SELECT id FROM contacts WHERE lower(name)=? AND ifnull(lower(email),'')=ifnull(?,'')",
                            (v["name"].lower(), (v.get("email") or "").lower())).fetchone()
        if dup:
            continue
        upsert(v)
        added += 1
    return added

def _add_ig_handles(pairs):
    added = 0; seen = set()
    for handle, href in pairs:
        h = (handle or "").lstrip("@").strip()
        if not h or h.lower() in seen:
            continue
        seen.add(h.lower())
        with db() as c:
            dup = c.execute("SELECT id FROM contacts WHERE lower(ifnull(instagram,''))=?",
                            (h.lower(),)).fetchone()
        if dup:
            continue
        upsert({"name": "@" + h, "instagram": h, "category": "Instagram",
                "how_met": "Instagram", "notes": href or ("https://instagram.com/" + h)})
        added += 1
    return added

def import_instagram(text):
    """Import from Instagram's official 'Download Your Information' export
    (followers/following JSON), or a plain list of @handles (one per line)."""
    text = (text or "").strip()
    if not text:
        return 0
    try:
        data = json.loads(text)
    except Exception:
        handles = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return _add_ig_handles([(h, "") for h in handles])
    found = []
    def walk(o):
        if isinstance(o, dict):
            sld = o.get("string_list_data")
            if isinstance(sld, list):
                for s in sld:
                    if isinstance(s, dict):
                        u = (s.get("value") or "").strip()
                        if u:
                            found.append((u, s.get("href") or ""))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(data)
    return _add_ig_handles(found)

LOGIN_PAGE = r"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<base href="__BASE__"><title>Rolodex · sign in</title>
<style>
:root{--bg:#0e1014;--panel:#171a21;--line:#272c37;--text:#e7ebf3;--muted:#8b93a7;--accent:#6366f1}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;display:flex;align-items:center;justify-content:center;padding:24px}
.card{width:100%;max-width:340px;background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:26px}
h1{margin:0 0 4px;font-size:22px;font-weight:800;letter-spacing:-.02em}h1 span{color:var(--accent)}
.sub{color:var(--muted);font-size:13px;margin-bottom:18px}
label{display:block;font-size:12px;color:var(--muted);margin:12px 0 5px;font-weight:700;text-transform:uppercase;letter-spacing:.04em}
input{width:100%;background:#0e1118;border:1px solid var(--line);border-radius:11px;color:var(--text);padding:12px;font-size:16px}
button{width:100%;margin-top:18px;background:var(--accent);color:#fff;border:0;border-radius:11px;padding:13px;font-size:15px;font-weight:700}
.err{color:#f0768a;font-size:13px;margin-top:12px;min-height:16px;text-align:center}
</style></head><body>
<form class="card" onsubmit="return go(event)">
  <h1>Rolo<span>dex</span></h1>
  <div class="sub">Sign in to your network.</div>
  <label>Email</label><input id="email" type="email" autocomplete="username" autofocus>
  <label>Password</label><input id="pw" type="password" autocomplete="current-password">
  <button type="submit">Sign in</button>
  <div class="err" id="err"></div>
</form>
<script>
async function go(e){e.preventDefault();document.getElementById('err').textContent='';
 const r=await fetch('api/login',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({email:document.getElementById('email').value,password:document.getElementById('pw').value})});
 if(r.ok){location.reload();}else{document.getElementById('err').textContent='Wrong email or password.';}
 return false;}
</script></body></html>"""

# ---------- HTTP ----------
class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ct="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(n) if n else b""

    def _cookie(self, name):
        for part in (self.headers.get("Cookie", "") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == name:
                return v
        return None

    def _authed(self):
        if not AUTH:
            return True
        tok = self._cookie("rolo_sess")
        return bool(tok and session_ok(tok))

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(u.query)
        p = u.path
        if AUTH and not self._authed():
            if p in ("/", "/index.html"):
                self._send(200, LOGIN_PAGE.replace("__BASE__", BASE), "text/html; charset=utf-8"); return
            self._send(401, {"error": "auth"}); return
        if p in ("/", "/index.html"):
            self._send(200, PAGE.replace("__BASE__", BASE), "text/html; charset=utf-8"); return
        if p == "/api/contacts":
            self._send(200, {"contacts": list_contacts(
                qs.get("q", [""])[0], qs.get("category", [""])[0], qs.get("filter", [""])[0])}); return
        if p == "/api/stats":
            self._send(200, stats()); return
        if re.match(r"^/api/contacts/\d+$", p):
            cid = int(p.rsplit("/", 1)[1]); r = get_contact(cid)
            self._send(200 if r else 404, r or {"error": "not found"}); return
        self._send(404, {"error": "not found"})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path); p = u.path
        if p == "/api/login":
            try: d = json.loads(self._body() or b"{}")
            except Exception: d = {}
            if verify_login(d.get("email", ""), d.get("password", "")):
                tok = new_session((d.get("email", "") or "").strip().lower())
                body = json.dumps({"ok": True}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Set-Cookie", f"rolo_sess={tok}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age={SESSION_TTL}")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers(); self.wfile.write(body); return
            self._send(401, {"error": "invalid credentials"}); return
        if p == "/api/logout":
            tok = self._cookie("rolo_sess")
            if tok: SESSIONS.pop(tok, None)
            self._send(200, {"ok": True}); return
        if AUTH and not self._authed():
            self._send(401, {"error": "auth"}); return
        try:
            if p == "/api/contacts":
                cid = upsert(json.loads(self._body() or b"{}"))
                self._send(200, {"ok": True, "id": cid}); return
            m = re.match(r"^/api/contacts/(\d+)(/(touch|delete|reachout))?$", p)
            if m:
                cid = int(m.group(1)); action = m.group(3)
                if action == "touch": log_touch(cid); self._send(200, {"ok": True}); return
                if action == "delete": delete_contact(cid); self._send(200, {"ok": True}); return
                if action == "reachout":
                    d = json.loads(self._body() or b"{}")
                    set_reachout(cid, d.get("on", True), d.get("reason"))
                    self._send(200, {"ok": True}); return
                upsert(json.loads(self._body() or b"{}"), cid); self._send(200, {"ok": True, "id": cid}); return
            if p == "/api/import":
                added = import_vcards(self._body().decode("utf-8", "ignore"))
                self._send(200, {"ok": True, "added": added}); return
            if p == "/api/import/instagram":
                added = import_instagram(self._body().decode("utf-8", "ignore"))
                self._send(200, {"ok": True, "added": added}); return
        except Exception as e:
            self._send(400, {"error": str(e)}); return
        self._send(404, {"error": "not found"})

    def log_message(self, *a):
        pass

PAGE = r"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<base href="__BASE__">
<title>Rolodex · your network</title>
<style>
:root{--bg:#0e1014;--panel:#171a21;--panel2:#1e222b;--line:#272c37;--text:#e7ebf3;--muted:#8b93a7;--accent:#3ddc97;--accent2:#7db4ff;--warn:#f0b429;--r:14px}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}
header{padding:calc(env(safe-area-inset-top,0) + 16px) 18px 12px;border-bottom:1px solid var(--line);background:linear-gradient(180deg,#141821,var(--bg));position:sticky;top:0;z-index:5}
h1{margin:0;font-size:19px;font-weight:800;letter-spacing:-.02em}h1 span{color:var(--accent)}
.sub{color:var(--muted);font-size:12.5px;margin-top:2px}
main{max-width:900px;margin:0 auto;padding:16px 14px calc(90px + env(safe-area-inset-bottom,0))}
.tabs{display:flex;gap:6px;margin-bottom:14px;overflow-x:auto}
.tab{flex:1;min-width:84px;text-align:center;padding:9px 6px;border:1px solid var(--line);border-radius:11px;background:var(--panel);color:var(--muted);font-weight:700;cursor:pointer;font-size:12.5px;white-space:nowrap}
.tab.on{color:var(--accent);border-color:var(--accent);background:rgba(61,220,151,.08)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:13px 15px;margin-bottom:10px}
.row{display:flex;gap:10px;align-items:center}.between{justify-content:space-between}.muted{color:var(--muted)}.small{font-size:12px}.wrap{flex-wrap:wrap}
input,select,textarea{font:inherit;background:var(--panel2);border:1px solid var(--line);border-radius:10px;color:var(--text);padding:9px 11px;width:100%}
textarea{min-height:64px;resize:vertical}
button{font:inherit;cursor:pointer;color:var(--text);background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:8px 12px}
button.primary{background:var(--accent);color:#08130d;border-color:var(--accent);font-weight:700}
button.sm{padding:5px 9px;font-size:12px;border-radius:8px}
.chip{display:inline-block;font-size:11px;padding:2px 9px;border-radius:999px;border:1px solid var(--line);background:var(--panel2);color:var(--muted);cursor:pointer;white-space:nowrap}
.chip.on{color:var(--accent);border-color:var(--accent);background:rgba(61,220,151,.08)}
.cat{display:inline-block;font-size:10.5px;padding:1px 8px;border-radius:999px;font-weight:700}
.name{font-weight:700;font-size:15px}
.avatar{width:38px;height:38px;border-radius:50%;flex:0 0 auto;display:flex;align-items:center;justify-content:center;font-weight:800;color:#08130d}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.tiles{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:14px}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:13px 15px}
.tile .n{font-size:26px;font-weight:800}.tile .l{color:var(--muted);font-size:12px}
.bar{height:22px;border-radius:6px;background:linear-gradient(90deg,var(--accent),#2aa}
.barrow{display:flex;align-items:center;gap:8px;margin:6px 0}
.barrow .lbl{width:110px;font-size:12.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.barrow .track{flex:1;background:var(--panel2);border-radius:6px;overflow:hidden}
.barrow .val{width:28px;text-align:right;font-size:12px;color:var(--muted)}
.spark{display:flex;align-items:flex-end;gap:3px;height:70px}
.spark .b{flex:1;background:var(--accent2);border-radius:3px 3px 0 0;min-height:2px}
.empty{color:var(--muted);text-align:center;padding:44px 14px}
.hidden{display:none}
label.f{display:block;font-size:12px;color:var(--muted);margin:8px 0 3px}
.linkish{color:var(--accent);text-decoration:none}
.modal{position:fixed;inset:0;background:rgba(0,0,0,.6);display:none;align-items:flex-end;justify-content:center;z-index:20}
.modal.on{display:flex}
.sheet{background:var(--panel);border:1px solid var(--line);border-radius:16px 16px 0 0;padding:16px;max-width:640px;width:100%;max-height:90vh;overflow:auto}
</style></head><body>
<header>
  <h1>Rolo<span>dex</span></h1>
  <div class="sub">Your network — searchable, categorized, follow-up aware</div>
</header>
<main>
  <div class="tabs">
    <div class="tab on" data-t="home" onclick="tab('home')">🏠 Overview</div>
    <div class="tab" data-t="net" onclick="tab('net')">👥 Network</div>
    <div class="tab" data-t="reach" onclick="tab('reach')">📞 Reach out</div>
    <div class="tab" data-t="viz" onclick="tab('viz')">📊 Insights</div>
    <div class="tab" data-t="add" onclick="tab('add')">＋ Add</div>
  </div>

  <div id="home"></div>

  <div id="net" class="hidden">
    <div class="row" style="margin-bottom:10px"><input id="q" placeholder="Search name, company, category, notes…" oninput="load()"></div>
    <div id="cats" class="row wrap" style="gap:6px;margin-bottom:12px"></div>
    <div id="list"></div>
  </div>

  <div id="reach" class="hidden"></div>

  <div id="viz" class="hidden"></div>

  <div id="add" class="hidden">
    <div class="card">
      <div id="formTitle" style="font-weight:800;margin-bottom:6px">Add a contact</div>
      <input type="hidden" id="f_id">
      <label class="f">Name *</label><input id="f_name">
      <div class="grid2"><div><label class="f">Company</label><input id="f_company"></div>
        <div><label class="f">Title</label><input id="f_title"></div></div>
      <div class="grid2"><div><label class="f">Category</label><input id="f_category" list="catlist" placeholder="tech, real estate…"></div>
        <div><label class="f">Priority</label><select id="f_priority"><option value="0">Normal</option><option value="1">Warm</option><option value="2">Key ⭐</option></select></div></div>
      <datalist id="catlist"></datalist>
      <div class="grid2"><div><label class="f">Phone</label><input id="f_phone"></div>
        <div><label class="f">Email</label><input id="f_email"></div></div>
      <div class="grid2"><div><label class="f">Location</label><input id="f_location"></div>
        <div><label class="f">Met on</label><input id="f_met_date" type="date"></div></div>
      <label class="f">How you met</label><input id="f_how_met" placeholder="conference, intro from…">
      <label class="f">Tags (comma-separated)</label><input id="f_tags">
      <div class="grid2"><div><label class="f">Follow-up date</label><input id="f_follow_up_date" type="date"></div>
        <div><label class="f">Follow-up note</label><input id="f_follow_up_note"></div></div>
      <label class="f">Instagram</label><input id="f_instagram" placeholder="@handle">
      <label class="f">Notes</label><textarea id="f_notes"></textarea>
      <div class="row" style="margin-top:12px;gap:8px"><button class="primary" onclick="save()">Save contact</button>
        <button onclick="resetForm();tab('net')">Cancel</button><span id="saveMsg" class="small muted"></span></div>
    </div>
    <div class="card">
      <div style="font-weight:800;margin-bottom:4px">Import from Contacts</div>
      <div class="small muted" style="margin-bottom:8px">Export contacts as a .vcf (vCard) on your phone/Mac and paste the contents here — names, company, title, phone, email, notes come in automatically.</div>
      <textarea id="vcf" placeholder="BEGIN:VCARD …"></textarea>
      <div class="row" style="margin-top:8px"><button class="primary" onclick="importVcf()">Import vCards</button><span id="impMsg" class="small muted"></span></div>

      <div style="font-weight:800;margin:18px 0 4px">Import from Instagram</div>
      <div class="small muted" style="margin-bottom:8px">In the Instagram app: <b>Settings → Account Center → Your information & permissions → Download your information</b> → pick <b>Followers and following</b>, Format <b>JSON</b>. When it arrives, paste the followers/following JSON here — or just paste <b>@handles, one per line</b>. Re-run anytime to pull in new follows.</div>
      <textarea id="ig" placeholder='Paste Instagram followers/following JSON — or @handle per line'></textarea>
      <div class="row" style="margin-top:8px"><button class="primary" onclick="importIg()">Import Instagram</button><span id="igMsg" class="small muted"></span></div>
    </div>
  </div>
</main>

<div class="modal" id="modal" onclick="if(event.target===this)closeSheet()"><div class="sheet" id="sheet"></div></div>

<script>
const $=id=>document.getElementById(id);
const CATCOLORS={};const PALETTE=['#3ddc97','#7db4ff','#f0b429','#ef7ea8','#a78bfa','#4dd0e1','#ffab6b','#9ccc65'];
function catColor(c){c=c||'Uncategorized';if(!CATCOLORS[c])CATCOLORS[c]=PALETTE[Object.keys(CATCOLORS).length%PALETTE.length];return CATCOLORS[c];}
const esc=s=>String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
let CURCAT='';

function tab(t){for(const el of document.querySelectorAll('.tab'))el.classList.toggle('on',el.dataset.t===t);
  for(const id of['home','net','reach','viz','add'])$(id).classList.toggle('hidden',id!==t);
  if(t==='home')loadOverview();if(t==='reach')loadReach();if(t==='viz')loadViz();if(t==='net')load();}

async function loadOverview(){
  const rec=await api('api/contacts?filter=recent');
  const ro=await api('api/contacts?filter=reachout');
  $('home').innerHTML=
    `<div class="row between" style="margin:2px 2px 8px"><b>🆕 Recently added <span class="muted small">· ${rec.contacts.length}</span></b></div>`+
    (rec.contacts.length?rec.contacts.map(contactCard).join(''):'<div class="empty">No contacts yet — add your first from the ＋ Add tab, or paste a vCard export.</div>')+
    `<div class="row between" style="margin:18px 2px 8px"><b>📌 Reach out to… <span class="muted small">· ${ro.contacts.length}</span></b></div>`+
    (ro.contacts.length?ro.contacts.map(contactCard).join(''):'<div class="card small muted">Your reach-out list is empty. Tap 📌 on anyone, or tell me to add someone.</div>');
}

async function api(path,opts){const r=await fetch(path,opts);return r.json();}

function initials(n){return (n||'?').split(/\s+/).slice(0,2).map(w=>w[0]||'').join('').toUpperCase();}
function contactCard(c){
  const col=catColor(c.category);
  const days=c.days_since_contact;
  const dtxt=days==null?'':(days===0?'today':days+'d ago');
  const star=(c.priority>=2)?' ⭐':'';
  const sub=[c.title,c.company].filter(Boolean).join(' @ ');
  const fu=(c.follow_up_date)?`<span class="chip" style="border-color:var(--warn);color:var(--warn)">↻ ${esc(c.follow_up_date)}${c.follow_up_note?' · '+esc(c.follow_up_note):''}</span>`:'';
  const ro=(c.reach_out)?`<span class="chip" style="border-color:var(--accent);color:var(--accent)">📌 to reach out${c.reach_out_reason?' · '+esc(c.reach_out_reason):''}</span>`:'';
  return `<div class="card"><div class="row between"><div class="row" style="gap:11px;min-width:0">
      <div class="avatar" style="background:${col}">${esc(initials(c.name))}</div>
      <div style="min-width:0"><div class="name">${esc(c.name)}${star}</div>
        <div class="small muted" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(sub)||'&nbsp;'}</div></div></div>
      ${c.category?`<span class="cat" style="background:${col}22;color:${col}">${esc(c.category)}</span>`:''}</div>
    <div class="row wrap small muted" style="gap:8px;margin-top:8px">
      ${c.location?`<span>📍 ${esc(c.location)}</span>`:''}
      ${c.met_date?`<span>🤝 ${esc(c.met_date)}</span>`:''}
      ${dtxt?`<span>💬 ${dtxt}</span>`:''}
      ${(c.tags||'').split(',').filter(x=>x.trim()).map(t=>`<span class="chip">${esc(t.trim())}</span>`).join('')}</div>
    ${c.notes?`<div class="small" style="margin-top:8px;color:#cdd5e4">${esc(c.notes)}</div>`:''}
    ${(fu||ro)?`<div class="row wrap" style="gap:6px;margin-top:8px">${fu}${ro}</div>`:''}
    <div class="row wrap" style="gap:6px;margin-top:10px">
      ${c.reach_out?`<button class="sm primary" onclick="reachedOut(${c.id})">✅ Reached out</button>`
                   :`<button class="sm primary" onclick="touch(${c.id})">Log touch</button>`}
      <button class="sm" onclick="toggleReach(${c.id},${c.reach_out?0:1})">${c.reach_out?'📌 Remove from list':'📌 Add to reach-out'}</button>
      <button class="sm" onclick="edit(${c.id})">Edit</button>
      ${c.phone?`<a class="chip" href="tel:${esc(c.phone)}">📱 Call</a>`:''}
      ${c.email?`<a class="chip" href="mailto:${esc(c.email)}">✉️ Email</a>`:''}
      <button class="sm" style="margin-left:auto;color:#ef5350" onclick="del(${c.id})">Delete</button></div></div>`;
}

async function load(){
  const q=$('q').value;
  const d=await api('api/contacts?q='+encodeURIComponent(q)+'&category='+encodeURIComponent(CURCAT));
  const s=await api('api/stats');
  const cats=$('cats');
  cats.innerHTML=`<span class="chip ${CURCAT===''?'on':''}" onclick="setCat('')">All ${s.total}</span>`+
    s.categories.map(c=>`<span class="chip ${CURCAT.toLowerCase()===c.name.toLowerCase()?'on':''}" onclick="setCat('${esc(c.name)}')">${esc(c.name)} ${c.count}</span>`).join('');
  $('catlist').innerHTML=s.categories.map(c=>`<option value="${esc(c.name)}">`).join('');
  $('list').innerHTML=d.contacts.length?d.contacts.map(contactCard).join(''):
    '<div class="empty">No contacts yet. Add one, or import your vCards from the Add tab.</div>';
}
function setCat(c){CURCAT=c;load();}

async function loadReach(){
  const box=$('reach');
  const groups=[
    {t:'📌 My reach-out list',f:'reachout',d:"People you've flagged to reach out to — tap ✅ Reached out when you do"},
    {t:'↻ Follow-ups due',f:'followups',d:'You set a reminder that has arrived'},
    {t:'😴 Gone quiet · 30d+',f:'stale:30',d:"Haven't connected in a month"},
    {t:'🧊 Cold · 90d+',f:'stale:90',d:'Long overdue for a check-in'},
    {t:'⭐ Key people',f:'priority',d:'Your most important contacts'},
  ];
  let html='';
  for(const g of groups){
    const d=await api('api/contacts?filter='+g.f);
    html+=`<div class="card" style="background:transparent;border:0;padding:0;margin-bottom:6px">
      <div class="row between" style="margin:6px 2px"><b>${g.t} <span class="muted small">· ${d.contacts.length}</span></b></div>
      <div class="small muted" style="margin:0 2px 8px">${g.d}</div></div>`;
    html+= d.contacts.length?d.contacts.map(contactCard).join(''):'<div class="card small muted">Nobody here — nice, you\'re on top of it.</div>';
  }
  box.innerHTML=html;
}

async function loadViz(){
  const s=await api('api/stats');
  const maxC=Math.max(1,...s.categories.map(c=>c.count));
  const maxM=Math.max(1,...s.byMonth.map(m=>m.count));
  $('viz').innerHTML=`
   <div class="tiles">
     <div class="tile"><div class="n">${s.total}</div><div class="l">People in network</div></div>
     <div class="tile"><div class="n">${s.categories.length}</div><div class="l">Categories</div></div>
     <div class="tile"><div class="n" style="color:var(--accent)">${s.toReachOut||0}</div><div class="l">📌 On reach-out list</div></div>
     <div class="tile"><div class="n" style="color:var(--warn)">${s.followupsDue}</div><div class="l">Follow-ups due</div></div>
     <div class="tile"><div class="n" style="color:var(--accent2)">${s.stale30}</div><div class="l">Quiet 30d+</div></div>
   </div>
   <div class="card"><b>Network by category</b><div style="margin-top:10px">
     ${s.categories.map(c=>`<div class="barrow"><span class="lbl" style="color:${catColor(c.name)}">${esc(c.name)}</span>
       <span class="track"><span class="bar" style="width:${Math.round(100*c.count/maxC)}%;background:${catColor(c.name)}"></span></span>
       <span class="val">${c.count}</span></div>`).join('')||'<span class="muted small">No data yet.</span>'}</div></div>
   <div class="card"><b>People met over time</b>
     <div class="spark" style="margin-top:12px">${s.byMonth.map(m=>`<div class="b" title="${m.month}: ${m.count}" style="height:${Math.round(100*m.count/maxM)}%"></div>`).join('')||''}</div>
     <div class="row between small muted" style="margin-top:6px"><span>${s.byMonth[0]?s.byMonth[0].month:''}</span><span>${s.byMonth.length?s.byMonth[s.byMonth.length-1].month:''}</span></div>
     ${s.byMonth.length?'':'<div class="muted small">No data yet.</div>'}</div>`;
}

// ---- form ----
function resetForm(){for(const f of ['id','name','company','title','category','phone','email','location','how_met','met_date','last_contacted','follow_up_date','follow_up_note','tags','notes'])if($('f_'+f))$('f_'+f).value='';$('f_priority').value='0';$('formTitle').textContent='Add a contact';$('saveMsg').textContent='';}
async function edit(id){const c=await api('api/contacts/'+id);for(const k in c){if($('f_'+k)!=null)$('f_'+k).value=c[k]==null?'':c[k];}$('f_id').value=c.id;$('formTitle').textContent='Edit '+c.name;tab('add');window.scrollTo(0,0);}
async function save(){
  const body={};for(const f of ['name','company','title','category','phone','email','location','how_met','met_date','follow_up_date','follow_up_note','tags','notes'])body[f]=$('f_'+f).value;
  body.priority=$('f_priority').value;
  if(!body.name){$('saveMsg').textContent='Name is required';return;}
  const id=$('f_id').value;
  await api(id?('api/contacts/'+id):'api/contacts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  resetForm();tab('net');
}
async function touch(id){await api('api/contacts/'+id+'/touch',{method:'POST'});load();}
async function del(id){if(!confirm('Delete this contact?'))return;await api('api/contacts/'+id+'/delete',{method:'POST'});refreshActive();}
function refreshActive(){if(!$('home').classList.contains('hidden'))loadOverview();else if(!$('reach').classList.contains('hidden'))loadReach();else load();}
async function toggleReach(id,on){let reason=null;if(on){reason=prompt('Add to reach-out list — why? (optional)')||'';}
  await api('api/contacts/'+id+'/reachout',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({on:!!on,reason:reason})});
  refreshActive();}
async function reachedOut(id){await api('api/contacts/'+id+'/touch',{method:'POST'});
  await api('api/contacts/'+id+'/reachout',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({on:false})});
  refreshActive();}
async function importVcf(){const t=$('vcf').value;if(!t.trim())return;$('impMsg').textContent='Importing…';
  const r=await api('api/import',{method:'POST',body:t});$('impMsg').textContent='Added '+(r.added||0)+' contacts';$('vcf').value='';load();}
async function importIg(){const t=$('ig').value;if(!t.trim())return;$('igMsg').textContent='Importing…';
  const r=await api('api/import/instagram',{method:'POST',body:t});$('igMsg').textContent='Added '+(r.added||0)+' from Instagram';$('ig').value='';load();}
function closeSheet(){$('modal').classList.remove('on');}

loadOverview();
</script></body></html>"""

if __name__ == "__main__":
    init_db()
    print(f"Rolodex on :{PORT} base={BASE} db={DB}")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()

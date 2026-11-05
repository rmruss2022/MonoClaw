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

PORT = int(os.environ.get("PORT", os.environ.get("ROLODEX_PORT", "18821")))
HOST = os.environ.get("ROLODEX_HOST", "127.0.0.1")
BASE = (os.environ.get("ROLODEX_BASE", "").rstrip("/") + "/") or "/"
DB   = os.environ.get("ROLODEX_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "rolodex.db"))

# ---------- auth (only enforced when ROLODEX_AUTH=1, i.e. the public instance) ----------
AUTH = os.environ.get("ROLODEX_AUTH") == "1"
USERS_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "users.json")
SESS_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sessions.json")
SESSION_TTL = 60 * 60 * 24 * 30

def _load_sessions():
    # Persist sessions to disk so a server restart doesn't log everyone out
    # (which surfaces as a spurious "auth" error on the next request).
    try:
        raw = json.load(open(SESS_DB))
        now = time.time()
        return {t: (v[0], v[1]) for t, v in raw.items() if v[1] > now}
    except Exception:
        return {}

SESSIONS = _load_sessions()  # token -> (email, expires_epoch)

def _save_sessions():
    try:
        os.makedirs(os.path.dirname(SESS_DB), exist_ok=True)
        json.dump(SESSIONS, open(SESS_DB, "w")); os.chmod(SESS_DB, 0o600)
    except Exception:
        pass

def _users():
    try:
        return json.load(open(USERS_DB))
    except Exception:
        return {}

def _save_users(u):
    os.makedirs(os.path.dirname(USERS_DB), exist_ok=True)
    json.dump(u, open(USERS_DB, "w")); os.chmod(USERS_DB, 0o600)

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
    _save_sessions()
    return tok

def session_ok(tok):
    v = SESSIONS.get(tok)
    if not v:
        return False
    if v[1] < time.time():
        SESSIONS.pop(tok, None); _save_sessions()
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
                         ("instagram", "instagram TEXT"),
                         ("owner", "owner TEXT")]:
            if col not in existing:
                try:
                    c.execute(f"ALTER TABLE contacts ADD COLUMN {ddl}")
                except sqlite3.OperationalError:
                    pass  # another instance added it first (shared DB, concurrent start)
        # multi-tenant: every contact belongs to one account (owner=email). Claim any
        # pre-existing (unowned) contacts for the primary account so legacy data stays private.
        c.execute("UPDATE contacts SET owner=? WHERE owner IS NULL OR owner=''",
                  (os.environ.get("ROLODEX_DEFAULT_OWNER", "matthew.motivate@proton.me").lower(),))
        c.execute("CREATE INDEX IF NOT EXISTS idx_contacts_owner ON contacts(owner)")
        # Your own profile — who you are, what you offer, what you're into.
        c.execute("""CREATE TABLE IF NOT EXISTS profiles(
            owner TEXT PRIMARY KEY,
            name TEXT, headline TEXT, bio TEXT,
            services TEXT, interests TEXT, location TEXT,
            instagram TEXT, website TEXT,
            visible INTEGER DEFAULT 1,
            updated_at TEXT)""")
        # Connections between accounts: a request from one owner to another.
        c.execute("""CREATE TABLE IF NOT EXISTS connections(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester TEXT NOT NULL, addressee TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT, updated_at TEXT)""")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_conn_pair ON connections(requester, addressee)")
        # ---- the social feed: posts, likes, comments ----
        c.execute("""CREATE TABLE IF NOT EXISTS posts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner TEXT NOT NULL, text TEXT, image_url TEXT,
            created_at TEXT)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at)")
        c.execute("""CREATE TABLE IF NOT EXISTS post_likes(
            post_id INTEGER NOT NULL, owner TEXT NOT NULL, created_at TEXT,
            PRIMARY KEY(post_id, owner))""")
        c.execute("""CREATE TABLE IF NOT EXISTS post_comments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL, owner TEXT NOT NULL,
            text TEXT NOT NULL, created_at TEXT)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_comments_post ON post_comments(post_id)")

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

def list_contacts(q="", category="", flt="", owner=None):
    sql = "SELECT * FROM contacts"
    where, args = ["owner=?"], [owner]
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

def get_contact(cid, owner=None):
    with db() as c:
        r = c.execute("SELECT * FROM contacts WHERE id=? AND owner=?", (cid, owner)).fetchone()
    return row_to_dict(r) if r else None

def upsert(data, cid=None, owner=None):
    vals = {k: (data.get(k) or None) for k in FIELDS}
    if not vals["name"]:
        raise ValueError("name required")
    if vals.get("priority") in (None, ""):
        vals["priority"] = 0
    with db() as c:
        if cid:
            vals["updated_at"] = now_iso()
            sets = ", ".join(f"{k}=?" for k in FIELDS + ["updated_at"])
            c.execute(f"UPDATE contacts SET {sets} WHERE id=? AND owner=?",
                      [vals[k] for k in FIELDS] + [vals["updated_at"], cid, owner])
            return cid
        vals["created_at"] = vals["updated_at"] = now_iso()
        if not vals.get("met_date"):
            vals["met_date"] = today()
        cols = FIELDS + ["created_at", "updated_at", "owner"]
        cur = c.execute(f"INSERT INTO contacts({','.join(cols)}) VALUES ({','.join('?'*len(cols))})",
                        [vals[k] for k in FIELDS] + [vals["created_at"], vals["updated_at"], owner])
        return cur.lastrowid

def log_touch(cid, owner=None):
    with db() as c:
        c.execute("UPDATE contacts SET last_contacted=?, updated_at=? WHERE id=? AND owner=?",
                  (today(), now_iso(), cid, owner))

def set_reachout(cid, on, reason=None, owner=None):
    with db() as c:
        row = c.execute("SELECT reach_out_added FROM contacts WHERE id=? AND owner=?", (cid, owner)).fetchone()
        added = ((row["reach_out_added"] if (row and row["reach_out_added"]) else now_iso()) if on else None)
        c.execute("UPDATE contacts SET reach_out=?, reach_out_reason=?, reach_out_added=?, updated_at=? WHERE id=? AND owner=?",
                  (1 if on else 0, (reason if on else None), added, now_iso(), cid, owner))

def delete_contact(cid, owner=None):
    with db() as c:
        c.execute("DELETE FROM contacts WHERE id=? AND owner=?", (cid, owner))

def stats(owner=None):
    with db() as c:
        rows = [row_to_dict(r) for r in c.execute("SELECT * FROM contacts WHERE owner=?", (owner,)).fetchall()]
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

def import_vcards(text, owner=None):
    added = 0
    for v in parse_vcards(text):
        with db() as c:
            dup = c.execute("SELECT id FROM contacts WHERE owner=? AND lower(name)=? AND ifnull(lower(email),'')=ifnull(?,'')",
                            (owner, v["name"].lower(), (v.get("email") or "").lower())).fetchone()
        if dup:
            continue
        upsert(v, owner=owner)
        added += 1
    return added

def _add_ig_handles(pairs, owner=None):
    added = 0; seen = set()
    for handle, href in pairs:
        h = (handle or "").lstrip("@").strip()
        if not h or h.lower() in seen:
            continue
        seen.add(h.lower())
        with db() as c:
            dup = c.execute("SELECT id FROM contacts WHERE owner=? AND lower(ifnull(instagram,''))=?",
                            (owner, h.lower())).fetchone()
        if dup:
            continue
        upsert({"name": "@" + h, "instagram": h, "category": "Instagram",
                "how_met": "Instagram", "notes": href or ("https://instagram.com/" + h)}, owner=owner)
        added += 1
    return added

def import_instagram(text, owner=None):
    """Import from Instagram's official 'Download Your Information' export
    (followers/following JSON), or a plain list of @handles (one per line)."""
    text = (text or "").strip()
    if not text:
        return 0
    try:
        data = json.loads(text)
    except Exception:
        handles = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return _add_ig_handles([(h, "") for h in handles], owner=owner)
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
    return _add_ig_handles(found, owner=owner)

# ---------- your profile ----------
PROFILE_FIELDS = ["name","headline","bio","services","interests","location","instagram","website"]

def get_profile(owner):
    with db() as c:
        r = c.execute("SELECT * FROM profiles WHERE owner=?", (owner,)).fetchone()
    if not r:
        return {"owner": owner, "visible": 1, **{k: "" for k in PROFILE_FIELDS}}
    return dict(r)

def save_profile(owner, data):
    vals = {k: (data.get(k) or "").strip() for k in PROFILE_FIELDS}
    visible = 1 if data.get("visible", True) else 0
    cols = PROFILE_FIELDS + ["visible", "updated_at", "owner"]
    with db() as c:
        exists = c.execute("SELECT 1 FROM profiles WHERE owner=?", (owner,)).fetchone()
        if exists:
            sets = ", ".join(f"{k}=?" for k in PROFILE_FIELDS + ["visible", "updated_at"])
            c.execute(f"UPDATE profiles SET {sets} WHERE owner=?",
                      [vals[k] for k in PROFILE_FIELDS] + [visible, now_iso(), owner])
        else:
            c.execute(f"INSERT INTO profiles({','.join(cols)}) VALUES ({','.join('?'*len(cols))})",
                      [vals[k] for k in PROFILE_FIELDS] + [visible, now_iso(), owner])
    return get_profile(owner)

# ---------- connecting with others ----------
def _conn_status(owner, other):
    """Relationship of `other` to `owner`: none|connected|outgoing|incoming."""
    with db() as c:
        r = c.execute("SELECT requester,addressee,status FROM connections "
                      "WHERE (requester=? AND addressee=?) OR (requester=? AND addressee=?)",
                      (owner, other, other, owner)).fetchone()
    if not r:
        return "none"
    if r["status"] == "accepted":
        return "connected"
    return "outgoing" if r["requester"] == owner else "incoming"

def directory(owner, q=""):
    """Other accounts with a visible profile, plus how you stand with each.

    `q` matches across name, headline, what they offer, and what they're into —
    so you can find people by need ("design", "fundraising", "climbing")."""
    with db() as c:
        rows = c.execute("SELECT * FROM profiles WHERE owner<>? AND visible=1 ORDER BY updated_at DESC",
                         (owner,)).fetchall()
    ql = (q or "").strip().lower()
    out = []
    for r in rows:
        d = dict(r)
        if ql:
            hay = " ".join(str(d.get(k) or "") for k in
                           ("name", "headline", "bio", "services", "interests", "location")).lower()
            if ql not in hay:
                continue
        d["status"] = _conn_status(owner, d["owner"])
        out.append(d)
    return out

def request_connection(owner, target):
    if not target or target == owner:
        raise ValueError("pick someone else")
    with db() as c:
        if not c.execute("SELECT 1 FROM profiles WHERE owner=?", (target,)).fetchone():
            raise ValueError("no such member")
        # If they already asked you, accept it instead of making a duplicate.
        theirs = c.execute("SELECT id FROM connections WHERE requester=? AND addressee=? AND status='pending'",
                           (target, owner)).fetchone()
        if theirs:
            c.execute("UPDATE connections SET status='accepted', updated_at=? WHERE id=?", (now_iso(), theirs["id"]))
            return "connected"
        c.execute("INSERT OR IGNORE INTO connections(requester,addressee,status,created_at,updated_at) "
                  "VALUES (?,?,'pending',?,?)", (owner, target, now_iso(), now_iso()))
    return "outgoing"

def respond_connection(owner, requester, accept):
    with db() as c:
        row = c.execute("SELECT id FROM connections WHERE requester=? AND addressee=? AND status='pending'",
                        (requester, owner)).fetchone()
        if not row:
            raise ValueError("no pending request from them")
        if accept:
            c.execute("UPDATE connections SET status='accepted', updated_at=? WHERE id=?", (now_iso(), row["id"]))
        else:
            c.execute("DELETE FROM connections WHERE id=?", (row["id"],))

def list_connections(owner):
    with db() as c:
        conns = c.execute("SELECT * FROM connections WHERE requester=? OR addressee=?",
                          (owner, owner)).fetchall()
        profs = {r["owner"]: dict(r) for r in c.execute("SELECT * FROM profiles").fetchall()}
    connected, incoming, outgoing = [], [], []
    for r in conns:
        other = r["addressee"] if r["requester"] == owner else r["requester"]
        prof = profs.get(other, {"owner": other, "name": other})
        prof = dict(prof); prof["owner"] = other
        if r["status"] == "accepted":
            prof["email"] = other  # connections can reach each other
            connected.append(prof)
        elif r["requester"] == owner:
            outgoing.append(prof)
        else:
            incoming.append(prof)
    return {"connected": connected, "incoming": incoming, "outgoing": outgoing}

# ---------- Apple Contacts: iCloud CardDAV sync (beta) ----------
def _dav(method, url, user, pw, body=None, depth=None, ctype="application/xml; charset=utf-8", _hops=0):
    """One CardDAV request. iCloud redirects contacts.icloud.com to a per-user
    partition host (e.g. p123-contacts.icloud.com); urllib strips the Authorization
    header across a host change, which iCloud answers with 401 — so we follow
    redirects ourselves and re-attach Basic auth each hop. iCloud also rejects
    requests with no User-Agent, so we always send one."""
    import base64, urllib.request, urllib.error
    data = body.encode() if isinstance(body, str) else body
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode())
    req.add_header("User-Agent", "Rolodex/1.0 (CardDAV sync)")
    req.add_header("Accept", "*/*")
    if depth is not None:
        req.add_header("Depth", str(depth))
    if body is not None:
        req.add_header("Content-Type", ctype)

    class _NoAutoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None  # we handle redirects manually, re-adding auth
    opener = urllib.request.build_opener(_NoAutoRedirect)
    try:
        with opener.open(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308) and _hops < 5:
            loc = e.headers.get("Location")
            if loc:
                return _dav(method, urllib.parse.urljoin(url, loc), user, pw, body, depth, ctype, _hops + 1)
        return e.code, e.read().decode("utf-8", "ignore")
    except Exception as e:
        return 0, str(e)

def carddav_sync(owner, icloud_email, app_password):
    """Pull contacts from iCloud over CardDAV and import them as vCards.

    Needs an Apple *app-specific* password (appleid.apple.com → Sign-In &
    Security → App-Specific Passwords), not the account password. iCloud uses
    per-user partition hosts, discovered from the principal, so we walk:
    principal → addressbook-home-set → the addressbooks → every .vcf.
    """
    import re as _re
    icloud_email = (icloud_email or "").strip()
    # Apple shows app-specific passwords as "abcd-efgh-ijkl-mnop"; users often paste
    # them with spaces or in the wrong case. Keep the dashes, drop stray whitespace.
    app_password = (app_password or "").strip().replace(" ", "")
    if "@" not in icloud_email or len(app_password) < 8:
        raise ValueError("Enter your iCloud email and an app-specific password (appleid.apple.com → Sign-In & Security → App-Specific Passwords).")
    base = "https://contacts.icloud.com"
    # 1) current-user-principal
    st, body = _dav("PROPFIND", base + "/", icloud_email, app_password, depth=0,
                    body='<d:propfind xmlns:d="DAV:"><d:prop><d:current-user-principal/></d:prop></d:propfind>')
    if st in (401, 403):
        raise ValueError("iCloud rejected those credentials. Use an app-specific password (not your Apple ID password) from appleid.apple.com → Sign-In & Security → App-Specific Passwords, and make sure 2-factor auth is on.")
    if st == 0 or st >= 500:
        raise ValueError("Couldn't reach iCloud right now — try again in a moment.")
    m = _re.search(r"<[^>]*current-user-principal>.*?<[^>]*href>([^<]+)</", body, _re.S | _re.I)
    if not m:
        raise ValueError(f"Connected to iCloud but couldn't read the account principal (HTTP {st}). Double-check the email.")
    principal = urllib.parse.urljoin(base + "/", m.group(1).strip())
    # 2) addressbook-home-set
    st, body = _dav("PROPFIND", principal, icloud_email, app_password, depth=0,
                    body='<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:carddav">'
                         '<d:prop><c:addressbook-home-set/></d:prop></d:propfind>')
    m = _re.search(r"addressbook-home-set>.*?<[^>]*href>([^<]+)</", body, _re.S | _re.I)
    if not m:
        raise ValueError("could not find your iCloud address-book home")
    home = urllib.parse.urljoin(principal, m.group(1).strip())
    # 3) list collections under the home, Depth:1
    st, body = _dav("PROPFIND", home, icloud_email, app_password, depth=1,
                    body='<d:propfind xmlns:d="DAV:"><d:prop><d:resourcetype/></d:prop></d:propfind>')
    books = _re.findall(r"<[^>]*response>(.*?)</[^>]*response>", body, _re.S | _re.I)
    vcards = []
    for resp in books:
        hm = _re.search(r"<[^>]*href>([^<]+)</", resp, _re.I)
        if not hm:
            continue
        href = hm.group(1).strip()
        coll = urllib.parse.urljoin(home, href)
        if coll.rstrip("/") == home.rstrip("/"):
            continue
        # 4) pull every card in this collection
        st2, b2 = _dav("REPORT", coll, icloud_email, app_password, depth=1,
                       body='<c:addressbook-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:carddav">'
                            '<d:prop><d:getetag/><c:address-data/></d:prop></c:addressbook-query>')
        for cd in _re.findall(r"BEGIN:VCARD.*?END:VCARD", b2, _re.S):
            vcards.append(cd.replace("&#13;", "").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">"))
    if not vcards:
        return 0
    return import_vcards("\n".join(vcards), owner=owner)

# ---------- the social feed ----------
def _author(c, owner):
    """A light author card for a post: their profile name/headline/instagram,
    falling back to the local part of their email when they have no profile."""
    r = c.execute("SELECT name, headline, instagram FROM profiles WHERE owner=?", (owner,)).fetchone()
    name = (r["name"] if r and r["name"] else "") or (owner.split("@")[0] if owner else "Someone")
    return {"owner": owner, "name": name,
            "headline": (r["headline"] if r else "") or "",
            "instagram": (r["instagram"] if r else "") or ""}

def create_post(owner, data):
    text = (data.get("text") or "").strip()
    image = (data.get("image_url") or "").strip()
    if not text and not image:
        raise ValueError("write something or add a photo")
    if image and not re.match(r"^https?://", image):
        raise ValueError("photo must be a http(s) link")
    with db() as c:
        cur = c.execute("INSERT INTO posts(owner,text,image_url,created_at) VALUES (?,?,?,?)",
                        (owner, text[:2000], image[:1000], now_iso()))
        return cur.lastrowid

def delete_post(owner, pid):
    with db() as c:
        c.execute("DELETE FROM posts WHERE id=? AND owner=?", (pid, owner))
        c.execute("DELETE FROM post_likes WHERE post_id=?", (pid,))
        c.execute("DELETE FROM post_comments WHERE post_id=?", (pid,))

def toggle_like(owner, pid):
    with db() as c:
        has = c.execute("SELECT 1 FROM post_likes WHERE post_id=? AND owner=?", (pid, owner)).fetchone()
        if has:
            c.execute("DELETE FROM post_likes WHERE post_id=? AND owner=?", (pid, owner))
            liked = False
        else:
            c.execute("INSERT OR IGNORE INTO post_likes(post_id,owner,created_at) VALUES (?,?,?)",
                      (pid, owner, now_iso()))
            liked = True
        n = c.execute("SELECT COUNT(*) FROM post_likes WHERE post_id=?", (pid,)).fetchone()[0]
    return {"liked": liked, "likes": n}

def add_comment(owner, pid, text):
    text = (text or "").strip()
    if not text:
        raise ValueError("empty comment")
    with db() as c:
        if not c.execute("SELECT 1 FROM posts WHERE id=?", (pid,)).fetchone():
            raise ValueError("no such post")
        c.execute("INSERT INTO post_comments(post_id,owner,text,created_at) VALUES (?,?,?,?)",
                  (pid, owner, text[:1000], now_iso()))
    return {"ok": True}

def feed(owner, only_owner=None, limit=100):
    """Newest posts across the whole network (Instagram-style public feed), or
    just one person's when `only_owner` is set. Each post carries its author
    card, like count + whether you liked it, and its comments."""
    with db() as c:
        if only_owner:
            rows = c.execute("SELECT * FROM posts WHERE owner=? ORDER BY id DESC LIMIT ?",
                             (only_owner, limit)).fetchall()
        else:
            rows = c.execute("SELECT * FROM posts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            pid = d["id"]
            d["author"] = _author(c, d["owner"])
            d["likes"] = c.execute("SELECT COUNT(*) FROM post_likes WHERE post_id=?", (pid,)).fetchone()[0]
            d["liked"] = bool(c.execute("SELECT 1 FROM post_likes WHERE post_id=? AND owner=?",
                                        (pid, owner)).fetchone())
            d["mine"] = (d["owner"] == owner)
            cm = c.execute("SELECT owner,text,created_at FROM post_comments WHERE post_id=? ORDER BY id ASC",
                           (pid,)).fetchall()
            d["comments"] = [{**dict(x), "author": _author(c, x["owner"])} for x in cm]
            out.append(d)
    return out

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
  <div class="sub" id="sub">Sign in to your network.</div>
  <label>Email</label><input id="email" type="email" autocomplete="username" autofocus>
  <label>Password</label><input id="pw" type="password" autocomplete="current-password">
  <button type="button" onclick="sub('login')">Sign in</button>
  <button type="button" onclick="sub('signup')" style="margin-top:9px;background:transparent;border:1px solid var(--line);color:var(--text)">Create account</button>
  <div class="err" id="err"></div>
</form>
<script>
function go(e){e.preventDefault();sub('login');return false;}
async function sub(mode){const email=document.getElementById('email').value,password=document.getElementById('pw').value,err=document.getElementById('err');err.textContent='';
 if(!email||!password){err.textContent='Enter your email and password.';return;}
 if(mode==='signup')document.getElementById('sub').textContent='Create your private network.';
 let r;try{r=await fetch('api/'+mode,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password})});}catch(_){err.textContent='Network error.';return;}
 if(r.ok){location.reload();return;}
 let m=mode==='signup'?'Could not create account.':'Wrong email or password.';try{const j=await r.json();if(j.error)m=j.error;}catch(_){}
 err.textContent=m;}
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

    def _user(self):
        """The owner (email) whose data this request may touch."""
        if not AUTH:
            return os.environ.get("ROLODEX_DEFAULT_OWNER", "matthew.motivate@proton.me").lower()
        tok = self._cookie("rolo_sess"); v = SESSIONS.get(tok) if tok else None
        return v[0] if v else None

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
        owner = self._user()
        if p == "/api/contacts":
            self._send(200, {"contacts": list_contacts(
                qs.get("q", [""])[0], qs.get("category", [""])[0], qs.get("filter", [""])[0], owner=owner)}); return
        if p == "/api/stats":
            self._send(200, stats(owner=owner)); return
        if p == "/api/profile":
            self._send(200, get_profile(owner)); return
        if p == "/api/directory":
            self._send(200, {"members": directory(owner, qs.get("q", [""])[0])}); return
        if p == "/api/connections":
            self._send(200, list_connections(owner)); return
        if p == "/api/feed":
            who = qs.get("owner", [""])[0].strip().lower() or None
            self._send(200, {"posts": feed(owner, only_owner=who)}); return
        if re.match(r"^/api/contacts/\d+$", p):
            cid = int(p.rsplit("/", 1)[1]); r = get_contact(cid, owner=owner)
            self._send(200 if r else 404, r or {"error": "not found"}); return
        self._send(404, {"error": "not found"})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path); p = u.path
        if p == "/api/login":
            try: d = json.loads(self._body() or b"{}")
            except Exception: d = {}
            if verify_login(d.get("email", ""), d.get("password", "")):
                tok = new_session((d.get("email", "") or "").strip().lower())
                body = json.dumps({"ok": True, "token": tok}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Set-Cookie", f"rolo_sess={tok}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age={SESSION_TTL}")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers(); self.wfile.write(body); return
            self._send(401, {"error": "invalid credentials"}); return
        if p == "/api/logout":
            tok = self._cookie("rolo_sess")
            if tok: SESSIONS.pop(tok, None); _save_sessions()
            self._send(200, {"ok": True}); return
        if p == "/api/signup":
            try: d = json.loads(self._body() or b"{}")
            except Exception: d = {}
            email = (d.get("email", "") or "").strip().lower(); pw = d.get("password", "") or ""
            if "@" not in email or "." not in email.split("@")[-1] or len(pw) < 6:
                self._send(400, {"error": "Enter a valid email and a password of at least 6 characters."}); return
            users = _users()
            if email in users:
                self._send(400, {"error": "That email already has an account — sign in instead."}); return
            salt = secrets.token_hex(16); users[email] = {"salt": salt, "hash": _hash_pw(pw, salt)}; _save_users(users)
            tok = new_session(email); body = json.dumps({"ok": True, "token": tok}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Set-Cookie", f"rolo_sess={tok}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age={SESSION_TTL}")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        if AUTH and not self._authed():
            self._send(401, {"error": "auth"}); return
        owner = self._user()
        try:
            if p == "/api/contacts":
                cid = upsert(json.loads(self._body() or b"{}"), owner=owner)
                self._send(200, {"ok": True, "id": cid}); return
            m = re.match(r"^/api/contacts/(\d+)(/(touch|delete|reachout))?$", p)
            if m:
                cid = int(m.group(1)); action = m.group(3)
                if action == "touch": log_touch(cid, owner=owner); self._send(200, {"ok": True}); return
                if action == "delete": delete_contact(cid, owner=owner); self._send(200, {"ok": True}); return
                if action == "reachout":
                    d = json.loads(self._body() or b"{}")
                    set_reachout(cid, d.get("on", True), d.get("reason"), owner=owner)
                    self._send(200, {"ok": True}); return
                upsert(json.loads(self._body() or b"{}"), cid, owner=owner); self._send(200, {"ok": True, "id": cid}); return
            if p == "/api/import":
                added = import_vcards(self._body().decode("utf-8", "ignore"), owner=owner)
                self._send(200, {"ok": True, "added": added}); return
            if p == "/api/import/instagram":
                added = import_instagram(self._body().decode("utf-8", "ignore"), owner=owner)
                self._send(200, {"ok": True, "added": added}); return
            if p == "/api/import/carddav":
                d = json.loads(self._body() or b"{}")
                added = carddav_sync(owner, (d.get("email") or "").strip(), d.get("password") or "")
                self._send(200, {"ok": True, "added": added}); return
            if p == "/api/profile":
                self._send(200, save_profile(owner, json.loads(self._body() or b"{}"))); return
            if p == "/api/connect":
                d = json.loads(self._body() or b"{}")
                status = request_connection(owner, (d.get("target") or "").strip().lower())
                self._send(200, {"ok": True, "status": status}); return
            if p == "/api/connect/respond":
                d = json.loads(self._body() or b"{}")
                respond_connection(owner, (d.get("requester") or "").strip().lower(), bool(d.get("accept")))
                self._send(200, {"ok": True}); return
            if p == "/api/posts":
                pid = create_post(owner, json.loads(self._body() or b"{}"))
                self._send(200, {"ok": True, "id": pid}); return
            if p == "/api/posts/like":
                d = json.loads(self._body() or b"{}")
                self._send(200, toggle_like(owner, int(d.get("id")))); return
            if p == "/api/posts/comment":
                d = json.loads(self._body() or b"{}")
                self._send(200, add_comment(owner, int(d.get("id")), d.get("text"))); return
            m = re.match(r"^/api/posts/(\d+)/delete$", p)
            if m:
                delete_post(owner, int(m.group(1))); self._send(200, {"ok": True}); return
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
/* ---- Lumen-style inline line-icons (currentColor) ---- */
.i{width:18px;height:18px;flex:0 0 auto;vertical-align:-3px}
.tab .i{width:17px;height:17px;display:block;margin:0 auto 3px}
.tab.on .i{filter:drop-shadow(0 0 5px currentColor)}
.icg .i{color:var(--accent)}
.chip .i,.btn .i,button .i{width:13px;height:13px;margin-right:4px}
.shead .i{width:16px;height:16px;color:var(--accent);filter:drop-shadow(0 0 5px currentColor)}
.shead{display:flex;align-items:center;gap:7px;font-weight:800;margin:2px 2px 8px}
/* ---- feed / posts ---- */
.composer{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:13px 15px;margin-bottom:14px}
.composer textarea{min-height:52px;border:none;background:transparent;padding:4px 2px}
.composer .crow{display:flex;gap:8px;align-items:center;margin-top:8px;border-top:1px solid var(--line);padding-top:10px}
.post{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);margin-bottom:12px;overflow:hidden}
.post-head{display:flex;align-items:center;gap:10px;padding:12px 14px}
.post-head .name{font-size:14px}.post-head .hl{color:var(--muted);font-size:11.5px}
.post-head .when{margin-left:auto;color:var(--muted);font-size:11px}
.post-text{padding:0 14px 12px;white-space:pre-wrap;word-break:break-word;font-size:14.5px;line-height:1.5}
.post-img{width:100%;display:block;max-height:560px;object-fit:cover;background:var(--panel2)}
.post-acts{display:flex;align-items:center;gap:16px;padding:10px 14px}
.act{display:flex;align-items:center;gap:6px;color:var(--muted);cursor:pointer;background:none;border:none;padding:0;font-weight:700;font-size:13px}
.act .i{width:21px;height:21px}
.act.on{color:#ff5d8f}.act.on .i{filter:drop-shadow(0 0 6px #ff5d8f)}
.act.del{margin-left:auto;color:var(--muted)}.act.del:hover{color:var(--warn)}
.cmts{border-top:1px solid var(--line);padding:10px 14px;display:flex;flex-direction:column;gap:7px}
.cmt{font-size:13px;line-height:1.4}.cmt b{font-weight:700}
.cmt-add{display:flex;gap:7px;margin-top:4px}
.cmt-add input{padding:7px 10px}
.post-empty{color:var(--muted);text-align:center;padding:40px 14px}
</style></head><body>
<header>
  <h1>Rolo<span>dex</span></h1>
  <div class="sub">Your network — searchable, categorized, follow-up aware</div>
</header>
<main>
  <div class="tabs">
    <div class="tab on" data-t="feed" onclick="tab('feed')" data-ic="grid">Feed</div>
    <div class="tab" data-t="home" onclick="tab('home')" data-ic="home">Overview</div>
    <div class="tab" data-t="net" onclick="tab('net')" data-ic="people">Network</div>
    <div class="tab" data-t="reach" onclick="tab('reach')" data-ic="phone">Reach out</div>
    <div class="tab" data-t="connect" onclick="tab('connect')" data-ic="link">Connect</div>
    <div class="tab" data-t="you" onclick="tab('you')" data-ic="user">You</div>
    <div class="tab" data-t="viz" onclick="tab('viz')" data-ic="chart">Insights</div>
    <div class="tab" data-t="add" onclick="tab('add')" data-ic="plus">Add</div>
  </div>

  <div id="feed" class="hidden">
    <div class="composer">
      <textarea id="po_text" placeholder="Share something with your network…"></textarea>
      <input id="po_img" placeholder="Photo link (optional) — https://…" style="margin-top:6px">
      <div class="crow">
        <span class="small muted icg"><span id="poImgIc"></span> add a photo by link</span>
        <button class="primary sm" style="margin-left:auto" onclick="createPost()">Post</button>
        <span id="poMsg" class="small muted"></span>
      </div>
    </div>
    <div id="feedList"></div>
  </div>

  <div id="home" class="hidden"></div>

  <div id="net" class="hidden">
    <div class="row" style="margin-bottom:10px"><input id="q" placeholder="Search name, company, category, notes…" oninput="load()"></div>
    <div id="cats" class="row wrap" style="gap:6px;margin-bottom:12px"></div>
    <div id="list"></div>
  </div>

  <div id="reach" class="hidden"></div>

  <div id="connect" class="hidden"></div>

  <div id="you" class="hidden">
    <div class="card">
      <div style="font-weight:800;margin-bottom:6px">Your profile</div>
      <div class="small muted" style="margin-bottom:8px">This is what other members see when you choose to be discoverable — who you are, what you offer, and what you're into.</div>
      <label class="f">Name</label><input id="p_name" placeholder="Your name">
      <label class="f">Headline</label><input id="p_headline" placeholder="e.g. Founder · building AI tools">
      <label class="f">About you</label><textarea id="p_bio" placeholder="A few sentences on who you are."></textarea>
      <label class="f">Services you offer</label><textarea id="p_services" placeholder="What you can help with — one per line or comma-separated."></textarea>
      <label class="f">Interested in</label><textarea id="p_interests" placeholder="Topics, hobbies, what you want to connect over."></textarea>
      <div class="grid2"><div><label class="f">Location</label><input id="p_location"></div>
        <div><label class="f">Instagram</label><input id="p_instagram" placeholder="@handle"></div></div>
      <label class="f">Website</label><input id="p_website" placeholder="https://">
      <label class="row" style="gap:8px;margin-top:12px;font-size:13px"><input type="checkbox" id="p_visible" style="width:auto" checked> Discoverable — let other members find &amp; connect with me</label>
      <div class="row" style="margin-top:12px;gap:8px"><button class="primary" onclick="saveProfile()">Save profile</button><span id="pMsg" class="small muted"></span></div>
    </div>
    <div id="myPosts" style="margin-top:16px"></div>
  </div>

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
      <div style="font-weight:800;margin-bottom:4px">Sync from Apple Contacts</div>
      <div class="small muted" style="margin-bottom:8px">Live sync pulls your iCloud contacts over CardDAV. Use an Apple <b>app-specific password</b> (appleid.apple.com → Sign-In &amp; Security → App-Specific Passwords) — not your Apple ID password. Nothing is stored; it's used once to pull and import.</div>
      <div class="grid2"><div><label class="f">iCloud email</label><input id="cd_email" placeholder="you@icloud.com" autocomplete="off"></div>
        <div><label class="f">App-specific password</label><input id="cd_pw" type="password" placeholder="xxxx-xxxx-xxxx-xxxx" autocomplete="off"></div></div>
      <div class="row" style="margin-top:8px"><button class="primary" onclick="syncCardDav()">Sync iCloud contacts</button><span id="cdMsg" class="small muted"></span></div>
      <div class="small muted" style="margin-top:12px">— or paste a vCard export (.vcf) —</div>
      <textarea id="vcf" placeholder="BEGIN:VCARD …" style="margin-top:6px"></textarea>
      <div class="row" style="margin-top:8px"><button class="primary" onclick="importVcf()">Import vCards</button>
        <label class="chip" style="cursor:pointer">📁 Upload .vcf<input type="file" id="vcfFile" accept=".vcf,text/vcard,text/x-vcard" style="display:none" onchange="uploadVcf(event)"></label>
        <span id="impMsg" class="small muted"></span></div>

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

// ---- Lumen-style inline line-icons (no asset files; currentColor-driven) ----
const SVGP={
  grid:'<rect x="3.5" y="3.5" width="7" height="7" rx="1.6"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.6"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.6"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.6"/>',
  home:'<path d="M3.5 11 12 4l8.5 7"/><path d="M5.5 10.2V19h13v-8.8"/><rect x="10" y="13.5" width="4" height="5.5" rx="0.6"/>',
  people:'<circle cx="12" cy="7" r="2.6"/><circle cx="5.3" cy="9.5" r="2.1"/><circle cx="18.7" cy="9.5" r="2.1"/><path d="M7.4 18.5c0-2.5 2-4.5 4.6-4.5s4.6 2 4.6 4.5"/><path d="M2.4 17.4c0-1.9 1.3-3.5 3.1-3.6M21.6 17.4c0-1.9-1.3-3.5-3.1-3.6"/>',
  phone:'<path d="M6.5 3.5h3l1.3 4-2 1.4a11 11 0 0 0 4.8 4.8l1.4-2 4 1.3v3a2 2 0 0 1-2.2 2A15.5 15.5 0 0 1 4.5 5.7 2 2 0 0 1 6.5 3.5Z"/>',
  link:'<path d="M9.5 14.5 14.5 9.5"/><path d="M8 11 6 13a3.5 3.5 0 0 0 5 5l2-2"/><path d="M16 13l2-2a3.5 3.5 0 0 0-5-5l-2 2"/>',
  user:'<circle cx="12" cy="8" r="3.4"/><path d="M5.5 19.5c0-3.3 2.9-5.8 6.5-5.8s6.5 2.5 6.5 5.8"/>',
  chart:'<line x1="4" y1="20" x2="20" y2="20"/><rect x="5.5" y="11" width="3" height="7" rx="1" fill="currentColor" stroke="none"/><rect x="10.5" y="7" width="3" height="11" rx="1" fill="currentColor" stroke="none"/><rect x="15.5" y="13" width="3" height="5" rx="1" fill="currentColor" stroke="none"/>',
  plus:'<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
  heart:'<path d="M12 20S4 15 4 9.2A4 4 0 0 1 12 6.6 4 4 0 0 1 20 9.2C20 15 12 20 12 20Z"/>',
  heartf:'<path d="M12 20S4 15 4 9.2A4 4 0 0 1 12 6.6 4 4 0 0 1 20 9.2C20 15 12 20 12 20Z" fill="currentColor" stroke="none"/>',
  chat:'<path d="M4 5.5h16a1.5 1.5 0 0 1 1.5 1.5v7.5a1.5 1.5 0 0 1-1.5 1.5H9.5L5 20v-4H4a1.5 1.5 0 0 1-1.5-1.5V7A1.5 1.5 0 0 1 4 5.5Z"/>',
  send:'<path d="M4 11.8 20 4l-7.2 16-2.6-6.2L4 11.8Z" fill="currentColor" stroke="none"/>',
  camera:'<path d="M3 8.5a2 2 0 0 1 2-2h2l1.2-1.8h7.6L17 6.5a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><circle cx="12" cy="13" r="3.4"/>',
  photo:'<rect x="3.5" y="5" width="17" height="14" rx="2.2"/><circle cx="8.5" cy="10" r="1.6"/><path d="M4 17l5-4 4 3 3-2.5 4 3.5"/>',
  globe:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.6 2.6 2.6 15.4 0 18M12 3c-2.6 2.6-2.6 15.4 0 18"/>',
  pin:'<path d="M12 21s7-6.5 7-12a7 7 0 0 0-14 0c0 5.5 7 12 7 12Z"/><circle cx="12" cy="9" r="2.5" fill="currentColor" stroke="none"/>',
  check:'<path d="M5 12.5l4.5 4.5L19 6.5"/>',
  close:'<line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/>',
  clock:'<circle cx="12" cy="12" r="8"/><path d="M12 8v4.5l3 1.8"/>',
  star:'<path d="M12 3l2.6 5.5 6 .8-4.4 4.1 1.1 5.9L12 16.6 6.7 19.3l1.1-5.9L3.4 9.3l6-.8L12 3Z" fill="currentColor" stroke="none"/>',
  mail:'<rect x="3.5" y="5.5" width="17" height="13" rx="2.2"/><path d="M4 7l8 6 8-6"/>',
  trash:'<path d="M5 7h14M9 7V5.5A1.5 1.5 0 0 1 10.5 4h3A1.5 1.5 0 0 1 15 5.5V7M7 7l1 12.5A1.5 1.5 0 0 0 9.5 21h5a1.5 1.5 0 0 0 1.5-1.4L17 7"/>',
  hourglass:'<path d="M7 4h10M7 20h10M8 4c0 4 8 4 8 8s-8 4-8 8M16 4c0 4-8 4-8 8s8 4 8 8"/>',
  sparkle:'<path d="M12 3c.7 5 3 7.3 8 8-5 .7-7.3 3-8 8-.7-5-3-7.3-8-8 5-.7 7.3-3 8-8Z" fill="currentColor" stroke="none"/>',
  search:'<circle cx="11" cy="11" r="6.5"/><line x1="16" y1="16" x2="21" y2="21"/>'
};
function ic(name,cls){return '<svg class="i '+(cls||'')+'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+(SVGP[name]||'')+'</svg>';}
function renderTabIcons(){
  for(const el of document.querySelectorAll('.tab[data-ic]')){
    el.innerHTML=ic(el.dataset.ic)+'<span>'+el.textContent.trim()+'</span>';
  }
  const pii=$('poImgIc');if(pii)pii.innerHTML=ic('photo');
}
function timeAgo(iso){if(!iso)return '';const s=Math.max(1,(Date.now()-new Date(iso).getTime())/1000);
  if(s<60)return Math.floor(s)+'s';if(s<3600)return Math.floor(s/60)+'m';if(s<86400)return Math.floor(s/3600)+'h';
  if(s<604800)return Math.floor(s/86400)+'d';return new Date(iso).toLocaleDateString(undefined,{month:'short',day:'numeric'});}

// ---- feed ----
async function loadFeed(){
  const d=await api('api/feed');
  $('feedList').innerHTML = d.posts.length ? d.posts.map(postCard).join('')
    : '<div class="post-empty">No posts yet — be the first to share something with your network.</div>';
}
function postCard(p){
  const a=p.author||{}, col=catColor(a.name||a.owner);
  const cmts=(p.comments||[]).map(c=>`<div class="cmt"><b>${esc((c.author&&c.author.name)||c.owner)}</b> ${esc(c.text)}</div>`).join('');
  return `<div class="post" data-id="${p.id}">
    <div class="post-head">
      <div class="avatar" style="width:34px;height:34px;background:${col}">${esc(initials(a.name||a.owner))}</div>
      <div style="min-width:0"><div class="name">${esc(a.name||a.owner)}</div>${a.headline?`<div class="hl">${esc(a.headline)}</div>`:''}</div>
      <span class="when">${timeAgo(p.created_at)}</span>
    </div>
    ${p.text?`<div class="post-text">${esc(p.text)}</div>`:''}
    ${p.image_url?`<img class="post-img" src="${esc(p.image_url)}" loading="lazy" alt="">`:''}
    <div class="post-acts">
      <button class="act like ${p.liked?'on':''}" onclick="likePost(${p.id})">${ic(p.liked?'heartf':'heart')}<span>${p.likes||0}</span></button>
      <button class="act" onclick="focusComment(${p.id})">${ic('chat')}<span>${(p.comments||[]).length}</span></button>
      ${p.mine?`<button class="act del" title="Delete" onclick="delPost(${p.id})">${ic('trash')}</button>`:''}
    </div>
    <div class="cmts">
      ${cmts}
      <div class="cmt-add"><input id="cm_${p.id}" placeholder="Add a comment…" onkeydown="if(event.key==='Enter')addComment(${p.id})">
        <button class="sm" onclick="addComment(${p.id})">${ic('send')}</button></div>
    </div>
  </div>`;
}
async function createPost(){
  const text=$('po_text').value, image_url=$('po_img').value;
  if(!text.trim()&&!image_url.trim()){$('poMsg').textContent='Write something or add a photo.';return;}
  $('poMsg').textContent='Posting…';
  const r=await api('api/posts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,image_url})});
  if(r.error){$('poMsg').textContent=r.error;return;}
  $('po_text').value='';$('po_img').value='';$('poMsg').textContent='';loadFeed();
}
async function likePost(id){await api('api/posts/like',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});loadFeed();}
function focusComment(id){const el=$('cm_'+id);if(el)el.focus();}
async function addComment(id){const el=$('cm_'+id);const text=el?el.value:'';if(!text.trim())return;
  await api('api/posts/comment',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,text})});loadFeed();}
async function delPost(id){if(!confirm('Delete this post?'))return;await api('api/posts/'+id+'/delete',{method:'POST'});loadFeed();}

function tab(t){for(const el of document.querySelectorAll('.tab'))el.classList.toggle('on',el.dataset.t===t);
  for(const id of['feed','home','net','reach','connect','you','viz','add'])$(id).classList.toggle('hidden',id!==t);
  if(t==='feed')loadFeed();if(t==='home')loadOverview();if(t==='reach')loadReach();if(t==='viz')loadViz();if(t==='net')load();
  if(t==='connect')loadConnect();if(t==='you')loadProfile();}

async function loadOverview(){
  const rec=await api('api/contacts?filter=recent');
  const ro=await api('api/contacts?filter=reachout');
  $('home').innerHTML=
    `<div class="shead">${ic('sparkle')}Recently added <span class="muted small">· ${rec.contacts.length}</span></div>`+
    (rec.contacts.length?rec.contacts.map(contactCard).join(''):`<div class="empty">No contacts yet — add your first from the Add tab, or paste a vCard export.</div>`)+
    `<div class="shead" style="margin-top:18px">${ic('pin')}Reach out to… <span class="muted small">· ${ro.contacts.length}</span></div>`+
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
function uploadVcf(ev){const f=ev.target.files[0];if(!f)return;const rd=new FileReader();
  rd.onload=async()=>{$('impMsg').textContent='Importing '+f.name+'…';
    const r=await api('api/import',{method:'POST',body:rd.result});$('impMsg').textContent='Added '+(r.added||0)+' contacts from '+f.name;load();};
  rd.readAsText(f);ev.target.value='';}
async function syncCardDav(){const email=$('cd_email').value.trim(),pw=$('cd_pw').value.trim();
  if(!email||!pw){$('cdMsg').textContent='Enter your iCloud email and app-specific password.';return;}
  $('cdMsg').textContent='Connecting to iCloud…';
  let r;try{r=await fetch('api/import/carddav',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password:pw})});}catch(_){$('cdMsg').textContent='Network error.';return;}
  const j=await r.json();
  if(r.ok){$('cd_pw').value='';$('cdMsg').textContent='Synced '+(j.added||0)+' contacts from iCloud.';load();}
  else{$('cdMsg').textContent=j.error||'Sync failed.';}}

// ---- profile ----
async function loadProfile(){const p=await api('api/profile');
  for(const k of ['name','headline','bio','services','interests','location','instagram','website'])if($('p_'+k))$('p_'+k).value=p[k]||'';
  $('p_visible').checked=p.visible!==0;$('pMsg').textContent='';loadMyPosts();}
async function saveProfile(){const body={visible:$('p_visible').checked};
  for(const k of ['name','headline','bio','services','interests','location','instagram','website'])body[k]=$('p_'+k).value;
  $('pMsg').textContent='Saving…';await api('api/profile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  $('pMsg').textContent='Saved ✓';}

// ---- connect with others ----
function memberCard(m,ctx){
  const col=catColor(m.name||m.owner);
  const bits=[];
  if(m.headline)bits.push(`<div class="small" style="color:#cdd5e4">${esc(m.headline)}</div>`);
  if(m.services)bits.push(`<div class="small muted" style="margin-top:4px"><b>Offers:</b> ${esc(m.services)}</div>`);
  if(m.interests)bits.push(`<div class="small muted"><b>Into:</b> ${esc(m.interests)}</div>`);
  const links=[];
  if(m.location)links.push(`<span>${ic('pin')} ${esc(m.location)}</span>`);
  if(m.instagram)links.push(`<a class="chip" target="_blank" rel="noopener" href="https://instagram.com/${esc((m.instagram||'').replace(/^@/,''))}">${ic('camera')} ${esc(m.instagram)}</a>`);
  if(m.website)links.push(`<a class="chip" target="_blank" rel="noopener" href="${esc(m.website)}">${ic('globe')} Site</a>`);
  let action='';
  const connChip=`<span class="chip" style="border-color:var(--accent);color:var(--accent)">${ic('link')} Connected</span>`;
  const reqChip=`<span class="chip">${ic('hourglass')} Requested</span>`;
  if(ctx==='incoming')action=`<button class="sm primary" onclick="respond('${esc(m.owner)}',true)">${ic('check')} Accept</button><button class="sm" onclick="respond('${esc(m.owner)}',false)">Decline</button>`;
  else if(ctx==='outgoing')action=reqChip;
  else if(ctx==='connected')action=connChip+(m.email?`<a class="chip" href="mailto:${esc(m.email)}">${ic('mail')} Email</a>`:'');
  else{const s=m.status;action=(s==='connected')?connChip
      :(s==='outgoing')?reqChip
      :(s==='incoming')?`<button class="sm primary" onclick="respond('${esc(m.owner)}',true)">${ic('check')} Accept</button>`
      :`<button class="sm primary" onclick="connectTo('${esc(m.owner)}')">${ic('plus')} Connect</button>`;}
  return `<div class="card"><div class="row" style="gap:11px;min-width:0">
      <div class="avatar" style="background:${col}">${esc(initials(m.name||m.owner))}</div>
      <div style="min-width:0;flex:1"><div class="name">${esc(m.name||m.owner)}</div>${bits.join('')}
        ${links.length?`<div class="row wrap small muted" style="gap:8px;margin-top:6px">${links.join('')}</div>`:''}</div></div>
    <div class="row wrap" style="gap:6px;margin-top:10px">${action}</div></div>`;
}
let DIRQ='';
async function loadConnect(){
  const conns=await api('api/connections');
  let html='';
  if(conns.incoming.length){html+=`<div class="shead">${ic('people')}Wants to connect <span class="muted small">· ${conns.incoming.length}</span></div>`+conns.incoming.map(m=>memberCard(m,'incoming')).join('');}
  html+=`<div class="shead" style="margin-top:18px">${ic('link')}Your connections <span class="muted small">· ${conns.connected.length}</span></div>`;
  html+= conns.connected.length?conns.connected.map(m=>memberCard(m,'connected')).join(''):'<div class="card small muted">No connections yet — find people below.</div>';
  html+=`<div class="shead" style="margin-top:18px">${ic('search')}Discover members</div>
    <div class="row" style="margin-bottom:10px"><input id="dq" placeholder="Search people by what they offer or want — design, legal, climbing…" value="${esc(DIRQ)}" oninput="dirSearch(this.value)"></div>
    <div id="dirList"></div>`;
  if(conns.outgoing.length){html+=`<div class="shead" style="margin-top:18px">${ic('hourglass')}Pending requests <span class="muted small">· ${conns.outgoing.length}</span></div>`+conns.outgoing.map(m=>memberCard(m,'outgoing')).join('');}
  $('connect').innerHTML=html;
  renderDir();
}
let _dirT=null;
function dirSearch(v){DIRQ=v;clearTimeout(_dirT);_dirT=setTimeout(renderDir,200);}
async function renderDir(){
  const dir=await api('api/directory?q='+encodeURIComponent(DIRQ));
  const box=$('dirList');if(!box)return;
  box.innerHTML= dir.members.length?dir.members.map(m=>memberCard(m,'')).join(''):
    `<div class="card small muted">${DIRQ?'No members match “'+esc(DIRQ)+'”.':'No other discoverable members yet. Fill out your profile in the 🙋 You tab so others can find you.'}</div>`;
}
async function connectTo(target){await api('api/connect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({target})});loadConnect();}
async function respond(requester,accept){await api('api/connect/respond',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({requester,accept})});loadConnect();}
async function importIg(){const t=$('ig').value;if(!t.trim())return;$('igMsg').textContent='Importing…';
  const r=await api('api/import/instagram',{method:'POST',body:t});$('igMsg').textContent='Added '+(r.added||0)+' from Instagram';$('ig').value='';load();}
function closeSheet(){$('modal').classList.remove('on');}

// ---- your own posts, shown under your profile ----
async function loadMyPosts(){
  const me=await api('api/profile');
  const d=await api('api/feed?owner='+encodeURIComponent(me.owner||''));
  const box=$('myPosts');if(!box)return;
  box.innerHTML='<div class="shead">'+ic('grid')+'Your posts <span class="muted small">· '+d.posts.length+'</span></div>'
    +(d.posts.length?d.posts.map(postCard).join(''):'<div class="card small muted">You haven\'t posted yet — share something from the Feed tab.</div>');
}

renderTabIcons();
loadFeed();
</script></body></html>"""

if __name__ == "__main__":
    init_db()
    print(f"Rolodex on :{PORT} base={BASE} db={DB}")
    ThreadingHTTPServer((HOST, PORT), H).serve_forever()

#!/usr/bin/env python3
"""
Travelog — a travel journal with an AI companion.

- Keep trips and per-place journal entries (place, date, who you were with,
  the experiences and the ideas you grappled with).
- Ask an AI agent to tell you about a place and its history (Gemini + Wikipedia).
- Let the companion reflect with you (prompts) or polish rough notes into a
  first-person journal entry, and write a whole-trip recap.
- Generate AI collages of your photos (Gemini image model), with a built-in
  client-side canvas collage as an always-works fallback.

Zero third-party deps — stdlib only (http.server + sqlite3), reboot-safe and light.
Storage lives in ./data (sqlite + photo/collage files). Mount under the command
hub with TRAVELOG_BASE=/travelog (served Tailscale-only, like the other apps).
"""
import os, json, re, sqlite3, base64, hashlib, urllib.request, urllib.parse, mimetypes, math, threading, subprocess, tempfile, shutil, secrets, struct
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone

# PORT: honor Railway's $PORT; local hub still sets TRAVELOG_PORT. HOST: stays
# loopback for the local hub, but Railway/containers set TRAVELOG_HOST=0.0.0.0.
PORT = int(os.environ.get("TRAVELOG_PORT") or os.environ.get("PORT") or "18824")
HOST = os.environ.get("TRAVELOG_HOST", "127.0.0.1")
BASE = (os.environ.get("TRAVELOG_BASE", "").rstrip("/"))  # e.g. "/travelog" or ""
HERE = os.path.dirname(os.path.abspath(__file__))
# DATA: overridable so a Railway persistent volume can hold the db + media.
DATA = os.environ.get("TRAVELOG_DATA") or os.path.join(HERE, "data")
PHOTOS = os.path.join(DATA, "photos")
COLLAGES = os.path.join(DATA, "collages")
DB = os.path.join(DATA, "travelog.db")
for d in (DATA, PHOTOS, COLLAGES):
    os.makedirs(d, exist_ok=True)

TEXT_MODEL = os.environ.get("TRAVELOG_TEXT_MODEL", "gemini-flash-latest")
IMAGE_MODEL = os.environ.get("TRAVELOG_IMAGE_MODEL", "gemini-3.1-flash-image")
UA = {"User-Agent": "Travelog/1.0 (personal travel journal; contact: matthew)"}

# ---- storage ---------------------------------------------------------------

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c

def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS trips(
      id INTEGER PRIMARY KEY, title TEXT, destination TEXT,
      start_date TEXT, end_date TEXT, cover TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS entries(
      id INTEGER PRIMARY KEY, trip_id INTEGER, place TEXT, lat REAL, lon REAL,
      date TEXT, companions TEXT, experience TEXT, ideas TEXT, briefing TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS photos(
      id INTEGER PRIMARY KEY, trip_id INTEGER, entry_id INTEGER, filename TEXT, created TEXT,
      category TEXT, tags TEXT, caption TEXT, people INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS collages(
      id INTEGER PRIMARY KEY, trip_id INTEGER, filename TEXT, style TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS ai_sections(
      id INTEGER PRIMARY KEY, entry_id INTEGER, kind TEXT,
      content TEXT, active INTEGER DEFAULT 1, created TEXT);
    CREATE INDEX IF NOT EXISTS ix_sections ON ai_sections(entry_id, kind);
    CREATE TABLE IF NOT EXISTS chat_messages(
      id INTEGER PRIMARY KEY, trip_id INTEGER, role TEXT, content TEXT, created TEXT);
    CREATE INDEX IF NOT EXISTS ix_chat ON chat_messages(trip_id, id);
    CREATE TABLE IF NOT EXISTS trip_notes(
      id INTEGER PRIMARY KEY, trip_id INTEGER, category TEXT, text TEXT,
      place TEXT, source TEXT DEFAULT 'ai', created TEXT);
    CREATE INDEX IF NOT EXISTS ix_notes ON trip_notes(trip_id, category, id);
    CREATE TABLE IF NOT EXISTS trip_members(
      id INTEGER PRIMARY KEY, trip_id INTEGER, token TEXT, name TEXT, color TEXT,
      created TEXT, last_seen TEXT, UNIQUE(trip_id, token));
    CREATE INDEX IF NOT EXISTS ix_members ON trip_members(trip_id, id);
    CREATE TABLE IF NOT EXISTS import_jobs(
      job_id TEXT PRIMARY KEY, trip_id INTEGER, kind TEXT DEFAULT 'icloud', state TEXT,
      total INTEGER DEFAULT 0, done INTEGER DEFAULT 0, imported INTEGER DEFAULT 0,
      unplaced INTEGER DEFAULT 0, error TEXT, created TEXT, updated TEXT);
    CREATE INDEX IF NOT EXISTS ix_imports ON import_jobs(trip_id, created);
    CREATE TABLE IF NOT EXISTS quizzes(
      entry_id INTEGER PRIMARY KEY, content TEXT, reward TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS quiz_progress(
      id INTEGER PRIMARY KEY, entry_id INTEGER, device TEXT, name TEXT,
      best INTEGER DEFAULT 0, total INTEGER DEFAULT 0, completed INTEGER DEFAULT 0,
      created TEXT, updated TEXT);
    CREATE UNIQUE INDEX IF NOT EXISTS ix_quizprog ON quiz_progress(entry_id, device);
    CREATE TABLE IF NOT EXISTS expenses(
      id INTEGER PRIMARY KEY, trip_id INTEGER, payer TEXT, amount_cents INTEGER,
      currency TEXT DEFAULT 'USD', description TEXT, created TEXT,
      source TEXT DEFAULT 'manual', external_id TEXT);
    CREATE INDEX IF NOT EXISTS ix_expenses ON expenses(trip_id, id);
    CREATE TABLE IF NOT EXISTS expense_shares(
      expense_id INTEGER, member TEXT);
    CREATE INDEX IF NOT EXISTS ix_eshares ON expense_shares(expense_id);
    CREATE TABLE IF NOT EXISTS trip_cards(
      trip_id INTEGER PRIMARY KEY, provider TEXT DEFAULT 'sim',
      cardholder_id TEXT, card_id TEXT, last4 TEXT, brand TEXT DEFAULT 'Visa',
      status TEXT DEFAULT 'active', funder TEXT, currency TEXT DEFAULT 'USD', created TEXT);
    """)
    # migrate older expenses tables (pre trip-card) to carry source + external_id
    ecol = [r[1] for r in c.execute("PRAGMA table_info(expenses)").fetchall()]
    for col, ddl in (("source", "source TEXT DEFAULT 'manual'"), ("external_id", "external_id TEXT")):
        if col not in ecol:
            c.execute(f"ALTER TABLE expenses ADD COLUMN {ddl}")
    # now that external_id exists (fresh or migrated), the dedupe index is safe
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_exp_ext ON expenses(external_id) WHERE external_id IS NOT NULL")
    # any job still marked "running" at startup lost its worker thread when the process stopped
    c.execute("UPDATE import_jobs SET state='interrupted', updated=? WHERE state='running'", (now(),))
    # collaborative trips: a share token to invite others, and per-row contributor attribution
    tcols = [r[1] for r in c.execute("PRAGMA table_info(trips)").fetchall()]
    if "share_token" not in tcols:
        c.execute("ALTER TABLE trips ADD COLUMN share_token TEXT")
    # migrate older DBs that predate photo auto-categorization / geotagging / contributor attribution
    cols = [r[1] for r in c.execute("PRAGMA table_info(photos)").fetchall()]
    for col, ddl in (("category", "category TEXT"), ("tags", "tags TEXT"),
                     ("caption", "caption TEXT"), ("people", "people INTEGER DEFAULT 0"),
                     ("lat", "lat REAL"), ("lon", "lon REAL"), ("member", "member TEXT")):
        if col not in cols:
            c.execute(f"ALTER TABLE photos ADD COLUMN {ddl}")
    # a user-chosen representative photo per location (entry); NULL = auto-pick
    ecols = [r[1] for r in c.execute("PRAGMA table_info(entries)").fetchall()]
    if "cover" not in ecols:
        c.execute("ALTER TABLE entries ADD COLUMN cover TEXT")
    if "landmark" not in ecols:
        c.execute("ALTER TABLE entries ADD COLUMN landmark TEXT")   # AI landmark "totem" for the map radiate
    if "member" not in ecols:
        c.execute("ALTER TABLE entries ADD COLUMN member TEXT")     # contributor who logged this place
    # migrate the old single per-entry "briefing" into the new sectioned guide (as History v1),
    # so existing trips keep their generated text instead of losing it to the redesign.
    for r in c.execute("SELECT id,briefing FROM entries WHERE briefing IS NOT NULL AND TRIM(briefing)!=''").fetchall():
        has = c.execute("SELECT 1 FROM ai_sections WHERE entry_id=? AND kind='history' LIMIT 1", (r["id"],)).fetchone()
        if not has:
            c.execute("INSERT INTO ai_sections(entry_id,kind,content,active,created) VALUES(?,?,?,1,?)",
                      (r["id"], "history", r["briefing"], now()))
    c.commit(); c.close()

def now():
    return datetime.now(timezone.utc).isoformat()

def expenses_payload(c, tid):
    """Everything the Split tab needs: the members, the expenses (each with who
    it was split among), each person's net balance, and the fewest transfers
    that settle everyone up."""
    members = [{"name": r["name"], "color": r["color"]}
               for r in c.execute("SELECT name,color FROM trip_members WHERE trip_id=? ORDER BY id", (tid,)).fetchall()]
    rows = c.execute("SELECT id,payer,amount_cents,currency,description,created FROM expenses "
                     "WHERE trip_id=? ORDER BY id DESC", (tid,)).fetchall()
    currency = rows[0]["currency"] if rows else "USD"
    # net[name] in cents: positive = owed money back, negative = owes
    net = {m["name"]: 0 for m in members}
    expenses = []
    for r in rows:
        shares = [x["member"] for x in
                  c.execute("SELECT member FROM expense_shares WHERE expense_id=?", (r["id"],)).fetchall()]
        amt = r["amount_cents"] or 0
        expenses.append({"id": r["id"], "payer": r["payer"], "amount_cents": amt,
                         "currency": r["currency"] or "USD", "description": r["description"] or "",
                         "created": r["created"], "shares": shares})
        if not shares:
            continue
        net.setdefault(r["payer"], 0)
        net[r["payer"]] += amt
        # integer cents, remainder spread onto the first few so the split is exact
        base, rem = divmod(amt, len(shares))
        for i, person in enumerate(shares):
            net.setdefault(person, 0)
            net[person] -= base + (1 if i < rem else 0)
    balances = []
    for m in members:
        n = net.get(m["name"], 0)
        paid = sum(e["amount_cents"] for e in expenses if e["payer"] == m["name"])
        balances.append({"name": m["name"], "color": m["color"], "net_cents": n, "paid_cents": paid})
    # settle-up: greedily match the biggest debtor to the biggest creditor
    debt = sorted([[k, v] for k, v in net.items() if v < -0], key=lambda x: x[1])      # most negative first
    cred = sorted([[k, v] for k, v in net.items() if v > 0], key=lambda x: -x[1])       # most positive first
    settle, i, j = [], 0, 0
    while i < len(debt) and j < len(cred):
        pay = min(-debt[i][1], cred[j][1])
        if pay > 0:
            settle.append({"from": debt[i][0], "to": cred[j][0], "amount_cents": pay})
            debt[i][1] += pay
            cred[j][1] -= pay
        if debt[i][1] == 0:
            i += 1
        if cred[j][1] == 0:
            j += 1
    return {"members": members, "expenses": expenses, "balances": balances,
            "settle": settle, "currency": currency, "card": get_trip_card(c, tid),
            "card_live": stripe_live()}

# ---- Trip Card: a shared card whose charges auto-split (Stripe Issuing) ----
STRIPE_SECRET = os.environ.get("STRIPE_SECRET_KEY")        # sk_test_... (test mode) or sk_live_...
STRIPE_WH_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")  # whsec_... to verify webhooks

def stripe_live():
    return bool(STRIPE_SECRET)

def _stripe(method, path, params=None):
    """Minimal Stripe REST call (form-encoded), no SDK. Flattens nested dicts
    into Stripe's bracket syntax (e.g. billing[address][city])."""
    import urllib.request
    flat = {}
    def put(k, v):
        if isinstance(v, dict):
            for kk, vv in v.items():
                put(f"{k}[{kk}]", vv)
        elif isinstance(v, (list, tuple)):
            for i, vv in enumerate(v):
                put(f"{k}[{i}]", vv)
        elif v is not None:
            flat[k] = v
    for k, v in (params or {}).items():
        put(k, v)
    data = urllib.parse.urlencode(flat).encode() if flat else None
    req = urllib.request.Request("https://api.stripe.com/v1/" + path, data=data, method=method)
    req.add_header("Authorization", "Bearer " + STRIPE_SECRET)
    req.add_header("Stripe-Version", "2024-06-20")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def create_trip_card(c, tid, funder, currency="USD"):
    """Issue a virtual card for the trip. Real card via Stripe Issuing when a
    secret key is set; otherwise a simulated card so the flow is demoable."""
    name = funder or "Trip"
    if stripe_live():
        ch = _stripe("POST", "issuing/cardholders", {
            "name": name[:24], "type": "individual",
            "billing": {"address": {"line1": "1 Trip St", "city": "NYC",
                                     "state": "NY", "postal_code": "10001", "country": "US"}}})
        card = _stripe("POST", "issuing/cards", {
            "cardholder": ch["id"], "currency": currency.lower(), "type": "virtual",
            "status": "active", "metadata": {"trip_id": str(tid)}})
        last4 = card.get("last4", "----"); brand = (card.get("brand") or "Visa").title()
        prov, chid, cid = "stripe", ch["id"], card["id"]
    else:
        import random
        last4 = "".join(random.choice("0123456789") for _ in range(4))
        prov, chid, cid, brand = "sim", None, "sim_" + secrets.token_hex(6), "Visa"
    c.execute("INSERT OR REPLACE INTO trip_cards(trip_id,provider,cardholder_id,card_id,last4,brand,status,funder,currency,created) "
              "VALUES(?,?,?,?,?,?,?,?,?,?)",
              (tid, prov, chid, cid, last4, brand, "active", funder, currency, now()))
    c.commit()
    return get_trip_card(c, tid)

def get_trip_card(c, tid):
    r = c.execute("SELECT provider,card_id,last4,brand,status,funder,currency FROM trip_cards WHERE trip_id=?",
                  (tid,)).fetchone()
    if not r:
        return None
    d = dict(r); d["live"] = (d["provider"] == "stripe")
    return d

def capture_card_charge(c, tid, amount_cents, merchant, ext_id, currency="USD"):
    """A swipe on the trip card becomes an expense paid by the card's funder,
    split equally across everyone on the trip. Deduped on the external id so a
    replayed webhook can't double-charge."""
    if amount_cents <= 0:
        return None
    if ext_id and c.execute("SELECT 1 FROM expenses WHERE external_id=?", (ext_id,)).fetchone():
        return None  # already captured
    card = get_trip_card(c, tid)
    funder = (card or {}).get("funder") or "Trip Card"
    members = [r["name"] for r in c.execute("SELECT name FROM trip_members WHERE trip_id=? ORDER BY id", (tid,)).fetchall()]
    if not members:
        members = [funder]
    cur = c.execute("INSERT INTO expenses(trip_id,payer,amount_cents,currency,description,created,source,external_id) "
                    "VALUES(?,?,?,?,?,?, 'card', ?)",
                    (tid, funder, amount_cents, currency, merchant or "Card charge", now(), ext_id))
    eid = cur.lastrowid
    for m in members:
        c.execute("INSERT INTO expense_shares(expense_id,member) VALUES(?,?)", (eid, m))
    c.commit()
    return eid

# ---- AI + geo backend ------------------------------------------------------

def _load_key():
    k = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if k:
        return k
    try:
        with open("/root/.openclaw/.env") as f:
            for line in f:
                line = line.strip()
                for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
                    if line.startswith(name + "="):
                        v = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if v:
                            return v
    except OSError:
        pass
    return ""

GEMINI_KEY = _load_key()

def get_json(url, timeout=12):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def gemini_text(prompt, want_json=False, timeout=30):
    if not GEMINI_KEY:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{TEXT_MODEL}:generateContent?key={GEMINI_KEY}"
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    if want_json:
        body["generationConfig"] = {"response_mime_type": "application/json"}
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            j = json.loads(r.read().decode("utf-8", "replace"))
        return j["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return None

def gemini_generate(contents, system=None, tools=None, timeout=45):
    """Lower-level call supporting system_instruction + function-calling tools.
    Returns the model's `content` dict ({'role','parts':[...]}) or None."""
    if not GEMINI_KEY:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{TEXT_MODEL}:generateContent?key={GEMINI_KEY}"
    body = {"contents": contents}
    if system:
        body["system_instruction"] = {"parts": [{"text": system}]}
    if tools:
        body["tools"] = tools
        body["toolConfig"] = {"functionCallingConfig": {"mode": "AUTO"}}
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            j = json.loads(r.read().decode("utf-8", "replace"))
        return j["candidates"][0]["content"]
    except Exception:
        return None

def gemini_image(prompt, images=None, timeout=150):
    """images: list of (mime, raw_bytes). Returns (mime, raw_bytes) or None."""
    if not GEMINI_KEY:
        return None
    parts = []
    for mime, raw in (images or []):
        parts.append({"inlineData": {"mimeType": mime, "data": base64.b64encode(raw).decode()}})
    parts.append({"text": prompt})
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{IMAGE_MODEL}:generateContent?key={GEMINI_KEY}"
    data = json.dumps({"contents": [{"parts": parts}]}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            j = json.loads(r.read().decode("utf-8", "replace"))
        for p in j["candidates"][0]["content"]["parts"]:
            if "inlineData" in p:
                d = p["inlineData"]
                return d.get("mimeType", "image/jpeg"), base64.b64decode(d["data"])
    except Exception:
        pass
    return None

# travel-photo taxonomy the quick AI sorts uploads into
CATEGORIES = ["People", "Scenery", "Food & Drink", "Architecture", "Nature",
              "City & Street", "Beach & Water", "Art & Museum", "Nightlife",
              "Signs & Documents", "Transit", "Animals", "Journal", "Other"]

def gemini_vision_text(raw, mime, prompt, timeout=45):
    """Send one image + a prompt, return plain text (used for handwriting OCR)."""
    if not GEMINI_KEY:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{TEXT_MODEL}:generateContent?key={GEMINI_KEY}"
    body = {"contents": [{"parts": [
                {"inlineData": {"mimeType": mime, "data": base64.b64encode(raw).decode()}},
                {"text": prompt}]}],
            "generationConfig": {"temperature": 0.1}}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            j = json.loads(r.read().decode("utf-8", "replace"))
        return j["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return None

def gemini_vision(raw, mime, timeout=30):
    """Quick-classify a travel photo. Returns {category,people,tags,caption} or None."""
    if not GEMINI_KEY:
        return None
    cats = ", ".join(CATEGORIES)
    prompt = ("You are sorting a traveler's photos into a tidy library. Look at this photo and reply with JSON only: "
              f'{{"category": one of [{cats}], '
              '"people": true if recognizable people are a main subject else false, '
              '"tags": up to 3 short lowercase keywords (subject, place-type, or mood), '
              '"caption": one short, specific, non-cheesy sentence describing what it shows}. '
              "Pick the single best category. No prose outside the JSON.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{TEXT_MODEL}:generateContent?key={GEMINI_KEY}"
    body = {"contents": [{"parts": [
                {"inlineData": {"mimeType": mime, "data": base64.b64encode(raw).decode()}},
                {"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json", "temperature": 0.2}}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            j = json.loads(r.read().decode("utf-8", "replace"))
        info = json.loads(j["candidates"][0]["content"]["parts"][0]["text"])
    except Exception:
        return None
    cat = info.get("category", "Other")
    if cat not in CATEGORIES:
        cat = "Other"
    tags = [str(t)[:24] for t in (info.get("tags") or [])][:3]
    return {"category": cat, "people": 1 if info.get("people") else 0,
            "tags": tags, "caption": str(info.get("caption", ""))[:200]}

def geocode(place):
    try:
        j = get_json("https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&q=" +
                     urllib.parse.quote(place))
        if j:
            return float(j[0]["lat"]), float(j[0]["lon"]), j[0].get("display_name", place)
    except Exception:
        pass
    return None, None, place

def _haversine_km(a_lat, a_lon, b_lat, b_lon):
    R = 6371.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp = math.radians(b_lat - a_lat); dl = math.radians(b_lon - a_lon)
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(min(1.0, math.sqrt(h)))

def _entry_latlon(c, e):
    """Resolve an entry's coordinates (explicit -> avg of its geotagged photos -> geocode),
    saving the resolved value back so we geocode each place at most once."""
    lat, lon = e["lat"], e["lon"]
    if lat is not None and lon is not None:
        return lat, lon
    ph = c.execute("SELECT AVG(lat),AVG(lon),COUNT(*) FROM photos WHERE entry_id=? AND lat IS NOT NULL", (e["id"],)).fetchone()
    if ph and ph[2]:
        lat, lon = ph[0], ph[1]
    elif e["place"]:
        lat, lon, _ = geocode(e["place"])
    if lat is not None and lon is not None:
        c.execute("UPDATE entries SET lat=?,lon=? WHERE id=?", (lat, lon, e["id"]))
        c.commit()
    return lat, lon

def exif_gps(raw):
    """Pull (lat, lon) from a JPEG's EXIF GPS block. Pure-stdlib, no deps.
    Returns (lat, lon) floats or (None, None). Mirrors the client getExifGps()."""
    try:
        if not raw or raw[0:2] != b"\xff\xd8":
            return (None, None)
        data = raw[:300000]
        n = len(data); i = 2
        while i + 4 < n:
            if data[i] != 0xFF:
                break
            marker = data[i + 1]
            seglen = struct.unpack(">H", data[i + 2:i + 4])[0]
            if marker == 0xE1 and data[i + 4:i + 8] == b"Exif":
                tiff = i + 10
                en = ">" if data[tiff:tiff + 2] == b"MM" else "<"
                ifd0 = tiff + struct.unpack(en + "I", data[tiff + 4:tiff + 8])[0]
                cnt = struct.unpack(en + "H", data[ifd0:ifd0 + 2])[0]
                gps = 0
                for k in range(cnt):
                    e = ifd0 + 2 + k * 12
                    if struct.unpack(en + "H", data[e:e + 2])[0] == 0x8825:
                        gps = tiff + struct.unpack(en + "I", data[e + 8:e + 12])[0]; break
                if not gps:
                    return (None, None)

                def rat(off):
                    num = struct.unpack(en + "I", data[off:off + 4])[0]
                    den = struct.unpack(en + "I", data[off + 4:off + 8])[0]
                    return num / den if den else 0.0

                def dms(off):
                    return rat(off) + rat(off + 8) / 60 + rat(off + 16) / 3600

                gcnt = struct.unpack(en + "H", data[gps:gps + 2])[0]
                latref = lonref = None; lat = lon = None
                for k in range(gcnt):
                    e = gps + 2 + k * 12
                    tag = struct.unpack(en + "H", data[e:e + 2])[0]
                    valoff = tiff + struct.unpack(en + "I", data[e + 8:e + 12])[0]
                    if tag == 1:   latref = data[e + 8:e + 9].decode("latin1")
                    elif tag == 2: lat = dms(valoff)
                    elif tag == 3: lonref = data[e + 8:e + 9].decode("latin1")
                    elif tag == 4: lon = dms(valoff)
                if lat is None or lon is None:
                    return (None, None)
                if latref == "S": lat = -lat
                if lonref == "W": lon = -lon
                return (round(lat, 6), round(lon, 6))
            i += 2 + seglen
    except Exception:
        pass
    return (None, None)

def match_photo_entry(c, trip_id, plat, plon, caption="", tags_json="", max_km=0.6):
    """Best-effort match of a photo to a location (entry) in the same trip.
    Primary signal: GPS (nearest entry within max_km). Fallback: the entry's place
    name appears in the photo's AI caption/tags. Returns an entry id or None."""
    ents = c.execute("SELECT * FROM entries WHERE trip_id=? ORDER BY date,id", (trip_id,)).fetchall()
    if not ents:
        return None
    if plat is not None and plon is not None:
        best, bestd = None, 1e9
        for e in ents:
            elat, elon = _entry_latlon(c, e)
            if elat is None or elon is None:
                continue
            d = _haversine_km(plat, plon, elat, elon)
            if d < bestd:
                best, bestd = e, d
        if best is not None and bestd <= max_km:
            return best["id"]
    hay = ((caption or "") + " " + (tags_json or "")).lower()
    if hay.strip():
        for e in ents:
            pl = (e["place"] or "").split(",")[0].strip().lower()
            if len(pl) >= 4 and pl in hay:
                return e["id"]
    return None

# ---- iCloud public Shared Album import (Apple's undocumented web-stream API) ----
IMPORTS = {}
_IMP_LOCK = threading.Lock()
_IMP_SEQ = [0]
_B62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
def _b62(s):
    n = 0
    for ch in s:
        n = n * 62 + _B62.index(ch)
    return n

def icloud_token(url):
    u = (url or "").strip()
    u = re.sub(r"^https?://", "", u, flags=re.I)        # drop scheme so host isn't mistaken for the token
    if "/icloudlinks/" in u:                              # newer iCloud shared *link*: icloud.com/photos/#/icloudlinks/TOKEN
        u = u.split("/icloudlinks/", 1)[1]
    elif "/photos/" in u:                                 # current album share: share.icloud.com/photos/TOKEN
        u = u.split("/photos/", 1)[1]
    elif "#" in u:                                         # classic: www.icloud.com/sharedalbum/#TOKEN
        u = u.split("#", 1)[1]
    elif "/sharedalbum/" in u:                            # www.icloud.com/sharedalbum/TOKEN
        u = u.split("/sharedalbum/", 1)[1]
    elif "/" in u:                                         # any other host/path — take the last segment
        u = u.rstrip("/").split("/")[-1]
    u = re.split(r"[?&/#]", u.strip().strip("/"))[0]
    return u or None

def _icloud_host(token):
    try:
        part = _b62(token[1:2]) if token[0] == "A" else _b62(token[1:3])
        return f"p{part:02d}-sharedstreams.icloud.com"
    except Exception:
        return "p01-sharedstreams.icloud.com"

def _icloud_post(host, token, path, payload):
    req = urllib.request.Request(
        f"https://{host}/{token}/sharedstreams/{path}", data=json.dumps(payload).encode(),
        method="POST", headers={"Content-Type": "text/plain;charset=UTF-8",
                                "Origin": "https://www.icloud.com", "User-Agent": "Mozilla/5.0"})
    try:
        r = urllib.request.urlopen(req, timeout=30)
        return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()
    except Exception:
        return -1, None, b""   # network/DNS failure (e.g. an unresolvable guessed partition host)

def icloud_fetch(token):
    """-> list of {url, caption}. Follows the 330 partition redirect. Raises on failure."""
    host = _icloud_host(token)
    code, hdrs, body = _icloud_post(host, token, "webstream", {"streamCtag": None})
    try: print(f"[icloud] token={token!r} guessed_host={host} webstream_code={code}", flush=True)
    except Exception: pass
    # Wrong partition (330) or an unresolvable/bad guessed host (-1): bootstrap from a known-good
    # host, which 330-redirects us to the album's real partition.
    if code in (-1, 330):
        nh = hdrs.get("X-Apple-MMe-Host") if (code == 330 and hdrs) else None
        if not nh:
            code, hdrs, body = _icloud_post("p01-sharedstreams.icloud.com", token, "webstream", {"streamCtag": None})
            nh = hdrs.get("X-Apple-MMe-Host") if (code == 330 and hdrs) else None
        if nh:
            host = nh
            code, hdrs, body = _icloud_post(host, token, "webstream", {"streamCtag": None})
        try: print(f"[icloud] redirect host={host} code={code}", flush=True)
        except Exception: pass
    if code != 200:
        raise RuntimeError(f"HTTP {code} — the album may be private (turn on its Public Website) or the link's expired.")
    data = json.loads(body or b"{}")
    picks, guids = [], []
    for ph in (data.get("photos") or []):
        best = None
        for d in (ph.get("derivatives") or {}).values():
            try:
                fs = int(d.get("fileSize") or 0)
            except Exception:
                fs = 0
            if d.get("checksum") and (best is None or fs > best[0]):
                best = (fs, d.get("checksum"))
        if best:
            picks.append({"checksum": best[1], "caption": ph.get("caption") or ""})
            guids.append(ph.get("photoGuid"))
    urls = {}
    for i in range(0, len(guids), 20):
        code, hdrs, body = _icloud_post(host, token, "webasseturls", {"photoGuids": guids[i:i + 20]})
        if code != 200:
            continue
        for checksum, it in (json.loads(body or b"{}").get("items") or {}).items():
            if it.get("url_location") and it.get("url_path"):
                urls[checksum] = f"https://{it['url_location']}{it['url_path']}"
    return [{"url": urls[p["checksum"]], "caption": p["caption"]} for p in picks if p["checksum"] in urls]

# ---- newer iCloud *shared links* (icloud.com/photos/#/icloudlinks/… = CloudKit "CMM" shared moments) ----
def icloud_cmm_token(url):
    u = (url or "").strip()
    m = re.search(r"/icloudlinks/([A-Za-z0-9_-]+)", u) or re.search(r"icloud\.com/photos/#/?([A-Za-z0-9_-]+)", u)
    return m.group(1) if m else None

_CMM_HDRS = {"Content-Type": "application/json", "Origin": "https://www.icloud.com", "User-Agent": "Mozilla/5.0"}
def _cmm_resolve(token):
    # Verified working: the public shared DB on ckdatabasews, passing the shortGUID as
    # both sharing_url_key and in the body. Returns the zone + anonymous access token + partition host.
    url = ("https://ckdatabasews.icloud.com/database/1/com.apple.photos.cloud/production/public/records/resolve"
           "?remapEnums=true&getCurrentSyncToken=true&sharing_url_key=" + urllib.parse.quote(token, safe=""))
    body = {"shortGUIDs": [{"value": token, "shouldFetchRootRecord": True}]}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers=_CMM_HDRS)
    with urllib.request.urlopen(req, timeout=30) as r:
        j = json.loads(r.read())
    res = (j.get("results") or [None])[0]
    if not res:
        raise RuntimeError("That iCloud link didn't resolve to a shared album.")
    if res.get("requireAppleLogin") or not (res.get("anonymousPublicAccess") or {}).get("token"):
        raise RuntimeError("That shared link isn't public (it needs sign-in).")
    return res

def _cmm_post(part, token, wtok, path, body):
    # The shared DB requires BOTH the sharing_url_key and the anonymous publicAccessAuthToken.
    url = (f"{part}/database/1/com.apple.photos.cloud/production/shared{path}"
           "?remapEnums=true&getCurrentSyncToken=true"
           "&sharing_url_key=" + urllib.parse.quote(token, safe="") +
           "&publicAccessAuthToken=" + urllib.parse.quote(wtok, safe=""))
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers=_CMM_HDRS)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

def icloud_cmm_fetch(token):
    """Fetch a public iCloud shared link (CloudKit CMM moment). -> [{url, caption, filename}]."""
    res = _cmm_resolve(token)
    apa = res["anonymousPublicAccess"]
    wtok, part = apa["token"], apa["databasePartition"].rstrip("/")
    zone = {k: res["zoneID"][k] for k in ("zoneName", "ownerRecordName", "zoneType") if k in res["zoneID"]}
    masters, cont, pages = [], None, 0
    while pages < 25:   # paginate the whole zone (25 pages * 200 = 5000 photo ceiling)
        body = {
            "query": {
                "recordType": "CPLAssetAndMasterByAssetDateWithoutHiddenOrDeleted",
                "filterBy": [{"fieldName": "direction", "comparator": "EQUALS",
                              "fieldValue": {"value": "DESCENDING", "type": "STRING"}}],
            },
            "zoneID": zone, "resultsLimit": 200,
        }
        if cont:
            body["continuationMarker"] = cont
        code, b = _cmm_post(part, token, wtok, "/records/query", body)
        if code != 200:
            if not masters:
                raise RuntimeError(f"HTTP {code} reading the shared moment.")
            break
        j = json.loads(b or b"{}")
        masters += [r for r in j.get("records", []) if r.get("recordType") == "CPLMaster"]
        cont = j.get("continuationMarker")
        pages += 1
        if not cont:
            break
    out = []
    for m in masters:
        f = m.get("fields", {})
        # prefer the medium JPEG rendering (displayable everywhere, GPS EXIF intact); then JPEG thumb
        v = ((f.get("resJPEGMedRes") or f.get("resJPEGThumbRes") or {}).get("value")) or {}
        du = v.get("downloadURL")
        if not du:
            continue
        fn = (f.get("filenameEnc") or {}).get("value") or ""
        try:
            fn = base64.b64decode(fn).decode("utf-8", "replace")
        except Exception:
            fn = ""
        # CloudKit download URLs carry a ${f} filename placeholder that must be filled in.
        safe = urllib.parse.quote((fn or (m.get("recordName", "photo") + ".jpg")).replace("/", "_"))
        du = du.replace("${f}", safe).replace("%24%7Bf%7D", safe)
        out.append({"url": du, "caption": "", "filename": fn})
    return out

def icloud_fetch_photos(raw_url):
    """Unified: supports classic Shared Albums (sharedstreams) AND iCloud shared links (CloudKit CMM)."""
    cmm = icloud_cmm_token(raw_url)
    if cmm:
        return icloud_cmm_fetch(cmm)
    tok = icloud_token(raw_url)
    if not tok:
        raise RuntimeError("Couldn't find a shared-album token in that link.")
    try:
        items = icloud_fetch(tok)
        if items:
            return items
        raise RuntimeError("empty album")
    except Exception:
        # share.icloud.com/photos/<token> can also be a CloudKit shared link — try that before giving up
        try:
            return icloud_cmm_fetch(tok)
        except Exception:
            raise

def _job_save(c, job_id, trip_id):
    """Mirror the in-memory job state to import_jobs so it survives page reloads / is trip-discoverable."""
    st = IMPORTS.get(job_id) or {}
    try:
        c.execute(
            "INSERT INTO import_jobs(job_id,trip_id,kind,state,total,done,imported,unplaced,error,created,updated)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(job_id) DO UPDATE SET state=excluded.state,total=excluded.total,done=excluded.done,"
            " imported=excluded.imported,unplaced=excluded.unplaced,error=excluded.error,updated=excluded.updated",
            (job_id, trip_id, "icloud", st.get("state"), st.get("total", 0), st.get("done", 0),
             st.get("imported", 0), st.get("unplaced", 0), st.get("error"), st.get("created") or now(), now()))
        c.commit()
    except Exception:
        pass

def _run_icloud_import(job_id, trip_id, url):
    st = IMPORTS[job_id]
    c = db()
    try:
        try:
            items = icloud_fetch_photos(url)
        except Exception as e:
            st.update(state="error", error="Couldn't read that album: " + str(e)); _job_save(c, job_id, trip_id); return
        st.update(total=len(items)); _job_save(c, job_id, trip_id)
        if not items:
            st.update(state="done", error="No photos found — check the link / Public Website setting.")
            _job_save(c, job_id, trip_id); return
        for it in items[:300]:
            try:
                raw = urllib.request.urlopen(urllib.request.Request(
                    it["url"], headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
                dataurl = "data:image/jpeg;base64," + base64.b64encode(raw).decode()
                fn = save_dataurl(dataurl, PHOTOS, "ic")
                if not fn:
                    st["done"] += 1; _job_save(c, job_id, trip_id); continue
                category, tags, caption, people = "Other", [], it.get("caption") or "", 0
                if GEMINI_KEY:
                    info = gemini_vision(raw, "image/jpeg")
                    if info:
                        category, tags = info["category"], info["tags"]
                        caption = info["caption"] or caption; people = info["people"]
                glat, glon = exif_gps(raw)   # auto-place on the map from embedded GPS
                cur = c.execute("INSERT INTO photos(trip_id,entry_id,filename,category,tags,caption,people,lat,lon,created)"
                                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                                (trip_id, None, fn, category, json.dumps(tags), caption, people, glat, glon, now()))
                pid = cur.lastrowid
                eid = match_photo_entry(c, trip_id, glat, glon, caption, json.dumps(tags))
                if eid:
                    c.execute("UPDATE photos SET entry_id=? WHERE id=?", (eid, pid))
                else:
                    st["unplaced"] += 1
                c.commit()
                st["imported"] += 1
            except Exception:
                pass
            st["done"] += 1
            _job_save(c, job_id, trip_id)
        st.update(state="done"); _job_save(c, job_id, trip_id)
    finally:
        c.close()

def start_icloud_import(trip_id, url):
    with _IMP_LOCK:
        _IMP_SEQ[0] += 1
        job_id = hashlib.sha1((now() + str(_IMP_SEQ[0]) + str(url)).encode()).hexdigest()[:12]
    IMPORTS[job_id] = {"state": "running", "total": 0, "done": 0, "imported": 0,
                       "unplaced": 0, "error": None, "created": now(), "trip_id": trip_id}
    c = db()
    try: _job_save(c, job_id, trip_id)
    finally: c.close()
    threading.Thread(target=_run_icloud_import, args=(job_id, trip_id, url), daemon=True).start()
    return job_id

# ---- AI "landmark totem": one generated landmark icon per location (center of its map radiate) ----
LANDJOBS = {}
def _run_landmarks(job_id, trip_id):
    st = LANDJOBS[job_id]
    c = db()
    try:
        trip = c.execute("SELECT destination,title FROM trips WHERE id=?", (trip_id,)).fetchone()
        dest = ((trip["destination"] or trip["title"] or "") if trip else "")
        rows = c.execute("SELECT id,place FROM entries WHERE trip_id=? AND (landmark IS NULL OR landmark='') "
                         "AND place IS NOT NULL AND TRIM(place)!=''", (trip_id,)).fetchall()
        st.update(total=len(rows))
        for e in rows:
            if not GEMINI_KEY:
                st.update(error="No image key configured."); break
            prompt = ("A single iconic landmark that best represents " + e["place"] + (", " + dest if dest else "") +
                      ". Render it as a clean miniature 3D icon / totem, centered, isolated on a solid dark charcoal "
                      "background, soft studio lighting, vivid colors, no text, no watermark, no border, square.")
            try:
                res = gemini_image(prompt)
                if res:
                    mime, raw = res
                    fn = save_dataurl("data:" + mime + ";base64," + base64.b64encode(raw).decode(), PHOTOS, "lm")
                    if fn:
                        c.execute("UPDATE entries SET landmark=? WHERE id=?", (fn, e["id"])); c.commit()
                        st["done_items"].append({"id": e["id"], "landmark": fn})
            except Exception:
                pass
            st["done"] += 1
        st.update(state="done")
    finally:
        c.close()

def start_landmarks(trip_id):
    with _IMP_LOCK:
        _IMP_SEQ[0] += 1
        job_id = hashlib.sha1((now() + "lm" + str(_IMP_SEQ[0])).encode()).hexdigest()[:12]
    LANDJOBS[job_id] = {"state": "running", "total": 0, "done": 0, "done_items": [], "error": None}
    threading.Thread(target=_run_landmarks, args=(job_id, trip_id), daemon=True).start()
    return job_id

def wiki_extract(place, lat=None, lon=None):
    """Best-effort: a short encyclopedic extract for context (place name, then nearby)."""
    try:
        j = get_json("https://en.wikipedia.org/w/api.php?action=query&prop=extracts&exintro"
                     "&explaintext&exsentences=5&redirects=1&format=json&titles=" +
                     urllib.parse.quote(place))
        pages = (j.get("query", {}) or {}).get("pages", {}) or {}
        for _, pg in pages.items():
            ex = pg.get("extract", "")
            if ex and len(ex) > 60:
                return ex
    except Exception:
        pass
    if lat is not None and lon is not None:
        try:
            j = get_json(f"https://en.wikipedia.org/w/api.php?action=query&list=geosearch"
                         f"&gscoord={lat}%7C{lon}&gsradius=4000&gslimit=1&format=json")
            lst = (j.get("query", {}) or {}).get("geosearch", []) or []
            if lst:
                return wiki_extract(lst[0]["title"])
        except Exception:
            pass
    return ""

# ---- per-destination AI guide sections -------------------------------------

SECTION_KINDS = ["landmarks", "history", "modern", "essentials", "guide"]

def generate_section(kind, e):
    """Generate one subsection of the 'About here' guide for an entry (dict)."""
    place = (e.get("place") or "").strip()
    if not place:
        return None
    # ground the factual sections with geo + wiki; the personal guide uses the traveler's own notes
    wiki = ""
    if kind in ("landmarks", "history", "modern", "essentials"):
        lat, lon = e.get("lat"), e.get("lon")
        if lat is None or lon is None:
            lat, lon, _ = geocode(place)
        wiki = wiki_extract(place, lat, lon)
    prompts = {
        "landmarks": (f"You are a seasoned local guide. For a traveler in {place}, describe the landmarks and sights "
                      f"genuinely worth their time — 3 to 5 of them. For each, put the name on its own line, then 1-2 vivid, "
                      f"specific sentences (what it is, why it matters, a detail to look for). Concrete, not generic. "
                      f"No intro or outro.\n\nReference notes (may be partial):\n{wiki[:1500]}"),
        "history":   (f"You are a warm historian. In 4-6 vivid sentences, tell the history of {place}: its origins, the eras "
                      f"and forces that shaped it, and a genuine detail most visitors miss. Specific and evocative, not a list, "
                      f"no preamble.\n\nReference notes (may be partial):\n{wiki[:1500]}"),
        "modern":    (f"Describe {place} as it is TODAY for a visitor — 4-6 sentences on modern life and culture: the feel of "
                      f"its streets and neighborhoods, food and markets, how people spend their days, and what's changed "
                      f"recently. Specific and grounded, no clichés, no preamble.\n\nReference notes (may be partial):\n{wiki[:1200]}"),
        "essentials":(f"You are a savvy, caring local helping a visitor truly UNDERSTAND {place} before they go. Write a practical "
                      f"'know before you go' briefing. Use these labeled lines, each on its own line, label then a colon then 1-2 "
                      f"concrete sentences (skip any that don't apply):\n"
                      f"Language: the main language + 2-3 useful phrases with rough pronunciation.\n"
                      f"Customs & etiquette: what's polite and what to avoid.\n"
                      f"Food to try: 2-3 specific local dishes or drinks.\n"
                      f"Money & tipping: currency, cards vs cash, tipping norms.\n"
                      f"Getting around: how people actually get around.\n"
                      f"Best time & pace: when to visit / daily rhythm.\n"
                      f"Good to know: one safety or cultural heads-up most visitors miss.\n"
                      f"Be specific to {place}, not generic travel advice. No intro or outro.\n\nReference notes (may be partial):\n{wiki[:1200]}"),
        "guide":     (f"You are this traveler's personal guide to {place}. Using what you know about THEM, write 4-6 warm, "
                      f"practical, specific sentences addressed to 'you' — what they'd personally love here, tips on timing and "
                      f"how to experience it, and a suggestion tuned to their company and interests. Grounded and genuine, no "
                      f"clichés, no preamble.\n\nAbout this visit:\n"
                      f"- Dates: {e.get('date') or '(unknown)'}\n- With: {e.get('companions') or 'traveling solo'}\n"
                      f"- Their notes on the experience: {(e.get('experience') or '(none yet)')[:600]}\n"
                      f"- Ideas they're grappling with: {(e.get('ideas') or '(none yet)')[:400]}"),
    }
    text = gemini_text(prompts[kind])
    if not text and kind in ("landmarks", "history", "modern") and wiki:
        text = wiki[:600]
    return text.strip() if text else None

def generate_quiz(e):
    """A short, fun multiple-choice quiz about a destination. Returns a list of
    {q, choices[4], answer(int 0-3), fact} dicts, or None."""
    place = (e.get("place") or "").strip()
    if not place:
        return None
    lat, lon = e.get("lat"), e.get("lon")
    if lat is None or lon is None:
        lat, lon, _ = geocode(place)
    wiki = wiki_extract(place, lat, lon)
    prompt = (f"Create a fun, surprising 5-question multiple-choice quiz that teaches a traveler about {place}. "
              f"Mix history, culture, food, geography and quirky trivia — delightful, not a dry exam. "
              f"Each question has exactly 4 options with ONE correct answer, and a one-sentence 'fact' that teaches "
              f"something memorable (shown after they answer). Keep questions and options short.\n"
              f"Return STRICT JSON: a list of 5 objects with keys: q (string), choices (array of 4 strings), "
              f"answer (integer 0-3 index of the correct choice), fact (string). No prose, JSON only.\n\n"
              f"Reference notes about {place} (may be partial):\n{wiki[:1800]}")
    raw = gemini_text(prompt, want_json=True)
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            data = data.get("questions") or data.get("quiz") or next((v for v in data.values() if isinstance(v, list)), None)
        out = []
        for q in (data or [])[:6]:
            ch = [str(x) for x in (q.get("choices") or [])][:4]
            ans = int(q.get("answer", 0))
            if len(ch) == 4 and q.get("q") and 0 <= ans <= 3:
                out.append({"q": str(q["q"]), "choices": ch, "answer": ans, "fact": str(q.get("fact", ""))})
        return out[:5] if len(out) >= 3 else None
    except Exception:
        return None

def generate_reward(e):
    """The piece of the trip unlocked by completing the quiz: an insider 'secret' of the place."""
    place = (e.get("place") or "").strip()
    if not place:
        return None
    txt = gemini_text(
        f"You are a well-traveled local letting a friend in on a secret about {place}. In 2-3 vivid sentences, share "
        f"ONE genuine hidden gem or insider ritual most tourists miss — a specific spot, a time of day, a small "
        f"tradition — that would make their visit unforgettable. Warm, specific, no preamble, no 'here's a secret'.")
    return (txt or "").strip() or None

def quiz_bundle(c, eid, device=""):
    """Load (or lazily generate) the quiz + reward + this device's progress for an entry."""
    row = c.execute("SELECT content,reward FROM quizzes WHERE entry_id=?", (eid,)).fetchone()
    if not row or not row["content"]:
        e = c.execute("SELECT * FROM entries WHERE id=?", (eid,)).fetchone()
        if not e:
            return None
        qs = generate_quiz(dict(e))
        if not qs:
            return {"questions": None}
        reward = generate_reward(dict(e))
        c.execute("INSERT OR REPLACE INTO quizzes(entry_id,content,reward,created) VALUES(?,?,?,?)",
                  (eid, json.dumps(qs), reward or "", now()))
        c.commit()
        content, reward_txt = qs, (reward or "")
    else:
        content = json.loads(row["content"])
        reward_txt = row["reward"] or ""
    prog = c.execute("SELECT best,total,completed FROM quiz_progress WHERE entry_id=? AND device=?",
                     (eid, device or "")).fetchone()
    pg = dict(prog) if prog else {"best": 0, "total": len(content), "completed": 0}
    return {"questions": content, "reward": reward_txt if pg.get("completed") else None,
            "locked_reward": bool(reward_txt), "progress": pg}

def section_payload(c, eid, kind):
    """Active content + full version history for one (entry, kind)."""
    rows = [dict(r) for r in c.execute(
        "SELECT id,content,active,created FROM ai_sections WHERE entry_id=? AND kind=? ORDER BY id DESC",
        (eid, kind)).fetchall()]
    if not rows:
        return None
    active = next((r for r in rows if r["active"]), rows[0])
    return {"active_id": active["id"], "content": active["content"],
            "versions": [{"id": r["id"], "created": r["created"], "content": r["content"],
                          "active": r["active"]} for r in rows]}

# ---- front-end -------------------------------------------------------------

PAGE = r'''<!doctype html><html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<meta name="theme-color" content="#0e0f13">
<link rel="manifest" href="__BASE__/manifest.webmanifest">
<link rel="apple-touch-icon" href="__BASE__/icon-192.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>Trip Sync</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@600;700;800&family=Newsreader:ital,opsz@0,6..72;1,6..72&display=swap" rel="stylesheet">
<style>
:root{
 --bg:#0b0c11;--bg2:#101119;
 --panel:rgba(22,24,32,.78);--panel2:rgba(33,35,47,.62);--panel-solid:#171922;
 --line:rgba(255,255,255,.085);--line2:#2a2c38;
 --text:#f5f4f8;--muted:#9a9cb0;
 --accent:#8b7cf6;--accent2:#6a4df0;--accent-soft:rgba(139,124,246,.16);
 --aurora:#58c7d8;--aurora2:#7d7cf0;--gold:#f5c977;--good:#5ecb8f;--pink:#ec74b4;
 --grad:linear-gradient(135deg,var(--accent),var(--accent2));
 --grad-cool:linear-gradient(135deg,var(--aurora),var(--aurora2));
 --r:18px;--r-sm:12px;
 --shadow:0 12px 36px rgba(0,0,0,.5);
 --glow:0 10px 30px -8px rgba(124,108,240,.55);
 --font:'Inter',-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
 --display:'Plus Jakarta Sans','Inter',sans-serif;
 --serif:'Newsreader',Georgia,'Times New Roman',serif}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
button{-webkit-tap-highlight-color:transparent}
@keyframes appin{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.fadein{animation:appin .22s cubic-bezier(.22,.61,.36,1)}
svg.ic{width:1.15em;height:1.15em;vertical-align:-.18em;flex:none;display:inline-block;stroke-width:2}
html,body{height:100%}
body{margin:0;color:var(--text);height:100vh;height:100dvh;overflow:hidden;display:flex;flex-direction:column;
font:15px/1.55 var(--font);-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;
overscroll-behavior:none;
background:
 radial-gradient(1150px 700px at 80% -12%, rgba(141,124,246,.17), transparent 58%),
 radial-gradient(950px 640px at 4% 108%, rgba(88,199,216,.11), transparent 56%),
 radial-gradient(760px 560px at 52% 46%, rgba(125,124,240,.055), transparent 70%),
 var(--bg);
background-attachment:fixed}
/* subtle starfield over the ambient aurora — pure CSS, fixed, very low-key */
body::before{content:"";position:fixed;inset:0;z-index:0;pointer-events:none;opacity:.5;
 background-image:
  radial-gradient(1.4px 1.4px at 18% 28%, rgba(255,255,255,.55), transparent),
  radial-gradient(1.2px 1.2px at 72% 16%, rgba(255,255,255,.4), transparent),
  radial-gradient(1.3px 1.3px at 44% 66%, rgba(255,255,255,.35), transparent),
  radial-gradient(1.1px 1.1px at 88% 54%, rgba(255,255,255,.4), transparent),
  radial-gradient(1.2px 1.2px at 28% 84%, rgba(255,255,255,.3), transparent),
  radial-gradient(1.3px 1.3px at 62% 92%, rgba(255,255,255,.33), transparent),
  radial-gradient(1.1px 1.1px at 8% 60%, rgba(255,255,255,.3), transparent);
 background-repeat:repeat;background-size:420px 420px}
header#topbar,main,nav.tabs{position:relative;z-index:1}
a{color:var(--accent)}
h2,.tabhead h2,.card h2,.placecard .ttl,.swipe-top .ttl,.entry h3{font-family:var(--display);letter-spacing:-.02em}
::selection{background:var(--accent-soft)}
/* ---- the top container: brand row + current-trip selector + tabs, one sticky unit ---- */
header#topbar{position:sticky;top:0;z-index:20;padding:calc(env(safe-area-inset-top,0) + 12px) 14px 11px;
background:linear-gradient(180deg,rgba(11,12,17,.9),rgba(11,12,17,.68));-webkit-backdrop-filter:saturate(1.5) blur(16px);backdrop-filter:saturate(1.5) blur(16px);border-bottom:1px solid var(--line)}
.brandrow{display:flex;align-items:center;gap:10px;padding:0 2px 10px}
/* brand + trip selector share one row */
.headrow{display:flex;align-items:center;gap:10px}
.headrow h1{flex:none;font-size:17px}
.headrow .tripselwrap{flex:1;min-width:0}
.headrow .tripsel{padding:7px 10px}
.headrow .tripsel .tcover{width:32px;height:32px}
.headrow .tripsel .nm{font-size:14px}
.brandrow .logo{width:30px;height:30px;display:block;filter:drop-shadow(0 2px 5px rgba(0,0,0,.4))}
h1{margin:0;font-size:20px;font-weight:800;letter-spacing:-.03em;flex:1;font-family:var(--display)}
h1 span{background:linear-gradient(90deg,var(--accent),var(--accent2));-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
.back{background:var(--panel2);border:1px solid var(--line);color:var(--text);border-radius:10px;
padding:7px 11px;font-size:13px;font-weight:700;cursor:pointer}
/* current-trip selector — the home's focus, full width at the top */
.tripsel{display:flex;align-items:center;gap:11px;width:100%;background:var(--panel2);border:1px solid var(--line);
color:var(--text);border-radius:14px;padding:9px 12px;cursor:pointer;text-align:left}
.tripsel:active{border-color:var(--accent)}
.tripsel .tcover{width:40px;height:40px;border-radius:10px;flex-shrink:0;overflow:hidden;background:var(--panel);
display:flex;align-items:center;justify-content:center;font-size:20px;border:1px solid var(--line)}
.tripsel .tcover img{width:100%;height:100%;object-fit:cover;display:block}
.tripsel .tinfo{flex:1;min-width:0;display:flex;flex-direction:column;line-height:1.28}
.tripsel .nm{font-size:15px;font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tripsel .dt{font-size:11.5px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tripsel .cr{color:var(--muted);font-size:16px;flex-shrink:0;font-weight:700;transition:transform .2s ease}
.tripsel.open .cr{transform:rotate(180deg)}
/* trip selector dropdown (natural, anchored under the selector — not a bottom sheet) */
.tripselwrap{position:relative}
.tripdd{position:absolute;left:0;right:0;top:calc(100% + 6px);z-index:40;background:var(--panel);border:1px solid var(--line);
border-radius:14px;box-shadow:0 14px 34px rgba(0,0,0,.55);max-height:68vh;overflow-y:auto;-webkit-overflow-scrolling:touch;padding:8px;animation:appin .16s ease}
.tripdd .triprow{margin-bottom:6px}
/* place cards (single column, big cover) */
.placecard{position:relative;border:1px solid var(--line);border-radius:20px;overflow:hidden;margin-bottom:15px;background:var(--panel);box-shadow:var(--shadow);
-webkit-backdrop-filter:blur(12px) saturate(1.3);backdrop-filter:blur(12px) saturate(1.3);transition:transform .18s cubic-bezier(.22,.61,.36,1),box-shadow .18s ease,border-color .18s ease}
.placecard:active{transform:scale(.985);border-color:rgba(139,124,246,.3);box-shadow:0 16px 42px -10px rgba(0,0,0,.6)}
.placecard .cov{width:100%;aspect-ratio:16/10;background:var(--panel);display:flex;align-items:center;justify-content:center;cursor:pointer}
.placecard .cov img{width:100%;height:100%;object-fit:cover;display:block}
.placecard .cov .novc{color:var(--muted)}
.placecard .editcov{position:absolute;top:10px;right:10px;z-index:2;display:flex;align-items:center;gap:5px;background:rgba(8,6,4,.68);
-webkit-backdrop-filter:blur(4px);backdrop-filter:blur(4px);border:1px solid rgba(255,255,255,.22);color:#fff;border-radius:10px;padding:6px 10px;font-size:12px;font-weight:700;cursor:pointer}
.placecard .body{padding:12px 14px;cursor:pointer}
.placecard .ttl{font-size:18px;font-weight:800;display:flex;align-items:center;gap:8px;letter-spacing:-.01em}
.placecard .ttl .go{color:var(--muted);font-size:24px;font-weight:300}
/* reversed, dashed "add a place" */
.addnew{background:transparent;border:2px dashed var(--line);color:var(--accent);font-weight:800;width:100%;margin-top:4px}
.addnew:active{border-color:var(--accent);background:var(--accent-soft)}
/* cover picker grid */
.covgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px}
.covpick{aspect-ratio:1;border-radius:10px;overflow:hidden;border:2px solid var(--line);cursor:pointer}
.covpick.on{border-color:var(--accent)}
.covpick img{width:100%;height:100%;object-fit:cover;display:block}
/* tabs — fixed bottom navigation bar (iOS-style, icon over label) */
/* floating capsule nav (Lumen-style) — centered, glassy, with an active pill */
nav.tabs{position:fixed;left:50%;transform:translateX(-50%);bottom:calc(env(safe-area-inset-bottom,0) + 13px);
z-index:30;display:flex;gap:2px;width:min(520px,calc(100% - 22px));
background:linear-gradient(180deg,rgba(28,30,40,.82),rgba(16,17,25,.86));
-webkit-backdrop-filter:saturate(1.5) blur(18px);backdrop-filter:saturate(1.5) blur(18px);
border:1px solid var(--line);border-radius:22px;padding:6px;
box-shadow:0 16px 40px -8px rgba(0,0,0,.6),inset 0 1px 0 rgba(255,255,255,.06)}
nav.tabs .tab.on svg.ic{filter:drop-shadow(0 2px 9px rgba(139,124,246,.6))}
nav.tabs .tab{flex:1;min-width:0;display:flex;flex-direction:column;align-items:center;gap:3px;padding:8px 2px;
border:0;background:transparent;color:var(--muted);font-size:10px;font-weight:700;cursor:pointer;border-radius:15px;
transition:color .18s ease,background .18s ease}
nav.tabs .tab svg.ic{width:21px;height:21px}
nav.tabs .tab.on{color:var(--accent);background:linear-gradient(180deg,var(--accent-soft),rgba(139,124,246,.05));
box-shadow:inset 0 0 0 1px rgba(139,124,246,.22)}
nav.tabs .tab:active{transform:scale(.94)}
.triprow{display:flex;align-items:center;gap:10px;cursor:pointer;padding:11px 12px;border:1px solid var(--line);
border-radius:12px;background:var(--panel2);margin-bottom:8px}
.triprow.cur{border-color:var(--accent)}
.triprow .cv{width:44px;height:44px;border-radius:9px;object-fit:cover;background:var(--panel);display:flex;
align-items:center;justify-content:center;font-size:20px;flex-shrink:0;border:1px solid var(--line)}
.tabhead{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:6px}
.tabhead h2{margin:0;font-size:17px}
main{flex:1 1 auto;min-height:0;overflow-y:auto;overscroll-behavior:contain;width:100%;max-width:860px;margin:0 auto;padding:18px 15px calc(104px + env(safe-area-inset-bottom,0));-webkit-overflow-scrolling:touch}
.btn{background:var(--grad);color:#fff;border:0;position:relative;overflow:hidden;
border-radius:14px;padding:14px 16px;font-weight:800;font-size:14.5px;cursor:pointer;width:100%;font-family:var(--display);
box-shadow:var(--glow);transition:transform .12s ease,box-shadow .12s ease,filter .12s ease}
.btn::before{content:"";position:absolute;inset:0 0 auto;height:45%;
background:linear-gradient(180deg,rgba(255,255,255,.28),transparent);pointer-events:none}
.btn:hover{filter:brightness(1.04)}
.btn:active{transform:translateY(1px) scale(.995);box-shadow:0 4px 12px rgba(124,108,240,.3)}
.btn.ghost{background:var(--panel2);color:var(--text);border:1px solid var(--line);box-shadow:none}
.btn.ghost:active{background:var(--panel);box-shadow:none}
.btn.sm{padding:9px 13px;font-size:13px;width:auto;box-shadow:0 3px 10px rgba(124,108,240,.22)}
.btn.sm.ghost{box-shadow:none}
/* ---- backlog swipe-sorter ---- */
.swipe-ov{position:fixed;inset:0;background:#07090d;z-index:80;display:flex;flex-direction:column}
.swipe-top{display:flex;align-items:center;gap:10px;padding:calc(env(safe-area-inset-top) + 12px) 16px 8px}
.swipe-top .ttl{font-weight:800}
.swipe-top .cnt{margin-left:auto;color:var(--muted);font-size:13px}
.swipe-stage{flex:1;position:relative;overflow:hidden}
.swipe-card{position:absolute;inset:14px;border-radius:18px;overflow:hidden;background:#0f0c09;border:1px solid var(--line);box-shadow:0 12px 44px rgba(0,0,0,.55);display:flex;flex-direction:column;touch-action:pan-y;will-change:transform}
.swipe-card img{width:100%;flex:1;object-fit:contain;background:#07090d;min-height:0}
.swipe-card .cardmeta{padding:10px 14px;background:rgba(8,6,4,.92)}
.swipe-card .cap{font-size:13px;color:var(--text);margin-bottom:6px;line-height:1.35}
.swipe-card .chips{display:flex;gap:6px;flex-wrap:wrap}
.swipe-card .chips .chip{font-size:11px;background:var(--panel2);border:1px solid var(--line);color:var(--muted);border-radius:8px;padding:3px 7px}
.swipe-stamp{position:absolute;top:26px;padding:5px 12px;border-radius:10px;font-weight:900;font-size:19px;border:3px solid;opacity:0;pointer-events:none}
.swipe-stamp.yes{right:26px;color:#22c55e;border-color:#22c55e;transform:rotate(12deg)}
.swipe-stamp.no{left:26px;color:#f0768a;border-color:#f0768a;transform:rotate(-12deg)}
.swipe-places{display:flex;gap:7px;overflow-x:auto;padding:8px 14px}
.swipe-places .pl{flex:0 0 auto;border:1px solid var(--line);background:var(--panel2);color:var(--text);border-radius:999px;padding:8px 13px;font-size:13px;font-weight:700;white-space:nowrap}
.swipe-places .pl.sug{border-color:var(--accent);background:rgba(224,122,63,.18)}
.swipe-actions{display:flex;gap:9px;padding:8px 14px calc(env(safe-area-inset-bottom) + 14px)}
.swipe-actions button{flex:1;border:0;border-radius:12px;padding:13px;font-weight:800;font-size:14px}
.sw-skip{background:var(--panel2);color:var(--text);border:1px solid var(--line)!important}
.sw-del{background:rgba(240,118,138,.14);color:#f0768a;border:1px solid rgba(240,118,138,.4)!important}
.sw-acc{background:linear-gradient(90deg,var(--accent),var(--accent2));color:#241403}
.sw-acc:disabled{opacity:.5}
.swipe-empty{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;color:var(--muted);text-align:center;padding:30px}
.btn:disabled{opacity:.55}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:17px;margin-bottom:13px;box-shadow:var(--shadow);
-webkit-backdrop-filter:blur(14px) saturate(1.3);backdrop-filter:blur(14px) saturate(1.3);position:relative}
.card::before{content:"";position:absolute;inset:0 0 auto;height:1px;border-radius:var(--r) var(--r) 0 0;
background:linear-gradient(90deg,transparent,rgba(255,255,255,.14),transparent);pointer-events:none}
.card h2{margin:0 0 3px;font-size:17px}
label{display:block;font-size:12px;color:var(--muted);font-weight:700;margin:11px 0 5px;text-transform:uppercase;letter-spacing:.04em}
input,textarea,select{width:100%;background:var(--panel2);border:1px solid var(--line);color:var(--text);
border-radius:12px;padding:12px 13px;font:inherit;outline:none;transition:border-color .15s,box-shadow .15s}
input:focus,textarea:focus,select:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
textarea{resize:vertical;min-height:70px}
.row{display:flex;gap:10px}.row>*{flex:1}
.muted{color:var(--muted)}.sm{font-size:12.5px}
.empty{color:var(--muted);text-align:center;padding:48px 10px}
/* first-run hero */
.hero{text-align:center;padding:34px 16px 20px;max-width:440px;margin:0 auto}
.hero-orb{width:108px;height:108px;margin:0 auto 22px;border-radius:50%;display:grid;place-items:center;color:var(--accent);
 background:radial-gradient(circle at 50% 38%,rgba(139,124,246,.28),rgba(106,77,240,.06) 62%,transparent 72%);
 box-shadow:0 0 0 1px rgba(139,124,246,.18) inset,0 18px 50px -14px rgba(124,108,240,.6);position:relative;animation:orbfloat 5s ease-in-out infinite}
.hero-orb::after{content:"";position:absolute;inset:-14px;border-radius:50%;border:1px solid rgba(139,124,246,.14)}
.hero-orb svg.ic{filter:drop-shadow(0 3px 12px rgba(139,124,246,.6))}
@keyframes orbfloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
.hero-ttl{font-family:var(--display);font-size:30px;line-height:1.12;font-weight:800;letter-spacing:-.03em;margin:0 0 12px}
.hero-ttl span{background:linear-gradient(100deg,var(--accent),var(--gold) 55%,var(--accent2));-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
.hero-sub{color:var(--muted);font-size:14.5px;line-height:1.6;margin:0 auto 22px;max-width:360px}
.hero-feats{display:flex;justify-content:center;gap:8px;margin-bottom:26px;flex-wrap:wrap}
.hero-feat{display:inline-flex;align-items:center;gap:6px;padding:8px 13px;border-radius:999px;font-size:12.5px;font-weight:700;
 background:var(--panel2);border:1px solid var(--line);color:var(--text);-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px)}
.hero-feat svg.ic{color:var(--accent)}
.hero-cta{max-width:320px;margin:0 auto;display:flex;align-items:center;justify-content:center;gap:8px}
.trip{display:flex;gap:13px;align-items:center;cursor:pointer}
.trip .cv{width:62px;height:62px;border-radius:12px;object-fit:cover;background:var(--panel2);flex-shrink:0;
display:flex;align-items:center;justify-content:center;font-size:26px;border:1px solid var(--line)}
.trip .meta{flex:1;min-width:0}
.trip .meta b{font-size:16px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px}
.chip{background:var(--panel2);border:1px solid var(--line);border-radius:999px;padding:3px 10px;font-size:12px;color:var(--muted)}
.entry h3{margin:0 0 2px;font-size:16px}
.entry .when{color:var(--muted);font-size:12.5px}
.entry .field{margin-top:9px}
.entry .field .k{font-size:11px;color:var(--accent);font-weight:800;text-transform:uppercase;letter-spacing:.05em}
.entry pre{white-space:pre-wrap;word-wrap:break-word;font-family:var(--serif);font-size:16px;line-height:1.62;margin:4px 0 0;color:#e7e8ee}
.briefing{background:var(--panel2);border:1px solid var(--line);border-left:3px solid var(--accent);
border-radius:10px;padding:11px 13px;margin-top:10px;white-space:pre-wrap}
/* ---- trip chat ---- */
.chatlog{display:flex;flex-direction:column;gap:9px;padding-bottom:76px;min-height:42vh}
.cmsg{max-width:85%;padding:9px 13px;border-radius:15px;font-size:14.5px;line-height:1.52;white-space:pre-wrap;word-wrap:break-word;overflow-wrap:anywhere}
.cmsg.user{align-self:flex-end;background:var(--accent);color:#1a1205;border-bottom-right-radius:5px;font-weight:500}
.cmsg.assistant{align-self:flex-start;background:var(--panel2);border:1px solid var(--line);border-bottom-left-radius:5px;color:#e7ded1}
.cmsg.assistant svg.ic{color:var(--accent);vertical-align:-.18em;margin-right:3px}
.chatbar{position:fixed;left:0;right:0;bottom:calc(env(safe-area-inset-bottom,0) + 84px);z-index:25;
background:rgba(14,15,19,.95);-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);border-top:1px solid var(--line);padding:9px 14px}
.chatbar .inner{max-width:860px;margin:0 auto;display:flex;gap:8px;align-items:flex-end}
.chatbar textarea{flex:1;resize:none;max-height:120px;background:var(--panel2);border:1px solid var(--line);color:var(--text);
border-radius:14px;padding:10px 12px;font:inherit;font-size:15px;line-height:1.4}
.chatbar .send{flex:none;width:42px;height:42px;padding:0;border-radius:50%;display:grid;place-items:center}
.chatbar .mic{flex:none;width:42px;height:42px;padding:0;border-radius:50%;display:grid;place-items:center;background:var(--panel2);border:1px solid var(--line);color:var(--text)}
.chatbar .mic.rec{background:#e4674f;color:#fff;border-color:#e4674f;animation:micpulse 1.1s infinite}
@keyframes micpulse{0%,100%{box-shadow:0 0 0 0 rgba(228,103,79,.55)}50%{box-shadow:0 0 0 9px rgba(228,103,79,0)}}
.chatempty{text-align:center;color:var(--muted);padding:34px 14px}
.chatempty svg.ic{color:var(--accent);opacity:.85}
.chatempty p{max-width:320px;margin:12px auto 0}
.chatempty .chips{justify-content:center;margin-top:16px}
.chatempty .chip{cursor:pointer}
.notebook{background:var(--panel2);border:1px solid var(--line);border-radius:14px;margin:4px 0 12px;overflow:hidden}
.nb-head{display:flex;align-items:center;justify-content:space-between;padding:11px 13px;cursor:pointer;font-weight:700;font-size:14px}
.nb-head svg.ic{color:var(--accent);vertical-align:-.18em;margin-right:5px}
.nb-count{display:inline-block;min-width:18px;text-align:center;background:var(--accent);color:#1a1205;border-radius:999px;font-size:11px;padding:1px 6px;margin-left:4px}
.nb-tog{color:var(--muted)}
.nb-body{padding:2px 13px 12px;border-top:1px solid var(--line)}
.nb-cat{margin-top:10px}
.nb-cat-h{font-family:var(--display);font-size:13px;font-weight:700;color:var(--accent);text-transform:uppercase;letter-spacing:.04em}
.nb-items{list-style:none;margin:5px 0 0;padding:0;display:flex;flex-direction:column;gap:4px}
.nb-items li{display:flex;gap:8px;align-items:flex-start;background:var(--bg);border:1px solid var(--line);border-radius:9px;padding:7px 9px;font-size:13.5px;line-height:1.45}
.nb-items li>span{flex:1;min-width:0}
.nb-place{display:inline-block;color:var(--muted);font-size:11.5px;margin-left:4px}
.nb-place svg.ic{color:var(--accent);vertical-align:-.1em}
.nb-del{flex:none;background:0;border:0;color:var(--muted);font-size:18px;line-height:1;cursor:pointer;padding:0 2px}
.nb-del:hover{color:#e4674f}
.nb-form{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
.nb-form input{flex:1;min-width:120px;background:var(--bg);border:1px solid var(--line);color:var(--text);border-radius:9px;padding:8px 10px;font:inherit;font-size:14px}
.nb-addbtn{margin-top:10px;background:0;border:1px dashed var(--line);color:var(--muted);border-radius:9px;padding:7px 12px;font:inherit;font-size:13px;font-weight:700;cursor:pointer;width:100%}
.nb-addbtn:hover{color:var(--accent);border-color:var(--accent)}
.dropzone{position:fixed;inset:0;z-index:300;display:none;align-items:center;justify-content:center;background:rgba(10,11,15,.82);-webkit-backdrop-filter:blur(5px);backdrop-filter:blur(5px);pointer-events:none}
.dropzone.on{display:flex;animation:dzfade .12s ease}
@keyframes dzfade{from{opacity:0}to{opacity:1}}
.dropzone .dz-inner{border:2.5px dashed var(--accent);border-radius:22px;padding:42px 48px;text-align:center;background:rgba(24,22,34,.7)}
.dropzone .dz-inner svg.ic{color:var(--accent)}
.dropzone .dz-t{font-family:var(--display);font-size:22px;margin-top:12px}
.dropzone .dz-s{color:var(--muted);font-size:13px;margin-top:4px}
/* ---- collaborative trips: crew bar, avatars ---- */
.mavatar{display:inline-grid;place-items:center;border-radius:50%;color:#1a1205;font-weight:800;border:2px solid var(--bg,#14130f);box-shadow:0 1px 3px rgba(0,0,0,.4);vertical-align:middle;flex:none;line-height:1}
.crewbar{display:flex;align-items:center;gap:10px;background:var(--panel2);border:1px solid var(--line);border-radius:13px;padding:8px 10px;margin:2px 0 12px;cursor:pointer}
.crew-av{display:flex;flex-direction:row-reverse}
.crew-av .mavatar{margin-left:-9px}
.crew-lbl{flex:1;min-width:0;font-size:13.5px;font-weight:700;color:var(--text)}
.crew-share{flex:none;padding:7px 12px !important}
/* ---- premium invite sheet ---- */
.iv{margin:-4px -2px 0}
.iv-hero{position:relative;text-align:center;padding:10px 6px 4px;overflow:hidden}
.iv-glow{position:absolute;left:50%;top:-30px;width:280px;height:200px;transform:translateX(-50%);pointer-events:none;
 background:radial-gradient(60% 60% at 50% 40%,rgba(139,124,246,.45),rgba(88,199,216,.18) 55%,transparent 72%);filter:blur(10px);opacity:.9}
.iv-cluster{position:relative;display:flex;justify-content:center;align-items:center;margin:6px 0 14px;z-index:1}
.iv-face{position:relative;border-radius:50%;box-shadow:0 4px 14px -4px rgba(0,0,0,.6)}
.iv-face .mavatar{border:2.5px solid #14131c}
.iv-more{display:grid;place-items:center;width:44px;height:44px;border-radius:50%;background:linear-gradient(135deg,#2a2540,#1c1930);
 border:2.5px solid #14131c;color:var(--text);font-weight:800;font-size:13px}
.iv-title{font-family:var(--display);font-size:23px;letter-spacing:-.02em;margin:0 0 6px;
 background:linear-gradient(120deg,#fff,#cfc9f5 60%,var(--aurora));-webkit-background-clip:text;background-clip:text;color:transparent}
.iv-sub{color:var(--muted);font-size:13.5px;line-height:1.5;margin:0 auto;max-width:300px}
.iv-sub b{color:var(--text)}
.iv-qr{display:flex;flex-direction:column;align-items:center;gap:7px;margin:16px auto 4px;width:max-content}
.iv-qr img{width:150px;height:150px;border-radius:16px;padding:12px;background:var(--panel-solid);
 border:1px solid var(--line);box-shadow:0 14px 40px -16px rgba(124,108,240,.5),0 0 0 1px rgba(255,255,255,.03) inset}
.iv-cta{display:flex;flex-direction:column;gap:9px;margin:16px 0 4px}
.iv-primary{box-shadow:var(--glow)}
.iv-copy{display:flex;align-items:center;gap:10px;justify-content:space-between;text-align:left;padding:11px 12px 11px 15px !important}
.iv-link{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12.5px;color:var(--muted);font-weight:600}
.iv-copybtn{flex:none;font-weight:800;color:var(--accent);font-size:13px;letter-spacing:.02em}
.iv-chans{display:flex;gap:8px;margin:14px 0 2px}
.iv-chan{flex:1;display:flex;flex-direction:column;align-items:center;gap:5px;padding:12px 4px;border-radius:14px;
 background:var(--panel2);border:1px solid var(--line);color:var(--text);text-decoration:none;font-size:11.5px;font-weight:700;
 transition:transform .15s ease,border-color .15s ease,background .15s ease}
.iv-chan svg.ic{width:19px;height:19px;color:var(--accent)}
.iv-chan:active{transform:scale(.95);border-color:var(--accent);background:var(--accent-soft)}
.iv-crew{margin-top:18px;border-top:1px solid var(--line);padding-top:14px}
.iv-crewhd{text-transform:uppercase;letter-spacing:.1em;font-size:11px;font-weight:800;color:var(--muted);margin-bottom:8px}
.iv-row{display:flex;align-items:center;gap:10px;padding:7px 2px}
.iv-dot{flex:none;width:8px;height:8px;border-radius:50%;background:var(--good);box-shadow:0 0 8px var(--good)}
/* ---- plan & book deep-link cards ---- */
.book-grid{display:grid;gap:9px;margin-top:4px}
.book-card{display:flex;align-items:center;gap:12px;padding:13px 14px;border-radius:15px;text-decoration:none;color:var(--text);
 background:linear-gradient(135deg,rgba(139,124,246,.10),rgba(88,199,216,.05)),var(--panel2);
 border:1px solid var(--line);transition:transform .15s ease,border-color .15s ease,box-shadow .2s ease}
.book-card:active{transform:scale(.985);border-color:var(--accent);box-shadow:0 10px 26px -14px rgba(124,108,240,.7)}
.book-ic{flex:none;width:40px;height:40px;display:grid;place-items:center;border-radius:12px;color:var(--accent);
 background:radial-gradient(circle at 50% 35%,rgba(139,124,246,.3),rgba(106,77,240,.08));border:1px solid rgba(139,124,246,.22)}
.book-ic svg.ic{width:20px;height:20px}
.book-tx{flex:1;min-width:0;display:flex;flex-direction:column;gap:1px}
.book-tx b{font-size:15px;font-weight:700}
.book-prov{flex:none;font-size:11.5px;font-weight:700;color:var(--muted);white-space:nowrap}
.book-note{margin-top:10px;display:flex;align-items:center;gap:6px;opacity:.85}
.book-note svg.ic{color:var(--gold)}
/* ---- place quiz game + reward unlock ---- */
.game-cta{display:flex;align-items:center;gap:13px;padding:15px 15px;border-radius:17px;cursor:pointer;
 background:linear-gradient(135deg,rgba(139,124,246,.16),rgba(88,199,216,.07)),var(--panel);
 border:1px solid rgba(139,124,246,.26);box-shadow:0 14px 40px -20px rgba(124,108,240,.7);
 transition:transform .15s ease,box-shadow .2s ease;position:relative;overflow:hidden}
.game-cta:active{transform:scale(.99)}
.game-orb{position:relative;flex:none;width:50px;height:50px;display:grid;place-items:center;border-radius:50%;color:#fff;
 background:radial-gradient(circle at 50% 35%,var(--accent),var(--accent2));box-shadow:0 0 22px -4px var(--accent);animation:gpulse 3.2s ease-in-out infinite}
.game-orb svg.ic{width:23px;height:23px;opacity:.95}
.game-q{position:absolute;right:-3px;bottom:-3px;width:20px;height:20px;border-radius:50%;background:var(--gold);color:#2a1a05;
 font-weight:900;font-size:13px;display:grid;place-items:center;border:2px solid var(--bg)}
@keyframes gpulse{0%,100%{box-shadow:0 0 20px -6px var(--accent)}50%{box-shadow:0 0 30px 2px var(--accent)}}
.game-tx{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px}
.game-tx b{font-size:15.5px;font-family:var(--display);letter-spacing:-.01em}
.game-play{flex:none;align-self:center}
/* reward / unlocked secret */
.reward-card{border-radius:17px;padding:16px;background:linear-gradient(150deg,rgba(245,201,119,.12),rgba(139,124,246,.08)),var(--panel);
 border:1px solid rgba(245,201,119,.3);position:relative;overflow:hidden}
.reward-card.big{margin:14px 0 18px;text-align:left}
.reward-stamp{position:absolute;top:12px;right:12px;width:36px;height:36px;display:grid;place-items:center;border-radius:50%;
 color:var(--gold);border:1.5px dashed var(--gold);transform:rotate(-12deg);opacity:.9}
.reward-stamp svg.ic{width:18px;height:18px}
.reward-h{font-family:var(--display);font-size:16px;letter-spacing:-.01em;margin-bottom:6px;
 background:linear-gradient(120deg,#ffe9b8,var(--gold) 55%,var(--accent));-webkit-background-clip:text;background-clip:text;color:transparent;padding-right:40px}
.reward-b{color:var(--text);font-family:var(--serif);font-style:italic;font-size:15px;line-height:1.5}
.reward-meta{display:flex;align-items:center;gap:10px;margin-top:12px}
.stars{color:var(--gold);letter-spacing:2px;font-size:14px}
/* quiz player (inside the bottom sheet) */
.quiz{min-height:40px}
.q-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.q-dots{display:flex;gap:6px}
.qd{width:22px;height:5px;border-radius:999px;background:var(--line2);transition:background .2s}
.qd.done{background:var(--accent)}
.qd.cur{background:var(--accent);box-shadow:0 0 8px var(--accent)}
.q-q{font-family:var(--display);font-size:19px;line-height:1.3;letter-spacing:-.01em;margin-bottom:16px}
.q-choices{display:flex;flex-direction:column;gap:9px}
.q-ch{text-align:left;padding:13px 15px;border-radius:13px;background:var(--panel2);border:1px solid var(--line);
 color:var(--text);font:inherit;font-size:15px;font-weight:600;cursor:pointer;transition:transform .12s ease,border-color .15s ease,background .15s ease}
.q-ch:active{transform:scale(.99)}
.q-ch.locked{pointer-events:none}
.q-ch.right{border-color:var(--good);background:linear-gradient(135deg,rgba(94,203,143,.22),rgba(94,203,143,.08));color:#dff6e8}
.q-ch.wrong{border-color:#e06a8a;background:linear-gradient(135deg,rgba(224,106,138,.2),rgba(224,106,138,.06));color:#f6dfe6}
.q-fact{max-height:0;opacity:0;overflow:hidden;transition:max-height .35s ease,opacity .35s ease,margin .3s ease}
.q-fact.show{max-height:220px;opacity:1;margin-top:14px}
.q-verdict{font-weight:800;font-size:13px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:5px}
.q-verdict.ok{color:var(--good)}.q-verdict.no{color:#e06a8a}
.q-factt{color:var(--muted);font-size:14px;line-height:1.5}
.q-next{margin-top:18px}
.q-reveal{text-align:center}
.q-reveal.show .reveal-stamp{animation:stampin .55s cubic-bezier(.2,1.4,.4,1) both}
.reveal-stamp{width:76px;height:76px;margin:6px auto 10px;display:grid;place-items:center;border-radius:50%;color:var(--gold);
 border:2.5px dashed var(--gold);transform:rotate(-10deg);box-shadow:0 0 40px -6px var(--gold)}
.reveal-stamp svg.ic{width:34px;height:34px}
@keyframes stampin{0%{transform:scale(2.4) rotate(16deg);opacity:0}60%{opacity:1}100%{transform:scale(1) rotate(-10deg);opacity:1}}
.reveal-title{font-family:var(--display);font-size:24px;letter-spacing:-.02em;
 background:linear-gradient(120deg,#fff,#cfc9f5 55%,var(--gold));-webkit-background-clip:text;background-clip:text;color:transparent}
.reveal-score{color:var(--muted);font-size:13.5px;margin:4px 0 2px}.reveal-score b{color:var(--gold)}
.pthumb{position:relative}
.pthumb-av{position:absolute;top:5px;right:5px;z-index:2}
.gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(78px,1fr));gap:7px;margin-top:10px}
.gallery img{width:100%;aspect-ratio:1;object-fit:cover;border-radius:9px;border:1px solid var(--line)}
.filters{display:flex;gap:6px;flex-wrap:wrap;margin:4px 0 10px}
.fil{padding:5px 11px;border:1px solid var(--line);border-radius:999px;background:var(--panel2);color:var(--muted);
font-size:12px;font-weight:700;cursor:pointer}
.fil.on{color:var(--accent);border-color:var(--accent);background:var(--accent-soft)}
.pgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:8px}
.pthumb{position:relative;border-radius:10px;overflow:hidden;border:1px solid var(--line);cursor:pointer;background:var(--panel2)}
.pthumb img{width:100%;aspect-ratio:1;object-fit:cover;display:block}
.pthumb .lab{position:absolute;left:0;right:0;bottom:0;padding:10px 6px 4px;font-size:10px;font-weight:700;color:#fff;
background:linear-gradient(0deg,rgba(0,0,0,.72),transparent)}
.lightbox{position:fixed;inset:0;background:rgba(0,0,0,.9);z-index:70;display:flex;flex-direction:column;
align-items:center;justify-content:center;padding:20px}
.lightbox img{max-width:100%;max-height:68vh;border-radius:12px;border:1px solid var(--line)}
.lightbox .info{max-width:560px;margin-top:14px;text-align:center}
.lightbox .cap{font-size:15px;color:var(--text)}
.lightbox .meta{margin-top:7px}
.lightbox .close{position:absolute;top:calc(env(safe-area-inset-top,0) + 14px);right:18px;font-size:26px;color:#fff;cursor:pointer}
#map{height:68vh;width:100%;border-radius:14px;border:1px solid var(--line);background:#12100e;overflow:hidden;position:relative}
.maplibregl-ctrl-attrib{font-size:9px}
#map.full{position:fixed;inset:0;height:100%!important;width:100%;border-radius:0;border:0;z-index:400;margin:0}
.mapfs{position:absolute;top:10px;right:10px;z-index:401;width:38px;height:38px;border-radius:9px;background:rgba(10,8,5,.82);border:1px solid var(--line);color:var(--text);font-size:17px;box-shadow:0 2px 8px rgba(0,0,0,.5);cursor:pointer}
#mapwrap.full .mapfs{position:fixed;top:calc(env(safe-area-inset-top,0) + 10px);right:12px;z-index:500}
.leaflet-popup-content-wrapper,.leaflet-popup-tip{background:#241c15;color:var(--text);border:1px solid var(--line)}
.leaflet-popup-content{margin:10px 12px;font:13px/1.4 inherit}
.leaflet-popup-content img{width:100%;border-radius:8px;margin-bottom:6px}
.leaflet-popup-content a{color:var(--accent2)}
.pin{background:linear-gradient(180deg,var(--accent2),var(--accent2));color:#241403;border:2px solid #fff6;border-radius:50% 50% 50% 0;
width:26px;height:26px;transform:rotate(-45deg);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:12px;box-shadow:0 2px 6px rgba(0,0,0,.5)}
.pin span{transform:rotate(45deg)}
.pin.journ{background:linear-gradient(180deg,#6bbf8a,#3f9e6a);border-color:#fff8;font-size:14px}
.pplace{position:relative;width:54px;height:54px;border-radius:12px;overflow:hidden;border:3px solid var(--accent);
box-shadow:0 3px 10px rgba(0,0,0,.6);background:var(--panel2)}
.pplace img{width:100%;height:100%;object-fit:cover;display:block}
.pplace.totem{border-radius:50%;border-color:var(--accent);box-shadow:0 0 14px rgba(244,162,89,.55),0 2px 8px rgba(0,0,0,.55)}
.pplace.totem img{object-fit:contain;background:#14110f}
.pplace.pjourn{border-color:#6bbf8a}
.pplace .pnum{position:absolute;top:-1px;left:-1px;background:var(--accent);color:#241403;font-weight:800;font-size:11px;
min-width:16px;height:16px;text-align:center;border-radius:0 0 7px 0;line-height:16px;padding:0 3px}
.pplace.pjourn .pnum{background:#6bbf8a}
.pplace .jbadge{position:absolute;bottom:-1px;right:-1px;color:#6bbf8a;background:#241c15;border-radius:7px 0 0 0;padding:1px 2px;line-height:1;display:flex}
.pplace .pcount{position:absolute;bottom:2px;left:3px;background:rgba(0,0,0,.65);color:#fff;font-size:10px;font-weight:700;
border-radius:6px;padding:0 4px;line-height:1.5}
.pmark{width:40px;height:40px;border-radius:9px;border:2px solid var(--accent);overflow:hidden;box-shadow:0 2px 7px rgba(0,0,0,.5);position:relative}
.pmark img{width:100%;height:100%;object-fit:cover}
.pmark.pjourn{border-color:#6bbf8a}
.pmark.inh{border-style:dashed;border-color:#e0b483}
.pmark .jbadge{position:absolute;bottom:-2px;right:-2px;color:#6bbf8a;background:#241c15;border-radius:6px;padding:1px 2px;line-height:1;display:flex}
/* ---- map "radiate" constellation ---- */
.rsat{width:46px;height:46px;border-radius:50%;overflow:hidden;border:2px solid #fff;box-shadow:0 2px 9px rgba(0,0,0,.6);background:var(--panel2);animation:rpop .22s ease}
.rsat img{width:100%;height:100%;object-fit:cover;display:block}
.rsat.ic{display:flex;align-items:center;justify-content:center;font-size:21px;border-color:var(--accent);background:#241c15}
.rsat.col{border-color:var(--accent2,#c98b5e)}
@keyframes rpop{from{transform:scale(.2);opacity:0}to{transform:scale(1);opacity:1}}
/* ---- geolocation-first photo clusters (Apple Photos-style, MapLibre/supercluster) ---- */
.pdot{width:42px;height:42px;border-radius:11px;overflow:hidden;border:2px solid #fff;box-shadow:0 2px 9px rgba(0,0,0,.55);cursor:pointer;background:var(--panel2);animation:rpop .18s ease}
.pdot img{width:100%;height:100%;object-fit:cover;display:block}
.pcl{position:relative;width:56px;height:56px;cursor:pointer;animation:rpop .18s ease}
.pcl .pcl-thumb{width:56px;height:56px;border-radius:15px;overflow:hidden;border:2.5px solid #fff;box-shadow:0 3px 13px rgba(0,0,0,.6);background:var(--panel2)}
.pcl .pcl-thumb img{width:100%;height:100%;object-fit:cover;display:block}
.pcl .pcl-thumb.ph{background:linear-gradient(135deg,var(--accent),var(--accent2))}
.pcl .pcl-n{position:absolute;top:-8px;right:-8px;min-width:23px;height:23px;padding:0 6px;border-radius:12px;
 background:linear-gradient(180deg,var(--accent),var(--accent2));color:#fff;font-weight:800;font-size:12px;
 display:flex;align-items:center;justify-content:center;box-shadow:0 2px 7px rgba(0,0,0,.5);border:1.5px solid rgba(255,255,255,.9)}
.rhubwrap{position:relative;width:0;height:0}
.rhub{position:absolute;left:0;top:0;transform:translate(-50%,calc(-100% - 30px));white-space:nowrap;background:rgba(10,8,5,.86);border:1px solid var(--accent);color:var(--text);font-weight:800;font-size:12px;padding:4px 10px;border-radius:999px;box-shadow:0 2px 8px rgba(0,0,0,.5)}
.rhub.up{transform:translate(-50%,calc(-100% - 50px))}
.rtotem{position:absolute;left:0;top:0;transform:translate(-50%,-50%);width:74px;height:74px;border-radius:50%;overflow:hidden;border:3px solid var(--accent);box-shadow:0 0 20px rgba(244,162,89,.6),0 3px 12px rgba(0,0,0,.65);background:#241c15;animation:rpop .25s ease}
.rtotem img{width:100%;height:100%;object-fit:cover;display:block}
.jexcerpt{margin-top:7px;max-height:140px;overflow:auto;white-space:pre-wrap;font-size:12.5px;line-height:1.5;
border-left:2px solid var(--accent);padding-left:8px;color:#e3dacd}
.jideas{margin-top:6px;font-size:12px;color:var(--muted)}
.collage img{width:100%;border-radius:12px;border:1px solid var(--line);margin-top:8px}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.spinner{display:inline-block;width:15px;height:15px;border:2px solid rgba(255,255,255,.3);
border-top-color:#fff;border-radius:50%;animation:sp .7s linear infinite;vertical-align:-2px;margin-right:6px}
@keyframes sp{to{transform:rotate(360deg)}}
.modal{position:fixed;inset:0;background:rgba(0,0,0,.72);z-index:90;display:flex;align-items:flex-end;justify-content:center;padding:0}
.modal.screen{align-items:stretch;background:transparent}
.screenpane{width:100%;max-width:640px;margin:0 auto;height:100%;overflow-y:auto;-webkit-overflow-scrolling:touch;
overscroll-behavior:contain;background:var(--bg);box-shadow:-8px 0 30px rgba(0,0,0,.45);
transform:translateX(100%);transition:transform .3s cubic-bezier(.22,.61,.36,1);
padding:calc(env(safe-area-inset-top,0) + 14px) 16px calc(env(safe-area-inset-bottom,0) + 28px)}
.modal.screen.in .screenpane{transform:translateX(0)}
.screenback{background:none;border:0;color:var(--accent);font-size:16px;font-weight:800;padding:2px 0 14px;cursor:pointer}
.sheet{background:linear-gradient(180deg,rgba(28,30,40,.92),rgba(18,19,27,.96));border-top-left-radius:22px;border-top-right-radius:22px;width:100%;max-width:560px;
max-height:92vh;overflow:auto;padding:18px 16px calc(24px + env(safe-area-inset-bottom,0));border:1px solid var(--line);
-webkit-backdrop-filter:blur(20px) saturate(1.4);backdrop-filter:blur(20px) saturate(1.4);box-shadow:0 -14px 50px rgba(0,0,0,.55)}
.sheet::before{content:"";display:block;width:38px;height:4px;border-radius:999px;background:var(--line2);margin:-6px auto 12px}
.sheet h2{margin:2px 0 6px}
.seg{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
.seg .opt{flex:1;min-width:84px;text-align:center;padding:9px;border:1px solid var(--line);border-radius:10px;
background:var(--panel2);font-size:12.5px;font-weight:700;cursor:pointer;color:var(--muted)}
.seg .opt.on{color:var(--accent);border-color:var(--accent);background:rgba(244,162,89,.1)}
.pick{display:grid;grid-template-columns:repeat(auto-fill,minmax(66px,1fr));gap:7px;margin-top:8px}
.pick .ph{position:relative;cursor:pointer;border-radius:9px;overflow:hidden;border:2px solid transparent}
.pick .ph img{width:100%;aspect-ratio:1;object-fit:cover;display:block}
.pick .ph.on{border-color:var(--accent)}
.pick .ph.on::after{content:"✓";position:absolute;top:2px;right:4px;color:var(--accent);font-weight:900;
text-shadow:0 1px 3px #000}
.toast{position:fixed;left:50%;bottom:96px;transform:translateX(-50%);background:linear-gradient(180deg,rgba(34,36,48,.92),rgba(20,21,29,.94));border:1px solid var(--line);
color:var(--text);padding:11px 16px;border-radius:13px;z-index:120;font-size:13.5px;max-width:90%;
-webkit-backdrop-filter:blur(16px) saturate(1.4);backdrop-filter:blur(16px) saturate(1.4);box-shadow:0 12px 36px rgba(0,0,0,.55)}
.danger{color:var(--accent2)}
.fab{position:sticky;bottom:16px;margin-top:6px}
hr.sep{border:0;border-top:1px solid var(--line);margin:14px 0}
/* ---- destination list (compact rows, tap to open a place) ---- */
.destrow{display:flex;gap:12px;align-items:center;cursor:pointer;padding:11px;border:1px solid var(--line);
border-radius:14px;background:var(--panel);margin-bottom:10px}
.destrow:active{border-color:var(--accent)}
.destrow .cv{width:56px;height:56px;border-radius:11px;flex-shrink:0;overflow:hidden;background:var(--panel2);
display:flex;align-items:center;justify-content:center;font-size:22px;border:1px solid var(--line)}
.destrow .cv img{width:100%;height:100%;object-fit:cover;display:block}
.destrow .m{flex:1;min-width:0}
.destrow .m b{font-size:16px;display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.destrow .go{color:var(--muted);font-size:24px;flex-shrink:0;font-weight:300}
.ministats{display:flex;gap:6px;margin-top:5px;flex-wrap:wrap}
.ministats .s{font-size:11px;color:var(--muted);background:var(--panel2);border:1px solid var(--line);
border-radius:999px;padding:2px 9px;white-space:nowrap}
/* ---- a place's sections (detail view) ---- */
.secgroup{margin:20px 0 4px}
.secgroup>.gh{display:flex;align-items:baseline;gap:8px;margin-bottom:10px;padding-bottom:7px;border-bottom:1px solid var(--line)}
.secgroup>.gh h2{margin:0;font-size:16px}
.secgroup>.gh .sub{font-size:12px;color:var(--muted);flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.subsec{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:13px 14px;margin-bottom:10px}
.subsec.empty{border-style:dashed;background:transparent}
.subsec .shd{display:flex;align-items:center;gap:8px}
.subsec .shd .ic18{color:var(--accent);flex:none;display:flex;align-items:center}
.subsec .shd .ti{font-weight:800;font-size:14.5px;flex:1;min-width:0}
.subsec .shd .ver{font-size:11px;color:var(--muted);background:var(--panel2);border:1px solid var(--line);
border-radius:999px;padding:3px 9px;cursor:pointer;font-weight:700;flex:none;display:inline-flex;align-items:center;gap:3px}
.subsec .iconbtn{background:var(--panel2);border:1px solid var(--line);color:var(--text);border-radius:9px;
width:32px;height:32px;cursor:pointer;flex:none;display:flex;align-items:center;justify-content:center}
.subsec .body{white-space:pre-wrap;color:#e7ded1;margin-top:9px;font-size:14px;line-height:1.62}
.subsec .hint{color:var(--muted);font-size:12.5px;margin-top:4px}
.verlist .vrow{border:1px solid var(--line);border-radius:12px;padding:10px 12px;margin-bottom:8px;background:var(--panel2)}
.verlist .vrow.cur{border-color:var(--accent)}
.verlist .vrow .vmeta{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:6px}
.verlist .vrow .vmeta .when{font-size:12px;color:var(--muted)}
.verlist .vrow .vtext{font-size:12.5px;color:#d8cfc0;max-height:130px;overflow:auto;white-space:pre-wrap;line-height:1.5}
/* persistent import-progress banner (survives tab switches & page reloads) */
#impbar{position:fixed;left:50%;transform:translateX(-50%);bottom:calc(env(safe-area-inset-bottom,0) + 92px);z-index:60;width:min(520px,calc(100% - 22px));
 background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:12px 14px;
 -webkit-backdrop-filter:blur(16px) saturate(1.4);backdrop-filter:blur(16px) saturate(1.4);
 box-shadow:0 16px 40px -8px rgba(0,0,0,.6);display:none}
#impbar.show{display:block;animation:impin .25s ease}
@keyframes impin{from{opacity:0;transform:translateX(-50%) translateY(8px)}to{opacity:1;transform:translateX(-50%) translateY(0)}}
#impbar .imphd{display:flex;align-items:center;gap:9px;font-size:13.5px;font-weight:600}
#impbar .impspin{width:15px;height:15px;border:2px solid var(--line);border-top-color:var(--accent);border-radius:50%;animation:impspin .8s linear infinite;flex:0 0 auto}
@keyframes impspin{to{transform:rotate(360deg)}}
#impbar .impsub{font-size:12px;color:var(--muted);margin-top:3px}
#impbar .imptrack{height:7px;border-radius:5px;background:var(--line);margin-top:9px;overflow:hidden}
#impbar .impfill{height:100%;width:0;background:linear-gradient(90deg,var(--accent),#f0b457);border-radius:5px;transition:width .4s ease}
#impbar .impx{margin-left:auto;background:none;border:0;color:var(--muted);font-size:17px;cursor:pointer;line-height:1;padding:0 2px}
#impbar.ok .impfill{background:#49b36b}#impbar.err .impfill{background:#d8574e}
/* ---- shareable trip card ---- */
.tcard-sheet{padding:16px 16px 22px}
.tcard{position:relative;overflow:hidden;border-radius:22px;padding:24px 22px 20px;background:linear-gradient(145deg,#141019,#2a1c3a 55%,#0f1a2e);box-shadow:0 18px 50px rgba(0,0,0,.5);min-height:300px;display:flex;flex-direction:column}
.tcard-glow{position:absolute;top:-80px;right:-60px;width:320px;height:320px;background:radial-gradient(circle,rgba(245,201,119,.33),transparent 70%);pointer-events:none}
.tcard-brand{display:flex;align-items:center;gap:7px;font-size:12px;letter-spacing:.14em;font-weight:700;color:rgba(235,232,248,.82)}
.tcard-brand .ic{width:16px;height:16px}
.tcard-body{margin-top:auto;padding-top:34px}
.tcard-kicker{font-size:11px;letter-spacing:.13em;font-weight:700;color:var(--accent);text-transform:uppercase}
.tcard-dest{margin:6px 0 8px;font-size:34px;line-height:1.05;font-weight:800;color:#fbfaff}
.tcard-dates{font-size:15px;color:rgba(235,232,248,.7)}
.tcard-stats{display:flex;gap:26px;margin-top:20px;padding-top:16px;border-top:1px solid rgba(255,255,255,.1)}
.tcard-stat b{display:block;font-size:24px;font-weight:800;color:#fbfaff}
.tcard-stat span{font-size:12px;color:rgba(235,232,248,.6)}
.tcard-cta{display:flex;gap:10px;margin-top:16px}
.tcard-cta .btn{flex:1}
/* ---- Split (shared expenses) ---- */
.splform input,.splform select{width:100%;background:var(--panel2,#1a1a24);border:1px solid var(--line);color:var(--text);border-radius:10px;padding:10px 12px;font:inherit;margin-bottom:8px}
.splrow{display:flex;gap:8px}.splrow select{flex:1}.splrow input{width:120px}
.splrow2{display:flex;align-items:center;gap:10px;margin-top:4px}
.splchks{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px}
.splchk{display:inline-flex;align-items:center;gap:6px;background:var(--panel2,#1a1a24);border:1px solid var(--line);border-radius:999px;padding:4px 11px 4px 8px;font-size:13px;cursor:pointer}
.splchk input{width:auto;margin:0}
.splhd{font-weight:800;margin:18px 2px 8px;font-size:15px}
.balrow,.setrow,.exprow{display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid var(--line)}
.balrow:last-child,.setrow:last-child,.exprow:last-child{border-bottom:0}
.balnm{flex:1}.balv{font-weight:700;font-size:13px}.balv.pos{color:#3ddc97}.balv.neg{color:#ff6b6b}
.setrow .ic{width:15px;height:15px;opacity:.7}.setrow .setv{margin-left:auto;font-weight:800}
.setrow b{color:var(--text)}
.exprow .expmain{flex:1;min-width:0}.exprow .expd{font-weight:600}
.exprow .expamt{font-weight:800;white-space:nowrap}
.iconbtn{background:none;border:0;color:var(--muted);cursor:pointer;padding:4px;border-radius:8px}
.iconbtn:hover{color:#ff6b6b}.iconbtn .ic{width:17px;height:17px}
.tcard{background:linear-gradient(135deg,#1c2030,#2a2340);border:1px solid var(--line)}
.tcardface{display:flex;flex-direction:column;gap:4px;padding:6px 2px}
.tcardbrand{font-size:12px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:#cbb6ff}
.tcarddots{font-size:20px;font-weight:700;letter-spacing:2px;font-variant-numeric:tabular-nums}
.tcardmeta{font-size:12px;color:var(--muted)}
.tcard .btn.ghost,.splform .btn{white-space:nowrap}
</style></head><body>
<header id="topbar">
  <div class="headrow">
    <span class="logo">__MARK__</span>
    <h1>Trip<span>Sync</span></h1>
    <div class="tripselwrap" id="tripselwrap">
     <button class="tripsel" id="tripsel" style="display:none" onclick="openSelector()">
      <span class="tcover" id="tripselCov" data-ic="map" data-icsize="18"></span>
      <span class="tinfo"><span class="nm" id="tripselNm">Trip</span><span class="dt" id="tripselDt"></span></span>
      <span class="cr" data-ic="chevronDown"></span>
     </button>
     <div class="tripdd" id="tripdd" style="display:none"></div>
    </div>
  </div>
</header>
<main id="app"></main>
<nav class="tabs" id="tabs" style="display:none">
  <button class="tab" data-t="places" data-ic="pin" onclick="goTab('places')">Places</button>
  <button class="tab" data-t="photos" data-ic="camera" onclick="goTab('photos')">Photos</button>
  <button class="tab" data-t="map" data-ic="map" onclick="goTab('map')">Map</button>
  <button class="tab" data-t="memories" data-ic="film" onclick="goTab('memories')">Memories</button>
  <button class="tab" data-t="chat" data-ic="chat" onclick="goTab('chat')">Chat</button>
  <button class="tab" data-t="split" data-ic="wallet" onclick="goTab('split')">Split</button>
</nav>
<canvas id="cv" style="display:none"></canvas>
<script>
const BASE="__BASE__";
const api=(p,o)=>fetch(BASE+p,o).then(r=>r.json());
const el=id=>document.getElementById(id);
const esc=s=>(s||"").replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));

// ---- inline SVG icon set (line style, inherits text color; replaces all emoji) ----
const ICONS={
 wallet:'<rect x="3" y="6" width="18" height="13" rx="2.4"/><path d="M3 9h18"/><path d="M16 13h2.5"/>',
 scale:'<path d="M12 4v16M7 20h10M5 7l7-2 7 2"/><path d="M5 7 2.5 13a2.5 2.5 0 0 0 5 0L5 7Zm14 0-2.5 6a2.5 2.5 0 0 0 5 0L19 7Z"/>',
 pin:'<path d="M12 21s7-6.3 7-12a7 7 0 1 0-14 0c0 5.7 7 12 7 12z"/><circle cx="12" cy="9" r="2.5"/>',
 camera:'<path d="M3 9a2 2 0 0 1 2-2h1.5L8 5h8l1.5 2H19a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><circle cx="12" cy="13" r="3.2"/>',
 map:'<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2z"/><path d="M9 4v14M15 6v14"/>',
 film:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4"/>',
 compass:'<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2.2 4.8-4.8 2.2 2.2-4.8z"/>',
 pen:'<path d="M14 5.5 18.5 10M4 20l1-4L16.5 4.5a1.5 1.5 0 0 1 2 0l1 1a1.5 1.5 0 0 1 0 2L8 18l-4 2z"/>',
 landmark:'<path d="M4 10h16M12 3 20 7H4l8-4zM6 10v7M10 10v7M14 10v7M18 10v7M3 20h18"/>',
 scroll:'<path d="M6 4h11v13a3 3 0 0 0 3 3H8a3 3 0 0 1-3-3V5.5A1.5 1.5 0 0 1 6 4zM9 8h5M9 12h5"/>',
 building:'<rect x="5" y="3" width="14" height="18" rx="1"/><path d="M9 7h2M13 7h2M9 11h2M13 11h2M9 15h2M13 15h2M10 21v-3h4v3"/>',
 bulb:'<path d="M9.5 18h5M10.5 21h3M12 3a6 6 0 0 0-3.5 10.9c.6.5.9 1.3.9 2.1h5.2c0-.8.3-1.6.9-2.1A6 6 0 0 0 12 3z"/>',
 book:'<path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5zM5 19.5A1.5 1.5 0 0 0 6.5 21H19"/>',
 sparkle:'<path d="M12 3c.4 3.4 2.2 5.2 5.6 5.6-3.4.4-5.2 2.2-5.6 5.6-.4-3.4-2.2-5.2-5.6-5.6C9.8 8.2 11.6 6.4 12 3zM18 14c.2 1.6 1 2.4 2.6 2.6-1.6.2-2.4 1-2.6 2.6-.2-1.6-1-2.4-2.6-2.6 1.6-.2 2.4-1 2.6-2.6z"/>',
 clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7.5V12l3 2"/>',
 keyboard:'<rect x="2.5" y="6" width="19" height="12" rx="2"/><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10"/>',
 chat:'<path d="M20 11.5a7.5 7.5 0 0 1-10.8 6.8L4 20l1.7-5.2A7.5 7.5 0 1 1 20 11.5z"/>',
 send:'<path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4z"/>',
 mic:'<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0 M12 18v3 M9 21h6"/>',
 palette:'<path d="M12 3a9 9 0 1 0 0 18c1.5 0 2-1.2 1.2-2.2-.7-.9-.2-2.3 1.1-2.3H17a4 4 0 0 0 4-4c0-4.9-4-8.5-9-8.5z"/><circle cx="7.5" cy="12" r="1.1"/><circle cx="10" cy="7.8" r="1.1"/><circle cx="15" cy="7.8" r="1.1"/>',
 bolt:'<path d="M13 2 5 13.5h6L10 22l8-11.5h-6z"/>',
 users:'<circle cx="9" cy="8" r="3.2"/><path d="M3.5 20c0-3.2 2.5-5 5.5-5s5.5 1.8 5.5 5M16.5 5.3a3.2 3.2 0 0 1 0 5.4M21 20c0-2.4-1.3-3.9-3.3-4.6"/>',
 notebook:'<rect x="6" y="3" width="13" height="18" rx="2"/><path d="M10 3v18M6 8H4M6 12H4M6 16H4"/>',
 mail:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/>',
 image:'<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9.5" r="1.6"/><path d="m4 18 5-5 3 3 3-3 5 5"/>',
 clapper:'<path d="M3 9h18v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="m3.5 4.5 16 1.6-1 2.9H3z"/>',
 refresh:'<path d="M20 11a8 8 0 0 0-13.7-4.7L4 8.5M4 4v4.5h4.5"/><path d="M4 13a8 8 0 0 0 13.7 4.7L20 15.5M20 20v-4.5h-4.5"/>',
 chevronDown:'<path d="m6 9 6 6 6-6"/>',
 edit:'<path d="M11 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5"/><path d="M18.5 2.5a2 2 0 0 1 3 3L12 15l-4 1 1-4z"/>',
 plus:'<path d="M12 5v14M5 12h14"/>',
 trash:'<path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13M10 11v6M14 11v6"/>',
};
function ic(n,size){const s=size?` width="${size}" height="${size}"`:'';
 return `<svg class="ic"${s} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[n]||''}</svg>`;}
function paintStaticIcons(){document.querySelectorAll('[data-ic]').forEach(e=>{e.insertAdjacentHTML('afterbegin',ic(e.dataset.ic,e.dataset.icsize));});}
let TRIP=null, TRIPS=[], TAB='places', SHARE_LINK='';
let PLACE=null;          // entry id when viewing a single destination
let MAPOBJ=null,RAD=null,COLLAGES=[],MAPCENTER=null,MAPPLACES=[],PLACEMARKERS={};   // map + active radiate burst
let CLUSMARKERS={},REPCACHE={};   // geolocation-first photo clustering: live HTML markers + per-cluster representative-thumb cache
let SECDATA={}, GENS=new Set();  // cached guide sections per entry; in-flight generations
let SHOWN=[];            // photo ids currently shown in the Photos gallery (for bulk assign)
// ---- collaborative trips: this device's identity + chosen display name ----
function deviceToken(){let t;try{t=localStorage.getItem('tl_device');}catch(e){}
 if(!t){t='d'+Math.random().toString(36).slice(2,11)+Date.now().toString(36);try{localStorage.setItem('tl_device',t);}catch(e){}}return t;}
function myName(){try{return (localStorage.getItem('tl_name')||'').trim();}catch(e){return '';}}
function setMyName(n){try{localStorage.setItem('tl_name',(n||'').trim());}catch(e){}}
function initialsOf(n){return ((n||'?').trim().split(/\s+/).map(w=>w[0]).slice(0,2).join('')||'?').toUpperCase();}
function avatarHTML(name,color,size){const s=size||28;return `<span class="mavatar" title="${esc(name)}" style="width:${s}px;height:${s}px;background:${color||'#888'};font-size:${Math.round(s*0.42)}px">${esc(initialsOf(name))}</span>`;}
function memberColor(name){const C=["#E8863B","#3BA6E8","#C65BCF","#3BC07A","#E85B7A","#D4A02B","#6C6CE0","#2BB3B3","#E8623B","#5BAF4A"];let s=0;for(const ch of (name||'?'))s+=ch.charCodeAt(0);return C[s%C.length];}
const SECS=[['landmarks','landmark','Landmarks','Sights genuinely worth your time'],
 ['history','scroll','History','How this place came to be'],
 ['modern','building','Modern life',"What it's like here today"],
 ['essentials','bulb','Know before you go','Language, customs, food & money'],
 ['guide','compass','For you','A guide personalized to your trip']];
const gk=(eid,kind)=>eid+':'+kind;
function fmtTime(iso){try{return new Date(iso).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});}catch(e){return iso||'';}}

function toast(m){let t=document.createElement('div');t.className='toast';t.textContent=m;
 document.body.appendChild(t);setTimeout(()=>t.remove(),2600);}

// ---- persistent import-progress banner (job-based; survives tab switches & reloads) ----
let IMPJOB=null, IMPTIMER=null;
function impBarEl(){let b=el('impbar');if(!b){b=document.createElement('div');b.id='impbar';document.body.appendChild(b);}return b;}
function renderImp(s){
 const b=impBarEl();const total=s.total||0,done=s.done||0;
 const pct=total?Math.min(100,Math.round(done/total*100)):(s.state==='running'?6:100);
 b.classList.remove('ok','err');
 let title,sub,spin='<span class="impspin"></span>',x='';
 if(s.state==='running'){
   title=total?('Importing photos… '+done+' / '+total):'Reading iCloud album…';
   sub=total?(pct+'% · you can leave this page — it keeps going'):'Fetching the album contents…';
 }else if(s.state==='error'){
   b.classList.add('err');spin='⚠️';title='Import failed';sub=s.error||'Something went wrong.';
   x='<button class="impx" onclick="dismissImp()">×</button>';
 }else if(s.state==='interrupted'){
   b.classList.add('err');spin='⚠️';title='Import interrupted';
   sub=(s.done||0)+' photo(s) imported before the server restarted — run it again to finish.';
   x='<button class="impx" onclick="dismissImp()">×</button>';
 }else{ // done
   b.classList.add('ok');spin='✅';
   title='Imported '+(s.imported||done)+' photo(s)';
   sub=s.error?s.error:'All set — tap to view.';
   x='<button class="impx" onclick="dismissImp()">×</button>';
 }
 b.innerHTML='<div class="imphd">'+spin+'<span>'+title+'</span>'+x+'</div>'+
   '<div class="impsub">'+sub+'</div>'+
   '<div class="imptrack"><div class="impfill" style="width:'+pct+'%"></div></div>';
 b.classList.add('show');
}
function dismissImp(){const b=el('impbar');if(b)b.classList.remove('show');IMPJOB=null;if(IMPTIMER){clearTimeout(IMPTIMER);IMPTIMER=null;}}
async function watchImport(jobId){
 if(!jobId)return;IMPJOB=jobId;if(IMPTIMER){clearTimeout(IMPTIMER);IMPTIMER=null;}
 const tick=async()=>{
  if(IMPJOB!==jobId)return; // a newer job/dismiss took over
  let s;try{s=await api('/api/import/status/'+jobId);}catch(e){s=null;}
  if(!s){IMPTIMER=setTimeout(tick,2500);return;}
  renderImp(s);
  if(s.state==='running'){IMPTIMER=setTimeout(tick,2000);return;}
  // terminal: refresh the trip so new photos show, keep the result banner up briefly
  if(TRIP&&(s.imported||s.done))await openTrip(TRIP.id);
  if(s.state==='done'){setTimeout(()=>{if(IMPJOB===jobId)dismissImp();},6000);}
  IMPJOB=null;IMPTIMER=null;
 };
 tick();
}
// on opening a trip, resume any in-flight import for it (so leaving/returning shows live progress)
async function checkImportJob(tripId){
 let d;try{d=await api('/api/import/active/'+tripId);}catch(e){return;}
 const j=d&&d.job;
 if(j&&j.state==='running'){if(IMPJOB!==j.job_id)watchImport(j.job_id);}
 else if(!IMPJOB){const b=el('impbar');if(b)b.classList.remove('show');}
}

// ---- downscale a File to a jpeg dataURL before upload ----
function fileToDataURL(file,max=1600,q=0.85){return new Promise((res,rej)=>{
 const img=new Image();const rd=new FileReader();
 rd.onload=()=>{img.onload=()=>{let{width:w,height:h}=img;
   if(Math.max(w,h)>max){const s=max/Math.max(w,h);w=Math.round(w*s);h=Math.round(h*s);}
   const cv=el('cv');cv.width=w;cv.height=h;cv.getContext('2d').drawImage(img,0,0,w,h);
   res(cv.toDataURL('image/jpeg',q));};img.onerror=rej;img.src=rd.result;};
 rd.onerror=rej;rd.readAsDataURL(file);});}

// read GPS from a photo's EXIF (iOS keeps it on JPEG uploads) BEFORE we downscale it away
function getExifGps(file){return new Promise(res=>{
 const rd=new FileReader();
 rd.onerror=()=>res(null);
 rd.onload=()=>{try{
   const v=new DataView(rd.result);
   if(v.getUint16(0)!==0xFFD8)return res(null);
   let off=2;const end=v.byteLength;
   while(off+4<end){
     const marker=v.getUint16(off);
     if(marker===0xFFE1){
       if(v.getUint32(off+4)!==0x45786966)return res(null); // "Exif"
       const tiff=off+10;
       const little=v.getUint16(tiff)===0x4949;
       const r16=o=>v.getUint16(o,little), r32=o=>v.getUint32(o,little);
       const ifd0=tiff+r32(tiff+4);
       let gps=0;const n0=r16(ifd0);
       for(let i=0;i<n0;i++){const e=ifd0+2+i*12;if(r16(e)===0x8825){gps=tiff+r32(e+8);break;}}
       if(!gps)return res(null);
       const rats=(o,c)=>{const a=[];for(let k=0;k<c;k++){const num=r32(o+k*8),den=r32(o+k*8+4);a.push(den?num/den:0);}return a;};
       let latRef,lonRef,lat,lon;const gn=r16(gps);
       for(let i=0;i<gn;i++){const e=gps+2+i*12,tag=r16(e);
         if(tag===1)latRef=String.fromCharCode(v.getUint8(e+8));
         else if(tag===3)lonRef=String.fromCharCode(v.getUint8(e+8));
         else if(tag===2)lat=rats(tiff+r32(e+8),3);
         else if(tag===4)lon=rats(tiff+r32(e+8),3);}
       if(!lat||!lon)return res(null);
       let dlat=lat[0]+lat[1]/60+lat[2]/3600;if(latRef==='S')dlat=-dlat;
       let dlon=lon[0]+lon[1]/60+lon[2]/3600;if(lonRef==='W')dlon=-dlon;
       if(!isFinite(dlat)||!isFinite(dlon)||(dlat===0&&dlon===0))return res(null);
       return res({lat:dlat,lon:dlon});
     }
     if((marker&0xFF00)!==0xFF00)return res(null);
     off+=2+v.getUint16(off+2); // skip to next marker by its length
   }
   res(null);
 }catch(e){res(null);}};
 rd.readAsArrayBuffer(file.slice(0,262144)); // EXIF sits near the start
});}

// ---- boot: land on the current (most recent) trip (or an invite link) ----
function joinTokenFromUrl(){try{return new URL(location.href).searchParams.get('join');}catch(e){return null;}}
function clearJoinUrl(){try{const u=new URL(location.href);u.searchParams.delete('join');history.replaceState(null,'',u.pathname+u.search+u.hash);}catch(e){}}
async function boot(){
 const jt=joinTokenFromUrl();
 if(jt){return showJoin(jt);}
 const d=await api('/api/trips');TRIPS=d.trips||[];
 if(!TRIPS.length){renderNoTrips();return;}
 openTrip(TRIPS[0].id);}

// ---- join a shared trip via an invite link ----
async function showJoin(token){
 el('tripsel').style.display='none';el('tabs').style.display='none';
 let info;try{info=await api('/api/join/'+encodeURIComponent(token));}catch(e){info=null;}
 if(!info||!info.trip_id){
  el('app').innerHTML=`<div class="empty">This invite link isn't valid anymore.</div>
   <button class="btn" onclick="clearJoinUrl();boot()">Go to Trip Sync</button>`;return;}
 const cov=info.cover?`<img src="${BASE}/collage/${info.cover}" style="width:100%;height:150px;object-fit:cover;border-radius:14px;margin-bottom:14px">`:'';
 el('app').innerHTML=`<div style="padding:20px 2px">
   ${cov}
   <div class="muted sm">You've been invited to join</div>
   <h1 style="margin:2px 0 6px">${esc(info.title)}</h1>
   <div class="muted sm">${esc(info.destination||'')} · ${info.members} traveler${info.members===1?'':'s'} · ${info.photos} photo${info.photos===1?'':'s'}</div>
   <p class="muted" style="margin-top:14px">Add your name so your photos and notes show up as yours in the shared trip.</p>
   <input id="joinNm" placeholder="Your name" value="${esc(myName())}" style="width:100%;margin-top:6px">
   <div class="err" id="joinErr" style="color:#e4674f;font-size:13px;min-height:16px;margin-top:6px"></div>
   <button class="btn" id="joinBtn" style="margin-top:8px">Join trip</button></div>`;
 el('joinBtn').onclick=async()=>{
  const name=(el('joinNm').value||'').trim();
  if(!name){el('joinErr').textContent='Enter your name to join.';return;}
  const btn=el('joinBtn');btn.disabled=true;btn.textContent='Joining…';
  try{await api('/api/trips/'+info.trip_id+'/join',{method:'POST',body:JSON.stringify({token:deviceToken(),name})});
   setMyName(name);clearJoinUrl();TAB='places';openTrip(info.trip_id);toast('Welcome to '+info.title+' 🎉');
  }catch(e){btn.disabled=false;btn.textContent='Join trip';el('joinErr').textContent='Could not join — try again.';}
 };
}

function renderNoTrips(){
 el('tripsel').style.display='none';el('tabs').style.display='none';
 el('app').innerHTML=`<div class="hero fadein">
   <div class="hero-orb">${ic('compass',46)}</div>
   <h1 class="hero-ttl">Every journey,<br><span>beautifully kept.</span></h1>
   <p class="hero-sub">Travelog turns your trips into living memories — map every place, journal the moments, and let AI weave it all into collages and stories.</p>
   <div class="hero-feats">
     <div class="hero-feat">${ic('pin',18)}<span>Map places</span></div>
     <div class="hero-feat">${ic('book',18)}<span>Journal</span></div>
     <div class="hero-feat">${ic('sparkle',18)}<span>AI memories</span></div>
   </div>
   <button class="btn hero-cta" onclick="newTrip()">${ic('plus',18)} Start your first trip</button>
  </div>`;
}

// ---- trip selector (top container) ----
function openSelector(){const dd=el('tripdd');if(!dd)return;
 if(dd.style.display!=='none'){closeSelector();return;}
 api('/api/trips').then(d=>{TRIPS=d.trips||[];
  let h='';
  for(const t of TRIPS){const cov=t.cover?`<img class="cv" src="${BASE}/collage/${t.cover}">`:`<div class="cv">${ic('map',20)}</div>`;
   const dates=[t.start_date,t.end_date].filter(Boolean).join(' → ');
   h+=`<div class="triprow ${TRIP&&t.id===TRIP.id?'cur':''}" onclick="pickTrip(${t.id})">${cov}
    <div style="flex:1;min-width:0"><b>${esc(t.title)}</b>
    <div class="muted sm">${esc(t.destination||'')}${dates?' · '+esc(dates):''}</div></div></div>`;}
  h+=`<button class="btn sm ghost" style="width:100%;margin-top:4px" onclick="newTrip()">+ New trip</button>`;
  if(TRIP)h+=`<div class="toolbar" style="margin-top:8px"><button class="btn sm ghost" style="flex:1" onclick="editTrip()">${ic('pen')} Edit</button>
    <button class="btn sm ghost danger" style="flex:1" onclick="delTrip()">Delete</button></div>`;
  dd.innerHTML=h;dd.style.display='';el('tripsel').classList.add('open');
  setTimeout(()=>document.addEventListener('click',selOutside),0);
 }).catch(()=>{});
}
function selOutside(e){const w=el('tripselwrap');if(w&&!w.contains(e.target))closeSelector();}
function closeSelector(){const dd=el('tripdd');if(dd)dd.style.display='none';const ts=el('tripsel');if(ts)ts.classList.remove('open');document.removeEventListener('click',selOutside);}
function pickTrip(id){closeSelector();TAB='places';openTrip(id);}

function newTrip(){closeSelector();sheet(`<h2>New trip</h2>
 <label>Title</label><input id="f_title" placeholder="Summer in Portugal">
 <label>Destination</label><input id="f_dest" placeholder="Lisbon, Portugal">
 <div class="row"><div><label>Start</label><input id="f_start" type="date"></div>
 <div><label>End</label><input id="f_end" type="date"></div></div>
 <div style="margin-top:16px"><button class="btn" onclick="createTrip()">Create trip</button></div>`);}

async function createTrip(){
 const title=el('f_title').value.trim();if(!title)return toast('Give it a title');
 const body={title,destination:el('f_dest').value.trim(),start_date:el('f_start').value,end_date:el('f_end').value};
 const r=await api('/api/trips',{method:'POST',body:JSON.stringify(body)});
 closeSheet();openTrip(r.id);
}

async function openTrip(id){
 const t=await api('/api/trips/'+id);TRIP=t;
 // keep the current traveler in this trip's crew (if they've named themselves)
 if(myName()){api('/api/trips/'+id+'/join',{method:'POST',body:JSON.stringify({token:deviceToken(),name:myName()})}).then(()=>{},()=>{});}
 const dates=[t.start_date,t.end_date].filter(Boolean).join(' → ');
 el('tripsel').style.display='';el('tabs').style.display='';
 el('tripselNm').textContent=t.title;
 el('tripselCov').innerHTML=t.cover?`<img src="${BASE}/collage/${t.cover}">`:ic('map',22);
 el('tripselDt').textContent=[t.destination,dates].filter(Boolean).join(' · ')||'Tap to switch or add a trip';
 renderTab();
 checkImportJob(id);
}
function goTab(tab){PLACE=null;TAB=tab;renderTab();}
function renderTab(){
 if(!TRIP)return;
 [...document.querySelectorAll('nav.tabs .tab')].forEach(b=>b.classList.toggle('on',b.dataset.t===TAB));
 // trip selector only on the trip home (the places list) — hidden on other tabs & place detail
 const ts=el('tripsel');if(ts)ts.style.display=(TAB==='places'&&!PLACE)?'':'none';
 const ap=el('app');if(ap){ap.classList.remove('fadein');void ap.offsetWidth;ap.classList.add('fadein');}
 if(TAB==='places')return renderPlaces();
 if(TAB==='photos')return renderPhotos();
 if(TAB==='map')return openMap();
 if(TAB==='memories')return renderMemories();
 if(TAB==='chat')return renderChat();
 if(TAB==='split')return renderSplit();
}

// ---- Split: shared-expense tracking (Splitwise-style) ----
function money(cents,cur){const v=(Math.abs(cents||0)/100).toFixed(2);
 const sym=cur==='USD'?'$':cur==='EUR'?'€':cur==='GBP'?'£':'';return sym?sym+v:v+' '+(cur||'');}
async function renderSplit(){
 const app=el('app');if(!TRIP)return;
 app.innerHTML=`<div class="tabhead"><h2>${ic('wallet')} Split</h2></div><div class="muted sm">Loading…</div>`;
 let d;try{d=await api('/api/trips/'+TRIP.id+'/expenses');}catch(e){app.innerHTML=`<div class="tabhead"><h2>${ic('wallet')} Split</h2></div><div class="empty">Couldn't load expenses.</div>`;return;}
 const mem=d.members||[],cur=d.currency||'USD';
 if(!mem.length){app.innerHTML=`<div class="tabhead"><h2>${ic('wallet')} Split</h2></div>
   <div class="empty">Add the people on this trip first — tap <b>Invite</b> on the trip home — then you can split expenses between them.</div>`;return;}
 const opts=mem.map(m=>`<option value="${esc(m.name)}">${esc(m.name)}</option>`).join('');
 const card=d.card;
 let cardHtml;
 if(!card){
   cardHtml=`<div class="card tcardnew"><div class="splhd" style="margin:0 0 6px">${ic('wallet')} Trip Card</div>
     <div class="muted sm">Add one shared card — every charge on it auto-splits across everyone on the trip. No manual entry.</div>
     <div class="splrow" style="margin-top:10px"><select id="card_funder" title="Who funds the card">${opts}</select>
       <button class="btn" onclick="createCard()">${ic('plus')}Create card</button></div>
     <div class="muted sm" style="margin-top:6px">${d.card_live?'Stripe test cards are enabled.':'Demo mode — issues a simulated card. Add a Stripe test key to mint real test cards.'}</div></div>`;
 } else {
   cardHtml=`<div class="card tcard"><div class="tcardface">
       <span class="tcardbrand">${esc(card.brand||'Visa')} ${card.live?'· Stripe test':'· Demo'}</span>
       <span class="tcarddots">•••• •••• •••• ${esc(card.last4||'----')}</span>
       <span class="tcardmeta">Funded by ${esc(card.funder||'—')} · ${esc(card.status||'active')}</span></div>
     <div class="splrow" style="margin-top:10px"><input id="sim_amt" type="number" min="0" step="0.01" placeholder="amount">
       <input id="sim_mer" placeholder="merchant (Uber, hotel…)">
       <button class="btn ghost" onclick="simCharge()">Simulate swipe</button></div>
     <div class="muted sm" style="margin-top:4px">${card.live?'Real test charges arrive automatically via webhook; simulate one to preview.':'Demo: simulate a swipe to watch it auto-split below.'}</div></div>`;
 }
 const checks=mem.map(m=>`<label class="splchk"><input type="checkbox" class="spl-mem" value="${esc(m.name)}" checked>${avatarHTML(m.name,m.color,22)}<span>${esc(m.name)}</span></label>`).join('');
 const settle=(d.settle||[]).length?d.settle.map(s=>`<div class="setrow"><span>${esc(s.from)}</span>${ic('send')}<b>${esc(s.to)}</b><span class="setv">${money(s.amount_cents,cur)}</span></div>`).join(''):'<div class="muted sm">Everyone\'s square 🎉</div>';
 const bal=(d.balances||[]).map(b=>{const n=b.net_cents||0,cls=n>0?'pos':n<0?'neg':'';
   const lbl=n>0?('gets back '+money(n,cur)):n<0?('owes '+money(-n,cur)):'settled up';
   return `<div class="balrow">${avatarHTML(b.name,b.color,28)}<span class="balnm">${esc(b.name)}</span><span class="balv ${cls}">${lbl}</span></div>`;}).join('');
 const list=(d.expenses||[]).length?d.expenses.map(e=>`<div class="exprow"><div class="expmain">
     <div class="expd">${esc(e.description||'Expense')}</div>
     <div class="muted sm">${esc(e.payer)} paid · split ${e.shares.length} way${e.shares.length===1?'':'s'}</div></div>
     <div class="expamt">${money(e.amount_cents,e.currency||cur)}</div>
     <button class="iconbtn" title="Delete" onclick="delExpense(${e.id})">${ic('trash')}</button></div>`).join(''):'<div class="muted sm">No expenses yet — add the first one above.</div>';
 app.innerHTML=`<div class="tabhead"><h2>${ic('wallet')} Split</h2></div>
   ${cardHtml}
   <div class="splhd">Add an expense by hand</div>
   <div class="card splform">
     <input id="exp_desc" placeholder="What was it? (dinner, taxi, hotel…)">
     <div class="splrow"><select id="exp_payer" title="Who paid">${opts}</select>
       <input id="exp_amt" type="number" inputmode="decimal" min="0" step="0.01" placeholder="0.00"></div>
     <div class="muted sm" style="margin:2px 0">Split between</div>
     <div class="splchks">${checks}</div>
     <div class="splrow2"><button class="btn" onclick="addExpense()">${ic('plus')}Add expense</button><span id="expMsg" class="muted sm"></span></div>
   </div>
   <div class="splhd">Who owes who</div><div class="card">${settle}</div>
   <div class="splhd">Balances</div><div class="card balcard">${bal}</div>
   <div class="splhd">Expenses</div>${list}`;
}
async function addExpense(){
 const desc=el('exp_desc').value,payer=el('exp_payer').value,amount=el('exp_amt').value;
 const members=[...document.querySelectorAll('.spl-mem:checked')].map(c=>c.value);
 if(!amount||Number(amount)<=0){el('expMsg').textContent='Enter an amount.';return;}
 if(!members.length){el('expMsg').textContent='Pick who to split between.';return;}
 el('expMsg').textContent='Saving…';
 let r;try{r=await api('/api/trips/'+TRIP.id+'/expenses',{method:'POST',body:JSON.stringify({payer,amount:Number(amount),description:desc,members})});}catch(e){el('expMsg').textContent='Could not save.';return;}
 if(r&&r.error){el('expMsg').textContent=r.error;return;}
 renderSplit();
}
async function delExpense(id){if(!confirm('Delete this expense?'))return;try{await api('/api/expenses/'+id,{method:'DELETE'});}catch(e){}renderSplit();}
async function createCard(){const funder=el('card_funder').value;
 let r;try{r=await api('/api/trips/'+TRIP.id+'/card',{method:'POST',body:JSON.stringify({funder})});}catch(e){toast('Could not create card');return;}
 if(r&&r.error){toast(r.error);return;}renderSplit();}
async function simCharge(){const amount=el('sim_amt').value,merchant=el('sim_mer').value;
 if(!amount||Number(amount)<=0){toast('Enter an amount');return;}
 try{await api('/api/trips/'+TRIP.id+'/card/charge',{method:'POST',body:JSON.stringify({amount:Number(amount),merchant})});}catch(e){toast('Could not add charge');return;}
 renderSplit();}

function tripSubhead(){const t=TRIP;const dates=[t.start_date,t.end_date].filter(Boolean).join(' → ');
 return `<div class="muted sm" style="margin:2px 0 12px">${esc(t.destination||'')}${dates?' · '+esc(dates):''}</div>`;}

// ---- collaborative crew bar + share sheet ----
function crewBar(t){
 const ms=(t.members||[]);
 const av=ms.slice(0,5).map(m=>avatarHTML(m.name,m.color,30)).join('');
 const extra=ms.length>5?`<span class="mavatar" style="width:30px;height:30px;background:#5b5b6e;font-size:11px">+${ms.length-5}</span>`:'';
 const label=ms.length?`${ms.length} traveler${ms.length===1?'':'s'}`:'Travel together';
 return `<div class="crewbar" onclick="openShareSheet()">
   <div class="crew-av">${av||avatarHTML(myName()||'You',memberColor(myName()||'You'),30)}${extra}</div>
   <div class="crew-lbl">${label}</div>
   <span class="btn sm ghost crew-share" style="width:auto">${ic('users')} Invite</span>
 </div>`;
}
async function openShareSheet(){
 if(!TRIP)return;
 let d;try{d=await api('/api/trips/'+TRIP.id+'/members');}catch(e){d={members:[],share_token:null};}
 let tok=d.share_token;
 if(!tok){try{tok=(await api('/api/trips/'+TRIP.id+'/share',{method:'POST',body:'{}'})).token;}catch(e){}}
 const link=location.origin+(BASE||'')+'/?join='+(tok||'');
 SHARE_LINK=link;
 const crew=(d.members||[]);
 // stacked avatar cluster for the hero
 const cluster=crew.length?crew.slice(0,4).map((m,i)=>`<span class="iv-face" style="margin-left:${i?'-12px':'0'};z-index:${9-i}">${avatarHTML(m.name,m.color,44)}</span>`).join('')
   :`<span class="iv-face">${avatarHTML(myName()||'You',memberColor(myName()||'You'),44)}</span>`;
 const more=crew.length>4?`<span class="iv-face iv-more" style="margin-left:-12px">+${crew.length-4}</span>`:'';
 const crewLine=crew.length?`${crew.length} traveler${crew.length===1?'':'s'} in the crew`:'Be the first — invite your crew';
 const rows=crew.length?crew.map(m=>`<div class="iv-row">${avatarHTML(m.name,m.color,36)}
   <div style="flex:1;min-width:0"><b>${esc(m.name)}</b><div class="muted sm">${m.photos} photo${m.photos===1?'':'s'} added</div></div>
   <span class="iv-dot" title="joined"></span></div>`).join('')
   :'';
 const qr='https://api.qrserver.com/v1/create-qr-code/?size=320x320&margin=0&qzone=1&bgcolor=16-17-24&color=235-232-248&data='+encodeURIComponent(link);
 const canNative=!!(navigator.share);
 sheet(`<div class="iv">
   <div class="iv-hero">
     <div class="iv-glow"></div>
     <div class="iv-cluster">${cluster}${more}</div>
     <h2 class="iv-title">Invite your crew</h2>
     <p class="iv-sub">Travel <b>${esc(TRIP.title)}</b> together — everyone adds their own photos &amp; journal entries, each credited to them.</p>
   </div>
   <div class="iv-qr"><img alt="Scan to join" src="${qr}" onerror="this.style.display='none'"><span class="muted sm">Scan to join</span></div>
   <div class="iv-cta">
     ${canNative?`<button class="btn iv-primary" onclick="nativeShare()">${ic('users')} Share invite</button>`:''}
     <button class="btn ${canNative?'ghost':''} iv-copy" onclick="copyShare()"><span class="iv-link">${esc(link)}</span><span class="iv-copybtn">Copy</span></button>
     <button class="btn ghost" onclick="openTripCard()">${ic('image')} Make a shareable trip card</button>
   </div>
   <div class="iv-chans">
     <a class="iv-chan" href="sms:?&body=${encodeURIComponent('Join my trip on Trip Sync: '+link)}">${ic('chat')}<span>Messages</span></a>
     <a class="iv-chan" href="https://wa.me/?text=${encodeURIComponent('Join my trip on Trip Sync: '+link)}" target="_blank" rel="noopener">${ic('users')}<span>WhatsApp</span></a>
     <a class="iv-chan" href="mailto:?subject=${encodeURIComponent('Join my trip: '+TRIP.title)}&body=${encodeURIComponent('Come travel '+TRIP.title+' with me on Trip Sync — add your photos and journal:\\n\\n'+link)}">${ic('mail')}<span>Email</span></a>
   </div>
   ${crew.length?`<div class="iv-crew"><div class="iv-crewhd">${crewLine}</div>${rows}</div>`:''}
 </div>`);
}
function nativeShare(){
 if(!SHARE_LINK)return;
 const title=TRIP?('Join my trip: '+TRIP.title):'Join my trip';
 if(navigator.share){navigator.share({title:title,text:'Travel '+(TRIP?TRIP.title:'')+' together on Trip Sync — add your photos and journal.',url:SHARE_LINK}).catch(()=>{});}
 else copyShare();
}
function copyShare(){const v=SHARE_LINK||'';if(!v)return;
 const done=()=>toast('Invite link copied ✓');
 if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(v).then(done).catch(()=>fallbackCopy(v,done));}
 else fallbackCopy(v,done);}
function fallbackCopy(v,done){try{const t=document.createElement('textarea');t.value=v;t.style.position='fixed';t.style.opacity='0';document.body.appendChild(t);t.select();document.execCommand('copy');document.body.removeChild(t);done();}catch(e){toast('Copy the link manually');}}

// ---- shareable trip card: a designed summary you can share/download as an image ----
let TCARD_BLOB=null, TCARD_URL='';
function tripDateStr(){const f=d=>{if(!d)return'';try{return new Date(d+'T00:00:00').toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'});}catch(_){return d;}};
 const s=TRIP&&TRIP.start_date, e=TRIP&&TRIP.end_date; if(s&&e&&s!==e)return f(s)+' – '+f(e); return f(s||e||'');}
async function openTripCard(){
 if(!TRIP){toast('Open a trip first');return;}
 const dest=TRIP.destination||TRIP.title||'My Trip', dates=tripDateStr();
 const nE=(TRIP.entries||[]).length, nP=(TRIP.photos||[]).length;
 let crew=1; try{const d=await api('/api/trips/'+TRIP.id+'/members');crew=Math.max(1,(d.members||[]).length);}catch(_){}
 sheet(`<div class="tcard-sheet">
   <div class="tcard" id="tcardPreview">
     <div class="tcard-glow"></div>
     <div class="tcard-brand">${ic('map')} TRIP SYNC</div>
     <div class="tcard-body">
       <div class="tcard-kicker">${esc(TRIP.title||'Trip')}</div>
       <h2 class="tcard-dest">${esc(dest)}</h2>
       <div class="tcard-dates">${esc(dates)||'&nbsp;'}</div>
     </div>
     <div class="tcard-stats">
       <div class="tcard-stat"><b>${nE}</b><span>place${nE===1?'':'s'}</span></div>
       <div class="tcard-stat"><b>${nP}</b><span>photo${nP===1?'':'s'}</span></div>
       <div class="tcard-stat"><b>${crew}</b><span>traveler${crew===1?'':'s'}</span></div>
     </div>
   </div>
   <div class="tcard-cta">
     <button class="btn iv-primary" onclick="shareTripCard()">${ic('send')} Share card</button>
     <button class="btn ghost" onclick="downloadTripCard()">${ic('image')} Download</button>
   </div>
 </div>`);
 renderTripCardPNG(dest,dates,nE,nP,crew);
}
function tcWrap(g,text,x,y,maxW,lh){const words=(text||'').split(' ');let line='',yy=y;
 words.forEach(w=>{const t=line?line+' '+w:w;if(g.measureText(t).width>maxW&&line){g.fillText(line,x,yy);line=w;yy+=lh;}else line=t;});if(line)g.fillText(line,x,yy);return yy;}
function renderTripCardPNG(dest,dates,nE,nP,crew){try{
 const W=1080,H=1350,cv=document.createElement('canvas');cv.width=W;cv.height=H;const g=cv.getContext('2d');
 const bg=g.createLinearGradient(0,0,W,H);bg.addColorStop(0,'#141019');bg.addColorStop(.55,'#2a1c3a');bg.addColorStop(1,'#0f1a2e');g.fillStyle=bg;g.fillRect(0,0,W,H);
 const rg=g.createRadialGradient(W*0.8,H*0.18,40,W*0.8,H*0.18,620);rg.addColorStop(0,'rgba(245,201,119,.33)');rg.addColorStop(1,'rgba(245,201,119,0)');g.fillStyle=rg;g.fillRect(0,0,W,H);
 g.textAlign='left';
 g.fillStyle='rgba(235,232,248,.85)';g.font='700 34px -apple-system,Segoe UI,Roboto,sans-serif';g.fillText('✦  TRIP SYNC',90,150);
 g.fillStyle='rgba(245,201,119,.95)';g.font='700 38px -apple-system,Segoe UI,Roboto,sans-serif';g.fillText(((TRIP.title||'').toUpperCase()).slice(0,42),90,H*0.52-150);
 g.fillStyle='#fbfaff';g.font='800 108px -apple-system,Segoe UI,Roboto,sans-serif';
 const endY=tcWrap(g,dest,88,H*0.52,W-176,112);
 g.fillStyle='rgba(235,232,248,.72)';g.font='400 46px -apple-system,Segoe UI,Roboto,sans-serif';if(dates)g.fillText(dates,90,endY+90);
 const stats=[[nE,'places'],[nP,'photos'],[crew,'travelers']];let x=90;const y=H-150;
 g.strokeStyle='rgba(255,255,255,.12)';g.lineWidth=2;g.beginPath();g.moveTo(90,y-80);g.lineTo(W-90,y-80);g.stroke();
 stats.forEach(([n,l])=>{g.fillStyle='#fbfaff';g.font='800 66px -apple-system,Segoe UI,Roboto,sans-serif';g.fillText(String(n),x,y);const w=g.measureText(String(n)).width;g.fillStyle='rgba(235,232,248,.6)';g.font='400 32px -apple-system,Segoe UI,Roboto,sans-serif';g.fillText(l,x,y+44);x+=Math.max(w,110)+78;});
 cv.toBlob(b=>{if(!b)return;if(TCARD_URL)URL.revokeObjectURL(TCARD_URL);TCARD_BLOB=b;TCARD_URL=URL.createObjectURL(b);},'image/png');
}catch(e){}}
function downloadTripCard(){if(!TCARD_URL){toast('Card still rendering…');return;}
 const a=document.createElement('a');a.href=TCARD_URL;a.download=(((TRIP&&TRIP.title)||'trip').replace(/[^a-z0-9]+/gi,'-').toLowerCase())+'-tripsync.png';
 document.body.appendChild(a);a.click();a.remove();toast('Card downloaded ✓');}
async function shareTripCard(){
 if(TCARD_BLOB&&navigator.canShare){const f=new File([TCARD_BLOB],'trip-card.png',{type:'image/png'});
  if(navigator.canShare({files:[f]})){try{await navigator.share({files:[f],title:(TRIP&&TRIP.title)||'My trip',text:'My trip on Trip Sync'});return;}catch(e){if(e&&e.name==='AbortError')return;}}}
 downloadTripCard();}

// ---- Places tab: a compact list of destinations; tap one to open its sections ----
function renderPlaces(){const t=TRIP;
 if(PLACE){const e=(t.entries||[]).find(x=>x.id===PLACE);if(e)return renderPlaceDetail(e);PLACE=null;}
 let h=crewBar(t);
 if(!t.entries.length){h+=`<div class="empty">No places logged yet.<br>Add the first place you visited and open it for its guide.</div>`;}
 for(const e of (t.entries||[])){
  const photos=(t.photos||[]).filter(p=>p.entry_id===e.id);
  const coverFn=(e.cover&&photos.some(p=>p.filename===e.cover))?e.cover:((photos.find(p=>p.category!=='Journal')||photos[0]||{}).filename);
  const cov=coverFn?`<img src="${BASE}/photo/${coverFn}">`:`<div class="novc">${ic('pin',34)}</div>`;
  h+=`<div class="placecard">
   <div class="cov" onclick="openPlace(${e.id})">${cov}</div>
   <button class="editcov" onclick="event.stopPropagation();editCover(${e.id})">${ic('image',13)} Cover</button>
   <div class="body" onclick="openPlace(${e.id})">
    <div class="ttl">${esc(e.place)}<span class="go" style="margin-left:auto">›</span></div>
    <div class="ministats">
     ${e.date?`<span class="s">${esc(e.date)}</span>`:''}
     ${e.companions?`<span class="s">${ic('users')} ${esc(e.companions)}</span>`:''}
     ${photos.length?`<span class="s">${ic('camera')} ${photos.length}</span>`:''}
     ${(e.experience||'').trim()?`<span class="s">${ic('book')} journal</span>`:''}
    </div></div>
  </div>`;
 }
 h+=`<button class="btn addnew" onclick="newEntry()">+ Add a place</button>`;
 el('app').innerHTML=h;
}
// quick cover picker for a place (tap a photo to set it as the card cover)
function editCover(id){const e=(TRIP.entries||[]).find(x=>x.id===id);if(!e)return;
 const photos=(TRIP.photos||[]).filter(p=>p.entry_id===id);
 if(!photos.length)return toast('Add photos to this place first');
 const grid=photos.map(p=>`<div class="covpick${e.cover===p.filename?' on':''}" onclick="pickCover(${id},'${p.filename}')"><img src="${BASE}/photo/${p.filename}"></div>`).join('');
 sheet(`<h2>Cover — ${esc(e.place)}</h2><p class="muted sm">Tap a photo to set it as this place's cover.</p><div class="covgrid">${grid}</div>`);
}
async function pickCover(id,fn){const e=(TRIP.entries||[]).find(x=>x.id===id);if(e)e.cover=fn;
 try{await api('/api/entries/cover',{method:'POST',body:JSON.stringify({entry_id:id,filename:fn})});}catch(_){}
 closeSheet();renderTab();}
function openPlace(id){PLACE=id;window.scrollTo(0,0);renderTab();}
function backToPlaces(){PLACE=null;renderTab();}

// ---- a single destination: About-here guide (sectioned) + journal + photos ----
function bookingUI(e){
 const place=(e.place||'').trim(); if(!place) return '';
 const q=encodeURIComponent(place);
 // pull trip dates through if present, so flight/stay searches land closer to the real trip
 const t=TRIP||{}; const din=(t.start_date||''),dout=(t.end_date||'');
 const cards=[
   {ic:'send', t:'Flights', s:'Find flights to '+place, prov:'Google Flights',
    u:'https://www.google.com/travel/flights?q='+encodeURIComponent('flights to '+place)},
   {ic:'building', t:'Stays', s:'Hotels & rentals', prov:'Booking.com',
    u:'https://www.booking.com/searchresults.html?ss='+q+(din?'&checkin='+din:'')+(dout?'&checkout='+dout:'')},
   {ic:'sparkle', t:'Experiences', s:'Tours & things to do', prov:'GetYourGuide',
    u:'https://www.getyourguide.com/s/?q='+q},
   {ic:'map', t:'Getting around', s:'Routes, trains & transfers', prov:'Rome2Rio',
    u:'https://www.rome2rio.com/s/'+q},
 ];
 const grid=cards.map(c=>`<a class="book-card" href="${c.u}" target="_blank" rel="noopener">
   <span class="book-ic">${ic(c.ic)}</span>
   <span class="book-tx"><b>${c.t}</b><span class="muted sm">${esc(c.s)}</span></span>
   <span class="book-prov">${c.prov} ›</span></a>`).join('');
 return `<div class="secgroup"><div class="gh"><h2>${ic('compass')} Plan &amp; book</h2>
   <span class="sub">everything for your trip to ${esc(place)}</span></div>
   <div class="book-grid">${grid}</div>
   <div class="book-note muted sm">${ic('bulb',13)} Opens in your browser — we don't take a cut or see your booking.</div></div>`;
}
// ---- place quiz game: learn through fun questions, unlock a hidden piece of your trip ----
let QUIZ={};        // eid -> server bundle {questions,reward,progress}
let QZ=null;        // active play state
function placeName(eid){const e=((TRIP||{}).entries||[]).find(x=>x.id===eid);return e?e.place:'this place';}
function pMiles(){try{return +(localStorage.getItem('tl_miles')||0)||0;}catch(e){return 0;}}
function addMiles(n){try{localStorage.setItem('tl_miles',String(pMiles()+(n||0)));}catch(e){}}
function gameUI(e){
 return `<div class="secgroup"><div class="gh"><h2>${ic('sparkle')} Unlock this place</h2>
   <span class="sub">learn ${esc(e.place)} through a quick game</span></div>
   <div id="gamecard-${e.id}"><div class="muted sm" style="padding:4px 2px"><span class="spinner"></span>Loading the game…</div></div></div>`;
}
async function loadGame(eid){
 let d;try{d=await api('/api/quiz/'+eid+'?device='+encodeURIComponent(deviceToken()));}catch(e){d=null;}
 QUIZ[eid]=d;renderGame(eid);
}
function renderGame(eid){
 const box=el('gamecard-'+eid);if(!box)return;const d=QUIZ[eid];
 if(!d||!d.questions){box.innerHTML=`<div class="subsec empty"><div class="hint">The place game isn't ready yet — it needs a place name (and the AI key) to build questions.</div></div>`;return;}
 const pg=d.progress||{};const n=d.questions.length;
 if(pg.completed&&d.reward){
  const stars=starsFor(pg.best,pg.total||n);
  box.innerHTML=`<div class="reward-card unlocked">
    <div class="reward-stamp" title="passport stamp">${ic('sparkle')}</div>
    <div class="reward-h">Secret of ${esc(placeName(eid))}</div>
    <div class="reward-b">${esc(d.reward)}</div>
    <div class="reward-meta"><span class="stars">${stars}</span><span class="muted sm">${pg.best}/${pg.total||n} right</span>
      <button class="btn sm ghost" style="width:auto;margin-left:auto" onclick="openQuiz(${eid})">Play again</button></div>
  </div>`;
 }else{
  box.innerHTML=`<div class="game-cta" onclick="openQuiz(${eid})">
    <div class="game-orb">${ic('sparkle')}<span class="game-q">?</span></div>
    <div class="game-tx"><b>Reveal a hidden gem</b><span class="muted sm">Answer ${n} fun questions about ${esc(placeName(eid))} to unlock a secret only locals know — and stamp your passport.</span></div>
    <span class="btn sm game-play">Play</span></div>`;
 }
}
function starsFor(best,total){const r=total?best/total:0;const s=r>=1?3:r>=.6?2:1;return '★'.repeat(s)+'☆'.repeat(3-s);}
function openQuiz(eid){const d=QUIZ[eid];if(!d||!d.questions)return;QZ={eid,qs:d.questions,i:0,score:0,picked:null};renderQuiz();}
function renderQuiz(){
 const z=QZ;if(!z)return;const q=z.qs[z.i];
 const dots=z.qs.map((_,k)=>`<i class="qd ${k<z.i?'done':(k===z.i?'cur':'')}"></i>`).join('');
 const last=z.i===z.qs.length-1;
 sheet(`<div class="quiz">
   <div class="q-top"><div class="q-dots">${dots}</div><div class="muted sm">${z.i+1}/${z.qs.length}</div></div>
   <div class="q-q">${esc(q.q)}</div>
   <div class="q-choices">${q.choices.map((c,k)=>`<button class="q-ch" data-k="${k}" onclick="pickQuiz(${k})">${esc(c)}</button>`).join('')}</div>
   <div class="q-fact" id="qfact"></div>
   <button class="btn q-next" id="qnext" style="display:none" onclick="nextQuiz()">${last?'See what you unlocked':'Next question'}</button>
 </div>`);
}
function pickQuiz(k){
 const z=QZ;if(!z||z.picked!==null)return;z.picked=k;const q=z.qs[z.i];const right=q.answer;
 if(k===right)z.score++;
 document.querySelectorAll('#modal .q-ch').forEach(b=>{const kk=+b.dataset.k;b.classList.add('locked');
   if(kk===right)b.classList.add('right');else if(kk===k)b.classList.add('wrong');});
 const f=el('qfact');if(f){f.innerHTML=`<div class="q-verdict ${k===right?'ok':'no'}">${k===right?'Correct':'Not quite'}</div>`+(q.fact?`<div class="q-factt">${esc(q.fact)}</div>`:'');f.classList.add('show');}
 const nx=el('qnext');if(nx)nx.style.display='';
}
function nextQuiz(){const z=QZ;z.i++;z.picked=null;if(z.i>=z.qs.length)finishQuiz();else renderQuiz();}
async function finishQuiz(){
 const z=QZ;
 sheet(`<div class="quiz"><div class="q-reveal"><div class="muted sm" style="text-align:center;padding:24px 0"><span class="spinner"></span><br>Unlocking your reward…</div></div></div>`);
 let r;try{r=await api('/api/quiz/'+z.eid+'/complete',{method:'POST',body:JSON.stringify({device:deviceToken(),name:myName()||'',score:z.score,total:z.qs.length})});}catch(e){r=null;}
 if(!r||r.error){toast('Could not save — try again');closeSheet();return;}
 addMiles(r.miles||0);
 if(QUIZ[z.eid]){QUIZ[z.eid].progress={best:r.best,total:r.total,completed:1};QUIZ[z.eid].reward=r.reward;}
 const stars=starsFor(r.best,r.total||z.qs.length);
 sheet(`<div class="quiz"><div class="q-reveal show">
   <div class="reveal-stamp">${ic('sparkle')}</div>
   <div class="reveal-title">Unlocked!</div>
   <div class="reveal-score">${stars} · ${r.best}/${r.total} right · <b>+${r.miles} miles</b></div>
   <div class="reward-card unlocked big"><div class="reward-h">Secret of ${esc(placeName(z.eid))}</div><div class="reward-b">${esc(r.reward||'')}</div></div>
   <button class="btn" onclick="closeQuiz(1)">${r.first_clear?'Add it to my trip':'Nice'}</button>
 </div></div>`);
}
function closeQuiz(refresh){closeSheet();const eid=QZ?QZ.eid:null;QZ=null;if(refresh&&eid!=null)renderGame(eid);}
function renderPlaceDetail(e){const t=TRIP;
 const photos=(t.photos||[]).filter(p=>p.entry_id===e.id);
 let h=`<button class="btn ghost sm" onclick="backToPlaces()" style="margin-bottom:12px">‹ All places</button>
  <div class="tabhead"><h2>${esc(e.place)}</h2></div>
  <div class="muted sm" style="margin:-2px 0 2px">${esc(e.date||'')}${e.companions?' · with '+esc(e.companions):''}</div>`;
 // 0) The game — learn this place, unlock a hidden piece of the trip
 h+=gameUI(e);
 // 1) About here — the AI guide, broken into subsections
 h+=`<div class="secgroup"><div class="gh"><h2>${ic('compass')} About here</h2><span class="sub">your guide to ${esc(e.place)}</span></div>
   <div id="secs"><div class="muted sm"><span class="spinner"></span>Loading the guide…</div></div>
   <button class="btn ghost sm" id="genAllBtn" onclick="genAll(${e.id})" style="margin-top:4px;display:none">${ic('sparkle')} Generate all sections</button></div>`;
 // 2) Book this trip — destination-aware deep links
 h+=bookingUI(e);
 // 3) Your journal
 h+=`<div class="secgroup"><div class="gh"><h2>${ic('pen')} Your journal</h2></div>`;
 if((e.experience||'').trim())h+=`<div class="subsec"><div class="body">${esc(e.experience)}</div></div>`;
 if((e.ideas||'').trim())h+=`<div class="subsec"><div class="shd"><span class="ic18">${ic('bulb',18)}</span><span class="ti">Ideas I grappled with</span></div><div class="body">${esc(e.ideas)}</div></div>`;
 if(!(e.experience||'').trim()&&!(e.ideas||'').trim())h+=`<div class="subsec empty"><div class="hint">No journal here yet — write it, or let the Keeper offer prompts.</div></div>`;
 h+=`<div class="toolbar">
   <button class="btn sm ghost" onclick="journalSession(${e.id})">${ic('book')} Journal this place</button>
   <button class="btn sm ghost" onclick="polish(${e.id})">${ic('pen')} Polish</button>
   <button class="btn sm ghost" onclick="editEntry(${e.id})">${ic('edit')} Edit place</button></div></div>`;
 // 3) Photos for this place
 h+=`<div class="secgroup"><div class="gh"><h2>${ic('camera')} Photos</h2><span class="sub">${photos.length}</span></div>`;
 if(photos.length){h+=`<div class="gallery">`;for(const p of photos)h+=`<img loading="lazy" src="${BASE}/photo/${p.filename}" onclick="openPhoto(${p.id})">`;h+=`</div>`;}
 h+=`<label class="btn sm ghost" style="cursor:pointer;margin-top:10px;display:inline-block;width:auto">${ic('camera')} Add photos<input type="file" accept="image/*" multiple style="display:none" onchange="uploadPhotos(${e.id},this)"></label></div>`;
 el('app').innerHTML=h;
 loadSections(e.id);
 loadGame(e.id);
}

async function loadSections(eid){
 try{const d=await api('/api/sections/'+eid);SECDATA[eid]=d.sections||{};}catch(e){SECDATA[eid]={};}
 renderSecs(eid);
}
function renderSecs(eid){const box=el('secs');if(!box)return;
 const data=SECDATA[eid]||{};let allDone=true,h='';
 for(const [kind,icn,title,hint] of SECS){
  const s=data[kind];const has=s&&(s.content||'').trim();
  if(GENS.has(gk(eid,kind))){
   h+=`<div class="subsec"><div class="shd"><span class="ic18">${ic(icn,18)}</span><span class="ti">${title}</span></div>
     <div class="hint"><span class="spinner"></span>Writing your ${title.toLowerCase()}…</div></div>`;
   allDone=false;continue;
  }
  if(has){
   const vers=(s.versions||[]).length;
   h+=`<div class="subsec"><div class="shd"><span class="ic18">${ic(icn,18)}</span><span class="ti">${title}</span>
     ${vers>1?`<span class="ver" onclick="showVersions(${eid},'${kind}')">${ic('clock')} v${vers}</span>`:''}
     <button class="iconbtn" title="Regenerate" onclick="confirmRegen(${eid},'${kind}')">${ic('refresh')}</button></div>
     <div class="body">${esc(s.content)}</div></div>`;
  }else{
   allDone=false;
   h+=`<div class="subsec empty"><div class="shd"><span class="ic18">${ic(icn,18)}</span><span class="ti">${title}</span>
     <button class="btn sm" style="width:auto" onclick="genSection(${eid},'${kind}')">Generate</button></div>
     <div class="hint">${hint}</div></div>`;
  }
 }
 box.innerHTML=h;
 const gb=el('genAllBtn');if(gb)gb.style.display=allDone?'none':'';
}
async function genSection(eid,kind){
 if(GENS.has(gk(eid,kind)))return;GENS.add(gk(eid,kind));renderSecs(eid);
 let r;try{r=await api('/api/section',{method:'POST',body:JSON.stringify({entry_id:eid,kind})});}catch(e){r=null;}
 GENS.delete(gk(eid,kind));
 if(r&&r.section){SECDATA[eid]=SECDATA[eid]||{};SECDATA[eid][kind]=r.section;}
 else toast((r&&r.error)||'Could not generate — try again');
 renderSecs(eid);
}
function confirmRegen(eid,kind){const title=(SECS.find(s=>s[0]===kind)||[])[2]||kind;
 sheet(`<h2>Regenerate ${esc(title)}?</h2>
  <p class="muted sm">I'll write a fresh version with AI. Your current ${esc(title)} is kept in version history, so you can switch back anytime.</p>
  <div style="margin-top:14px"><button class="btn" onclick="doRegen(${eid},'${kind}')">${ic('refresh')} Regenerate</button>
   <button class="btn ghost" style="margin-top:8px" onclick="closeSheet()">Cancel</button></div>`);}
async function doRegen(eid,kind){closeSheet();await genSection(eid,kind);}
async function genAll(eid){const gb=el('genAllBtn');if(gb){gb.disabled=true;gb.innerHTML='<span class="spinner"></span>Generating…';}
 for(const [kind] of SECS){const s=(SECDATA[eid]||{})[kind];if(s&&(s.content||'').trim())continue;await genSection(eid,kind);}
}
function showVersions(eid,kind){const s=(SECDATA[eid]||{})[kind];if(!s)return;
 const title=(SECS.find(x=>x[0]===kind)||[])[2]||kind;
 let h=`<h2>${ic('clock')} ${esc(title)} — versions</h2><p class="muted sm">Every regeneration is saved. Switch back to any one.</p><div class="verlist" style="margin-top:12px">`;
 for(const v of (s.versions||[])){const cur=v.id===s.active_id;
  h+=`<div class="vrow ${cur?'cur':''}"><div class="vmeta"><span class="when">${esc(fmtTime(v.created))}${cur?' · current':''}</span>
    ${cur?'':`<button class="btn sm" style="width:auto" onclick="restoreVersion(${eid},'${kind}',${v.id})">Use this</button>`}</div>
    <div class="vtext">${esc(v.content)}</div></div>`;}
 h+=`</div>`;sheet(h);
}
async function restoreVersion(eid,kind,vid){
 let r;try{r=await api('/api/section/restore',{method:'POST',body:JSON.stringify({id:vid})});}catch(e){r=null;}
 if(r&&r.section){SECDATA[eid][kind]=r.section;closeSheet();renderSecs(eid);toast('Switched version');}
 else toast('Could not switch version');
}

function renderPhotos(){const t=TRIP;
 let h=`<div class="tabhead"><h2>${ic('camera')} Photos</h2>
  <label class="btn sm" style="cursor:pointer">${ic('plus')} Add photos<input type="file" accept="image/*" multiple style="display:none" onchange="uploadPhotos(null,this)"></label><button class="btn sm ghost" style="width:auto" onclick="importICloud()">☁️ iCloud link</button></div>`;
 h+=`<div class="muted sm" style="margin:2px 2px 0">Tap <b>Add photos</b> — or drag &amp; drop images anywhere to upload.</div>`;
 h+=galleryHTML(t);
 el('app').innerHTML=h;
}
// assign photos to a place so they pin there on the map (used when they have no embedded GPS)
function assignPhotoSheet(ids){const es=TRIP.entries||[];
 if(!ids||!ids.length)return toast('No photos to assign');
 if(!es.length)return toast('Add a place first, then assign photos to it');
 let h=`<h2>${ic('pin')} Put ${ids.length} photo${ids.length!==1?'s':''} on the map</h2>
  <p class="muted sm">Pick the place ${ids.length!==1?'they':'it'} belong${ids.length!==1?'':'s'} to — ${ids.length!==1?'they':'it'}'ll pin there on the map, even without embedded GPS.</p>
  <div style="margin-top:10px"></div>`;
 for(const e of es)h+=`<div class="triprow" onclick='assignPhotos(${JSON.stringify(ids)},${e.id})'>
   <div class="cv">${ic('pin',22)}</div><div style="flex:1;min-width:0"><b>${esc(e.place)}</b>
   <div class="muted sm">${esc(e.date||'')}${e.companions?' · with '+esc(e.companions):''}</div></div></div>`;
 sheet(h);
}
async function assignPhotos(ids,eid){
 await api('/api/photos/assign',{method:'POST',body:JSON.stringify({ids,entry_id:eid})});
 closeSheet();const lb=el('lightbox');if(lb)lb.remove();
 toast(`${ids.length} photo${ids.length!==1?'s':''} will now map at that place`);
 openTrip(TRIP.id);
}

function renderMemories(){const t=TRIP;
 let h=`<div class="tabhead"><h2>${ic('film')} Memories</h2>
  <button class="btn sm" onclick="collageStudio()">${ic('palette')} Make a collage</button></div>
  <button class="btn ghost" onclick="tripRecap()">${ic('book')} Write a trip recap</button><div id="recap"></div>`;
 if(t.collages&&t.collages.length){
  for(const c of t.collages){h+=`<div class="card collage" style="margin-top:12px"><img src="${BASE}/collage/${c.filename}">
   <div class="toolbar"><a class="btn sm ghost" href="${BASE}/collage/${c.filename}" download>Download</a>
   <button class="btn sm ghost danger" onclick="delCollage(${c.id})">Remove</button></div></div>`;}
 }else{h+=`<div class="empty">No collages yet.<br>Tap <b>Make a collage</b> to blend your photos into art.</div>`;}
 el('app').innerHTML=h;
}

let photoFilter='All';
function galleryHTML(t){
 const photos=t.photos||[];
 if(!photos.length)return `<div class="card"><h2>${ic('camera')} Photos</h2>
  <div class="muted sm">No photos yet. Tap <b>Add photos</b> above — a quick AI sorts each one by people, place, food, and more.</div></div>`;
 // counts by category
 const counts={};for(const p of photos){const c=p.category||'Other';counts[c]=(counts[c]||0)+1;}
 const cats=Object.keys(counts).sort((a,b)=>counts[b]-counts[a]);
 if(photoFilter!=='All'&&!counts[photoFilter])photoFilter='All';
 const shown=photoFilter==='All'?photos:photos.filter(p=>(p.category||'Other')===photoFilter);
 SHOWN=shown.map(p=>p.id);
 const unplaced=photos.filter(p=>!p.entry_id).length;
 let h=`<div class="card"><h2>${ic('camera')} Photos <span class="muted sm">· ${photos.length}</span></h2>`;
 if(unplaced)h+=`<div class="subsec" style="margin:8px 0 2px;border-style:dashed"><div class="hint">${ic('pin')} ${unplaced} photo${unplaced!==1?'s aren\'t':' isn\'t'} on the map yet — assign ${unplaced!==1?'them':'it'} to a place to pin ${unplaced!==1?'them':'it'}.</div>
   <div class="toolbar"><button class="btn sm" style="width:auto" onclick="openBacklog()">🗂 Sort backlog (${unplaced})</button><button class="btn sm ghost" style="width:auto" onclick="autoMatchPhotos()">✨ Auto-match</button><button class="btn sm ghost" style="width:auto" onclick="assignPhotoSheet(SHOWN)">${ic('pin')} Assign shown</button></div></div>`;
 h+=`<div class="filters"><span class="fil ${photoFilter==='All'?'on':''}" onclick="setPF('All')">All ${photos.length}</span>`;
 for(const c of cats)h+=`<span class="fil ${photoFilter===c?'on':''}" onclick="setPF('${c.replace(/'/g,"")}')">${esc(c)} ${counts[c]}</span>`;
 h+=`</div><div class="pgrid">`;
 for(const p of shown)h+=`<div class="pthumb" onclick="openPhoto(${p.id})"><img loading="lazy" src="${BASE}/photo/${p.filename}">
   ${p.member?`<span class="pthumb-av">${avatarHTML(p.member,memberColor(p.member),18)}</span>`:''}
   <div class="lab">${esc(p.category||'Other')}${p.entry_id?' '+ic('pin',11):''}</div></div>`;
 h+=`</div></div>`;
 return h;
}
function setPF(c){photoFilter=c;renderPhotos();}
function openPhoto(id){const p=(TRIP.photos||[]).find(x=>x.id===id);if(!p)return;
 let tags=[];try{tags=JSON.parse(p.tags||'[]');}catch(e){}
 const lb=document.createElement('div');lb.className='lightbox';lb.id='lightbox';
 lb.onclick=e=>{if(e.target===lb)lb.remove();};
 const ent=p.entry_id?(TRIP.entries||[]).find(e=>e.id===p.entry_id):null;
 const hasGps=(p.lat!=null&&p.lon!=null);
 const placeline=ent?`${ic('pin')} ${esc(ent.place)}`:(hasGps?`${ic('pin')} located by GPS`:`${ic('pin')} not on the map yet`);
 lb.innerHTML=`<span class="close" onclick="document.getElementById('lightbox').remove()">✕</span>
  <img src="${BASE}/photo/${p.filename}">
  <div class="info"><div class="cap">${esc(p.caption||'')}</div>
  <div class="meta"><span class="chip">${esc(p.category||'Other')}</span>
  ${tags.map(t=>`<span class="chip">#${esc(t)}</span>`).join(' ')}
  <span class="chip">${placeline}</span>
  ${p.member?`<span class="chip">${avatarHTML(p.member,memberColor(p.member),16)} ${esc(p.member)}</span>`:''}</div>
  <div class="toolbar" style="justify-content:center">
  <button class="btn sm ghost" onclick="assignPhotoSheet([${p.id}])">${ic('pin')} ${ent?'Change place':'Assign to a place'}</button>
  ${ent?(ent.cover===p.filename?`<button class="btn sm ghost" disabled>★ Location photo ✓</button>`:`<button class="btn sm ghost" onclick="setPlaceCover(${ent.id},${p.id})">★ Set as location photo</button>`):''}
  <a class="btn sm ghost" href="${BASE}/photo/${p.filename}" download>Download</a>
  <button class="btn sm ghost danger" onclick="delPhoto(${p.id})">Delete</button></div></div>`;
 document.body.appendChild(lb);
}
async function delPhoto(id){const lb=el('lightbox');if(lb)lb.remove();
 await api('/api/photos/'+id,{method:'DELETE'});openTrip(TRIP.id);}
async function autoMatchPhotos(){
 let r;try{r=await api('/api/photos/automatch',{method:'POST',body:JSON.stringify({trip_id:TRIP.id})});}catch(e){r=null;}
 if(r&&r.ok) alert(r.matched? ('Matched '+r.matched+' photo'+(r.matched!==1?'s':'')+' to locations by GPS.') : 'No new matches — photos need GPS near a place, or a place name in their caption.');
 openTrip(TRIP.id);}
async function setPlaceCover(eid,pid){
 const p=(TRIP.photos||[]).find(x=>x.id===pid);if(!p)return;
 const lb=el('lightbox');if(lb)lb.remove();
 try{await api('/api/entries/cover',{method:'POST',body:JSON.stringify({entry_id:eid,filename:p.filename})});}catch(e){}
 openTrip(TRIP.id);}

// ---- import a whole public iCloud Shared Album by link ----
// In-page sheet (not window.prompt — that's silently dropped inside the iOS
// WebView wrapper, which made the importer look broken on the phone).
function importICloud(){
 sheet(`<h2>☁️ Import from iCloud</h2>
  <p style="margin:2px 0 14px;font-size:13px;line-height:1.5;color:#8b93a7">Paste a <b>public</b> iCloud link —
   a Shared Album (Photos → Shared Album → turn on <b>Public Website</b> → copy the link) or an iCloud
   <b>shared link</b> (icloud.com/photos/…). A personal library link won't work.</p>
  <label>iCloud link</label>
  <input id="f_icloud" type="url" inputmode="url" autocapitalize="off" autocorrect="off" spellcheck="false"
   placeholder="https://share.icloud.com/photos/…">
  <div style="margin-top:16px"><button class="btn" id="icloudgo" onclick="startICloudImport()">Import photos</button></div>`);
 setTimeout(()=>{const i=el('f_icloud');if(i)i.focus();},60);
}
async function startICloudImport(){
 const i=el('f_icloud');const url=((i&&i.value)||'').trim();
 if(!url)return toast('Paste an iCloud link first');
 const btn=el('icloudgo');if(btn){btn.disabled=true;btn.textContent='Starting…';}
 const reset=()=>{if(btn){btn.disabled=false;btn.textContent='Import photos';}};
 let r;
 try{r=await api('/api/import/icloud',{method:'POST',body:JSON.stringify({trip_id:TRIP.id,url})});}
 catch(e){reset();return toast((e&&e.message)||'Could not start the import.');}
 if(!r||!r.job_id){reset();return toast((r&&r.error)||'Could not start the import.');}
 closeSheet();
 renderImp({state:'running',done:0,total:0});
 watchImport(r.job_id);
}

// ---- backlog: Tinder-style swipe sorter for photos we couldn't auto-place ----
let BL=null, BLi=0;
async function openBacklog(){
 let d;try{d=await api('/api/backlog/'+TRIP.id);}catch(e){d=null;}
 if(!d||!d.photos||!d.photos.length){alert('Backlog is empty — every photo is already sorted into a place.');return;}
 if(!d.places.length){alert('Add a place first (in the Places tab), then you can sort photos into it.');return;}
 BL=d;BLi=0;
 const ov=document.createElement('div');ov.className='swipe-ov';ov.id='swipeov';
 ov.innerHTML=`<div class="swipe-top"><span class="ttl">🗂 Sort backlog</span><span class="cnt" id="swcnt"></span>
   <button class="btn sm ghost" onclick="closeBacklog()">Done</button></div>
  <div class="swipe-stage" id="swstage"></div>
  <div class="swipe-places" id="swplaces"></div>
  <div class="swipe-actions">
   <button class="sw-del" onclick="blDelete()">🗑 Delete</button>
   <button class="sw-skip" onclick="blSkip()">⏭ Skip</button>
   <button class="sw-acc" id="swacc" onclick="blAcceptSuggest()">✓ Place</button></div>`;
 document.body.appendChild(ov);renderCard();
}
function closeBacklog(){const o=el('swipeov');if(o)o.remove();BL=null;openTrip(TRIP.id);}
function renderCard(){
 const stage=el('swstage');if(!stage)return;const total=BL.photos.length;
 el('swcnt').textContent=Math.min(BLi+1,total)+' / '+total;
 if(BLi>=total){stage.innerHTML=`<div class="swipe-empty"><div style="font-size:34px">🎉</div><div>Backlog cleared.</div>
   <button class="btn" onclick="closeBacklog()">Done</button></div>`;el('swplaces').innerHTML='';
   el('swacc').disabled=true;return;}
 const p=BL.photos[BLi];
 const places=[...BL.places].sort((a,b)=>((b.id===p.suggest)?1:0)-((a.id===p.suggest)?1:0));
 el('swplaces').innerHTML=places.map(pl=>`<button class="pl${pl.id===p.suggest?' sug':''}" onclick="blAssign(${pl.id})">${pl.id===p.suggest?'✓ ':''}${esc(pl.place)}</button>`).join('')
   +`<button class="pl" onclick="blNewPlace()">➕ New place</button>`;
 const acc=el('swacc');acc.textContent=p.suggest_place?('✓ '+p.suggest_place):'Pick a place';acc.disabled=!p.suggest;
 const card=document.createElement('div');card.className='swipe-card';card.id='swcard';
 card.innerHTML=`<img src="${BASE}/photo/${p.filename}">
  <div class="cardmeta"><div class="cap">${esc(p.caption||'(no caption)')}</div>
  <div class="chips"><span class="chip">${esc(p.category)}</span>${p.has_gps?'<span class="chip">📍 GPS</span>':''}${(p.tags||[]).slice(0,4).map(t=>`<span class="chip">#${esc(t)}</span>`).join('')}</div></div>
  <div class="swipe-stamp yes" id="stampyes">PLACE</div><div class="swipe-stamp no" id="stampno">SKIP</div>`;
 stage.innerHTML='';stage.appendChild(card);attachSwipe(card,p);
}
function attachSwipe(card,p){
 let sx=0,sy=0,dx=0,dragging=false;
 card.addEventListener('pointerdown',e=>{dragging=true;sx=e.clientX;sy=e.clientY;try{card.setPointerCapture(e.pointerId);}catch(_){}card.style.transition='none';});
 card.addEventListener('pointermove',e=>{if(!dragging)return;dx=e.clientX-sx;const dy=e.clientY-sy;
  card.style.transform=`translate(${dx}px,${dy*0.25}px) rotate(${dx/18}deg)`;
  const y=el('stampyes'),n=el('stampno');if(y)y.style.opacity=Math.max(0,Math.min(1,dx/90));if(n)n.style.opacity=Math.max(0,Math.min(1,-dx/90));});
 const end=()=>{if(!dragging)return;dragging=false;card.style.transition='transform .25s ease, opacity .25s ease';
  if(dx>100){if(p.suggest){flyOut(card,1);blAssign(p.suggest,true);}else snapBack(card);}
  else if(dx<-100){flyOut(card,-1);blSkip(true);}
  else snapBack(card);dx=0;};
 card.addEventListener('pointerup',end);card.addEventListener('pointercancel',end);
}
function snapBack(card){card.style.transform='';const y=el('stampyes'),n=el('stampno');if(y)y.style.opacity=0;if(n)n.style.opacity=0;}
function flyOut(card,dir){card.style.transform=`translate(${dir*innerWidth*1.2}px,0) rotate(${dir*22}deg)`;card.style.opacity=0;}
async function blAssign(eid,fromSwipe){const p=BL.photos[BLi];if(!p)return;
 try{await api('/api/photos/assign',{method:'POST',body:JSON.stringify({ids:[p.id],entry_id:eid})});}catch(e){}
 BLi++;setTimeout(renderCard,fromSwipe?200:0);}
function blAcceptSuggest(){const p=BL.photos[BLi];if(p&&p.suggest)blAssign(p.suggest);}
function blSkip(fromSwipe){BLi++;setTimeout(renderCard,fromSwipe?200:0);}
async function blDelete(){const p=BL.photos[BLi];if(!p)return;
 try{await api('/api/photos/'+p.id,{method:'DELETE'});}catch(e){}
 BLi++;renderCard();}
async function blNewPlace(){const name=prompt('New place name:');if(!name||!name.trim())return;
 let r;try{r=await api('/api/entries',{method:'POST',body:JSON.stringify({trip_id:TRIP.id,place:name.trim()})});}catch(e){r=null;}
 if(r&&r.id){BL.places.push({id:r.id,place:name.trim()});blAssign(r.id);}}

// ---- geo map of the trip (MapLibre GL — satellite basemap, two-finger tilt + rotate) ----
function loadMapLibre(cb){
 if(window.maplibregl)return cb();
 const css=document.createElement('link');css.rel='stylesheet';
 css.href='https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css';document.head.appendChild(css);
 const s=document.createElement('script');s.src='https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js';
 s.onload=cb;s.onerror=()=>toast('Could not load the map library (need internet)');document.head.appendChild(s);
}
const MAP_STYLE={version:8,sources:{
  esri:{type:'raster',tiles:['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],tileSize:256,attribution:'Esri, Maxar, Earthstar Geographics',maxzoom:18},
  lbl:{type:'raster',tiles:['https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}'],tileSize:256,maxzoom:18}},
 layers:[{id:'esri',type:'raster',source:'esri'},{id:'lbl',type:'raster',source:'lbl',paint:{'raster-opacity':0.9}}]};
// a custom-HTML marker; the content lives in a child so MapLibre's transform never fights our CSS animations
function mkMarker(contentEl,lnglat){const w=document.createElement('div');w.appendChild(contentEl);
 return new maplibregl.Marker({element:w,anchor:'center'}).setLngLat(lnglat).addTo(MAPOBJ);}
async function openMap(){
 el('app').innerHTML=`<div class="tabhead"><h2>${ic('map')} Map</h2></div>
  <div class="muted sm" id="mapnote">Plotting your journey…</div>
  <div id="mapwrap" style="position:relative;margin-top:10px">
   <div id="map"></div>
   <button id="mapfs" class="mapfs" onclick="toggleMapFull()" title="Full screen">⛶</button>
  </div>
  <button class="btn sm ghost" id="placeBtn" style="width:auto;margin-top:10px" onclick="placePhotos()">${ic('pin')} Place photos on map</button>`;
 const data=await api('/api/map/'+TRIP.id);
 loadMapLibre(()=>renderMap(data));
}
async function placePhotos(){
 const btn=el('placeBtn');if(btn){btn.disabled=true;btn.innerHTML='<span class="spinner"></span> Scanning photos…';}
 let r;try{r=await api('/api/photos/backfill-gps',{method:'POST',body:JSON.stringify({trip_id:TRIP.id})});}catch(e){r=null;}
 if(!r){toast('Could not scan right now');if(btn){btn.disabled=false;btn.innerHTML='Place photos on map';}return;}
 toast(r.placed?`Placed ${r.placed} photo${r.placed!==1?'s':''} on the map`:'No new photos with embedded GPS');
 openMap();  // refresh with the newly-placed pins
}
// Geolocation-first map: every photo is pinned at its OWN GPS (EXIF), then grouped by
// MapLibre's built-in clustering (supercluster: a hierarchical KD-tree precomputed per
// zoom level — the same family of algorithm MapKit uses for Apple Photos/Maps). Clusters
// split as you zoom, so a hike 10 miles out of town folds into the city at low zoom and
// peels off to its true spot as you zoom in. Pan/zoom stays fast because we only ever
// render the handful of clusters currently in view (queried on moveend), not every photo.
function renderMap(data){
 const photos=(data.photos||[]),places=(data.places||[]);
 const note=el('mapnote');
 if(!photos.length&&!places.length){note.innerHTML='No locations yet. Upload photos taken with location on, or add places — I\'ll map them. <span class="muted">(iOS: Settings → Privacy → Location → Camera = While Using, and Camera settings → keep location.)</span>';return;}
 note.innerHTML=photos.length
  ? `${photos.length} geotagged photo${photos.length!==1?'s':''} · pinch to zoom · tap a stack to zoom in, a photo to open it.`
  : `${places.length} place${places.length!==1?'s':''} · upload geotagged photos to pin your journey.`;
 const map=new maplibregl.Map({container:'map',style:MAP_STYLE,center:MAPCENTER?[MAPCENTER[1],MAPCENTER[0]]:[20,8],zoom:2.4,pitch:0,bearing:0,attributionControl:true,dragRotate:true});
 MAPOBJ=map;RAD=null;COLLAGES=data.collages||[];MAPCENTER=data.center||null;MAPPLACES=places;PLACEMARKERS={};
 CLUSMARKERS={};REPCACHE={};
 map.on('load',()=>{
  // faint date-ordered route between the trip's destinations — context only, never the container
  if(places.length>1){try{map.addSource('route',{type:'geojson',data:{type:'Feature',geometry:{type:'LineString',coordinates:places.map(p=>[p.lon,p.lat])}}});
   map.addLayer({id:'route',type:'line',source:'route',paint:{'line-color':'#8b7cf6','line-width':2,'line-opacity':0.3,'line-dasharray':[2,2]}});}catch(_){}}
  // the clustered photo source
  const feats=photos.filter(p=>p.lat!=null&&p.lon!=null).map(p=>({type:'Feature',
   geometry:{type:'Point',coordinates:[p.lon,p.lat]},
   properties:{id:p.id,file:p.filename,cap:p.caption||''}}));
  try{
   map.addSource('photos',{type:'geojson',data:{type:'FeatureCollection',features:feats},cluster:true,clusterRadius:60,clusterMaxZoom:17});
   // invisible circle layer so the source's tiles load & stay queryable as we pan/zoom
   map.addLayer({id:'photo-src',type:'circle',source:'photos',paint:{'circle-radius':0,'circle-opacity':0}});
  }catch(_){}
  // frame the journey on the actual photos (fall back to places)
  const bpts=feats.length?feats.map(f=>f.geometry.coordinates):places.map(p=>[p.lon,p.lat]);
  if(bpts.length>1){const b=new maplibregl.LngLatBounds();bpts.forEach(p=>b.extend(p));
   map.fitBounds(b,{padding:54,maxZoom:14,duration:0});}
  else if(bpts.length===1){map.jumpTo({center:bpts[0],zoom:12});}
  map.on('moveend',refreshPhotoClusters);
  map.on('data',e=>{if(e.sourceId==='photos'&&map.isSourceLoaded('photos'))refreshPhotoClusters();});
  refreshPhotoClusters();
 });
}
// Reconcile the on-screen marker set with whatever clusters/points the source reports for the
// current view. Only touches what changed, so repeated pan/zoom is cheap.
function refreshPhotoClusters(){
 const map=MAPOBJ;if(!map||!map.getSource('photos'))return;
 const src=map.getSource('photos');let feats;
 try{feats=map.querySourceFeatures('photos');}catch(_){return;}
 const want={};
 for(const f of feats){const pr=f.properties||{};
  if(pr.cluster){const k='c'+pr.cluster_id;if(!want[k])want[k]={type:'cluster',cid:pr.cluster_id,n:pr.point_count,ll:f.geometry.coordinates.slice()};}
  else{const k='p'+pr.id;if(!want[k])want[k]={type:'photo',pid:pr.id,file:pr.file,ll:f.geometry.coordinates.slice()};}}
 for(const k in CLUSMARKERS){if(!want[k]){try{CLUSMARKERS[k].remove();}catch(_){}delete CLUSMARKERS[k];}}
 for(const k in want){
  if(CLUSMARKERS[k]){try{CLUSMARKERS[k].setLngLat(want[k].ll);}catch(_){}continue;}
  const it=want[k];const node=document.createElement('div');
  if(it.type==='cluster'){
   node.className='pcl';const rep=REPCACHE[it.cid];
   node.innerHTML=`<div class="pcl-thumb${rep?'':' ph'}">${rep?`<img src="${BASE}/photo/${rep}">`:''}</div><div class="pcl-n">${it.n}</div>`;
   if(!rep){Promise.resolve(src.getClusterLeaves(it.cid,1,0)).then(lv=>{if(!lv||!lv[0])return;const fn=lv[0].properties.file;REPCACHE[it.cid]=fn;
    const t=node.querySelector('.pcl-thumb');if(t){t.classList.remove('ph');t.innerHTML=`<img src="${BASE}/photo/${fn}">`;}}).catch(()=>{});}
   node.addEventListener('click',ev=>{ev.stopPropagation();Promise.resolve(src.getClusterExpansionZoom(it.cid))
    .then(z=>map.easeTo({center:it.ll,zoom:Math.min((z||map.getZoom())+0.3,18),duration:650}))
    .catch(()=>map.easeTo({center:it.ll,zoom:Math.min(map.getZoom()+1.5,18),duration:650}));});
  }else{
   node.className='pdot';node.innerHTML=`<img loading="lazy" src="${BASE}/photo/${it.file}">`;
   node.addEventListener('click',ev=>{ev.stopPropagation();bigImage(BASE+'/photo/'+it.file);});
  }
  CLUSMARKERS[k]=mkMarker(node,it.ll);
 }
}
// a place's map pin content = its AI city totem (falls back to cover photo, then a numbered pin)
function placeEl(pl){
 const i=Math.max(0,MAPPLACES.indexOf(pl));const face=pl.landmark||pl.thumb;const d=document.createElement('div');
 if(face){d.className='pplace'+(pl.has_journal?' pjourn':'')+(pl.landmark?' totem':'');
  d.innerHTML=`<img src="${BASE}/photo/${face}"><div class="pnum">${i+1}</div>`
   +(pl.has_journal?`<div class="jbadge">${ic('book',12)}</div>`:'')
   +(pl.nphotos>1?`<div class="pcount">${pl.nphotos}</div>`:'');
 }else{d.className=pl.has_journal?'pin journ':'pin';d.innerHTML=`<span>${pl.has_journal?ic('book',14):(i+1)}</span>`;}
 return d;
}
function updatePlaceIcon(pl){const m=PLACEMARKERS[pl.id];if(!m)return;if(RAD&&RAD.hiddenId===pl.id)return;
 const c=m.getElement().firstChild;if(!c)return;const fresh=placeEl(pl);c.className=fresh.className;c.innerHTML=fresh.innerHTML;}
function startLandmarks(){
 api('/api/map/landmarks',{method:'POST',body:JSON.stringify({trip_id:TRIP.id})}).then(r=>{
  if(!r||!r.job_id)return;const note=el('mapnote');
  const poll=async()=>{let s;try{s=await api('/api/map/landmarks/status/'+r.job_id);}catch(e){s=null;}
   if(!s)return;
   (s.done_items||[]).forEach(di=>{const p=(MAPPLACES||[]).find(x=>x.id===di.id);if(p){p.landmark=di.landmark;updatePlaceIcon(p);}});
   if(RAD&&RAD.pl&&RAD.pl.landmark)radiateItems(RAD.center,RAD.items,RAD.pl); // refresh an open burst
   if(s.state==='running'){if(note&&s.total)note.textContent='Generating landmark totems… '+(s.done||0)+'/'+s.total;setTimeout(poll,2500);return;}
   if(note)note.textContent='Tap a location to radiate its memories.';
  };setTimeout(poll,2500);
 }).catch(()=>{});
}
function closePopupThenEntry(id){openTrip(TRIP.id);}
function toggleMapFull(){
 const w=el('mapwrap'),m=el('map'),b=el('mapfs');if(!w||!m)return;
 const full=m.classList.toggle('full');w.classList.toggle('full',full);
 if(b)b.textContent=full?'✕':'⛶';
 document.body.style.overflow=full?'hidden':'';
 setTimeout(()=>{if(MAPOBJ){MAPOBJ.resize();if(RAD)radiateItems(RAD.center,RAD.items,RAD.pl);}},220);
}

// ---- "radiate": fan a location's photos / journal / collages around its pin (Radiate-style) ----
// does a place have anything to radiate? (a landmark totem alone does NOT count)
function placeHasItems(pl){return (!!pl.pfiles&&pl.pfiles.length>0)||!!pl.has_journal||!!((pl.ideas||'').trim());}
function radiatePlace(pl){
 const items=(pl.pfiles||[]).map(f=>({t:'photo',f}));
 if(pl.has_journal)items.push({t:'journal'});
 if((pl.ideas||'').trim())items.push({t:'ideas'});
 if(!items.length){clearRadiate();if(MAPOBJ)MAPOBJ.easeTo({center:[pl.lon,pl.lat],zoom:Math.max(MAPOBJ.getZoom(),9),duration:600});toast('No photos at '+((pl&&pl.place)||'this spot')+' yet');return;}
 radiateItems([pl.lat,pl.lon],items,pl);
}
function clearRadiate(){
 if(RAD){(RAD.layer||[]).forEach(m=>{try{m.remove();}catch(_){}});
  if(RAD.hiddenId&&PLACEMARKERS[RAD.hiddenId]){const e2=PLACEMARKERS[RAD.hiddenId].getElement();if(e2)e2.style.display='';}}
 try{const s=MAPOBJ&&MAPOBJ.getSource&&MAPOBJ.getSource('radlines');if(s)s.setData({type:'FeatureCollection',features:[]});}catch(_){}
 RAD=null;
}
function radiateItems(center,items,pl){
 clearRadiate();if(!MAPOBJ||!items.length)return;
 // the landmark totem owns the centre — hide the place's own pin while its burst is open
 let hiddenId=null;
 if(pl&&pl.id&&PLACEMARKERS[pl.id]){const e2=PLACEMARKERS[pl.id].getElement();if(e2){e2.style.display='none';hiddenId=pl.id;}}
 // ---- concentric orbit: rings fan OUTWARD, each holding as many as its circumference fits.
 //      how many photos we show scales with the real screen room to the nearest other city,
 //      so a zoomed-in / isolated city spreads far more memories than a crowded one. ----
 const specials=items.filter(it=>it.t==='journal'||it.t==='ideas');
 const imgs=items.filter(it=>it.t==='photo'||it.t==='collage');
 const cpt=MAPOBJ.project([center[1],center[0]]);   // [lng,lat] -> screen px
 // distance (screen px) to the nearest OTHER city — our room before bursts would collide
 let nearest=Infinity;
 (MAPPLACES||[]).forEach(o=>{if(!o||(pl&&o.id===pl.id))return;const p=MAPOBJ.project([o.lon,o.lat]);
  const d=Math.hypot(p.x-cpt.x,p.y-cpt.y);if(d<nearest)nearest=d;});
 const mc=MAPOBJ.getContainer();const vp=Math.min(mc.clientWidth||innerWidth,mc.clientHeight||innerHeight);
 const maxR=Math.max(88, Math.min(vp*0.46, nearest===Infinity?vp*0.46:nearest*0.46));
 // ring radii out to maxR; each ring fits floor(circumference / 58px) satellites (46px + gap)
 const SAT=58,R0=78,STEP=56,RINGCAP=8;
 const rings=[];let total=0;
 for(let r=R0;r<=maxR+1&&rings.length<RINGCAP;r+=STEP){const k=Math.max(3,Math.floor((2*Math.PI*r)/SAT));rings.push({r,k});total+=k;}
 if(!rings.length){const k=Math.max(3,Math.floor((2*Math.PI*R0)/SAT));rings.push({r:R0,k});total=k;}
 const HARD=60,slots=Math.min(total,HARD);
 // journal/ideas always kept in the inner ring; photos fill the rest; overflow -> a "+N" bubble
 let roomImgs=Math.max(0,slots-specials.length);
 let showImgs=imgs.slice(0,roomImgs);
 let extra=imgs.length-showImgs.length;
 if(extra>0&&specials.length+showImgs.length>=slots){showImgs=showImgs.slice(0,Math.max(0,slots-specials.length-1));extra=imgs.length-showImgs.length;}
 let show=specials.concat(showImgs);
 if(extra>0)show.push({t:'more',n:extra});
 const n=show.length;const markers=[];const feats=[];let idx=0;
 for(let ri=0;ri<rings.length&&idx<n;ri++){
  const r=rings[ri].r, cnt=Math.min(rings[ri].k,n-idx), off=(ri%2)?(180/Math.max(cnt,1)):0;
  for(let j=0;j<cnt;j++,idx++){
   const ang=(-90+off+j*(360/cnt))*Math.PI/180;
   const ll=MAPOBJ.unproject([cpt.x+r*Math.cos(ang),cpt.y+r*Math.sin(ang)]);
   feats.push({type:'Feature',geometry:{type:'LineString',coordinates:[[center[1],center[0]],[ll.lng,ll.lat]]}});
   const it=show[idx];const c=document.createElement('div');
   if(it.t==='photo'){c.className='rsat';c.innerHTML=`<img src="${BASE}/photo/${it.f}">`;}
   else if(it.t==='collage'){c.className='rsat col';c.innerHTML=`<img src="${BASE}/collage/${it.f}">`;}
   else if(it.t==='journal'){c.className='rsat ic';c.innerHTML=ic('book',20);}
   else if(it.t==='ideas'){c.className='rsat ic';c.innerHTML=ic('bulb',20);}
   else{c.className='rsat ic more';c.textContent='+'+it.n;}
   c.addEventListener('click',ev=>{ev.stopPropagation();radiateTap(it,pl);});
   markers.push(mkMarker(c,[ll.lng,ll.lat]));
  }
 }
 // centre hub: the landmark totem + the place label
 const hub=document.createElement('div');hub.className='rhubwrap';const hasTot=pl&&pl.landmark;
 hub.innerHTML=(hasTot?`<div class="rtotem"><img src="${BASE}/photo/${pl.landmark}"></div>`:'')
   +`<div class="rhub${hasTot?' up':''}">${esc((pl&&pl.place)||'✨')}</div>`;
 markers.push(mkMarker(hub,[center[1],center[0]]));
 try{MAPOBJ.getSource('radlines').setData({type:'FeatureCollection',features:feats});}catch(_){}
 RAD={center,items,layer:markers,pl,hiddenId};
}
function radiateTap(it,pl){
 if(it.t==='photo')bigImage(BASE+'/photo/'+it.f);
 else if(it.t==='collage')bigImage(BASE+'/collage/'+it.f);
 else if(it.t==='more'){if(RAD&&MAPOBJ)MAPOBJ.easeTo({center:[RAD.center[1],RAD.center[0]],zoom:Math.min(MAPOBJ.getZoom()+2,16)});}
 else if(pl&&pl.id){goTab('places');openPlace(pl.id);}
}
function bigImage(url){const lb=document.createElement('div');lb.className='lightbox';lb.id='lightbox';
 lb.onclick=()=>lb.remove();lb.innerHTML=`<span class="close" onclick="document.getElementById('lightbox').remove()">✕</span><img src="${url}">`;
 document.body.appendChild(lb);}

function newEntry(){editEntryForm(null);}
function editEntry(id){editEntryForm((TRIP.entries||[]).find(e=>e.id===id));}
function editEntryForm(e){e=e||{};
 screen(`<h2>${e.id?'Edit place':'Add a place'}</h2>
 <label>Place</label><input id="e_place" value="${esc(e.place||'')}" placeholder="Sintra, Pena Palace">
 <div class="row"><div><label>Date</label><input id="e_date" type="date" value="${esc(e.date||'')}"></div>
 <div><label>Who with</label><input id="e_comp" value="${esc(e.companions||'')}" placeholder="Maya, Leo"></div></div>
 <label>The experience</label><textarea id="e_exp" placeholder="What happened, how it felt...">${esc(e.experience||'')}</textarea>
 <label>Ideas I grappled with</label><textarea id="e_ideas" placeholder="Thoughts, questions, things that shifted...">${esc(e.ideas||'')}</textarea>
 <div style="margin-top:16px"><button class="btn" onclick="saveEntry(${e.id||'null'})">Save place</button></div>
 ${e.id?`<hr class="sep"><button class="btn sm ghost danger" onclick="delEntry(${e.id})">${ic('trash')} Delete this place</button>`:''}`);
}
async function delEntry(id){const e=(TRIP.entries||[]).find(x=>x.id===id);
 if(!confirm(`Delete "${e?e.place:'this place'}"? Its guide and journal go with it. Your photos are kept — they're just unassigned from this place.`))return;
 await api('/api/entries/'+id,{method:'DELETE'});
 closeSheet();PLACE=null;openTrip(TRIP.id);toast('Place deleted');
}
async function saveEntry(id){
 const place=el('e_place').value.trim();if(!place)return toast('Needs a place');
 const body={id,trip_id:TRIP.id,place,date:el('e_date').value,companions:el('e_comp').value.trim(),
  experience:el('e_exp').value,ideas:el('e_ideas').value,member:myName()||null};
 await api('/api/entries',{method:'POST',body:JSON.stringify(body)});
 closeSheet();openTrip(TRIP.id);
}

async function uploadPhotos(entryId,input){
 const files=[...input.files];if(!files.length)return;input.value='';
 return uploadFiles(entryId,files);
}
async function uploadFiles(entryId,files){
 files=[...files].filter(f=>/^image\//.test(f.type||''));
 if(!files.length){toast('Drop image files to upload');return;}
 let done=0;const seen={};
 toast('Uploading & sorting '+files.length+' photo(s)…');
 let geo=0;
 for(const f of files){try{const gps=await getExifGps(f);const dataURL=await fileToDataURL(f);
  const body={trip_id:TRIP.id,entry_id:entryId,data:dataURL,member:myName()||null};
  if(gps){body.lat=gps.lat;body.lon=gps.lon;geo++;}
  const r=await api('/api/photos',{method:'POST',body:JSON.stringify(body)});
  done++;if(r&&r.category){seen[r.category]=(seen[r.category]||0)+1;
   toast(`Sorted ${done}/${files.length} · ${r.category}`);}
 }catch(err){toast('A photo failed');}}
 const summary=Object.entries(seen).map(([k,v])=>`${v} ${k}`).join(', ');
 await openTrip(TRIP.id);
 if(summary)toast('Done — '+summary+(geo?` · ${geo} mapped`:''));
 // album workflow: whatever couldn't be auto-placed drops into the swipe backlog
 if(!entryId){const unplaced=(TRIP.photos||[]).filter(p=>!p.entry_id).length;
  if(unplaced&&confirm(unplaced+" photo"+(unplaced!==1?"s":"")+" couldn't be auto-placed. Sort them into locations now?"))openBacklog();}
}

// ---- drag & drop photo upload (drop anywhere while a trip is open) ----
let DRAGDEPTH=0;
function isFileDrag(e){return !!(e.dataTransfer&&[...(e.dataTransfer.types||[])].indexOf('Files')>=0);}
function showDrop(on){
 let d=el('dropzone');
 if(!d){d=document.createElement('div');d.id='dropzone';d.className='dropzone';
  d.innerHTML='<div class="dz-inner">'+ic('camera',42)+'<div class="dz-t">Drop photos to add them</div><div class="dz-s" id="dzsub"></div></div>';
  document.body.appendChild(d);}
 const sub=el('dzsub');if(sub)sub.textContent=TRIP?('to '+(TRIP.title||'this trip')+" — I'll sort & map them"):'';
 d.classList.toggle('on',on);
}
function initDnD(){
 window.addEventListener('dragenter',e=>{if(!isFileDrag(e))return;e.preventDefault();if(!TRIP)return;DRAGDEPTH++;showDrop(true);});
 window.addEventListener('dragover',e=>{if(!isFileDrag(e))return;e.preventDefault();if(TRIP&&e.dataTransfer)e.dataTransfer.dropEffect='copy';});
 window.addEventListener('dragleave',e=>{if(!isFileDrag(e))return;DRAGDEPTH=Math.max(0,DRAGDEPTH-1);if(DRAGDEPTH===0)showDrop(false);});
 window.addEventListener('drop',e=>{if(!isFileDrag(e))return;e.preventDefault();DRAGDEPTH=0;showDrop(false);
  if(!TRIP){toast('Open a trip first, then drop photos in');return;}
  const files=[...((e.dataTransfer&&e.dataTransfer.files)||[])].filter(f=>/^image\//.test(f.type||''));
  if(!files.length){toast('Drop image files to upload');return;}
  uploadFiles(null,files);});
}

// ---- journaling session: opens with a clear choice, incl. handwrite & upload ----
function journalSession(id){const e=(TRIP.entries||[]).find(x=>x.id===id);
 screen(`<h2>${ic('book')} Journaling — ${esc(e.place)}</h2>
  <p class="muted sm">A few quiet minutes to set down what ${esc(e.place)} was. Write it by hand and upload the pages, type it here, or let the Keeper offer a few prompts.</p>
  <label class="btn" style="cursor:pointer;display:block;text-align:center;margin-top:12px">${ic('pen')} Handwrite &amp; upload pages
   <input type="file" accept="image/*" capture="environment" multiple style="display:none" onchange="uploadJournal(${id},this)"></label>
  <button class="btn ghost" style="margin-top:9px" onclick="editEntry(${id})">${ic('keyboard')} Type it myself</button>
  <button class="btn ghost" style="margin-top:9px" onclick="reflectPrompts(${id})">${ic('chat')} Give me a few prompts</button>
  <div id="js_out" style="margin-top:12px"></div>`);
}

async function uploadJournal(id,input){const files=[...input.files];if(!files.length)return;input.value='';
 const out=el('js_out');out.innerHTML=`<div class="briefing"><span class="spinner"></span>Reading your handwriting… (page 1/${files.length})</div>`;
 let full='';let done=0;
 for(const f of files){try{const gps=await getExifGps(f);const dataURL=await fileToDataURL(f,2000,0.9);
   const body={trip_id:TRIP.id,entry_id:id,data:dataURL,member:myName()||null};if(gps){body.lat=gps.lat;body.lon=gps.lon;}
   const r=await api('/api/transcribe',{method:'POST',body:JSON.stringify(body)});
   done++;if(r.text)full+=(full?'\n\n':'')+r.text;
   out.innerHTML=`<div class="briefing"><span class="spinner"></span>Reading your handwriting… (page ${Math.min(done+1,files.length)}/${files.length})</div>`;
 }catch(err){done++;}}
 if(!full.trim()){out.innerHTML=`<div class="briefing danger">Saved your page(s), but I couldn't read the handwriting. Try a flatter, well-lit photo — the pages are kept in this place's gallery either way.</div>`;openTrip(TRIP.id);return;}
 out.innerHTML=`<label>Transcribed — edit anything, then keep it</label>
  <textarea id="js_text" rows="9" style="font-family:var(--serif)">${esc(full)}</textarea>
  <div class="toolbar"><button class="btn sm" onclick="saveJournal(${id})">Save to this place</button>
   <button class="btn sm ghost" onclick="closeSheet()">Discard text</button></div>
  <p class="muted sm" style="margin-top:6px">Your original page photos are saved to this place's gallery under “Journal”.</p>`;
}
async function saveJournal(id){const e=(TRIP.entries||[]).find(x=>x.id===id);const t=el('js_text').value.trim();
 if(!t)return toast('Nothing to save');
 const merged=(e.experience?e.experience.trim()+'\n\n':'')+t;
 await api('/api/entries',{method:'POST',body:JSON.stringify({...e,experience:merged})});
 closeSheet();openTrip(TRIP.id);toast('Journal saved');
}

async function reflectPrompts(id){const e=(TRIP.entries||[]).find(x=>x.id===id);const out=el('js_out');
 out.innerHTML=`<div class="briefing"><span class="spinner"></span>Thinking of a few good questions…</div>`;
 let r;try{r=await api('/api/reflect',{method:'POST',body:JSON.stringify(e)});}catch(err){r={};}
 const prompts=(r&&r.prompts)||[
   `What's one small moment from ${e.place} you don't want to forget?`,
   'Who were you with, and how did they shape it?',
   'What idea are you still turning over from this place?'];
 out.innerHTML=prompts.map(p=>`<div class="briefing">${esc(p)}</div>`).join('')
  +`<div class="toolbar"><button class="btn sm" onclick="editEntry(${id})">Write my answer</button></div>`;
}

async function polish(id){const e=(TRIP.entries||[]).find(x=>x.id===id);
 if(!e.experience&&!e.ideas)return toast('Jot a few rough notes first');
 sheet(`<h2>${ic('pen')} Polished entry — ${esc(e.place)}</h2>
  <div id="pc" class="muted"><span class="spinner"></span>Shaping your notes into a journal entry…</div>`);
 const r=await api('/api/journal',{method:'POST',body:JSON.stringify(e)});
 if(r.text){el('pc').innerHTML=`<div class="briefing">${esc(r.text)}</div>
  <div class="toolbar"><button class="btn sm" onclick="applyPolish(${id})">Replace my experience note</button>
  <button class="btn sm ghost" onclick="closeSheet()">Keep mine</button></div>`;
  window._polish=r.text;}
 else el('pc').innerHTML='<div class="danger">Could not reach the companion.</div>';
}
async function applyPolish(id){const e=(TRIP.entries||[]).find(x=>x.id===id);
 await api('/api/entries',{method:'POST',body:JSON.stringify({...e,experience:window._polish})});
 closeSheet();openTrip(TRIP.id);
}

async function tripRecap(){const box=el('recap');
 box.innerHTML=`<div class="briefing"><span class="spinner"></span>Writing your trip recap…</div>`;
 const r=await api('/api/recap',{method:'POST',body:JSON.stringify({trip_id:TRIP.id})});
 box.innerHTML=r.text?`<div class="briefing">${ic('book')} ${esc(r.text)}</div>`:'<div class="briefing danger">Could not write a recap yet.</div>';
}

// ---- Chat tab: talk about the currently selected trip (agentic journaling) ----
let CHATMSGS=[],CHATTHINKING=false,NOTES=[],NBOPEN=true,NBADD=false;
async function renderChat(){
 const app=el('app');
 const where=esc(TRIP.destination||TRIP.title||'this trip');
 app.innerHTML=`<div class="tabhead"><h2>${ic('chat')} Chat</h2></div>
  ${tripSubhead()}
  <div id="notebook" class="notebook"></div>
  <div id="chatlog" class="chatlog"><div class="muted sm" style="text-align:center;padding:24px"><span class="spinner"></span></div></div>
  <div class="chatbar"><div class="inner">
    <textarea id="chatin" rows="1" placeholder="Ask or speak about ${where}…"
      oninput="chatGrow(this)" onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendChat();}"></textarea>
    <button class="btn mic" id="micbtn" onclick="toggleMic(this)" aria-label="Speak" title="Tap to speak">${ic('mic')}</button>
    <button class="btn send" onclick="sendChat()" aria-label="Send">${ic('send')}</button>
  </div></div>`;
 CHATTHINKING=false;
 let d;try{d=await api('/api/chat/'+TRIP.id);}catch(e){d=null;}
 CHATMSGS=(d&&d.messages)||[];
 drawChat();
 await loadNotes();
}
function chatGrow(t){t.style.height='auto';t.style.height=Math.min(t.scrollHeight,120)+'px';}
function chatSuggest(){return ['Tell me the history of this place','What spots should I not miss?','Help me plan the next day','Log what I did today'];}
function drawChat(){
 const log=el('chatlog');if(!log)return;
 if(!CHATMSGS.length&&!CHATTHINKING){
  log.innerHTML=`<div class="chatempty">${ic('chat',34)}
    <p>Chat about <b>${esc(TRIP.destination||TRIP.title||'this trip')}</b> — and I'll journal as we go, filing history, spots to visit, places you've been & more into your notebook above.</p>
    <div class="chips">${chatSuggest().map(s=>`<button class="chip" onclick="askSuggest(this)">${esc(s)}</button>`).join('')}</div></div>`;
  return;
 }
 log.innerHTML=CHATMSGS.map(m=>`<div class="cmsg ${m.role==='user'?'user':'assistant'}">${m.role==='assistant'?ic('compass',15):''}<span>${esc(m.content)}</span></div>`).join('')
   +(CHATTHINKING?`<div class="cmsg assistant"><span class="spinner"></span> thinking…</div>`:'');
 log.scrollTop=log.scrollHeight;
}
function askSuggest(btn){el('chatin').value=btn.textContent;sendChat();}
async function sendChat(){
 const inp=el('chatin');if(!inp)return;const msg=(inp.value||'').trim();if(!msg||CHATTHINKING)return;
 inp.value='';inp.style.height='auto';
 CHATMSGS.push({role:'user',content:msg});CHATTHINKING=true;drawChat();
 let r;try{r=await api('/api/chat',{method:'POST',body:JSON.stringify({trip_id:TRIP.id,message:msg})});}catch(e){r=null;}
 CHATTHINKING=false;
 CHATMSGS.push({role:'assistant',content:(r&&r.reply)||(r&&r.error)||"Sorry — I couldn't respond right now."});
 drawChat();
 if(r&&r.saved&&r.saved.length){NBOPEN=true;await loadNotes();toast(`${ic('notebook',14)} Saved ${r.saved.length} to your notebook`);}
}

// ---- voice input: speak to the agent (records → transcribes → auto-sends) ----
let REC=null,RECCHUNKS=[],RECSTREAM=null;
function blobToDataURL(b){return new Promise(res=>{const fr=new FileReader();fr.onload=()=>res(fr.result);fr.readAsDataURL(b);});}
async function toggleMic(btn){
 if(REC&&REC.state==='recording'){REC.stop();return;}
 if(!navigator.mediaDevices||!window.MediaRecorder){toast('Voice input not supported on this browser');return;}
 let stream;try{stream=await navigator.mediaDevices.getUserMedia({audio:true});}catch(e){toast('Microphone permission needed');return;}
 RECSTREAM=stream;RECCHUNKS=[];
 const mime=MediaRecorder.isTypeSupported('audio/webm')?'audio/webm':(MediaRecorder.isTypeSupported('audio/mp4')?'audio/mp4':'');
 try{REC=new MediaRecorder(stream,mime?{mimeType:mime}:undefined);}catch(e){REC=new MediaRecorder(stream);}
 REC.ondataavailable=e=>{if(e.data&&e.data.size)RECCHUNKS.push(e.data);};
 REC.onstop=async()=>{
  try{RECSTREAM.getTracks().forEach(t=>t.stop());}catch(e){}
  btn.classList.remove('rec');
  const blob=new Blob(RECCHUNKS,{type:(REC&&REC.mimeType)||'audio/webm'});
  if(!blob.size){toast('Didn’t catch that');return;}
  const inp=el('chatin');const prev=inp?inp.placeholder:'';if(inp){inp.disabled=true;inp.placeholder='Transcribing…';}
  let r;try{const data=await blobToDataURL(blob);r=await api('/api/voice',{method:'POST',body:JSON.stringify({data})});}catch(e){r=null;}
  if(inp){inp.disabled=false;inp.placeholder=prev;}
  const txt=((r&&r.text)||'').trim();
  if(!txt){toast('Didn’t catch that — try again');return;}
  if(inp){inp.value=txt;chatGrow(inp);}
  sendChat();
 };
 REC.start();btn.classList.add('rec');toast('Listening… tap the mic to stop');
}

// ---- Trip Notebook (the agentic, categorized notes) ----
async function loadNotes(){let d;try{d=await api('/api/notes/'+TRIP.id);}catch(e){d=null;}NOTES=(d&&d.categories)||[];drawNotes();}
function toggleNotebook(){NBOPEN=!NBOPEN;drawNotes();}
function toggleNoteAdd(){NBADD=!NBADD;drawNotes();if(NBADD){const t=el('nb_txt');if(t)t.focus();}}
function drawNotes(){
 const box=el('notebook');if(!box)return;
 const total=NOTES.reduce((n,c)=>n+c.items.length,0);
 const cats=NOTES.map(cat=>`<div class="nb-cat"><div class="nb-cat-h">${esc(cat.name)} <span class="muted sm">${cat.items.length}</span></div>
   <ul class="nb-items">${cat.items.map(it=>`<li><span>${esc(it.text)}${it.place?` <span class="nb-place">${ic('pin',10)} ${esc(it.place)}</span>`:''}</span><button class="nb-del" onclick="delNote(${it.id})" aria-label="Delete note">×</button></li>`).join('')}</ul></div>`).join('');
 const form=NBADD?`<div class="nb-form">
   <input id="nb_cat" list="nb_cats" placeholder="Category">
   <datalist id="nb_cats">${NOTES.map(c=>`<option value="${esc(c.name)}">`).join('')}</datalist>
   <input id="nb_txt" placeholder="Add a note…" onkeydown="if(event.key==='Enter')saveManualNote()">
   <button class="btn sm" style="width:auto" onclick="saveManualNote()">Add</button></div>`:'';
 const body=total?cats:`<div class="muted sm" style="padding:4px 2px 8px">Empty for now — as we chat I'll file notes here (history, spots to visit, places visited…). You can add your own too.</div>`;
 box.innerHTML=`<div class="nb-head" onclick="toggleNotebook()">
   <span>${ic('notebook',16)} Trip Notebook${total?` <span class="nb-count">${total}</span>`:''}</span>
   <span class="nb-tog">${NBOPEN?'▾':'▸'}</span></div>
  <div class="nb-body" style="display:${NBOPEN?'':'none'}">${body}
   ${form}
   <button class="nb-addbtn" onclick="toggleNoteAdd()">${NBADD?'Cancel':'+ Add note'}</button></div>`;
}
async function saveManualNote(){
 const cat=(el('nb_cat').value||'Notes').trim();const txt=(el('nb_txt').value||'').trim();if(!txt)return;
 try{await api('/api/notes',{method:'POST',body:JSON.stringify({trip_id:TRIP.id,category:cat,text:txt})});}catch(e){toast('Could not save');return;}
 NBADD=false;await loadNotes();
}
async function delNote(id){try{await api('/api/notes/'+id,{method:'DELETE'});}catch(e){}await loadNotes();}

// ---- collage studio ----
let COL={style:'scrapbook',sel:new Set()};
const STYLES=[['scrapbook',ic('notebook')+' Scrapbook'],['postcard',ic('mail')+' Postcard'],['watercolor',ic('palette')+' Watercolor'],
 ['polaroid',ic('image')+' Polaroid'],['cinematic',ic('clapper')+' Cinematic']];
function collageStudio(){
 const photos=TRIP.photos||[];COL={style:'scrapbook',sel:new Set(photos.slice(0,6).map(p=>p.id))};
 if(!photos.length){return sheet(`<h2>${ic('palette')} Make a collage</h2>
  <p class="muted">Add a few photos to your places first — then I can blend them into a collage.</p>`);}
 let ph=photos.map(p=>`<div class="ph ${COL.sel.has(p.id)?'on':''}" data-id="${p.id}" onclick="togglePh(${p.id},this)">
  <img src="${BASE}/photo/${p.filename}"></div>`).join('');
 sheet(`<h2>${ic('palette')} Make a collage</h2>
  <label>Style</label><div class="seg" id="styleSeg">${STYLES.map(s=>`<div class="opt ${s[0]==COL.style?'on':''}" onclick="pickStyle('${s[0]}',this)">${s[1]}</div>`).join('')}</div>
  <label>Photos (${photos.length}) — tap to include</label><div class="pick">${ph}</div>
  <label>A note for the AI (optional)</label><input id="col_note" placeholder="warm sunset tones, include the trip name">
  <div style="margin-top:16px"><button class="btn" id="genBtn" onclick="genCollage()">${ic('sparkle')} Generate AI collage</button>
  <button class="btn ghost" style="margin-top:8px" onclick="quickCollage()">${ic('bolt')} Quick collage (offline, no AI)</button></div>
  <p class="muted sm" style="margin-top:8px">AI collage reimagines your photos in the chosen style. Quick collage arranges the originals on a canvas instantly.</p>`);
}
function pickStyle(s,n){COL.style=s;[...el('styleSeg').children].forEach(c=>c.classList.remove('on'));n.classList.add('on');}
function togglePh(id,n){if(COL.sel.has(id)){COL.sel.delete(id);n.classList.remove('on');}
 else{if(COL.sel.size>=8)return toast('Up to 8 photos');COL.sel.add(id);n.classList.add('on');}}

async function genCollage(){
 if(!COL.sel.size)return toast('Pick at least one photo');
 const b=el('genBtn');b.disabled=true;b.innerHTML='<span class="spinner"></span>Painting your collage… (up to ~1 min)';
 const r=await api('/api/collage',{method:'POST',body:JSON.stringify({trip_id:TRIP.id,
  photo_ids:[...COL.sel],style:COL.style,note:el('col_note').value.trim()})});
 if(r.filename){closeSheet();openTrip(TRIP.id);toast('Collage ready');}
 else{b.disabled=false;b.innerHTML=ic('sparkle')+' Generate AI collage';toast(r.error||'AI collage failed — try Quick collage');}
}

// client-side canvas collage (always works)
async function quickCollage(){
 const ids=[...COL.sel];if(!ids.length)return toast('Pick some photos');
 const photos=(TRIP.photos||[]).filter(p=>ids.includes(p.id));
 toast('Composing…');
 const imgs=await Promise.all(photos.map(p=>new Promise(res=>{const i=new Image();
  i.crossOrigin='anonymous';i.onload=()=>res(i);i.onerror=()=>res(null);i.src=BASE+'/photo/'+p.filename;})));
 const ok=imgs.filter(Boolean);if(!ok.length)return toast('Could not load photos');
 const W=1200,H=1500,cv=el('cv');cv.width=W;cv.height=H;const g=cv.getContext('2d');
 g.fillStyle='#211b15';g.fillRect(0,0,W,H);
 const n=ok.length,cols=n<=2?1:(n<=6?2:3),rows=Math.ceil(n/cols),pad=26;
 const cw=(W-pad*(cols+1))/cols,ch=(H-120-pad*(rows+1))/rows;
 ok.forEach((im,i)=>{const r=Math.floor(i/cols),c=i%cols;
  const x=pad+c*(cw+pad),y=pad+r*(ch+pad);const rot=(((i*37)%7)-3)*Math.PI/180;
  g.save();g.translate(x+cw/2,y+ch/2);g.rotate(rot);
  g.fillStyle='#faf6ee';g.fillRect(-cw/2-8,-ch/2-8,cw+16,ch+40);
  const s=Math.max(cw/im.width,ch/im.height),sw=im.width*s,sh=im.height*s;
  g.save();g.beginPath();g.rect(-cw/2,-ch/2,cw,ch);g.clip();
  g.drawImage(im,-sw/2,-sh/2,sw,sh);g.restore();g.restore();});
 g.fillStyle='#f4a259';g.font='800 46px -apple-system,sans-serif';g.textAlign='center';
 g.fillText(TRIP.title,W/2,H-46);
 const dataURL=cv.toDataURL('image/jpeg',0.9);
 const r=await api('/api/collage',{method:'POST',body:JSON.stringify({trip_id:TRIP.id,style:'quick',data:dataURL})});
 if(r.filename){closeSheet();openTrip(TRIP.id);toast('Collage saved');}else toast('Save failed');
}

async function delCollage(id){if(!confirm('Remove this collage?'))return;
 await api('/api/collage/'+id,{method:'DELETE'});openTrip(TRIP.id);}
async function delTrip(){if(!confirm('Delete this whole trip and its photos?'))return;
 closeSelector();await api('/api/trips/'+TRIP.id,{method:'DELETE'});closeSheet();TRIP=null;boot();}
function editTrip(){const t=TRIP;closeSelector();closeSheet();sheet(`<h2>Edit trip</h2>
 <label>Title</label><input id="f_title" value="${esc(t.title)}">
 <label>Destination</label><input id="f_dest" value="${esc(t.destination||'')}">
 <div class="row"><div><label>Start</label><input id="f_start" type="date" value="${esc(t.start_date||'')}"></div>
 <div><label>End</label><input id="f_end" type="date" value="${esc(t.end_date||'')}"></div></div>
 <div style="margin-top:16px"><button class="btn" onclick="saveTripEdit()">Save</button></div>`);}
async function saveTripEdit(){const title=el('f_title').value.trim();if(!title)return toast('Give it a title');
 await api('/api/trips',{method:'POST',body:JSON.stringify({id:TRIP.id,title,destination:el('f_dest').value.trim(),
  start_date:el('f_start').value,end_date:el('f_end').value})});
 closeSheet();openTrip(TRIP.id);}

// ---- bottom sheet ----
function sheet(html){closeSheet();const m=document.createElement('div');m.className='modal';m.id='modal';
 m.onclick=e=>{if(e.target===m)closeSheet();};
 m.innerHTML=`<div class="sheet">${html}</div>`;document.body.appendChild(m);}
// ---- full-page screen with iOS slide-in + edge swipe-back ----
function screen(html){closeSheet();const m=document.createElement('div');m.className='modal screen';m.id='modal';
 m.innerHTML=`<div class="screenpane"><button class="screenback" onclick="dismissScreen()">‹ Back</button>${html}</div>`;
 document.body.appendChild(m);document.body.style.overflow='hidden';
 const pane=m.firstElementChild;
 requestAnimationFrame(()=>m.classList.add('in'));         // slide in from the right
 // edge swipe-back: start the drag only from the left ~28px, follow the finger, release to go back
 let sx=0,drag=false;
 m.addEventListener('touchstart',e=>{const t=e.touches[0];if(t.clientX<=28){drag=true;sx=t.clientX;pane.style.transition='none';}},{passive:true});
 m.addEventListener('touchmove',e=>{if(!drag)return;const dx=Math.max(0,e.touches[0].clientX-sx);pane.style.transform='translateX('+dx+'px)';},{passive:true});
 m.addEventListener('touchend',e=>{if(!drag)return;drag=false;pane.style.transition='';pane.style.transform='';
  if((e.changedTouches[0].clientX-sx)>innerWidth*0.32)dismissScreen();},{passive:true});
}
function dismissScreen(){const m=el('modal');if(!m)return;if(!m.classList.contains('screen'))return closeSheet();
 m.classList.remove('in');document.body.style.overflow='';setTimeout(()=>{if(el('modal')===m)m.remove();},300);}
function closeSheet(){const m=el('modal');if(m)m.remove();document.body.style.overflow='';}

if('serviceWorker' in navigator)navigator.serviceWorker.register(BASE+'/sw.js').catch(()=>{});
paintStaticIcons();initDnD();boot();
</script></body></html>'''

MANIFEST = json.dumps({
    "name": "Trip Sync", "short_name": "Trip Sync",
    "start_url": (BASE + "/") or "/", "scope": (BASE + "/") or "/",
    "display": "standalone", "background_color": "#14110f", "theme_color": "#14110f",
    "description": "A travel journal with an AI companion — places, people, ideas, and collages.",
    "icons": [
        {"src": (BASE + "/icon-192.png"), "sizes": "192x192", "type": "image/png"},
        {"src": (BASE + "/icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
    ],
})

SW = ("const C='tripsync-v5';const SHELL=['__B__/','__B__/manifest.webmanifest','__B__/icon-192.png','__B__/icon-512.png'];"
      "self.addEventListener('install',e=>{self.skipWaiting();e.waitUntil(caches.open(C).then(c=>c.addAll(SHELL).catch(()=>{})))});"
      "self.addEventListener('activate',e=>{self.clients.claim();e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==C).map(k=>caches.delete(k)))))});"
      "self.addEventListener('fetch',e=>{const u=new URL(e.request.url);"
      "if(u.pathname.indexOf('/api/')>=0)return;"  # never touch API
      # network-first for the page/navigation so it can never get stuck on a stale shell
      "if(e.request.mode==='navigate'||u.pathname===C){e.respondWith(fetch(e.request).then(res=>{"
      "const cp=res.clone();caches.open(C).then(c=>c.put(e.request,cp));return res;}).catch(()=>caches.match(e.request).then(r=>r||caches.match('__B__/'))));return;}"
      # cache-first for static assets (icons/manifest)
      "e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request).then(res=>{"
      "if(e.request.method==='GET'&&res.ok){const cp=res.clone();caches.open(C).then(c=>c.put(e.request,cp));}return res;})"
      ".catch(()=>r)))});").replace("__B__", BASE)

# ---- helpers for API -------------------------------------------------------

def save_dataurl(dataurl, folder, prefix):
    m = re.match(r"data:(image/[a-zA-Z0-9.+-]+);base64,(.*)", dataurl or "", re.DOTALL)
    if not m:
        return None
    mime, b64 = m.group(1), m.group(2)
    raw = base64.b64decode(b64)
    ext = mimetypes.guess_extension(mime) or ".jpg"
    if ext == ".jpe":
        ext = ".jpg"
    fn = prefix + "-" + hashlib.sha1((now() + str(len(raw))).encode()).hexdigest()[:12] + ext
    with open(os.path.join(folder, fn), "wb") as f:
        f.write(raw)
    return fn

def _jit(seed):
    """Deterministic small offset (~up to ~300m) so photos sharing a place don't stack on one point."""
    a = ((seed * 2654435761) % 1000) / 1000.0 - 0.5
    b = ((seed * 40503) % 1000) / 1000.0 - 0.5
    return a * 0.006, b * 0.006

MEMBER_COLORS = ["#E8863B", "#3BA6E8", "#C65BCF", "#3BC07A", "#E85B7A", "#D4A02B", "#6C6CE0", "#2BB3B3", "#E8623B", "#5BAF4A"]
def member_color(name):
    return MEMBER_COLORS[sum(ord(ch) for ch in (name or "?")) % len(MEMBER_COLORS)]

def trip_dict(c, tid):
    t = c.execute("SELECT * FROM trips WHERE id=?", (tid,)).fetchone()
    if not t:
        return None
    d = dict(t)
    d["entries"] = [dict(r) for r in c.execute(
        "SELECT * FROM entries WHERE trip_id=? ORDER BY date,id", (tid,)).fetchall()]
    d["photos"] = [dict(r) for r in c.execute(
        "SELECT * FROM photos WHERE trip_id=? ORDER BY id", (tid,)).fetchall()]
    d["collages"] = [dict(r) for r in c.execute(
        "SELECT * FROM collages WHERE trip_id=? ORDER BY id DESC", (tid,)).fetchall()]
    d["members"] = [dict(r) for r in c.execute(
        "SELECT name,color FROM trip_members WHERE trip_id=? ORDER BY id", (tid,)).fetchall()]
    return d

STYLE_PROMPTS = {
    "scrapbook": "a warm travel scrapbook page: photos arranged with torn-paper edges, washi tape, handwritten-style captions and little doodles on textured cream paper",
    "postcard": "a vintage 'greetings from' travel postcard: bold retro lettering, sunny saturated colors, stamp and postmark motifs",
    "watercolor": "a dreamy watercolor travel journal spread, soft painterly washes blending the scenes together with ink accents",
    "polaroid": "a scattered stack of polaroid instant photos on a dark desk, slight shadows, a few handwritten dates on the white borders",
    "cinematic": "a cinematic film-still collage with moody color grading, letterbox framing and elegant minimalist typography",
}

# ---- server ----------------------------------------------------------------

class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ct="application/json", extra=None):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj), "application/json")

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def _path(self):
        return urllib.parse.urlparse(self.path).path

    def _query(self):
        return urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

    # ---- GET ----
    def do_GET(self):
        p = self._path()
        if BASE and p.startswith(BASE):
            p = p[len(BASE):] or "/"
        if p == "/" or p == "/index.html":
            return self._send(200, PAGE.replace("__BASE__", BASE).replace("__MARK__", ICON_SVG), "text/html; charset=utf-8")
        if p == "/manifest.webmanifest":
            return self._send(200, MANIFEST, "application/manifest+json")
        if p == "/sw.js":
            return self._send(200, SW, "application/javascript")
        if p in ("/icon.svg",):
            return self._send(200, ICON_SVG, "image/svg+xml")
        if p in ("/icon.png", "/icon-192.png", "/icon-512.png"):
            fp = os.path.join(HERE, p.lstrip("/"))
            if os.path.isfile(fp):
                with open(fp, "rb") as f:
                    return self._send(200, f.read(), "image/png")
            return self._send(200, ICON_SVG, "image/svg+xml")
        if p == "/api/trips":
            c = db()
            rows = []
            for t in c.execute("SELECT * FROM trips ORDER BY id DESC").fetchall():
                d = dict(t)
                d["entry_count"] = c.execute("SELECT COUNT(*) FROM entries WHERE trip_id=?", (t["id"],)).fetchone()[0]
                d["photo_count"] = c.execute("SELECT COUNT(*) FROM photos WHERE trip_id=?", (t["id"],)).fetchone()[0]
                rows.append(d)
            c.close()
            return self._json(200, {"trips": rows})
        m = re.match(r"/api/trips/(\d+)$", p)
        if m:
            c = db(); d = trip_dict(c, int(m.group(1))); c.close()
            return self._json(200 if d else 404, d or {"error": "not found"})
        m = re.match(r"/api/chat/(\d+)$", p)
        if m:
            c = db()
            try:
                rows = c.execute("SELECT role,content,created FROM chat_messages WHERE trip_id=? ORDER BY id",
                                 (int(m.group(1)),)).fetchall()
            finally:
                c.close()
            return self._json(200, {"messages": [dict(r) for r in rows]})
        m = re.match(r"/api/notes/(\d+)$", p)
        if m:
            c = db()
            try:
                rows = c.execute("SELECT id,category,text,place,source,created FROM trip_notes "
                                 "WHERE trip_id=? ORDER BY id", (int(m.group(1)),)).fetchall()
            finally:
                c.close()
            cats = []
            idx = {}
            for r in rows:
                cat = r["category"] or "Notes"
                if cat not in idx:
                    idx[cat] = len(cats)
                    cats.append({"name": cat, "items": []})
                cats[idx[cat]]["items"].append(dict(r))
            return self._json(200, {"categories": cats, "count": len(rows)})
        m = re.match(r"/api/trips/(\d+)/members$", p)
        if m:
            tid = int(m.group(1)); c = db()
            try:
                rows = c.execute("SELECT name,color FROM trip_members WHERE trip_id=? ORDER BY id", (tid,)).fetchall()
                out = []
                for r in rows:
                    pc = c.execute("SELECT COUNT(*) n FROM photos WHERE trip_id=? AND member=?", (tid, r["name"])).fetchone()["n"]
                    out.append({"name": r["name"], "color": r["color"], "photos": pc})
                tok = c.execute("SELECT share_token FROM trips WHERE id=?", (tid,)).fetchone()
            finally:
                c.close()
            return self._json(200, {"members": out, "share_token": tok["share_token"] if tok else None})
        m = re.match(r"/api/trips/(\d+)/expenses$", p)
        if m:
            tid = int(m.group(1)); c = db()
            try:
                return self._json(200, expenses_payload(c, tid))
            finally:
                c.close()
        m = re.match(r"/api/join/([A-Za-z0-9_-]+)$", p)
        if m:
            c = db()
            try:
                t = c.execute("SELECT id,title,destination,cover FROM trips WHERE share_token=?", (m.group(1),)).fetchone()
                mem = ph = 0
                if t:
                    mem = c.execute("SELECT COUNT(*) n FROM trip_members WHERE trip_id=?", (t["id"],)).fetchone()["n"]
                    ph = c.execute("SELECT COUNT(*) n FROM photos WHERE trip_id=?", (t["id"],)).fetchone()["n"]
            finally:
                c.close()
            if not t:
                return self._json(404, {"error": "This invite link isn't valid anymore."})
            return self._json(200, {"trip_id": t["id"], "title": t["title"], "destination": t["destination"],
                                    "cover": t["cover"], "members": mem, "photos": ph})
        m = re.match(r"/api/map/(\d+)$", p)
        if m:
            return self._map(int(m.group(1)))
        m = re.match(r"/api/sections/(\d+)$", p)
        if m:
            eid = int(m.group(1)); c = db()
            try:
                out = {k: section_payload(c, eid, k) for k in SECTION_KINDS}
            finally:
                c.close()
            return self._json(200, {"sections": out})
        m = re.match(r"/api/quiz/(\d+)$", p)
        if m:
            eid = int(m.group(1))
            device = (self._query().get("device", [""])[0] or "")
            c = db()
            try:
                bundle = quiz_bundle(c, eid, device)
            finally:
                c.close()
            if bundle is None:
                return self._json(404, {"error": "no such place"})
            return self._json(200, bundle)
        m = re.match(r"/api/import/status/([0-9a-f]+)$", p)
        if m:
            st = IMPORTS.get(m.group(1))
            if st:
                return self._json(200, {**st, "job_id": m.group(1)})
            c = db()
            try:
                row = c.execute("SELECT * FROM import_jobs WHERE job_id=?", (m.group(1),)).fetchone()
            finally:
                c.close()
            return self._json(200 if row else 404, dict(row) if row else {"error": "unknown job"})
        m = re.match(r"/api/import/active/(\d+)$", p)
        if m:
            # latest job for this trip so the UI can resume a progress view after a reload
            c = db()
            try:
                row = c.execute("SELECT * FROM import_jobs WHERE trip_id=? ORDER BY created DESC, rowid DESC LIMIT 1",
                                (m.group(1),)).fetchone()
            finally:
                c.close()
            job = dict(row) if row else None
            # prefer the live in-memory copy if present (freshest counts)
            if job and IMPORTS.get(job["job_id"]):
                job = {**job, **IMPORTS[job["job_id"]], "job_id": job["job_id"]}
            return self._json(200, {"job": job})
        m = re.match(r"/api/map/landmarks/status/([0-9a-f]+)$", p)
        if m:
            st = LANDJOBS.get(m.group(1))
            return self._json(200 if st else 404, st or {"error": "unknown job"})
        m = re.match(r"/api/backlog/(\d+)$", p)
        if m:
            tid = int(m.group(1)); c = db()
            try:
                ents = c.execute("SELECT * FROM entries WHERE trip_id=? ORDER BY date,id", (tid,)).fetchall()
                out = []
                for ph in c.execute("SELECT id,filename,caption,category,tags,lat,lon FROM photos "
                                    "WHERE trip_id=? AND entry_id IS NULL ORDER BY id", (tid,)).fetchall():
                    suggest = match_photo_entry(c, tid, ph["lat"], ph["lon"], ph["caption"] or "", ph["tags"] or "")
                    # no confident match but we have GPS -> still offer the nearest place as a guess
                    if suggest is None and ph["lat"] is not None and ph["lon"] is not None:
                        best, bestd = None, 1e9
                        for e in ents:
                            elat, elon = _entry_latlon(c, e)
                            if elat is None or elon is None:
                                continue
                            d = _haversine_km(ph["lat"], ph["lon"], elat, elon)
                            if d < bestd:
                                best, bestd = e, d
                        if best is not None:
                            suggest = best["id"]
                    sp = None
                    if suggest is not None:
                        r = c.execute("SELECT place FROM entries WHERE id=?", (suggest,)).fetchone()
                        sp = r["place"] if r else None
                    try:
                        tags = json.loads(ph["tags"] or "[]")
                    except Exception:
                        tags = []
                    out.append({"id": ph["id"], "filename": ph["filename"], "caption": ph["caption"] or "",
                                "category": ph["category"] or "Other", "tags": tags,
                                "has_gps": ph["lat"] is not None, "suggest": suggest, "suggest_place": sp})
                places = [{"id": e["id"], "place": e["place"]} for e in ents]
            finally:
                c.close()
            return self._json(200, {"photos": out, "places": places})
        m = re.match(r"/(photo|collage)/([A-Za-z0-9._-]+)$", p)
        if m:
            folder = PHOTOS if m.group(1) == "photo" else COLLAGES
            fp = os.path.join(folder, m.group(2))
            if ".." in m.group(2) or not os.path.isfile(fp):
                return self._send(404, b"not found", "text/plain")
            ct = mimetypes.guess_type(fp)[0] or "application/octet-stream"
            with open(fp, "rb") as f:
                return self._send(200, f.read(), ct, {"Cache-Control": "public, max-age=604800"})
        return self._send(404, b"not found", "text/plain")

    def _map(self, tid):
        """Geo points for a trip: photos (own GPS, or inherited from their assigned place) + places."""
        c = db()
        try:
            photos = [dict(r, inherited=False) for r in c.execute(
                "SELECT id,filename,lat,lon,category,caption,entry_id FROM photos "
                "WHERE trip_id=? AND lat IS NOT NULL AND lon IS NOT NULL ORDER BY id", (tid,)).fetchall()]
            places = []
            for e in c.execute("SELECT * FROM entries WHERE trip_id=? ORDER BY date,id", (tid,)).fetchall():
                lat, lon = e["lat"], e["lon"]
                if lat is None or lon is None:
                    ph = c.execute("SELECT AVG(lat),AVG(lon),COUNT(*) FROM photos "
                                   "WHERE entry_id=? AND lat IS NOT NULL", (e["id"],)).fetchone()
                    if ph and ph[2]:
                        lat, lon = ph[0], ph[1]
                    elif e["place"]:
                        glat, glon, _ = geocode(e["place"])
                        lat, lon = glat, glon
                    if lat is not None and lon is not None:
                        c.execute("UPDATE entries SET lat=?,lon=? WHERE id=?", (lat, lon, e["id"]))
                        c.commit()
                if lat is not None and lon is not None:
                    # photos assigned to this place but WITHOUT their own GPS: pin them at the
                    # place (spread a little so they don't stack) — "place pin" fallback.
                    for ph in c.execute("SELECT id,filename,category,caption FROM photos "
                                        "WHERE entry_id=? AND (lat IS NULL OR lon IS NULL) ORDER BY id",
                                        (e["id"],)).fetchall():
                        dlat, dlon = _jit(ph["id"])
                        photos.append({"id": ph["id"], "filename": ph["filename"], "lat": lat + dlat,
                                       "lon": lon + dlon, "category": ph["category"], "caption": ph["caption"],
                                       "entry_id": e["id"], "inherited": True, "place": e["place"]})
                    exp = (e["experience"] or "").strip()
                    # a representative photo for this place: user's chosen cover first,
                    # else a real scene over a journal page, else anything
                    cover = None
                    if e["cover"]:
                        cover = c.execute("SELECT filename FROM photos WHERE entry_id=? AND filename=? LIMIT 1", (e["id"], e["cover"])).fetchone()
                    cover = cover \
                        or c.execute("SELECT filename FROM photos WHERE entry_id=? AND category!='Journal' ORDER BY id LIMIT 1", (e["id"],)).fetchone() \
                        or c.execute("SELECT filename FROM photos WHERE entry_id=? ORDER BY id LIMIT 1", (e["id"],)).fetchone()
                    nphotos = c.execute("SELECT COUNT(*) FROM photos WHERE entry_id=?", (e["id"],)).fetchone()[0]
                    # photo filenames for this place's radial "radiate" burst (cover/scenes first)
                    pfiles = [r["filename"] for r in c.execute(
                        "SELECT filename FROM photos WHERE entry_id=? ORDER BY (category='Journal'), id LIMIT 18",
                        (e["id"],)).fetchall()]
                    places.append({"id": e["id"], "place": e["place"], "lat": lat, "lon": lon,
                                   "date": e["date"], "companions": e["companions"],
                                   "has_journal": bool(exp),
                                   "journal": exp[:700],
                                   "journal_more": len(exp) > 700,
                                   "ideas": (e["ideas"] or "").strip()[:400],
                                   "thumb": cover["filename"] if cover else None,
                                   "pfiles": pfiles,
                                   "landmark": e["landmark"],
                                   "nphotos": nphotos})
            collages = [r["filename"] for r in c.execute(
                "SELECT filename FROM collages WHERE trip_id=? ORDER BY id DESC LIMIT 18", (tid,)).fetchall()]
            cen = None
            if places:
                cen = [sum(p["lat"] for p in places) / len(places), sum(p["lon"] for p in places) / len(places)]
            return self._json(200, {"photos": photos, "places": places, "collages": collages, "center": cen})
        finally:
            c.close()

    # ---- POST ----
    def do_POST(self):
        p = self._path()
        if BASE and p.startswith(BASE):
            p = p[len(BASE):] or "/"
        b = self._body()
        c = db()
        try:
            if p == "/api/trips":
                if b.get("id"):
                    c.execute("UPDATE trips SET title=?,destination=?,start_date=?,end_date=? WHERE id=?",
                              (b.get("title", "Trip"), b.get("destination", ""),
                               b.get("start_date", ""), b.get("end_date", ""), b.get("id")))
                    c.commit()
                    return self._json(200, {"id": b.get("id")})
                cur = c.execute("INSERT INTO trips(title,destination,start_date,end_date,created) VALUES(?,?,?,?,?)",
                                (b.get("title", "Trip"), b.get("destination", ""),
                                 b.get("start_date", ""), b.get("end_date", ""), now()))
                c.commit()
                return self._json(200, {"id": cur.lastrowid})

            m = re.match(r"/api/trips/(\d+)/share$", p)
            if m:
                tid = int(m.group(1))
                row = c.execute("SELECT share_token FROM trips WHERE id=?", (tid,)).fetchone()
                if not row:
                    return self._json(404, {"error": "not found"})
                tok = row["share_token"]
                if not tok:
                    tok = secrets.token_urlsafe(9)
                    c.execute("UPDATE trips SET share_token=? WHERE id=?", (tok, tid)); c.commit()
                return self._json(200, {"token": tok})

            m = re.match(r"/api/trips/(\d+)/join$", p)
            if m:
                tid = int(m.group(1))
                if not c.execute("SELECT 1 FROM trips WHERE id=?", (tid,)).fetchone():
                    return self._json(404, {"error": "not found"})
                dev = (b.get("token") or "").strip()[:64]
                name = (b.get("name") or "").strip()[:40] or "Traveler"
                if not dev:
                    return self._json(400, {"error": "missing device token"})
                color = member_color(name)
                ex = c.execute("SELECT id FROM trip_members WHERE trip_id=? AND token=?", (tid, dev)).fetchone()
                if ex:
                    c.execute("UPDATE trip_members SET name=?,color=?,last_seen=? WHERE id=?", (name, color, now(), ex["id"]))
                else:
                    c.execute("INSERT INTO trip_members(trip_id,token,name,color,created,last_seen) VALUES(?,?,?,?,?,?)",
                              (tid, dev, name, color, now(), now()))
                c.commit()
                return self._json(200, {"name": name, "color": color})

            m = re.match(r"/api/trips/(\d+)/expenses$", p)
            if m:
                tid = int(m.group(1))
                payer = (b.get("payer") or "").strip()[:40]
                desc = (b.get("description") or "").strip()[:200]
                currency = (b.get("currency") or "USD").strip()[:8] or "USD"
                shares = [str(x).strip()[:40] for x in (b.get("members") or []) if str(x).strip()]
                try:
                    cents = round(float(b.get("amount") or 0) * 100)
                except (TypeError, ValueError):
                    cents = 0
                if not payer:
                    return self._json(400, {"error": "who paid?"})
                if cents <= 0:
                    return self._json(400, {"error": "enter an amount greater than zero"})
                if not shares:
                    return self._json(400, {"error": "pick at least one person to split between"})
                cur = c.execute("INSERT INTO expenses(trip_id,payer,amount_cents,currency,description,created) "
                                "VALUES(?,?,?,?,?,?)", (tid, payer, cents, currency, desc, now()))
                eid = cur.lastrowid
                for person in shares:
                    c.execute("INSERT INTO expense_shares(expense_id,member) VALUES(?,?)", (eid, person))
                c.commit()
                return self._json(200, expenses_payload(c, tid))

            m = re.match(r"/api/trips/(\d+)/card$", p)
            if m:
                tid = int(m.group(1))
                funder = (b.get("funder") or "").strip()[:40]
                if not funder:
                    return self._json(400, {"error": "pick who funds the card"})
                try:
                    create_trip_card(c, tid, funder, (b.get("currency") or "USD")[:8])
                except Exception as e:
                    return self._json(502, {"error": "card provider error: " + str(e)[:160]})
                return self._json(200, expenses_payload(c, tid))

            m = re.match(r"/api/trips/(\d+)/card/charge$", p)
            if m:
                # Simulate a swipe (dev/test). In live mode real charges arrive via the webhook.
                tid = int(m.group(1))
                try:
                    cents = round(float(b.get("amount") or 0) * 100)
                except (TypeError, ValueError):
                    cents = 0
                if cents <= 0:
                    return self._json(400, {"error": "enter an amount"})
                if not get_trip_card(c, tid):
                    return self._json(400, {"error": "create the trip card first"})
                capture_card_charge(c, tid, cents, (b.get("merchant") or "Card charge").strip()[:80],
                                    "sim_" + secrets.token_hex(8))
                return self._json(200, expenses_payload(c, tid))

            if p == "/api/stripe/webhook":
                # Don't trust the payload — use it only as a ping, then re-fetch the
                # authoritative object from Stripe with our own key before capturing.
                try:
                    obj = (b.get("data") or {}).get("object") or {}
                    kind = b.get("type") or ""
                    if stripe_live() and ("issuing_transaction" in kind or "issuing_authorization" in kind):
                        oid = obj.get("id")
                        path2 = "issuing/transactions/" if "transaction" in kind else "issuing/authorizations/"
                        real = _stripe("GET", path2 + oid)
                        card_id = real.get("card", {}).get("id") if isinstance(real.get("card"), dict) else real.get("card")
                        row = c.execute("SELECT trip_id FROM trip_cards WHERE card_id=?", (card_id,)).fetchone()
                        if row:
                            amt = abs(int(real.get("amount") or 0))
                            mer = ((real.get("merchant_data") or {}).get("name")) or "Card charge"
                            capture_card_charge(c, row["trip_id"], amt, mer, real.get("id"),
                                                (real.get("currency") or "usd").upper())
                except Exception:
                    pass  # never 500 a webhook; Stripe will retry on non-2xx
                return self._json(200, {"received": True})

            if p == "/api/entries":
                eid = b.get("id")
                vals = (b.get("place", ""), b.get("date", ""), b.get("companions", ""),
                        b.get("experience", ""), b.get("ideas", ""))
                if eid:
                    c.execute("UPDATE entries SET place=?,date=?,companions=?,experience=?,ideas=? WHERE id=?",
                              vals + (eid,))
                else:
                    cur = c.execute("INSERT INTO entries(trip_id,place,date,companions,experience,ideas,member,created)"
                                    " VALUES(?,?,?,?,?,?,?,?)", (b.get("trip_id"),) + vals + (b.get("member"), now()))
                    eid = cur.lastrowid
                c.commit()
                return self._json(200, {"id": eid})

            if p == "/api/photos":
                dataurl = b.get("data")
                fn = save_dataurl(dataurl, PHOTOS, "ph")
                if not fn:
                    return self._json(400, {"error": "bad image"})
                # quick AI categorization of the travel pic
                category, tags, caption, people = "Other", [], "", 0
                m = re.match(r"data:(image/[a-zA-Z0-9.+-]+);base64,(.*)", dataurl or "", re.DOTALL)
                raw_bytes = base64.b64decode(m.group(2)) if m else b""
                if m and GEMINI_KEY:
                    info = gemini_vision(raw_bytes, m.group(1))
                    if info:
                        category, tags = info["category"], info["tags"]
                        caption, people = info["caption"], info["people"]
                # auto-place on the map: trust the client's EXIF read, else extract server-side
                plat, plon = b.get("lat"), b.get("lon")
                if plat is None or plon is None:
                    glat, glon = exif_gps(raw_bytes)
                    if glat is not None:
                        plat, plon = glat, glon
                cur = c.execute("INSERT INTO photos(trip_id,entry_id,filename,category,tags,caption,people,lat,lon,member,created)"
                          " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                          (b.get("trip_id"), b.get("entry_id"), fn, category,
                           json.dumps(tags), caption, people, plat, plon, b.get("member"), now()))
                pid = cur.lastrowid
                # auto-match the new photo to a location (if the caller didn't pin it to one)
                matched_eid = None
                if not b.get("entry_id"):
                    matched_eid = match_photo_entry(c, b.get("trip_id"), plat, plon,
                                                    caption, json.dumps(tags))
                    if matched_eid:
                        c.execute("UPDATE photos SET entry_id=? WHERE id=?", (matched_eid, pid))
                c.commit()
                return self._json(200, {"filename": fn, "category": category, "tags": tags,
                                        "caption": caption, "people": people, "entry_id": matched_eid})

            if p == "/api/voice":
                # speech → text for the trip chat (reuses Gemini multimodal: audio in, text out)
                dataurl = b.get("data") or ""
                m = re.match(r"data:(audio/[a-zA-Z0-9.+-]+);base64,(.*)", dataurl, re.DOTALL)
                if not m:
                    return self._json(400, {"error": "bad audio"})
                if not GEMINI_KEY:
                    return self._json(200, {"text": "", "error": "voice transcription unavailable"})
                audio = base64.b64decode(m.group(2))
                mime = m.group(1)
                # Browsers record webm/opus or mp4/aac; transcode to wav (ffmpeg) so Gemini always accepts it.
                if shutil.which("ffmpeg"):
                    try:
                        with tempfile.TemporaryDirectory() as td:
                            src = os.path.join(td, "in"); dst = os.path.join(td, "out.wav")
                            with open(src, "wb") as f:
                                f.write(audio)
                            subprocess.run(["ffmpeg", "-y", "-i", src, "-ar", "16000", "-ac", "1", dst],
                                           capture_output=True, timeout=30)
                            if os.path.exists(dst) and os.path.getsize(dst) > 44:
                                with open(dst, "rb") as f:
                                    audio = f.read()
                                mime = "audio/wav"
                    except Exception:
                        pass
                text = gemini_vision_text(
                    audio, mime,
                    "Transcribe this spoken audio clip to plain text. Output ONLY the exact words spoken — no "
                    "commentary, labels or timestamps. If it is silent or unintelligible, output nothing.")
                return self._json(200, {"text": (text or "").strip()})

            if p == "/api/transcribe":
                # a handwritten journal page: keep the original image AND transcribe it
                dataurl = b.get("data")
                fn = save_dataurl(dataurl, PHOTOS, "jr")
                if not fn:
                    return self._json(400, {"error": "bad image"})
                text = None
                m = re.match(r"data:(image/[a-zA-Z0-9.+-]+);base64,(.*)", dataurl or "", re.DOTALL)
                if m and GEMINI_KEY:
                    text = gemini_vision_text(base64.b64decode(m.group(2)), m.group(1),
                        "This is a photo of a handwritten travel-journal page. Transcribe it into clean typed text. "
                        "Preserve the writer's exact words, wording and voice; fix only obvious line-break artifacts and "
                        "clear spelling slips. If a word is truly illegible, write [?]. Output ONLY the transcription, no commentary.")
                c.execute("INSERT INTO photos(trip_id,entry_id,filename,category,tags,caption,people,lat,lon,created)"
                          " VALUES(?,?,?,?,?,?,?,?,?,?)",
                          (b.get("trip_id"), b.get("entry_id"), fn, "Journal",
                           json.dumps(["handwritten", "journal"]), "Handwritten journal page", 0,
                           b.get("lat"), b.get("lon"), now()))
                c.commit()
                if not text:
                    return self._json(200, {"filename": fn, "text": "", "error": "Saved the page, but couldn't read the handwriting — try a clearer, well-lit photo."})
                return self._json(200, {"filename": fn, "text": text})

            if p == "/api/photos/assign":
                ids = b.get("ids") or ([b.get("id")] if b.get("id") is not None else [])
                eid = b.get("entry_id")
                for pid in ids:
                    c.execute("UPDATE photos SET entry_id=? WHERE id=?", (eid, pid))
                c.commit()
                return self._json(200, {"ok": True, "n": len(ids)})

            if p == "/api/import/icloud":
                raw = b.get("url") or ""
                tok = icloud_cmm_token(raw) or icloud_token(raw)
                try: print(f"[icloud] import request url={raw!r} -> token={tok!r} cmm={bool(icloud_cmm_token(raw))}", flush=True)
                except Exception: pass
                if not tok:
                    return self._json(400, {"error": (
                        "That doesn't look like an iCloud photo link. Paste a shared-album or shared-link URL "
                        "(icloud.com/sharedalbum/#…, share.icloud.com/photos/…, or icloud.com/photos/…/icloudlinks/…). "
                        "A personal iCloud Photos library link can't be imported.")})
                job_id = start_icloud_import(b.get("trip_id"), raw)
                return self._json(200, {"job_id": job_id})

            if p == "/api/map/landmarks":
                return self._json(200, {"job_id": start_landmarks(b.get("trip_id"))})

            if p == "/api/photos/automatch":
                # backfill: match already-uploaded, unplaced photos to locations
                tid = b.get("trip_id")
                trips = [tid] if tid else [r["id"] for r in c.execute("SELECT id FROM trips").fetchall()]
                n = 0
                for t in trips:
                    for ph in c.execute("SELECT id,lat,lon,caption,tags FROM photos "
                                        "WHERE trip_id=? AND entry_id IS NULL", (t,)).fetchall():
                        eid = match_photo_entry(c, t, ph["lat"], ph["lon"], ph["caption"] or "", ph["tags"] or "")
                        if eid:
                            c.execute("UPDATE photos SET entry_id=? WHERE id=?", (eid, ph["id"])); n += 1
                c.commit()
                return self._json(200, {"ok": True, "matched": n})

            if p == "/api/entries/cover":
                # set (or clear, with filename null) the representative photo for a location
                eid = b.get("entry_id"); fn = b.get("filename")
                if fn:
                    ok = c.execute("SELECT 1 FROM photos WHERE entry_id=? AND filename=? LIMIT 1", (eid, fn)).fetchone()
                    if not ok:
                        return self._json(400, {"error": "photo not in this place"})
                c.execute("UPDATE entries SET cover=? WHERE id=?", (fn, eid))
                c.commit()
                return self._json(200, {"ok": True, "cover": fn})

            if p == "/api/section":
                eid, kind = b.get("entry_id"), b.get("kind")
                if kind not in SECTION_KINDS:
                    return self._json(400, {"error": "unknown section"})
                e = c.execute("SELECT * FROM entries WHERE id=?", (eid,)).fetchone()
                if not e:
                    return self._json(404, {"error": "no such place"})
                content = generate_section(kind, dict(e))
                if not content:
                    return self._json(200, {"error": "AI unavailable right now — try again in a moment"})
                # new active version; the previous one stays in history (active=0)
                c.execute("UPDATE ai_sections SET active=0 WHERE entry_id=? AND kind=?", (eid, kind))
                c.execute("INSERT INTO ai_sections(entry_id,kind,content,active,created) VALUES(?,?,?,1,?)",
                          (eid, kind, content, now()))
                c.commit()
                return self._json(200, {"section": section_payload(c, eid, kind)})

            if p == "/api/photos/backfill-gps":
                # read embedded EXIF GPS from stored photos that have none, place them on the map,
                # and auto-match freshly-located photos to their nearest place.
                tid = b.get("trip_id")
                if tid:
                    rows = c.execute("SELECT id,filename,trip_id,entry_id FROM photos WHERE trip_id=? AND (lat IS NULL OR lon IS NULL)", (tid,)).fetchall()
                else:
                    rows = c.execute("SELECT id,filename,trip_id,entry_id FROM photos WHERE lat IS NULL OR lon IS NULL").fetchall()
                placed = 0; matched = 0
                for r in rows:
                    fp = os.path.join(PHOTOS, r["filename"] or "")
                    if not r["filename"] or not os.path.exists(fp):
                        continue
                    try:
                        with open(fp, "rb") as fh:
                            glat, glon = exif_gps(fh.read(300000))
                    except Exception:
                        glat = glon = None
                    if glat is None:
                        continue
                    c.execute("UPDATE photos SET lat=?,lon=? WHERE id=?", (glat, glon, r["id"]))
                    placed += 1
                    if not r["entry_id"]:
                        eid = match_photo_entry(c, r["trip_id"], glat, glon)
                        if eid:
                            c.execute("UPDATE photos SET entry_id=? WHERE id=?", (eid, r["id"]))
                            matched += 1
                c.commit()
                return self._json(200, {"placed": placed, "matched": matched, "scanned": len(rows)})

            m = re.match(r"/api/quiz/(\d+)/complete$", p)
            if m:
                eid = int(m.group(1))
                device = (b.get("device") or "").strip()
                name = (b.get("name") or "").strip()
                score = int(b.get("score") or 0)
                total = int(b.get("total") or 0)
                bundle = quiz_bundle(c, eid, device)   # ensures quiz+reward exist
                if not bundle or not bundle.get("questions"):
                    return self._json(200, {"error": "quiz unavailable"})
                row = c.execute("SELECT best,completed FROM quiz_progress WHERE entry_id=? AND device=?",
                                (eid, device)).fetchone()
                best = max(score, row["best"] if row else 0)
                if row:
                    c.execute("UPDATE quiz_progress SET best=?,total=?,completed=1,name=?,updated=? "
                              "WHERE entry_id=? AND device=?", (best, total, name, now(), eid, device))
                else:
                    c.execute("INSERT INTO quiz_progress(entry_id,device,name,best,total,completed,created,updated) "
                              "VALUES(?,?,?,?,?,1,?,?)", (eid, device, name, best, total, now(), now()))
                c.commit()
                rw = c.execute("SELECT reward FROM quizzes WHERE entry_id=?", (eid,)).fetchone()
                miles = best * 20 + (50 if (row is None or not row["completed"]) else 0)  # bonus on first clear
                return self._json(200, {"completed": 1, "best": best, "total": total,
                                        "reward": (rw["reward"] if rw else "") or "",
                                        "miles": miles, "first_clear": bool(row is None or not row["completed"])})

            if p == "/api/section/restore":
                vid = b.get("id")
                row = c.execute("SELECT entry_id,kind FROM ai_sections WHERE id=?", (vid,)).fetchone()
                if not row:
                    return self._json(404, {"error": "no such version"})
                eid, kind = row["entry_id"], row["kind"]
                c.execute("UPDATE ai_sections SET active=0 WHERE entry_id=? AND kind=?", (eid, kind))
                c.execute("UPDATE ai_sections SET active=1 WHERE id=?", (vid,))
                c.commit()
                return self._json(200, {"section": section_payload(c, eid, kind)})

            if p == "/api/briefing":
                place = b.get("place", "").strip()
                lat, lon, disp = geocode(place)
                wiki = wiki_extract(place, lat, lon)
                prompt = (f"You are a well-traveled local historian. In 4-6 warm, vivid sentences, tell a traveler "
                          f"about {place}. Cover what makes it special and a genuine piece of its history or culture. "
                          f"Be specific and evocative, not a list. No preamble.\n\n"
                          f"Reference notes (may be partial):\n{wiki[:1500]}")
                text = gemini_text(prompt) or (wiki[:600] if wiki else None)
                if not text:
                    return self._json(200, {"error": "AI unavailable and no reference found"})
                text = text.strip()
                if b.get("entry_id"):
                    c.execute("UPDATE entries SET briefing=? WHERE id=?", (text, b["entry_id"]))
                    c.commit()
                return self._json(200, {"text": text})

            if p == "/api/reflect":
                prompt = (f"A traveler just visited {b.get('place','a place')}"
                          f"{' with ' + b.get('companions') if b.get('companions') else ''}. "
                          f"Their rough notes — experience: {b.get('experience','(none)')}; "
                          f"ideas they grappled with: {b.get('ideas','(none)')}. "
                          f"As a thoughtful journaling companion, offer 3 short, open, specific questions that would help them "
                          f"reflect more deeply on the people, the experience, and the ideas. "
                          f'Return JSON: {{"prompts":["...","...","..."]}}')
                raw = gemini_text(prompt, want_json=True)
                try:
                    prompts = json.loads(raw).get("prompts", [])
                except Exception:
                    prompts = []
                if not prompts:
                    # never leave the writer hanging — tailored, offline fallback prompts
                    place = b.get("place") or "this place"
                    comp = b.get("companions")
                    prompts = [
                        f"What's one small, specific moment from {place} you don't want to forget?",
                        (f"What did being there with {comp} change about how you saw it?" if comp
                         else "Who were you with, and how did they shape the day?"),
                        "What idea or question are you still turning over from this place?"]
                return self._json(200, {"prompts": prompts})

            if p == "/api/journal":
                prompt = (f"Turn these rough travel notes into a reflective first-person journal entry "
                          f"(1-2 short paragraphs, warm and honest, the traveler's own voice, no clichés, no title).\n"
                          f"Place: {b.get('place','')}\nDate: {b.get('date','')}\n"
                          f"With: {b.get('companions','')}\nExperience: {b.get('experience','')}\n"
                          f"Ideas grappled with: {b.get('ideas','')}")
                text = gemini_text(prompt)
                return self._json(200, {"text": text.strip()} if text else {"error": "unavailable"})

            if p == "/api/chat":
                tid = b.get("trip_id")
                msg = (b.get("message") or "").strip()
                d = trip_dict(c, tid)
                if not d:
                    return self._json(404, {"error": "not found"})
                if not msg:
                    return self._json(400, {"error": "empty message"})
                c.execute("INSERT INTO chat_messages(trip_id,role,content,created) VALUES(?,?,?,?)",
                          (tid, "user", msg, now()))
                c.commit()
                if not GEMINI_KEY:
                    reply = "AI chat isn't available right now — no AI key is configured on the server."
                    c.execute("INSERT INTO chat_messages(trip_id,role,content,created) VALUES(?,?,?,?)",
                              (tid, "assistant", reply, now()))
                    c.commit()
                    return self._json(200, {"reply": reply, "saved": []})
                # ---- trip context (system instruction) ----
                ctx = [f"Trip: {d.get('title','')}" + (f" to {d['destination']}" if d.get('destination') else "")]
                dates = " to ".join([x for x in (d.get('start_date'), d.get('end_date')) if x])
                if dates:
                    ctx.append(f"Dates: {dates}")
                places = [e.get('place', '') for e in d["entries"] if (e.get('place') or '').strip()]
                if places:
                    ctx.append("Places logged: " + ", ".join(places))
                for e in d["entries"]:
                    if (e.get('experience') or '').strip() or (e.get('ideas') or '').strip():
                        seg = f"  • {e.get('place','')}:"
                        if (e.get('experience') or '').strip():
                            seg += " " + e['experience'].strip()[:300]
                        if (e.get('ideas') or '').strip():
                            seg += " | ideas: " + e['ideas'].strip()[:150]
                        ctx.append(seg)
                if not d["entries"]:
                    ctx.append("(No places logged yet.)")
                existing = c.execute("SELECT category,text FROM trip_notes WHERE trip_id=? ORDER BY id", (tid,)).fetchall()
                if existing:
                    by = {}
                    for r in existing:
                        by.setdefault(r["category"], []).append(r["text"])
                    ctx.append("Existing notebook (do NOT duplicate these items):")
                    for cat, items in by.items():
                        ctx.append(f"  [{cat}] " + " | ".join(items[:15]))
                system = (
                    "You are Trip Sync's trip companion — a warm, knowledgeable travel guide and journaling buddy for the "
                    "specific trip below. Chat naturally: give concrete recommendations, history, planning help and reflective "
                    "prompts, grounded in the trip context. Keep replies conversational and fairly concise.\n\n"
                    "YOU ALSO KEEP A STRUCTURED NOTEBOOK for this trip. Whenever the conversation surfaces something worth "
                    "remembering, call the save_trip_note tool to file it — one note per distinct item. Save durable, itemized "
                    "facts such as: the place's history, specific spots/attractions to visit, places the traveler already "
                    "visited, food & restaurants, practical tips, logistics. Choose a short clean category name (e.g. 'History', "
                    "'Spots to Visit', 'Places Visited', 'Food', 'Tips'); reuse an existing category when it fits, and create a "
                    "NEW category when nothing fits. Never duplicate notes already in the notebook. Save notes silently as you "
                    "go, then give your normal conversational reply.\n\n"
                    "=== TRIP CONTEXT ===\n" + "\n".join(ctx))
                hist = list(reversed(c.execute(
                    "SELECT role,content FROM chat_messages WHERE trip_id=? ORDER BY id DESC LIMIT 16",
                    (tid,)).fetchall()))
                contents = [{"role": ("user" if h["role"] == "user" else "model"),
                             "parts": [{"text": h["content"]}]} for h in hist]
                tools = [{"functionDeclarations": [{
                    "name": "save_trip_note",
                    "description": ("Save one itemized note to this trip's structured notebook, under a category. "
                                    "Create a new category if none fits. One distinct fact/spot per call."),
                    "parameters": {"type": "object", "properties": {
                        "category": {"type": "string", "description": "Short category name, e.g. History, Spots to Visit, Places Visited, Food, Tips."},
                        "note": {"type": "string", "description": "A single concise note or item."},
                        "place": {"type": "string", "description": "Optional specific place/spot this note is about."}},
                        "required": ["category", "note"]}}]}]
                saved = []
                reply = ""
                for _ in range(4):
                    cand = gemini_generate(contents, system=system, tools=tools)
                    if not cand:
                        break
                    parts = cand.get("parts", []) or []
                    fcs = [p["functionCall"] for p in parts if isinstance(p, dict) and "functionCall" in p]
                    if not fcs:
                        texts = [p["text"] for p in parts if isinstance(p, dict) and p.get("text")]
                        if texts:
                            reply = "\n".join(texts).strip()
                        break
                    contents.append({"role": "model", "parts": parts})
                    resp_parts = []
                    for fc in fcs:
                        args = fc.get("args", {}) or {}
                        ok = False
                        if fc.get("name") == "save_trip_note":
                            cat = (args.get("category") or "Notes").strip()[:40] or "Notes"
                            txt = (args.get("note") or "").strip()[:500]
                            plc = (args.get("place") or "").strip()[:80]
                            if txt and not c.execute(
                                    "SELECT 1 FROM trip_notes WHERE trip_id=? AND category=? AND text=?",
                                    (tid, cat, txt)).fetchone():
                                c.execute("INSERT INTO trip_notes(trip_id,category,text,place,source,created) VALUES(?,?,?,?,?,?)",
                                          (tid, cat, txt, plc, "ai", now()))
                                c.commit()
                                saved.append({"category": cat, "text": txt})
                                ok = True
                        resp_parts.append({"functionResponse": {"name": fc.get("name", "unknown"), "response": {"saved": ok}}})
                    contents.append({"role": "user", "parts": resp_parts})
                if not reply:
                    reply = ("Added that to your trip notebook." if saved
                             else "Sorry — I couldn't generate a response just now. Try again in a moment.")
                c.execute("INSERT INTO chat_messages(trip_id,role,content,created) VALUES(?,?,?,?)",
                          (tid, "assistant", reply, now()))
                c.commit()
                return self._json(200, {"reply": reply, "saved": saved})

            if p == "/api/notes":
                tid = b.get("trip_id")
                cat = (b.get("category") or "Notes").strip()[:40] or "Notes"
                txt = (b.get("text") or "").strip()[:500]
                plc = (b.get("place") or "").strip()[:80]
                if not tid or not txt:
                    return self._json(400, {"error": "trip_id and text required"})
                cur = c.execute("INSERT INTO trip_notes(trip_id,category,text,place,source,created) VALUES(?,?,?,?,?,?)",
                                (tid, cat, txt, plc, "user", now()))
                c.commit()
                return self._json(200, {"id": cur.lastrowid, "category": cat, "text": txt})

            if p == "/api/recap":
                d = trip_dict(c, b.get("trip_id"))
                if not d:
                    return self._json(404, {"error": "not found"})
                parts = []
                for e in d["entries"]:
                    parts.append(f"- {e['place']} ({e.get('date','')}) with {e.get('companions','')}: "
                                 f"{e.get('experience','')} | ideas: {e.get('ideas','')}")
                prompt = (f"Write a warm, reflective recap (2-3 short paragraphs) of this trip titled "
                          f"\"{d['title']}\"{' to ' + d['destination'] if d['destination'] else ''}, weaving together "
                          f"the places, the people, and the ideas the traveler wrestled with. First person, honest, no clichés.\n\n"
                          + "\n".join(parts))
                text = gemini_text(prompt)
                return self._json(200, {"text": text.strip()} if text else {"error": "unavailable"})

            if p == "/api/collage":
                tid = b.get("trip_id")
                # offline canvas collage: client sends ready data URL
                if b.get("data"):
                    fn = save_dataurl(b["data"], COLLAGES, "col")
                    if not fn:
                        return self._json(400, {"error": "bad image"})
                    c.execute("INSERT INTO collages(trip_id,filename,style,created) VALUES(?,?,?,?)",
                              (tid, fn, b.get("style", "quick"), now()))
                    c.execute("UPDATE trips SET cover=? WHERE id=?", (fn, tid))
                    c.commit()
                    return self._json(200, {"filename": fn})
                # AI collage
                if not GEMINI_KEY:
                    return self._json(200, {"error": "No AI key — use Quick collage"})
                ids = b.get("photo_ids", [])
                imgs = []
                for pid in ids[:8]:
                    row = c.execute("SELECT filename FROM photos WHERE id=?", (pid,)).fetchone()
                    if not row:
                        continue
                    fp = os.path.join(PHOTOS, row["filename"])
                    if os.path.isfile(fp):
                        mime = mimetypes.guess_type(fp)[0] or "image/jpeg"
                        with open(fp, "rb") as f:
                            imgs.append((mime, f.read()))
                if not imgs:
                    return self._json(200, {"error": "no photos selected"})
                t = c.execute("SELECT * FROM trips WHERE id=?", (tid,)).fetchone()
                style = STYLE_PROMPTS.get(b.get("style", "scrapbook"), STYLE_PROMPTS["scrapbook"])
                prompt = (f"Create {style}. Compose ALL of the provided photos together into a single beautiful "
                          f"travel collage image celebrating a trip titled \"{t['title']}\""
                          f"{(' (' + t['destination'] + ')') if t['destination'] else ''}. "
                          f"Keep the real subjects of the photos recognizable; arrange them artfully as one cohesive piece. "
                          f"{b.get('note','')}".strip())
                res = gemini_image(prompt, imgs)
                if not res:
                    return self._json(200, {"error": "AI collage failed — try Quick collage"})
                mime, raw = res
                ext = mimetypes.guess_extension(mime) or ".jpg"
                if ext == ".jpe":
                    ext = ".jpg"
                fn = "col-" + hashlib.sha1((now() + str(len(raw))).encode()).hexdigest()[:12] + ext
                with open(os.path.join(COLLAGES, fn), "wb") as f:
                    f.write(raw)
                c.execute("INSERT INTO collages(trip_id,filename,style,created) VALUES(?,?,?,?)",
                          (tid, fn, b.get("style", "ai"), now()))
                c.execute("UPDATE trips SET cover=? WHERE id=?", (fn, tid))
                c.commit()
                return self._json(200, {"filename": fn})

            return self._send(404, b"not found", "text/plain")
        finally:
            c.close()

    # ---- DELETE ----
    def do_DELETE(self):
        p = self._path()
        if BASE and p.startswith(BASE):
            p = p[len(BASE):] or "/"
        c = db()
        try:
            m = re.match(r"/api/trips/(\d+)$", p)
            if m:
                tid = int(m.group(1))
                for row in c.execute("SELECT filename FROM photos WHERE trip_id=?", (tid,)).fetchall():
                    _rm(os.path.join(PHOTOS, row["filename"]))
                for row in c.execute("SELECT filename FROM collages WHERE trip_id=?", (tid,)).fetchall():
                    _rm(os.path.join(COLLAGES, row["filename"]))
                c.execute("DELETE FROM entries WHERE trip_id=?", (tid,))
                c.execute("DELETE FROM photos WHERE trip_id=?", (tid,))
                c.execute("DELETE FROM collages WHERE trip_id=?", (tid,))
                c.execute("DELETE FROM chat_messages WHERE trip_id=?", (tid,))
                c.execute("DELETE FROM trip_notes WHERE trip_id=?", (tid,))
                c.execute("DELETE FROM trip_members WHERE trip_id=?", (tid,))
                for ex in c.execute("SELECT id FROM expenses WHERE trip_id=?", (tid,)).fetchall():
                    c.execute("DELETE FROM expense_shares WHERE expense_id=?", (ex["id"],))
                c.execute("DELETE FROM expenses WHERE trip_id=?", (tid,))
                c.execute("DELETE FROM trips WHERE id=?", (tid,))
                c.commit()
                return self._json(200, {"ok": True})
            m = re.match(r"/api/expenses/(\d+)$", p)
            if m:
                eid = int(m.group(1))
                c.execute("DELETE FROM expense_shares WHERE expense_id=?", (eid,))
                c.execute("DELETE FROM expenses WHERE id=?", (eid,))
                c.commit()
                return self._json(200, {"ok": True})
            m = re.match(r"/api/notes/(\d+)$", p)
            if m:
                c.execute("DELETE FROM trip_notes WHERE id=?", (int(m.group(1)),))
                c.commit()
                return self._json(200, {"ok": True})
            m = re.match(r"/api/entries/(\d+)$", p)
            if m:
                eid = int(m.group(1))
                c.execute("UPDATE photos SET entry_id=NULL WHERE entry_id=?", (eid,))  # keep photos, just unassign
                c.execute("DELETE FROM ai_sections WHERE entry_id=?", (eid,))
                c.execute("DELETE FROM entries WHERE id=?", (eid,))
                c.commit()
                return self._json(200, {"ok": True})
            m = re.match(r"/api/collage/(\d+)$", p)
            if m:
                row = c.execute("SELECT filename FROM collages WHERE id=?", (int(m.group(1)),)).fetchone()
                if row:
                    _rm(os.path.join(COLLAGES, row["filename"]))
                c.execute("DELETE FROM collages WHERE id=?", (int(m.group(1)),))
                c.commit()
                return self._json(200, {"ok": True})
            m = re.match(r"/api/photos/(\d+)$", p)
            if m:
                row = c.execute("SELECT filename FROM photos WHERE id=?", (int(m.group(1)),)).fetchone()
                if row:
                    _rm(os.path.join(PHOTOS, row["filename"]))
                c.execute("DELETE FROM photos WHERE id=?", (int(m.group(1)),))
                c.commit()
                return self._json(200, {"ok": True})
            return self._send(404, b"not found", "text/plain")
        finally:
            c.close()

    def log_message(self, *a):
        pass

def _rm(fp):
    try:
        os.remove(fp)
    except OSError:
        pass

ICON_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
            '<defs>'
            '<linearGradient id="tlg" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#f6ad5b"/><stop offset="1" stop-color="#e5683f"/></linearGradient>'
            '<linearGradient id="tls" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#ffe6d2"/></linearGradient>'
            '</defs>'
            '<rect width="512" height="512" rx="116" fill="url(#tlg)"/>'
            # dotted travel route arc beneath the pin
            '<path d="M150 408 q106 -54 212 0" fill="none" stroke="#fff" stroke-width="14" '
            'stroke-linecap="round" stroke-dasharray="2 34" opacity="0.6"/>'
            # location pin (soft top-to-warm gradient)
            '<path d="M256 90 c-71 0 -128 57 -128 128 c0 93 128 218 128 218 s128 -125 128 -218 '
            'c0 -71 -57 -128 -128 -128 z" fill="url(#tls)"/>'
            # compass rose inside the pin: gradient disc + white 4-point star
            '<circle cx="256" cy="218" r="72" fill="url(#tlg)"/>'
            '<path d="M256 158 l17 43 43 17 -43 17 -17 43 -17 -43 -43 -17 43 -17 z" fill="#fff"/>'
            '<circle cx="256" cy="218" r="9" fill="#e5683f"/></svg>')

if __name__ == "__main__":
    init_db()
    print(f"travelog on {HOST}:{PORT}  base={BASE or '/'}  ai={'on' if GEMINI_KEY else 'OFF'}  db={DB}")
    ThreadingHTTPServer((HOST, PORT), H).serve_forever()

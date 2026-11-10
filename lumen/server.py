#!/usr/bin/env python3
"""
Lumen — light up the world, one breath at a time.

A gamified meditation app. Every session you complete adds a point of light to a
living world map, earns you Light (XP), builds your streak, and moves you up the
weekly leagues (Ember -> Supernova). See everyone who meditated today on the map,
climb the leaderboards, journal your practice, and unlock achievements.

Zero third-party deps — stdlib only (http.server + sqlite3), reboot-safe + light.
Storage lives in ./data (sqlite). Mount under the command hub with LUMEN_BASE=/lumen.
Soundscapes are synthesized client-side (Web Audio) so there are no audio assets.
"""
import os, json, re, sqlite3, hashlib, hmac, secrets, time, math, random, threading, base64
import urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone, date, timedelta

PORT = int(os.environ.get("PORT") or os.environ.get("LUMEN_PORT", "18834"))  # Railway sets $PORT
HOST = os.environ.get("LUMEN_HOST", "127.0.0.1")  # set 0.0.0.0 in Docker/Railway
BASE = (os.environ.get("LUMEN_BASE", "").rstrip("/"))  # e.g. "/lumen" or ""
HERE = os.path.dirname(os.path.abspath(__file__))
# owner email(s) with access to /admin (comma-separated). Default: Matthew.
OWNER_EMAILS = {e.strip().lower() for e in
                (os.environ.get("LUMEN_OWNER_EMAILS", "m@m.com")).split(",") if e.strip()}
DATA = os.environ.get("LUMEN_DATA") or os.path.join(HERE, "data")  # point at a mounted volume in prod
DB = os.path.join(DATA, "lumen.db")
SPOT_DIR = os.path.join(DATA, "spots")  # user photos of where they meditated
os.makedirs(DATA, exist_ok=True)
os.makedirs(SPOT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# storage
# ---------------------------------------------------------------------------

_dblock = threading.Lock()

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=4000")
    return c

def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY,
      email TEXT UNIQUE, name TEXT, salt TEXT, hash TEXT,
      light INTEGER DEFAULT 0,            -- lifetime Light (XP)
      streak INTEGER DEFAULT 0,
      best_streak INTEGER DEFAULT 0,
      last_day TEXT,                      -- UTC date of last completed session
      total_minutes INTEGER DEFAULT 0,
      total_sessions INTEGER DEFAULT 0,
      lat REAL, lon REAL, city TEXT,      -- coarse home location
      is_bot INTEGER DEFAULT 0,
      created TEXT);
    CREATE TABLE IF NOT EXISTS sessions(
      id INTEGER PRIMARY KEY, user_id INTEGER,
      minutes INTEGER, soundscape TEXT, light INTEGER,
      lat REAL, lon REAL, city TEXT, mood TEXT, note TEXT,
      started TEXT, ended TEXT, day TEXT, week TEXT);
    CREATE TABLE IF NOT EXISTS journal(
      id INTEGER PRIMARY KEY, user_id INTEGER,
      prompt TEXT, text TEXT, mood TEXT, shared INTEGER DEFAULT 0,
      session_id INTEGER, created TEXT);
    CREATE TABLE IF NOT EXISTS achievements(
      id INTEGER PRIMARY KEY, user_id INTEGER, code TEXT, created TEXT,
      UNIQUE(user_id, code));
    CREATE TABLE IF NOT EXISTS items(
      id INTEGER PRIMARY KEY, user_id INTEGER, code TEXT, created TEXT,
      UNIQUE(user_id, code));
    CREATE TABLE IF NOT EXISTS mkt_state(
      key TEXT PRIMARY KEY, status TEXT DEFAULT 'todo', note TEXT, updated TEXT);
    CREATE TABLE IF NOT EXISTS mkt_subtasks(
      id INTEGER PRIMARY KEY AUTOINCREMENT, parent TEXT, text TEXT,
      status TEXT DEFAULT 'todo', pos INTEGER DEFAULT 0, created TEXT);
    CREATE TABLE IF NOT EXISTS push_tokens(
      id INTEGER PRIMARY KEY, user_id INTEGER, token TEXT UNIQUE,
      platform TEXT, created TEXT, updated TEXT);
    CREATE TABLE IF NOT EXISTS notif_prefs(
      user_id INTEGER PRIMARY KEY, enabled INTEGER DEFAULT 1,
      quiet_start INTEGER DEFAULT 21, quiet_end INTEGER DEFAULT 8,
      tz_offset_min INTEGER DEFAULT 0, cats TEXT, sto INTEGER DEFAULT 1,
      pref_hour INTEGER, updated TEXT);
    CREATE TABLE IF NOT EXISTS notif_log(
      id INTEGER PRIMARY KEY, user_id INTEGER, category TEXT, title TEXT,
      body TEXT, dedupe_key TEXT, status TEXT DEFAULT 'queued',
      created TEXT, sent TEXT, opened TEXT);
    CREATE INDEX IF NOT EXISTS ix_notiflog_user ON notif_log(user_id, dedupe_key);
    CREATE INDEX IF NOT EXISTS ix_notiflog_status ON notif_log(status);
    CREATE TABLE IF NOT EXISTS mod_reports(
      id INTEGER PRIMARY KEY, entry_id INTEGER, reporter_id INTEGER, created TEXT,
      UNIQUE(entry_id, reporter_id));
    CREATE TABLE IF NOT EXISTS mod_blocks(
      blocker_id INTEGER, blocked_id INTEGER, created TEXT,
      UNIQUE(blocker_id, blocked_id));
    CREATE TABLE IF NOT EXISTS companions(
      id INTEGER PRIMARY KEY, user_id INTEGER, code TEXT,
      fed INTEGER DEFAULT 0, created TEXT,
      UNIQUE(user_id, code));
    CREATE TABLE IF NOT EXISTS user_notes(
      id INTEGER PRIMARY KEY, user_id INTEGER, note TEXT, created TEXT);
    CREATE INDEX IF NOT EXISTS ix_sess_user ON sessions(user_id);
    CREATE INDEX IF NOT EXISTS ix_sess_day ON sessions(day);
    CREATE INDEX IF NOT EXISTS ix_sess_week ON sessions(week);
    CREATE INDEX IF NOT EXISTS ix_jour_user ON journal(user_id);
    """)
    cols = [r[1] for r in c.execute("PRAGMA table_info(users)").fetchall()]
    for col, ddl in (("equipped", "equipped TEXT"), ("motes", "motes INTEGER DEFAULT 0"),
                     ("companion", "companion TEXT"), ("lifeos", "lifeos TEXT"),
                     ("lo_prompts", "lo_prompts TEXT"), ("lo_prompts_day", "lo_prompts_day TEXT"),
                     ("chal_streak", "chal_streak INTEGER DEFAULT 0"),
                     ("chal_best", "chal_best INTEGER DEFAULT 0"),
                     ("chal_last_day", "chal_last_day TEXT"),
                     ("sun_sign", "sun_sign TEXT"),
                     ("birth_date", "birth_date TEXT"),
                     ("birth_time", "birth_time TEXT"),
                     ("birth_place", "birth_place TEXT"),
                     ("birth_tz", "birth_tz INTEGER"),
                     ("horo", "horo TEXT"),
                     ("horo_day", "horo_day TEXT"),
                     ("goal_days", "goal_days INTEGER DEFAULT 0"),  # meditation days/week pledge (0=unset)
                     ("tier", "tier TEXT DEFAULT 'free'"),          # free | premium (RevenueCat wires this later)
                     ("email_optout", "email_optout INTEGER DEFAULT 0"),  # 1 = unsubscribed from lifecycle email
                     ("unsub_token", "unsub_token TEXT"),           # per-user unsubscribe token
                     ("phone", "phone TEXT"),                       # E.164 mobile, if given at signup
                     ("sms_consent", "sms_consent INTEGER DEFAULT 0"),  # 1 = opted in to SMS notifications
                     ("sms_optout", "sms_optout INTEGER DEFAULT 0"),    # 1 = texted STOP / unsubscribed
                     ("last_journey", "last_journey TEXT")):        # track key of the most recently practiced journey
        if col not in cols:
            c.execute(f"ALTER TABLE users ADD COLUMN {ddl}")
    # Daily "Morning Pilgrimage" challenge: sit in the morning, at a new place, with a photo.
    c.execute("""CREATE TABLE IF NOT EXISTS challenges(
      user_id INTEGER, day TEXT,
      morning INTEGER DEFAULT 0, new_place INTEGER DEFAULT 0, photo INTEGER DEFAULT 0,
      done INTEGER DEFAULT 0, place TEXT, bonus INTEGER DEFAULT 0, created TEXT,
      PRIMARY KEY(user_id, day))""")
    # daily horoscope, generated once per sign per day and shared across users
    c.execute("""CREATE TABLE IF NOT EXISTS horoscopes(
      sign TEXT, day TEXT, text TEXT, theme TEXT, soundscape TEXT, created TEXT,
      PRIMARY KEY(sign, day))""")
    # pre-launch waitlist for the physical Lumen Journal (the anchor product)
    c.execute("""CREATE TABLE IF NOT EXISTS journal_waitlist(
      email TEXT PRIMARY KEY, created TEXT)""")
    # lifecycle email log — one row per (user, dedupe_key); mirrors notif_log so the
    # engine never emails the same beat twice and we can report what was sent.
    c.execute("""CREATE TABLE IF NOT EXISTS email_log(
      id INTEGER PRIMARY KEY, user_id INTEGER, kind TEXT, dedupe_key TEXT,
      status TEXT, created TEXT, sent TEXT)""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_email_log_uid ON email_log(user_id)")
    c.execute("""CREATE TABLE IF NOT EXISTS sms_log(
      id INTEGER PRIMARY KEY, user_id INTEGER, kind TEXT, dedupe_key TEXT,
      status TEXT, created TEXT, sent TEXT)""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sms_log_uid ON sms_log(user_id)")
    # first-party product analytics — screen views, onboarding steps, etc.
    c.execute("""CREATE TABLE IF NOT EXISTS events(
      id INTEGER PRIMARY KEY, anon_id TEXT, user_id INTEGER, name TEXT,
      props TEXT, screen TEXT, created TEXT)""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_events_name ON events(name, created)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_events_anon ON events(anon_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_events_created ON events(created)")
    # premium interest / waitlist (until RevenueCat is live, 'upgrade' CTAs land here)
    c.execute("""CREATE TABLE IF NOT EXISTS premium_waitlist(
      user_id INTEGER PRIMARY KEY, email TEXT, created TEXT)""")
    # new-user feedback survey: one row per submission, full answers stored as JSON
    c.execute("""CREATE TABLE IF NOT EXISTS survey(
      id INTEGER PRIMARY KEY, user_id INTEGER, email TEXT, nps INTEGER,
      data TEXT, created TEXT)""")
    # password-reset codes: a 6-digit code (stored hashed) with expiry + attempt cap
    c.execute("""CREATE TABLE IF NOT EXISTS password_resets(
      email TEXT PRIMARY KEY, code_hash TEXT, expires REAL, tries INTEGER DEFAULT 0, sent REAL)""")
    scols = [r[1] for r in c.execute("PRAGMA table_info(sessions)").fetchall()]
    if "lesson" not in scols:
        c.execute("ALTER TABLE sessions ADD COLUMN lesson TEXT")
    # spot photos: a picture of where you sat, optionally shared to the community
    if "photo" not in scols:
        c.execute("ALTER TABLE sessions ADD COLUMN photo TEXT")
    if "photo_share" not in scols:
        c.execute("ALTER TABLE sessions ADD COLUMN photo_share INTEGER DEFAULT 0")
    # stable ~1km place key from the RAW (pre-fuzz) coords, so revisiting the same
    # real spot resolves to the same place for the pilgrimage passport
    if "pk" not in scols:
        c.execute("ALTER TABLE sessions ADD COLUMN pk TEXT")
    npcols = [r[1] for r in c.execute("PRAGMA table_info(notif_prefs)").fetchall()]
    if "pref_hour" not in npcols:
        c.execute("ALTER TABLE notif_prefs ADD COLUMN pref_hour INTEGER")
    # the Keeper's AI reflection, written back on each sealed letter
    jcols = [r[1] for r in c.execute("PRAGMA table_info(journal)").fetchall()]
    if "reflection" not in jcols:
        c.execute("ALTER TABLE journal ADD COLUMN reflection TEXT")
    # Three journaling categories: 'daily' (default), 'deep' (pillar work), 'season'.
    # Deep entries carry their pillar; season entries carry an optional season label (in `place`).
    for jcol, jddl in (("kind", "kind TEXT DEFAULT 'daily'"),
                       ("pillar", "pillar TEXT"), ("place", "place TEXT")):
        if jcol not in jcols:
            c.execute(f"ALTER TABLE journal ADD COLUMN {jddl}")
    # Pre-check marketing steps that are already true (app is LIVE on the App Store +
    # the marketing site is live). INSERT OR IGNORE so any later owner toggle wins.
    for _k in ("apple_aso#0", "apple_aso#1", "apple_aso#2", "apple_aso#3",
               "website#0", "website#3", "o_apple_aso#0", "o_apple_aso#2"):
        c.execute("INSERT OR IGNORE INTO mkt_state(key,status,note,updated) VALUES(?,?,?,?)",
                  (_k, "done", "auto: already live", now_iso()))
    c.commit(); c.close()

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def today_str():
    return datetime.now(timezone.utc).date().isoformat()

def week_str(d=None):
    d = d or datetime.now(timezone.utc).date()
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"

# ---------------------------------------------------------------------------
# auth (rolodex pattern: pbkdf2 + in-memory token sessions + cookie)
# ---------------------------------------------------------------------------

SESSIONS = {}  # token -> (email, expires_epoch)
SESSION_TTL = 60 * 60 * 24 * 30

def _hash_pw(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200000).hex()

def new_session(email):
    tok = secrets.token_urlsafe(32)
    SESSIONS[tok] = (email, time.time() + SESSION_TTL)
    return tok

def session_email(tok):
    v = SESSIONS.get(tok)
    if not v:
        return None
    email, exp = v
    if time.time() > exp:
        SESSIONS.pop(tok, None)
        return None
    return email

# Catch obvious email typos at signup (a ".con" address can never receive mail).
_TYPO_DOMAINS = {
    "gmail.con": "gmail.com", "gmail.co": "gmail.com", "gmail.cm": "gmail.com", "gmail.comm": "gmail.com",
    "gmial.com": "gmail.com", "gmai.com": "gmail.com", "gmaill.com": "gmail.com", "gmail.xom": "gmail.com",
    "hotmail.con": "hotmail.com", "hotmial.com": "hotmail.com", "hotmail.co": "hotmail.com",
    "yahoo.con": "yahoo.com", "yaho.com": "yahoo.com", "yahoo.co": "yahoo.com",
    "outlook.con": "outlook.com", "outlook.co": "outlook.com", "icloud.con": "icloud.com", "icloud.co": "icloud.com",
}
_BAD_TLD = {"con", "cpm", "ocm", "comm", "cmo", "xom", "vom", "coom", "vcom"}

def email_typo_fix(email):
    """Return a corrected address for an obvious typo, else None."""
    try:
        local, dom = email.rsplit("@", 1)
    except ValueError:
        return None
    dom = dom.lower()
    if dom in _TYPO_DOMAINS:
        return local + "@" + _TYPO_DOMAINS[dom]
    tld = dom.rsplit(".", 1)[-1] if "." in dom else ""
    if tld in _BAD_TLD:
        return local + "@" + dom[: -len(tld)] + "com"
    return None

# --- transactional email -----------------------------------------------------
# Railway has no mail service and Cloudflare only forwards inbound mail, so we
# send via a transactional HTTPS API (Resend) or SMTP, chosen by env vars.
#   RESEND_API_KEY + MAIL_FROM            -> Resend (https, Railway-friendly)
#   SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS + MAIL_FROM -> any SMTP provider
# MAIL_FROM must be an address on a domain you've verified with the provider
# (e.g. "Lumen <noreply@yourdomain>"). Returns True only if actually accepted.
MAIL_FROM = os.environ.get("MAIL_FROM", "Lumen <onboarding@resend.dev>")

_PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")  # E.164

def normalize_phone(raw, default_cc="1"):
    """Best-effort E.164 from user input. Returns normalized phone or None."""
    if not raw:
        return None
    s = re.sub(r"[^\d+]", "", str(raw))
    if not s:
        return None
    if s.startswith("+"):
        return s if _PHONE_RE.match(s) else None
    digits = re.sub(r"\D", "", s)
    if len(digits) == 10:            # bare US/CA number
        digits = default_cc + digits
    cand = "+" + digits
    return cand if _PHONE_RE.match(cand) else None

def send_sms(to, body):
    """Send one SMS via Twilio's Messages API. Returns True only if accepted (2xx).
    Needs TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN + TWILIO_FROM_NUMBER."""
    import urllib.request, urllib.parse, base64
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    tok = os.environ.get("TWILIO_AUTH_TOKEN")
    frm = os.environ.get("TWILIO_FROM_NUMBER")
    if not (sid and tok and frm and to):
        print("[sms] NOT SENT (missing Twilio env or recipient). To=%s" % to)
        return False
    try:
        data = urllib.parse.urlencode({"To": to, "From": frm, "Body": body[:1500]}).encode()
        auth = base64.b64encode(("%s:%s" % (sid, tok)).encode()).decode()
        req = urllib.request.Request(
            "https://api.twilio.com/2010-04-01/Accounts/%s/Messages.json" % sid,
            data=data, method="POST",
            headers={"Authorization": "Basic " + auth, "Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=12) as r:
            return 200 <= r.status < 300
    except Exception as e:
        print("[sms] twilio failed:", e)
        return False

def send_email(to, subject, text, html=None):
    import urllib.request
    key = os.environ.get("RESEND_API_KEY")
    if key:
        try:
            payload = json.dumps({
                "from": MAIL_FROM, "to": [to], "subject": subject,
                "text": text, "html": html or ("<pre style='font:15px/1.6 -apple-system,system-ui,sans-serif'>" + text + "</pre>"),
            }).encode()
            req = urllib.request.Request("https://api.resend.com/emails", data=payload, method="POST",
                                         headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                                                  "User-Agent": "Lumen-mailer/1.0 (+https://lumen.app)"})
            with urllib.request.urlopen(req, timeout=12) as r:
                return 200 <= r.status < 300
        except Exception as e:
            print("[mail] resend failed:", e)
    host = os.environ.get("SMTP_HOST")
    if host:
        try:
            import smtplib
            from email.message import EmailMessage
            msg = EmailMessage()
            msg["From"] = MAIL_FROM; msg["To"] = to; msg["Subject"] = subject
            msg.set_content(text)
            if html:
                msg.add_alternative(html, subtype="html")
            port = int(os.environ.get("SMTP_PORT", "587"))
            with smtplib.SMTP(host, port, timeout=15) as s:
                s.starttls()
                u, pwd = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASS")
                if u:
                    s.login(u, pwd or "")
                s.send_message(msg)
            return True
        except Exception as e:
            print("[mail] smtp failed:", e)
    # no provider configured — log so the code is recoverable during setup
    print("[mail] NOT SENT (no RESEND_API_KEY/SMTP_HOST). To=%s Subject=%s\n%s" % (to, subject, text))
    return False

# ---------------------------------------------------------------------------
# game engine
# ---------------------------------------------------------------------------

# (name, weekly_light_threshold, color, color2) — color2 is the gradient partner
LEAGUES = [
    ("Ember",     0,    "#ef4444", "#f97316"),
    ("Spark",     50,   "#f97316", "#fbbf24"),
    ("Glow",      150,  "#eab308", "#a3e635"),
    ("Flare",     350,  "#22c55e", "#2dd4bf"),
    ("Beacon",    700,  "#06b6d4", "#38bdf8"),
    ("Nova",      1200, "#6366f1", "#818cf8"),
    ("Supernova", 2000, "#d946ef", "#ec4899"),
]

def league_for(weekly_light):
    cur = LEAGUES[0]
    nxt = None
    for i, lg in enumerate(LEAGUES):
        if weekly_light >= lg[1]:
            cur = lg
            nxt = LEAGUES[i + 1] if i + 1 < len(LEAGUES) else None
    return {
        "name": cur[0], "color": cur[2], "color2": cur[3], "at": cur[1],
        "next": (nxt[0] if nxt else None),
        "next_at": (nxt[1] if nxt else None),
    }

def level_for(light):
    """Return (level, light_into_level, light_needed_for_next)."""
    lvl = 1
    need = 100
    remaining = light
    while remaining >= need:
        remaining -= need
        lvl += 1
        need = int(need * 1.35)
    return lvl, remaining, need

def streak_multiplier(streak):
    return min(1.0 + 0.08 * max(0, streak - 1), 2.5)

def time_bonus(dt):
    h = dt.hour
    if 22 <= h or h < 4:   # night owl
        return 1.2, "night"
    if 4 <= h < 7:         # dawn patrol
        return 1.2, "dawn"
    return 1.0, ""

def compute_light(minutes, streak, dt):
    mult = streak_multiplier(streak)
    tb, _ = time_bonus(dt)
    return max(1, round(minutes * 10 * mult * tb))

# --- Atlas: a photo passport of the places you meditate -------------
# Gamified around COLLECTING SPOTS: travel somewhere new, keep a photo of where
# you sat, and share it with the community. Two hooks:
#   * a PHOTO STREAK  — consecutive days you keep a photo of your spot
#   * a PLACES PASSPORT — the distinct spots you've photographed (travel reward)
PILG_NEW_PLACE = 60        # Light the first time each day you sit at a brand-new place
PILG_PHOTO = 25            # Light for keeping a photo of a place you've sat before
PILG_MILESTONES = [3, 5, 10, 25, 50, 100]   # places-collected milestones

def place_key(lat, lon):
    """A coarse ~1km coord cell used to tell meditation spots apart."""
    if lat is None or lon is None:
        return None
    try:
        return "%.2f,%.2f" % (round(float(lat), 2), round(float(lon), 2))
    except Exception:
        return None

def distinct_places(c, uid):
    """Size of this user's passport: distinct ~1km spots they've photographed.
    Uses the stable `pk` (pre-fuzz) and falls back to fuzzed coords for legacy rows."""
    pks = set()
    for r in c.execute("SELECT pk,lat,lon FROM sessions WHERE user_id=? AND photo IS NOT NULL", (uid,)):
        k = r["pk"] or place_key(r["lat"], r["lon"])
        if k:
            pks.add(k)
    return len(pks)


def seed_demo_account(c):
    """Fill the App Review demo account (appreview@lumen.app) with believable,
    backdated history so the app films full: a real streak, weeks of sessions, a
    traveled map, a tended journal, achievements and a collection. Idempotent."""
    import random
    from datetime import datetime, timedelta, timezone
    rnd = random.Random(7)
    email, name, pw = "appreview@lumen.app", "Ava Rowe", "LumenReview!2026"
    u = user_by_email(c, email)
    if not u:
        salt = secrets.token_hex(16)
        c.execute("INSERT INTO users(email,name,salt,hash,created) VALUES(?,?,?,?,?)",
                  (email, name, salt, _hash_pw(pw, salt), now_iso()))
        c.commit(); u = user_by_email(c, email)
    uid = u["id"]
    for t in ("sessions", "journal", "achievements", "items", "companions"):
        c.execute("DELETE FROM %s WHERE user_id=?" % t, (uid,))

    home = ("Brooklyn", 40.68, -73.94)
    places = [home, home, home, ("Manhattan", 40.78, -73.97), ("Jersey City", 40.73, -74.07),
              ("Boston", 42.36, -71.06), ("Los Angeles", 34.05, -118.24), ("Lisbon", 38.72, -9.14),
              ("Reykjavik", 64.15, -21.94)]
    lessons = ["foundations_breath_1", "foundations_breath_2", "vishnu", "vishnu_avatars"]
    now = datetime.now(timezone.utc)
    # current streak of 18 consecutive days, plus scattered earlier history
    offsets = list(range(0, 18)) + [19, 20, 22, 24, 25, 28, 30, 33, 37, 41, 44]
    offsets = sorted(set(offsets))
    total_min = total_light = 0
    streak_run = 18
    for off in offsets:
        d = now - timedelta(days=off)
        hour = rnd.choice([6, 7, 7, 8, 8, 9, 18, 20, 21])
        if off == 6:
            hour = 23      # moon_child
        if off == 9:
            hour = 5       # dawn_patrol
        ts = d.replace(hour=hour, minute=rnd.randint(0, 55), second=0, microsecond=0)
        minutes = rnd.choice([5, 8, 10, 10, 12, 15, 15, 20, 25])
        pl = places[off % len(places)]
        lg = compute_light(minutes, max(1, 18 - (off % 18)), ts)
        total_min += minutes; total_light += lg
        les = lessons[off % len(lessons)] if off % 5 == 0 else None
        pk = place_key(pl[1], pl[2])
        c.execute("""INSERT INTO sessions(user_id,minutes,soundscape,light,lat,lon,city,mood,note,
                     started,ended,day,week,lesson,pk) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (uid, minutes, rnd.choice(SOUNDSCAPES), lg, pl[1], pl[2], pl[0],
                   rnd.choice(["calm", "clear", "tender", "steady", "grateful", "light", "tired"]),
                   "", ts.isoformat(), (ts + timedelta(minutes=minutes)).isoformat(),
                   ts.date().isoformat(), week_str(ts.date()), les, pk))
        # give a few sessions a photo so the Atlas/passport + globetrotter fill in
        if off % len(places) in (3, 5, 6, 7, 8) or off in (0, 2):
            c.execute("UPDATE sessions SET photo=?, photo_share=? WHERE id=last_insert_rowid()",
                      ("", 0))

    # journal: a tended mix of daily / deep / season, backdated
    jentries = []
    pil_names = list(PILLARS)
    for i, off in enumerate([0, 1, 3, 4, 6, 8, 10, 13, 16, 19, 23, 28, 34, 41]):
        ts = (now - timedelta(days=off)).replace(hour=rnd.choice([7, 21]), minute=rnd.randint(0, 55))
        kind = ["daily", "deep", "daily", "season", "daily", "deep", "daily", "deep",
                "daily", "season", "daily", "deep", "daily", "daily"][i]
        if kind == "deep":
            pil = pil_names[i % len(pil_names)]
            ch = PILLAR_PLANS[pil][1][0]
            prompt, text = ch[1], _demo_text(kind, pil)
            pillar, place = pil, None
        elif kind == "season":
            prompt, text = SEASON_PLAN[0][1], _demo_text(kind, None)
            pillar, place = None, rnd.choice(["rebuilding", "the long spring", "beginning again"])
        else:
            prompt, text = PROMPTS[i % len(PROMPTS)], _demo_text(kind, None)
            pillar, place = None, None
        mood = rnd.choice(["calm", "tender", "hopeful", "clear", "grateful", "heavy", "steady"])
        refl = rnd.choice([
            "There's real honesty here — you named the thing instead of circling it.",
            "I hear some tenderness toward yourself in this. Stay with it.",
            "You're further along than the worry suggests. Keep returning.",
            "", ""])
        shared = 1 if i in (2, 7) else 0
        c.execute("INSERT INTO journal(user_id,prompt,text,mood,reflection,shared,created,kind,pillar,place) "
                  "VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (uid, prompt, text, mood, refl, shared, ts.isoformat(), kind, pillar, place))

    # achievements that match the seeded history
    for code, off in [("first_light", 44), ("week_warrior", 30), ("scribe", 20),
                      ("pilgrim", 41), ("globetrotter", 25), ("moon_child", 6),
                      ("dawn_patrol", 9), ("chronicler", 2)]:
        ts = now - timedelta(days=off)
        c.execute("INSERT OR IGNORE INTO achievements(user_id,code,created) VALUES(?,?,?)",
                  (uid, code, ts.isoformat()))
    # collection pieces
    for code, off in [("zafu", 44), ("incense", 40), ("candle", 33), ("mala", 30),
                      ("bell", 24), ("flags", 25), ("crystal", 16), ("bonsai", 8)]:
        ts = now - timedelta(days=off)
        c.execute("INSERT OR IGNORE INTO items(user_id,code,created) VALUES(?,?,?)",
                  (uid, code, ts.isoformat()))

    best = max(streak_run, 21)
    c.execute("""UPDATE users SET name=?, light=?, streak=?, best_streak=?, last_day=?,
                 total_minutes=?, total_sessions=?, lat=?, lon=?, city=?,
                 motes=COALESCE(motes,0)+420 WHERE id=?""",
              (name, total_light, streak_run, best, now.date().isoformat(),
               total_min, len(offsets), home[1], home[2], home[0], uid))
    c.commit()
    lvl = level_for(total_light)[0]
    return {"sessions": len(offsets), "minutes": total_min, "light": total_light,
            "level": lvl, "streak": streak_run, "journal": 14}


def _demo_text(kind, pillar):
    if kind == "deep" and pillar:
        return ("Sat with my %s pillar tonight. It's easier to see the pattern than to "
                "forgive it, but I'm trying. Naming what I inherited — and what I want to "
                "set down — made it feel less heavy, more like a choice I actually get to make." % pillar.lower())
    if kind == "season":
        return ("Naming this season helped. It's not a detour, it's the road. What it's "
                "asking of me is patience, and what it's giving back is a slower, steadier "
                "kind of clarity I didn't have a year ago.")
    return ("A quiet day. I noticed I kept bracing for something that never came. Writing it "
            "down loosened it. Grateful for ten minutes of actual stillness, and for noticing "
            "the light change in the kitchen before anyone else was up.")

def eval_pilgrimage(c, u, local_day, pk, has_photo):
    """Fold a just-completed session into the photo pilgrimage. Advances the photo
    streak the first time a spot photo is kept today, and rewards brand-new places
    to push travel. `pk` is the stable place key for this session (pre-fuzz).
    Returns (progress, newly_today, bonus, chal_fields).
    (Reuses the `challenges` table: new_place/photo sticky per day; `done` = photo kept today.)"""
    row = c.execute("SELECT * FROM challenges WHERE user_id=? AND day=?", (u["id"], local_day)).fetchone()
    already_photo = (row["photo"] if row else 0)
    new_place = 0
    if pk:
        prior = set()
        for r in c.execute("SELECT pk,lat,lon FROM sessions WHERE user_id=? AND day<?", (u["id"], today_str())):
            k = r["pk"] or place_key(r["lat"], r["lon"])
            if k:
                prior.add(k)
        new_place = 0 if pk in prior else 1
    if row and row["new_place"]:
        new_place = 1   # sticky across the local day
    photo = 1 if (has_photo or already_photo) else 0
    first_photo_today = 1 if (has_photo and not already_photo) else 0
    if first_photo_today:
        bonus = PILG_NEW_PLACE if new_place else PILG_PHOTO
    else:
        bonus = (row["bonus"] if row else 0)
    c.execute("""INSERT INTO challenges(user_id,day,morning,new_place,photo,done,place,bonus,created)
                 VALUES(?,?,?,?,?,?,?,?,?)
                 ON CONFLICT(user_id,day) DO UPDATE SET
                   new_place=excluded.new_place,photo=excluded.photo,
                   done=excluded.done,place=COALESCE(excluded.place,challenges.place),bonus=excluded.bonus""",
              (u["id"], local_day, 0, new_place, photo, photo, pk, bonus, now_iso()))
    chal = {}
    if first_photo_today:
        last = u["chal_last_day"]; streak = u["chal_streak"] or 0
        yday = (datetime.strptime(local_day, "%Y-%m-%d").date() - timedelta(days=1)).isoformat()
        if last == local_day:   pass
        elif last == yday:      streak += 1
        else:                   streak = 1
        chal = {"chal_streak": streak, "chal_best": max(u["chal_best"] or 0, streak),
                "chal_last_day": local_day}
    prog = {"new_place": bool(new_place), "photo": bool(photo), "done": bool(photo)}
    return prog, bool(first_photo_today), bonus, chal

# --- Vedic (Jyotish) daily reading -------------------------------------------
# Grounded in classical Jyotish, not Western sun-sign astrology: the SIDEREAL
# zodiac (Lahiri ayanamsa), the 12 rashis with their planetary lords, and — at
# the heart of it — the Moon's NAKSHATRA of the day (the 27 lunar mansions, each
# with its classical deity, ruling graha and shakti/power). Significations follow
# the canon: Brihat Parashara Hora Shastra, Varahamihira's Brihat Jataka, and the
# nakshatra attributes preserved in the Taittiriya Brahmana.

# rashi: key, glyph, english, sanskrit, graha-lord, element (tattva), nature
ZODIAC = [
 ("aries","♈","Aries","Mesha","Mars","fire","initiating, courageous, pioneering"),
 ("taurus","♉","Taurus","Vrishabha","Venus","earth","steady, sensual, enduring"),
 ("gemini","♊","Gemini","Mithuna","Mercury","air","curious, communicative, dual"),
 ("cancer","♋","Cancer","Karka","Moon","water","nurturing, feeling, protective"),
 ("leo","♌","Leo","Simha","Sun","fire","radiant, noble, self-expressive"),
 ("virgo","♍","Virgo","Kanya","Mercury","earth","discerning, careful, of service"),
 ("libra","♎","Libra","Tula","Venus","air","harmonizing, relational, fair"),
 ("scorpio","♏","Scorpio","Vrishchika","Mars","water","intense, probing, transformative"),
 ("sagittarius","♐","Sagittarius","Dhanu","Jupiter","fire","seeking, philosophical, free"),
 ("capricorn","♑","Capricorn","Makara","Saturn","earth","disciplined, patient, enduring"),
 ("aquarius","♒","Aquarius","Kumbha","Saturn","air","detached, humanitarian, visionary"),
 ("pisces","♓","Pisces","Meena","Jupiter","water","devotional, imaginative, surrendering"),
]
ZODIAC_BY_KEY = {z[0]: z for z in ZODIAC}
# sidereal (Lahiri) sun ingress — (month, cutoff-day, prev-rashi, this-rashi)
_SIGN_RANGES = [
 (1,14,"sagittarius","capricorn"),(2,13,"capricorn","aquarius"),(3,15,"aquarius","pisces"),
 (4,14,"pisces","aries"),(5,15,"aries","taurus"),(6,15,"taurus","gemini"),
 (7,16,"gemini","cancer"),(8,17,"cancer","leo"),(9,17,"leo","virgo"),
 (10,17,"virgo","libra"),(11,16,"libra","scorpio"),(12,16,"scorpio","sagittarius"),
]
def zodiac_sign(month, day):
    cut = _SIGN_RANGES[month-1]
    return cut[2] if day < cut[1] else cut[3]

def sign_from_birthdate(s):
    try:
        p = [int(x) for x in str(s).split("-")[:3]]
        return zodiac_sign(p[1], p[2])
    except Exception:
        return None

# 27 nakshatras: name, ruling graha (Vimshottari lord), deity, symbol, shakti/theme
NAKSHATRAS = [
 ("Ashwini","Ketu","the Ashwini Kumaras (divine healers)","a horse's head","swift healing and fresh beginnings"),
 ("Bharani","Venus","Yama (lord of dharma and death)","the yoni","bearing what must be borne; patient transformation"),
 ("Krittika","Sun","Agni (fire)","a flame or blade","burning away the impure; sharp, honest clarity"),
 ("Rohini","Moon","Brahma / Prajapati","an ox-cart","growth, nourishment and quiet flourishing"),
 ("Mrigashira","Mars","Soma","a deer's head","the gentle search; seeking without grasping"),
 ("Ardra","Rahu","Rudra (the storm)","a teardrop","the storm that clears; release through feeling"),
 ("Punarvasu","Jupiter","Aditi (the boundless)","a quiver of arrows","return and renewal; coming safely home"),
 ("Pushya","Saturn","Brihaspati","a lotus and cow's udder","nourishment and devotion; steady flourishing"),
 ("Ashlesha","Mercury","the Nagas (serpents)","a coiled serpent","penetrating insight; the awakening coil"),
 ("Magha","Ketu","the Pitris (ancestors)","a royal throne","honoring your roots and inherited strength"),
 ("Purva Phalguni","Venus","Bhaga (delight)","the front legs of a bed","rest, pleasure and creative ease"),
 ("Uttara Phalguni","Sun","Aryaman (the patron)","the back legs of a bed","steady union and generous support"),
 ("Hasta","Moon","Savitar (the skillful Sun)","an open hand","the skill of the hands; making things real"),
 ("Chitra","Mars","Tvashtar / Vishvakarma","a bright jewel","radiant craft; beauty taking form"),
 ("Swati","Rahu","Vayu (the wind)","a young sprout in the wind","independence and self-sufficient movement"),
 ("Vishakha","Jupiter","Indra-Agni","a triumphal archway","focused purpose ripening toward a goal"),
 ("Anuradha","Saturn","Mitra (friendship)","a lotus","devotion, friendship and cooperation"),
 ("Jyeshtha","Mercury","Indra (the chief)","an umbrella or earring","courage and protective, seasoned power"),
 ("Mula","Ketu","Nirriti (dissolution)","a tuft of tied roots","getting to the root; return to essence"),
 ("Purva Ashadha","Venus","Apas (the waters)","a winnowing fan","invincibility and purification"),
 ("Uttara Ashadha","Sun","the Vishvedevas","an elephant's tusk","lasting victory and unshakable purpose"),
 ("Shravana","Moon","Vishnu","an ear and three footprints","deep listening and learning"),
 ("Dhanishtha","Mars","the eight Vasus","a drum","rhythm, abundance and inner music"),
 ("Shatabhisha","Rahu","Varuna (cosmic waters)","an empty circle of a hundred healers","healing, solitude and the hidden"),
 ("Purva Bhadrapada","Jupiter","Aja Ekapada","the front of a funeral cot","fiery aspiration; intensity for the heights"),
 ("Uttara Bhadrapada","Saturn","Ahir Budhnya (the deep serpent)","the back of a funeral cot","deep stillness; the calm of the depths"),
 ("Revati","Mercury","Pushan (the nourisher)","a fish","safe passage and nourishing completion"),
]

def _jd(y, m, d, hour=12.0):
    if m <= 2:
        y -= 1; m += 12
    a = y // 100; b = 2 - a + a // 4
    return int(365.25*(y+4716)) + int(30.6001*(m+1)) + d + b - 1524.5 + hour/24.0

def _ayanamsa(jd):
    # Lahiri: ~23.853 deg at J2000, precessing ~50.2388"/yr (≈24.2 deg in 2026)
    return 23.853 + (jd - 2451545.0)/365.25 * (50.2388/3600.0)

def _moon_longitude(jd):
    # Moon's apparent ecliptic longitude via the main periodic terms of the Meeus
    # lunar theory (ch. 47, public domain) — ~arc-minute accuracy, pure Python, no deps.
    T = (jd - 2451545.0) / 36525.0; r = math.radians
    Lp = 218.3164477 + 481267.88123421*T - 0.0015786*T*T + T*T*T/538841.0 - T*T*T*T/65194000.0
    D  = 297.8501921 + 445267.1114034*T - 0.0018819*T*T + T*T*T/545868.0 - T*T*T*T/113065000.0
    M  = 357.5291092 + 35999.0502909*T - 0.0001536*T*T + T*T*T/24490000.0
    Mp = 134.9633964 + 477198.8675055*T + 0.0087414*T*T + T*T*T/69699.0 - T*T*T*T/14712000.0
    F  = 93.2720950 + 483202.0175233*T - 0.0036539*T*T - T*T*T/3526000.0 + T*T*T*T/863310000.0
    E = 1.0 - 0.002516*T - 0.0000074*T*T
    # (coeff in 1e-6 deg, D, M, Mp, F) — leading Sigma-l terms
    terms = [
        (6288774,0,0,1,0),(1274027,2,0,-1,0),(658314,2,0,0,0),(213618,0,0,2,0),
        (-185116,0,1,0,0),(-114332,0,0,0,2),(58793,2,0,-2,0),(57066,2,-1,-1,0),
        (53322,2,0,1,0),(45758,2,-1,0,0),(-40923,0,1,-1,0),(-34720,1,0,0,0),
        (-30383,0,1,1,0),(15327,2,0,0,-2),(-12528,0,0,1,2),(10980,0,0,1,-2),
        (10675,4,0,-1,0),(10034,0,0,3,0),(8548,4,0,-2,0),(-7888,2,1,-1,0),
        (-6766,2,1,0,0),(-5163,1,0,-1,0),(4987,1,1,0,0),(4036,2,-1,1,0),
        (3994,2,0,2,0),(3861,4,0,0,0),(3665,2,0,-3,0),(-2689,0,1,-2,0),
        (-2602,2,0,-1,2),(2390,2,-1,-2,0),(-2348,1,0,1,0),(2236,2,-2,0,0),
        (-2120,0,1,2,0),(-2069,0,2,0,0),(2048,2,-2,-1,0),(-1773,2,0,1,-2),
        (-1595,2,0,0,2),(1215,4,-1,-1,0),(-1110,0,0,2,2),(-892,3,0,-1,0),
    ]
    s = 0.0
    for c, dd, mm, mp, ff in terms:
        arg = r(dd*D + mm*M + mp*Mp + ff*F)
        e = E**abs(mm)
        s += c * e * math.sin(arg)
    return (Lp + s/1000000.0) % 360.0

def moon_nakshatra(day_str):
    """Return (index, nakshatra-tuple, pada 1-4) for the Moon's position on a day."""
    try:
        y, m, d = [int(x) for x in str(day_str).split("-")[:3]]
    except Exception:
        y, m, d = 2000, 1, 1
    jd = _jd(y, m, d, 12.0)
    sid = (_moon_longitude(jd) - _ayanamsa(jd)) % 360.0
    span = 360.0/27.0
    idx = int(sid // span) % 27
    pada = int((sid % span) // (span/4.0)) + 1
    return idx, NAKSHATRAS[idx], pada

# Vimshottari dasha: nakshatra-lord order and their period lengths (total 120 yrs)
VIMSHOTTARI = [("Ketu",7),("Venus",20),("Sun",6),("Moon",10),("Mars",7),
               ("Rahu",18),("Jupiter",16),("Saturn",19),("Mercury",17)]

def _natal_moon_sid(birth_date, birth_time, tz_min):
    """Sidereal ecliptic longitude of the Moon at birth, and the birth JD. tz_min is
    minutes east of UTC. Returns (sid_lon_deg, jd) or None."""
    try:
        y, m, d = [int(x) for x in str(birth_date).split("-")[:3]]
        hh, mm = 12, 0
        if birth_time:
            parts = str(birth_time).split(":"); hh = int(parts[0]); mm = int(parts[1]) if len(parts) > 1 else 0
        hour_ut = hh + mm/60.0 - (tz_min or 0)/60.0
        jd = _jd(y, m, d, hour_ut)
        return (_moon_longitude(jd) - _ayanamsa(jd)) % 360.0, jd
    except Exception:
        return None

def natal_profile(u):
    """Janma (birth) nakshatra + current Vimshottari Maha/Antar dasha from the natal
    Moon. Needs birth_date (+ ideally birth_time/tz). Returns dict or None."""
    nm = _natal_moon_sid(u["birth_date"], u["birth_time"], u["birth_tz"]) if u["birth_date"] else None
    if not nm:
        return None
    sid, birth_jd = nm
    span = 360.0/27.0
    idx = int(sid // span) % 27
    frac = (sid % span) / span            # fraction traversed through the janma nakshatra
    start = idx % 9                       # starting dasha lord = lord of janma nakshatra
    bal_years = (1.0 - frac) * VIMSHOTTARI[start][1]   # balance of the first mahadasha
    today_jd = _jd(*[int(x) for x in today_str().split("-")], hour=12.0)
    elapsed = max(0.0, (today_jd - birth_jd) / 365.2425)
    # walk mahadashas
    i = start; remain = bal_years
    while elapsed > remain:
        elapsed -= remain; i = (i + 1) % 9; remain = float(VIMSHOTTARI[i][1])
    maha_lord, maha_years = VIMSHOTTARI[i]
    # how far we are into the current mahadasha (years): its length minus what's left
    pos_in_maha = maha_years - (remain - elapsed)
    # antardasha: sub-periods start from the maha lord, each = maha_years*sub_years/120
    j = i; acc = 0.0; antar_lord = maha_lord
    for k in range(9):
        jj = (i + k) % 9
        sub = maha_years * VIMSHOTTARI[jj][1] / 120.0
        if pos_in_maha < acc + sub:
            antar_lord = VIMSHOTTARI[jj][0]; break
        acc += sub
    return {"janma_idx": idx, "janma": NAKSHATRAS[idx][0], "janma_deity": NAKSHATRAS[idx][2],
            "janma_shakti": NAKSHATRAS[idx][4], "maha": maha_lord, "antar": antar_lord,
            "precise": bool(u["birth_time"])}

HORO_SOUNDS = ("rain","forest","ocean","space","silence")
HORO_MINS = (5, 10, 20, 30)

# Varied fallback readings — used only when the AI companion is unreachable.
# Rotated by day + sign so consecutive days never read alike, and deliberately
# retired the old fixed "one unhurried breath" tagline that repeated endlessly.
_HORO_OPENERS = (
    "The Moon moves through %(nak)s today, carrying the shakti of %(shakti)s.",
    "Today the Moon rests in %(nak)s, whose power is %(shakti)s.",
    "%(nak)s holds the Moon today — its gift is %(shakti)s, watched over by %(deity)s.",
    "As the Moon crosses %(nak)s, the day leans toward %(shakti)s.",
    "The Moon's light falls on %(nak)s, the nakshatra of %(deity)s, today.",
    "Under %(nak)s the Moon asks for %(shakti)s rather than speed.",
)
_HORO_BODIES = (
    "As %(arch)s, ruled by %(ruler)s, you feel this most where your attention already wants to go.",
    "For %(arch)s under %(ruler)s, it is an invitation to meet the day a little more awake.",
    "%(ruler)s, your ruler, asks less effort of you today and more presence.",
    "Being %(arch)s, let %(ruler)s steady you rather than hurry you.",
    "With %(ruler)s guiding %(arch)s, the work today is noticing, not forcing.",
)
_HORO_CLOSERS = (
    "Sit when you can; let the breath arrive on its own.",
    "One honest pause today is enough.",
    "Notice what softens when you stop pushing against it.",
    "Let awareness rest where it falls, and leave the rest.",
    "Return to the breath once, without making it a task.",
    "Carry a little of this quiet into whatever comes next.",
    "Meet the next hard moment with attention, not force.",
    "Begin where you are; nothing here needs to be earned.",
)

def _horo_pick(seq, day, sign, salt):
    h = 2166136261
    for ch in (day + "|" + sign):
        h = ((h ^ ord(ch)) * 16777619) & 0xffffffff
    return seq[(h + salt * 2654435761) % len(seq)]

def _horo_fallback(sign, day):
    z = ZODIAC_BY_KEY.get(sign)
    _, nak, _ = moon_nakshatra(day)
    d = {"nak": nak[0], "shakti": nak[4], "deity": nak[2],
         "arch": (z[3] if z else "a seeker"), "ruler": (z[4] if z else "the heavens")}
    text = " ".join((
        _horo_pick(_HORO_OPENERS, day, sign, 1) % d,
        _horo_pick(_HORO_BODIES, day, sign, 2) % d,
        _horo_pick(_HORO_CLOSERS, day, sign, 3) % d,
    ))
    mins = HORO_MINS[(len(nak[0]) + len(sign)) % len(HORO_MINS)]
    return {"text": text, "theme": nak[0], "soundscape": HORO_SOUNDS[len(nak[0]) % len(HORO_SOUNDS)],
            "minutes": mins, "nakshatra": nak[0], "deity": nak[2], "nak_theme": nak[4], "pada": 1}

def personal_horoscope(c, u, day):
    """Vedic daily reading grounded in the user's rashi (sidereal) and the Moon's
    nakshatra of the day, woven with their recent practice. Cached per user per local day."""
    # prefer a sidereal rashi computed from the birthday; else a chosen sign
    sign = sign_from_birthdate(u["birth_date"]) if u["birth_date"] else (u["sun_sign"] or "").lower()
    if sign not in ZODIAC_BY_KEY:
        return None
    if u["sun_sign"] != sign:   # self-heal: migrate tropical/stale signs to the sidereal rashi
        try:
            c.execute("UPDATE users SET sun_sign=? WHERE id=?", (sign, u["id"])); c.commit()
        except Exception:
            pass
    if u["horo_day"] == day and u["horo"]:
        try:
            cached = json.loads(u["horo"])
            # self-heal: regenerate any reading still carrying the retired tagline
            if "one unhurried breath" not in (cached.get("text") or ""):
                return cached
        except Exception:
            pass
    z = ZODIAC_BY_KEY[sign]
    _, nak, pada = moon_nakshatra(day)
    natal = natal_profile(u)
    recent = c.execute("SELECT mood,soundscape FROM sessions WHERE user_id=? ORDER BY ended DESC LIMIT 1",
                       (u["id"],)).fetchone()
    ctx = []
    if (u["streak"] or 0): ctx.append("current streak %d day(s)" % (u["streak"] or 0))
    if recent and recent["mood"]: ctx.append("last felt '%s'" % recent["mood"])
    if recent and recent["soundscape"]: ctx.append("last soundscape '%s'" % recent["soundscape"])
    try:
        lo = json.loads(u["lifeos"]) if u["lifeos"] else None
        if isinstance(lo, dict) and lo.get("focus"):
            f = lo["focus"]; ctx.append("life focus: %s" % (", ".join(f) if isinstance(f, list) else str(f)))
    except Exception:
        pass
    ctx_s = "; ".join(ctx) if ctx else "a new practitioner"
    natal_s = ""
    if natal:
        natal_s = (" Their natal (janma) nakshatra is %s, deity %s, shakti '%s'; they are currently in "
                   "the Vimshottari Mahadasha of %s with Antardasha of %s — let this birth-star and dasha "
                   "lord quietly colour the reading.") % (
                   natal["janma"], natal["janma_deity"], natal["janma_shakti"], natal["maha"], natal["antar"])
    prompt = (
        "You are a gentle, learned voice of Vedic astrology (Jyotish) inside Lumen, a meditation app. "
        "Write today's short reading for someone whose rashi (Moon/sidereal sign) is %s (%s), ruled by "
        "the graha %s, of a %s, %s nature. Ground it in REAL Jyotish for today: the Moon transits the "
        "nakshatra %s (pada %d), whose presiding deity is %s, whose symbol is %s, and whose shakti "
        "(power) is %s.%s Weave these together with the person's recent practice (%s) into a calm, "
        "meditative reflection that is true to Vedic understanding — not a generic fortune. Name the "
        "transiting nakshatra. 2 to 3 sentences, present tense, warm, no emojis; no predictions about "
        "money, health, or romance, and no deterministic or fatalistic claims — frame everything as an "
        "invitation to awareness, breath and dharma. Then recommend today's sit: one soundscape from "
        "exactly rain, forest, ocean, space, silence, and one duration from exactly 5, 10, 20, 30 "
        'minutes. Return JSON {"text":"...","theme":"the nakshatra name",'
        '"soundscape":"one of the five","minutes":10}.'
    ) % (z[3], z[2], z[4], z[5], z[6], nak[0], pada, nak[2], nak[3], nak[4], natal_s, ctx_s)
    r = ai_json(prompt)
    if not isinstance(r, dict) or not r.get("text"):
        r = _horo_fallback(sign, day)
    snd = (r.get("soundscape") or "silence").lower()
    if snd not in HORO_SOUNDS: snd = "silence"
    try:
        mins = int(r.get("minutes") or 10)
    except Exception:
        mins = 10
    if mins not in HORO_MINS: mins = min(HORO_MINS, key=lambda m: abs(m - mins))
    out = {"text": str(r.get("text"))[:700], "theme": str(r.get("theme") or nak[0])[:40],
           "soundscape": snd, "minutes": mins,
           "nakshatra": nak[0], "deity": nak[2], "nak_theme": nak[4], "pada": pada}
    if natal:
        out["janma"] = natal["janma"]; out["maha"] = natal["maha"]; out["antar"] = natal["antar"]
    try:
        c.execute("UPDATE users SET horo=?, horo_day=? WHERE id=?", (json.dumps(out), day, u["id"]))
        c.commit()
    except Exception:
        pass
    return out

ACHIEVEMENTS = [
    ("first_light",  "First Light",   "Complete your first session",            "🔆"),
    ("marathoner",   "Marathoner",    "Finish a single session of 30+ min",     "🏃"),
    ("week_warrior", "Week Warrior",  "Reach a 7-day streak",                    "🔥"),
    ("constellation","Constellation", "Reach a 30-day streak",                   "✨"),
    ("moon_child",   "Moon Child",    "Meditate between 10pm and 4am",           "🌙"),
    ("dawn_patrol",  "Dawn Patrol",   "Meditate between 4am and 7am",            "🌅"),
    ("globetrotter", "Globetrotter",  "Meditate from 3+ different places",       "🌍"),
    ("centurion",    "Centurion",     "Accumulate 100 total minutes",            "💯"),
    ("deep_diver",   "Deep Diver",    "Earn 500 lifetime Light",                 "🌊"),
    ("luminary",     "Luminary",      "Earn 2000 lifetime Light",                "💫"),
    ("scribe",       "Scribe",        "Write 5 journal letters",                 "📜"),
    ("chronicler",   "Chronicler",    "Write 30 journal letters",                "📖"),
    ("pilgrim",      "Pilgrim",       "Complete a guided lesson",                "🪷"),
]
ACH_BY_CODE = {a[0]: a for a in ACHIEVEMENTS}

def award_journal_ach(c, u):
    """Unlock journaling achievements based on how many entries the user has written."""
    jc = c.execute("SELECT COUNT(*) n FROM journal WHERE user_id=?", (u["id"],)).fetchone()["n"]
    have = {r["code"] for r in c.execute("SELECT code FROM achievements WHERE user_id=?", (u["id"],))}
    new = []
    for code, th in (("scribe", 5), ("chronicler", 30)):
        if jc >= th and code not in have:
            c.execute("INSERT OR IGNORE INTO achievements(user_id,code,created) VALUES(?,?,?)",
                      (u["id"], code, now_iso()))
            new.append(code)
    return new

def check_achievements(c, u, minutes, dt):
    """Unlock any newly-earned achievements for user row u. Returns list of codes."""
    have = {r["code"] for r in c.execute("SELECT code FROM achievements WHERE user_id=?", (u["id"],))}
    new = []
    def unlock(code):
        if code not in have:
            c.execute("INSERT OR IGNORE INTO achievements(user_id,code,created) VALUES(?,?,?)",
                      (u["id"], code, now_iso()))
            new.append(code)
    unlock("first_light")
    if minutes >= 30:
        unlock("marathoner")
    if u["streak"] >= 7:
        unlock("week_warrior")
    if u["streak"] >= 30:
        unlock("constellation")
    if 22 <= dt.hour or dt.hour < 4:
        unlock("moon_child")
    if 4 <= dt.hour < 7:
        unlock("dawn_patrol")
    places = c.execute("SELECT COUNT(DISTINCT city) n FROM sessions WHERE user_id=? AND city IS NOT NULL", (u["id"],)).fetchone()["n"]
    if places >= 3:
        unlock("globetrotter")
    if u["total_minutes"] >= 100:
        unlock("centurion")
    if u["light"] >= 500:
        unlock("deep_diver")
    if u["light"] >= 2000:
        unlock("luminary")
    jc = c.execute("SELECT COUNT(*) n FROM journal WHERE user_id=?", (u["id"],)).fetchone()["n"]
    if jc >= 5:
        unlock("scribe")
    if jc >= 30:
        unlock("chronicler")
    return new

# ---------------------------------------------------------------------------
# collectible meditation items (real-world objects you unlock by practicing)
# ---------------------------------------------------------------------------

# code, name, rarity(0-3), icon, flavor, (cond_type, cond_value), unlock_text
ITEMS = [
    ("zafu",    "Lotus Cushion", 0, "cushion", "Where every sit begins.",        ("level", 1),     "Yours from your first breath"),
    ("incense", "Incense",       0, "incense", "A thread of smoke to follow.",    ("sessions", 5),  "Complete 5 sessions"),
    ("candle",  "Candle",        0, "candle",  "A small, steady flame.",          ("minutes", 30),  "Meditate 30 total minutes"),
    ("mala",    "Mala Beads",    1, "mala",    "108 beads, one breath each.",     ("streak", 7),    "Reach a 7-day streak"),
    ("bowl",    "Singing Bowl",  1, "bowl",    "A tone that lingers.",            ("level", 5),     "Reach level 5"),
    ("bell",    "Temple Bell",   1, "bell",    "Begin and end in sound.",         ("league", "Glow"),"Reach the Glow league"),
    ("crystal", "Amethyst",      2, "crystal", "Still, clear, and ancient.",      ("light", 500),   "Earn 500 lifetime Light"),
    ("flags",   "Prayer Flags",  2, "flags",   "Wishes carried on the wind.",     ("places", 3),    "Meditate from 3 places"),
    ("enso",    "Ensō",          3, "enso",    "One unbroken circle.",            ("streak", 30),   "Reach a 30-day streak"),
    ("bonsai",  "Bonsai",        3, "bonsai",  "Patience, shaped over years.",    ("light", 2000),  "Earn 2000 lifetime Light"),
    # shop-only specialty items (obtained in the Shop, shown here once owned)
    ("chimes",  "Tingsha Chimes",   1, "chimes",  "Two notes to open the silence.",  ("shop", 0), "Available in the Shop"),
    ("sand",    "Zen Sand Garden",  2, "sand",    "Rake the ripples; find the still.",("shop", 0), "Available in the Shop"),
    ("lantern", "Founder's Lantern",3, "lantern", "A light for the earliest to arrive.",("shop", 0), "Founder — in the Shop"),
]
ITEM_BY_CODE = {it[0]: it for it in ITEMS}
LEAGUE_ORDER = [l[0] for l in LEAGUES]

def item_eligible(c, u, cond):
    t, v = cond
    light = u["light"] or 0
    if t == "level":    return level_for(light)[0] >= v
    if t == "sessions": return (u["total_sessions"] or 0) >= v
    if t == "minutes":  return (u["total_minutes"] or 0) >= v
    if t == "streak":   return max(u["streak"] or 0, u["best_streak"] or 0) >= v
    if t == "light":    return light >= v
    if t == "places":
        return c.execute("SELECT COUNT(DISTINCT city) n FROM sessions WHERE user_id=? AND city IS NOT NULL",
                         (u["id"],)).fetchone()["n"] >= v
    if t == "league":
        wl = c.execute("SELECT COALESCE(SUM(light),0) s FROM sessions WHERE user_id=? AND week=?",
                       (u["id"], week_str())).fetchone()["s"]
        return LEAGUE_ORDER.index(league_for(wl)["name"]) >= LEAGUE_ORDER.index(v)
    return False

def collection_for(c, u):
    owned = {r["code"] for r in c.execute("SELECT code FROM items WHERE user_id=?", (u["id"],))}
    out = []
    for code, name, rar, icon, flavor, cond, utext in ITEMS:
        out.append({"code": code, "name": name, "rarity": rar, "flavor": flavor,
                    "unlock": utext, "owned": code in owned,
                    "eligible": (code in owned) or item_eligible(c, u, cond)})
    return out

# ---- living companions you raise with Motes -------------------------------

# code, name, icon, element, adopt_cost(motes), flavor
COMPANIONS = [
    ("moth",  "Lumen Moth",  "c_moth",  "Light",  0,    "Drawn to every flame you light."),
    ("fox",   "Ember Fox",   "c_fox",   "Fire",   400,  "Warm, curious, never still for long."),
    ("koi",   "Tide Koi",    "c_koi",   "Water",  400,  "Swims the current of your breath."),
    ("owl",   "Dawn Owl",    "c_owl",   "Air",    900,  "Keeps watch through the quiet hours."),
    ("deer",  "Grove Deer",  "c_deer",  "Earth",  900,  "Steps softly through the inner forest."),
    ("whale", "Star Whale",  "c_whale", "Cosmos", 1800, "Carries your stillness across the deep."),
]
COMP_BY_CODE = {x[0]: x for x in COMPANIONS}
# cumulative Motes fed -> stage
COMP_STAGES = [(0, "Spark"), (300, "Glimmer"), (900, "Radiant"), (2000, "Celestial")]

def comp_stage(fed):
    idx = 0
    for i, (at, _) in enumerate(COMP_STAGES):
        if fed >= at:
            idx = i
    name = COMP_STAGES[idx][1]
    nxt = COMP_STAGES[idx + 1] if idx + 1 < len(COMP_STAGES) else None
    return {"index": idx, "name": name, "at": COMP_STAGES[idx][0],
            "next": (nxt[1] if nxt else None), "next_at": (nxt[0] if nxt else None),
            "max": nxt is None}

def companions_for(c, u):
    owned = {r["code"]: r["fed"] for r in c.execute("SELECT code,fed FROM companions WHERE user_id=?", (u["id"],))}
    out = []
    for code, name, icon, element, cost, flavor in COMPANIONS:
        o = code in owned
        out.append({"code": code, "name": name, "element": element, "cost": cost,
                    "flavor": flavor, "owned": o, "fed": owned.get(code, 0),
                    "stage": comp_stage(owned.get(code, 0)) if o else None})
    return out

# ---- shop: specialty gear in Motes, some gated by membership tenure --------

# code, name, icon, rarity, price(motes), (gate_type, gate_val) | None, flavor
SHOP = [
    ("chimes",  "Tingsha Chimes",    "chimes",  1, 600,  None,         "Two notes to open and close the silence."),
    ("sand",    "Zen Sand Garden",   "sand",    2, 1000, None,         "Rake the ripples; find the still point."),
    ("lantern", "Founder's Lantern", "lantern", 3, 0,    ("days", 14), "A light kept for the earliest to arrive."),
]
SHOP_BY_CODE = {x[0]: x for x in SHOP}
SHOP_ICON = {x[0]: x[2] for x in SHOP}

# ---- Artifacts: real physical pieces + their digital travel companion -------
# code, name, icon, origin, material, flavor, price_usd, edition, rarity(0-3), source
ARTIFACTS = [
    ("drachma",  "Owl Drachma",       "coin",    "Athens · c. 440 BCE", "Hand-struck silver",
     "An original tetradrachm, worn smooth by twenty-four centuries of hands.", 240, "Ancient original", 3,
     "Vetted antiquities dealer · provenance papers & certificate included"),
    ("skyiron",  "Sky-Iron Amulet",   "pendant", "Himalaya · thokcha",  "Meteoric iron",
     "Forged from metal that fell from the stars, carried by mountain monks.", 380, "Edition of 50", 3,
     "Hand-forged by a verified Himalayan smith — paid fairly for their craft"),
    ("rudraksha","Rudraksha Mala",    "mala",    "Nepal",               "108 sacred seeds",
     "One bead for each breath of the old counting — strung by hand.", 120, "Edition of 300", 1,
     "Strung by a verified artisan co-op in Nepal — paid fairly"),
    ("jade",     "Nephrite Worry Stone","stone", "River jade",          "Tumbled nephrite",
     "A cool, smooth hollow shaped over years to fit a single thumb.", 65, "Edition of 500", 0,
     "Shaped by a verified lapidary artist — paid fairly"),
    ("amberbead","Baltic Amber",      "amber",   "Baltic coast",        "Fossil tree resin",
     "Sunlight caught in ancient resin — roughly forty million years old.", 95, "Edition of 200", 2,
     "Certified-genuine from a trusted Baltic amber house"),
    ("tingbowl", "Hand-Hammered Bowl","bowl",    "Himalaya",            "Seven-metal alloy",
     "A single tone that outlives the hand that strikes it.", 290, "Edition of 100", 2,
     "Hand-hammered by a verified maker — paid fairly for their work"),
]
ART_BY_CODE = {x[0]: x for x in ARTIFACTS}

def artifacts_for(c, u):
    owned = {r["code"] for r in c.execute("SELECT code FROM items WHERE user_id=?", (u["id"],))}
    out = []
    for code, name, icon, origin, material, flavor, price, edition, rar, source in ARTIFACTS:
        imgfile = os.path.join(HERE, "art", code + ".png")
        out.append({"code": code, "name": name, "origin": origin, "material": material,
                    "flavor": flavor, "price": price, "edition": edition, "rarity": rar,
                    "source": source, "owned": code in owned,
                    "img": ("art/" + code + ".png?v=3") if os.path.isfile(imgfile) else None})
    return out

def member_days(u):
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(u["created"])).days
    except Exception:
        return 0

def shop_for(c, u):
    owned = {r["code"] for r in c.execute("SELECT code FROM items WHERE user_id=?", (u["id"],))}
    days = member_days(u)
    out = []
    for code, name, icon, rar, price, gate, flavor in SHOP:
        locked = False; gate_text = None
        if gate and gate[0] == "days":
            locked = days < gate[1]
            gate_text = (f"{gate[1]-days} days of membership to go" if locked else f"Founder · member {gate[1]}+ days")
        out.append({"code": code, "name": name, "rarity": rar, "price": price, "flavor": flavor,
                    "owned": code in owned, "locked": locked, "gate": gate_text})
    return out

# ---------------------------------------------------------------------------
# daily reflection prompt (deterministic by day so everyone shares one)
# ---------------------------------------------------------------------------

PROMPTS = [
    "What are you carrying today that isn't yours to hold?",
    "Where did you feel most alive this week — and what were you doing?",
    "What would you do today if you weren't afraid?",
    "What is one thing you can set down right now, even for an hour?",
    "Who deserves your gratitude today — and have you told them?",
    "What does your body need that your mind keeps overruling?",
    "What story are you telling yourself that may not be true?",
    "When did you last feel truly at peace? Take yourself back there.",
    "What small, ordinary thing brought you joy recently?",
    "What are you avoiding — and what's the fear underneath it?",
    "What would 'enough' look like for you today?",
    "What are you quietly ready to begin?",
    "Where are you rushing when you could be present?",
    "If you could sit with yourself as a child for five minutes, what would you want them to know?",
    "What did today ask of you — and how did you answer?",
    "What are you proud of this week that no one else saw?",
    "Who are you becoming, and did today move you toward them or away?",
    "What's one thing you'd forgive yourself for, if you let yourself?",
    "What felt heavy today, and where did you feel it in your body?",
    "What are you holding on to that was never really yours to fix?",
    "When did you feel most like yourself lately?",
    "What would change if you believed you were already enough?",
    "What's a kindness someone showed you that you've never fully acknowledged?",
    "What are you pretending not to know?",
    "What would make tomorrow feel 2% lighter?",
    "Where did you say yes today when you meant no?",
    "What's something you're grieving, even quietly, even small?",
    "What part of today do you want to remember a year from now?",
    "What are you learning the hard way right now?",
    "If this feeling could speak, what would it be trying to tell you?",
    "What do you need to hear tonight that no one has said to you?",
    "What's one small promise you can keep to yourself this week?",
]

def prompt_for_today():
    doy = datetime.now(timezone.utc).timetuple().tm_yday
    return PROMPTS[doy % len(PROMPTS)]

# ---- Life OS: pillars, focuses, and AI-generated daily prompts -------------

# The eight life pillars of Lumen's deep journaling. The first six grew out of
# Ora Health's taxonomy; Finances and Purpose round it into a full wheel of life.
PILLARS = ["Family", "Relationships", "Career", "Finances",
           "Health", "Hobbies", "Inner Growth", "Purpose"]

# Deep journaling — each pillar is a LESSON PLAN: an ordered series of guided
# sittings ("chapters"), adapted from Ora Health's structured journey/aspect model.
# The Keeper walks one chapter per visit and advances as the person returns, so a
# pillar becomes a path you move through, not a single prompt. Each chapter is a
# short sitting of three steps.
#   PILLAR_PLANS[pillar] = (arc_blurb, [ (title, invitation, [step prompts]), ... ])
PILLAR_PLANS = {
    "Family": ("Turn toward where you came from — one honest sitting at a time.", [
        ("Understanding your parents",
         "See one parent as a whole person, not just the role they played for you.",
         ["Picture one parent (or the person who raised you) as a whole human — their younger self, their fears, the life they lived before you. What do you understand now that you once couldn't?",
          "What did they give you that you're genuinely grateful for? And what couldn't they give — through their own limits, not your fault?",
          "Write one sentence you most want them to know — whether or not you ever say it aloud."]),
        ("The child you were",
         "Sit gently with your younger self, and offer what they needed.",
         ["Bring to mind yourself as a child — a real age, a real room. What did that child need most that they didn't get enough of?",
          "If you could sit beside them now, what would you tell them? Say it in your own words, as if they could hear you.",
          "What's one way you could give grown-up you a little of that same thing this week?"]),
        ("How your upbringing shaped you",
         "Look at the environment that formed you, with clear eyes.",
         ["What was the emotional weather of your childhood home — tense, warm, unpredictable, silent? How did you learn to move through it?",
          "What role did you play back then (the good one, the peacemaker, the invisible one, the strong one)? Where does that role still run you today?",
          "Name one belief about yourself you absorbed early. Is it still true — and do you still want to keep it?"]),
        ("What you inherited",
         "Separate the gifts from the weight you're still carrying.",
         ["What did you inherit from your family that you're proud to carry forward — a value, a strength, a way of loving?",
          "What did you inherit that was never yours to carry? What would it feel like to set it down?",
          "Write the one pattern you most want to keep — and the one you most want to end with you."]),
        ("Cycles to break",
         "Face what goes unspoken, and choose what you'll plant instead.",
         ["What goes unsaid in your family — the thing everyone feels but no one names? What has keeping it quiet cost?",
          "What cycle do you not want to pass on? Be specific about how it shows up.",
          "What new pattern do you want to plant in its place? Name the first small, real act of planting it."]),
    ]),
    "Relationships": ("Honest work on the people you choose to keep close.", [
        ("The one on your heart",
         "Sit with a single relationship that's been asking for your attention.",
         ["Bring one relationship to mind. Under the surface of how it looks — what's actually going on there right now?",
          "What do you need from them that you haven't asked for? What's stopped you?",
          "What do they need from you that you've been slow to give?"]),
        ("What you hold back",
         "Find the truth you've been keeping just out of reach.",
         ["Where have you been holding something back — a truth, a need, an apology? Name it plainly here, where it's safe.",
          "What's the risk you're actually avoiding by staying quiet? And what's the cost of the silence?",
          "Write what you'd say if there were no risk at all. Then name one small, real step toward it."]),
        ("How you love",
         "Look at your own patterns, not just theirs.",
         ["How do you tend to show love — and how do you most want to receive it? Do the people close to you know that?",
          "When you get hurt or scared in a relationship, what do you do — pull away, cling, go cold, overgive? Where did you learn that?",
          "What's one way you'd like to show up differently in your closest relationship this week?"]),
        ("Repair",
         "Tend to something that's frayed, without needing to be right.",
         ["Think of a rupture that hasn't healed. Set aside who was right — what was each of you actually protecting?",
          "What would a true repair look like — not winning, but reconnection? What's your part to own?",
          "Write the first sentence of that repair. The one you could actually say."]),
        ("Being truly known",
         "Reach toward the intimacy of being fully seen.",
         ["Who, if anyone, truly knows you — the unedited version? What makes that safe?",
          "What part of yourself do you keep hidden even from the people closest to you? What are you afraid would happen if they saw it?",
          "What's one small thing you could let someone see this week, as an experiment in being known?"]),
    ]),
    "Career": ("Step back from the to-do list and look at the work itself.", [
        ("The work that's yours",
         "Find the thread of work that's actually yours to do.",
         ["Name the work you'd still do even if no one paid or noticed. Where did this season meet that work — or miss it?",
          "When do you feel most like yourself at work? What's present in those moments?",
          "What's one part of your work you could do more of, and one you could do less of?"]),
        ("What 'enough' means",
         "Loosen the grip of 'more' and name your actual target.",
         ["What would 'enough' look like in your work — in money, status, recognition? Get specific.",
          "Where are you chasing past enough, and what are you really chasing — safety, worth, someone's approval?",
          "If you trusted you were already enough, what would you stop doing tomorrow?"]),
        ("Ambition and fear",
         "Tell apart the drive that's yours from the fear that drives you.",
         ["What do you most want to build or become in your work? Say it without hedging.",
          "What are you afraid of — failing, being seen, being ordinary, being found out? Name the fear precisely.",
          "Where is fear steering decisions you'd make differently from a place of trust?"]),
        ("Quiet pride",
         "Give yourself credit you don't usually say out loud.",
         ["What are you quietly proud of this season that no one else fully saw?",
          "What hard thing did you handle better than you would have a few years ago?",
          "Write the sentence of recognition you wish someone would say to you — then say it to yourself."]),
        ("The next true step",
         "Turn all of it toward one honest move.",
         ["Given everything you've sat with here, what's the work you most want the next chapter to hold?",
          "What's the smallest real step toward it — one you could take this week?",
          "What will you need to protect that step from (busyness, doubt, other people's expectations)?"]),
    ]),
    "Finances": ("Look plainly at the thing most of us look away from — without shame.", [
        ("What money means to you",
         "Name the feeling money carries for you, underneath the numbers.",
         ["What does money mean to you right now — safety, freedom, pressure, proof of worth? Sit with the honest answer.",
          "When do you feel most anxious about money, and when most at ease? What's different in those moments?",
          "If money were simply a tool and not a verdict on you, what would change in how you feel?"]),
        ("The story you inherited",
         "Trace your money beliefs back to where they began.",
         ["What did you learn about money growing up — from what was said, and from what you watched?",
          "Which of those beliefs still runs you today? Is it serving you, or just familiar?",
          "What's one money belief you'd like to consciously rewrite?"]),
        ("The worry you half-look-at",
         "Turn toward the money fear you keep in your peripheral vision.",
         ["Write honestly about one money worry you keep only half-looking-at. Say the whole thing.",
          "What's the real fear underneath it — not the number, but what the number threatens?",
          "What would it feel like to face it fully, maybe with help? What's the first step?"]),
        ("Enough",
         "Find the line where enough actually lives.",
         ["What would 'enough' actually feel like in your body — not a number, a feeling of ease?",
          "Where do you already have more than enough, and forget to notice?",
          "What's one quiet step toward more ease — a conversation, a plan, a boundary, a look at the real numbers?"]),
        ("Money and your values",
         "Line your spending up with what you actually care about.",
         ["Look at where your money actually goes. What does it say you value?",
          "Where is there a gap between what you spend on and what you say matters most?",
          "What's one way you could use money this month in service of something you truly care about?"]),
    ]),
    "Health": ("Give your body the floor — it's been trying to tell you something.", [
        ("Listening to the body",
         "Check in with your body the way you would a friend.",
         ["Scan through your body slowly. What has it been asking for that your mind keeps overruling?",
          "Where do you hold stress physically — and what tends to put it there?",
          "If your body could say one sentence to you right now, what would it be?"]),
        ("Rest",
         "Look honestly at how you recover — or don't.",
         ["When did you last feel genuinely rested? What made that possible?",
          "What gets in the way of real rest for you — habits, guilt, other people, your own mind?",
          "What's one kind, doable change that would give you more true rest this week?"]),
        ("The one habit",
         "Find the small change that would ripple outward.",
         ["What's one health habit that, if it were steady, would quietly improve everything else?",
          "What's made it hard to keep before — and what's one way to make it 2% easier this time?",
          "Picture yourself a season from now, having kept it. What's different?"]),
        ("Your body and you",
         "Tend the relationship, not just the metrics.",
         ["How do you talk to yourself about your body? Would you talk to someone you love that way?",
          "What has your body carried you through that you've never thanked it for?",
          "What would it mean to treat your body as an ally this season, not a project?"]),
        ("What well feels like",
         "Define wellness in your own terms, then step toward it.",
         ["Forget the metrics — what does 'well' actually feel like for you, on a good day?",
          "What's quietly been draining your energy, and what reliably restores it?",
          "Name one small, doable thing your body would thank you for this week."]),
    ]),
    "Hobbies": ("Remember the things you do for no reason but joy.", [
        ("For the love of it",
         "Reconnect with what you do purely because you love it.",
         ["Describe the last time something you love made you lose track of time. What did that give you?",
          "What draws you to it — the challenge, the beauty, the quiet, the people, the flow itself?",
          "When did you last make real space for it? What crowded it out?"]),
        ("What you let slip",
         "Go looking for a joy you quietly abandoned.",
         ["What did you love as a kid or younger adult that you've let slip away? What happened to it?",
          "What did that thing give you that you might still be missing?",
          "Is there a small, low-stakes way to taste it again — not to master it, just to touch it?"]),
        ("Flow",
         "Study the state where you lose and find yourself at once.",
         ["When are you most absorbed — so in it that self-consciousness falls away? What are you doing?",
          "What conditions make that flow possible for you (time, place, no phone, a certain mood)?",
          "How could you engineer one pocket of flow into this week on purpose?"]),
        ("Play",
         "Make room for the part of you that isn't trying to achieve.",
         ["Where in your life do you get to be playful, silly, unproductive — and is it enough?",
          "What's something you'd love to try with zero pressure to be good at it?",
          "Give yourself permission here: what's one playful thing you'll let yourself do soon?"]),
        ("Making space",
         "Turn love into a small, protected place on your calendar.",
         ["If this pursuit mattered as much as you say, what would your week look like?",
          "What small, repeating pocket of time could you protect for it?",
          "What's the first tiny step — the gear out, the lesson booked, the hour blocked?"]),
    ]),
    "Inner Growth": ("Look at the arc of your own becoming.", [
        ("Who you were",
         "Honor the distance you've already travelled.",
         ["Write about who you were a year or five ago. What would that version of you thank you for?",
          "What have you survived or outgrown that you don't give yourself enough credit for?",
          "What's one way you've genuinely changed that you're proud of?"]),
        ("The pattern you're outgrowing",
         "Meet an old habit with curiosity instead of judgment.",
         ["What pattern are you ready to outgrow — a reaction, a fear, a way of hiding?",
          "What has that pattern been protecting you from? (It started as a kind of help.)",
          "What could you trust instead of that pattern, in the moment it usually takes over?"]),
        ("Your inner critic",
         "Turn toward the harsh voice and learn its shape.",
         ["Whose voice is your inner critic, really? What does it say when you're down?",
          "What is it actually trying to do — protect you, push you, keep you safe from shame?",
          "What would a wiser, kinder voice say instead? Write a few lines in that voice."]),
        ("Self-compassion",
         "Practice meeting yourself the way you'd meet a friend.",
         ["Think of something you're being hard on yourself about. What would you say to a friend in exactly your position?",
          "What do you need to hear right now that no one has said to you?",
          "Offer yourself one sentence of real compassion — and let yourself mean it."]),
        ("Who you're becoming",
         "Name the person on the horizon and take a step toward them.",
         ["Who are you becoming? Describe that person — how they move through a day, how they treat themselves.",
          "What's one value you want that future self to be known for?",
          "What's one way you can meet that person halfway today?"]),
    ]),
    "Purpose": ("Reach past the daily and ask what it's all for.", [
        ("The bigger why",
         "Look for the thread of meaning running under your days.",
         ["When did you last feel part of something larger than yourself? What was it?",
          "What makes you lose the sense that you're just filling time?",
          "If your life were quietly about one thing, what might it be?"]),
        ("What you'd stand for",
         "Find the commitments that are worth a cost.",
         ["What matters to you enough that you'd stand by it even when it costs you?",
          "Where is that showing up in how you actually live — and where is it missing?",
          "What would it look like to live one degree more in line with it?"]),
        ("Meaning in the ordinary",
         "Notice the purpose hiding in small, unglamorous acts.",
         ["Where does meaning show up in your ordinary days — a person you help, a thing you make, a small faithfulness?",
          "What small act of yours matters more than you usually let it?",
          "How could you do a little more of that, on purpose?"]),
        ("Contribution",
         "Ask what you want to give, and to whom.",
         ["What do you most want to give to the people and world around you?",
          "Whose life is better because you're in it — and do they know?",
          "What's one way you could contribute this month that would feel genuinely like you?"]),
        ("The purpose of this season",
         "Give this particular chapter of your life a reason.",
         ["If this specific season of your life had a purpose, what would you want it to be?",
          "What is this time asking you to learn, build, heal, or become?",
          "Name one thing you want to be true by the time this season ends."]),
    ]),
}

# Backward-compatible view: the first chapter of each plan, as the old
# (title, invitation, steps) shape. Kept so any older reference still works.
PILLAR_EXERCISES = {k: v[1][0] for k, v in PILLAR_PLANS.items()}

# Season = a guided arc too. An onboarding lesson plan that helps someone name the
# chapter of life they're in and keep tending it, one sitting at a time.
#   (title, invitation, [step prompts])
SEASON_PLAN = [
    ("Name your season",
     "Before anything else — give this chapter of your life a name.",
     ["Step back from today and feel for the larger chapter you're in. If this season of your life had a name — 'rebuilding', 'the long wait', 'blooming', 'holding on' — what would you call it?",
      "What's been true of this whole stretch of time, not just today?",
      "How did this season begin? What ended or started to let it in?"]),
    ("What it's asking of you",
     "Every season asks something. Listen for what this one wants.",
     ["What is this season asking of you — patience, courage, rest, letting go, showing up?",
      "Where are you resisting that ask, and what would it feel like to stop fighting it?",
      "What would it look like to meet this season on its own terms, just for now?"]),
    ("What it's giving you",
     "Even hard seasons give something. Go looking for it.",
     ["What is this season quietly giving you — a lesson, a strength, a clarity, a person, a kind of growth?",
      "What have you learned here that you couldn't have learned anywhere else?",
      "What are you grateful for in this chapter, even if it's hard?"]),
    ("What's ending, what's beginning",
     "Honor the turning you're in the middle of.",
     ["What feels like it's ending in this season? Let yourself name it, and feel it.",
      "What feels like it's just beginning, even faintly?",
      "What do you want to carry forward, and what are you ready to leave behind?"]),
    ("Who you're becoming in it",
     "See the person this season is shaping.",
     ["Who are you becoming through this chapter? How are you different from who you were when it started?",
      "If you looked back on this time in five years, what would you want to remember about who you were?",
      "What would make you proud of how you moved through it?"]),
    ("How you'll tend it",
     "Seasons need tending. Choose how you'll stay with this one.",
     ["Knowing what this season is, how do you want to tend yourself through it — what do you need more of, and less of?",
      "What's one small practice or promise that would help you stay steady here?",
      "Write a short note to the you who's a little further along in this season. What do you want them to know?"]),
]

# The three journaling modes. Deep = pillar work; Daily = a letter to today;
# Season = where you are in the larger arc of your life right now.
JOURNAL_KINDS = ("deep", "daily", "season")

def _gemini_key():
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

GEMINI_KEY = _gemini_key()

# ---------------------------------------------------------------------------
# ElevenLabs narration (server-side; key never reaches the client). Audio is
# cached on disk (the /data volume) keyed by voice+model+text, so repeated
# meditation lines are generated once and reused — keeping credit use low.
# ---------------------------------------------------------------------------
ELEVEN_KEY = os.environ.get("ELEVENLABS_API_KEY")
ELEVEN_VOICE = os.environ.get("ELEVEN_VOICE", "SAz9YHcvj6GT2YYXdXww")  # "River" — calm, neutral
ELEVEN_MODEL = os.environ.get("ELEVEN_MODEL", "eleven_turbo_v2_5")
ELEVEN_SPEED = float(os.environ.get("ELEVEN_SPEED", "0.88"))  # <1.0 = slower, calmer pace
TTS_DIR = os.path.join(DATA, "tts")

def eleven_tts(text):
    if not ELEVEN_KEY:
        return None
    text = (text or "").strip()[:900]
    if not text:
        return None
    key = hashlib.sha1(("%s|%s|%.2f|%s" % (ELEVEN_VOICE, ELEVEN_MODEL, ELEVEN_SPEED, text)).encode("utf-8")).hexdigest()
    path = os.path.join(TTS_DIR, key + ".mp3")
    try:
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
    except OSError:
        pass
    body = json.dumps({
        "text": text, "model_id": ELEVEN_MODEL,
        "voice_settings": {"stability": 0.55, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True, "speed": ELEVEN_SPEED},
    }).encode("utf-8")
    url = "https://api.elevenlabs.io/v1/text-to-speech/%s?output_format=mp3_44100_128" % ELEVEN_VOICE
    req = urllib.request.Request(url, data=body, headers={
        "xi-api-key": ELEVEN_KEY, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            audio = r.read()
    except Exception:
        return None
    if not audio:
        return None
    try:
        os.makedirs(TTS_DIR, exist_ok=True)
        with open(path, "wb") as f:
            f.write(audio)
    except OSError:
        pass
    return audio

# ---------------------------------------------------------------------------
# Sentry (zero-dep). Backend errors are posted to Sentry's envelope endpoint via
# stdlib urllib — no sentry-sdk dependency, so the tiny reboot-safe image stays
# dependency-free. Best-effort: never raises, never blocks a request meaningfully.
# ---------------------------------------------------------------------------
SENTRY_DSN = os.environ.get("SENTRY_DSN", "").strip()
SENTRY_ENV = os.environ.get("SENTRY_ENV", "production")
SENTRY_REL = os.environ.get("SENTRY_REL", "lumen-prod")

def _sentry_parse_dsn(dsn):
    # https://<key>@<host>/<project_id>
    try:
        m = re.match(r"https://([0-9a-f]+)@([^/]+)/(\d+)", dsn)
        if not m:
            return None
        return {"key": m.group(1), "host": m.group(2), "project": m.group(3)}
    except Exception:
        return None

_SENTRY = _sentry_parse_dsn(SENTRY_DSN) if SENTRY_DSN else None

def sentry_capture(exc, request=None, level="error"):
    if not _SENTRY:
        return
    try:
        import traceback as _tb
        frames = []
        for fr in _tb.extract_tb(exc.__traceback__)[-25:]:
            frames.append({"filename": fr.filename, "function": fr.name,
                           "lineno": fr.lineno, "context_line": (fr.line or "")[:200]})
        event = {
            "event_id": secrets.token_hex(16),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "platform": "python",
            "level": level,
            "environment": SENTRY_ENV,
            "release": SENTRY_REL,
            "server_name": "lumen",
            "exception": {"values": [{
                "type": type(exc).__name__,
                "value": str(exc)[:500],
                "stacktrace": {"frames": frames},
            }]},
        }
        if request:
            event["request"] = request
        hdr = json.dumps({"event_id": event["event_id"], "dsn": SENTRY_DSN})
        item_hdr = json.dumps({"type": "event"})
        payload = json.dumps(event)
        body = ("%s\n%s\n%s" % (hdr, item_hdr, payload)).encode("utf-8")
        url = "https://%s/api/%s/envelope/" % (_SENTRY["host"], _SENTRY["project"])
        auth = ("Sentry sentry_version=7, sentry_client=lumen-stdlib/1.0, sentry_key=%s"
                % _SENTRY["key"])
        req = urllib.request.Request(url, data=body, method="POST", headers={
            "Content-Type": "application/x-sentry-envelope", "X-Sentry-Auth": auth})
        urllib.request.urlopen(req, timeout=4).read()
    except Exception:
        pass  # monitoring must never break the app

def gemini_json(prompt, timeout=20):
    if not GEMINI_KEY:
        return None
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "gemini-flash-latest:generateContent?key=" + GEMINI_KEY)
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json",
                                 "thinkingConfig": {"thinkingBudget": 0},
                                 "maxOutputTokens": 500, "temperature": 0.8}}
    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        parts = data["candidates"][0]["content"]["parts"]
        txt = "".join(p["text"] for p in parts if isinstance(p, dict) and "text" in p)
        return json.loads(txt)
    except Exception:
        return None

# Claude via our ccut-gateway (the signed-in `claude` CLI behind a bearer token).
# Preferred over Gemini for journal intelligence when configured.
CLAUDE_URL = os.environ.get("LUMEN_CLAUDE_URL") or os.environ.get("CCUT_CLAUDE_URL")
CLAUDE_TOKEN = os.environ.get("LUMEN_CLAUDE_TOKEN") or os.environ.get("CCUT_CLAUDE_TOKEN")

def claude_json(prompt, timeout=40):
    """Ask Claude (ccut-gateway, bearer auth) for a JSON object. Returns dict or None.
    Same contract as gemini_json so callers can prefer Claude and fall back."""
    if not (CLAUDE_URL and CLAUDE_TOKEN):
        return None
    body = json.dumps({"prompt": prompt, "model": "sonnet"}).encode()
    try:
        req = urllib.request.Request(
            CLAUDE_URL.rstrip("/") + "/v1/claude", data=body,
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + CLAUDE_TOKEN})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            outer = json.loads(r.read().decode("utf-8", "replace"))
        env = json.loads(outer.get("stdout") or "{}")
        txt = (env.get("result") or "").strip()
        if txt.startswith("```"):
            txt = re.sub(r"^```[a-zA-Z]*\n?", "", txt)
            txt = re.sub(r"\n?```$", "", txt).strip()
        try:
            return json.loads(txt)
        except Exception:
            m = re.search(r"\{.*\}", txt, re.S)
            return json.loads(m.group(0)) if m else None
    except Exception:
        return None

def ai_enabled():
    return bool((CLAUDE_URL and CLAUDE_TOKEN) or GEMINI_KEY)

def ai_json(prompt, timeout=40):
    """Prefer Claude (ccut-gateway); fall back to Gemini; else None."""
    return claude_json(prompt, timeout) or gemini_json(prompt, timeout)

def journal_reflect(prompt, text, kind="daily", pillar=None, place=None):
    """The Keeper's brief, warm reflection on a sealed letter + an inferred mood word.
    Mode-aware: deep (pillar work), daily, or travel. Best-effort — returns empty
    strings if the companion is unavailable, so it never blocks a save."""
    if not ai_enabled():
        return {"reflection": "", "mood": ""}
    if kind == "deep" and pillar:
        ctx = (f"This is deep journaling work on their '{pillar}' pillar — a chosen, "
               "intentional sitting, not a quick note. Honour the depth: reflect on the "
               "whole piece, name what they're really wrestling with on this pillar, and "
               "mirror one brave or true thing with warmth.")
    elif kind == "season":
        named = (" they named '%s'" % place) if place else ""
        ctx = ("This is a 'season of life' reflection%s — about the larger chapter they are "
               "living through right now, not just today. Reflect on the season itself with "
               "warmth: what it is asking of them, what it is giving, and honour where they "
               "are in the arc without rushing them past it." % named)
    else:
        ctx = "This is a daily journal letter — a check-in with themselves."
    p = ("You are the Keeper — a warm, grounded meditation companion inside Lumen. "
         "Someone just wrote this private journal entry"
         + (f' responding to the prompt “{prompt}”.' if prompt else ".") + " " + ctx +
         " Reflect back in 1-2 short sentences: name the feeling you hear, mirror one true "
         "thing with warmth, and leave them lighter. Second person, gentle, human. Do NOT "
         "advise, diagnose, or sound clinical. Also infer their overall mood as ONE lowercase "
         "word.\n\nReturn ONLY JSON: {\"reflection\":\"...\",\"mood\":\"<one word>\"}\n\nEntry:\n"
         + text[:1800])
    r = ai_json(p, timeout=25) or {}
    return {"reflection": (r.get("reflection") or "").strip()[:400],
            "mood": (r.get("mood") or "").strip().lower()[:24]}

def deep_exercise(c, u, pillar, chapter=None):
    """The next chapter of a pillar's lesson plan, chosen by how far the person has
    already walked it, plus an optional AI-written opening that greets them where
    their recent work left off. The plan is the backbone; the opening is the touch.
    If `chapter` (1-based) is given and valid, open that specific chapter instead."""
    plan = PILLAR_PLANS.get(pillar)
    if not plan:
        return None
    arc, chapters = plan
    # How many deep sittings has this person logged on this pillar? The count
    # decides which chapter is next; we cycle back through once the plan is done.
    done = c.execute("SELECT COUNT(*) n FROM journal WHERE user_id=? AND kind='deep' "
                     "AND pillar=?", (u["id"], pillar)).fetchone()["n"]
    n = len(chapters)
    if chapter and str(chapter).isdigit() and 1 <= int(chapter) <= n:
        idx = int(chapter) - 1
    else:
        idx = done % n if n else 0
    title, invitation, steps = chapters[idx]
    titles = [ch[0] for ch in chapters]
    opening = ""
    if ai_enabled():
        prev = c.execute("SELECT text,created FROM journal WHERE user_id=? AND kind='deep' "
                         "AND pillar=? ORDER BY id DESC LIMIT 3", (u["id"], pillar)).fetchall()
        hist = "\n\n".join(f"[{(r['created'] or '')[:10]}] {(r['text'] or '')[:300]}" for r in prev)
        name = (u["name"] or "").split()[0] if u["name"] else ""
        p = ("You are the Keeper inside Lumen, opening a deep journaling sitting on the "
             f"person's '{pillar}' pillar. Today's chapter is '{title}' ({invitation}). "
             "Write ONE warm, grounding opening line (max 22 words, second person, no emoji) "
             "that invites them into this chapter. "
             + (f"Their name is {name}. " if name else "")
             + ("Here is their recent work on this pillar, newest first — gently acknowledge "
                "where they've been without repeating it:\n" + hist
                if hist else "This is their first time on this pillar; welcome them to it.")
             + "\n\nReturn ONLY JSON: {\"opening\":\"...\"}")
        r = ai_json(p, timeout=20) or {}
        opening = (r.get("opening") or "").strip()[:200]
    return {"pillar": pillar, "title": title, "invitation": invitation, "steps": steps,
            "opening": opening, "arc": arc, "chapter": idx + 1, "chapters": n,
            "chapter_titles": titles, "looped": done >= n}

def season_exercise(c, u):
    """The next chapter of the Season onboarding plan — a guided arc that walks a
    person through naming and tending the chapter of life they're in. Advances by
    how many season sittings they've logged, then gently cycles."""
    chapters = SEASON_PLAN
    done = c.execute("SELECT COUNT(*) n FROM journal WHERE user_id=? AND kind='season'",
                     (u["id"],)).fetchone()["n"]
    n = len(chapters)
    idx = done % n if n else 0
    title, invitation, steps = chapters[idx]
    opening = ""
    if ai_enabled():
        prev = c.execute("SELECT text,place,created FROM journal WHERE user_id=? AND kind='season' "
                         "ORDER BY id DESC LIMIT 2", (u["id"],)).fetchall()
        named = next((r["place"] for r in prev if r["place"]), "")
        hist = "\n\n".join(f"[{(r['created'] or '')[:10]}] {(r['text'] or '')[:300]}" for r in prev)
        name = (u["name"] or "").split()[0] if u["name"] else ""
        p = ("You are the Keeper inside Lumen, opening a 'season of life' sitting — part of a "
             f"guided arc. Today's chapter is '{title}' ({invitation}). Write ONE warm, grounding "
             "opening line (max 22 words, second person, no emoji) that invites them in. "
             + (f"Their name is {name}. " if name else "")
             + (f"They've named this season '{named}'. " if named else "")
             + ("Their recent season reflections, newest first:\n" + hist
                if hist else "This is their first season sitting; welcome them to it.")
             + "\n\nReturn ONLY JSON: {\"opening\":\"...\"}")
        r = ai_json(p, timeout=20) or {}
        opening = (r.get("opening") or "").strip()[:200]
    return {"title": title, "invitation": invitation, "steps": steps, "opening": opening,
            "chapter": idx + 1, "chapters": n, "chapter_titles": [ch[0] for ch in chapters],
            "looped": done >= n}

def journal_insights(rows):
    """Find the gentle throughline across a person's recent letters."""
    if not ai_enabled() or len(rows) < 2:
        return None
    joined = "\n\n".join(
        f"[{(r['created'] or '')[:10]} · felt {r['mood'] or '—'}] {(r['text'] or '')[:400]}"
        for r in rows)
    p = ("You are the Keeper inside Lumen. Below are a person's recent private journal letters, "
         "newest first. Find the gentle throughline — do not advise or diagnose, just notice with "
         "warmth. Return ONLY JSON: {\"themes\":[\"..\",\"..\",\"..\"] (2-4 short noun phrases), "
         "\"arc\":\"one sentence on their emotional arc lately\", \"observation\":\"one warm, "
         "specific observation, 2 sentences max\", \"nudge\":\"one gentle thing to sit with or "
         "write about next\"}\n\n" + joined)
    r = ai_json(p, timeout=45)
    if not r:
        return None
    return {"themes": [str(x)[:40] for x in (r.get("themes") or [])][:4],
            "arc": (r.get("arc") or "").strip()[:240],
            "observation": (r.get("observation") or "").strip()[:400],
            "nudge": (r.get("nudge") or "").strip()[:240]}

def gemini_transcribe(img_b64, mime, timeout=40):
    """OCR/transcribe handwriting or text in a photo via Gemini vision."""
    if not GEMINI_KEY:
        return None
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "gemini-flash-latest:generateContent?key=" + GEMINI_KEY)
    prompt = ("Transcribe all handwritten or printed text in this image exactly as written, "
              "preserving line breaks and paragraphs. Do not add commentary or corrections. "
              'Return JSON {"text":"..."}. If there is no legible text, return {"text":""}.')
    body = {"contents": [{"parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime, "data": img_b64}}]}],
            "generationConfig": {"response_mime_type": "application/json",
                                 "thinkingConfig": {"thinkingBudget": 0},
                                 "maxOutputTokens": 2048, "temperature": 0.2}}
    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        parts = data["candidates"][0]["content"]["parts"]
        txt = "".join(p["text"] for p in parts if isinstance(p, dict) and "text" in p)
        return (json.loads(txt).get("text") or "").strip()
    except Exception:
        return None

# ---- the Keeper: conversational agent with tools --------------------------

CHAT_SYSTEM = (
    "You are the Keeper — a warm, grounded meditation and journaling companion inside Lumen, "
    "an app where people meditate, light up a world map, build a mandala of achievements, "
    "and write reflective journal 'letters'. Speak gently, briefly, and human — your replies are "
    "often read aloud, so keep them short (1-3 sentences) and plain, no markdown, no emojis. "
    "You can act for the user through tools: write a journal entry (write_journal), look up their "
    "stats (get_stats), read or change their Life OS pillars and daily focus (get_lifeos, "
    "set_lifeos_pillar, set_focus), remember things about them (remember), and recall recent "
    "entries (get_recent_journal). When the user asks you to save/write/update something, use the "
    "tool and then confirm warmly what you did. Never invent stats — call get_stats. Life OS pillars "
    "are exactly: Family, Hobbies, Career, Health, Relationships, Inner Growth. Directions are N, E, S, W. "
    "If the user is just venting or reflecting, listen and reflect back; offer to write it down. "
    "About Lumen, if asked: Meditate runs timed sessions with live soundscapes; the Map glows with "
    "everyone who meditated and can replay your journey around the world; the Mandala is a single sacred object "
    "whose colored facets light up as you earn achievements (sitting, streaks, visiting places, journaling); "
    "Artifacts are real, meaningful objects you can acquire; the Journal holds your reflective letters; "
    "and Life OS is your compass of life pillars and daily focus."
)

CHAT_TOOLS = [{"function_declarations": [
    {"name": "get_stats", "description": "Get the user's meditation stats (level, light, streak, sessions, minutes, places, league).",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "get_lifeos", "description": "Get the user's Life OS: base, the four cardinal pillars, and daily focus pillars.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "get_recent_journal", "description": "Get the text of the user's most recent journal letters.",
     "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "description": "How many entries (default 3, max 8)."}}}},
    {"name": "write_journal", "description": "Save a new journal letter for the user. Use their own words when possible.",
     "parameters": {"type": "object", "properties": {
         "text": {"type": "string", "description": "The journal entry body."},
         "prompt": {"type": "string", "description": "Optional prompt/title this reflects on."},
         "share": {"type": "boolean", "description": "Share it to the community feed (default false)."}},
         "required": ["text"]}},
    {"name": "set_lifeos_pillar", "description": "Assign (or clear) a Life OS pillar at a cardinal direction.",
     "parameters": {"type": "object", "properties": {
         "direction": {"type": "string", "enum": ["N", "E", "S", "W"]},
         "pillar": {"type": "string", "description": "One of: Family, Hobbies, Career, Health, Relationships, Inner Growth. Empty string to clear."}},
         "required": ["direction", "pillar"]}},
    {"name": "set_focus", "description": "Set the user's one or two daily focus pillars (must be pillars already on their compass).",
     "parameters": {"type": "object", "properties": {
         "pillars": {"type": "array", "items": {"type": "string"}, "description": "Up to two pillar names."}},
         "required": ["pillars"]}},
    {"name": "remember", "description": "Record a short, durable fact or summary about the user for future conversations.",
     "parameters": {"type": "object", "properties": {"note": {"type": "string"}}, "required": ["note"]}},
]}]

def chat_tool_exec(c, u, name, args):
    args = args or {}
    u = c.execute("SELECT * FROM users WHERE id=?", (u["id"],)).fetchone()  # refresh
    if name == "get_stats":
        return profile_dict(c, u)
    if name == "get_lifeos":
        return lifeos_get(u)
    if name == "get_recent_journal":
        lim = max(1, min(8, int(args.get("limit") or 3)))
        rows = c.execute("SELECT text,created FROM journal WHERE user_id=? ORDER BY id DESC LIMIT ?", (u["id"], lim)).fetchall()
        return {"entries": [{"text": r["text"], "date": r["created"][:10]} for r in rows]}
    if name == "write_journal":
        text = (args.get("text") or "").strip()
        if not text:
            return {"ok": False, "error": "empty"}
        c.execute("INSERT INTO journal(user_id,prompt,text,mood,shared,created) VALUES(?,?,?,?,?,?)",
                  (u["id"], (args.get("prompt") or "")[:300], text[:4000], "",
                   1 if args.get("share") else 0, now_iso()))
        award_journal_ach(c, u); c.commit()
        return {"ok": True, "count": c.execute("SELECT COUNT(*) n FROM journal WHERE user_id=?", (u["id"],)).fetchone()["n"]}
    if name == "set_lifeos_pillar":
        d = (args.get("direction") or "").upper()
        pil = (args.get("pillar") or "").strip()
        if d not in ("N", "E", "S", "W"):
            return {"ok": False, "error": "bad direction"}
        if pil and pil not in PILLARS:
            return {"ok": False, "error": "unknown pillar"}
        lo = lifeos_get(u)
        for k in ("N", "E", "S", "W"):
            if lo["pillars"].get(k) == pil and k != d:
                lo["pillars"][k] = None
        lo["pillars"][d] = pil or None
        lo["focus"] = [f for f in lo.get("focus", []) if f in [v for v in lo["pillars"].values() if v]]
        c.execute("UPDATE users SET lifeos=?, lo_prompts=NULL, lo_prompts_day=NULL WHERE id=?",
                  (json.dumps({"base": lo["base"], "pillars": lo["pillars"], "focus": lo["focus"]}), u["id"])); c.commit()
        return {"ok": True, "pillars": lo["pillars"]}
    if name == "set_focus":
        lo = lifeos_get(u)
        chosen = [v for v in lo["pillars"].values() if v]
        focus = [f for f in (args.get("pillars") or []) if f in chosen][:2]
        c.execute("UPDATE users SET lifeos=?, lo_prompts=NULL, lo_prompts_day=NULL WHERE id=?",
                  (json.dumps({"base": lo["base"], "pillars": lo["pillars"], "focus": focus}), u["id"])); c.commit()
        return {"ok": True, "focus": focus}
    if name == "remember":
        note = (args.get("note") or "").strip()
        if note:
            c.execute("INSERT INTO user_notes(user_id,note,created) VALUES(?,?,?)", (u["id"], note[:500], now_iso())); c.commit()
        return {"ok": True}
    return {"error": "unknown tool"}

def gemini_chat(contents, timeout=30):
    if not GEMINI_KEY:
        return None
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "gemini-flash-latest:generateContent?key=" + GEMINI_KEY)
    body = {"systemInstruction": {"parts": [{"text": CHAT_SYSTEM}]},
            "contents": contents, "tools": CHAT_TOOLS,
            "generationConfig": {"temperature": 0.7, "thinkingConfig": {"thinkingBudget": 0},
                                 "maxOutputTokens": 800}}
    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        return data["candidates"][0]["content"].get("parts", [])
    except Exception:
        return None

def lifeos_get(u):
    try:
        lo = json.loads(u["lifeos"]) if u["lifeos"] else {}
    except Exception:
        lo = {}
    lo.setdefault("base", (u["city"] or "My base"))
    lo.setdefault("pillars", {})     # {N,E,S,W: pillar}
    lo.setdefault("focus", [])       # up to 2 pillar names
    lo["configured"] = bool(lo.get("pillars")) and len([v for v in lo["pillars"].values() if v]) >= 1
    return lo

def daily_prompts(c, u):
    """Three AI daily prompts (focus / reflection / gratitude), cached per UTC day."""
    today = today_str()
    if u["lo_prompts_day"] == today and u["lo_prompts"]:
        try:
            return json.loads(u["lo_prompts"])
        except Exception:
            pass
    lo = lifeos_get(u)
    focus = [f for f in lo.get("focus", []) if f] or \
            [v for v in lo.get("pillars", {}).values() if v][:2]
    out = None
    if focus:
        pr = (
            "You are a gentle meditation journaling guide. A person's chosen life focuses are: "
            + ", ".join(focus) + ". "
            "Return ONE single JSON object (NOT an array) with exactly three string keys: "
            '"focus", "reflection", "gratitude". '
            "The \"focus\" value is a journaling prompt inviting reflection specifically on "
            + focus[0] + ". The \"reflection\" value is a calm daily self-check-in prompt. "
            "The \"gratitude\" value is a prompt inviting them to notice something to be grateful for. "
            "Each value is one warm second-person question under 18 words. No emojis."
        )
        g = gemini_json(pr)
        if isinstance(g, list) and g:
            g = g[0]
        if isinstance(g, dict) and all(isinstance(g.get(k), str) and g.get(k).strip()
                                       for k in ("focus", "reflection", "gratitude")):
            out = {"focus": g["focus"].strip(), "reflection": g["reflection"].strip(),
                   "gratitude": g["gratitude"].strip(), "ai": True}
    if out:
        # only cache a real AI result — never cache the fallback, so it keeps retrying
        c.execute("UPDATE users SET lo_prompts=?, lo_prompts_day=? WHERE id=?",
                  (json.dumps(out), today, u["id"]))
        c.commit()
        return out
    f0 = focus[0] if focus else "what matters most"
    return {"focus": f"Where did {f0.lower()} ask for your attention today?",
            "reflection": prompt_for_today(),
            "gratitude": "What is one small thing you can be grateful for right now?", "ai": False}

# ---------------------------------------------------------------------------
# synthetic community seed (so the map + leagues feel alive on day one)
# ---------------------------------------------------------------------------

SEED_CITIES = [
    ("Tokyo", 35.68, 139.69), ("Seoul", 37.57, 126.98), ("Mumbai", 19.08, 72.88),
    ("Bangkok", 13.76, 100.50), ("Bali", -8.65, 115.22), ("Sydney", -33.87, 151.21),
    ("Auckland", -36.85, 174.76),
    ("Dubai", 25.20, 55.27), ("Istanbul", 41.01, 28.98),
    ("Berlin", 52.52, 13.40), ("Paris", 48.86, 2.35), ("London", 51.51, -0.13),
    ("Lisbon", 38.72, -9.14), ("Reykjavik", 64.15, -21.94), ("Stockholm", 59.33, 18.07),
    ("New York", 40.71, -74.01), ("Toronto", 43.65, -79.38), ("Mexico City", 19.43, -99.13),
    ("Los Angeles", 34.05, -118.24), ("Austin", 30.27, -97.74), ("Boulder", 40.01, -105.27),
    ("Vancouver", 49.28, -123.12), ("São Paulo", -23.55, -46.63), ("Buenos Aires", -34.60, -58.38),
    ("Lima", -12.05, -77.04), ("Bogotá", 4.71, -74.07), ("Honolulu", 21.31, -157.86),
]
SEED_NAMES = ["Aria","Kai","Nadia","Leo","Mei","Omar","Sofia","Ravi","Luna","Theo","Ines","Yuki",
    "Mateo","Zara","Finn","Priya","Noah","Ada","Hugo","Elif","Rin","Diego","Maya","Jonas",
    "Amara","Sage","Noor","Felix","Iris","Tomas","Chloe","Bodhi","Esme","Arlo","Nova","River",
    "Wren","Ezra","Juno","Milo","Dara","Ocean","Indira","Soren","Yara","Cassian","Lila","Oden"]
SOUNDSCAPES = ["rain", "forest", "ocean", "space", "silence"]

# Extra well-known cities used only for labelling real coordinates (not seeded as practitioners).
LABEL_CITIES = SEED_CITIES + [
    ("Jersey City", 40.73, -74.07), ("Brooklyn", 40.68, -73.94), ("Philadelphia", 39.95, -75.17),
    ("Boston", 42.36, -71.06), ("Washington", 38.91, -77.04), ("Chicago", 41.88, -87.63),
    ("San Francisco", 37.77, -122.42), ("Seattle", 47.61, -122.33), ("Denver", 39.74, -104.99),
    ("Miami", 25.76, -80.19), ("Atlanta", 33.75, -84.39), ("Montreal", 45.50, -73.57),
    ("Madrid", 40.42, -3.70), ("Rome", 41.90, 12.50), ("Amsterdam", 52.37, 4.90),
    ("Dublin", 53.35, -6.26), ("Singapore", 1.35, 103.82), ("Hong Kong", 22.32, 114.17),
    ("Delhi", 28.61, 77.21), ("Barcelona", 41.39, 2.17),
]

def nearest_city(lat, lon):
    """Approximate reverse-geocode: closest known city to coarse coords. Keeps us dep-free/offline
    and consistent with the app's fuzzed-location privacy model. None if nothing is reasonably close."""
    try:
        lat = float(lat); lon = float(lon)
    except Exception:
        return None
    best = None; bestd = None
    for name, clat, clon in LABEL_CITIES:
        d = (lat - clat) ** 2 + (lon - clon) ** 2
        if bestd is None or d < bestd:
            bestd = d; best = name
    # cap ~ 2.5deg (~275km) so remote coords don't get a misleading nearby-city tag
    return best if bestd is not None and bestd <= 6.25 else None

def _fuzz(v, amt=0.04):
    return round(v + random.uniform(-amt, amt), 4)

def save_spot_photo(sid, dataurl):
    """Decode a data-URL JPEG/PNG for a session's spot photo, write it to the
    spots dir, and return the relative URL path (or None on failure)."""
    try:
        img = dataurl or ""
        if img.startswith("data:"):
            head, _, b64 = img.partition(",")
            ext = "png" if "png" in head.lower() else "jpg"
            img = b64
        else:
            ext = "jpg"
        if not img:
            return None
        raw = base64.b64decode(img, validate=False)
        if not raw or len(raw) > 6 * 1024 * 1024:  # cap ~6MB decoded
            return None
        fn = "%d.%s" % (int(sid), ext)
        with open(os.path.join(SPOT_DIR, fn), "wb") as f:
            f.write(raw)
        return "spot/" + fn
    except Exception as e:
        print("save_spot_photo error:", e)
        return None

def seed_world():
    c = db()
    n = c.execute("SELECT COUNT(*) n FROM users WHERE is_bot=1").fetchone()["n"]
    if n > 0:
        c.close(); return
    rnd = random.Random(42)
    nm = rnd.sample(SEED_NAMES, min(46, len(SEED_NAMES)))
    today = datetime.now(timezone.utc)
    for i, name in enumerate(nm):
        city, lat, lon = rnd.choice(SEED_CITIES)
        light = 0
        total_min = 0
        total_sess = 0
        max_min = 0
        has_night = False
        has_dawn = False
        uid = c.execute(
            "INSERT INTO users(name,is_bot,lat,lon,city,created) VALUES(?,?,?,?,?,?)",
            (name, 1, _fuzz(lat), _fuzz(lon), city, now_iso())).lastrowid
        # generate a trailing history so lifetime + weekly stats look organic
        days_active = rnd.randint(3, 40)
        streak = rnd.randint(0, 25)
        today_date = today.date()
        for d in range(days_active):
            # ~70% chance of a session today so the live map/leaderboards look alive,
            # tapering for older days.
            p = 0.70 if d == 0 else 0.45
            if rnd.random() > p:
                continue
            day_d = today_date - timedelta(days=d)
            # a real clock time within that day (not "now minus hours", which would
            # otherwise push today's sessions into yesterday near UTC midnight)
            dt = datetime(day_d.year, day_d.month, day_d.day,
                          rnd.randint(5, 22), rnd.randint(0, 59), tzinfo=timezone.utc)
            mins = rnd.choice([5, 5, 10, 10, 10, 20, 30])
            ss = rnd.choice(SOUNDSCAPES)
            lg = compute_light(mins, rnd.randint(1, 12), dt)
            lat2, lon2 = _fuzz(lat), _fuzz(lon)
            c.execute("""INSERT INTO sessions(user_id,minutes,soundscape,light,lat,lon,city,mood,note,started,ended,day,week)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (uid, mins, ss, lg, lat2, lon2, city, rnd.choice(["calm","energized","unclear",""]), "",
                       dt.isoformat(), dt.isoformat(), dt.date().isoformat(), week_str(dt.date())))
            light += lg; total_min += mins; total_sess += 1
            if mins >= 30: max_min = 30
            if 22 <= dt.hour or dt.hour < 4: has_night = True
            if 4 <= dt.hour < 7: has_dawn = True
        best = max(streak, rnd.randint(0, 30))
        c.execute("UPDATE users SET light=?,streak=?,best_streak=?,total_minutes=?,total_sessions=? WHERE id=?",
                  (light, streak, best, total_min, total_sess, uid))
        # award achievements from the bot's final stats so the "% have this" rarity
        # stat and leaderboards look believable
        earned = []
        if total_sess > 0: earned.append("first_light")
        if max_min >= 30: earned.append("marathoner")
        if best >= 7: earned.append("week_warrior")
        if best >= 30: earned.append("constellation")
        if has_night: earned.append("moon_child")
        if has_dawn: earned.append("dawn_patrol")
        if total_min >= 100: earned.append("centurion")
        if light >= 500: earned.append("deep_diver")
        if light >= 2000: earned.append("luminary")
        for code in earned:
            c.execute("INSERT OR IGNORE INTO achievements(user_id,code,created) VALUES(?,?,?)", (uid, code, now_iso()))
    c.commit(); c.close()


def seed_live_week(c):
    """Refresh the community bots' CURRENT-week activity so Leagues, global ranks
    and the live map all feel alive. seed_world() only runs once, so its bot
    sessions drift into past weeks and the weekly views go empty. This re-seeds
    the current ISO week with a believable spread across league tiers (so every
    league has a cohort), clustered near each bot's home city. Idempotent: it
    clears this week's bot sessions first, then recomputes bot lifetime stats."""
    wk = week_str()
    bots = c.execute("SELECT id,lat,lon,city FROM users WHERE is_bot=1").fetchall()
    if not bots:
        return {"bots": 0}
    rnd = random.Random(hash(wk) & 0xffffffff)
    ids = [b["id"] for b in bots]
    qmarks = ",".join("?" * len(ids))
    c.execute(f"DELETE FROM sessions WHERE week=? AND user_id IN ({qmarks})", (wk, *ids))
    today = datetime.now(timezone.utc)
    dow = today.isoweekday()            # 1=Mon .. 7=Sun; valid in-week offsets 0..dow-1
    order = bots[:]; rnd.shuffle(order)
    n = len(order)
    # weekly-light target bands, as cumulative fractions of the shuffled pool, chosen
    # to populate each tier (Ember..Supernova) and give a real cohort around Nova.
    bands = [(0.20, 20, 130), (0.42, 150, 340), (0.60, 360, 680),
             (0.76, 720, 1150), (0.90, 1250, 1950), (1.01, 2050, 3400)]
    added = 0
    for i, b in enumerate(order):
        frac = (i + 0.5) / n
        lo, hi = next((lo, hi) for cut, lo, hi in bands if frac < cut)
        target = rnd.randint(lo, hi)
        nsess = rnd.randint(3, 8)
        # at least one sit today (offset 0) for map liveness; rest spread across the week
        offsets = [0] + [rnd.randint(0, max(0, dow - 1)) for _ in range(nsess - 1)]
        shares = [rnd.random() + 0.3 for _ in offsets]
        tot = sum(shares)
        for off, sh in zip(offsets, shares):
            lgt = max(5, round(target * sh / tot))
            day_d = today.date() - timedelta(days=off)
            dt = datetime(day_d.year, day_d.month, day_d.day,
                          rnd.randint(5, 22), rnd.randint(0, 59), tzinfo=timezone.utc)
            mins = rnd.choice([5, 10, 10, 15, 20, 30])
            c.execute("""INSERT INTO sessions(user_id,minutes,soundscape,light,lat,lon,city,mood,note,started,ended,day,week)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (b["id"], mins, rnd.choice(SOUNDSCAPES), lgt, _fuzz(b["lat"]), _fuzz(b["lon"]),
                       b["city"], rnd.choice(["calm", "energized", "", ""]), "",
                       dt.isoformat(), dt.isoformat(), dt.date().isoformat(), wk))
            added += 1
    # recompute each bot's lifetime stats from all its sessions (keeps all-time ranks + idempotency)
    for b in bots:
        r = c.execute("SELECT COALESCE(SUM(light),0) l, COALESCE(SUM(minutes),0) m, COUNT(*) n "
                      "FROM sessions WHERE user_id=?", (b["id"],)).fetchone()
        c.execute("UPDATE users SET light=?, total_minutes=?, total_sessions=? WHERE id=?",
                  (r["l"], r["m"], r["n"], b["id"]))
    c.commit()
    return {"bots": n, "sessions_added": added, "week": wk}

# ---------------------------------------------------------------------------
# data access helpers
# ---------------------------------------------------------------------------

def user_by_email(c, email):
    return c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

def profile_dict(c, u):
    lvl, into, need = level_for(u["light"])
    wl = c.execute("SELECT COALESCE(SUM(light),0) s FROM sessions WHERE user_id=? AND week=?",
                   (u["id"], week_str())).fetchone()["s"]
    lg = league_for(wl)
    ach = [r["code"] for r in c.execute("SELECT code FROM achievements WHERE user_id=?", (u["id"],))]
    lessons = {}
    for r in c.execute("""SELECT lesson, COUNT(*) n, MAX(ended) last FROM sessions
                          WHERE user_id=? AND lesson IS NOT NULL AND lesson!='' GROUP BY lesson""", (u["id"],)):
        lessons[r["lesson"]] = {"count": r["n"], "last": r["last"]}
    jr = {r["kind"]: r["n"] for r in c.execute(
        "SELECT kind, COUNT(*) n FROM journal WHERE user_id=? GROUP BY kind", (u["id"],))}
    return {
        "lessons": lessons,
        "name": u["name"], "email": u["email"],
        "light": u["light"], "level": lvl, "level_into": into, "level_need": need,
        "streak": u["streak"], "best_streak": u["best_streak"],
        "total_minutes": u["total_minutes"], "total_sessions": u["total_sessions"],
        "weekly_light": wl, "league": lg,
        "tier": (u["tier"] if "tier" in u.keys() else "free"),
        "last_journey": (u["last_journey"] if "last_journey" in u.keys() else None),
        "phone": (u["phone"] if "phone" in u.keys() else None),
        "sms_consent": (u["sms_consent"] if "sms_consent" in u.keys() else 0),
        "sms_optout": (u["sms_optout"] if "sms_optout" in u.keys() else 0),
        "lat": u["lat"], "lon": u["lon"], "city": u["city"],
        "birth_date": u["birth_date"], "birth_time": u["birth_time"],
        "birth_place": u["birth_place"], "sun_sign": u["sun_sign"],
        "achievements": ach,
        "equipped": u["equipped"],
        "companion": u["companion"],
        "motes": u["motes"] or 0,
        "goal_days": u["goal_days"] or 0,   # meditation days/week the user pledged (0 = not set yet)
        "items_owned": c.execute("SELECT COUNT(*) n FROM items WHERE user_id=?", (u["id"],)).fetchone()["n"],
        # Atlas facets — your whole practice, not just travel
        "journal": {"daily": jr.get("daily", 0), "season": jr.get("season", 0),
                    "deep": jr.get("deep", 0), "total": sum(jr.values())},
        "places": distinct_places(c, u["id"]),
    }

# ---------------------------------------------------------------------------
# http
# ---------------------------------------------------------------------------

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, maximum-scale=1">
<meta name="theme-color" content="#0b0a12">
<meta name="description" content="Lumen — a gamified meditation app. Light up a living world map with every sit, earn Light, build streaks, and walk guided voice journeys.">
<link rel="manifest" href="manifest.webmanifest">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Lumen">
<link rel="apple-touch-icon" href="icon-192.png">
<title>Lumen — light up the world, one breath at a time</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
:root{
  --bg:#0b0a12; --bg2:#13111d; --panel:#181527cc; --line:#2a2540;
  --text:#ece9f5; --muted:#9a93b8; --gold:#f5c977; --purple:#a855f7;
  --purple2:#7c3aed; --pink:#ec4899; --good:#6ee7b7;
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif;
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;height:100%}
body{
  background:
    radial-gradient(1200px 700px at 70% -10%, #1b1430 0%, transparent 60%),
    radial-gradient(900px 600px at 10% 110%, #231436 0%, transparent 55%),
    var(--bg);
  color:var(--text); font-family:ui-rounded,-apple-system,"Segoe UI",Roboto,system-ui,sans-serif;
  overscroll-behavior:none;
}
.stars{position:fixed;inset:0;pointer-events:none;z-index:0;opacity:.5}
#app{position:relative;z-index:1;max-width:620px;margin:0 auto;min-height:100%;
  padding:calc(env(safe-area-inset-top) + 8px) 16px calc(96px + env(safe-area-inset-bottom)) 16px}
h1,h2,h3{font-weight:700;letter-spacing:-.02em}
.brand{display:flex;align-items:center;gap:10px;padding:18px 2px 8px}
.brand .mark{font-size:26px;filter:drop-shadow(0 0 10px var(--gold))}
.brand b{font-size:20px}
.hdr{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px 2px 12px}
.hdr-l{display:flex;align-items:center;gap:11px;min-width:0}
.hdr-mark{width:40px;height:40px;flex:none;filter:drop-shadow(0 0 9px rgba(245,201,119,.5));animation:markpulse 4.5s ease-in-out infinite}
.hdr-mark svg{display:block;width:100%;height:100%}
.hdr-wm{display:flex;flex-direction:column;line-height:1;min-width:0}
.hdr-name{font-family:var(--serif);font-weight:700;font-size:27px;letter-spacing:.015em;background:linear-gradient(180deg,#fff2d4,#f3cf84 55%,#e0a648);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;color:transparent}
.hdr-tag{font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hdr-r{text-align:right;flex:none}
.hdr-greet{font-size:13px;font-weight:700;color:var(--text)}
.hdr-date{font-size:11.5px;color:var(--muted);margin-top:2px}
.brand small{color:var(--muted);font-weight:500;margin-left:auto;font-size:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:18px;backdrop-filter:blur(8px);margin:12px 0}
.muted{color:var(--muted)}
.btn{appearance:none;border:0;border-radius:14px;padding:14px 18px;font-size:16px;font-weight:700;
  background:linear-gradient(135deg,var(--purple),var(--purple2));color:#fff;cursor:pointer;width:100%;
  box-shadow:0 6px 24px -8px var(--purple)}
.btn:active{transform:translateY(1px)}
.btn.ghost{background:transparent;border:1px solid var(--line);color:var(--text);box-shadow:none}
.btn.gold{background:linear-gradient(135deg,#f5c977,#e0953a);color:#2a1a05;box-shadow:0 6px 24px -8px var(--gold)}
/* luxe-gold Continue/Begin — taller, richer, larger seal */
.btn.jrnext-btn{display:flex;align-items:center;justify-content:center;gap:10px;padding:19px 18px;font-size:16px;font-weight:800;letter-spacing:.01em;color:#3a2408;border-radius:16px;
  background:linear-gradient(135deg,#ffeeb8 0%,#f7cf84 32%,#e7a94f 64%,#cf8c33 100%);
  box-shadow:0 14px 32px -10px rgba(226,153,62,.8),inset 0 1px 0 rgba(255,247,220,.8),inset 0 -3px 8px -3px rgba(120,76,20,.55)}
.btn.jrnext-btn:active{transform:translateY(1px)}
.btn.jrnext-btn .i{width:22px;height:22px;filter:drop-shadow(0 1px 1px rgba(90,56,12,.4))}
/* luxe "seal" CTA — gold-on-dark, sticks out, bigger gold seal */
.btn.seal-cta{background:linear-gradient(135deg,#2b2010,#1d1408 55%,#120c05);color:#f7d488;
  border:1px solid rgba(245,201,119,.58);
  box-shadow:0 10px 30px -12px rgba(245,201,119,.55),inset 0 1px 0 rgba(255,236,180,.14),inset 0 0 0 1px rgba(245,201,119,.06);
  text-shadow:0 0 12px rgba(245,201,119,.35);letter-spacing:.015em}
.btn.seal-cta:active{transform:translateY(1px)}
.seal-cta .seal-ic{width:30px;height:30px;filter:drop-shadow(0 0 7px rgba(245,201,119,.7))}
.row{display:flex;gap:10px}.row>*{flex:1}
input,textarea,select{width:100%;background:#0f0d18;border:1px solid var(--line);border-radius:12px;
  color:var(--text);padding:12px 14px;font-size:16px;font-family:inherit}
/* custom checkboxes */
input[type=checkbox]{-webkit-appearance:none;appearance:none;width:22px;height:22px;flex:none;padding:0;
  border:1.6px solid var(--line);border-radius:7px;background:#0f0d18;cursor:pointer;position:relative;
  vertical-align:middle;transition:background .15s,border-color .15s,box-shadow .15s}
input[type=checkbox]:hover{border-color:#4b3a6e}
input[type=checkbox]:checked{background:linear-gradient(135deg,var(--purple),var(--purple2));border-color:var(--purple);box-shadow:0 0 10px -2px var(--purple)}
input[type=checkbox]:checked::after{content:"";position:absolute;left:7px;top:3px;width:5px;height:10px;
  border:solid #fff;border-width:0 2.2px 2.2px 0;border-radius:1px;transform:rotate(43deg)}
input[type=checkbox]:active{transform:scale(.92)}
label{font-size:13px;color:var(--muted);display:block;margin:10px 0 5px}
.err{color:#fda4af;font-size:13px;min-height:18px;margin-top:6px}
.pill{display:inline-flex;align-items:center;gap:6px;padding:5px 11px;border-radius:999px;background:#201a33;border:1px solid var(--line);font-size:12px;font-weight:600}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
.chip{border:1px solid var(--line);background:#13101f;border-radius:14px;padding:12px;text-align:center;cursor:pointer;font-weight:600;transition:transform .14s ease,border-color .18s ease,box-shadow .18s ease}
.chip:active{transform:scale(.97)}
.chip.sel{border-color:var(--purple);background:linear-gradient(135deg,#241a3e,#1a1430);box-shadow:0 0 0 1px var(--purple) inset}
.chip .big{font-size:20px}
/* branded section headers (Duration / Soundscape) */
.sec-head{display:flex;align-items:center;gap:9px;margin:2px 0 12px}
.sec-head h3{margin:0;font-size:16px;font-weight:700}
.sec-ic{width:30px;height:30px;border-radius:9px;flex:none;display:grid;place-items:center;
  background:linear-gradient(135deg,#2a2047,#191430);border:1px solid #ffffff14;color:var(--gold)}
.sec-ic.snd{color:var(--purple)}
.sec-ic .i{width:17px;height:17px;filter:drop-shadow(0 0 5px currentColor)}
/* done-up duration chips */
.dur-chip{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:0;padding:12px 4px;position:relative;overflow:hidden}
.dur-chip .big{font-size:23px;font-weight:800;line-height:1;color:var(--text)}
.dur-chip .chip-unit{font-size:9.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.09em;margin-top:3px}
.dur-chip .chip-sub{font-size:11px;color:var(--muted);font-weight:600;margin-top:5px}
.dur-chip.sel{border-color:var(--gold);background:linear-gradient(135deg,#2b2112,#1b150b);box-shadow:0 0 0 1px var(--gold) inset,0 7px 22px -12px var(--gold)}
.dur-chip.sel .big{color:var(--gold)}
.dur-chip.sel .chip-sub{color:#f3d8a0}
.snd-chip{display:flex;flex-direction:column;align-items:center;gap:5px;font-size:13px}
.quick-med{display:flex;align-items:center;gap:14px;width:100%;text-align:left;cursor:pointer;color:var(--text);
  background:linear-gradient(135deg,#1c1626,#141019);border:1px solid var(--line);border-radius:18px;padding:14px 16px;margin:16px 0 0}
.quick-med:active{transform:translateY(1px)}
.qm-ic{flex:none;width:48px;height:48px;border-radius:15px;display:grid;place-items:center;background:radial-gradient(circle at 50% 34%,rgba(245,201,119,.22),transparent 72%);box-shadow:inset 0 0 0 1px rgba(245,201,119,.28)}
.qm-ic .i{width:27px;height:27px;color:var(--gold);filter:drop-shadow(0 0 6px rgba(245,201,119,.45))}
.qm-body{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px}
.qm-title{font-weight:800;font-size:16px}
.qm-sub{font-size:13px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.qm-sub .i.qm-snd{width:14px;height:14px;vertical-align:-2px;color:var(--gold);margin-right:1px}
.qm-go{flex:none;width:36px;height:36px;border-radius:50%;display:grid;place-items:center;background:#ffffff0d;color:var(--gold)}
.qm-go .i{width:16px;height:16px}
.sheet-ov{position:fixed;inset:0;z-index:60;background:rgba(5,4,10,.55);backdrop-filter:blur(3px);display:flex;align-items:flex-end;justify-content:center;opacity:0;transition:opacity .24s}
.sheet-ov.on{opacity:1}
.sheet{width:100%;max-width:560px;background:linear-gradient(180deg,#18131f,#120d18);border:1px solid var(--line);border-bottom:0;border-radius:22px 22px 0 0;padding:10px 18px calc(24px + env(safe-area-inset-bottom));transform:translateY(100%);transition:transform .28s cubic-bezier(.2,.85,.25,1);box-shadow:0 -24px 70px -24px #000}
.sheet-ov.on .sheet{transform:translateY(0)}
.sheet-grip{width:40px;height:4px;border-radius:2px;background:#ffffff26;margin:2px auto 14px}
.sheet-h{font-size:18px;margin:0 2px 16px;font-weight:800}
.sheet-lbl{display:flex;align-items:center;gap:7px;font-size:11px;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);margin:0 2px 9px}
.sheet-lbl .i{width:15px;height:15px;color:var(--gold)}
@media (prefers-reduced-motion:reduce){.sheet,.sheet-ov{transition:none}}
.stat{text-align:center}.stat .n{font-size:26px;font-weight:800}.stat .l{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
.bar{height:9px;border-radius:999px;background:#241d3a;overflow:hidden}
.bar>i{display:block;height:100%;background:linear-gradient(90deg,#e0953a,var(--gold));box-shadow:0 0 12px -2px rgba(245,201,119,.65)}
.home-hero{display:flex;flex-direction:column;gap:12px;position:relative;overflow:hidden}
.home-hero:before{content:"";position:absolute;inset:0;pointer-events:none;opacity:.6;
  background:linear-gradient(135deg,color-mix(in srgb,var(--lc) 30%,transparent),color-mix(in srgb,var(--lc2,var(--lc)) 22%,transparent) 55%,transparent 78%)}
.orb-hero{display:flex;flex-direction:column;align-items:center;gap:2px;position:relative;z-index:1;padding:2px 0 6px}
.orb-wrap{width:168px;height:168px;position:relative;margin-bottom:-10px;filter:drop-shadow(0 0 20px color-mix(in srgb,var(--lc) 42%,transparent))}
.lumorb{display:block;animation:orbpulse 5.5s ease-in-out infinite}
.lumorb-rays{transform-origin:80px 80px;animation:orbspin 70s linear infinite}
@keyframes orbspin{to{transform:rotate(360deg)}}
@keyframes orbpulse{0%,100%{opacity:.9}50%{opacity:1}}
.orb-lv{font-weight:800;font-size:17px;letter-spacing:.01em;margin-top:2px}
.orb-sub{font-size:12px}
.orb-stage{position:relative;width:272px;height:272px;max-width:82vw;max-height:82vw;margin:-6px 0 -12px;touch-action:none;cursor:grab;-webkit-tap-highlight-color:transparent}
.orb-stage:active{cursor:grabbing}
.orb-stage canvas,.orb-stage>svg,.orb-stage .orb-fallback{position:absolute;inset:0;width:100%;height:100%}
.orb-fallback{display:none;border-radius:50%}
.journal-cta{width:100%;display:flex;align-items:center;justify-content:center;gap:11px;margin:22px 0 6px;
  background:linear-gradient(135deg,#33250f 0%,#211607 55%,#140d06 100%);color:var(--gold);
  border:1px solid rgba(245,201,119,.52);border-radius:16px;padding:16px 18px;cursor:pointer;
  box-shadow:0 0 16px rgba(245,201,119,.22),inset 0 0 16px rgba(245,201,119,.06);animation:ctaglow 3.6s ease-in-out infinite}
.journal-cta .jc-row{display:flex;align-items:center;justify-content:center;gap:9px}
.journal-cta .jc-txt{font-family:var(--serif);font-style:italic;font-weight:600;font-size:17px;letter-spacing:.01em;
  background:linear-gradient(180deg,#fff0cf 0%,#f3d79a 45%,#e0ad52 100%);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;color:transparent;
  text-shadow:0 1px 10px rgba(245,201,119,.18)}
.journal-cta>.jbook,.journal-cta>.jc-txt,.journal-cta>.i{position:relative;z-index:1}
.journal-cta .jbook{width:40px;height:40px;filter:drop-shadow(0 0 8px rgba(245,201,119,.55))}
.journal-cta .i{width:26px;height:26px;color:var(--gold);transform:rotate(45deg);filter:drop-shadow(0 0 7px rgba(245,201,119,.6));animation:sealpulse 3.6s ease-in-out infinite}
.journal-cta:active{transform:translateY(1px)}
@keyframes sealpulse{0%,100%{filter:drop-shadow(0 0 5px rgba(245,201,119,.4))}50%{filter:drop-shadow(0 0 12px rgba(245,201,119,.72))}}
@keyframes ctaglow{0%,100%{border-color:rgba(245,201,119,.42);box-shadow:0 0 13px rgba(245,201,119,.18),inset 0 0 12px rgba(245,201,119,.04)}50%{border-color:rgba(245,201,119,.72);box-shadow:0 0 26px rgba(245,201,119,.38),inset 0 0 16px rgba(245,201,119,.07)}}
@media (prefers-reduced-motion:reduce){.journal-cta,.journal-cta .i{animation:none}}
.spinner{display:inline-block;width:1.3em;height:1.3em;vertical-align:-0.3em;line-height:0}
.spinner svg{display:block;width:100%;height:100%}
.center .spinner{display:block;width:60px;height:60px;margin:2px auto 10px;vertical-align:baseline}
.boot-load{min-height:100vh;display:flex;align-items:center;justify-content:center}
.boot-load .spinner{display:block;width:200px;height:200px;vertical-align:baseline}
@media (prefers-reduced-motion:reduce){.lumorb,.lumorb-rays{animation:none}}
.hh-top{display:flex;align-items:center;justify-content:space-between;gap:10px;position:relative;z-index:1}
.hh-league{display:flex;align-items:center;gap:11px}
.hh-badge{width:44px;height:44px;border-radius:50%;flex:none;display:grid;place-items:center;
  background:radial-gradient(circle at 32% 28%,color-mix(in srgb,var(--lc) 60%,transparent),color-mix(in srgb,var(--lc2,var(--lc)) 32%,transparent) 62%,transparent 82%);
  filter:drop-shadow(0 0 11px color-mix(in srgb,var(--lc) 52%,transparent))}
.hh-badge .i{width:25px;height:25px}
.hh-lg-name{font-weight:800;font-size:15px}
.hh-streak{display:flex;align-items:center;gap:4px;font-size:12px;color:var(--muted);flex:none}
.hh-streak b{color:var(--text);font-size:18px;margin-left:1px}.hh-streak .i{width:19px;height:19px}
.hh-stats{display:flex;gap:8px;position:relative;z-index:1}
.hh-stat{flex:1;background:#ffffff08;border:1px solid #ffffff10;border-radius:12px;padding:9px 6px;text-align:center}
.hh-stat span{display:block;font-weight:800;font-size:16px}
.hh-stat label{display:block;font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-top:2px}
.hh-bar{position:relative;z-index:1}
.hh-live{position:relative;z-index:1;display:flex;align-items:center;gap:7px;font-size:13px;color:var(--muted);
  border-top:1px solid #ffffff10;margin-top:2px;padding-top:12px}
.hh-live b{color:var(--text)}
.live-globe{width:18px;height:18px;flex:none;color:var(--purple);filter:drop-shadow(0 0 5px var(--purple));animation:liveglow 2.4s ease-in-out infinite}
@keyframes liveglow{0%,100%{filter:drop-shadow(0 0 3px var(--purple));opacity:.82}50%{filter:drop-shadow(0 0 10px var(--purple));opacity:1}}
@media (prefers-reduced-motion:reduce){.live-globe{animation:none}}
/* bottom nav */
nav{position:fixed;left:0;right:0;bottom:0;z-index:5;display:flex;justify-content:center;
  background:linear-gradient(0deg,#0b0a12 60%,transparent);padding:8px 10px calc(10px + env(safe-area-inset-bottom))}
nav .inner{display:flex;gap:4px;background:#14111f;border:1px solid var(--line);border-radius:20px;padding:5px;max-width:560px;width:100%}
nav button{flex:1;min-width:0;background:transparent;border:0;color:var(--muted);font-size:10px;font-weight:600;padding:7px 1px;border-radius:14px;cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:3px}
nav .inner{gap:2px}
nav button .ic{font-size:19px}
nav button.on{color:var(--text);background:#211a37}
/* meditate / breathing */
.orb-wrap{position:relative;height:300px;display:grid;place-items:center;margin:8px 0}
.orb{width:180px;height:180px;border-radius:50%;
  background:radial-gradient(circle at 50% 40%, #f7d99a, #c084fc 55%, #6d28d9 100%);
  box-shadow:0 0 70px 10px #a855f788, 0 0 140px 30px #7c3aed44;
  display:grid;place-items:center;animation:breathe 10s ease-in-out infinite}
.orb .t{font-size:34px;font-weight:800;color:#1a0b2e;text-shadow:0 1px 0 #ffffff55}
@keyframes breathe{0%,100%{transform:scale(.72)}45%,55%{transform:scale(1.08)}}
.ring{position:absolute;width:260px;height:260px;border-radius:50%;border:1px solid #a855f755;animation:breathe 10s ease-in-out infinite}
.breath-label{position:absolute;bottom:6px;color:var(--muted);font-size:14px;letter-spacing:.12em;text-transform:uppercase}
/* lesson-player orb — accent-tinted, with slow rotating sun-rays like the home orb */
.lorb-wrap{--a:#a855f7}
.lorb-wrap:before{content:"";position:absolute;width:300px;height:300px;border-radius:50%;pointer-events:none;
  background:repeating-conic-gradient(from 0deg,color-mix(in srgb,var(--a) 22%,transparent) 0deg 2.4deg,transparent 2.4deg 15deg);
  -webkit-mask:radial-gradient(circle,transparent 44%,#000 55%,transparent 80%);mask:radial-gradient(circle,transparent 44%,#000 55%,transparent 80%);
  animation:orbspin 70s linear infinite;opacity:.55}
@keyframes orbspin{to{transform:rotate(360deg)}}
.lorb-wrap .orb{background:radial-gradient(circle at 50% 38%,#fff6e0,var(--a) 52%,color-mix(in srgb,var(--a) 58%,#140b24) 100%);
  box-shadow:0 0 72px 10px color-mix(in srgb,var(--a) 55%,transparent),0 0 150px 34px color-mix(in srgb,var(--a) 26%,transparent)}
.lorb-wrap .ring{border-color:color-mix(in srgb,var(--a) 48%,transparent)}
.lorb-wrap .orb .t{color:color-mix(in srgb,var(--a) 62%,#120b20)}
.lesson-teach.lead{font-style:italic;color:#d9cff2}
.lesson-teach.resting{color:var(--muted);font-size:13px;letter-spacing:.14em;text-transform:uppercase;font-family:inherit;opacity:.85;transition:opacity .6s}
/* map */
#map{height:56vh;min-height:360px;border-radius:18px;overflow:hidden;border:1px solid var(--line)}
.leaflet-container{background:#0a0912}
/* custom glowing map markers */
.mkr-wrap{background:none!important;border:none!important}
.mkr{width:100%;height:100%;border-radius:50%;display:flex;align-items:center;justify-content:center;
  background:radial-gradient(circle at 50% 40%,#241a3e,#140f24);border:1.6px solid var(--c);color:var(--c);
  box-shadow:0 0 8px var(--c),0 0 16px -3px var(--c);transition:transform .15s}
.mkr:hover{transform:scale(1.15);z-index:999}
.mkr .mkri{width:15px;height:15px;filter:drop-shadow(0 0 3px var(--c))}
.mkr.me{animation:mkrpulse 2.2s ease-in-out infinite}
.mkr.me .mkri{width:18px;height:18px}
@keyframes mkrpulse{0%,100%{box-shadow:0 0 8px var(--c),0 0 14px -4px var(--c)}50%{box-shadow:0 0 16px var(--c),0 0 30px var(--c)}}
.dotleg{width:13px;height:13px;border-radius:50%;background:radial-gradient(circle,#241a3e,#140f24);border:1.5px solid var(--c);box-shadow:0 0 7px var(--c);display:inline-block}
/* journey timelapse */
.jny-play{position:absolute;z-index:1000;left:50%;bottom:14px;transform:translateX(-50%);display:inline-flex;align-items:center;gap:7px;
  background:linear-gradient(135deg,#f5c977,#e0953a);color:#2a1a05;border:0;border-radius:999px;padding:11px 18px;font-weight:700;font-size:14px;cursor:pointer;box-shadow:0 6px 22px -6px #000}
.jny-play .i{width:16px;height:16px}
.jny-ov{position:absolute;z-index:1000;left:12px;top:12px;min-width:148px;background:#12101eef;border:1px solid var(--line);border-radius:14px;padding:10px 12px;opacity:0;transform:translateY(-6px);transition:.25s;pointer-events:none;backdrop-filter:blur(4px)}
.jny-ov.show{opacity:1;transform:none}
.jny-count{font-size:22px;font-weight:800;color:var(--gold);line-height:1}
.jny-count span{font-size:13px;color:var(--muted);font-weight:600}
.jny-meta{margin-top:4px;display:flex;flex-direction:column}
.jny-meta b{font-size:14px}.jny-meta span{font-size:11px;color:var(--muted)}
.jny-bar{height:5px;border-radius:5px;background:#241d3a;margin-top:7px;overflow:hidden}
.jny-bar>i{display:block;height:100%;background:linear-gradient(90deg,var(--gold),var(--pink));box-shadow:0 0 9px -2px var(--pink);transition:width .4s}
.jny-done{font-size:13px;color:var(--gold);display:flex;align-items:center;gap:6px;font-weight:700}
.jny-drop{animation:jnydrop .5s cubic-bezier(.2,1.3,.3,1)}
@keyframes jnydrop{0%{transform:scale(0);opacity:0}60%{transform:scale(1.3)}100%{transform:scale(1);opacity:1}}
.leaflet-pane path.jny-path{filter:drop-shadow(0 0 4px #f5c977aa)}
.leaflet-pane path.jny-seg{opacity:0;transition:opacity .9s ease;filter:drop-shadow(0 0 4px #f5c977aa)}
/* journey finale */
.jny-finale{position:fixed;inset:0;z-index:70;display:grid;place-items:center;padding:24px;overflow:auto;
  background:radial-gradient(1100px 760px at 50% 38%, rgba(18,13,34,.30), rgba(7,6,14,.74) 76%);
  -webkit-backdrop-filter:blur(1.5px) brightness(.85);backdrop-filter:blur(1.5px) brightness(.85);
  opacity:0;transition:opacity .6s}
.jny-finale.show{opacity:1}
.finale-card{max-width:400px;width:100%;text-align:center;position:relative;z-index:2;padding:26px 20px 22px;border-radius:26px;
  background:radial-gradient(120% 90% at 50% 0%, rgba(40,28,66,.66), rgba(12,9,22,.74));
  border:1px solid #ffffff1a;box-shadow:0 24px 70px -22px #000, 0 0 0 1px #ffffff08 inset;
  -webkit-backdrop-filter:blur(9px) saturate(1.1);backdrop-filter:blur(9px) saturate(1.1);
  transform:translateY(18px) scale(.97);opacity:0;transition:transform .6s cubic-bezier(.2,.9,.25,1.12),opacity .55s}
.jny-finale.show .finale-card{transform:none;opacity:1}
.finale-mark{color:var(--gold);display:flex;justify-content:center;filter:drop-shadow(0 0 26px var(--gold));animation:markpulse 4s ease-in-out infinite}
.finale-mark .i{width:56px;height:56px}
.finale-sub{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.2em;margin-top:12px}
.finale-h{font-size:34px;font-weight:800;letter-spacing:-.02em;margin:6px 0 6px;line-height:1.12;
  background:linear-gradient(120deg,#ffe9b8,#f5c977 40%,#ec4899);-webkit-background-clip:text;background-clip:text;color:transparent}
.finale-poem{color:#cbbfe6;font-family:var(--serif);font-style:italic;font-size:15px;margin:2px 16px 18px;line-height:1.5}
.finale-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:14px}
.fstat{background:#160f26;border:1px solid var(--line);border-radius:16px;padding:14px 4px}
.fsn{font-size:27px;font-weight:800;color:var(--gold);line-height:1}
.fsl{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-top:6px;line-height:1.2}
.finale-lines{text-align:left;display:flex;flex-direction:column;gap:8px;margin-bottom:18px}
.fline{display:flex;align-items:center;gap:12px;background:#120e20;border:1px solid var(--line);border-radius:14px;padding:11px 13px}
.fli{display:flex}.fli .i{width:20px;height:20px}
.fline>div{display:flex;flex-direction:column}
.fline b{font-size:14px}.fline>div span{font-size:12px;color:var(--muted)}
.fspk{position:absolute;inset:0;pointer-events:none;overflow:hidden;z-index:1}
.fspark{position:absolute;bottom:-12px;width:4px;height:4px;border-radius:50%;background:#f5c977;box-shadow:0 0 8px #f5c977;opacity:0;animation:frise linear infinite}
@keyframes frise{0%{transform:translateY(0) scale(.5);opacity:0}12%{opacity:1}100%{transform:translateY(-108vh) scale(1);opacity:0}}
/* journal sealed celebration */
.seal-finale{background:radial-gradient(1000px 720px at 50% 18%,#221839,#0a0912 78%)!important;
  -webkit-backdrop-filter:none!important;backdrop-filter:none!important}
.seal-stamp{display:flex;justify-content:center;color:var(--gold);margin-bottom:4px}
.seal-stamp .i{width:68px;height:68px;filter:drop-shadow(0 0 22px #f5c977cc);animation:stampin .6s cubic-bezier(.2,1.5,.3,1) both}
@keyframes stampin{0%{transform:scale(2.6) rotate(-14deg);opacity:0}55%{transform:scale(.88) rotate(4deg);opacity:1}100%{transform:scale(1) rotate(0)}}
/* dark popups */
.leaflet-popup-content-wrapper{background:#181527;color:var(--text);border:1px solid var(--line);border-radius:14px;box-shadow:0 10px 40px -10px #000}
.leaflet-popup-tip{background:#181527;border:1px solid var(--line)}
.leaflet-popup-content{margin:11px 14px;font-family:inherit}
.pop-h{display:flex;align-items:center;gap:7px;font-size:15px}
.pop-ic .i{width:17px;height:17px;filter:drop-shadow(0 0 4px currentColor)}
.pop-you{font-size:10px;background:#3a2d14;color:var(--gold);padding:1px 7px;border-radius:999px;font-weight:700}
.pop-b{margin-top:4px;font-size:13px;color:#cbb5e8}
.pop-m{margin-top:2px;font-size:11px;color:var(--muted)}
.pop-img{display:block;width:210px;max-width:60vw;height:120px;object-fit:cover;border-radius:10px;margin:-2px 0 8px;border:1px solid var(--line)}
/* photo markers on the map */
.mkr-photo{width:100%;height:100%;border-radius:50%;overflow:hidden;border:2px solid var(--c);
  box-shadow:0 0 8px var(--c),0 0 16px -4px var(--c);background:#140f24;transition:transform .15s}
.mkr-photo:hover{transform:scale(1.18);z-index:999}
.mkr-photo img{width:100%;height:100%;object-fit:cover;display:block}
.mkr-photo.me{animation:mkrpulse 2.2s ease-in-out infinite}
/* map Photos / Icons toggle */
.map-view{display:flex;gap:8px;justify-content:center;margin-top:10px}
.map-vbtn{display:inline-flex;align-items:center;gap:6px;background:#160f26;border:1px solid var(--line);color:var(--muted);
  border-radius:999px;padding:7px 14px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit}
.map-vbtn .i{width:15px;height:15px}
.map-vbtn.on{border-color:var(--gold);color:var(--gold);background:#1e1630}
/* spot-photo capture in session complete */
.spot-cap{margin:4px 0 2px}
.spot-add{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;background:#160f26;border:1px dashed var(--line);
  color:var(--muted);border-radius:12px;padding:12px;font-size:14px;font-weight:600;cursor:pointer;font-family:inherit}
.spot-add .i{width:18px;height:18px}
/* location "holder" preview — an aerial thumbnail of where they sat */
.spot-hold{position:relative;margin-bottom:10px;border-radius:12px;overflow:hidden;border:1px solid var(--line);
  background:#0f0b1c linear-gradient(135deg,#161030,#0d0a18)}
.spot-hold img{display:block;width:100%;height:150px;object-fit:cover;opacity:0;transition:opacity .5s ease}
.spot-hold img.on{opacity:.92}
.spot-hold .pin{position:absolute;left:50%;top:50%;transform:translate(-50%,-100%);color:var(--gold);
  filter:drop-shadow(0 2px 6px #000) drop-shadow(0 0 7px var(--gold))}
.spot-hold .pin .i{width:30px;height:30px}
.spot-hold .spot-glow{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:38px;height:38px;z-index:2}
.spot-hold .cap{position:absolute;left:0;right:0;bottom:0;padding:16px 12px 8px;font-size:12px;color:#f3ead6;
  display:flex;align-items:center;gap:5px;background:linear-gradient(transparent,#000000cc)}
.spot-hold .cap .i{width:14px;height:14px}
.spot-hold.load::after{content:"";position:absolute;inset:0;background:
  linear-gradient(90deg,transparent,#ffffff14,transparent) 0/40% 100% no-repeat;animation:shimmer 1.3s infinite}
@keyframes shimmer{to{background-position:200% 0}}
.spot-prev{position:relative}
.spot-prev img{display:block;width:100%;max-height:220px;object-fit:cover;border-radius:12px;border:1px solid var(--line)}
.spot-lbl{display:flex;align-items:center;gap:5px;font-size:12px;color:var(--muted);margin-bottom:6px}
.spot-lbl .i{width:14px;height:14px}
/* daily Morning Atlas challenge card */
.chal-card{position:relative;overflow:hidden}
.chal-head{display:flex;align-items:center;justify-content:space-between;gap:10px}
.chal-title{display:flex;align-items:center;gap:8px;font-weight:700;font-size:15px}
.chal-title .i{width:18px;height:18px;color:var(--gold)}
.chal-streak{display:inline-flex;align-items:center;gap:4px;font-size:13px;color:var(--gold)}
.chal-streak .i{width:16px;height:16px}
.chal-blurb{color:var(--muted);font-size:12.5px;margin:6px 0 13px;line-height:1.45}
.chal-items{display:flex;flex-direction:column;gap:10px}
.chal-item{display:flex;align-items:center;gap:11px;font-size:14px}
.chal-box{width:22px;height:22px;flex:none;border-radius:7px;border:1.5px solid var(--line);display:grid;place-items:center;color:transparent;transition:.25s}
.chal-box .i{width:14px;height:14px}
.chal-item.on .chal-box{background:linear-gradient(135deg,var(--gold),var(--pink));border-color:transparent;color:#1a1326}
.chal-lbl{color:var(--muted)}
.chal-item.on .chal-lbl{color:var(--text)}
.chal-done-banner{margin-top:13px;display:flex;align-items:center;gap:7px;justify-content:center;font-size:13px;font-weight:600;color:var(--gold);background:#1e1630;border:1px solid var(--gold);border-radius:12px;padding:9px}
.chal-done-banner .i{width:15px;height:15px}
.chal-bonus{font-size:11.5px;color:var(--muted);margin-top:12px;text-align:center;line-height:1.4}
.chal-bonus .i{width:13px;height:13px;vertical-align:-2px}
/* notification settings */
.nrow{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:9px 0;border-top:1px solid var(--line)}
.nrow .nl{font-size:14px}
.nsel{background:#1a1330;border:1px solid var(--line);color:var(--text);border-radius:9px;padding:6px 8px;font-size:13px;font-family:inherit}
.switch{position:relative;display:inline-block;width:46px;height:27px;flex:none}
.switch input{opacity:0;width:0;height:0}
.switch .sl{position:absolute;inset:0;background:#2a2442;border-radius:999px;transition:.2s;cursor:pointer}
.switch .sl:before{content:"";position:absolute;width:21px;height:21px;left:3px;top:3px;background:#fff;border-radius:50%;transition:.2s}
.switch input:checked+.sl{background:linear-gradient(135deg,#e0953a,var(--gold))}
.switch input:checked+.sl:before{transform:translateX(19px)}
.chal-streak-u{font-size:11px;color:var(--muted);margin-left:2px}
/* Atlas — a map of your whole practice (progress across every facet) */
.atlas-card{position:relative;overflow:hidden;border:1px solid color-mix(in srgb,var(--gold) 26%,var(--line));
  background:linear-gradient(165deg,color-mix(in srgb,var(--gold) 8%,#15111f),#110d1b 72%)}
.atlas-card:before{content:"";position:absolute;inset:0;pointer-events:none;opacity:.5;
  background:radial-gradient(120% 85% at 90% -12%,color-mix(in srgb,var(--gold) 22%,transparent),transparent 55%)}
.atlas-card>*{position:relative;z-index:1}
.atlas-head{display:flex;align-items:center;justify-content:space-between;gap:10px}
.atlas-eyebrow{display:inline-flex;align-items:center;gap:7px;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.14em;color:var(--gold)}
.atlas-eyebrow .i{width:19px;height:19px}
.atlas-streak{display:inline-flex;align-items:center;gap:5px;font-size:12px;font-weight:700;color:var(--gold)}
.atlas-streak .i{width:15px;height:15px}
.atlas-tag{font-family:var(--serif);font-style:italic;font-size:13.5px;color:var(--muted);margin:6px 0 8px}
.atlas-facets{display:flex;flex-direction:column}
.atlas-facet{display:flex;align-items:center;gap:13px;padding:13px 0;border-top:1px solid #ffffff0e}
.atlas-fic{flex:none;width:42px;height:42px;border-radius:50%;display:grid;place-items:center;color:var(--fc,var(--gold));
  background:radial-gradient(circle at 34% 30%,color-mix(in srgb,var(--fc,var(--gold)) 46%,transparent),color-mix(in srgb,var(--fc2,var(--fc,var(--gold))) 20%,transparent) 62%,#160f2b 92%);
  border:1px solid color-mix(in srgb,var(--fc,var(--gold)) 30%,#ffffff12);
  box-shadow:0 0 14px -5px color-mix(in srgb,var(--fc,var(--gold)) 75%,transparent)}
.atlas-fic .i{width:20px;height:20px}
.atlas-fmain{flex:1;min-width:0}
.atlas-ftop{display:flex;align-items:baseline;justify-content:space-between;gap:10px}
.atlas-fname{font-weight:700;font-size:14px;color:#f1ecff}
.atlas-fval{flex:none;font-family:var(--serif);font-size:21px;font-weight:600;color:#f3eeff;line-height:1;white-space:nowrap}
.atlas-fval small{font-family:-apple-system,system-ui,sans-serif;font-size:10.5px;font-weight:600;color:var(--muted);margin-left:3px}
.atlas-fval.badge{color:var(--fc)}
.atlas-fbar{height:5px;border-radius:999px;background:#ffffff10;overflow:hidden;margin:8px 0 5px}
.atlas-fbar>i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,var(--fc),var(--fc2,var(--fc)));box-shadow:0 0 8px -2px var(--fc);transition:width .5s ease}
.atlas-fsub{font-size:11px;color:var(--muted);line-height:1.3}
.atlas-foot{margin-top:4px;display:flex;align-items:center;justify-content:center;gap:7px;font-size:12.5px;font-weight:600;color:var(--gold);cursor:pointer;border-top:1px solid #ffffff10;padding-top:14px}
.atlas-foot .i{width:14px;height:14px}
.atlas-foot .rt{transform:rotate(90deg)}
/* daily horoscope card */
/* zodiac symbols render as monochrome text, never emoji */
.zsym{font-variant-emoji:text}
.horo-card{position:relative;overflow:hidden;border:1px solid #2a2048;
  background:linear-gradient(165deg,#191130,#120d22 74%)}
.horo-card:before{content:"";position:absolute;inset:0;pointer-events:none;opacity:.55;
  background:radial-gradient(120% 85% at 92% -12%,#3a2866,transparent 55%)}
.horo-card>*{position:relative;z-index:1}
.horo-eyebrow{display:flex;align-items:center;justify-content:space-between;gap:10px;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.14em;color:var(--gold)}
.horo-eyebrow>span:first-child{display:flex;align-items:center;gap:7px}
.horo-constell{flex:none;line-height:0;filter:drop-shadow(0 0 5px rgba(245,201,119,.5))}
.horo-constell svg{display:block}
.horo-eyebrow .i{width:13px;height:13px}
.horo-intro{font-size:12.5px;line-height:1.5;margin:8px 0 14px;max-width:40ch}
.horo-head{display:flex;align-items:center;gap:14px;margin:13px 0}
.horo-medallion{flex:none;width:58px;height:58px;border-radius:50%;display:grid;place-items:center;
  background:radial-gradient(circle at 50% 34%,#2d2256,#160f2b);border:1px solid #ffffff1c;
  box-shadow:0 0 0 4px #ffffff07,0 10px 26px -14px #000}
.horo-sym{font-size:29px;line-height:1;color:var(--gold);filter:drop-shadow(0 0 9px #f5c97788);font-variant-emoji:text}
.horo-medallion .i{width:26px;height:26px;color:var(--gold)}
.horo-name{font-family:var(--serif);font-size:22px;font-weight:600;color:#f1ecff;line-height:1.12}
.horo-sub{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;color:var(--muted);margin-top:5px}
.horo-sub .i{width:13px;height:13px;flex:none}
.horo-text{font-family:var(--serif);font-size:16px;line-height:1.75;color:#e9e2f7;margin:0;
  padding-top:15px;border-top:1px solid #ffffff12}
.horo-cta{display:flex;flex-direction:column;align-items:center;gap:11px;margin-top:18px}
.rndbtn{flex:none;width:52px;height:52px;border-radius:50%;cursor:pointer;display:grid;place-items:center;
  border:1px solid color-mix(in srgb,var(--gold) 42%,var(--line));background:#ffffff08;color:var(--gold);transition:.15s}
.rndbtn:hover{background:color-mix(in srgb,var(--gold) 13%,transparent);box-shadow:0 0 18px -4px var(--gold)}
.rndbtn .i{width:21px;height:21px}
.rndbtn.playing{animation:rndpulse 1.25s ease-in-out infinite}
@keyframes rndpulse{0%,100%{box-shadow:0 0 0 0 color-mix(in srgb,var(--gold) 42%,transparent)}50%{box-shadow:0 0 0 8px transparent}}
.horo-sit{background:none;border:0;padding:3px 4px;margin:0;color:var(--gold);font-weight:700;font-size:14px;cursor:pointer;
  font-family:inherit;display:inline-flex;align-items:center;gap:7px}
.horo-sit:hover{text-decoration:underline;text-underline-offset:3px}
.horo-sit .i{width:15px;height:15px}
.horo-signs{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:2px}
.horo-sign{display:flex;flex-direction:column;align-items:center;gap:7px;padding:14px 4px 11px;background:#17112e;border:1px solid var(--line);border-radius:16px;color:var(--text);cursor:pointer;font-family:inherit;transition:.15s}
.horo-sign:hover,.horo-sign:active{border-color:var(--gold);background:#201839;transform:translateY(-1px)}
.hs-med{width:40px;height:40px;border-radius:50%;display:grid;place-items:center;background:radial-gradient(circle at 50% 34%,#2d2256,#160f2b);border:1px solid #ffffff16}
.hs-glyph{font-size:21px;line-height:1;color:var(--gold);font-variant-emoji:text}
.hs-nm{font-size:12.5px;font-weight:600;color:var(--text)}
.hs-sub{font-size:10px;color:var(--muted);letter-spacing:.02em}
.horo-foot{margin-top:14px;font-size:11.5px;color:var(--muted);display:flex;align-items:center;justify-content:center;text-align:center;gap:6px;opacity:.85}
.horo-foot .i{width:13px;height:13px;flex:none}
.horo-foot.horo-addnatal{color:var(--gold);opacity:1;font-weight:600}
.spot-x{position:absolute;top:8px;right:8px;display:inline-flex;align-items:center;gap:5px;background:#000000b3;color:#fff;
  border:0;border-radius:999px;padding:6px 11px;font-size:12px;font-weight:600;cursor:pointer;font-family:inherit}
.spot-x .i{width:13px;height:13px}
.spot-shot{margin-top:14px;display:flex;flex-direction:column;align-items:center;gap:6px}
.spot-shot img{width:100%;max-width:260px;max-height:200px;object-fit:cover;border-radius:14px;border:1px solid var(--line)}
/* spot posts in the community feed */
.spot-post{padding:0;overflow:hidden}
.spot-img{display:block;width:100%;max-height:260px;object-fit:cover;border-bottom:1px solid var(--line)}
.spot-meta{padding:12px 14px}
.spot-where{font-size:12px;color:var(--muted);display:flex;align-items:center;gap:5px;margin-top:4px}
.spot-where .i{width:14px;height:14px}
.toast{position:fixed;left:50%;top:calc(env(safe-area-inset-top, 0px) + 14px);transform:translateX(-50%);z-index:50;background:#1c1630;border:1px solid var(--purple);
  padding:12px 16px;border-radius:14px;box-shadow:0 10px 40px -10px #000;max-width:92%;text-align:center;font-weight:600}
.hidden{display:none!important}
.center{text-align:center}
.lb-row{display:flex;align-items:center;gap:12px;padding:10px 4px;border-bottom:1px solid var(--line)}
.lb-row .rk{min-width:34px;display:flex;align-items:center;justify-content:center;gap:1px;color:var(--muted);font-weight:800;text-align:center}
.lb-row .rk.g{color:var(--gold)}
.lb-row .rk .medal{width:20px;height:20px}
.lb-row .nm{flex:1;font-weight:600}.lb-row .vl{font-weight:800;color:var(--gold)}
.lb-row.you{background:#1c1636;border-radius:12px;border-bottom-color:transparent}
.league-hero{position:relative;overflow:hidden}
.league-hero:before{content:"";position:absolute;inset:0;pointer-events:none;opacity:.5;
  background:linear-gradient(135deg,color-mix(in srgb,var(--lc) 26%,transparent),color-mix(in srgb,var(--lc2,var(--lc)) 20%,transparent) 55%,transparent 80%)}
.league-hero>*{position:relative;z-index:1}
.lg-bar{background:#ffffff14}
.lg-bar>i{background:linear-gradient(90deg,var(--lc),var(--lc2,var(--lc)))!important;box-shadow:0 0 12px -2px color-mix(in srgb,var(--lc2,var(--lc)) 70%,transparent)}
.league-badge{margin:2px auto 8px;width:64px;height:64px;border-radius:50%;display:grid;place-items:center;
  background:radial-gradient(circle at 32% 28%,color-mix(in srgb,var(--lc) 62%,transparent),color-mix(in srgb,var(--lc2,var(--lc)) 34%,transparent) 60%,transparent 80%);
  filter:drop-shadow(0 0 16px color-mix(in srgb,var(--lc) 55%,transparent))}
.league-badge .i{width:34px;height:34px}
.lemblem{display:block;margin:0 auto;filter:drop-shadow(0 6px 20px rgba(0,0,0,.45))}
.lemblem .lem-ring{transform-origin:60px 60px;animation:lemSpin 26s linear infinite}
.lemblem .lem-motes{transform-origin:60px 60px;animation:lemSpin 40s linear infinite reverse}
.lemblem .lem-glyph .i{width:26px;height:26px}
@keyframes lemSpin{to{transform:rotate(360deg)}}
@media (prefers-reduced-motion:reduce){.lemblem .lem-ring,.lemblem .lem-motes{animation:none}}
.ach{display:flex;gap:12px;align-items:center;padding:12px;border:1px solid var(--line);border-radius:14px;margin:8px 0}
.ach .e{color:var(--muted);opacity:.5;display:flex}
.ach .e .i{width:26px;height:26px}
.ach.on .e{color:var(--gold);opacity:1}
.ach.on{border-color:#4b3a6e;background:#160f26}
.seg{display:flex;background:#13101f;border:1px solid var(--line);border-radius:12px;padding:3px;gap:3px}
.seg button{flex:1;background:transparent;border:0;color:var(--muted);padding:8px;border-radius:9px;font-weight:600;cursor:pointer;font-size:13px}
.seg button.on{background:#271f42;color:var(--text)}
.ctoggle{display:flex;justify-content:center;margin:20px 2px calc(96px + env(safe-area-inset-bottom))}
.ctoggle .seg{max-width:560px;width:100%;background:#15111f}
.ctoggle .seg button{display:flex;align-items:center;justify-content:center;gap:6px}
.ctoggle .seg button .i{width:15px;height:15px}
.cbody-art{padding-top:4px}
.cbody-altar{padding-top:26px}
.sms-consent{display:flex;gap:9px;align-items:flex-start;font-size:12px;color:var(--muted);font-weight:400;margin-top:12px;cursor:pointer;line-height:1.45}
.sms-consent input{width:17px;height:17px;margin:1px 0 0;flex:none;accent-color:var(--gold)}
.feed-item{border-left:2px solid var(--purple);padding:4px 0 4px 12px;margin:12px 0}
.feed-item .who{font-size:12px;color:var(--muted)}
a{color:var(--purple)}
/* ---- journal: a letter to yourself ---- */
.letter{position:relative;border-radius:20px;padding:22px 20px 18px;overflow:hidden;
  background:linear-gradient(175deg,#1c1830,#17132690 70%,#141022);
  border:1px solid #2e2747;box-shadow:0 18px 50px -24px #000, 0 0 0 1px #ffffff05 inset}
.letter:before{content:"";position:absolute;inset:0;pointer-events:none;opacity:.5;
  background:radial-gradient(130% 70% at 50% -10%, #c084fc22, transparent 55%)}
.letter-head{display:flex;align-items:center;justify-content:space-between;position:relative;z-index:1;
  font-family:var(--serif);font-style:italic;color:var(--muted);font-size:14px;margin-bottom:4px}
.letter-seal .i{width:18px;height:18px;color:var(--gold);filter:drop-shadow(0 0 6px #f5c97799)}
.letter-prompt{position:relative;z-index:1;display:flex;flex-direction:column;gap:8px;margin:10px 0 12px;
  padding-bottom:14px;border-bottom:1px solid #ffffff10}
.lp-q{font-family:var(--serif);font-style:italic;font-size:18px;line-height:1.45;color:#e9e3f7}
.lp-shuffle{align-self:flex-start;background:transparent;border:0;color:var(--purple);font-size:12px;font-weight:600;
  cursor:pointer;display:inline-flex;align-items:center;gap:5px;padding:0}
.lp-shuffle .i{width:13px;height:13px}
.letter-body{width:100%;background:transparent;border:0;outline:0;resize:none;color:#efe9f8;
  font-family:var(--serif);font-size:17px;line-height:1.8;padding:2px;min-height:150px;
  background-image:linear-gradient(transparent 1.78em,#ffffff0d 1.8em);background-size:100% 1.8em;background-attachment:local}
.letter-body::placeholder{color:#6f6790;font-style:italic}
.letter-interim{position:relative;z-index:1;color:var(--purple);font-family:var(--serif);font-style:italic;font-size:15px;min-height:10px;margin-top:4px}
.letter-foot{display:flex;align-items:center;gap:12px;margin-top:14px;position:relative;z-index:1}
.letter-share{flex:1;display:flex;align-items:center;gap:8px;margin:0;font-size:13px;color:var(--muted)}
.letter-share input{margin:0}
.mic{position:relative;width:48px;height:48px;flex:none;border-radius:50%;border:1px solid var(--line);
  background:#1b1530;color:var(--purple);display:grid;place-items:center;cursor:pointer;transition:.2s}
.mic .i{width:22px;height:22px;position:relative;z-index:2}
.mic:active{transform:scale(.94)}
.mic-ring{position:absolute;inset:-4px;border-radius:50%;border:2px solid var(--purple);opacity:0}
.mic.live{background:linear-gradient(135deg,#7c3aed,#ec4899);color:#fff;border-color:transparent;box-shadow:0 0 18px -2px var(--purple)}
.mic.live .mic-ring{opacity:1;animation:micpulse 1.4s ease-out infinite}
@keyframes micpulse{0%{transform:scale(1);opacity:.7}100%{transform:scale(1.6);opacity:0}}
.mic-hint{position:relative;z-index:1;color:var(--purple);font-size:12px;font-style:italic;min-height:14px;margin-top:9px;text-align:center}
.letter-seal-btn{position:relative;z-index:1;margin:16px auto 2px;width:auto;padding:13px 28px;display:flex;align-items:center;justify-content:center;gap:9px}
.letter-seal-btn .seal-ic{width:22px;height:22px}
.letter.mini{padding:16px 18px;margin-top:12px}
.letter-tag{display:inline-flex;align-items:center;gap:5px;font-style:normal;font-size:11px;color:var(--muted)}
.letter-tag .i{width:13px;height:13px}
.mini-q{font-family:var(--serif);font-style:italic;color:#c9bfe6;font-size:15px;margin:8px 0 8px}
.mini-body{font-family:var(--serif);font-size:15.5px;line-height:1.7;color:#e3ddf1;white-space:pre-wrap}
.mini-mood{font-family:var(--serif);font-style:italic;color:var(--muted);font-size:13px;margin-top:8px;text-align:right}
.mini-mod{display:flex;gap:8px;justify-content:flex-end;margin-top:10px}
.mini-modbtn{display:inline-flex;align-items:center;gap:4px;background:transparent;border:1px solid var(--line);
  color:var(--muted);border-radius:999px;padding:4px 11px;font-size:11.5px;cursor:pointer}
.mini-modbtn:hover{color:var(--text);border-color:var(--muted)}.mini-modbtn .i{width:12px;height:12px}
/* life os + speaker */
.lo-btn{margin-left:auto;display:inline-flex;align-items:center;gap:6px;background:#1a1330;border:1px solid #3a2d5e;color:var(--purple);border-radius:999px;padding:6px 12px;font-size:12px;font-weight:700;cursor:pointer}
.back-btn{flex:none;width:34px;height:34px;border-radius:50%;background:#1a1330;border:1px solid #3a2d5e;color:var(--purple);font-size:22px;line-height:1;font-weight:700;cursor:pointer;display:grid;place-items:center;padding:0 0 3px 0}
.back-btn:active{transform:scale(.94)}
.lo-btn .i{width:14px;height:14px}
/* ---- journal: three modes, weekly ring, pillar grid ---- */
.jweekbar{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:2px 2px 12px;flex-wrap:wrap}
.jwk-row{display:flex;gap:7px}
.jwk{display:inline-flex;align-items:center;gap:5px;font-size:11.5px;font-weight:600;color:var(--muted);
  background:#17132690;border:1px solid var(--line);border-radius:999px;padding:4px 10px}
.jwk.on{color:var(--gold);border-color:rgba(245,201,119,.4);background:rgba(245,201,119,.08)}
.jwk .i{width:12px;height:12px}
.jwk-o{width:8px;height:8px;border-radius:50%;border:1.5px solid #5b5280;display:inline-block}
.jwk-cap{font-size:11.5px;color:var(--muted);font-style:italic;font-family:var(--serif)}
/* journal hero — three journaling facets that glow when tended this week (mandala-inspired) */
.jhero{position:relative;overflow:hidden;border:1px solid #2e2747;border-radius:20px;padding:18px 16px 16px;margin:2px 2px 16px;text-align:center;
  background:linear-gradient(165deg,#1b1530,#120d1f 74%)}
.jhero:before{content:"";position:absolute;inset:0;pointer-events:none;opacity:.55;
  background:radial-gradient(120% 82% at 50% -12%,rgba(168,85,247,.22),rgba(56,189,248,.13) 42%,transparent 64%)}
.jhero>*{position:relative;z-index:1}
.jhero-eyebrow{display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.14em;color:var(--gold);margin-bottom:15px}
.jhero-eyebrow .i{width:13px;height:13px}
.jhero-facets{display:flex;justify-content:center;gap:clamp(18px,8vw,34px)}
.jfacet{display:flex;flex-direction:column;align-items:center;gap:8px;cursor:pointer;background:none;border:0;padding:0;font-family:inherit}
.jfacet:active{transform:scale(.96)}
.jfacet-med{width:58px;height:58px;border-radius:50%;display:grid;place-items:center;position:relative;color:var(--fc);transition:.2s;
  background:radial-gradient(circle at 34% 30%,color-mix(in srgb,var(--fc) 18%,#1a1330),#140e26);border:1px solid color-mix(in srgb,var(--fc) 22%,#ffffff12)}
.jfacet-med .i{width:25px;height:25px}
.jfacet.lit .jfacet-med{border-color:color-mix(in srgb,var(--fc) 50%,transparent);
  background:radial-gradient(circle at 34% 30%,color-mix(in srgb,var(--fc) 56%,transparent),color-mix(in srgb,var(--fc2,var(--fc)) 26%,transparent) 64%,#140e26);
  animation:jfpulse 4.2s ease-in-out infinite}
@keyframes jfpulse{0%,100%{box-shadow:0 0 15px -5px color-mix(in srgb,var(--fc) 70%,transparent)}50%{box-shadow:0 0 26px -3px color-mix(in srgb,var(--fc) 88%,transparent)}}
.jfacet-check{position:absolute;bottom:-2px;right:-2px;width:19px;height:19px;border-radius:50%;background:#0f2a20;border:1px solid #6ee7b7;display:grid;place-items:center;color:#6ee7b7}
.jfacet-check .i{width:11px;height:11px}
.jfacet-lbl{font-size:11.5px;font-weight:600;color:var(--muted)}
.jfacet.lit .jfacet-lbl{color:var(--fc)}
.jhero-cap{font-family:var(--serif);font-style:italic;font-size:13px;color:var(--muted);margin-top:16px}
.jmodes{display:flex;gap:7px;background:#13101f;border:1px solid var(--line);border-radius:14px;padding:4px;margin-bottom:6px}
.jmode{flex:1;display:flex;flex-direction:column;align-items:center;gap:3px;background:transparent;border:0;cursor:pointer;
  color:var(--muted);padding:9px 6px;border-radius:10px;font-size:12px;font-weight:700;transition:.18s}
.jmode .i{width:18px;height:18px}
.jmode.on{background:linear-gradient(160deg,#241c3e,#1b1530);color:var(--text);box-shadow:0 0 0 1px #ffffff0c inset}
.jmode-blurb{font-size:12.5px;font-style:italic;font-family:var(--serif);margin:0 2px 12px;color:var(--muted)}
.jrec{display:flex;align-items:center;gap:12px;margin:2px 2px 12px;padding:13px 14px;border-radius:16px;
  background:linear-gradient(135deg,rgba(245,201,119,.10),rgba(168,85,247,.07));
  border:1px solid rgba(245,201,119,.28);box-shadow:0 8px 28px -16px var(--gold)}
.jrec-ico{flex:none;width:40px;height:40px;border-radius:12px;display:flex;align-items:center;justify-content:center;
  background:rgba(245,201,119,.12);border:1px solid rgba(245,201,119,.25)}
.jrec-ico .i{width:20px;height:20px}
.jrec-main{flex:1;min-width:0}
.jrec-kick{font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:.09em;color:var(--gold);display:flex;align-items:center;gap:4px}
.jrec-kick .i{width:12px;height:12px}
.jrec-title{font-family:var(--serif);font-size:16px;color:var(--text);margin-top:3px}
.jrec-reason{font-size:12px;color:var(--muted);margin-top:3px;line-height:1.35}
.jrec-btn{flex:none;align-self:center;background:linear-gradient(135deg,#f5c977,#e0953a);color:#2a1a05;border:0;
  border-radius:999px;padding:9px 16px;font-size:13px;font-weight:800;cursor:pointer;white-space:nowrap}
.jrec-btn:active{transform:scale(.97)}
/* journal first-run welcome + pledge */
.jwelc-hero{text-align:center;padding:12px 6px 4px}
.jwelc-halo{width:64px;height:64px;margin:6px auto 12px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  background:radial-gradient(circle at 50% 40%,rgba(245,201,119,.22),transparent 70%);border:1px solid rgba(245,201,119,.3)}
.jwelc-halo .i{width:30px;height:30px}
.jwelc-h{font-family:var(--serif);font-size:24px;margin:0 0 6px;color:var(--text)}
.jwelc-sub{font-size:13.5px;line-height:1.5;color:var(--muted);margin:0 auto;max-width:36ch}
.jwelc-cards{display:flex;flex-direction:column;gap:11px;margin:18px 2px}
.jwc{display:flex;gap:12px;padding:14px;border-radius:16px;background:#13101f;border:1px solid var(--line)}
.jwc-ico{flex:none;width:38px;height:38px;border-radius:11px;display:flex;align-items:center;justify-content:center;
  background:rgba(168,85,247,.12);border:1px solid rgba(168,85,247,.22)}
.jwc-ico .i{width:19px;height:19px}
.jwc-body{flex:1;min-width:0}
.jwc-title{font-family:var(--serif);font-size:17px;color:var(--text)}
.jwc-desc{font-size:12.5px;color:#c7bfe0;margin-top:2px;line-height:1.4}
.jwc-stat{font-size:12px;color:var(--muted);margin-top:8px;line-height:1.45;border-left:2px solid rgba(245,201,119,.5);padding-left:9px}
.jwc-stat b{color:var(--gold);font-weight:700}
.jwc-cite{font-size:10.5px;color:#6f6794;margin-top:5px;font-style:italic}
.jwelc-note{font-size:11.5px;color:var(--muted);line-height:1.5;background:#15122280;border:1px solid var(--line);border-radius:12px;padding:11px 12px;margin:0 2px 18px;display:flex;gap:8px}
.jwelc-note .i{width:14px;height:14px;flex:none;margin-top:1px}
.jwelc-pledge{background:linear-gradient(160deg,rgba(245,201,119,.09),rgba(168,85,247,.06));border:1px solid rgba(245,201,119,.26);border-radius:18px;padding:18px 16px;margin:0 2px 8px;text-align:center}
.jwelc-pl-h{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--gold);display:flex;align-items:center;justify-content:center;gap:5px}
.jwelc-pl-h .i{width:14px;height:14px}
.jwelc-pl-body{font-family:var(--serif);font-size:16px;line-height:1.5;color:var(--text);font-style:italic;margin:10px auto 14px;max-width:32ch}
.jwelc-sign{width:100%;box-sizing:border-box;background:#0f0c1a;border:1px solid var(--line);border-radius:12px;padding:13px 14px;
  font-family:var(--serif);font-size:18px;color:var(--gold);text-align:center;letter-spacing:.02em}
.jwelc-sign::placeholder{color:#6f6794;font-style:italic;font-size:15px}
.jwelc-sign.miss{border-color:#e0953a;animation:jwshake .3s}
.jwelc-seal{width:100%;margin-top:12px}
.jwelc-skip{display:block;margin:12px auto 0;background:none;border:0;color:var(--muted);font-size:12.5px;cursor:pointer;text-decoration:underline}
@keyframes jwshake{0%,100%{transform:translateX(0)}25%{transform:translateX(-5px)}75%{transform:translateX(5px)}}
.jwelc-h3{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin:0 4px 2px;text-align:left}
.mgoal{background:#13101f;border:1px solid var(--line);border-radius:16px;padding:16px 14px;margin:4px 2px 18px;text-align:center}
.mgoal-q{font-size:14px;color:var(--text);font-weight:600;margin-bottom:12px}
.mgoal-chips{display:flex;gap:7px;justify-content:center;flex-wrap:wrap}
.mgc{width:38px;height:44px;border-radius:12px;background:#1a1530;border:1px solid var(--line);color:var(--muted);font-size:16px;font-weight:700;cursor:pointer;transition:.15s}
.mgc.on{background:linear-gradient(160deg,#f5c977,#e0953a);color:#2a1a05;border-color:transparent;box-shadow:0 6px 18px -8px var(--gold)}
.mgoal-echo{font-size:12px;color:var(--muted);margin-top:14px;font-style:italic;font-family:var(--serif)}
.mgoal-echo b{color:var(--gold);font-style:normal}
/* journal home — three full-width doors + links + community feed */
.jbigs{display:flex;flex-direction:column;gap:9px;margin:4px 2px 18px}
.jbig{display:flex;align-items:center;gap:13px;width:100%;text-align:left;cursor:pointer;border-radius:15px;padding:15px;transition:.16s;color:var(--text);
  border:1px solid rgba(255,255,255,.07);background:linear-gradient(165deg,#17131f,#110d17 82%)}
.jbig:active{transform:scale(.99)}
.jbig.rec{border-color:rgba(245,201,119,.34);background:linear-gradient(165deg,#1c1710,#120d17 82%)}
.jbig-ico{flex:none;width:40px;height:40px;border-radius:12px;display:flex;align-items:center;justify-content:center;color:color-mix(in srgb,var(--gold) 86%,#fff);
  background:radial-gradient(circle at 34% 28%,rgba(245,201,119,.18),#17121f 72%);border:1px solid rgba(245,201,119,.16)}
.jbig-ico .i{width:20px;height:20px}
.jbig-txt{flex:1;min-width:0;display:flex;flex-direction:column;gap:3px}
.jbig-t{font-family:var(--serif);font-size:17px;display:flex;align-items:center;gap:8px;color:#efe7d6}
.jbig-badge{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.08em;color:#2a1a05;background:linear-gradient(135deg,#f5c977,#e0953a);border-radius:999px;padding:2px 8px}
.jbig-b{font-size:12px;color:var(--muted);line-height:1.3;overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.jbig-go{flex:none;color:#6f6794;font-size:20px;font-weight:300;line-height:1}
.jlinks{display:flex;gap:10px;margin:0 2px 20px}
.jlink{flex:1;display:flex;align-items:center;gap:10px;text-align:left;cursor:pointer;background:#13101f;border:1px solid var(--line);border-radius:14px;padding:12px;color:var(--text);transition:.15s}
.jlink:active{transform:scale(.98)}
.jlink-ico{flex:none;width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:var(--gold);background:radial-gradient(circle at 34% 30%,rgba(245,201,119,.32),#1a1330);border:1px solid rgba(245,201,119,.26);box-shadow:0 0 12px -5px var(--gold)}
.jlink-ico .i{width:16px;height:16px}
.jlink-txt{display:flex;flex-direction:column;min-width:0}
.jlink-txt b{font-size:13px}
.jlink-txt span{font-size:11px;color:var(--muted)}
.jfeed-h{display:flex;align-items:center;gap:7px;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.13em;color:var(--gold);margin:6px 2px 10px}
.jfeed-h .i{width:14px;height:14px}
/* pillars & progress */
.pp-top{background:#13101f;border:1px solid var(--line);border-radius:16px;padding:16px;margin:4px 2px 14px;text-align:center}
.pp-count{font-family:var(--serif);font-size:15px;color:var(--text)}
.pp-count b{color:var(--gold);font-size:17px}
.pp-bar{height:8px;border-radius:999px;background:#241c3e;overflow:hidden;margin-top:10px}
.pp-bar>i{display:block;height:100%;background:linear-gradient(90deg,var(--gold),#e0953a);border-radius:999px;transition:width .4s}
.plz-head{background:#13101f;border:1px solid var(--line);border-radius:16px;padding:16px;margin:2px 2px 16px}
.plz-pill{display:inline-flex;align-items:center;gap:8px;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.1em;color:var(--gold)}
.plz-pill .i{width:15px;height:15px}
.plz-arc{font-family:var(--serif);font-size:14px;color:#d8cff0;line-height:1.42;margin:10px 0 2px}
.plz-meta{font-size:12px;color:var(--muted);margin-top:8px}
.pp-list{display:flex;flex-direction:column;gap:10px}
.pp-row{display:flex;align-items:center;gap:13px;width:100%;text-align:left;cursor:pointer;background:#13101f;border:1px solid var(--line);border-left:3px solid var(--pc,#a855f7);border-radius:14px;padding:13px 14px;color:var(--text);transition:.15s}
.pp-row:active{transform:scale(.99)}
.pp-ico{flex:none;width:40px;height:40px;border-radius:12px;display:flex;align-items:center;justify-content:center;background:color-mix(in srgb,var(--pc,#a855f7) 16%,transparent)}
.pp-ico .i{width:20px;height:20px}
.pp-main{flex:1;min-width:0}
.pp-name{font-family:var(--serif);font-size:16px;display:flex;align-items:center;gap:7px}
.pp-fchip{font-size:9.5px;font-weight:800;text-transform:uppercase;letter-spacing:.06em;color:var(--gold);border:1px solid rgba(245,201,119,.4);border-radius:999px;padding:1px 6px}
.pp-desc{font-size:11.5px;color:var(--muted);margin-top:2px;line-height:1.3}
.pp-stat{flex:none;text-align:center;min-width:44px}
.pp-dot{width:26px;height:26px;border-radius:50%;margin:0 auto;display:flex;align-items:center;justify-content:center;border:1.5px solid #4a4170;color:var(--muted)}
.pp-stat.done .pp-dot{border-color:var(--gold);background:rgba(245,201,119,.12);color:var(--gold)}
.pp-dot .i{width:14px;height:14px}
.pp-sn{font-size:10px;color:var(--muted);margin-top:3px}
/* Pillars redesign — a display case of focus pillars under an arch + pillar cards + Jungian path */
.pcase{position:relative;overflow:hidden;background:linear-gradient(180deg,#0c0a16,#080610);border:1px solid #241d38;border-radius:100px 100px 20px 20px;padding:30px 20px 20px;margin:6px 0 18px;text-align:center;box-shadow:inset 0 2px 30px -6px #000,inset 0 0 70px -24px #000,0 14px 36px -18px #000}
.pcase:before{content:"";position:absolute;inset:0;pointer-events:none;background:radial-gradient(110% 60% at 50% 0,rgba(245,201,119,.14),transparent 56%)}
/* faint fluted pilasters down the sides of the niche */
.pcase:after{content:"";position:absolute;left:14px;right:14px;top:70px;bottom:14px;pointer-events:none;
  background:linear-gradient(90deg,rgba(245,201,119,.16),transparent 7%,transparent 93%,rgba(245,201,119,.16)),linear-gradient(90deg,transparent 2.5%,rgba(245,201,119,.08) 3%,transparent 3.5%,transparent 96.5%,rgba(245,201,119,.08) 97%,transparent 97.5%)}
/* inner gold outline tracing the arch */
.pcase-frame{position:absolute;inset:9px;border:1px solid rgba(245,201,119,.22);border-radius:92px 92px 14px 14px;pointer-events:none;box-shadow:inset 0 0 22px -10px rgba(245,201,119,.4)}
.pcase-eyebrow,.pcase-row{position:relative;z-index:1}
.pcase-eyebrow,.pcols{position:relative;z-index:1}
.pcase-eyebrow{display:inline-flex;align-items:center;gap:7px;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.14em;color:var(--gold);margin-bottom:10px}
.pcase-eyebrow .i{width:14px;height:14px}
/* the four focus pillars, each a recoloured Lottie column standing in the niche */
.pcols{display:flex;justify-content:center;align-items:flex-end;gap:clamp(4px,3vw,14px)}
.pcolumn{position:relative;display:flex;flex-direction:column;align-items:center;gap:6px;width:clamp(56px,20vw,74px);background:none;border:0;cursor:pointer;font-family:inherit;padding:0}
.pcolumn:active{transform:translateY(1px)}
.pcolumn-glow{position:absolute;left:50%;top:40px;width:62px;height:62px;transform:translateX(-50%);pointer-events:none;z-index:0;border-radius:50%;
  background:radial-gradient(circle,color-mix(in srgb,var(--pc) 55%,transparent),transparent 68%);filter:blur(7px);opacity:.5}
.pcolumn:active .pcolumn-glow{opacity:.75}
.pcolumn-art{position:relative;z-index:1;width:100%;height:92px;filter:drop-shadow(0 6px 9px rgba(0,0,0,.55))}
.pcolumn-art svg{width:100%!important;height:100%!important}
.pcolumn-base{position:relative;z-index:1;width:92%;height:3px;border-radius:2px;margin-top:-2px;background:linear-gradient(90deg,transparent,color-mix(in srgb,var(--pc) 45%,transparent),transparent)}
.pcolumn-nm{font-size:11px;font-weight:700;color:#efe6ff;line-height:1.12;text-align:center}
.pcase-empty{color:var(--muted);font-size:12.5px;max-width:30ch;margin:8px auto 2px}
.pgrid-h,.jpath-eyebrow{display:inline-flex;align-items:center;gap:7px;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.13em}
.pgrid-h{color:var(--gold);margin:2px 2px 10px}
.pgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}
.pgrid-card{display:flex;flex-direction:column;align-items:center;gap:9px;cursor:pointer;font-family:inherit;padding:13px 6px 11px;border-radius:15px;
  background:linear-gradient(165deg,#191326,#110d1b 82%);border:1px solid rgba(245,201,119,.14);box-shadow:0 8px 22px -18px #000}
.pgrid-card:active{transform:scale(.97)}
.pgrid-med{flex:none;width:42px;height:42px;border-radius:50%;display:grid;place-items:center;color:color-mix(in srgb,var(--gold) 82%,#fff);
  background:radial-gradient(circle at 34% 30%,color-mix(in srgb,var(--gold) 24%,transparent),#140e26 72%);border:1px solid color-mix(in srgb,var(--gold) 22%,transparent);box-shadow:0 0 12px -5px color-mix(in srgb,var(--gold) 70%,transparent)}
.pgrid-med .i{width:21px;height:21px}
.pgrid-nm{font-size:10.5px;font-weight:600;color:#d6ccdf;text-align:center;line-height:1.15}
.jpath{position:relative;overflow:hidden;border:1px solid #2a2144;border-radius:18px;padding:16px;margin-top:20px;background:linear-gradient(165deg,#171127,#100c1b 78%)}
.jpath:before{content:"";position:absolute;inset:0;pointer-events:none;opacity:.5;background:radial-gradient(120% 70% at 92% -10%,rgba(168,85,247,.2),transparent 55%)}
.jpath>*{position:relative;z-index:1}
.jpath-h{display:flex;align-items:center;justify-content:space-between;gap:10px}
.jpath-eyebrow{color:#c3b2ee}
.jpath-eyebrow .i{width:13px;height:13px}
.jpath-soon{font-size:9.5px;font-weight:800;text-transform:uppercase;letter-spacing:.06em;color:#140f22;background:linear-gradient(135deg,#c084fc,#8b5cf6);border-radius:999px;padding:3px 9px;white-space:nowrap}
.jpath-sub{font-size:12.5px;color:var(--muted);line-height:1.45;margin:9px 0 12px}
.jpath-rows{display:flex;flex-direction:column;gap:8px}
.jpath-row{display:flex;align-items:center;gap:12px;padding:11px 12px;border-radius:12px;background:#120e1e;border:1px dashed #352b54}
.jpath-ico{flex:none;width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:#1a1430;border:1px solid #352b54;color:#8b7fb5}
.jpath-ico .i{width:15px;height:15px}
.jpath-main{flex:1;min-width:0}
.jpath-t{display:block;font-weight:700;font-size:13.5px;color:#d8cff0}
.jpath-d{display:block;font-size:11.5px;color:var(--muted)}
.jpath-lock{font-size:9.5px;font-weight:800;text-transform:uppercase;letter-spacing:.05em;color:#8b7fb5}
.pcase-editrow{display:flex;justify-content:center;margin:-8px 0 16px}
.pcase-edit{display:inline-flex;align-items:center;gap:6px;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.08em;color:#cbbfe6;background:rgba(255,255,255,.05);border:1px solid rgba(245,201,119,.25);border-radius:999px;padding:6px 13px;cursor:pointer;font-family:inherit}
.pcase-edit .i{width:12px;height:12px;color:var(--gold)}
.pcase-edit:active{transform:scale(.97)}
.jgrid{display:grid;grid-template-columns:1fr 1fr;gap:9px}
.jcard{position:relative;display:flex;flex-direction:column;gap:5px;padding:14px 13px 13px;border-radius:14px;background:linear-gradient(165deg,#191230,#100c1b 84%);border:1px solid rgba(168,85,247,.16);text-align:left}
.jcard-top{display:flex;align-items:center;gap:9px;margin-bottom:3px}
.jcard-med{flex:none;width:34px;height:34px;border-radius:50%;display:grid;place-items:center;color:#c8b6f5;background:radial-gradient(circle at 34% 30%,rgba(168,85,247,.28),#140e26 72%);border:1px solid rgba(168,85,247,.28)}
.jcard-med .i{width:18px;height:18px}
.jcard-n{font-family:var(--serif);font-size:20px;font-weight:600;color:#8f82b8;line-height:1;margin-left:auto}
.jcard-lk{position:absolute;bottom:12px;right:12px;color:#6b5f93}
.jcard-lk .i{width:13px;height:13px}
.jcard-t{font-weight:700;font-size:13.5px;color:#e4dcf6;line-height:1.15}
.jcard-d{font-size:11px;color:var(--muted);line-height:1.35;padding-right:15px}
/* localized sparks behind the featured (recommended) journal door */
.jbig{position:relative;overflow:hidden}
.jbig-sparks{position:absolute;inset:0;pointer-events:none;z-index:0}
.jbig-ico,.jbig-txt,.jbig-go{position:relative;z-index:1}
.jsp{position:absolute;bottom:-5px;width:3px;height:3px;border-radius:50%;background:var(--gold);box-shadow:0 0 6px var(--gold);opacity:0;animation:jsprise linear infinite}
@keyframes jsprise{0%{transform:translateY(0) scale(.5);opacity:0}16%{opacity:.95}100%{transform:translateY(-68px) scale(1.05);opacity:0}}
.pp-stat.done .pp-sn{color:var(--gold)}
.pillar-grid{display:grid;grid-template-columns:1fr 1fr;gap:11px}
.pcard{position:relative;text-align:left;cursor:pointer;color:var(--text);
  background:linear-gradient(165deg,#1c1830,#15112275);border:1px solid var(--line);border-radius:16px;
  padding:14px 13px 13px;display:flex;flex-direction:column;gap:5px;overflow:hidden;transition:.18s}
.pcard:before{content:"";position:absolute;inset:0 auto 0 0;width:3px;background:var(--pc,#a855f7);opacity:.9}
.pcard:hover{border-color:var(--pc,#a855f7);transform:translateY(-1px)}
.pcard.focus{box-shadow:0 0 0 1px var(--pc,#a855f7) inset,0 10px 30px -18px var(--pc,#a855f7)}
.pcard .pico{width:26px;height:26px}.pcard .pico .i{width:26px;height:26px}
.pname{font-weight:700;font-size:14px}
.pdesc{font-size:11.5px;color:var(--muted);line-height:1.4;font-family:var(--serif)}
.pfocus{position:absolute;top:10px;right:10px;font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;
  color:var(--pc,#a855f7);background:#0e0b18;border:1px solid var(--pc,#a855f7);border-radius:999px;padding:2px 7px}
.jgrid-hint{font-size:12px;font-style:italic;font-family:var(--serif);text-align:center;margin:13px 4px 2px}
.deep-head{position:relative;z-index:1;display:flex;align-items:center;gap:12px;margin-bottom:6px}
.deep-back{flex:none;width:38px;height:38px;border-radius:50%;border:1px solid var(--line);background:#1b1530;
  color:var(--pc,#a855f7);display:grid;place-items:center;cursor:pointer}
.deep-back .i{width:18px;height:18px}
.deep-pill{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:700;color:var(--pc,#a855f7)}
.deep-pill .i{width:14px;height:14px}
.deep-title{font-family:var(--serif);font-size:19px;color:#efe9f8;margin-top:2px}
.season-head{align-items:flex-start}
.planbar{position:relative;z-index:1;margin:2px 0 12px}
.pb-arc{font-family:var(--serif);font-size:13.5px;line-height:1.5;color:#b7add2;font-style:italic;margin-bottom:8px}
.pb-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.pb-dots{display:flex;align-items:center;gap:6px}
.pb-dot{width:9px;height:9px;border-radius:50%;background:#2a2340;border:1px solid var(--line);transition:all .3s}
.pb-dot.done{background:var(--pc,#a855f7);opacity:.55;border-color:transparent}
.pb-dot.on{background:var(--gold);border-color:transparent;box-shadow:0 0 8px var(--gold);transform:scale(1.25)}
.pb-cap{font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;color:#8c82a6;font-weight:600}
.deep-steps{position:relative;z-index:1;margin:4px 0 14px;padding-left:20px;display:flex;flex-direction:column;gap:9px}
.deep-steps li{font-family:var(--serif);font-size:14px;line-height:1.55;color:#cdc5e6}
.deep-steps li::marker{color:var(--pc,#a855f7);font-weight:700}
.jplace-wrap{position:relative;z-index:1;display:flex;align-items:center;gap:9px;margin-bottom:12px;
  background:#15112270;border:1px solid var(--line);border-radius:12px;padding:9px 13px}
.jplace-wrap .i{width:16px;height:16px;flex:none}
.jplace{flex:1;background:transparent;border:0;outline:0;color:var(--text);font-size:15px;font-family:var(--serif)}
.jplace::placeholder{color:#6f6790;font-style:italic}
.lp-speak{background:transparent;border:0;color:var(--muted);cursor:pointer;padding:2px;display:inline-flex}
.lp-speak.on{color:var(--gold)}
.lp-speak .i{width:18px;height:18px}
.compass2{position:relative;width:min(330px,88vw);margin:10px auto 16px}
.compass2:before{content:"";display:block;padding-top:100%}
.crays{position:absolute;inset:0;width:100%;height:100%}
.crays .cray{stroke:#2e2747;stroke-width:1.6;stroke-linecap:round;transition:stroke .3s,filter .3s}
.crays .cray.set{stroke:#6a5630;filter:drop-shadow(0 0 3px #f5c97755)}
.cnode{position:absolute;width:33%;display:flex;flex-direction:column;align-items:center;gap:5px;cursor:pointer;z-index:2}
.cN{top:0;left:50%;transform:translateX(-50%)}
.cS{bottom:0;left:50%;transform:translateX(-50%)}
.cW{left:0;top:50%;transform:translateY(-50%)}
.cE{right:0;top:50%;transform:translateY(-50%)}
.cbadge{width:60px;height:60px;border-radius:50%;display:grid;place-items:center;transition:.2s;
  background:radial-gradient(circle at 50% 38%,#1f1838,#120e22);border:1.5px solid #2e2747;color:var(--muted)}
.cnode:active .cbadge{transform:scale(.93)}
.cnode.set .cbadge{border-color:var(--gold);color:var(--gold);box-shadow:0 0 16px -5px var(--gold)}
.cnode.focus .cbadge{box-shadow:0 0 20px -3px var(--gold),0 0 0 2px #f5c97740;animation:cfoc 3s ease-in-out infinite}
@keyframes cfoc{0%,100%{box-shadow:0 0 14px -5px var(--gold),0 0 0 2px #f5c97733}50%{box-shadow:0 0 24px -3px var(--gold),0 0 0 2px #f5c97766}}
.cbadge .pico{width:30px;height:30px}
.cnode.set .cbadge .pico{filter:drop-shadow(0 0 5px #f5c97799)}
.cadd{font-size:26px;color:var(--purple);font-weight:300;line-height:1}
.clabel{font-size:11px;font-weight:600;text-align:center;max-width:92px;line-height:1.2;color:var(--muted)}
.cnode.set .clabel{color:var(--text)}
.cnode.focus .clabel{color:var(--gold)}
.cbase2{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:86px;height:86px;border-radius:50%;z-index:3;
  background:radial-gradient(circle at 50% 38%,#3a2b5e,#160f28);border:1.6px solid var(--gold);
  display:flex;flex-direction:column;align-items:center;justify-content:center;box-shadow:0 0 28px -6px #f5c97777;padding:6px}
.cbase2 input{background:transparent;border:0;text-align:center;color:var(--gold);font-weight:800;font-size:14px;width:74px;padding:0}
.cbase2 input:focus{outline:none}
.cbase2 span{font-size:8px;color:var(--muted);text-transform:uppercase;letter-spacing:.12em;margin-top:3px}
.lo-focus{display:flex;gap:8px;flex-wrap:wrap}
.fchip{border:1px solid var(--line);background:#13101f;color:var(--text);border-radius:999px;padding:8px 14px;font-weight:600;font-size:13px;cursor:pointer;display:inline-flex;align-items:center;gap:5px}
.fchip.on{border-color:var(--gold);color:var(--gold);background:#1c1608}
.fchip .i{width:14px;height:14px}
.lo-pick{display:flex;flex-wrap:wrap;gap:8px}
.pchip{border:1px solid var(--line);background:#13101f;color:var(--text);border-radius:12px;padding:9px 13px;font-size:13px;font-weight:600;cursor:pointer;display:inline-flex;align-items:center;gap:6px}
.pchip .i{width:15px;height:15px;color:var(--pc,var(--purple))}
.pchip.on{border-color:var(--purple);background:#1e1636;color:#e9d5ff}
.pchip.on .i{color:#c9a6ff}
.pchip.used{opacity:.45}
.lo-prompt{display:flex;align-items:center;gap:12px;padding:12px;border:1px solid var(--line);border-radius:14px;background:#13101f;margin:9px 0;cursor:pointer;transition:border-color .15s}
.lo-prompt:active{transform:scale(.99)}
.lo-prompt:hover{border-color:#3a2d5e}
.lo-pico{width:34px;height:34px;flex:none;border-radius:10px;background:#0f0d18;display:grid;place-items:center}
.lo-pico .i{width:19px;height:19px}
.lo-write{flex:none;background:#1a1330;border:1px solid #3a2d5e;color:var(--purple);border-radius:10px;width:38px;height:38px;display:grid;place-items:center;cursor:pointer}
.lo-write .i{width:17px;height:17px}
.lo-lesson{position:relative;z-index:2;text-align:left;background:#120e20cc;border:1px solid var(--line);border-left:3px solid var(--c);border-radius:12px;padding:12px 14px;margin:12px 4px 2px}
.lo-lesson-h{display:flex;align-items:center;gap:6px;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--c);font-weight:700}
.lo-lesson-h .i{width:13px;height:13px}
.lo-lesson-b{font-family:var(--serif);font-size:14.5px;line-height:1.55;color:#e8e2f2;margin-top:6px}
/* the Keeper chat */
.chatbox{height:58vh;min-height:300px;overflow-y:auto;display:flex;flex-direction:column;gap:12px;padding:6px 2px 2px}
.chat-input{display:flex;align-items:center;gap:9px;margin-top:12px}
.chat-input input{flex:1;width:auto;border-radius:999px;padding:12px 16px}
.csend{flex:none;width:46px;height:46px;border-radius:50%;border:0;background:linear-gradient(135deg,var(--purple),var(--purple2));color:#fff;display:grid;place-items:center;cursor:pointer;box-shadow:0 4px 16px -6px var(--purple)}
.csend:active{transform:scale(.94)}
.csend .i{width:20px;height:20px}
.msg{display:flex;gap:9px;max-width:88%}
.msg.u{align-self:flex-end;flex-direction:row-reverse}
.msg-ic{flex:none;width:28px;height:28px;border-radius:50%;background:#1a1330;border:1px solid var(--line);display:grid;place-items:center;color:var(--gold)}
.msg-ic .i{width:16px;height:16px;filter:drop-shadow(0 0 5px #f5c97777)}
.bub{padding:11px 14px;border-radius:16px;font-size:15px;line-height:1.5}
.msg.k .bub{background:#17132a;border:1px solid var(--line);border-top-left-radius:5px;color:#ece9f5}
.msg.u .bub{background:linear-gradient(135deg,#2a1f52,#3a2d6e);border-top-right-radius:5px;color:#fff}
.bub.typing{display:flex;gap:4px;align-items:center}
.bub.typing i{width:6px;height:6px;border-radius:50%;background:var(--muted);animation:tdot 1.2s infinite}
.bub.typing i:nth-child(2){animation-delay:.2s}.bub.typing i:nth-child(3){animation-delay:.4s}
@keyframes tdot{0%,60%,100%{opacity:.3;transform:translateY(0)}30%{opacity:1;transform:translateY(-3px)}}
/* achievement collectible card */
.ach-ov{position:fixed;inset:0;z-index:60;display:grid;place-items:center;padding:24px;
  background:rgba(6,5,12,.72);backdrop-filter:blur(6px);opacity:0;transition:opacity .22s}
.ach-ov.show{opacity:1}
.ach-card{position:relative;width:min(320px,86vw);border-radius:24px;padding:30px 24px 22px;text-align:center;overflow:hidden;
  background:
    radial-gradient(120% 80% at 50% -10%, var(--glow,transparent), transparent 60%),
    linear-gradient(170deg,var(--tint,#1d1733),#140f24 62%,#0e0a1b);
  border:1.5px solid var(--rc);box-shadow:0 0 0 1px #ffffff08 inset,0 24px 70px -20px #000,0 0 44px -12px var(--rc);
  transform:translateY(16px) scale(.94);opacity:0;transition:transform .35s cubic-bezier(.2,.9,.25,1.2),opacity .3s}
.ach-ov.show .ach-card{transform:translateY(0) scale(1);opacity:1}
.ach-card.locked{filter:saturate(.45) brightness(.9)}
.ach-foil{position:absolute;inset:0;pointer-events:none;mix-blend-mode:screen;opacity:.42;
  background:linear-gradient(115deg,transparent 34%,var(--rc) 50%,transparent 66%);
  background-size:280% 280%;animation:foil 3.6s linear infinite}
@keyframes foil{0%{background-position:160% 0}100%{background-position:-60% 0}}
/* per-rarity foil + shine */
.ach-card.rar-0 .ach-foil{opacity:.3;background:linear-gradient(115deg,transparent 36%,#c9cde0 50%,transparent 64%);background-size:280% 280%}
.ach-card.rar-1 .ach-foil{opacity:.5;background:linear-gradient(115deg,transparent 32%,#5fb0fa 48%,#bfe0ff 52%,transparent 68%);background-size:280% 280%}
.ach-card.rar-2 .ach-foil{opacity:.55;background:linear-gradient(115deg,transparent 30%,#a855f7 45%,#e9a8ff 51%,#ec4899 57%,transparent 72%);background-size:280% 280%}
.ach-card.rar-3{box-shadow:0 0 0 1px #ffffff12 inset,0 24px 80px -18px #000,0 0 60px -10px var(--rc)}
.ach-card.rar-3 .ach-foil{opacity:.7;background:linear-gradient(115deg,transparent 22%,#a855f7 40%,#f5c977 50%,#ec4899 60%,#f5c977 70%,transparent 82%);background-size:260% 260%;animation-duration:2.8s}
.ach-x{position:absolute;top:12px;right:12px;z-index:3;background:#ffffff12;border:0;color:var(--muted);
  width:30px;height:30px;border-radius:50%;display:grid;place-items:center;cursor:pointer}
.ach-x .i{width:16px;height:16px}
.ach-rare{position:relative;z-index:2;display:inline-block;font-size:11px;font-weight:800;letter-spacing:.14em;
  text-transform:uppercase;border:1px solid;border-radius:999px;padding:3px 12px;margin-bottom:16px}
.ach-badge{position:relative;z-index:2;height:128px;display:grid;place-items:center;margin-bottom:6px}
.ach-ring{position:absolute;width:118px;height:118px;border-radius:50%;
  background:radial-gradient(circle,var(--rc) 0%,transparent 62%);opacity:.28;animation:ringpulse 2.6s ease-in-out infinite}
@keyframes ringpulse{0%,100%{transform:scale(.9);opacity:.22}50%{transform:scale(1.08);opacity:.4}}
.ach-ic .achbig{width:82px;height:82px;filter:drop-shadow(0 0 14px var(--rc))}
.ach-card.locked .ach-ic .achbig{filter:none;color:var(--muted);opacity:.7}
.ach-title{position:relative;z-index:2;font-size:24px;font-weight:800;letter-spacing:-.02em}
.ach-desc{position:relative;z-index:2;color:var(--muted);font-size:14px;margin:6px 12px 16px}
.ach-meta{position:relative;z-index:2;display:flex;flex-direction:column;gap:7px;align-items:center}
.ach-chip{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--muted);
  background:#ffffff0a;border:1px solid var(--line);border-radius:999px;padding:5px 12px}
.ach-chip .i{width:14px;height:14px}
.rtag{font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--c);
  border:1px solid var(--c);border-radius:999px;padding:2px 9px;align-self:center;opacity:.9}
/* collection */
.coll-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:4px}
.coll{position:relative;border:1px solid var(--line);border-radius:16px;padding:14px 8px 10px;text-align:center;cursor:pointer;background:#13101f;transition:transform .16s,box-shadow .3s;overflow:hidden}
.coll:active{transform:scale(.95)}
.coll-ic{height:46px;display:grid;place-items:center;color:var(--muted)}
.coll-ic .i{width:38px;height:38px}
.coll-nm{font-size:12px;font-weight:600;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.coll-st{font-size:10px;text-transform:uppercase;letter-spacing:.05em;margin-top:3px;color:var(--muted)}
.coll.owned{border-color:var(--rc);box-shadow:0 0 16px -8px var(--rc)}
.coll.owned .coll-ic{color:var(--rc)}
.coll.owned .coll-ic .i{filter:drop-shadow(0 0 6px var(--rc))}
.coll.owned .coll-st{color:var(--rc)}
.coll.claim{border-color:var(--gold);animation:claimglow 2.2s ease-in-out infinite}
.coll.claim .coll-ic{color:var(--gold)}
.coll.claim .coll-ic .i{filter:drop-shadow(0 0 7px var(--gold))}
.coll.claim .coll-st{color:var(--gold);font-weight:800}
.coll.locked{opacity:.55}
@keyframes claimglow{0%,100%{box-shadow:0 0 0 0 transparent}50%{box-shadow:0 0 18px -5px var(--gold)}}
.companion{display:inline-flex;align-items:center;gap:7px;margin-top:10px;font-size:12px;color:var(--muted)}
.companion .i{width:16px;height:16px;color:var(--gold);filter:drop-shadow(0 0 5px #f5c97799)}
/* guided lessons */
.lesson-card{display:flex;gap:0;align-items:stretch;border:1px solid var(--line);border-radius:18px;overflow:hidden;
  background:linear-gradient(135deg,#15111f,#120e1c);cursor:pointer;transition:border-color .15s,transform .12s;margin-bottom:10px}
.lesson-card:active{transform:scale(.99)}
.lesson-card:hover{border-color:var(--a)}
.lesson-img{position:relative;overflow:hidden;width:98px;flex:none;display:grid;place-items:center;border-right:1px solid var(--line);
  background:radial-gradient(circle at 50% 30%,#4a3410,#2a1c46 60%,#140e26)}
/* modern Hindu-cultural mandala motif behind the glyph */
.lesson-img:before,.deity-emblem:before{content:"";position:absolute;inset:0;z-index:0;opacity:.5;background-position:center;background-repeat:no-repeat;background-size:116%;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Cg fill='none' stroke='%23f5c977' stroke-width='0.9'%3E%3Ccircle cx='50' cy='50' r='43'/%3E%3Ccircle cx='50' cy='50' r='31'/%3E%3Ccircle cx='50' cy='50' r='19'/%3E%3Cline x1='68' y1='50' x2='92' y2='50'/%3E%3Cline x1='50' y1='68' x2='50' y2='92'/%3E%3Cline x1='32' y1='50' x2='8' y2='50'/%3E%3Cline x1='50' y1='32' x2='50' y2='8'/%3E%3Cline x1='62.7' y1='62.7' x2='79.7' y2='79.7'/%3E%3Cline x1='37.3' y1='62.7' x2='20.3' y2='79.7'/%3E%3Cline x1='37.3' y1='37.3' x2='20.3' y2='20.3'/%3E%3Cline x1='62.7' y1='37.3' x2='79.7' y2='20.3'/%3E%3Ccircle cx='59' cy='50' r='7'/%3E%3Ccircle cx='54.5' cy='57.8' r='7'/%3E%3Ccircle cx='45.5' cy='57.8' r='7'/%3E%3Ccircle cx='41' cy='50' r='7'/%3E%3Ccircle cx='45.5' cy='42.2' r='7'/%3E%3Ccircle cx='54.5' cy='42.2' r='7'/%3E%3C/g%3E%3Cg fill='%23f5c977'%3E%3Ccircle cx='92' cy='50' r='1.8'/%3E%3Ccircle cx='86.4' cy='71' r='1.8'/%3E%3Ccircle cx='71' cy='86.4' r='1.8'/%3E%3Ccircle cx='50' cy='92' r='1.8'/%3E%3Ccircle cx='29' cy='86.4' r='1.8'/%3E%3Ccircle cx='13.6' cy='71' r='1.8'/%3E%3Ccircle cx='8' cy='50' r='1.8'/%3E%3Ccircle cx='13.6' cy='29' r='1.8'/%3E%3Ccircle cx='29' cy='13.6' r='1.8'/%3E%3Ccircle cx='50' cy='8' r='1.8'/%3E%3Ccircle cx='71' cy='13.6' r='1.8'/%3E%3Ccircle cx='86.4' cy='29' r='1.8'/%3E%3C/g%3E%3C/svg%3E")}
.lesson-img img{position:absolute;inset:0;z-index:2;width:100%;height:100%;object-fit:cover}
.lesson-imic{position:relative;z-index:1;color:var(--gold);filter:drop-shadow(0 0 10px #f5c97766)}.lesson-imic .i{width:30px;height:30px}
.lesson-meta{padding:12px 13px;min-width:0}
.lesson-name{font-weight:700;font-size:15px}
.lesson-sub{font-size:10.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-top:3px}
.lesson-blurb{font-family:var(--serif);font-size:13px;color:#cbbfe6;line-height:1.5;margin-top:7px}
.lesson-go{display:inline-flex;align-items:center;gap:6px;color:var(--a);font-size:12px;font-weight:700;margin-top:9px}
.lesson-go .i{width:13px;height:13px}
.lesson-head{display:flex;align-items:center;justify-content:space-between;gap:10px}
.lesson-all{color:var(--gold);font-size:12px;font-weight:700;cursor:pointer;white-space:nowrap}
.lesson-done{display:inline-flex;align-items:center;gap:6px;color:#6ee7b7;font-size:11.5px;font-weight:700;margin-top:9px}
.lesson-done .i{width:13px;height:13px}
.lesson-card.done{border-color:#2e6b52}
.lesson-card.resume{border-color:var(--a)}
.lesson-resume-bar{height:5px;border-radius:999px;background:#241d3a;overflow:hidden;margin:9px 0 3px}
.lesson-resume-bar>i{display:block;height:100%;background:linear-gradient(90deg,var(--a),var(--gold))}
/* --- reworked vertical journey cards (deity centered, title + description below) --- */
.jcard{flex-direction:column;align-items:stretch;gap:0;padding:0}
/* --- Today's pick — clean featured card --- */
.rec-feature{margin:18px 0 0}
.pickcard{display:flex;flex-direction:column;border:1px solid color-mix(in srgb,var(--a) 45%,var(--line));border-radius:22px;overflow:hidden;cursor:pointer;
  background:linear-gradient(165deg,color-mix(in srgb,var(--a) 15%,#15111f),#110d1b 72%);
  box-shadow:0 16px 44px -22px color-mix(in srgb,var(--a) 80%,#000);transition:transform .12s,border-color .15s}
.pickcard:active{transform:scale(.99)}
.pick-head{display:flex;align-items:center;justify-content:space-between;padding:14px 16px 0}
.pick-tag{display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.13em;color:var(--gold)}
.pick-tag .i{width:13px;height:13px}
.pick-listen{flex:none;width:36px;height:36px;border-radius:50%;border:1px solid var(--line);background:#ffffff0a;color:var(--muted);display:grid;place-items:center;cursor:pointer;transition:.15s}
.pick-listen:hover{color:var(--gold);border-color:color-mix(in srgb,var(--gold) 50%,var(--line))}
.pick-listen .i{width:16px;height:16px}
.pick-top{display:flex;gap:15px;align-items:center;padding:13px 16px 16px}
.pick-art{flex:none;width:84px;height:84px;border-radius:20px;overflow:hidden;position:relative;display:grid;place-items:center;
  background:radial-gradient(circle at 50% 32%,color-mix(in srgb,var(--a) 42%,#2a1c46),#140e26);border:1px solid #ffffff16;box-shadow:0 8px 22px -12px color-mix(in srgb,var(--a) 80%,#000)}
.pick-art .deity-emblem{width:100%;height:100%;border-radius:0;border:0;box-shadow:none}
.pick-art .deity-emblem .deity-glyph .i{width:36px;height:36px}
.pick-main{min-width:0;flex:1}
.pick-title{font-size:20px;font-weight:800;color:#f3eeff;line-height:1.14;letter-spacing:-.01em}
.pick-meta{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-top:5px}
.pick-blurb{font-family:var(--serif);font-size:13.5px;color:#c4b9e0;line-height:1.5;margin-top:8px;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.pick-progress{height:4px;background:#ffffff12;margin:0 16px}
.pick-progress>i{display:block;height:100%;background:linear-gradient(90deg,var(--a),var(--gold))}
.pick-cta{display:flex;align-items:center;justify-content:center;gap:8px;padding:14px;font-weight:800;font-size:14.5px;
  color:var(--a);border-top:1px solid #ffffff12;background:#ffffff07}
.pick-cta .i{width:15px;height:15px}
/* onboarding */
.onb-top{display:flex;align-items:center;justify-content:space-between;padding:4px 2px 0}
.onb-brand{display:flex;align-items:center;gap:7px;font-weight:800;color:var(--gold)}
.onb-brand .i{width:22px;height:22px}
.onb-signin{color:var(--muted,#9a93b8);font-size:14px;text-decoration:none;cursor:pointer}
.onb-body{min-height:52vh;display:flex;flex-direction:column;justify-content:center}
.onb-hero{text-align:center;padding:12px 6px}
.onb-photo{width:100%;max-width:330px;margin:0 auto 4px;border-radius:22px;overflow:hidden;aspect-ratio:4/3;background:rgba(255,255,255,.04);box-shadow:0 16px 44px rgba(0,0,0,.5),inset 0 0 0 1px rgba(245,201,119,.12)}
.onb-photo img{width:100%;height:100%;object-fit:cover;display:block}
.onb-hero.has-photo .onb-ic{display:none}
.onb-hero.has-photo .onb-h{margin-top:16px}
.onb-ic .i{width:84px;height:84px;color:var(--gold);filter:drop-shadow(0 0 26px rgba(245,201,119,.5))}
.onb-h{font-size:28px;line-height:1.15;margin:18px 10px 10px}
.onb-h.sm{font-size:22px;margin:6px 2px 6px;text-align:left}
.onb-qic{text-align:left;margin:0 2px 2px}
.onb-qic .i{width:40px;height:40px;color:var(--gold);filter:drop-shadow(0 0 16px rgba(245,201,119,.45))}
.onb-p{color:var(--muted,#b4acd0);font-size:16px;line-height:1.55;margin:0 14px}
.onb-p.sm{font-size:14px;margin:0 2px 14px;text-align:left}
.onb-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:4px}
.onb-grid.two{grid-template-columns:1fr 1fr}
.onb-chip{display:flex;align-items:center;gap:10px;justify-content:flex-start;background:var(--panel,#161326);
  border:1px solid var(--line);border-radius:14px;padding:16px 14px;color:var(--text,#ece9f5);font-size:15px;
  font-weight:600;cursor:pointer;text-align:left;transition:border-color .15s,background .15s}
.onb-chip.wide{grid-column:1/-1;justify-content:center}
.onb-chip .i{width:20px;height:20px}
.onb-chip.sel{border-color:var(--gold);background:rgba(245,201,119,.10)}
.onb-chip.sel .i{color:var(--gold)}
.onb-foot{position:sticky;bottom:0;padding:14px 0 calc(10px + env(safe-area-inset-bottom));
  background:linear-gradient(0deg,var(--bg) 72%,transparent)}
.onb-dots{display:flex;gap:7px;justify-content:center;margin-bottom:14px}
.onb-dots span{width:7px;height:7px;border-radius:50%;background:var(--line)}
.onb-dots span.on{background:var(--gold);width:20px;border-radius:4px}
.onb-nav{display:flex;gap:10px;align-items:center}
.onb-nav .btn{flex:1}
.onb-nav .btn[disabled]{opacity:.4;pointer-events:none}
/* onboarding animated scenes (replace the old real-people photos) */
.onb-anim{width:100%;max-width:330px;margin:0 auto 6px;border-radius:22px;overflow:hidden;aspect-ratio:4/3;position:relative;
  background:radial-gradient(130% 110% at 50% 18%,#241a3a 0%,#181127 52%,#0f0a1e 100%);
  box-shadow:0 18px 46px rgba(0,0,0,.5),inset 0 0 0 1px rgba(245,201,119,.14),inset 0 -40px 60px -30px rgba(245,201,119,.12)}
.onb-anim svg{width:100%;height:100%;display:block}
.onb-enter{animation:onbRise .5s cubic-bezier(.2,.8,.25,1) both}
.onb-enter.d1{animation-delay:.05s}.onb-enter.d2{animation-delay:.11s}
@keyframes onbRise{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
@keyframes osBreathe{0%,100%{transform:scale(1)}50%{transform:scale(1.035)}}
@keyframes osTwinkle{0%,100%{opacity:.25}50%{opacity:1}}
@keyframes osSpin{to{transform:rotate(360deg)}}
@keyframes osSpinR{to{transform:rotate(-360deg)}}
@keyframes osRise{0%{opacity:0;transform:translateY(8px) scale(.6)}25%{opacity:1}100%{opacity:0;transform:translateY(-26px) scale(1)}}
@keyframes osRipple{0%{opacity:.7;transform:scale(.2)}100%{opacity:0;transform:scale(1)}}
@keyframes osDrop{0%{opacity:0;transform:translateY(-22px)}55%{opacity:1;transform:translateY(3px)}72%{transform:translateY(-2px)}100%{transform:translateY(0)}}
@keyframes osSweep{to{stroke-dashoffset:0}}
@keyframes osBloom{0%{opacity:0;transform:scale(.3) rotate(-18deg)}100%{opacity:1;transform:none}}
@keyframes osGlow{0%,100%{opacity:.5}50%{opacity:1}}
@keyframes osShimmer{0%{transform:translateX(-120%)}60%,100%{transform:translateX(220%)}}
.os-spin{transform-box:fill-box;transform-origin:center;animation:osSpin 26s linear infinite}
.os-spinr{transform-box:fill-box;transform-origin:center;animation:osSpinR 34s linear infinite}
.os-breathe{transform-box:fill-box;transform-origin:center;animation:osBreathe 5s ease-in-out infinite}
.os-tw{animation:osTwinkle 2.6s ease-in-out infinite}
.os-glow{animation:osGlow 3.4s ease-in-out infinite}
.os-rise{transform-box:fill-box;transform-origin:center;animation:osRise 3.6s ease-in-out infinite}
.os-ripple{transform-box:fill-box;transform-origin:center;animation:osRipple 3s ease-out infinite}
.os-drop{transform-box:fill-box;transform-origin:center bottom;animation:osDrop 3.2s ease-in-out infinite}
.os-bloom{transform-box:fill-box;transform-origin:center;animation:osBloom .9s cubic-bezier(.2,1.3,.3,1) both}
.os-sweep{stroke-dasharray:240;stroke-dashoffset:240;animation:osSweep 3.2s ease-in-out infinite alternate}
@media (prefers-reduced-motion:reduce){.onb-enter,.os-spin,.os-spinr,.os-breathe,.os-tw,.os-glow,.os-rise,.os-ripple,.os-drop,.os-bloom,.os-sweep{animation:none}.os-rise,.os-ripple{opacity:.6}}
.jcard-art{position:relative;height:148px;display:grid;place-items:center;overflow:hidden;border-bottom:1px solid var(--line);
  background:radial-gradient(circle at 50% 32%,#4a3410,#2a1c46 60%,#140e26)}
.deity-emblem{position:relative;width:104px;height:104px;border-radius:50%;overflow:hidden;display:grid;place-items:center;
  border:2px solid #ffffff22;box-shadow:0 10px 30px -12px #000,0 0 0 6px #ffffff08}
.deity-emblem .deity-glyph{position:relative;z-index:1;color:var(--gold);filter:drop-shadow(0 0 10px #f5c97766)}
.deity-emblem .deity-glyph .i{width:40px;height:40px}
.deity-emblem img{position:absolute;inset:0;z-index:2;width:100%;height:100%;object-fit:cover}
.deity-emblem.lg{width:150px;height:150px}
.deity-emblem.lg .deity-glyph .i{width:58px;height:58px}
.jcard-badge{position:absolute;top:10px;right:10px;z-index:3;background:var(--a);color:#15101f;font-size:10px;font-weight:800;
  text-transform:uppercase;letter-spacing:.05em;padding:3px 9px;border-radius:999px}
.jcard-body{padding:14px 15px 15px}
.jcard-title{font-weight:800;font-size:16px}.jcard-title span{color:var(--muted);font-weight:600}
.jcard-sub{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-top:4px}
.jcard-desc{font-family:var(--serif);font-size:13.5px;color:#cbbfe6;line-height:1.55;margin-top:9px}
/* --- journey detail / preview screen --- */
.jdetail{text-align:center;position:relative;overflow:hidden;border:1px solid color-mix(in srgb,var(--a) 30%,var(--line));
  background:linear-gradient(165deg,color-mix(in srgb,var(--a) 11%,#15111f),#110d1b 76%)}
.jdetail:before{content:"";position:absolute;inset:0;pointer-events:none;opacity:.45;background:radial-gradient(120% 75% at 50% -8%,color-mix(in srgb,var(--a) 30%,transparent),transparent 56%)}
.jdetail>*{position:relative;z-index:1}
.jd-eyebrow{display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.13em;color:var(--a);margin-bottom:2px}
.jd-eyebrow .i{width:13px;height:13px}
.jd-art{display:flex;justify-content:center;margin:4px 0 14px}
.jd-title{margin:0;font-size:26px}
.jd-subtitle{font-family:var(--serif);font-style:italic;color:#cbbfe6;font-size:16px;margin-top:2px}
.jd-chips{display:flex;flex-wrap:wrap;gap:7px;justify-content:center;margin:14px 0 4px}
.jd-chips span{display:inline-flex;align-items:center;gap:5px;font-size:11px;color:var(--muted);background:#ffffff08;border:1px solid #ffffff12;border-radius:999px;padding:5px 10px}
.jd-chips .i{width:13px;height:13px}
.jd-desc{font-family:var(--serif);font-size:15px;line-height:1.6;color:#e2dcf2;text-align:left;margin:14px 2px 16px}
.jd-head{text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin:0 2px 8px}
.jd-steps{text-align:left;margin:0 0 4px;padding-left:20px}
.jd-steps li{font-size:14px;color:#d9cff2;margin:5px 0;font-family:var(--serif)}
.jd-prompt{display:flex;gap:8px;text-align:left;background:#ffffff07;border:1px solid #ffffff12;border-radius:12px;padding:11px 12px;margin:14px 0 2px;font-family:var(--serif);font-style:italic;font-size:14px;color:#cbbfe6}
.jd-sound{margin-top:16px}
.jd-sound-lbl{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted,#9a93b8);text-align:center;margin-bottom:9px}
.jd-prompt .i{flex:none;margin-top:2px;width:15px;height:15px}
.lesson-card.done .lesson-img{filter:saturate(1.05)}
.lesson-seal{position:absolute;z-index:2;top:6px;left:6px;width:22px;height:22px;border-radius:50%;background:#0f2a20cc;border:1px solid #6ee7b7;display:grid;place-items:center;color:#6ee7b7}
.lesson-seal .i{width:12px;height:12px}
.lesson-card.soon{cursor:default;opacity:.62}
.lesson-card.soon:hover{border-color:var(--line)}
.lesson-card.soon .lesson-imic{color:var(--muted)}
.soon-tag{color:var(--muted)!important}
.trk-head{margin:20px 2px 10px;padding-left:11px;border-left:3px solid var(--a)}
.trk-name{font-weight:800;font-size:16px;color:#f1ecff}
.trk-sub{font-family:var(--serif);font-size:12.5px;color:var(--muted);line-height:1.45;margin-top:2px}
/* Journeys tab — journey cards + journey-detail lesson rows */
.jrny-grid{display:flex;flex-direction:column;gap:30px}
.jrny-card{display:flex;align-items:stretch;gap:0;text-align:left;border:1px solid color-mix(in srgb,var(--a) 34%,var(--line));border-radius:18px;overflow:hidden;cursor:pointer;padding:0;position:relative;
  background:linear-gradient(135deg,color-mix(in srgb,var(--a) 13%,#15111f),#110d1b 72%);
  box-shadow:0 12px 32px -20px color-mix(in srgb,var(--a) 85%,#000);transition:transform .14s,border-color .15s}
.jrny-card:active{transform:scale(.995)}
.jrny-art{flex:none;width:114px;display:grid;place-items:center;overflow:hidden;position:relative;
  background:radial-gradient(circle at 50% 38%,color-mix(in srgb,var(--a) 32%,#140f24),#120d20 78%);border-right:1px solid color-mix(in srgb,var(--a) 20%,var(--line))}
.jrny-art:after{content:"";position:absolute;inset:0;pointer-events:none;opacity:.55;background:radial-gradient(circle at 50% 36%,color-mix(in srgb,var(--a) 34%,transparent),transparent 62%)}
.jrny-art .i,.jrny-art svg{position:relative;z-index:1;width:42px;height:42px}
/* most recently practiced journey — pulsing glow so you can pick up where you left off */
.jrny-card.recent{border-color:color-mix(in srgb,var(--a) 62%,transparent);animation:jrnyPulse 2.4s ease-in-out infinite}
.jrny-card.recent .jrny-art:after{opacity:.9;animation:jrnyArt 2.4s ease-in-out infinite}
.jrny-tag{position:absolute;top:9px;right:10px;z-index:2;font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
  color:var(--a);background:color-mix(in srgb,var(--a) 15%,#0c0a14);border:1px solid color-mix(in srgb,var(--a) 45%,transparent);
  border-radius:999px;padding:3px 8px}
@keyframes jrnyPulse{0%,100%{box-shadow:0 12px 32px -20px color-mix(in srgb,var(--a) 85%,#000),0 0 0 0 color-mix(in srgb,var(--a) 40%,transparent)}
  50%{box-shadow:0 12px 30px -18px color-mix(in srgb,var(--a) 95%,#000),0 0 22px 2px color-mix(in srgb,var(--a) 42%,transparent)}}
@keyframes jrnyArt{0%,100%{opacity:.55}50%{opacity:1}}
@media (prefers-reduced-motion:reduce){.jrny-card.recent,.jrny-card.recent .jrny-art:after{animation:none}}
.jrny-body{flex:1;min-width:0;padding:13px 14px 13px 15px}
.jrny-name{font-weight:800;font-size:16.5px;color:#f1ecff;letter-spacing:-.01em}
.jrny-sub{font-family:var(--serif);font-size:12.5px;color:var(--muted);line-height:1.4;margin-top:2px}
.jrny-bar{height:6px;border-radius:99px;background:#ffffff12;overflow:hidden;margin:11px 0 6px}
.jrny-bar>i{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,var(--a),color-mix(in srgb,var(--a) 50%,#ffffff));box-shadow:0 0 9px -2px var(--a);transition:width .4s}
.jrny-meta{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.jrny-next{display:flex;align-items:center;gap:6px;font-size:12.5px;font-weight:700;color:#efe6ff;margin-top:7px}
.jrny-next .i{width:14px;height:14px;color:var(--a)}
.jrny-go{flex:none;display:grid;place-items:center;width:40px;color:var(--a);opacity:.9}
.jrny-go .i{width:16px;height:16px}
/* journey-detail hero — accent-glow header with medallion */
.jrh{position:relative;overflow:hidden;border:1px solid color-mix(in srgb,var(--a) 34%,var(--line));border-radius:20px;padding:22px 16px;margin:2px 2px 18px;text-align:center;
  background:linear-gradient(165deg,color-mix(in srgb,var(--a) 14%,#15111f),#110d1b 74%)}
.jrh:before{content:"";position:absolute;inset:0;pointer-events:none;opacity:.5;background:radial-gradient(120% 80% at 50% -10%,color-mix(in srgb,var(--a) 34%,transparent),transparent 58%)}
.jrh>*{position:relative;z-index:1}
.jrh-med{margin:0 auto 10px;width:72px;height:72px}
.jrh-med .deity-emblem{width:72px;height:72px}
.jrh-med .deity-emblem .deity-glyph .i{width:34px;height:34px}
.jrh-eyebrow{display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.14em;color:var(--a)}
.jrh-eyebrow .i{width:13px;height:13px}
.jrh-name{font-family:var(--serif);font-size:23px;font-weight:600;color:#f3eeff;margin:6px 0 2px;line-height:1.1}
.jrh-sub{font-family:var(--serif);font-style:italic;font-size:13.5px;color:var(--muted);margin:0 auto 13px;max-width:34ch;line-height:1.45}
.jrh-bar{height:7px;border-radius:999px;background:#ffffff12;overflow:hidden;max-width:260px;margin:0 auto}
.jrh-bar>i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,var(--a),color-mix(in srgb,var(--a) 50%,#ffffff));box-shadow:0 0 10px -2px var(--a);transition:width .4s}
.jrh-count{font-size:12px;color:var(--muted);margin-top:9px;letter-spacing:.02em}
.lj-list{display:flex;flex-direction:column;gap:11px}
.lj-row{display:flex;align-items:center;gap:13px;text-align:left;width:100%;background:#140f24;border:1px solid var(--line);border-radius:14px;padding:15px 14px;cursor:pointer}
/* lesson-detail modal (opened from the journey list) */
/* lesson preview — a bottom sheet pinned to the bottom edge (can't float off the top) */
.lmodal-ov{position:fixed;inset:0;z-index:80;display:flex;align-items:flex-end;justify-content:center;
  background:rgba(5,4,10,.62);backdrop-filter:blur(4px);opacity:0;transition:opacity .24s}
.lmodal-ov.show{opacity:1}
.lmodal{position:relative;width:100%;max-width:520px;max-height:76vh;max-height:76dvh;overflow-y:auto;-webkit-overflow-scrolling:touch;
  transform:translateY(100%);transition:transform .3s cubic-bezier(.2,.85,.25,1)}
.lmodal-ov.show .lmodal{transform:translateY(0)}
.lmodal .card{margin:0;border-radius:22px 22px 0 0;border-bottom:0;padding-bottom:calc(20px + env(safe-area-inset-bottom))}
.lmodal-x{position:absolute;top:12px;right:12px;z-index:5;width:34px;height:34px;border-radius:50%;border:1px solid var(--line);background:#00000055;color:#d8d0ef;display:grid;place-items:center;cursor:pointer}
.lmodal-x .i{width:16px;height:16px}
.lj-row:active{transform:scale(.995)}
.lj-row.next{border-color:var(--gold);box-shadow:0 0 0 1px var(--gold) inset,0 0 16px -6px var(--gold)}
.lj-row.done{opacity:.82}
.lj-row.soon{opacity:.6;cursor:default}
.lj-num{flex:none;width:30px;height:30px;border-radius:50%;display:grid;place-items:center;background:#201839;border:1px solid var(--line);color:var(--a);font-weight:800;font-size:13px}
.lj-row.done .lj-num{color:#7ee0b0}
.lj-num .i{width:15px;height:15px}
/* per-lesson emblem icon (journey detail rows) */
.lj-ico{flex:none;position:relative;width:40px;height:40px}
/* distinct per-lesson glyph emblem — accent-tinted, one icon per lesson */
.lj-emb{position:relative;width:40px;height:40px;border-radius:50%;display:grid;place-items:center;
  background:radial-gradient(circle at 50% 36%,color-mix(in srgb,var(--a) 34%,#1b1530),#130e22);
  border:1px solid color-mix(in srgb,var(--a) 50%,var(--line))}
.lj-emb .i{width:21px;height:21px;color:var(--a);filter:drop-shadow(0 0 5px color-mix(in srgb,var(--a) 55%,transparent))}
.lj-emb.lg{width:54px;height:54px;border-width:1.5px}
.lj-emb.lg .i{width:28px;height:28px}
.lj-row.next .lj-emb{box-shadow:0 0 0 1px var(--gold),0 0 12px -3px var(--gold)}
.lj-row.done .lj-emb{opacity:.72}
.lj-ico.lock{display:grid;place-items:center;border-radius:50%;background:#201839;border:1px solid var(--line);color:var(--muted)}
.lj-ico.lock .i{width:16px;height:16px}
.deity-emblem.ljm{width:40px;height:40px;border-width:1px}
.deity-emblem.ljm .deity-glyph .i{width:19px;height:19px}
.lj-row.next .deity-emblem.ljm{box-shadow:0 0 0 1px var(--gold),0 0 12px -3px var(--gold)}
.lj-step{position:absolute;bottom:-3px;right:-3px;min-width:16px;height:16px;padding:0 3px;border-radius:9px;background:#201839;border:1px solid var(--line);color:#cbbfe6;font-weight:800;font-size:10px;line-height:14px;text-align:center}
.lj-row.done .lj-step{display:none}
.lj-seal{position:absolute;z-index:3;top:-4px;left:-4px;width:19px;height:19px;border-radius:50%;background:#0f2a20;border:1px solid #6ee7b7;display:grid;place-items:center;color:#6ee7b7}
.lj-seal .i{width:11px;height:11px}
.lj-main{flex:1;min-width:0}
.lj-title{display:block;font-weight:700;font-size:14.5px;color:#f1ecff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lj-sub{display:block;font-size:11.5px;color:var(--muted);margin-top:2px}
.lj-badge{flex:none;background:var(--gold);color:#15101f;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.04em;padding:4px 9px;border-radius:99px}
.lj-go{flex:none;color:var(--a);opacity:.7}.lj-go .i{width:16px;height:16px}
.lesson-bg{position:fixed;inset:0;z-index:0;background-size:cover;background-position:center 30%;opacity:.26;filter:blur(2px) saturate(1.15);pointer-events:none;-webkit-mask-image:radial-gradient(ellipse 120% 85% at center 38%,#000 42%,transparent 82%);mask-image:radial-gradient(ellipse 120% 85% at center 38%,#000 42%,transparent 82%)}
.lesson-bg:after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,transparent,#0b0a12cc 72%,#0b0a12)}
.lesson-top{margin:6px 2px 2px;position:relative;z-index:1;text-align:center}
.lesson-ttl{font-size:19px;font-weight:800;letter-spacing:.2px}
.lesson-ttl .muted{font-weight:600}
.lesson-step{font-size:12px;margin-top:4px;text-transform:uppercase;letter-spacing:.08em}
.lesson-teach{font-family:var(--serif);font-size:16px;line-height:1.6;color:#e8e2f2;text-align:center;padding:4px 12px;max-width:540px;margin:4px auto 0;min-height:92px}
.lesson-foot{display:flex;align-items:center;gap:12px;margin-top:12px}
/* full-viewport session layouts (nav is hidden during a sit) — break out of #app's
   nav padding and center the content so nothing floats to the top */
.sit-screen,.lesson-screen{min-height:100dvh;display:flex;flex-direction:column;position:relative;z-index:1;
  margin:calc(-1*(env(safe-area-inset-top) + 8px)) -16px calc(-1*(96px + env(safe-area-inset-bottom))) -16px;
  padding:calc(env(safe-area-inset-top) + 12px) 20px calc(env(safe-area-inset-bottom) + 16px)}
.sit-screen{justify-content:center;align-items:center;text-align:center}
.sit-screen .end-wrap{width:100%;max-width:340px;margin-top:28px}
.lesson-screen .lesson-mid{flex:1 1 auto;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:2px;min-height:0}
.lesson-screen .lesson-foot{margin-top:auto}
.companion .cph{width:26px;height:26px;border-radius:50%;object-fit:cover;border:1px solid #4a3d6e;box-shadow:0 0 8px #f5c97755}
.motebal{margin-left:auto;display:inline-flex;align-items:center;gap:5px;font-size:13px;font-weight:700;color:var(--gold);
  background:#1a1330;border:1px solid #3a2d5e;border-radius:999px;padding:4px 11px}
.motebal .i{width:14px;height:14px}
/* companions */
.comp-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:4px}
.comp{position:relative;border:1px solid var(--line);border-radius:16px;padding:16px 8px 10px;text-align:center;cursor:pointer;background:#13101f;overflow:hidden;transition:transform .16s}
.comp:active{transform:scale(.95)}
.comp.owned{border-color:var(--el);box-shadow:0 0 16px -8px var(--el)}
.comp.eq{box-shadow:0 0 18px -6px var(--el)}
.comp-eqtag{position:absolute;top:0;left:0;right:0;font-size:9px;letter-spacing:.08em;text-transform:uppercase;
  background:var(--el);color:#120d1e;font-weight:800;padding:2px}
.comp-ic{height:50px;display:grid;place-items:center;color:var(--el);margin-top:4px}
.comp-ic .i{width:40px;height:40px;transition:filter .3s,transform .3s}
.comp.owned .comp-ic .i{filter:drop-shadow(0 0 5px var(--el))}
.comp-ic.s1 .i{filter:drop-shadow(0 0 7px var(--el));transform:scale(1.05)}
.comp-ic.s2 .i{filter:drop-shadow(0 0 10px var(--el));transform:scale(1.12)}
.comp-ic.s3 .i{filter:drop-shadow(0 0 14px var(--el)) drop-shadow(0 0 22px var(--el));transform:scale(1.18)}
.comp.locked{opacity:.78}
.comp.locked .comp-ic{color:var(--muted)}
.comp-nm{font-size:12px;font-weight:600;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.comp-st{font-size:11px;margin-top:3px;color:var(--muted);display:flex;align-items:center;justify-content:center;gap:3px}
.comp.owned .comp-st{color:var(--el)}
.ach-ic.s3 .achbig{filter:drop-shadow(0 0 16px currentColor) drop-shadow(0 0 28px currentColor)}
.ach-ic.s2 .achbig{filter:drop-shadow(0 0 14px currentColor)}
/* shop */
.shop-row{display:flex;align-items:center;gap:12px;padding:12px;border:1px solid var(--line);border-radius:16px;background:#13101f;margin:10px 0}
.shop-row.owned{opacity:.75}
.shop-row.locked{opacity:.7}
.shop-ic{width:46px;height:46px;flex:none;border-radius:12px;background:#0f0d18;display:grid;place-items:center;border:1px solid var(--rc)}
.shop-ic .i{width:26px;height:26px}
.shop-nm{font-weight:700;display:flex;align-items:center;gap:7px}
.shop-buy{flex:none}
/* artifacts */
.art-row{display:flex;align-items:center;gap:13px;padding:13px;border:1px solid var(--line);border-radius:16px;
  background:linear-gradient(135deg,#15111f,#120e1c);margin:10px 0;cursor:pointer;transition:border-color .15s,transform .12s}
.art-row:active{transform:scale(.99)}
.art-row:hover{border-color:#3a3550}
.art-row.owned{border-color:var(--rc);box-shadow:0 0 16px -9px var(--rc)}
.art-ic{position:relative;overflow:hidden;width:52px;height:52px;flex:none;border-radius:50%;display:grid;place-items:center;
  background:radial-gradient(circle at 50% 38%,#241a3a,#100c1c);border:1px solid var(--rc);box-shadow:0 0 14px -7px var(--rc)}
.art-ic .i{width:28px;height:28px}
.art-img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;border-radius:50%}
.art-cimg{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:114px;height:114px;object-fit:cover;
  border-radius:20px;box-shadow:0 0 28px -6px var(--rc),0 0 0 1px #ffffff14}
.art-nm{font-weight:700;font-size:15px}
.art-origin{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-top:2px}
.art-sub{font-size:12.5px;color:#cbbfe6;margin-top:3px}.art-sub b{color:var(--gold)}
.art-act{flex:none}
.art-pill{display:inline-flex;align-items:center;gap:4px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;
  border:1px solid var(--line);border-radius:999px;padding:4px 10px}
.art-pill .i{width:12px;height:12px}
/* altar scene */
.altar-stage{position:relative;margin:8px 0 2px;border-radius:18px;overflow:hidden;border:1px solid var(--line);
  background:radial-gradient(120% 95% at 50% 22%,#1a1530,#0c0a16)}
.altar-svg{display:block;width:100%;height:auto}
.altar-stage.complete{box-shadow:inset 0 0 50px -12px #f5c97755,0 0 34px -14px var(--gold);border-color:#5a4826}
.apiece{transition:opacity .18s}
.apiece:active{opacity:.6}
/* icons */
.i{width:1.15em;height:1.15em;display:inline-block;vertical-align:-.2em;flex:none;transition:transform .2s ease,filter .2s ease}
.i.g{color:var(--gold)}.i.p{color:var(--purple)}.i.pink{color:var(--pink)}.i.flame{color:#fb923c}
/* gradient-filled variants (stroke + fill follow the gradient) */
.i.grad-gold{stroke:url(#gGold)}.i.grad-gold [fill="currentColor"]{fill:url(#gGold)}
.i.grad-aur{stroke:url(#gAur)}.i.grad-aur [fill="currentColor"]{fill:url(#gAur)}
.i.grad-pur{stroke:url(#gPur)}.i.grad-pur [fill="currentColor"]{fill:url(#gPur)}
.i.grad-flame{stroke:url(#gFlame)}.i.grad-flame [fill="currentColor"]{fill:url(#gFlame)}
.i.grad-blue{stroke:url(#gBlue)}.i.grad-blue [fill="currentColor"]{fill:url(#gBlue)}
.i.grad-slate{stroke:url(#gSlate)}.i.grad-slate [fill="currentColor"]{fill:url(#gSlate)}
/* glow */
.i.glow{filter:drop-shadow(0 0 4px currentColor)}
.i.glow2{filter:drop-shadow(0 0 7px currentColor) drop-shadow(0 0 14px currentColor)}
.i.mark{width:27px;height:27px;color:var(--gold);stroke:url(#gGold);filter:drop-shadow(0 0 7px #f5c977cc);animation:markpulse 4s ease-in-out infinite}
.i.mark circle{fill:url(#gGold)}
.i.nav{width:22px;height:22px}
.i.lg{width:46px;height:46px;filter:drop-shadow(0 0 16px currentColor)}
@keyframes markpulse{0%,100%{filter:drop-shadow(0 0 5px #f5c97799)}50%{filter:drop-shadow(0 0 12px #f5c977ee)}}
.brand .mark{display:inline-flex}
/* lumen brand orb mark (shared logo) */
.lmark{display:inline-block;vertical-align:-.25em;flex:none}
.lmark.mark{width:31px;height:31px;filter:drop-shadow(0 0 8px rgba(245,201,119,.5));animation:markpulse 4.5s ease-in-out infinite}
.lmark.lg{width:48px;height:48px;filter:drop-shadow(0 0 18px rgba(245,201,119,.45))}
.lmark.xl{width:92px;height:92px;filter:drop-shadow(0 0 30px rgba(245,201,119,.5))}
.finale-mark .lmark{width:72px;height:72px}
.onb-ic .lmark{width:96px;height:96px}
.onb-brand .lmark{width:24px;height:24px}
.hdr-mark svg.lmark{width:100%;height:100%}
.chip .big .i{width:26px;height:26px;color:#cbb5e8;transition:transform .2s ease,filter .2s ease}
.chip.sel .big .i{color:#f0e6ff;filter:drop-shadow(0 0 7px var(--purple));transform:scale(1.12)}
.lb-row .rk .i{width:18px;height:18px}
.lb-row .rk .medal{width:20px;height:20px;filter:drop-shadow(0 0 5px currentColor)}
.pill .i{width:15px;height:15px;filter:drop-shadow(0 0 4px currentColor)}
nav button .ic .i{width:22px;height:22px}
nav button.on .ic .i{color:var(--purple);filter:drop-shadow(0 0 7px var(--purple));transform:translateY(-1px) scale(1.1)}
.ach .e .i{filter:none}
.ach.on .e .i{filter:drop-shadow(0 0 6px var(--gold))}
/* journal intelligence: Keeper reflections + insights */
.keeper-note{margin-top:12px;padding:12px 14px;border:1px solid rgba(245,201,119,.28);border-radius:14px;background:rgba(245,201,119,.06);text-align:left}
.keeper-lbl{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--gold);display:flex;align-items:center;gap:6px}
.keeper-lbl .i{width:14px;height:14px}
.keeper-refl{margin:6px 0 0;font-family:var(--serif);font-size:15px;line-height:1.5;color:var(--text)}
.mini-refl{margin-top:8px;padding-top:8px;border-top:1px dashed rgba(245,201,119,.25);font-family:var(--serif);font-size:13.5px;line-height:1.45;color:#d9cfa0;display:flex;gap:7px;align-items:flex-start}
.mini-refl .i{width:14px;height:14px;flex:none;margin-top:3px;color:var(--gold)}
.insights{display:flex;flex-direction:column;gap:12px;margin-top:4px}
.ins-themes{display:flex;flex-wrap:wrap;gap:7px}
.ins-chip{font-size:12px;padding:4px 11px;border-radius:999px;border:1px solid rgba(168,85,247,.4);background:rgba(168,85,247,.1);color:#d9c2f7}
.ins-block{padding:13px 15px;border:1px solid var(--line,#2a2740);border-radius:14px;background:rgba(255,255,255,.02);text-align:left}
.ins-lbl{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);display:flex;align-items:center;gap:6px;margin-bottom:5px}
.ins-lbl .i{width:14px;height:14px}
.ins-arc{font-family:var(--serif);font-size:15px;line-height:1.5}
.ins-nudge{border-color:rgba(245,201,119,.3);background:rgba(245,201,119,.05)}
</style>
<!-- Sentry error monitoring (project loader auto-injects the DSN; buffers errors
     from first paint so onboarding/auth are covered). Release = deploy version. -->
<script src="https://js.sentry-cdn.com/7ace4c4f0dca0ac2f91f436fcb17929d.min.js" crossorigin="anonymous"></script>
<script>
  (function(){
    if(!(window.Sentry&&Sentry.onLoad))return;
    Sentry.onLoad(function(){
      Sentry.init({
        environment:"production",
        release:"__SENTRY_REL__",
        tracesSampleRate:0.0,
        ignoreErrors:["ResizeObserver loop limit exceeded","AbortError"]
      });
      Sentry.setTag("screen","boot");
    });
  })();
  // call on every screen change so an error names the screen (incl. onboarding/auth)
  window.__screen=function(name){try{window.Sentry&&Sentry.setTag&&Sentry.setTag("screen",name);}catch(e){}};
</script>
</head>
<body>
<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
  <linearGradient id="gGold" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="24" y2="24"><stop offset="0" stop-color="#ffe9b8"/><stop offset="1" stop-color="#e0953a"/></linearGradient>
  <linearGradient id="gAur" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="24" y2="24"><stop offset="0" stop-color="#f7d99a"/><stop offset=".5" stop-color="#c084fc"/><stop offset="1" stop-color="#ec4899"/></linearGradient>
  <linearGradient id="gPur" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="24" y2="24"><stop offset="0" stop-color="#d8b4fe"/><stop offset="1" stop-color="#7c3aed"/></linearGradient>
  <linearGradient id="gFlame" gradientUnits="userSpaceOnUse" x1="12" y1="24" x2="12" y2="0"><stop offset="0" stop-color="#f97316"/><stop offset="1" stop-color="#fde047"/></linearGradient>
  <linearGradient id="gBlue" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="24" y2="24"><stop offset="0" stop-color="#bfe0ff"/><stop offset="1" stop-color="#3b82f6"/></linearGradient>
  <linearGradient id="gSlate" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="24" y2="24"><stop offset="0" stop-color="#e2e8f0"/><stop offset="1" stop-color="#94a3b8"/></linearGradient>
</defs></svg>
<canvas class="stars"></canvas>
<div id="app"><div class="boot-load"><span class="spinner"></span></div></div>
<nav class="hidden" id="nav"><div class="inner">
  <button data-tab="meditate" class="on"><span class="ic"></span>Meditate</button>
  <button data-tab="lessons"><span class="ic"></span>Journeys</button>
  <button data-tab="map"><span class="ic"></span>Map</button>
  <button data-tab="leagues"><span class="ic"></span>Leagues</button>
  <button data-tab="journal"><span class="ic"></span>Journal</button>
  <button data-tab="collect"><span class="ic"></span>Collect</button>
  <button data-tab="profile"><span class="ic"></span>You</button>
</div></nav>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/bodymovin/5.12.2/lottie.min.js"></script>
<script src="/assets/orb.js?v=4" defer></script>
<script>
const $=(s,r=document)=>r.querySelector(s);
/* Diya flame loading spinner — upgrade every .spinner span into the Lottie.
   Fetched once, reused as animationData; a MutationObserver catches spinners
   injected by any later render. Falls back silently if lottie/CDN is unavailable. */
let _diyaData=null;
function _mountDiya(){
  if(!window.lottie||!_diyaData)return;
  document.querySelectorAll('.spinner:not([data-diya])').forEach(elm=>{
    elm.setAttribute('data-diya','1');
    try{window.lottie.loadAnimation({container:elm,renderer:'svg',loop:true,autoplay:true,animationData:_diyaData});}catch(e){}
  });
}
fetch('/assets/diya.json').then(r=>r.json()).then(d=>{_diyaData=d;_mountDiya();}).catch(()=>{});
try{new MutationObserver(()=>_mountDiya()).observe(document.documentElement,{childList:true,subtree:true});}catch(e){}
/* Ancient-column Lottie, recoloured per-pillar and frozen on its finished frame,
   mounted into any .pcolumn-art placeholder (data-pc = the pillar's colour). */
let _colData=null;
function _hexRgb(h){h=(h||'#f5c977').replace('#','');return [parseInt(h.slice(0,2),16)/255,parseInt(h.slice(2,4),16)/255,parseInt(h.slice(4,6),16)/255];}
function _tintCol(data,hex){const rgb=_hexRgb(hex),r=rgb[0],g=rgb[1],b=rgb[2];const cl=JSON.parse(JSON.stringify(data));
  const dark=[r*0.4,g*0.4,b*0.4],mid=[r,g,b],light=[r+(1-r)*0.65,g+(1-g)*0.65,b+(1-b)*0.65];
  (function w(o){if(Array.isArray(o))return o.forEach(w);
    if(o&&typeof o==='object'){if((o.ty==='fl'||o.ty==='st')&&o.c&&Array.isArray(o.c.k)&&o.c.k.length>=3){
      const c=o.c.k,lum=(c[0]+c[1]+c[2])/3;const n=lum<0.35?dark:(c[0]>0.7&&c[1]<0.55?mid:light);o.c.k=[n[0],n[1],n[2],c[3]!=null?c[3]:1];}
      Object.values(o).forEach(w);}})(cl.layers);return cl;}
function _mountCols(){if(!window.lottie||!_colData)return;
  document.querySelectorAll('.pcolumn-art:not([data-col])').forEach(elm=>{elm.setAttribute('data-col','1');
    try{const a=window.lottie.loadAnimation({container:elm,renderer:'svg',loop:false,autoplay:false,animationData:_tintCol(_colData,elm.getAttribute('data-pc')||'#f5c977')});
      a.addEventListener('DOMLoaded',()=>{try{a.goToAndStop(a.totalFrames-1,true);}catch(e){}});}catch(e){}});}
fetch('/assets/column.json').then(r=>r.json()).then(d=>{_colData=d;_mountCols();}).catch(()=>{});
try{new MutationObserver(()=>_mountCols()).observe(document.documentElement,{childList:true,subtree:true});}catch(e){}
const el=(h)=>{const d=document.createElement('div');d.innerHTML=h.trim();return d.firstChild;};
async function api(path,method='GET',body){
  const o={method,headers:{}};
  if(body){o.headers['Content-Type']='application/json';o.body=JSON.stringify(body);}
  const r=await fetch('api/'+path,o);
  let j={};try{j=await r.json();}catch(e){}
  if(!r.ok) throw (j.error||'Something went wrong');
  return j;
}
function toast(html,ms=2600){const t=el(`<div class="toast">${html}</div>`);document.body.appendChild(t);setTimeout(()=>t.remove(),ms);}
const fmt=(n)=>n>=1000?(n/1000).toFixed(n>=10000?0:1)+'k':''+n;

/* ---- inline SVG icon set (no asset files; currentColor-driven) ---- */
const SVGP={
  jg_shadow:'<circle cx="12" cy="12" r="8.5"/><path d="M12 3.5a8.5 8.5 0 0 0 0 17 10 10 0 0 1 0 -17Z" fill="currentColor" stroke="none"/>',
  jg_persona:'<path d="M12 3.4c3.6 0 5.6 2.9 5.6 7.6 0 5.1-2.9 9.6-5.6 9.6S6.4 16.1 6.4 11s2-7.6 5.6-7.6Z"/><path d="M8.6 10.5c.6-.7 1.7-.7 2.3 0"/><path d="M13.1 10.5c.6-.7 1.7-.7 2.3 0"/><path d="M9.5 14.7c1.5 1.2 3.5 1.2 5 0"/>',
  jg_anima:'<circle cx="9.4" cy="12" r="5.6"/><circle cx="14.6" cy="12" r="5.6"/><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none"/>',
  jg_self:'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.3"/><circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none"/><path d="M12 3v3.4M12 17.6v3.4M3 12h3.4M17.6 12h3.4"/>',
  lumen:'<circle cx="12" cy="12" r="4" fill="currentColor" stroke="none"/><g><line x1="12" y1="2.5" x2="12" y2="5"/><line x1="12" y1="19" x2="12" y2="21.5"/><line x1="2.5" y1="12" x2="5" y2="12"/><line x1="19" y1="12" x2="21.5" y2="12"/><line x1="5.6" y1="5.6" x2="7.3" y2="7.3"/><line x1="16.7" y1="16.7" x2="18.4" y2="18.4"/><line x1="18.4" y1="5.6" x2="16.7" y2="7.3"/><line x1="7.3" y1="16.7" x2="5.6" y2="18.4"/></g>',
  meditate:'<circle cx="12" cy="4.8" r="2.4" fill="currentColor" stroke="none"/><path d="M12 8.2c-2.3.2-3.9 1.7-4.2 4.5"/><path d="M12 8.2c2.3.2 3.9 1.7 4.2 4.5"/><path d="M4.6 18c1.9-3.1 4.4-4.1 7.4-4.1s5.5 1 7.4 4.1c.4.6-.1 1.4-.8 1.4H5.4c-.7 0-1.2-.8-.8-1.4Z" fill="currentColor" stroke="none"/><circle cx="7.8" cy="12.9" r="1.05" fill="currentColor" stroke="none"/><circle cx="16.2" cy="12.9" r="1.05" fill="currentColor" stroke="none"/>',
  medlotus:'<circle cx="12" cy="4.3" r="2.15" fill="currentColor" stroke="none"/><path d="M12 7c-2.1 0-3.8 1.5-4.9 4"/><path d="M12 7c2.1 0 3.8 1.5 4.9 4"/><path d="M9.3 13c.7.9 1.6 1.4 2.7 1.4s2-.5 2.7-1.4"/><path d="M12 15.4c-1.5-1.7-3.3-2.3-5.4-2 .4 2.4 2.4 4 5.4 4s5-1.6 5.4-4c-2.1-.3-3.9.3-5.4 2Z" fill="currentColor" stroke="none"/><circle cx="6.5" cy="12.6" r=".95" fill="currentColor" stroke="none"/><circle cx="17.5" cy="12.6" r=".95" fill="currentColor" stroke="none"/>',
  globe:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.6 2.6 2.6 15.4 0 18M12 3c-2.6 2.6-2.6 15.4 0 18"/>',
  trophy:'<path d="M8 4h8v4.5a4 4 0 0 1-8 0V4Z"/><path d="M8 5.2H5a2 2 0 0 0 0 4h1.2M16 5.2h3a2 2 0 0 1 0 4h-1.2"/><path d="M12 12.5V16M9.2 20h5.6M10 20c0-1.4 .9-2 2-2s2 .6 2 2"/>',
  book:'<path d="M5 4.5h10.5a2 2 0 0 1 2 2V20H7a2 2 0 0 1-2-2V4.5Z"/><path d="M17.5 17H7a2 2 0 0 0-2 2"/><path d="M8.5 8.5h6M8.5 11.5h5"/>',
  spark:'<path d="M12 3c.7 5 3 7.3 8 8-5 .7-7.3 3-8 8-.7-5-3-7.3-8-8 5-.7 7.3-3 8-8Z" fill="currentColor" stroke="none"/>',
  flame:'<path d="M12 3c3 3 5 5.5 5 9a5 5 0 0 1-10 0c0-1.9.7-3.1 1.9-4.3C9 9.2 9.6 10 10.1 10.6 10.6 8 11 5.5 12 3Z" fill="currentColor" stroke="none"/>',
  live:'<circle cx="12" cy="12" r="3.2" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="7" opacity=".55"/>',
  rain:'<path d="M7.2 14.5a4.3 4.3 0 0 1-.4-8.6 5.8 5.8 0 0 1 11.1 1.4A3.4 3.4 0 0 1 17 14.5"/><line x1="8.5" y1="17.5" x2="7.5" y2="20"/><line x1="12" y1="17.5" x2="11" y2="21"/><line x1="15.5" y1="17.5" x2="14.5" y2="20"/>',
  forest:'<path d="M12 3 7 11h3l-3 5h10l-3-5h3L12 3Z" fill="currentColor" stroke="none"/><line x1="12" y1="16" x2="12" y2="21"/>',
  ocean:'<path d="M3 9c2 0 2.2-2 4.5-2S10 9 12 9s2.2-2 4.5-2S19 9 21 9"/><path d="M3 14c2 0 2.2-2 4.5-2S10 14 12 14s2.2-2 4.5-2S19 14 21 14"/><path d="M3 19c2 0 2.2-2 4.5-2S10 19 12 19s2.2-2 4.5-2S19 19 21 19"/>',
  space:'<circle cx="12" cy="12" r="3" fill="currentColor" stroke="none"/><ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(-25 12 12)"/>',
  silence:'<circle cx="12" cy="12" r="8.5" opacity=".5"/><circle cx="12" cy="12" r="2.4" fill="currentColor" stroke="none"/>',
  calm:'<path d="M3 12c2 0 2.4-3 4.5-3S10 12 12 12s2.4-3 4.5-3S19 12 21 12"/><path d="M3 17c2 0 2.4-3 4.5-3S10 17 12 17s2.4-3 4.5-3S19 17 21 17"/>',
  bolt:'<path d="M13 2 4 14h6l-1 8 9-12h-6l1-8Z" fill="currentColor" stroke="none"/>',
  fog:'<path d="M4 8c2-1.6 4.5 1.6 7 0s4-1.6 6 0"/><path d="M5 12c2-1.6 4.5 1.6 7 0s4-1.6 6 0"/><path d="M4 16c2-1.6 4.5 1.6 7 0s4-1.6 6 0"/>',
  moon:'<path d="M20 14.5A8 8 0 1 1 9.5 4 6.5 6.5 0 0 0 20 14.5Z" fill="currentColor" stroke="none"/>',
  sunrise:'<line x1="3" y1="19" x2="21" y2="19"/><path d="M7.5 19a4.5 4.5 0 0 1 9 0"/><line x1="12" y1="4" x2="12" y2="8"/><line x1="4.8" y1="10.8" x2="6.2" y2="12.2"/><line x1="19.2" y1="10.8" x2="17.8" y2="12.2"/>',
  season:'<path d="M5.5 18.5c-1.3-7 2.7-14.5 14-15.5 1.1 9.3-3 15.6-11.2 16.1-1 .06-1.9-.1-2.8-.6Z"/><path d="M6.4 17.6C10.4 13.9 14.5 11 18 9.2"/><path d="M8.9 15.6c.2-1.7 1-3.1 2.2-4.2M11.3 13.4c.3-1.6 1.2-2.9 2.4-3.7M7.6 16.8c-.3-1.3-.9-2.3-1.8-3" opacity=".65"/>',
  jdeep:'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="6.1" opacity=".45"/><path d="M12 3.4 13.25 10.75 20.6 12 13.25 13.25 12 20.6 10.75 13.25 3.4 12 10.75 10.75Z" fill="currentColor" stroke="none"/><path d="M12 7 12.55 11.45 17 12 12.55 12.55 12 17 11.45 12.55 7 12 11.45 11.45Z" opacity=".55"/><circle cx="12" cy="12" r="1.15" fill="currentColor" stroke="none"/>',
  jdaily:'<path d="M12 6.4C9.6 5 6.6 4.8 4.4 5.5V18c2.1-.7 5.1-.5 7.6 1 2.5-1.5 5.5-1.7 7.6-1V5.5c-2.2-.7-5.2-.5-7.6.9Z"/><path d="M12 6.4V19" opacity=".7"/><path d="M6.3 8.6h3.2M6.3 11h3.2M6.3 13.4h3.2M14.5 8.6h3.2M14.5 11h3.2M14.5 13.4h3.2" opacity=".6"/>',
  flag:'<line x1="6" y1="3" x2="6" y2="21"/><path d="M6 4h11l-2 3 2 3H6Z" fill="currentColor" stroke="none"/>',
  target:'<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none"/>',
  pin:'<path d="M12 21s7-6.5 7-12a7 7 0 0 0-14 0c0 5.5 7 12 7 12Z"/><circle cx="12" cy="9" r="2.5" fill="currentColor" stroke="none"/>',
  up:'<line x1="12" y1="19" x2="12" y2="6"/><path d="M6 11l6-6 6 6"/>',
  share:'<path d="M12 3v12"/><path d="M8.5 6.5 12 3l3.5 3.5"/><path d="M6 11H5a1 1 0 0 0-1 1v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7a1 1 0 0 0-1-1h-1"/>',
  check:'<path d="M5 12.5l4.5 4.5L19 6.5"/>',
  clock:'<circle cx="12" cy="12.5" r="8"/><path d="M12 8v4.5l3.2 1.9"/><path d="M9 2.8h6"/><path d="M12 2.8v1.7"/>',
  seal:'<circle cx="12" cy="12" r="8.6"/><circle cx="12" cy="12" r="6.1" stroke-dasharray="0.4 2" opacity=".75"/><path d="M12 15.7c-2.6 0-4.6-1.6-4.6-3.2 1.2 0 2 .3 2.6.8C9.4 11.5 10.4 9.9 12 8.5c1.6 1.4 2.6 3 2 4.8.6-.5 1.4-.8 2.6-.8 0 1.6-2 3.2-4.6 3.2Z" fill="currentColor" stroke="none"/>',
  glow:'<circle cx="12" cy="12" r="3.2" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="5.8" opacity=".85"/><circle cx="12" cy="12" r="8.6" opacity=".45"/>',
  flare:'<circle cx="12" cy="12" r="2.7" fill="currentColor" stroke="none"/><path d="M12 2.4v4.3M12 17.3v4.3M3.5 7.2l3.7 2.1M16.8 14.7l3.7 2.1M20.5 7.2l-3.7 2.1M7.2 14.7l-3.7 2.1"/>',
  beacon:'<circle cx="12" cy="5" r="2.3" fill="currentColor" stroke="none"/><path d="M12 7.6 6 20h12L12 7.6Z" opacity=".5"/><path d="M9 15h6"/>',
  nova:'<path d="M12 2l1.9 5.6L19 4.8l-2.4 5.3L22 12l-5.4 1.9L19 19.2l-5.3-2.4L12 22l-1.9-5.2L4.8 19l2.4-5.3L2 12l5.2-1.9L4.8 4.8l5.3 2.4L12 2Z" fill="currentColor" stroke="none"/>',
  star:'<path d="M12 3l2.6 5.5 6 .8-4.4 4.1 1.1 5.9L12 16.6 6.7 19.3l1.1-5.9L3.4 9.3l6-.8L12 3Z" fill="currentColor" stroke="none"/>',
  lotus:'<path d="M12 20c-4.2 0-7.5-2.6-7.5-5.2 2 0 3.2.5 4.2 1.3C8 13 9.6 10.2 12 7.5c2.4 2.7 4 5.5 3.3 8.6 1-.8 2.2-1.3 4.2-1.3C19.5 17.4 16.2 20 12 20Z" fill="currentColor" stroke="none"/>',
  lock:'<rect x="5" y="10.5" width="14" height="9.5" rx="2.2"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/><circle cx="12" cy="15" r="1.4" fill="currentColor" stroke="none"/>',
  close:'<line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/>',
  play:'<path d="M7 4.5 19 12 7 19.5V4.5Z" fill="currentColor" stroke="none"/>',
  stop:'<rect x="6" y="6" width="12" height="12" rx="2.5" fill="currentColor" stroke="none"/>',
  sound:'<path d="M4 9.5v5h3.5L12 18V6L7.5 9.5H4Z" fill="currentColor" stroke="none"/><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/>',
  waveform:'<line x1="3.5" y1="10.5" x2="3.5" y2="13.5"/><line x1="7" y1="8" x2="7" y2="16"/><line x1="10.5" y1="4.5" x2="10.5" y2="19.5"/><line x1="14" y1="7" x2="14" y2="17"/><line x1="17.5" y1="9.5" x2="17.5" y2="14.5"/><line x1="21" y1="11" x2="21" y2="13"/>',
  mute:'<path d="M4 9.5v5h3.5L12 18V6L7.5 9.5H4Z" fill="currentColor" stroke="none"/><line x1="16" y1="9.5" x2="21" y2="14.5"/><line x1="21" y1="9.5" x2="16" y2="14.5"/>',
  compass:'<circle cx="12" cy="12" r="9"/><path d="M15.6 8.4 13.2 13l-4.8 2.6L10.8 11l4.8-2.6Z" fill="currentColor" stroke="none"/>',
  chat:'<path d="M4 5.5h16a1.5 1.5 0 0 1 1.5 1.5v7.5a1.5 1.5 0 0 1-1.5 1.5H9.5L5 20v-4H4a1.5 1.5 0 0 1-1.5-1.5V7A1.5 1.5 0 0 1 4 5.5Z"/><circle cx="8.5" cy="11" r="1" fill="currentColor" stroke="none"/><circle cx="12" cy="11" r="1" fill="currentColor" stroke="none"/><circle cx="15.5" cy="11" r="1" fill="currentColor" stroke="none"/>',
  send:'<path d="M4 11.8 20 4l-7.2 16-2.6-6.2L4 11.8Z" fill="currentColor" stroke="none"/><path d="M10.2 13.8 20 4"/>',
  // life-os pillar icons
  p_rel:'<path d="M8 13.3S3.6 10.8 3.6 7.6A2.6 2.6 0 0 1 8 5.8 2.6 2.6 0 0 1 12.4 7.6C12.4 10.8 8 13.3 8 13.3Z" fill="currentColor" stroke="none"/><path d="M15 18.3s-4.4-2.5-4.4-5.7A2.6 2.6 0 0 1 15 10.8a2.6 2.6 0 0 1 4.4 1.8c0 3.2-4.4 5.7-4.4 5.7Z" fill="currentColor" stroke="none"/>',
  p_home:'<path d="M3.5 11 12 4l8.5 7"/><path d="M5.5 10.2V19h13v-8.8"/><rect x="10" y="13.5" width="4" height="5.5" rx="0.6"/>',
  p_career:'<rect x="3" y="7.5" width="18" height="11.5" rx="2.2"/><path d="M8.5 7.5V6a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v1.5"/><line x1="3" y1="13" x2="21" y2="13"/><rect x="10.3" y="11.4" width="3.4" height="3.2" rx="0.7" fill="currentColor" stroke="none"/>',
  p_music:'<path d="M9 18V5l11-2v13"/><circle cx="6.5" cy="18" r="2.5" fill="currentColor" stroke="none"/><circle cx="17.5" cy="16" r="2.5" fill="currentColor" stroke="none"/>',
  p_fit:'<rect x="2.3" y="9.5" width="2.3" height="5" rx="1" fill="currentColor" stroke="none"/><rect x="5.4" y="7.4" width="2.3" height="9.2" rx="1" fill="currentColor" stroke="none"/><rect x="16.3" y="7.4" width="2.3" height="9.2" rx="1" fill="currentColor" stroke="none"/><rect x="19.4" y="9.5" width="2.3" height="5" rx="1" fill="currentColor" stroke="none"/><line x1="7.7" y1="12" x2="16.3" y2="12"/>',
  p_health:'<path d="M12 20S4 15 4 9.2A4 4 0 0 1 12 6.6 4 4 0 0 1 20 9.2C20 15 12 20 12 20Z"/><path d="M5 12h3l1.5-3 2.5 5.5L14 11h5"/>',
  p_growth:'<path d="M12 20.5v-7"/><path d="M12 14c0-3-2.3-5.2-5.3-5.2C6.4 11.8 8.6 14 12 14Z" fill="currentColor" stroke="none"/><path d="M12 12c0-3.2 2.4-5.6 5.6-5.6C17.9 9.6 15.5 12 12 12Z" fill="currentColor" stroke="none"/>',
  p_coin:'<circle cx="12" cy="12" r="8.5"/><path d="M12 7v10M14.4 9.3c-.5-.8-1.4-1.2-2.4-1.2-1.4 0-2.5.8-2.5 2s1.1 1.8 2.5 2 2.5.8 2.5 2-1.1 2-2.5 2c-1 0-2-.4-2.5-1.2"/>',
  p_palette:'<path d="M12 3C6.8 3 3 6.8 3 11.5S6.8 20 12 20c1.1 0 1.8-.9 1.8-2 0-1.4 1-2.1 2.4-2.1 2.7 0 4.8-2 4.8-4.9C21 6.6 17 3 12 3Z"/><circle cx="7.6" cy="10.2" r="1.1" fill="currentColor" stroke="none"/><circle cx="11" cy="7.6" r="1.1" fill="currentColor" stroke="none"/><circle cx="15.4" cy="8.8" r="1.1" fill="currentColor" stroke="none"/>',
  p_purpose:'<circle cx="12" cy="12" r="8.5"/><path d="M12 5.5 13.7 10.3 18.5 12 13.7 13.7 12 18.5 10.3 13.7 5.5 12 10.3 10.3Z" fill="currentColor" stroke="none"/>',
  p_compass8:'<circle cx="12" cy="12" r="9"/><path d="M12 3.5 13 11 20.5 12 13 13 12 20.5 11 13 3.5 12 11 11Z" fill="currentColor" stroke="none"/>',
  p_people:'<circle cx="12" cy="7" r="2.6"/><circle cx="5.3" cy="9.5" r="2.1"/><circle cx="18.7" cy="9.5" r="2.1"/><path d="M7.4 18.5c0-2.5 2-4.5 4.6-4.5s4.6 2 4.6 4.5"/><path d="M2.4 17.4c0-1.9 1.3-3.5 3.1-3.6M21.6 17.4c0-1.9-1.3-3.5-3.1-3.6"/>',
  p_mtn:'<path d="M2.4 19 9 7l3.8 6.8L15.2 10 21.6 19Z" fill="currentColor" stroke="none"/><path d="M7.6 11.6 9 9.2l1.3 2.3"/>',
  mic:'<rect x="9" y="2.5" width="6" height="11" rx="3" fill="currentColor" stroke="none"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0"/><line x1="12" y1="17.5" x2="12" y2="21"/><line x1="8.5" y1="21" x2="15.5" y2="21"/>',
  camera:'<path d="M3 8.5a2 2 0 0 1 2-2h2l1.2-1.8h7.6L19 6.5h0a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><circle cx="12" cy="13" r="3.4"/>',
  // collectible meditation items
  cushion:'<path d="M12 8c4.4 0 8 1.8 8 4s-3.6 4-8 4-8-1.8-8-4 3.6-4 8-4Z" fill="currentColor" stroke="none"/><path d="M4 12v2c0 2.2 3.6 4 8 4s8-1.8 8-4v-2"/>',
  incense:'<path d="M12 2.6c-1.1 1.3.9 2.2 0 3.6"/><circle cx="12" cy="7" r="1" fill="currentColor" stroke="none"/><line x1="12" y1="8" x2="12" y2="18.5"/><path d="M8 18.5h8l-1 2.4H9Z" fill="currentColor" stroke="none"/>',
  candle:'<path d="M12 3.4c1.4 1.5 2.3 2.7 2.3 4.1a2.3 2.3 0 0 1-4.6 0c0-1.4.9-2.6 2.3-4.1Z" fill="currentColor" stroke="none"/><rect x="8.5" y="10" width="7" height="10.5" rx="1.4"/><line x1="12" y1="8" x2="12" y2="10"/>',
  mala:'<circle cx="12" cy="10" r="6" stroke-dasharray="1.4 2.4"/><circle cx="12" cy="16" r="1.4" fill="currentColor" stroke="none"/><path d="M12 17.4v3.6M10.6 21h2.8"/>',
  bowl:'<path d="M4.5 11h15l-1.8 5.2a3 3 0 0 1-2.8 2H9.1a3 3 0 0 1-2.8-2L4.5 11Z" fill="currentColor" stroke="none"/><line x1="3.5" y1="11" x2="20.5" y2="11"/><line x1="19" y1="5.5" x2="21" y2="7.5"/>',
  bell:'<path d="M12 4a6 6 0 0 1 6 6v5H6v-5a6 6 0 0 1 6-6Z"/><path d="M4.5 15h15"/><line x1="12" y1="4" x2="12" y2="2.4"/><circle cx="12" cy="18" r="1.4" fill="currentColor" stroke="none"/>',
  crystal:'<path d="M12 2.5 5 9l7 12.5L19 9l-7-6.5Z"/><path d="M5 9h14M8.5 9 12 2.5 15.5 9M8.5 9 12 21.5 15.5 9"/>',
  flags:'<path d="M3 5c6 2.6 12 2.6 18 0"/><path d="M6 5.8v4l2.6-.9ZM11 6.1v4l2.6-.9ZM16 5.9v4l2.6-.9Z" fill="currentColor" stroke="none"/>',
  enso:'<path d="M16.6 5.4A8 8 0 1 0 19 13.4" stroke-width="2.5"/>',
  bonsai:'<path d="M7.5 17.5h9l-1 3.5h-7Z" fill="currentColor" stroke="none"/><path d="M12 17.5v-5M12 14c-2.5 0-4-1.2-4-3M12 12.5c2.5 0 4.5-1 4.5-3"/><circle cx="7.5" cy="8.5" r="2.4"/><circle cx="16.5" cy="8.5" r="2.8"/><circle cx="12" cy="6.3" r="2.6"/>',
  // companions
  c_moth:'<path d="M12 7.5c-1.3-2.4-5.5-3-7.3-1S4 12 6.2 12.6c-2 .6-2.3 3.4-.8 4.4s4.4-.2 6.6-2.5M12 7.5c1.3-2.4 5.5-3 7.3-1S20 12 17.8 12.6c2 .6 2.3 3.4.8 4.4s-4.4-.2-6.6-2.5" fill="currentColor" stroke="none"/><line x1="12" y1="7.5" x2="12" y2="15"/><path d="M12 7.5 10 4.5M12 7.5 14 4.5"/>',
  c_fox:'<path d="M5 5c-.6 4 .9 8.2 7 11 6.1-2.8 7.6-7 7-11-2 .5-3.4 1.5-4.2 3.1C20 6.9 19 6.6 18 6.6M5 5c2 .5 3.4 1.5 4.2 3.1C4 6.9 5 6.6 6 6.6" fill="currentColor" stroke="none"/><path d="M9.3 11.2h0M14.7 11.2h0"/>',
  c_koi:'<path d="M2.5 12c3-5 9.5-6 13.5-4 1.6.8 3.2 2.1 4.2 4-1 1.9-2.6 3.2-4.2 4-4 2-10.5 1-13.5-4Z" fill="currentColor" stroke="none"/><path d="M20.2 12 23 8.8v6.4L20.2 12Z" fill="currentColor" stroke="none"/><path d="M7.5 9.5c1 1 1 4 0 5"/>',
  c_owl:'<path d="M6.5 5.5C8 4 10 4 11.5 5.3M17.5 5.5C16 4 14 4 12.5 5.3"/><path d="M6 11.5a6 6 0 0 0 12 0c0-3.2-2.6-6-6-6s-6 2.8-6 6Z"/><circle cx="9.6" cy="11" r="1.7"/><circle cx="14.4" cy="11" r="1.7"/><path d="M12 12.6v2.2"/><path d="M9.2 18.2 12 17l2.8 1.2"/>',
  c_deer:'<path d="M12 8.5c-2.1 0-3.6 1.6-3.6 4 0 2.6 1.6 5.2 3.6 6.2 2-1 3.6-3.6 3.6-6.2 0-2.4-1.5-4-3.6-4Z" fill="currentColor" stroke="none"/><path d="M8.5 8C8 6.5 8 5 9 3.6 9.4 5 10.2 5.4 11 6M15.5 8c.5-1.5.5-3-.5-4.4C14.6 5 13.8 5.4 13 6M7.2 5.2 6 3.6M16.8 5.2 18 3.6"/>',
  c_whale:'<path d="M2.5 13.5c0-3.2 3.2-5.3 7.3-5.3s7.3 2.1 7.3 5.3c0 2.1-1.6 3.7-4.2 4.2H6.7c-2.6-.5-4.2-2.1-4.2-4.2Z" fill="currentColor" stroke="none"/><path d="M17 13c1.6-.6 3.2-.6 4.8 0-1 1.3-1 2.6 0 3.9-1.6.3-3.2 0-4.8-1.1" fill="currentColor" stroke="none"/><path d="M8.5 7.5C8 5.8 8.8 4.6 9.6 3.6"/>',
  // shop
  chimes:'<path d="M7.5 5.5c2 1.4 7 1.4 9 0"/><line x1="7.5" y1="5.5" x2="7.5" y2="9.3"/><line x1="16.5" y1="5.5" x2="16.5" y2="9.3"/><ellipse cx="7.5" cy="10.5" rx="4.5" ry="1.7" fill="currentColor" stroke="none"/><ellipse cx="16.5" cy="10.5" rx="4.5" ry="1.7" fill="currentColor" stroke="none"/>',
  sand:'<rect x="3" y="7" width="18" height="10" rx="2.2"/><path d="M5.5 10.5c2-1 4 1 6 0s3.5-1 5.5 0M5.5 13.5c2-1 4 1 6 0s3.5-1 5.5 0"/><circle cx="16.5" cy="11.8" r="1.3" fill="currentColor" stroke="none"/>',
  lantern:'<path d="M9.5 3.2h5M12 3.2v2"/><rect x="7" y="5.2" width="10" height="12.6" rx="2.6"/><path d="M7 8.4h10M7 14.6h10"/><path d="M10 17.8v2M14 17.8v2"/><circle cx="12" cy="11.5" r="2" fill="currentColor" stroke="none"/>',
  coin:'<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="5.6"/><path d="M12 9.2c-1.3 0-2 .8-2 1.6 0 2 4 1 4 3 0 .9-.8 1.6-2 1.6M12 8.3v1M12 15.4v.9"/>',
  pendant:'<circle cx="12" cy="3.7" r="1.5"/><line x1="12" y1="5.2" x2="12" y2="6.7"/><path d="M12 6.7c-3 0-5.2 2.7-5.2 5.8S9 18.5 12 18.5s5.2-2.9 5.2-6S15 6.7 12 6.7Z" fill="currentColor" stroke="none"/><path d="M9.2 11.4h5.6" opacity="0.45"/>',
  stone:'<ellipse cx="12" cy="12" rx="8.6" ry="6.2" fill="currentColor" stroke="none"/><ellipse cx="12" cy="11.6" rx="3.3" ry="2.4" fill="#120e22"/>',
  amber:'<path d="M12 3.4c-3 3.9-4.9 6.3-4.9 9.1A4.9 4.9 0 0 0 16.9 12.5c0-2.8-1.9-5.2-4.9-9.1Z" fill="currentColor" stroke="none"/><circle cx="10.8" cy="13" r="1.1" fill="#120e22"/>',
};
const ITEM_ICON={zafu:'cushion',incense:'incense',candle:'candle',mala:'mala',bowl:'bowl',bell:'bell',crystal:'crystal',flags:'flags',enso:'enso',bonsai:'bonsai',chimes:'chimes',sand:'sand',lantern:'lantern',drachma:'coin',skyiron:'pendant',rudraksha:'mala',jade:'stone',amberbead:'amber',tingbowl:'bowl'};
const ITEM_NAME={zafu:'Lotus Cushion',incense:'Incense',candle:'Candle',mala:'Mala Beads',bowl:'Singing Bowl',bell:'Temple Bell',crystal:'Amethyst',flags:'Prayer Flags',enso:'Ensō',bonsai:'Bonsai',chimes:'Tingsha Chimes',sand:'Zen Sand Garden',lantern:'Founder\'s Lantern',drachma:'Owl Drachma',skyiron:'Sky-Iron Amulet',rudraksha:'Rudraksha Mala',jade:'Nephrite Worry Stone',amberbead:'Baltic Amber',tingbowl:'Hand-Hammered Bowl'};
const ART_ICON={drachma:'coin',skyiron:'pendant',rudraksha:'mala',jade:'stone',amberbead:'amber',tingbowl:'bowl'};
const ART_IMG={drachma:'art/drachma.png?v=4',skyiron:'art/skyiron.png?v=4',rudraksha:'art/rudraksha.png?v=4',jade:'art/jade.png?v=4',amberbead:'art/amberbead.png?v=4',tingbowl:'art/tingbowl.png?v=4'};
const COMP_ICON={moth:'c_moth',fox:'c_fox',koi:'c_koi',owl:'c_owl',deer:'c_deer',whale:'c_whale'};
const COMP_NAME={moth:'Lumen Moth',fox:'Ember Fox',koi:'Tide Koi',owl:'Dawn Owl',deer:'Grove Deer',whale:'Star Whale'};
const RARITY=[['Common','#9aa3b8','#232233','rgba(154,163,184,.20)'],['Rare','#5fb0fa','#13233e','rgba(95,176,250,.26)'],['Epic','#c084fc','#271640','rgba(192,132,252,.28)'],['Legendary','#f5c977','#33260f','rgba(245,201,119,.32)']];
const ACH_RARITY={first_light:0,centurion:0,marathoner:1,moon_child:1,dawn_patrol:1,week_warrior:2,globetrotter:2,deep_diver:2,constellation:3,luminary:3,scribe:1,chronicler:2,pilgrim:2};
function rarityOf(code){return ACH_RARITY[code]!=null?ACH_RARITY[code]:0;}
function ic(name,cls){return `<svg class="i ${cls||''}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${SVGP[name]||''}</svg>`;}
// The Lumen brand mark: a dimensional ringed light-orb (mini of the home hero orb).
// This is the app logo everywhere — the old line-art sun (SVGP.lumen) is kept as the
// legacy "light motif" glyph for inline, in-text uses (Keeper notes, map points, etc.).
let __lmN=0;
function lumenMark(cls){const u='lm'+(++__lmN);return `<svg class="lmark ${cls||''}" viewBox="0 0 44 44" aria-hidden="true"><defs><radialGradient id="${u}c" cx="46%" cy="40%" r="60%"><stop offset="0" stop-color="#fffdf6"/><stop offset=".2" stop-color="#fff0c6"/><stop offset=".5" stop-color="#f7c972"/><stop offset=".82" stop-color="#e49b38"/><stop offset="1" stop-color="#9a5e1c"/></radialGradient><radialGradient id="${u}h" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#f6c977" stop-opacity=".55"/><stop offset=".6" stop-color="#f0a84a" stop-opacity=".18"/><stop offset="1" stop-color="#f0a84a" stop-opacity="0"/></radialGradient><linearGradient id="${u}r" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#e49b38" stop-opacity=".12"/><stop offset=".5" stop-color="#ffe7b0"/><stop offset="1" stop-color="#e49b38" stop-opacity=".12"/></linearGradient><clipPath id="${u}f"><rect x="0" y="22" width="44" height="22"/></clipPath></defs><circle cx="22" cy="22" r="21" fill="url(#${u}h)"/><ellipse cx="22" cy="22" rx="18" ry="5.6" fill="none" stroke="url(#${u}r)" stroke-width="1.3" transform="rotate(-20 22 22)"/><circle cx="22" cy="22" r="11" fill="url(#${u}c)"/><circle cx="22" cy="22" r="11" fill="none" stroke="#ffe7b0" stroke-width=".6" opacity=".35"/><ellipse cx="18.4" cy="18" rx="3.1" ry="2.1" fill="#fffdf4" opacity=".8" transform="rotate(-25 18.4 18)"/><g clip-path="url(#${u}f)"><ellipse cx="22" cy="22" rx="18" ry="5.6" fill="none" stroke="url(#${u}r)" stroke-width="1.5" transform="rotate(-20 22 22)"/></g><circle cx="38.6" cy="15.9" r="1.2" fill="#fff3d0"/><circle cx="5.4" cy="28.1" r="1.05" fill="#fff3d0" opacity=".9"/></svg>`;}
const ACH_ICON={first_light:'lumen',marathoner:'flag',week_warrior:'flame',constellation:'spark',moon_child:'moon',dawn_patrol:'sunrise',globetrotter:'globe',centurion:'target',deep_diver:'ocean',luminary:'spark',scribe:'book',chronicler:'book',pilgrim:'lotus'};
// each facet is coloured by the kind of act it represents
const ACH_CAT_COLOR={
  first_light:'#f5c977', marathoner:'#5fd3c2', centurion:'#5fd3c2',
  deep_diver:'#5fb0fa', luminary:'#c084fc',
  week_warrior:'#fb923c', constellation:'#ec4899',
  moon_child:'#818cf8', dawn_patrol:'#fbbf24',
  globetrotter:'#34d399', scribe:'#f472b6', chronicler:'#f9a8d4', pilgrim:'#f59e0b'};
const catColor=(code)=>ACH_CAT_COLOR[code]||'#f5c977';

/* starfield */
(function(){const c=$('.stars'),x=c.getContext('2d');function rs(){c.width=innerWidth;c.height=innerHeight;}rs();addEventListener('resize',rs);
  const st=[...Array(90)].map(()=>({x:Math.random()*c.width,y:Math.random()*c.height,r:Math.random()*1.3+.2,a:Math.random()}));
  (function loop(){x.clearRect(0,0,c.width,c.height);for(const s of st){s.a+=0.02;const o=.3+.3*Math.sin(s.a);x.fillStyle=`rgba(220,210,255,${o})`;x.beginPath();x.arc(s.x,s.y,s.r,0,7);x.fill();}requestAnimationFrame(loop);})();
})();

/* ---- Web Audio soundscapes (no asset files) ---- */
const Sound=(function(){
  let ac=null,nodes=[],master=null;
  function ctx(){if(!ac){ac=new (window.AudioContext||window.webkitAudioContext)();}return ac;}
  function noiseBuf(a){const b=a.createBuffer(1,a.sampleRate*2,a.sampleRate);const d=b.getChannelData(0);for(let i=0;i<d.length;i++)d[i]=Math.random()*2-1;return b;}
  function stopAll(){nodes.forEach(n=>{try{n.stop&&n.stop();n.disconnect&&n.disconnect();}catch(e){}});nodes=[];}
  function start(kind){
    const a=ctx();if(a.state==='suspended')a.resume();
    stopAll();
    master=a.createGain();master.gain.value=0;master.connect(a.destination);
    master.gain.linearRampToValueAtTime(0.5,a.currentTime+2);
    nodes.push(master);
    if(kind==='silence')return;
    if(kind==='rain'||kind==='ocean'){
      const src=a.createBufferSource();src.buffer=noiseBuf(a);src.loop=true;
      const lp=a.createBiquadFilter();lp.type='lowpass';lp.frequency.value=kind==='rain'?1600:500;
      const g=a.createGain();g.gain.value=kind==='rain'?0.5:0.6;
      if(kind==='ocean'){const lfo=a.createOscillator();lfo.frequency.value=0.12;const lg=a.createGain();lg.gain.value=0.35;lfo.connect(lg);lg.connect(g.gain);lfo.start();nodes.push(lfo);}
      src.connect(lp);lp.connect(g);g.connect(master);src.start();nodes.push(src,lp,g);
    }
    if(kind==='forest'){
      const src=a.createBufferSource();src.buffer=noiseBuf(a);src.loop=true;
      const bp=a.createBiquadFilter();bp.type='bandpass';bp.frequency.value=900;bp.Q.value=0.6;
      const g=a.createGain();g.gain.value=0.18;src.connect(bp);bp.connect(g);g.connect(master);src.start();nodes.push(src,bp,g);
      // occasional bird chirps
      const timer=setInterval(()=>{if(!ac)return;const o=a.createOscillator();o.type='sine';const f=1400+Math.random()*1600;o.frequency.setValueAtTime(f,a.currentTime);o.frequency.linearRampToValueAtTime(f*1.3,a.currentTime+0.08);const bg=a.createGain();bg.gain.value=0.0;bg.gain.linearRampToValueAtTime(0.12,a.currentTime+0.02);bg.gain.linearRampToValueAtTime(0,a.currentTime+0.18);o.connect(bg);bg.connect(master);o.start();o.stop(a.currentTime+0.2);},1400+Math.random()*1500);
      nodes.push({stop:()=>clearInterval(timer),disconnect:()=>{}});
    }
    if(kind==='space'){
      [110,110.4,164.8,220].forEach((f,i)=>{const o=a.createOscillator();o.type='sine';o.frequency.value=f;const g=a.createGain();g.gain.value=0.0;g.gain.linearRampToValueAtTime(0.12,a.currentTime+3);
        const lfo=a.createOscillator();lfo.frequency.value=0.05+i*0.02;const lg=a.createGain();lg.gain.value=0.05;lfo.connect(lg);lg.connect(g.gain);lfo.start();
        o.connect(g);g.connect(master);o.start();nodes.push(o,g,lfo);});
    }
  }
  function bell(){const a=ctx();if(a.state==='suspended')a.resume();const o=a.createOscillator();o.type='sine';o.frequency.value=528;const g=a.createGain();g.gain.value=0.0;g.gain.linearRampToValueAtTime(0.5,a.currentTime+0.01);g.gain.exponentialRampToValueAtTime(0.0001,a.currentTime+3.5);const o2=a.createOscillator();o2.type='sine';o2.frequency.value=1056;const g2=a.createGain();g2.gain.value=0;g2.gain.linearRampToValueAtTime(0.18,a.currentTime+0.01);g2.gain.exponentialRampToValueAtTime(0.0001,a.currentTime+2.5);o.connect(g);o2.connect(g2);g.connect(a.destination);g2.connect(a.destination);o.start();o2.start();o.stop(a.currentTime+3.6);o2.stop(a.currentTime+2.6);}
  function stop(){if(master){try{master.gain.linearRampToValueAtTime(0,ac.currentTime+1.2);}catch(e){}}setTimeout(stopAll,1300);}
  // Play a narration clip THROUGH the same context as the soundscape so iOS keeps one
  // audio session (fixes the music cutting out) and duck the music under the voice.
  let curVoice=null;
  function duck(v,t){if(master){try{master.gain.cancelScheduledValues(ac.currentTime);master.gain.setValueAtTime(master.gain.value,ac.currentTime);master.gain.linearRampToValueAtTime(v,ac.currentTime+t);}catch(e){}}}
  function say(arrayBuf,onend,onfail){
    const a=ctx();if(a.state==='suspended')a.resume();
    let done=false;const fin=(f)=>{if(done)return;done=true;duck(0.5,0.7);(f?onfail:onend)&&(f?onfail:onend)();};
    try{
      a.decodeAudioData(arrayBuf.slice(0)).then(buf=>{
        try{duck(0.14,0.3);const src=a.createBufferSource();src.buffer=buf;const g=a.createGain();g.gain.value=1.0;
          src.connect(g);g.connect(a.destination);src.onended=()=>fin(false);curVoice=src;src.start();}
        catch(e){fin(true);}
      }).catch(()=>fin(true));
    }catch(e){fin(true);}
    return {stop:()=>{try{curVoice&&curVoice.stop();}catch(e){}curVoice=null;duck(0.5,0.4);}};
  }
  return {start,stop,bell,say};
})();

/* ---- app state ---- */
let ME=null, TAB='meditate', map=null, mapLayer=null, MARKERS=null, JPATH=null, journeyTok=0;
let geoFix=null;  // last known device location {lat,lon,t}
function getGeo(opts){return new Promise(res=>{
  if(!navigator.geolocation)return res(null);
  navigator.geolocation.getCurrentPosition(
    p=>{geoFix={lat:p.coords.latitude,lon:p.coords.longitude,t:Date.now()};res(geoFix);},
    ()=>res(null),
    opts||{enableHighAccuracy:true,timeout:15000,maximumAge:120000});});}
const SOUNDS=[['rain','rain','Rain'],['forest','forest','Forest'],['ocean','ocean','Ocean'],['space','space','Deep Space'],['silence','silence','Silence']];
const DUR_LABEL={5:'Quick',10:'Daily',20:'Deep',30:'Long'};
let pick={minutes:(()=>{try{return +localStorage.getItem('lumen_pref_min')||10;}catch(e){return 10;}})(),sound:'rain'};

// --- first-party product analytics: batched events -> /api/ev (admin dashboard) ---
const _AID=(function(){try{let a=localStorage.getItem('lumen_aid');if(!a){a=Date.now().toString(36)+Math.random().toString(36).slice(2,10);localStorage.setItem('lumen_aid',a);}return a;}catch(e){return 'anon';}})();
let _evq=[],_evt=null;
function _evflush(){if(!_evq.length)return;const batch=_evq.splice(0,25);const body=JSON.stringify({aid:_AID,events:batch});
  try{if(navigator.sendBeacon&&navigator.sendBeacon('api/ev',new Blob([body],{type:'application/json'})))return;}catch(e){}
  try{fetch('api/ev',{method:'POST',headers:{'Content-Type':'application/json'},body:body,keepalive:true}).catch(()=>{});}catch(e){}}
function track(name,props,screen){try{_evq.push({name:name,props:props||null,screen:screen||(typeof TAB!=='undefined'?TAB:null)});clearTimeout(_evt);_evt=setTimeout(_evflush,1200);}catch(e){}}
try{addEventListener('visibilitychange',function(){if(document.visibilityState==='hidden')_evflush();});}catch(e){}
function onbLabel(s){if(typeof Q_INTENT==='undefined')return 'Slide '+(s+1);
  const m={};m[Q_INTENT]='Q: Intent';m[Q_FREQ]='Q: Frequency';m[Q_TIME]='Q: Time';m[Q_DUR]='Q: Duration';m[Q_LEVEL]='Q: Level';m[ONB_LAST]='Signup';
  return (s>=Q_INTENT)?(m[s]||('Step '+s)):('Slide '+(s+1));}
async function boot(){
  try{const r=await api('me');if(r.authed){ME=r.profile;}}catch(e){}
  try{if(window.Sentry&&Sentry.setUser)Sentry.setUser(ME?{id:String(ME.id||''),email:ME.email}:null);}catch(e){}
  if(!ME){
    let done=false;try{done=localStorage.getItem('lumen_onb_done')==='1';}catch(e){}
    try{window.__screen&&window.__screen(done?'auth':'onboarding');}catch(e){}
    if(done){track('screen_view',null,'auth');renderAuth();}else{renderOnboarding();}
    return;
  }
  $('#nav').classList.remove('hidden');
  bindNav();
  go('meditate');
}
const NAV_ICON={meditate:'meditate',lessons:'lotus',map:'globe',leagues:'trophy',journal:'book',collect:'crystal',profile:'spark'};
const LEAGUE_ICON={Ember:'flame',Spark:'spark',Glow:'glow',Flare:'flare',Beacon:'beacon',Nova:'star',Supernova:'nova'};
const leagueIcon=(name,cls)=>ic(LEAGUE_ICON[name]||'trophy',cls||'');
// Premium league emblem: a glowing tiered medallion themed to the league colour —
// concentric light-rings, a radiant halo, orbiting motes, and the tier glyph at
// the core. Riffs on the home orb so Leagues reads as one system. SVG = crisp +
// re-colours per tier with no raster assets.
let _lemUID=0;
function leagueEmblem(lg,size){
  size=size||120;const c1=lg.color||'#f5c977',c2=lg.color2||c1;const id='lem'+(_lemUID++);
  const g=leagueIcon(lg.name);
  return `<svg class="lemblem" viewBox="0 0 120 120" width="${size}" height="${size}" aria-hidden="true">
    <defs>
      <radialGradient id="${id}h" cx="50%" cy="42%" r="60%">
        <stop offset="0%" stop-color="${c1}" stop-opacity=".55"/>
        <stop offset="55%" stop-color="${c2}" stop-opacity=".16"/>
        <stop offset="100%" stop-color="${c2}" stop-opacity="0"/>
      </radialGradient>
      <radialGradient id="${id}d" cx="38%" cy="30%" r="75%">
        <stop offset="0%" stop-color="#fff" stop-opacity=".9"/>
        <stop offset="26%" stop-color="${c1}"/>
        <stop offset="100%" stop-color="${c2}"/>
      </radialGradient>
      <linearGradient id="${id}r" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="${c1}"/><stop offset="100%" stop-color="${c2}"/>
      </linearGradient>
    </defs>
    <circle cx="60" cy="60" r="58" fill="url(#${id}h)"/>
    <g fill="none" stroke="url(#${id}r)" class="lem-ring">
      <circle cx="60" cy="60" r="46" stroke-opacity=".30" stroke-width="1"/>
      <circle cx="60" cy="60" r="39" stroke-opacity=".55" stroke-width="1.4" stroke-dasharray="3 7" stroke-linecap="round"/>
    </g>
    <circle cx="60" cy="60" r="29" fill="url(#${id}d)"/>
    <circle cx="60" cy="60" r="29" fill="none" stroke="#fff" stroke-opacity=".25" stroke-width="1"/>
    <ellipse cx="52" cy="50" rx="13" ry="8" fill="#fff" opacity=".22"/>
    <g class="lem-motes" fill="${c1}">
      <circle cx="60" cy="14" r="2.3"/><circle cx="106" cy="60" r="1.8"/>
      <circle cx="60" cy="106" r="1.8"/><circle cx="14" cy="60" r="2.1"/>
    </g>
    <g transform="translate(60 60)" class="lem-glyph" style="color:#fff">
      <g transform="translate(-13 -13) scale(1.08)">${g.replace('<svg','<svg width=\"24\" height=\"24\"')}</g>
    </g>
  </svg>`;
}
function bindNav(){document.querySelectorAll('nav button').forEach(b=>{b.onclick=()=>{if(b.dataset.tab==='journal')jScreen='home';go(b.dataset.tab);};const s=b.querySelector('.ic');if(s)s.innerHTML=ic(NAV_ICON[b.dataset.tab],'nav');});}
function go(tab){TAB=tab;try{window.__screen&&window.__screen(tab);}catch(e){}try{track('screen_view',null,tab);}catch(e){}document.querySelectorAll('.jny-finale').forEach(x=>x.remove());
  if(window.speechSynthesis)speechSynthesis.cancel();try{stopNarration();}catch(e){}try{Sound.stop();}catch(e){}
  document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('on',b.dataset.tab===tab));
  ({meditate:renderMeditate,map:renderMap,leagues:renderLeagues,journal:renderJournal,collect:renderCollection,profile:renderProfile,lessons:renderLessons}[tab])();}

/* ---- auth ---- */
function renderAuth(){
  $('#nav').classList.add('hidden');
  $('#app').innerHTML=`
  <div class="brand"><span class="mark">${lumenMark('mark')}</span><b>Lumen</b></div>
  <div class="center" style="margin:26px 0 10px">
    <div style="color:var(--gold);filter:drop-shadow(0 0 24px var(--gold))">${lumenMark('lg')}</div>
    <h1 style="margin:14px 0 4px">Light up the world</h1>
    <p class="muted" style="margin:0 28px">Meditate, earn Light, and watch the planet glow with everyone practicing today.</p>
  </div>
  <div class="card">
    <label>Email</label><input id="em" type="email" autocomplete="email" placeholder="you@example.com">
    <label>Password</label><input id="pw" type="password" autocomplete="current-password" placeholder="at least 6 characters">
    <div id="nameWrap" class="hidden"><label>Display name (shown on the map & leagues)</label><input id="nm" placeholder="e.g. Matthew">
      <label>Birthday <span class="muted" style="font-weight:400">(for your daily reading)</span></label><input id="bd" type="date">
      <label>Mobile <span class="muted" style="font-weight:400">(optional — for reminders)</span></label><input id="ph" type="tel" autocomplete="tel" placeholder="+1 555 123 4567">
      <label class="sms-consent"><input type="checkbox" id="smsok"><span>Text me gentle practice reminders. Msg &amp; data rates may apply; reply STOP anytime to opt out.</span></label></div>
    <div class="err" id="er"></div>
    <button class="btn" id="go">Sign in</button>
    <button class="btn ghost" id="sw" style="margin-top:9px">Create an account</button>
    <div class="center" style="margin-top:12px"><a class="onb-signin" id="forgot">Forgot password?</a></div>
  </div>`;
  let mode='login';
  $('#sw').onclick=()=>{mode=mode==='login'?'signup':'login';
    $('#nameWrap').classList.toggle('hidden',mode!=='signup');
    $('#go').textContent=mode==='login'?'Sign in':'Create account & begin';
    $('#sw').textContent=mode==='login'?'Create an account':'I already have an account';
    $('#forgot').style.display=mode==='login'?'':'none';};
  $('#forgot').onclick=()=>renderReset(($('#em').value||'').trim());
  $('#go').onclick=async()=>{const er=$('#er');er.textContent='';
    const email=$('#em').value.trim(),password=$('#pw').value;
    if(!email||!password){er.textContent='Enter your email and password.';return;}
    try{if(mode==='signup'){await api('signup','POST',{email,password,name:$('#nm').value,birth_date:($('#bd')&&$('#bd').value)||'',phone:($('#ph')&&$('#ph').value)||'',sms_consent:($('#smsok')&&$('#smsok').checked)?1:0});}else{await api('login','POST',{email,password});}
      const r=await api('me');ME=r.profile;$('#nav').classList.remove('hidden');bindNav();go('meditate');
    }catch(e){er.textContent=e;}};
  // Enter submits from any field
  ['em','pw','nm','ph'].forEach(id=>{const el=$('#'+id);if(el)el.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();$('#go').click();}});});
}
// Password reset — request a 6-digit code by email, then enter it with a new password.
function renderReset(prefill){
  $('#nav').classList.add('hidden');
  let stage='request';
  const draw=()=>{
    $('#app').innerHTML=`
    <div class="brand"><span class="mark">${lumenMark('mark')}</span><b>Lumen</b></div>
    <div class="center" style="margin:26px 0 10px">
      <div style="color:var(--gold);filter:drop-shadow(0 0 24px var(--gold))">${ic('lock','lg grad-gold')}</div>
      <h1 style="margin:14px 0 4px">Reset your password</h1>
      <p class="muted" style="margin:0 28px">${stage==='request'?'Enter your email and we’ll send you a 6-digit reset code.':'Enter the code we emailed you and choose a new password.'}</p>
    </div>
    <div class="card">
      <label>Email</label><input id="rem" type="email" autocomplete="email" placeholder="you@example.com" value="${esc(prefill||'')}" ${stage==='verify'?'readonly':''}>
      ${stage==='verify'?`<label>Reset code</label><input id="rcode" inputmode="numeric" autocomplete="one-time-code" placeholder="6-digit code">
      <label>New password</label><input id="rpw" type="password" autocomplete="new-password" placeholder="at least 6 characters">`:''}
      <div class="err" id="rer"></div>
      <button class="btn" id="rgo">${stage==='request'?'Send reset code':'Reset password'}</button>
      ${stage==='verify'?`<button class="btn ghost" id="rresend" style="margin-top:9px">Resend code</button>`:''}
      <div class="center" style="margin-top:12px"><a class="onb-signin" id="rback">Back to sign in</a></div>
    </div>`;
    $('#rback').onclick=renderAuth;
    const rr=$('#rresend');if(rr)rr.onclick=()=>{stage='request';draw();};
    ['rem','rcode','rpw'].forEach(id=>{const el=$('#'+id);if(el)el.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();$('#rgo').click();}});});
    $('#rgo').onclick=async()=>{const er=$('#rer');er.textContent='';
      const email=($('#rem').value||'').trim();
      if(!email){er.textContent='Enter your email.';return;}
      if(stage==='request'){
        try{await api('forgot','POST',{email});prefill=email;stage='verify';draw();
          toast(ic('check','g')+' If that email has an account, a code is on its way');
        }catch(e){er.textContent=e;}
        return;
      }
      const code=($('#rcode').value||'').trim(),password=$('#rpw').value||'';
      if(!code){er.textContent='Enter the code from your email.';return;}
      if(password.length<6){er.textContent='Password needs at least 6 characters.';return;}
      try{await api('reset','POST',{email,code,password});
        const r=await api('me');ME=r.profile;$('#nav').classList.remove('hidden');bindNav();go('meditate');
        toast(ic('check','g')+' Password updated — welcome back');
      }catch(e){er.textContent=e;}
    };
  };
  draw();
}

/* ---- onboarding (value slides → personalization → account) ---- */
let onb={step:0,intents:[],timeHour:null,level:null,freq:null,minutes:null};
const ONB_SLIDES=[
  {scene:'world',h:"Show up with a vibrant community",p:"Thousands are meditating right now, glowing across a living world map. You sit alongside a real, worldwide community — and their momentum keeps you coming back."},
  {scene:'explore',h:"Explore the world, one meditation at a time",p:"Discover the beautiful places people meditate across the globe, claim your own spots on the map, and earn bonus Light every time you sit somewhere new."},
  {scene:'inspire',h:"Inspire, and be inspired",p:"Wake up to a community that shows up with you — cheer others on, share your own places, and draw daily inspiration from people chasing the same stillness."},
  {scene:'learn',h:"Learn from real, deep traditions",p:"Narrated journeys teach genuine technique — breathwork, meditation and sacred knowledge drawn from living spiritual traditions, not watered-down soundbites."},
  {scene:'collect',h:"Collect Light as you grow",p:"Earn Light for every sit, with bonuses for meditating in new places, finishing new lessons, and contributing to your community. Your practice, made visible."},
  {scene:'vedic',h:"Your Vedic reading, every day",p:"Each morning brings a horoscope written for you — drawn from ancient Jyotish teachings and your own rāśi and nakshatra — a calm, personal invitation to begin."},
  {scene:'mandala',h:"Watch your mandala bloom",p:"A single sacred mandala grows with you — each milestone revealing one more facet, until it becomes a beautiful record of the journey only you have walked."},
  {scene:'badges',h:"Earn badges for the inner path",p:"Every new level awards a unique emblem — merit badges for the soul — a growing collection of honors that mark how far your practice has carried you."},
];
const ONB_INTENTS=[['calm','Calm my mind','lotus'],['sleep','Sleep better','glow'],['focus','Focus & clarity','compass'],['stress','Ease stress & anxiety','ocean'],['habit','Build a habit','flame'],['spirit','Spiritual growth','nova'],['self','Understand myself','crystal'],['grief','Sit with something hard','moon']];
const ONB_FREQS=[['daily','Every day','flame'],['most','Most days','sunrise'],['few','A few times a week','glow'],['open','Just exploring','compass']];
const ONB_TIMES=[['Morning',8,'sunrise'],['Afternoon',13,'compass'],['Evening',19,'glow'],['Before sleep',21,'moon']];
const ONB_DURS=[[5,'Just a taste','5 min','spark'],[10,'A daily sit','10 min','lotus'],[20,'Go deep','20 min','nova'],[30,'A long stillness','30 min','glow']];
const ONB_LEVELS=[['New to it','new','spark'],['I dabble','some','glow'],['Seasoned','pro','nova']];
const NSL=ONB_SLIDES.length;                        // value slides are steps 0..NSL-1
const Q_INTENT=NSL, Q_FREQ=NSL+1, Q_TIME=NSL+2, Q_DUR=NSL+3, Q_LEVEL=NSL+4, ONB_LAST=NSL+5;  // ONB_LAST = signup step
const ONB_QIC={[Q_INTENT]:'compass',[Q_FREQ]:'flame',[Q_TIME]:'clock',[Q_DUR]:'meditate',[Q_LEVEL]:'lotus'};  // header icon per question step

function _oStars(list){return list.map(([x,y,r,d])=>`<circle cx="${x}" cy="${y}" r="${r}" fill="#fff6dc" class="os-tw" style="filter:drop-shadow(0 0 4px #f5c977);animation-delay:${d}s"/>`).join('');}
function _oMotes(list){return list.map(([x,y,r,d])=>`<circle cx="${x}" cy="${y}" r="${r}" fill="#ffe9bc" class="os-rise" style="filter:drop-shadow(0 0 5px #f5c977);animation-delay:${d}s"/>`).join('');}
// Animated, on-brand onboarding scenes — built from our own orb/light/mandala language
// (these replace the legacy real-people photos onb1..8.jpg, which remain on disk unused).
function onbScene(key){
  const V='viewBox="0 0 300 225" preserveAspectRatio="xMidYMid meet" aria-hidden="true"';
  if(key==='world') return `<svg ${V}><defs><radialGradient id="osw" cx="42%" cy="36%" r="68%"><stop offset="0" stop-color="#2f74b6"/><stop offset=".55" stop-color="#1d3f74"/><stop offset="1" stop-color="#0e1830"/></radialGradient></defs>
    <g class="os-breathe"><circle cx="150" cy="112" r="64" fill="url(#osw)" stroke="rgba(245,201,119,.28)" stroke-width="1"/>
    <ellipse cx="150" cy="112" rx="64" ry="22" fill="none" stroke="rgba(245,201,119,.18)" stroke-width="1"/>
    <ellipse cx="150" cy="112" rx="38" ry="64" fill="none" stroke="rgba(245,201,119,.14)" stroke-width="1"/>
    <ellipse cx="150" cy="112" rx="64" ry="48" fill="none" stroke="rgba(245,201,119,.11)" stroke-width="1"/>
    <line x1="86" y1="112" x2="214" y2="112" stroke="rgba(245,201,119,.16)" stroke-width="1"/></g>
    ${_oStars([[112,70,2.6,0],[196,82,3,.5],[210,138,2.4,1.1],[150,52,2.2,1.6],[96,150,2.6,.8],[150,172,3,1.9],[62,112,2.2,1.4],[238,112,2.4,.3]])}
    </svg>`;
  if(key==='explore') return `<svg ${V}><rect x="40" y="46" width="220" height="134" rx="16" fill="#141028" stroke="rgba(245,201,119,.16)" stroke-width="1"/>
    <g stroke="rgba(245,201,119,.08)" stroke-width="1"><line x1="40" y1="90" x2="260" y2="90"/><line x1="40" y1="134" x2="260" y2="134"/><line x1="112" y1="46" x2="112" y2="180"/><line x1="188" y1="46" x2="188" y2="180"/></g>
    <path d="M78 150 Q120 100 150 118 T228 74" fill="none" stroke="rgba(245,201,119,.5)" stroke-width="1.6" stroke-dasharray="4 6" stroke-linecap="round"/>
    ${_oStars([[78,150,3,.2],[150,118,2.6,1.2]])}
    <g style="transform-box:fill-box;transform-origin:228px 74px"><circle class="os-ripple" cx="228" cy="74" r="20" fill="none" stroke="#f5c977" stroke-width="1.5"/></g>
    <g class="os-drop" style="transform-origin:228px 74px"><path d="M228 50 C216 50 208 59 208 70 C208 82 228 98 228 98 C228 98 248 82 248 70 C248 59 240 50 228 50 Z" fill="#f5c977" stroke="#fff3d0" stroke-width="1"/><circle cx="228" cy="70" r="6" fill="#241a0a"/></g>
    </svg>`;
  if(key==='inspire') return `<svg ${V}><defs><radialGradient id="osi" cx="50%" cy="100%" r="80%"><stop offset="0" stop-color="#ffe7a8"/><stop offset=".4" stop-color="#f3a93f"/><stop offset="1" stop-color="#f3a93f" stop-opacity="0"/></radialGradient></defs>
    <circle cx="150" cy="168" r="96" fill="url(#osi)" class="os-glow"/>
    <g class="os-spin" style="transform-origin:150px 168px" stroke="#ffdf9a" stroke-width="2" stroke-linecap="round" opacity=".7">
    ${[0,30,60,90,120,150].map(a=>`<line x1="150" y1="168" x2="${150+Math.cos((a-90)*Math.PI/180)*120}" y2="${168+Math.sin((a-90)*Math.PI/180)*120}"/>`).join('')}</g>
    <circle cx="150" cy="168" r="34" fill="#fff3d0" class="os-breathe" style="transform-origin:150px 168px"/>
    <line x1="34" y1="168" x2="266" y2="168" stroke="rgba(245,201,119,.5)" stroke-width="1.5"/>
    ${_oStars([[70,64,2.2,.3],[228,54,2.6,1],[262,96,2,1.6]])}
    </svg>`;
  if(key==='learn') return `<svg ${V}><g class="os-breathe" style="transform-origin:150px 130px">
    <path d="M150 86 C128 72 98 72 80 80 L80 164 C98 156 128 156 150 170 Z" fill="#241a3a" stroke="rgba(245,201,119,.4)" stroke-width="1.4"/>
    <path d="M150 86 C172 72 202 72 220 80 L220 164 C202 156 172 156 150 170 Z" fill="#2a1f44" stroke="rgba(245,201,119,.4)" stroke-width="1.4"/>
    <line x1="150" y1="86" x2="150" y2="170" stroke="rgba(245,201,119,.55)" stroke-width="1.4"/>
    <g stroke="rgba(245,201,119,.22)" stroke-width="1"><line x1="92" y1="100" x2="138" y2="94"/><line x1="92" y1="114" x2="138" y2="108"/><line x1="92" y1="128" x2="138" y2="122"/><line x1="162" y1="94" x2="208" y2="100"/><line x1="162" y1="108" x2="208" y2="114"/><line x1="162" y1="122" x2="208" y2="128"/></g></g>
    ${_oMotes([[150,120,2.6,0],[132,120,2,1.1],[168,120,2.2,2],[150,120,1.8,1.6],[140,118,2,.6]])}
    </svg>`;
  if(key==='collect') return `<svg ${V}><defs><radialGradient id="osc" cx="46%" cy="40%" r="60%"><stop offset="0" stop-color="#fffdf6"/><stop offset=".45" stop-color="#f7c972"/><stop offset=".85" stop-color="#e49b38"/><stop offset="1" stop-color="#9a5e1c"/></radialGradient><radialGradient id="osch" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#f6c977" stop-opacity=".5"/><stop offset="1" stop-color="#f0a84a" stop-opacity="0"/></radialGradient></defs>
    <circle cx="150" cy="112" r="70" fill="url(#osch)"/>
    <circle cx="150" cy="112" r="40" fill="none" stroke="rgba(245,201,119,.35)" stroke-width="2" stroke-linecap="round" class="os-sweep" style="transform-origin:150px 112px;transform:rotate(-90deg)"/>
    <circle cx="150" cy="112" r="30" fill="url(#osc)" class="os-breathe" style="transform-origin:150px 112px"/>
    <ellipse cx="143" cy="104" rx="7" ry="5" fill="#fffdf4" opacity=".8" transform="rotate(-25 143 104)"/>
    ${_oMotes([[90,150,2.4,0],[214,150,2.2,.9],[96,78,2.2,1.5],[206,74,2.4,.5],[150,182,2,2]])}
    </svg>`;
  if(key==='vedic') return `<svg ${V}><g class="os-spinr" style="transform-origin:150px 112px">
    <circle cx="150" cy="112" r="70" fill="none" stroke="rgba(245,201,119,.22)" stroke-width="1"/>
    <circle cx="150" cy="112" r="58" fill="none" stroke="rgba(245,201,119,.14)" stroke-width="1" stroke-dasharray="2 8"/>
    ${Array.from({length:12}).map((_,i)=>{const a=i*30*Math.PI/180;return `<line x1="${150+Math.cos(a)*64}" y1="${112+Math.sin(a)*64}" x2="${150+Math.cos(a)*70}" y2="${112+Math.sin(a)*70}" stroke="rgba(245,201,119,.4)" stroke-width="1.4"/>`;}).join('')}</g>
    <path d="M110 150 L132 96 L168 120 L196 80" fill="none" stroke="rgba(245,201,119,.45)" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
    ${_oStars([[110,150,2.4,.2],[132,96,3,.9],[168,120,2,1.4],[196,80,2.6,.5]])}
    <circle cx="150" cy="112" r="7" fill="#fff3d0" class="os-glow" style="filter:drop-shadow(0 0 7px #f5c977)"/>
    </svg>`;
  if(key==='mandala'){const rings=[64,50,36,22];return `<svg ${V}><g style="transform-origin:150px 112px" class="os-spin">
    ${rings.map((r,ri)=>`<g class="os-bloom" style="transform-origin:150px 112px;animation-delay:${ri*.18}s">${Array.from({length:8+ri*2}).map((_,i)=>{const n=8+ri*2;const a=i*2*Math.PI/n;const x=150+Math.cos(a)*r,y=112+Math.sin(a)*r;return `<ellipse cx="${x}" cy="${y}" rx="${7-ri}" ry="${13-ri*2}" fill="none" stroke="rgba(245,201,119,${.5-ri*.07})" stroke-width="1.2" transform="rotate(${a*180/Math.PI+90} ${x} ${y})"/>`;}).join('')}</g>`).join('')}
    <circle cx="150" cy="112" r="7" fill="#f5c977" class="os-glow"/></g></svg>`;}
  if(key==='badges') return `<svg ${V}><defs><linearGradient id="osb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff0c6"/><stop offset=".5" stop-color="#f5c977"/><stop offset="1" stop-color="#cf8a2e"/></linearGradient><clipPath id="osbc"><path d="M150 58 L164 92 L200 94 L172 118 L182 154 L150 134 L118 154 L128 118 L100 94 L136 92 Z"/></clipPath></defs>
    <circle cx="150" cy="112" r="72" fill="none" stroke="rgba(245,201,119,.16)" stroke-width="1" class="os-spin" style="transform-origin:150px 112px;stroke-dasharray:3 10"/>
    <g class="os-breathe" style="transform-origin:150px 112px"><path d="M150 58 L164 92 L200 94 L172 118 L182 154 L150 134 L118 154 L128 118 L100 94 L136 92 Z" fill="url(#osb)" stroke="#fff3d0" stroke-width="1.2"/>
    <circle cx="150" cy="110" r="15" fill="#241a0a" opacity=".25"/>
    <g clip-path="url(#osbc)"><rect x="0" y="40" width="46" height="150" fill="#ffffff" opacity=".45" class="os-shimmer" style="animation:osShimmer 3.4s ease-in-out infinite"/></g></g>
    ${_oStars([[92,70,2.4,.3],[214,78,2.6,1.1],[206,150,2.2,.7],[96,152,2,1.6]])}
    </svg>`;
  return '';
}
function onbDots(){let h='<div class="onb-dots">';for(let i=0;i<=ONB_LAST;i++)h+=`<span class="${i===onb.step?'on':''}"></span>`;return h+'</div>';}
function onbSlideFit(){ // soft gate: value slides free; the only required answer is >=1 intent
  if(onb.step===Q_INTENT)return onb.intents.length>0;
  return true;
}
async function renderOnboarding(){
  $('#nav').classList.add('hidden');
  const s=onb.step;
  try{track('onboarding_step',{step:s,label:onbLabel(s)},'onboarding');}catch(e){}
  let body='';
  if(s<NSL){
    const sl=ONB_SLIDES[s];
    body=`<div class="onb-hero">
      <div class="onb-anim onb-enter">${onbScene(sl.scene)}</div>
      <h1 class="onb-h onb-enter d1">${sl.h}</h1><p class="onb-p onb-enter d2">${sl.p}</p></div>`;
  }else if(s===Q_INTENT){
    body=`<div class="onb-qic onb-enter">${ic(ONB_QIC[Q_INTENT],'g')}</div><h1 class="onb-h sm onb-enter">What brings you to Lumen?</h1><p class="onb-p sm onb-enter d1">Pick any that feel true — we'll shape your practice around them.</p>
      <div class="onb-grid onb-enter d1">${ONB_INTENTS.map(([k,label,icn])=>`<button class="onb-chip ${onb.intents.includes(k)?'sel':''}" data-k="${k}"><span>${ic(icn,'g')}</span>${label}</button>`).join('')}</div>`;
  }else if(s===Q_FREQ){
    body=`<div class="onb-qic onb-enter">${ic(ONB_QIC[Q_FREQ],'g')}</div><h1 class="onb-h sm onb-enter">What rhythm are you hoping for?</h1><p class="onb-p sm onb-enter d1">We'll shape your streak goal around it — nothing's locked in.</p>
      <div class="onb-grid two onb-enter d1">${ONB_FREQS.map(([k,label,icn])=>`<button class="onb-chip wide ${onb.freq===k?'sel':''}" data-f="${k}"><span>${ic(icn,'g')}</span>${label}</button>`).join('')}</div>`;
  }else if(s===Q_TIME){
    body=`<div class="onb-qic onb-enter">${ic(ONB_QIC[Q_TIME],'g')}</div><h1 class="onb-h sm onb-enter">When do you like to practice?</h1><p class="onb-p sm onb-enter d1">We'll send a gentle nudge around then — never during your quiet hours.</p>
      <div class="onb-grid two onb-enter d1">${ONB_TIMES.map(([label,hr,icn])=>`<button class="onb-chip ${onb.timeHour===hr?'sel':''}" data-h="${hr}"><span>${ic(icn,'g')}</span>${label}</button>`).join('')}</div>`;
  }else if(s===Q_DUR){
    body=`<div class="onb-qic onb-enter">${ic(ONB_QIC[Q_DUR],'g')}</div><h1 class="onb-h sm onb-enter">How long feels right to sit?</h1><p class="onb-p sm onb-enter d1">We'll set your timer here — one tap changes it before any session.</p>
      <div class="onb-grid onb-enter d1">${ONB_DURS.map(([m,label,sub,icn])=>`<button class="onb-chip ${onb.minutes===m?'sel':''}" data-d="${m}"><span>${ic(icn,'g')}</span><span style="display:flex;flex-direction:column;line-height:1.14;text-align:left"><b style="font-weight:700">${sub}</b><small class="muted" style="font-size:12px">${label}</small></span></button>`).join('')}</div>`;
  }else if(s===Q_LEVEL){
    body=`<div class="onb-qic onb-enter">${ic(ONB_QIC[Q_LEVEL],'g')}</div><h1 class="onb-h sm onb-enter">How familiar is this for you?</h1><p class="onb-p sm onb-enter d1">No wrong answer — it just helps us meet you where you are.</p>
      <div class="onb-grid onb-enter d1">${ONB_LEVELS.map(([label,k,icn])=>`<button class="onb-chip wide ${onb.level===k?'sel':''}" data-l="${k}"><span>${ic(icn,'g')}</span>${label}</button>`).join('')}</div>`;
  }else{
    let live=0;try{live=(await api('presence')).now;}catch(e){}
    body=`<div class="onb-hero" style="padding-bottom:6px"><div class="onb-anim onb-enter" style="max-width:210px">${onbScene('collect')}</div>
      <h1 class="onb-h onb-enter d1">Save your light</h1>
      <p class="onb-p">${live>0?`<b>${live}</b> meditating right now. `:''}Create your account to start a streak, keep your journal, and claim your place on the map.</p></div>
      <div class="card" style="margin-top:4px">
        <label>Email</label><input id="em" type="email" autocomplete="email" placeholder="you@example.com">
        <label>Password</label><input id="pw" type="password" autocomplete="new-password" placeholder="at least 6 characters">
        <label>Display name <span class="muted" style="font-weight:400">(shown on the map)</span></label><input id="nm" placeholder="e.g. Matthew">
        <label>Birthday <span class="muted" style="font-weight:400">(powers your daily Vedic reading)</span></label><input id="bd" type="date">
        <label>Birth time &amp; place <span class="muted" style="font-weight:400">(optional — unlocks your birth star &amp; daśā)</span></label>
        <div style="display:flex;gap:8px"><input id="bt" type="time" style="flex:0 0 42%"><input id="bp" placeholder="City of birth" style="flex:1"></div>
        <p class="muted" style="font-size:11px;margin:8px 0 0">Private to you — used only to compute your reading, never shown on the map or shared. You can add or change it later in your profile.</p>
        <div class="err" id="er"></div>
        <button class="btn gold" id="create">Create account &amp; begin</button>
      </div>`;
  }
  $('#app').innerHTML=`
    <div class="onb-top"><span class="onb-brand">${lumenMark('mark')} Lumen</span>
      ${s<NSL?'<a class="onb-signin" id="toSignin">Sign in</a>':''}</div>
    <div class="onb-body">${body}</div>
    <div class="onb-foot">
      ${onbDots()}
      <div class="onb-nav">
        ${s>0&&s<=ONB_LAST?'<button class="btn ghost" id="onbBack" style="flex:0 0 auto;width:auto;padding:12px 18px">Back</button>':''}
        ${s<ONB_LAST?`<button class="btn gold" id="onbNext" ${onbSlideFit()?'':'disabled'}>${s>=Q_INTENT?'Continue':'Next'}</button>`:''}
        ${(s>Q_INTENT&&s<ONB_LAST)?'<button class="btn ghost" id="onbSkip" style="flex:0 0 auto;width:auto;padding:12px 16px">Skip</button>':''}
      </div>
    </div>`;
  const si=$('#toSignin');if(si)si.onclick=()=>{try{localStorage.setItem('lumen_onb_done','1');}catch(e){}renderAuth();};
  const bk=$('#onbBack');if(bk)bk.onclick=()=>{onb.step=Math.max(0,onb.step-1);renderOnboarding();};
  const nx=$('#onbNext');if(nx)nx.onclick=()=>{if(!onbSlideFit())return;onb.step++;renderOnboarding();};
  const sk=$('#onbSkip');if(sk)sk.onclick=()=>{onb.step++;renderOnboarding();};
  document.querySelectorAll('.onb-chip[data-k]').forEach(b=>b.onclick=()=>{const k=b.dataset.k;
    onb.intents.includes(k)?onb.intents=onb.intents.filter(x=>x!==k):onb.intents.push(k);renderOnboarding();});
  document.querySelectorAll('.onb-chip[data-f]').forEach(b=>b.onclick=()=>{onb.freq=b.dataset.f;renderOnboarding();});
  document.querySelectorAll('.onb-chip[data-d]').forEach(b=>b.onclick=()=>{onb.minutes=+b.dataset.d;renderOnboarding();});
  document.querySelectorAll('.onb-chip[data-h]').forEach(b=>b.onclick=()=>{onb.timeHour=+b.dataset.h;renderOnboarding();});
  document.querySelectorAll('.onb-chip[data-l]').forEach(b=>b.onclick=()=>{onb.level=b.dataset.l;renderOnboarding();});
  const cr=$('#create');if(cr)cr.onclick=onbCreate;
}
async function onbCreate(){
  const er=$('#er');er.textContent='';
  const email=$('#em').value.trim(),password=$('#pw').value,name=$('#nm').value.trim();
  const birth_date=($('#bd')&&$('#bd').value)||'';
  const birth_time=($('#bt')&&$('#bt').value)||'';
  const birth_place=($('#bp')&&$('#bp').value.trim())||'';
  const birth_tz=-new Date().getTimezoneOffset();
  if(!email||!password){er.textContent='Enter your email and password.';return;}
  if(password.length<6){er.textContent='Password needs at least 6 characters.';return;}
  const btn=$('#create');btn.disabled=true;btn.textContent='Creating…';
  try{
    await api('signup','POST',{email,password,name,birth_date,birth_time,birth_place,birth_tz});
    try{localStorage.setItem('lumen_intent',JSON.stringify(onb.intents));
        if(onb.freq)localStorage.setItem('lumen_freq',onb.freq);
        if(onb.minutes){localStorage.setItem('lumen_pref_min',String(onb.minutes));pick.minutes=onb.minutes;}
        localStorage.setItem('lumen_onb_done','1');}catch(e){}
    try{const tz=-new Date().getTimezoneOffset();
        await api('notif/prefs','POST',{tz_offset_min:tz,pref_hour:onb.timeHour,sto:true});}catch(e){}
    const r=await api('me');ME=r.profile;
    $('#nav').classList.remove('hidden');bindNav();go('meditate');
  }catch(e){btn.disabled=false;btn.textContent='Create account & begin';er.textContent=e;}
}

/* ---- meditate ---- */
function challengeCardHTML(ch){
  if(!ME)return '';
  const J=ME.journal||{total:0,daily:0,season:0,deep:0};
  const places=(ME.places!=null?ME.places:((ch&&ch.places)||0));
  const lessonsDone=Object.values(ME.lessons||{}).filter(l=>l&&l.count>0).length;
  const totalLessons=(typeof LESSONS!=='undefined'?LESSONS.length:0);
  const mStreak=ME.streak||0, pStreak=(ch&&ch.streak)||0, shared=(ch&&ch.shared_today)||0;
  const lg=ME.league||{};
  const streakChip=mStreak>0?`<span class="atlas-streak">${ic('flame','flame grad-flame glow')}<b>${mStreak}</b> day streak</span>`:'';
  // progress + remaining for each dimension
  const lvlInto=ME.level_into||0, lvlNeed=ME.level_need||1, lvlPct=Math.round(100*lvlInto/(lvlInto+lvlNeed));
  const jPct=totalLessons?Math.round(100*lessonsDone/totalLessons):0;
  const JM=[3,5,10,20,40,75,120,200], jNext=JM.find(m=>m>(J.total||0))||((J.total||0)+100), jrPct=Math.round(100*(J.total||0)/jNext);
  const tNext=(ch&&ch.next_milestone)||Math.max(3,places+ (places<3?3-places:1)), tPct=tNext?Math.round(100*places/tNext):0;
  const cAt=lg.at||0, cNextAt=lg.next_at, cPct=cNextAt?Math.min(100,Math.round(100*((ME.weekly_light||0)-cAt)/((cNextAt-cAt)||1))):100;
  const jsub=[J.daily?J.daily+' daily':'',J.season?J.season+' seasonal':'',J.deep?J.deep+' pillar':''].filter(Boolean).join(' · ')||'open your first letter';
  // facet(colors, iconHTML, name, valueHTML, progress%, subline)
  const facet=(c1,c2,iconHTML,name,valHTML,pct,sub)=>`<div class="atlas-facet" style="--fc:${c1};--fc2:${c2}">
    <span class="atlas-fic">${iconHTML}</span>
    <div class="atlas-fmain">
      <div class="atlas-ftop"><span class="atlas-fname">${name}</span>${valHTML}</div>
      <div class="atlas-fbar"><i style="width:${Math.max(4,Math.min(100,pct))}%"></i></div>
      <div class="atlas-fsub">${sub}</div>
    </div></div>`;
  const val=(n,u,cls)=>`<span class="atlas-fval ${cls||''}">${fmt(n)}${u?`<small>${u}</small>`:''}</span>`;
  return `<div class="card atlas-card">
    <div class="atlas-head"><span class="atlas-eyebrow">${ic('compass','g')} Atlas</span>${streakChip}</div>
    <div class="atlas-tag">A map of your whole practice.</div>
    <div class="atlas-facets">
      ${facet('#f5c977','#f59e0b',ic('meditate'),'Meditation',val(ME.total_sessions||0,'sits'),lvlPct,
        `${fmt(ME.total_minutes||0)} min · ${100-lvlPct}% to Level ${(ME.level||1)+1}`)}
      ${facet('#22c55e','#4ade80',ic('lotus'),'Journeys',`<span class="atlas-fval">${lessonsDone}<small>/ ${totalLessons}</small></span>`,jPct,
        totalLessons&&lessonsDone>=totalLessons?'every journey walked':`${totalLessons-lessonsDone} lesson${(totalLessons-lessonsDone)===1?'':'s'} to go`)}
      ${facet('#a855f7','#c084fc',ic('book'),'Journal',val(J.total||0,'entries'),jrPct,jsub)}
      ${facet('#06b6d4','#38bdf8',ic('globe'),'Travel',val(places,places===1?'place':'places'),tPct,
        places?`${tNext-places} to your ${tNext}-spot badge${pStreak>0?' · '+pStreak+'-day photo streak':''}`:'light a place to begin your map')}
      ${facet(lg.color||'#ec4899',lg.color2||'#f472b6',leagueIcon(lg.name),'Community',val(ME.weekly_light||0,'light',''),cPct,
        cNextAt?`${esc(lg.name||'Ember')} · ${fmt(Math.max(0,cNextAt-(ME.weekly_light||0)))} to ${esc(lg.next||'next')}${shared>0?' · '+shared+' shared today':''}`:`${esc(lg.name||'')} — top league`)}
    </div>
    <div class="atlas-foot" onclick="go('map')">${ic('globe','g')} See where the world is meditating ${ic('up','rt')}</div>
  </div>`;
}
function horoscopeCardHTML(h){
  if(!h)return '';
  if(h.need_sign){
    return `<div class="card horo-card">
      <div class="horo-eyebrow"><span>${ic('nova','g')} Today's sky</span><span class="horo-constell"><svg viewBox="0 0 56 26" width="54" height="25" fill="none" aria-hidden="true"><path d="M5 18 L15 9 L25 15 L35 6 L46 12 L50 19" stroke="rgba(245,201,119,.4)" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"/><g fill="#f5c977"><circle cx="5" cy="18" r="1.5"/><circle cx="15" cy="9" r="2.1"/><circle cx="25" cy="15" r="1.3"/><circle cx="35" cy="6" r="1.8"/><circle cx="46" cy="12" r="1.5"/><circle cx="50" cy="19" r="1.1"/></g></svg></span></div>
      <div class="horo-intro muted">Choose your rāśi — your Vedic Moon sign — for a daily reading grounded in the nakshatra of the day.</div>
      <div class="horo-signs">${h.signs.map(s=>`<button class="horo-sign" data-sign="${esc(s.key)}"><span class="hs-med"><span class="hs-glyph">${s.glyph}︎</span></span><span class="hs-nm">${esc(s.sanskrit||s.name)}</span><span class="hs-sub">${esc(s.name)}</span></button>`).join('')}</div>
    </div>`;
  }
  const SS={rain:'Rain',forest:'Forest',ocean:'Ocean',space:'Deep Space',silence:'Silence'};
  const mins=h.minutes||10;
  const snd=SS[h.soundscape]||esc(h.soundscape||'');
  return `<div class="card horo-card">
    <div class="horo-eyebrow"><span>${ic('nova','g')} Today's sky</span><span class="horo-constell"><svg viewBox="0 0 56 26" width="54" height="25" fill="none" aria-hidden="true"><path d="M5 18 L15 9 L25 15 L35 6 L46 12 L50 19" stroke="rgba(245,201,119,.4)" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"/><g fill="#f5c977"><circle cx="5" cy="18" r="1.5"/><circle cx="15" cy="9" r="2.1"/><circle cx="25" cy="15" r="1.3"/><circle cx="35" cy="6" r="1.8"/><circle cx="46" cy="12" r="1.5"/><circle cx="50" cy="19" r="1.1"/></g></svg></span></div>
    <div class="horo-head">
      <span class="horo-medallion"><span class="horo-sym">${h.glyph}︎</span></span>
      <div>
        <div class="horo-name">${esc(h.sanskrit||h.name)}</div>
        <div class="horo-sub">${ic('moon','p')} ${esc(h.name)}${h.nakshatra?' · Moon in '+esc(h.nakshatra):''}</div>
      </div>
    </div>
    <div class="horo-text">${esc(h.text)}</div>
    <div class="horo-cta">
      <button class="rndbtn horo-listen" title="Hear it aloud" aria-label="Hear it aloud">${ic('waveform')}</button>
      <button class="horo-sit" data-snd="${esc(h.soundscape)}" data-min="${mins}">${ic(h.soundscape||'silence')} Meditate with this · ${mins} min${snd?' · '+snd:''}</button>
    </div>
    ${h.janma?`<div class="horo-foot">${ic('lotus','g')} Birth star ${esc(h.janma)} · daśā ${esc(h.maha)}–${esc(h.antar)}</div>`
             :`<div class="horo-foot horo-addnatal" style="cursor:pointer">${ic('nova','g')} Add your birth time for your birth star &amp; daśā</div>`}
  </div>`;
}
async function addNatal(){
  const t=prompt('Birth time (HH:MM, 24h) — optional but unlocks your birth star & daśā:','');
  if(t===null)return;
  const place=prompt('City of birth (optional):','')||'';
  try{await api('natal','POST',{birth_time:(t||'').trim(),birth_place:place.trim(),birth_tz:-new Date().getTimezoneOffset()});
    toast('Birth details saved '+ic('spark','g'));renderMeditate();}
  catch(e){toast(e);}
}
function _btnRound(btn){return btn.classList.contains('rndbtn')||btn.classList.contains('pick-listen');}
// Horoscope + daily-pick narration uses the SAME pipeline as lessons: ElevenLabs
// via /api/tts, played through the shared Web Audio context (so it never fights the
// soundscape and works on iOS), with the quote-stripping text policy and the
// device-voice fallback — all handled by narrate(). One voice, one path (NARRATOR.md).
let _horoBtn=null;
function playHoroscope(btn,text){
  if(!text)return;
  const orig=btn.dataset.orig||btn.innerHTML; btn.dataset.orig=orig;
  const round=_btnRound(btn);
  const set=(label)=>{if(round)btn.classList.toggle('playing',!!label);else btn.innerHTML=label?ic('sound')+' '+label:orig;};
  const done=()=>{btn.disabled=false;if(round)btn.classList.remove('playing');btn.innerHTML=orig;if(_horoBtn===btn)_horoBtn=null;};
  // tap again to stop
  if(_horoBtn===btn){try{stopNarration();}catch(e){}done();return;}
  try{stopNarration();}catch(e){}   // stop any other narration first
  _horoBtn=btn; btn.disabled=false; set('Playing…');
  narrate(text, done);              // ElevenLabs -> shared Web Audio context, device-voice fallback
}
// First-run meditation onboarding: a pledge + how many days/week they want to
// sit (saved server-side via /api/goal for reminders + record-keeping), then a
// nudge toward the three ways to practice. Shown once (localStorage gate).
let mediGoal=5;
let mediGoal_touched=false;
function _mediPledged(){try{return localStorage.getItem('lumen_medi_pledged')==='1';}catch(e){return true;}}
function _medEx(icn,title,desc){
  return `<div class="jwc"><div class="jwc-ico">${ic(icn,'g')}</div>`
    +`<div class="jwc-body"><div class="jwc-title">${title}</div>`
    +`<div class="jwc-desc">${desc}</div></div></div>`;
}
/* Your light — a living orb that brightens, grows and gathers rays as your
   Light (XP), level and sessions climb. The ring around it fills with your
   progress to the next level. It lights up a little more every time you sit. */
function lumenOrb(me){
  const lvl=Math.max(1,me.level||1);
  const into=me.level_into||0, need=me.level_need||100;
  const prog=Math.max(0,Math.min(1,into/((into+need)||1)));
  const b=Math.max(.16,Math.min(1,(lvl-1)/11 + prog/11));   // brightness 0..1, grows with level
  const col=(me.league&&me.league.color)||'#f5c977';
  const rays=Math.min(18,6+Math.floor(lvl*0.9));
  const motes=Math.min(12,Math.floor((me.total_sessions||0)/5));
  const coreR=17+Math.round(20*b);
  let rayEls='';
  for(let i=0;i<rays;i++){
    const a=(i/rays)*Math.PI*2;
    const r0=coreR+7, r1=coreR+12+24*b*(0.6+0.4*Math.abs(Math.sin(i*2.3)));
    const x0=(80+Math.cos(a)*r0).toFixed(1),y0=(80+Math.sin(a)*r0).toFixed(1);
    const x1=(80+Math.cos(a)*r1).toFixed(1),y1=(80+Math.sin(a)*r1).toFixed(1);
    rayEls+=`<line x1="${x0}" y1="${y0}" x2="${x1}" y2="${y1}" stroke="${col}" stroke-width="2" stroke-linecap="round" opacity="${(0.22+0.5*b).toFixed(2)}"/>`;
  }
  let moteEls='';
  for(let i=0;i<motes;i++){
    const a=(i/motes)*Math.PI*2+0.6, rr=coreR+30+(i%2?9:0);
    const x=(80+Math.cos(a)*rr).toFixed(1),y=(80+Math.sin(a)*rr).toFixed(1);
    moteEls+=`<circle cx="${x}" cy="${y}" r="${(1.5+1.4*b).toFixed(1)}" fill="#fff" opacity="${(0.35+0.45*b).toFixed(2)}"/>`;
  }
  const pr=coreR+30, arc=(2*Math.PI*pr*prog).toFixed(1);
  return `<svg class="lumorb" viewBox="0 0 160 160" width="100%" height="100%">
    <defs>
      <radialGradient id="lo_core" cx="50%" cy="45%" r="55%">
        <stop offset="0" stop-color="#fff" stop-opacity="${(0.6+0.35*b).toFixed(2)}"/>
        <stop offset="0.4" stop-color="${col}" stop-opacity="${(0.5+0.45*b).toFixed(2)}"/>
        <stop offset="1" stop-color="${col}" stop-opacity="0"/></radialGradient>
      <radialGradient id="lo_halo" cx="50%" cy="50%" r="50%">
        <stop offset="0" stop-color="${col}" stop-opacity="${(0.3*b+0.05).toFixed(2)}"/>
        <stop offset="1" stop-color="${col}" stop-opacity="0"/></radialGradient>
    </defs>
    <circle cx="80" cy="80" r="79" fill="url(#lo_halo)"/>
    <g class="lumorb-rays">${rayEls}</g>
    ${moteEls}
    <circle cx="80" cy="80" r="${pr}" fill="none" stroke="#ffffff12" stroke-width="2.5"/>
    <circle cx="80" cy="80" r="${pr}" fill="none" stroke="${col}" stroke-width="3" stroke-linecap="round"
      stroke-dasharray="${arc} 9999" transform="rotate(-90 80 80)" opacity="0.92"
      style="filter:drop-shadow(0 0 5px ${col})"/>
    <circle cx="80" cy="80" r="${coreR+10}" fill="url(#lo_core)"/>
    <circle cx="80" cy="80" r="${Math.round(coreR*0.52)}" fill="#fff" opacity="${(0.45+0.4*b).toFixed(2)}"/>
  </svg>`;
}
function renderMeditatePledge(){
  if(ME&&ME.goal_days&&!mediGoal_touched)mediGoal=ME.goal_days;
  const dayword=mediGoal===1?'day':'days';
  const chips=[1,2,3,4,5,6,7].map(n=>`<button class="mgc${n===mediGoal?' on':''}" data-d="${n}">${n}</button>`).join('');
  $('#app').innerHTML=`<div class="brand"><span class="mark">${lumenMark('mark')}</span><b>Lumen</b></div>`
  +`<div class="jwelc">`
    +`<div class="jwelc-hero"><div class="jwelc-halo">${ic('lotus','g')}</div>`
      +`<h2 class="jwelc-h">A promise to your practice</h2>`
      +`<p class="jwelc-sub">Meditation works the way exercise does — not from one big effort, but from showing up. Even 10–13 minutes a day has been shown to sharpen focus, memory and mood in about 8 weeks.</p>`
      +`<div class="jwc-cite" style="text-align:center;margin-top:6px">Basso et al., 2019</div></div>`
    +`<div class="mgoal">`
      +`<div class="mgoal-q">How many days a week do you want to sit?</div>`
      +`<div class="mgoal-chips">${chips}</div>`
      +`<div class="mgoal-echo">${ic('flame','g')} <b>${mediGoal}</b> ${dayword} a week — we’ll keep your streak and gently remind you.</div>`
    +`</div>`
    +`<div class="jwelc-h3">Three ways to practice</div>`
    +`<div class="jwelc-cards">`
      +_medEx('spark','A daily exercise','A short guided practice, picked fresh for you each day.')
      +_medEx('compass','Lessons & journeys','Guided voice journeys and courses that build the skill over time.')
      +_medEx('lotus','Free-form meditation','Choose a soundscape and a length, and simply sit.')
    +`</div>`
    +`<div class="jwelc-pledge">`
      +`<div class="jwelc-pl-h">${ic('seal','g')} My pledge</div>`
      +`<p class="jwelc-pl-body">“I’ll sit ${mediGoal} ${dayword} a week — showing up for my own mind, one breath at a time.”</p>`
      +`<button class="btn seal-cta jwelc-seal" id="mpl-sign">${ic('seal','seal-ic grad-gold')} Set my rhythm &amp; begin</button>`
      +`<button class="jwelc-skip" id="mpl-skip">Maybe later</button>`
    +`</div>`
  +`</div>`;
  document.querySelectorAll('.mgc').forEach(b=>b.onclick=()=>{mediGoal=+b.dataset.d;mediGoal_touched=true;renderMeditatePledge();});
  $('#mpl-sign').onclick=async()=>{try{await api('goal','POST',{days:mediGoal});if(ME)ME.goal_days=mediGoal;}catch(e){}
    try{localStorage.setItem('lumen_medi_pledged','1');localStorage.setItem('lumen_medi_goal',String(mediGoal));}catch(e){}
    toast('Your rhythm is set ✦');renderMeditate();};
  $('#mpl-skip').onclick=()=>{try{localStorage.setItem('lumen_medi_pledged','1');}catch(e){}renderMeditate();};
}
/* Subtle sparks that flick off the journal outline — spark, pause, spark again.
   Each arcs up over the top border and falls back toward the bottom. Reduced-
   motion safe, off-screen paused, torn down per render. */
function ctaSparks(){
  if(window.__ctaSparks){try{window.__ctaSparks();}catch(e){}window.__ctaSparks=null;}
  if(matchMedia('(prefers-reduced-motion: reduce)').matches)return;
  const btn=document.getElementById('journalCta'); if(!btn)return;
  btn.style.position='relative';
  const PAD=46,BOT=12;
  const cv=document.createElement('canvas');
  cv.style.cssText='position:absolute;left:0;top:-'+PAD+'px;width:100%;height:calc(100% + '+(PAD+BOT)+'px);pointer-events:none;z-index:0';
  btn.insertBefore(cv, btn.firstChild);
  const ctx=cv.getContext('2d'); const dpr=Math.min(window.devicePixelRatio||1,2);
  let W=0,H=0,topY=0,botY=0,tx=0,ty=0,tw=0;
  function size(){const r=btn.getBoundingClientRect(); if(!r.width)return;
    W=cv.width=Math.round(r.width*dpr); H=cv.height=Math.round((r.height+PAD+BOT)*dpr); topY=PAD*dpr; botY=(PAD+r.height)*dpr;
    const tm=btn.querySelector('.jbook'); if(tm){const q=tm.getBoundingClientRect(); tx=(q.left-r.left+q.width/2)*dpr; ty=(q.top-r.top+PAD+q.height*0.58)*dpr; tw=q.width*dpr;} else {tx=W*0.28; ty=topY+34*dpr; tw=40*dpr;}}
  size();
  const P=[]; const grav=0.03*dpr; let raf=0,dead=false,last=performance.now(),nextBurst=500,inBurst=0,tick=0,bAcc=0,visible=true;
  function spark(){const x=(0.08+Math.random()*0.84)*W; const vx=(Math.random()-0.5)*1.3*dpr; const vy=-(1.15+Math.random()*0.95)*dpr;
    P.push({x:x,y:topY,vx:vx,vy:vy,life:1,r:(0.8+Math.random()*1.1)*dpr,tw:Math.random()*6.28,g:1});}
  function behindSpark(){const a=-Math.PI/2+(Math.random()-0.5)*1.25; const sp=(0.7+Math.random()*1.35)*dpr;
    P.push({x:tx+(Math.random()-0.5)*tw*1.05, y:ty+(Math.random()-0.2)*tw*0.5, vx:Math.cos(a)*sp*0.6, vy:Math.sin(a)*sp-0.5*dpr, life:1, r:(0.7+Math.random()*1.0)*dpr, tw:Math.random()*6.28, g:0.42});}
  function frame(now){raf=0; if(dead||!visible)return; const dt=Math.min(now-last,50); last=now; const f=dt/16;
    bAcc+=dt; if(bAcc>140){bAcc=0; behindSpark(); if(Math.random()<0.4)behindSpark();}
    nextBurst-=dt;
    if(inBurst>0){ tick-=dt; if(tick<=0){ spark(); inBurst--; tick=90+Math.random()*80; } }
    else if(nextBurst<=0){ inBurst=1+Math.floor(Math.random()*3); tick=0; nextBurst=2000+Math.random()*2200; }
    ctx.clearRect(0,0,W,H); ctx.globalCompositeOperation='lighter';
    for(let i=P.length-1;i>=0;i--){const p=P[i];
      p.vy+=grav*p.g*f; p.x+=p.vx*f; p.y+=p.vy*f; p.life-=dt/2400;
      if(p.life<=0 || p.y>botY+8*dpr){P.splice(i,1);continue;}
      const al=Math.max(0,Math.min(1,p.life*1.1))*(0.4+0.22*Math.sin(now*0.013+p.tw)); const R=p.r;
      const rg=ctx.createRadialGradient(p.x,p.y,0,p.x,p.y,R*4.4);
      rg.addColorStop(0,'rgba(255,238,195,'+(al*0.55)+')'); rg.addColorStop(0.4,'rgba(246,196,104,'+(al*0.24)+')'); rg.addColorStop(1,'rgba(246,196,104,0)');
      ctx.fillStyle=rg; ctx.beginPath(); ctx.arc(p.x,p.y,R*4.4,0,6.2832); ctx.fill();
      ctx.fillStyle='rgba(255,248,228,'+(al*0.55)+')'; ctx.beginPath(); ctx.arc(p.x,p.y,R*0.7,0,6.2832); ctx.fill();
    }
    ctx.globalCompositeOperation='source-over';
    raf=requestAnimationFrame(frame);
  }
  function start(){if(!raf&&!dead){last=performance.now();raf=requestAnimationFrame(frame);}}
  const io=new IntersectionObserver(es=>{es.forEach(e=>visible=e.isIntersecting); if(visible)start();}); io.observe(btn);
  window.addEventListener('resize',size);
  start();
  window.__ctaSparks=function(){dead=true; if(raf)cancelAnimationFrame(raf); try{io.disconnect();}catch(e){} window.removeEventListener('resize',size); if(cv.parentNode)cv.parentNode.removeChild(cv);};
}
function sessionSummary(){const s=SOUNDS.find(x=>x[0]===pick.sound); return `${pick.minutes} min · ${ic((s?s[0]:'silence'),'qm-snd')} ${s?s[2]:'Silence'}`;}
function syncQuick(){const q=document.getElementById('quickSummary'); if(q)q.innerHTML=sessionSummary();}
function closeSessionSheet(){const o=document.getElementById('sessSheet'); if(o){o.classList.remove('on'); setTimeout(()=>{try{o.remove();}catch(e){}},240);}}
function openSessionSheet(){
  closeSessionSheet();
  const ov=el(`<div class="sheet-ov" id="sessSheet"><div class="sheet" role="dialog" aria-label="Set your session">
    <div class="sheet-grip"></div>
    <h3 class="sheet-h">Set your session</h3>
    <div class="sheet-lbl">${ic('clock')} Duration</div>
    <div class="grid4" id="mDurs">${[5,10,20,30].map(d=>`<div class="chip dur-chip ${d===pick.minutes?'sel':''}" data-d="${d}"><div class="big">${d}</div><div class="chip-unit">min</div><div class="chip-sub">${DUR_LABEL[d]||''}</div></div>`).join('')}</div>
    <div class="sheet-lbl" style="margin-top:16px">${ic('sound')} Soundscape</div>
    <div class="grid3" id="mSnds">${SOUNDS.map(s=>`<div class="chip snd-chip ${s[0]===pick.sound?'sel':''}" data-s="${s[0]}"><div class="big">${ic(s[1])}</div>${s[2]}</div>`).join('')}</div>
    <button class="btn gold" id="mStart" style="margin-top:20px">Begin session &rarr;</button>
  </div></div>`);
  document.body.appendChild(ov);
  requestAnimationFrame(()=>ov.classList.add('on'));
  ov.addEventListener('click',e=>{if(e.target===ov)closeSessionSheet();});
  ov.querySelectorAll('#mDurs .chip').forEach(c=>c.onclick=()=>{pick.minutes=+c.dataset.d; ov.querySelectorAll('#mDurs .chip').forEach(x=>x.classList.toggle('sel',x===c)); syncQuick();});
  ov.querySelectorAll('#mSnds .chip').forEach(c=>c.onclick=()=>{pick.sound=c.dataset.s; ov.querySelectorAll('#mSnds .chip').forEach(x=>x.classList.toggle('sel',x===c)); syncQuick();});
  ov.querySelector('#mStart').onclick=()=>{closeSessionSheet(); startSession();};
}
async function renderMeditate(){
  if(!_mediPledged()){renderMeditatePledge();return;}
  let pres={now:0,today_sessions:0};try{pres=await api('presence');}catch(e){}
  let dp=null;try{dp=(await api('lifeos/prompts')).prompts;}catch(e){}
  let chal=null;try{chal=await api('challenge?tz='+(-new Date().getTimezoneOffset()));}catch(e){}
  let horo=null;try{horo=await api('horoscope?tz='+(-new Date().getTimezoneOffset()));}catch(e){}
  const durs=[5,10,20,30];
  const PICK=todaysPick();
  const REST=recommendedLessons().filter(l=>!PICK||l.code!==PICK.code);
  const _h=new Date().getHours();
  const _greet=_h<5?'Rest well':_h<12?'Good morning':_h<17?'Good afternoon':_h<22?'Good evening':'Resting hours';
  const _nm=(ME&&ME.name)?esc(ME.name.split(' ')[0]):'';
  const _date=new Date().toLocaleDateString(undefined,{weekday:'short',month:'short',day:'numeric'});
  $('#app').innerHTML=`
  <header class="hdr">
    <div class="hdr-l">
      <span class="hdr-mark">${lumenMark('')}</span>
      <div class="hdr-wm"><span class="hdr-name">lumen</span><span class="hdr-tag">light, one breath at a time</span></div>
    </div>
    <div class="hdr-r">
      <div class="hdr-greet">${_greet}${_nm?', '+_nm:''}</div>
      <div class="hdr-date">${_date}</div>
    </div>
  </header>
  <div class="card home-hero" style="--lc:${ME.league.color};--lc2:${ME.league.color2||ME.league.color}">
    <div class="orb-hero">
      <div class="orb-stage" id="lumStage" role="img" aria-label="Your light — Level ${ME.level}">
        <div class="orb-fallback" id="lumFallback"></div>
        <canvas id="lumOrbCanvas"></canvas>
        <svg viewBox="0 0 100 100" aria-hidden="true">
          <defs>
            <linearGradient id="arcGrad" gradientUnits="userSpaceOnUse" x1="50" y1="4" x2="96" y2="50">
              <stop id="g0" offset="0" stop-color="#ff6a13" stop-opacity=".15"/>
              <stop id="g1" offset=".6" stop-color="#ff9a3a" stop-opacity=".85"/>
              <stop id="g2" offset="1" stop-color="#ffe2b0"/>
            </linearGradient>
            <filter id="soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation=".9"/></filter>
            <radialGradient id="head"><stop offset="0" stop-color="#fff6e6"/><stop id="h1" offset=".35" stop-color="#ffc173" stop-opacity=".9"/><stop id="h2" offset="1" stop-color="#ff7a1a" stop-opacity="0"/></radialGradient>
          </defs>
          <circle cx="50" cy="50" r="46" fill="none" stroke="rgba(255,255,255,.055)" stroke-width=".35"/>
          <g transform="rotate(-90 50 50)">
            <circle class="arcGlow" cx="50" cy="50" r="46" fill="none" stroke="url(#arcGrad)" stroke-width="1.6" stroke-linecap="round" filter="url(#soft)" opacity=".55" pathLength="1000" stroke-dasharray="0 1000"/>
            <circle class="arc" cx="50" cy="50" r="46" fill="none" stroke="url(#arcGrad)" stroke-width=".5" stroke-linecap="round" pathLength="1000" stroke-dasharray="0 1000"/>
          </g>
          <g class="headDot"><circle r="3.2" fill="url(#head)"/><circle r=".75" fill="#fff8ec"/></g>
        </svg>
      </div>
      <div class="orb-lv">Level ${ME.level}</div>
      <div class="orb-sub muted">${fmt(ME.level_into)} / ${fmt(ME.level_into+ME.level_need)} light to Level ${ME.level+1}</div>
    </div>
    <div class="hh-top">
      <div class="hh-league"><span class="hh-badge" style="color:${ME.league.color}">${leagueIcon(ME.league.name)}</span>
        <div><div class="hh-lg-name" style="color:${ME.league.color}">${ME.league.name} league</div>
        <div class="muted" style="font-size:12px">Lv ${ME.level} · ${fmt(ME.light)} light</div></div></div>
      <div class="hh-streak">${ic('flame','flame grad-flame glow')}<b>${ME.streak}</b><span>day${ME.streak===1?'':'s'}</span></div>
    </div>
    ${ME.league.next?`<div class="bar hh-bar"><i style="width:${Math.min(100,Math.round(100*(ME.weekly_light-ME.league.at)/((ME.league.next_at-ME.league.at)||1)))}%;background:linear-gradient(90deg,${ME.league.color},${ME.league.color2||ME.league.color})"></i></div>
      <div class="muted" style="font-size:12px;margin-top:5px">${fmt(Math.max(0,ME.league.next_at-ME.weekly_light))} light to <b style="color:var(--text)">${leagueIcon(ME.league.next,'g')} ${ME.league.next}</b></div>`
      :`<div class="pill" style="border-color:var(--gold);color:var(--gold);align-self:flex-start">${ic('nova','g glow')} Top league — keep it lit</div>`}
    <div class="hh-live">${ic('globe','live-globe')} <b>${pres.now}</b>&nbsp;meditating now · ${pres.today_sessions} sat today</div>
  </div>
  <button class="journal-cta" id="journalCta" type="button"><svg class="jbook" viewBox="0 0 44 48" aria-hidden="true"><defs><linearGradient id="jbCov" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f0bd69"/><stop offset="1" stop-color="#b9792e"/></linearGradient><linearGradient id="jbSpn" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#6f4616"/><stop offset=".5" stop-color="#b9823a"/><stop offset="1" stop-color="#7a4e1a"/></linearGradient></defs><rect x="12" y="7.5" width="26" height="35" rx="2" fill="#f1e3c2"/><g stroke="#cdb888" stroke-width=".5" opacity=".7"><path d="M35.5 10 V40"/><path d="M36.6 10.5 V39.5"/></g><rect x="9" y="5" width="26" height="36" rx="2.6" fill="url(#jbCov)" stroke="#5e3b12" stroke-width="1"/><rect x="9" y="5" width="6.5" height="36" rx="2.6" fill="url(#jbSpn)"/><rect x="14.4" y="5" width="1.3" height="36" fill="#5e3b12" opacity=".55"/><g stroke="#4f3110" stroke-width="1.5" opacity=".6"><path d="M9 12.5 H15.5"/><path d="M9 19.5 H15.5"/><path d="M9 26.5 H15.5"/><path d="M9 33.5 H15.5"/></g><g stroke="#fbe3a4" stroke-width=".5" opacity=".45"><path d="M9 11.7 H15.5"/><path d="M9 18.7 H15.5"/><path d="M9 25.7 H15.5"/><path d="M9 32.7 H15.5"/></g><rect x="18" y="9" width="14" height="28" rx="1.5" fill="none" stroke="#5e3b12" stroke-width=".9" opacity=".75"/><rect x="19.4" y="10.4" width="11.2" height="25.2" rx="1" fill="none" stroke="#fbe3a4" stroke-width=".5" opacity=".5"/><g transform="translate(25,23)"><circle r="2.7" fill="#fbe3a4" stroke="#5e3b12" stroke-width=".7"/><g stroke="#5e3b12" stroke-width="1" stroke-linecap="round"><path d="M0 -4.4 V-6 M0 4.4 V6 M-4.4 0 H-6 M4.4 0 H6 M-3.1 -3.1 L-4.3 -4.3 M3.1 -3.1 L4.3 -4.3 M-3.1 3.1 L-4.3 4.3 M3.1 3.1 L4.3 4.3"/></g></g><g fill="#fbe3a4" stroke="#5e3b12" stroke-width=".5"><circle cx="19.6" cy="9.6" r="1"/><circle cx="31.4" cy="9.6" r="1"/><circle cx="19.6" cy="36.4" r="1"/><circle cx="31.4" cy="36.4" r="1"/></g><path d="M34.5 19.5 H38.8 V26.5 H34.5" fill="#d8af63" stroke="#5e3b12" stroke-width=".6" stroke-linejoin="round"/><circle cx="37" cy="23" r=".95" fill="#5e3b12"/></svg><span class="jc-txt">Unlock today’s journal entry</span>${ic('seal')}</button>
  ${PICK?`<div class="rec-feature">${lessonCardHTML(PICK)}</div>
  <button class="btn ghost" id="allles" style="width:auto;padding:9px 16px;margin:14px auto 0;display:flex;align-items:center;gap:7px">${ic('lotus')} Explore all ${LESSONS.length} journeys &rarr;</button>`:''}
  <button class="quick-med" id="quickMed" type="button">
    <span class="qm-ic">${ic('medlotus')}</span>
    <span class="qm-body"><span class="qm-title">Quick meditate</span><span class="qm-sub" id="quickSummary">${sessionSummary()}</span></span>
    <span class="qm-go">${ic('play')}</span>
  </button>
  ${horoscopeCardHTML(horo)}
  ${challengeCardHTML(chal)}`;
  {const qm=$('#quickMed');if(qm)qm.onclick=openSessionSheet;}
  document.querySelectorAll('.horo-sign').forEach(b=>b.onclick=async()=>{b.disabled=true;try{await api('horoscope/sign','POST',{sign:b.dataset.sign});renderMeditate();}catch(e){b.disabled=false;toast(e);}});
  {const hs=document.querySelector('.horo-sit');if(hs)hs.onclick=()=>{pick.sound=hs.dataset.snd;pick.minutes=+hs.dataset.min||pick.minutes;startSession();};
   const hl=document.querySelector('.horo-listen:not(.pick-listen)');if(hl&&horo&&horo.text)hl.onclick=()=>playHoroscope(hl,horo.text);
   const pl=document.querySelector('.pick-listen');if(pl&&PICK)pl.onclick=()=>playHoroscope(pl,pickInvite(PICK));
   const hn=document.querySelector('.horo-addnatal');if(hn)hn.onclick=addNatal;}
  {const jc=$('#journalCta');if(jc)jc.onclick=()=>openJournalDaily(dp?dp.focus:undefined);}
  document.querySelectorAll('.lesson-card,.pickcard').forEach(c=>c.onclick=(e)=>{if(e.target.closest('.pick-listen'))return;lessonFrom='meditate';lessonDetail(c.dataset.l);});
  const al=$('#allles');if(al)al.onclick=()=>go('lessons');
  if(window.mountLumenOrb)mountLumenOrb({level:ME.level,into:ME.level_into,need:ME.level_need,palette:(window.LUM_LEAGUE_PAL&&window.LUM_LEAGUE_PAL[ME.league.name])||'Ember'});
  try{ctaSparks();}catch(e){}
}

/* ---- guided journeys library ---- */
// Journeys tab — a card per journey (track). Tap a card to open the journey and
// pick your next lesson. Each card shows how far you've walked it + what's next.
function _journeyNext(ls){
  return ls.find(l=>{const p=lessonProg(l.code);return !(p&&p.count>0);})
    || ls.find(l=>lessonResumeSi(l)>0) || null;
}
function _trackLast(key){let m=0;LESSONS.filter(l=>l.track===key).forEach(l=>{const p=lessonProg(l.code);
  if(p&&p.last){const t=Date.parse(p.last);if(t>m)m=t;}});return m;}
async function renderLessons(){
  try{const r=await api('me');ME=r.profile;}catch(e){}
  // order journeys by most-recently practiced (saved last_journey wins the tie / drives the pulse)
  const tracks=[...TRACKS].sort((a,b)=>_trackLast(b.key)-_trackLast(a.key));
  let recentKey=(ME&&ME.last_journey&&TRACKS.some(t=>t.key===ME.last_journey))?ME.last_journey:null;
  if(!recentKey&&_trackLast(tracks[0].key)>0)recentKey=tracks[0].key;
  const card=(t)=>{
    const isRecent=t.key===recentKey;
    const ls=LESSONS.filter(l=>l.track===t.key);
    const soon=(ROADMAP[t.key]||[]).length;
    const total=ls.length;
    const done=ls.filter(l=>{const p=lessonProg(l.code);return p&&p.count>0;}).length;
    const pct=total?Math.round(100*done/total):0;
    const mins=ls.reduce((s,l)=>s+lessonMins(l),0);
    const next=_journeyNext(ls);
    const allDone=total&&done>=total;
    const nextLbl=allDone?'Journey complete · revisit'
      :(next?('Next · '+next.title+' · '+next.subtitle):(soon?'Coming soon':'Start'));
    return `<button class="jrny-card${isRecent?' recent':''}" data-k="${t.key}" style="--a:${t.accent}">
      ${isRecent?`<span class="jrny-tag">${ic('play')} Continue</span>`:''}
      <div class="jrny-art">${ls[0]?deityEmblem(ls[0]):ic('lotus','g')}</div>
      <div class="jrny-body">
        <div class="jrny-name">${esc(t.name)}</div>
        <div class="jrny-sub">${esc(t.sub)}</div>
        <div class="jrny-bar"><i style="width:${pct}%"></i></div>
        <div class="jrny-meta">${done} of ${total} lessons${soon?' · '+soon+' coming':''} · ~${mins} min</div>
        <div class="jrny-next">${ic(allDone?'check':'play')} ${esc(nextLbl)}</div>
      </div>
      <span class="jrny-go">${ic('play')}</span>
    </button>`;
  };
  $('#app').innerHTML=`
  <div class="brand"><span class="mark">${lumenMark('mark')}</span><b>Journeys</b></div>
  <p class="muted" style="font-size:13px;margin:4px 2px 16px">Each journey is a guided course that builds over time. Open one to pick up your next lesson.</p>
  <div class="jrny-grid">${tracks.map(card).join('')}</div>
  <p class="muted center" style="font-size:12px;margin:20px 0 4px">More journeys are added over time. Have one you'd love? Ask the Keeper.</p>`;
  document.querySelectorAll('.jrny-card').forEach(c=>c.onclick=()=>renderJourney(c.dataset.k));
}

// A single journey — its lessons in order, your next lesson highlighted, tap to open.
function renderJourney(key){
  const t=TRACKS.find(x=>x.key===key);if(!t)return;
  if(window.speechSynthesis)speechSynthesis.cancel();try{Sound.stop();}catch(e){}
  curJourney=key;
  const ls=LESSONS.filter(l=>l.track===key);
  const total=ls.length;
  const done=ls.filter(l=>{const p=lessonProg(l.code);return p&&p.count>0;}).length;
  const pct=total?Math.round(100*done/total):0;
  const next=_journeyNext(ls);
  const row=(l,i)=>{
    const p=lessonProg(l.code);const isDone=p&&p.count>0;const rs=lessonResumeSi(l);
    const isNext=next&&l.code===next.code;
    const meta=lessonMins(l)+' min · '+l.segments.length+' steps'
      +(isDone?(' · done '+p.count+'×'):(rs>0?' · resume · step '+(rs+1):''));
    return `<button class="lj-row${isDone?' done':''}${isNext?' next':''}" data-l="${l.code}" style="--a:${l.accent}">
      <span class="lj-ico">${lessonEmblem(l,'ljm')}${isDone?`<span class="lj-seal">${ic('check')}</span>`:''}</span>
      <span class="lj-main"><span class="lj-title">${esc(l.title)} · ${esc(l.subtitle)}</span>
      <span class="lj-sub">${esc(meta)}</span></span>
      ${isNext?`<span class="lj-badge">Next up</span>`:`<span class="lj-go">${ic('play')}</span>`}
    </button>`;
  };
  const soonRows=(ROADMAP[key]||[]).map(r=>`<div class="lj-row soon"><span class="lj-ico lock">${ic('lock')}</span>`
    +`<span class="lj-main"><span class="lj-title">${esc(r.title)}</span><span class="lj-sub">${esc(r.sub)}</span></span></div>`).join('');
  $('#app').innerHTML=`
  <div class="brand"><button class="back-btn" id="jrback" title="All journeys">‹</button><span class="mark">${lumenMark('mark')}</span><b>${esc(t.name)}</b></div>
  <div class="jrh" style="--a:${t.accent}">
    <div class="jrh-med">${ls[0]?deityEmblem(ls[0]):''}</div>
    <div class="jrh-eyebrow">${ic('lotus')} Journey</div>
    <div class="jrh-name">${esc(t.name)}</div>
    <div class="jrh-sub">${esc(t.sub)}</div>
    <div class="jrh-bar"><i style="width:${pct}%"></i></div>
    <div class="jrh-count">${done} of ${total} lessons complete</div>
  </div>
  ${next?`<button class="btn jrnext-btn" id="jrnext" style="margin:2px 0 16px">${ic('seal')} ${done>0?'Continue':'Start'} · ${esc(next.title)} · ${esc(next.subtitle)}</button>`:`<div class="muted center" style="margin:6px 0 14px">${ic('check','g')} You've completed this journey — revisit any lesson below.</div>`}
  <div class="lj-list">${ls.map(row).join('')}</div>
  ${soonRows?`<div class="trk-head" style="--a:${t.accent};margin-top:18px"><div class="trk-name">Coming soon</div></div>${soonRows}`:''}`;
  $('#jrback').onclick=()=>go('lessons');
  const nb=$('#jrnext');if(nb&&next)nb.onclick=()=>{lessonFrom='journey';lessonDetail(next.code);};
  document.querySelectorAll('.lj-row:not(.soon)').forEach(c=>c.onclick=()=>{lessonFrom='journey';lessonDetail(c.dataset.l);});
}

let timerInt=null;
async function startSession(){
  try{await api('session/start','POST',{});}catch(e){}
  getGeo();  // capture location now (user gesture) so it's ready by the time the sit ends
  Sound.bell();Sound.start(pick.sound);
  const total=pick.minutes*60;let left=total;let ended=false;
  $('#nav').classList.add('hidden');
  $('#app').innerHTML=`
  <div class="sit-screen">
    <div class="orb-wrap">
      <div class="ring"></div>
      <div class="orb"><div class="t" id="clock">${mm(left)}</div></div>
      <div class="breath-label" id="bl">breathe in</div>
    </div>
    <div class="center muted" style="margin-top:-4px">${SOUNDS.find(s=>s[0]===pick.sound)[2]} · ${pick.minutes} min</div>
    <div class="end-wrap"><button class="btn ghost" id="end">End session</button></div>
  </div>`;
  const bl=$('#bl');let phase=0;
  const breath=setInterval(()=>{phase=(phase+1)%2;bl.textContent=phase?'breathe out':'breathe in';},5000);
  timerInt=setInterval(()=>{left--;$('#clock')&&($('#clock').textContent=mm(left));if(left<=0){finish(true);}},1000);
  function stopTimers(){clearInterval(timerInt);clearInterval(breath);}
  async function finish(complete){
    if(ended)return;ended=true;stopTimers();Sound.stop();if(complete)Sound.bell();
    const done=complete?pick.minutes:Math.max(1,Math.round((total-left)/60));
    completeFlow(done);
  }
  $('#end').onclick=()=>finish(false);
  window._finishEarly=finish;
}
const mm=(s)=>`${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;

function completeFlow(minutes){
  $('#app').innerHTML=`
  <div class="brand"><span class="mark">${lumenMark('mark')}</span><b>Session complete</b></div>
  <div class="card center"><div style="color:var(--gold)">${ic('lotus','lg grad-gold')}</div>
    <h2 style="margin:8px 0 2px">${minutes} minutes</h2>
    <p class="muted" style="margin:0">How do you feel?</p>
    <div class="grid3" id="mood" style="margin-top:12px">
      ${[['calm','calm','calm'],['energized','bolt','energized'],['unclear','fog','unclear']].map(m=>`<div class="chip" data-m="${m[0]}"><div class="big">${ic(m[1])}</div>${m[2]}</div>`).join('')}
    </div>
    <label style="text-align:left">A note for your journal (optional)</label>
    <textarea id="note" rows="3" placeholder="What came up?"></textarea>
    <div class="spot-cap">
      <div id="spothold" class="spot-hold" style="display:none"></div>
      <input type="file" id="spotfile" accept="image/*" capture="environment" style="display:none">
      <button class="spot-add" id="spotadd" type="button">${ic('camera')} Add a photo of your spot</button>
      <div id="spotprev" class="spot-prev"></div>
    </div>
    <label style="display:flex;align-items:center;gap:9px;text-align:left"><input type="checkbox" id="share"> Share your spot & note to the community</label>
    <div id="locnote" class="muted" style="font-size:12px;margin-top:8px"></div>
    <button class="btn gold" id="save" style="margin-top:14px">Collect your Light ${ic('spark')}</button>
  </div>`;
  let mood='';
  let spotPhoto=null;
  // "holder" map: a keyless Esri dark-gray basemap thumbnail of where they sat —
  // same map style as the Map tab, with a glowing marker (below). Local preview only, never uploaded.
  let holderKey='';
  const holderUrl=(lat,lon)=>{
    const aspect=640/360, latH=0.02, lonH=latH*aspect/Math.max(.2,Math.cos(lat*Math.PI/180));
    const bbox=[lon-lonH,lat-latH,lon+lonH,lat+latH].map(n=>n.toFixed(5)).join(',');
    return 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/export'
      +'?bbox='+bbox+'&bboxSR=4326&imageSR=3857&size=640,360&format=png&transparent=false&f=image';
  };
  const renderHolder=()=>{
    const h=$('#spothold');if(!h)return;
    if(!coords){h.style.display='none';return;}   // keep it alongside any photo they add
    const key=coords.lat.toFixed(3)+','+coords.lon.toFixed(3);
    h.style.display='';
    if(key===holderKey&&h.querySelector('img'))return;   // already showing this spot
    holderKey=key;
    h.classList.add('load');
    h.innerHTML=`<img alt="your meditation spot"><span class="spot-glow"><span class="mkr me" style="--c:#f5c977">${ic(pick&&pick.sound?pick.sound:'silence','mkri')}</span></span><span class="cap">${ic('pin')} Where you meditated</span>`;
    const img=h.querySelector('img');
    img.onload=()=>{img.classList.add('on');h.classList.remove('load');};
    img.onerror=()=>{h.classList.remove('load');h.style.display='none';holderKey='';};
    img.src=holderUrl(coords.lat,coords.lon);
  };
  $('#spotadd').onclick=()=>$('#spotfile').click();
  $('#spotfile').onchange=async(e)=>{
    const f=e.target.files&&e.target.files[0];if(!f)return;
    const add=$('#spotadd');if(add)add.textContent='Processing photo…';
    try{spotPhoto=await downscaleImage(f,1280,0.82);
      $('#spotprev').innerHTML=`<div class="spot-lbl">${ic('camera','g')} Your photo</div><img src="${spotPhoto}" alt="your spot"><button type="button" class="spot-x" id="spotx">${ic('close')||'✕'} Remove</button>`;
      if(add){add.style.display='none';}
      renderHolder();   // keep the location holder visible above your photo
      const x=$('#spotx');if(x)x.onclick=()=>{spotPhoto=null;$('#spotprev').innerHTML='';if(add){add.style.display='';add.innerHTML=ic('camera')+' Add a photo of your spot';}$('#spotfile').value='';renderHolder();};
    }catch(err){toast(err);if(add){add.innerHTML=ic('camera')+' Add a photo of your spot';}}
  };
  $('#mood').querySelectorAll('.chip').forEach(c=>c.onclick=()=>{mood=c.dataset.m;$('#mood').querySelectorAll('.chip').forEach(x=>x.classList.toggle('sel',x===c));});
  // prefer the fix captured when the sit began; refresh in the background
  let coords=(geoFix&&Date.now()-geoFix.t<3600000)?{lat:geoFix.lat,lon:geoFix.lon}:null;
  const setNote=()=>{const n=$('#locnote');if(!n)return;
    n.innerHTML=coords?ic('pin')+' Your light will appear where you sat.'
      :(ME.lat?ic('pin')+' Using your saved location — enable location for a precise pin.'
             :'Location is off — enable it for this site to light up the map.');};
  setNote();renderHolder();
  getGeo().then(g=>{if(g){coords={lat:g.lat,lon:g.lon};}setNote();renderHolder();});
  $('#save').onclick=async()=>{
    const btn=$('#save');if(btn){btn.disabled=true;btn.textContent='Collecting…';}
    try{
      if(!coords){const g=await getGeo({enableHighAccuracy:true,timeout:7000,maximumAge:120000});if(g)coords={lat:g.lat,lon:g.lon};}
      const share=$('#share').checked;
      const body={minutes,soundscape:pick.sound,mood,note:$('#note').value,share,tz_offset_min:-new Date().getTimezoneOffset()};
      if(spotPhoto){body.photo=spotPhoto;body.photo_share=share;}
      if(coords){body.lat=coords.lat;body.lon=coords.lon;}
      const res=await api('session/complete','POST',body);
      // best-effort profile refresh — must NOT block showing the reward if it blips
      try{const r=await api('me');if(r&&r.profile)ME=r.profile;}catch(_e){}
      showRewards(res,minutes);
    }catch(e){
      if(btn){btn.disabled=false;btn.innerHTML='Collect your Light '+ic('spark');}
      toast(typeof e==='string'?e:'Could not collect your Light — check your connection and try again.');
    }
  };
}

// A shareable 1080×1350 card of the session just finished — drawn on a canvas,
// then handed to the native share sheet (Web Share API) with the App Store link.
function buildShareCard(d){
  const W=1080,H=1350,c=document.createElement('canvas');c.width=W;c.height=H;const g=c.getContext('2d');
  const bg=g.createRadialGradient(W/2,H*0.34,60,W/2,H*0.34,H*0.9);
  bg.addColorStop(0,'#1c1636');bg.addColorStop(.55,'#120f24');bg.addColorStop(1,'#09080f');
  g.fillStyle=bg;g.fillRect(0,0,W,H);
  for(let i=0;i<48;i++){g.globalAlpha=0.05+Math.random()*0.28;g.fillStyle='#f5c977';g.beginPath();g.arc(Math.random()*W,Math.random()*H,Math.random()*1.9,0,7);g.fill();}
  g.globalAlpha=1;g.textAlign='center';
  g.fillStyle='#f5c977';g.font='700 58px Georgia,"Times New Roman",serif';g.fillText('lumen',W/2,152);
  const ox=W/2,oy=438;
  let halo=g.createRadialGradient(ox,oy,0,ox,oy,255);halo.addColorStop(0,'rgba(246,201,119,.55)');halo.addColorStop(.5,'rgba(240,168,74,.16)');halo.addColorStop(1,'rgba(240,168,74,0)');
  g.fillStyle=halo;g.beginPath();g.arc(ox,oy,255,0,7);g.fill();
  g.save();g.translate(ox,oy);g.rotate(-0.34);g.strokeStyle='rgba(255,231,176,.5)';g.lineWidth=5;g.beginPath();g.ellipse(0,0,192,54,0,0,7);g.stroke();g.restore();
  let core=g.createRadialGradient(ox-30,oy-40,8,ox,oy,116);core.addColorStop(0,'#fffdf6');core.addColorStop(.45,'#f7c972');core.addColorStop(.84,'#e49b38');core.addColorStop(1,'#9a5e1c');
  g.fillStyle=core;g.beginPath();g.arc(ox,oy,112,0,7);g.fill();
  g.save();g.translate(ox,oy);g.rotate(-0.34);g.strokeStyle='rgba(255,231,176,.92)';g.lineWidth=5;g.beginPath();g.ellipse(0,0,192,54,0,3.14,6.28);g.stroke();g.restore();
  g.fillStyle='#f6f1ea';g.font='700 170px Georgia,serif';g.fillText(String(d.minutes||0),W/2,780);
  g.fillStyle='#b9b0d0';g.font='400 46px -apple-system,"Segoe UI",sans-serif';g.fillText((d.minutes===1?'minute':'minutes')+' of stillness',W/2,848);
  if(d.sound){g.fillStyle='#8f8a9d';g.font='400 38px -apple-system,sans-serif';g.fillText(d.sound.charAt(0).toUpperCase()+d.sound.slice(1)+' soundscape',W/2,910);}
  g.fillStyle='#f5c977';g.font='700 72px -apple-system,sans-serif';g.fillText('+'+fmt(d.light||0)+' Light',W/2,1022);
  if(d.streak&&d.streak>1){g.fillStyle='#fb923c';g.font='600 44px -apple-system,sans-serif';g.fillText(d.streak+'-day streak',W/2,1092);}
  g.fillStyle='#7f7a92';g.font='400 34px -apple-system,sans-serif';g.fillText('light, one breath at a time',W/2,1272);
  return c;
}
async function shareMeditation(d){
  const url='https://apps.apple.com/app/id6822133425';
  const text=`I sat for ${d.minutes} ${d.minutes===1?'minute':'minutes'} with Lumen${d.streak>1?` — ${d.streak}-day streak`:''}. Light, one breath at a time.`;
  let file=null;
  try{const cv=buildShareCard(d);const blob=await new Promise(r=>cv.toBlob(r,'image/png',0.92));if(blob)file=new File([blob],'lumen-meditation.png',{type:'image/png'});}catch(e){}
  try{
    if(file&&navigator.canShare&&navigator.canShare({files:[file]})){await navigator.share({files:[file],text:text+'\n'+url});return;}
    if(navigator.share){await navigator.share({title:'Lumen',text,url});return;}
  }catch(e){if(e&&e.name==='AbortError')return;}
  try{await navigator.clipboard.writeText(text+' '+url);toast(ic('check','g')+' Link copied — share it anywhere');return;}catch(e){}
  toast('Sharing isn’t available on this device.');
}
function showRewards(res,minutes){
  $('#nav').classList.remove('hidden');bindNav();
  const ach=(res.new_achievements||[]).map(a=>`<div class="pill" style="border-color:var(--gold);color:var(--gold)">${ic(ACH_ICON[a.code]||'star')} ${a.title}</div>`).join(' ');
  $('#app').innerHTML=`
  <div class="brand"><span class="mark">${lumenMark('mark')}</span><b>Lumen</b></div>
  <div class="card center">
    <div style="color:var(--gold);filter:drop-shadow(0 0 20px var(--gold))">${ic('spark','lg grad-aur')}</div>
    <div style="font-size:34px;font-weight:800;color:var(--gold)">+${res.light_earned} Light</div>
    <div class="muted" style="font-size:13px;margin-top:2px">${ic('spark','g')} +${res.motes_earned||res.light_earned} Motes collected</div>
    ${res.time_bonus?`<div class="pill" style="margin-top:6px">${res.time_bonus==='night'?ic('moon','p glow')+' night owl +20%':ic('sunrise','g glow')+' dawn +20%'}</div>`:''}
    ${res.multiplier>1?`<div class="pill" style="margin-top:6px">${ic('flame','flame grad-flame glow')} ${res.streak}-day streak ×${res.multiplier}</div>`:`<div class="muted" style="margin-top:8px">${ic('flame','flame grad-flame glow')} ${res.streak}-day streak</div>`}
    ${res.challenge&&res.challenge.newly_done?`<div class="chal-done-banner" style="margin-top:14px">${res.challenge.new_place?ic('pin','g')+' New place added to your passport':ic('camera','g')+' Spot kept'} · +${res.challenge.bonus} Light${res.challenge.streak>1?` · ${res.challenge.streak}-day photo streak`:''}${res.challenge.places?` · ${res.challenge.places} place${res.challenge.places===1?'':'s'} collected`:''}</div>`:''}
    ${res.photo?`<div class="spot-shot">${ic('pin','g')} <span class="muted" style="font-size:12px">Your spot</span><img src="${esc(res.photo)}" alt="your spot"></div>`:''}
    ${res.leveled_up?`<h2 style="margin:14px 0 0;color:var(--pink)">Level ${res.level} reached!</h2>`:''}
    ${ach?`<div style="margin-top:14px"><div class="muted" style="font-size:12px">Achievement unlocked</div><div style="margin-top:8px;display:flex;gap:8px;justify-content:center;flex-wrap:wrap">${ach}</div></div>`:''}
    ${lessonReflect?`<div class="reflect-note" style="margin-top:16px"><div class="muted" style="font-size:12px;margin-bottom:7px">Carry the lesson forward</div><button class="btn ghost" id="reflect" style="text-align:left;line-height:1.4">${ic('book')} “${esc(lessonReflect)}”</button></div>`:''}
    <button class="btn gold" id="shareSit" style="margin-top:18px">${ic('share')} Share your sit</button>
    <button class="btn ghost" id="done" style="margin-top:9px">Done</button>
    <button class="btn ghost" id="seemap" style="margin-top:9px">See your light on the map ${ic('globe')}</button>
  </div>`;
  const rf=lessonReflect;lessonReflect=null;
  const rb=$('#reflect');if(rb)rb.onclick=()=>{openJournalDaily(rf);};
  const sb=$('#shareSit');if(sb)sb.onclick=()=>shareMeditation({minutes:minutes||0,light:res.light_earned||0,streak:res.streak||0,sound:(pick&&pick.sound)||''});
  $('#done').onclick=()=>go('meditate');
  $('#seemap').onclick=()=>go('map');
}

/* ---- guided lessons ---- */
function lessonProg(code){return (ME&&ME.lessons&&ME.lessons[code])||null;}
// Recommendation order: resume-in-progress first, then fresh (never done), then completed.
function recommendedLessons(){
  const seen=new Set(), out=[];
  const push=l=>{if(l&&!seen.has(l.code)){seen.add(l.code);out.push(l);}};
  LESSONS.filter(l=>lessonResumeSi(l)>0).forEach(push);   // continue where you left off
  LESSONS.filter(l=>!lessonProg(l.code)).forEach(push);   // new to you
  LESSONS.forEach(push);                                  // everything else (completed)
  return out;
}
function todBucket(){const h=new Date().getHours();return h<5?'night':h<11?'morning':h<17?'midday':h<21?'evening':'night';}
function todGreeting(){return {morning:'A calm start to your morning',midday:'A midday reset',
  evening:'An evening wind-down',night:'Something gentle for the night'}[todBucket()];}
// Today's pick: scored by time-of-day fit, then rotated daily so it's stable for the day but changes.
function todaysPick(){
  const b=todBucket();
  const KW={morning:['intention','focus','clarity','energy','breath','wake','begin','start','steadiness','pranayama','awaken','light'],
    midday:['focus','reset','balance','calm','clarity','breath','steady','center'],
    evening:['gratitude','reflection','release','preserve','wind','calm','rest','ease','compassion','heart'],
    night:['sleep','rest','stillness','let go','release','calm','ocean','rain','night','surrender','dissolve']}[b];
  const SND={morning:['forest','silence'],midday:['forest','silence','space'],
    evening:['ocean','rain'],night:['ocean','rain','space']}[b];
  const text=l=>[l.title,l.subtitle,l.focus,l.technique,l.blurb,l.series].filter(Boolean).join(' ').toLowerCase();
  let intents=[];try{intents=JSON.parse(localStorage.getItem('lumen_intent')||'[]');}catch(e){}
  const IKW={calm:['calm','ease','settle','breath','still'],sleep:['sleep','rest','night','ocean','rain','surrender'],
    focus:['focus','clarity','concentration','steady','center'],habit:['steadiness','return','daily','practice','discipline'],
    spirit:['devotion','sacred','divine','soul','spirit','deity'],self:['shadow','reflection','self','inner','archetype','understand']};
  const IK=[].concat(...intents.map(i=>IKW[i]||[]));
  const score=l=>{let s=0;const t=text(l);KW.forEach(k=>{if(t.indexOf(k)!==-1)s+=2;});
    IK.forEach(k=>{if(t.indexOf(k)!==-1)s+=1;});
    if(SND.indexOf(l.soundscape)!==-1)s+=2; if(lessonResumeSi(l)>0)s+=3; return s;};
  // Only consider the NEXT lesson in each journey — _journeyNext walks the track
  // in order and returns the first lesson you haven't finished (or the one you're
  // mid-way through). So the pick is always the right next step: never Shiva 5
  // before Shiva 4, and never a lesson you've already completed.
  let candidates=[];
  TRACKS.forEach(t=>{const ls=LESSONS.filter(l=>l.track===t.key);const nx=_journeyNext(ls);if(nx)candidates.push(nx);});
  if(!candidates.length) candidates=LESSONS.slice();   // every journey complete — allow a revisit
  const ranked=candidates.map(l=>({l,s:score(l)})).sort((a,b)=>b.s-a.s||a.l.code.localeCompare(b.l.code));
  const best=ranked[0].s, top=ranked.filter(x=>x.s===best).map(x=>x.l);
  const day=Math.floor((Date.now()-new Date().getTimezoneOffset()*60000)/86400000);
  return top[day%top.length];
}
// A short, warm spoken invitation for the day's pick (played via ElevenLabs TTS).
function pickInvite(l){
  const snd={rain:'rain',forest:'the forest',ocean:'the ocean',space:'cosmic space',silence:'silence'}[l.soundscape]||l.soundscape;
  const sndPhrase=l.soundscape==='silence'?'in silence':('with '+snd);
  const mins=lessonMins(l);
  let s=todGreeting()+'. Today’s pick is '+l.title+(l.subtitle?', '+l.subtitle:'')+'.';
  if(l.blurb)s+=' '+String(l.blurb).replace(/\s+/g,' ').trim();
  s+=' Take about '+mins+' minutes '+sndPhrase+', and let yourself simply arrive.';
  return s;
}
/* resume: where the user paused inside a journey (segment index), kept on-device */
function jnyKey(code){return 'lumen_jny_'+code;}
function jnyProg(code){try{const v=localStorage.getItem(jnyKey(code));return v==null?null:parseInt(v,10);}catch(e){return null;}}
function jnySave(code,si){try{localStorage.setItem(jnyKey(code),String(si));}catch(e){}}
function jnyClear(code){try{localStorage.removeItem(jnyKey(code));}catch(e){}}
function lessonResumeSi(l){const rs=jnyProg(l.code);return (rs!=null&&rs>0&&rs<l.segments.length)?rs:0;}
const SERIES_ART={Vishnu:'art/lesson_vishnu.png?v=2',Shiva:'art/lesson_shiva.png?v=2',Lakshmi:'art/lesson_lakshmi.png?v=2',Breath:'art/lesson_breath.png?v=2'};
function deityEmblem(l,cls){const art=SERIES_ART[l.series]||l.img;
  return `<div class="deity-emblem ${cls||''}"><span class="deity-glyph">${ic('lotus','grad-gold')}</span>${art?`<img src="${art}" alt="" onerror="this.remove()">`:''}</div>`;}
// A distinct emblem per lesson — each lesson gets its own themed glyph so every
// step in a journey reads differently (instead of the same deity art repeated).
const LESSON_ICON={
  vishnu:'glow', vishnu_avatars:'star', vishnu_breath:'ocean', vishnu_emblems:'seal', vishnu_reflect:'spark',
  shiva:'p_mtn', shiva_dance:'nova', shiva_breath:'calm', shiva_name:'target', shiva_reflect:'moon',
  lakshmi:'lotus', lakshmi_forms:'coin', lakshmi_breath:'enso', lakshmi_flow:'flare', lakshmi_reflect:'bell',
  breath:'meditate', breath_sigh:'bolt', breath_vagus:'ocean', breath_box:'target', breath_carry:'flag',
};
function lessonIcon(l){return LESSON_ICON[l.code]||'lotus';}
function lessonEmblem(l,cls){
  return `<div class="lj-emb ${cls||''}" style="--a:${l.accent}">${ic(lessonIcon(l))}</div>`;}
let lessonFrom='lessons';
let curJourney=null;       // which journey (track key) the open lesson belongs to
let lessonSoundPick=null;  // background soundscape chosen in the journey detail modal
// The "Today's pick" feature card — a clean, spacious featured card:
// a small gold tag, a rounded art thumbnail, title + one meta line + a short
// blurb, and a single full-width CTA bar. (A thin progress bar shows only when
// a session is mid-way through resuming.)
function lessonCardHTML(l){
  const pr=lessonProg(l.code);
  const done=pr&&pr.count>0;
  const nSeg=l.segments.length;
  const rs=lessonResumeSi(l);
  const cta=rs>0?('Resume · step '+(rs+1)):(done?'Practice again':'Begin · '+lessonMins(l)+' min');
  return `<div class="pickcard" data-l="${l.code}" style="--a:${l.accent}">
    <div class="pick-head">
      <span class="pick-tag">${ic('spark','g')} Today's pick</span>
      <button class="pick-listen" type="button" title="Hear today's pick aloud">${ic('sound')}</button>
    </div>
    <div class="pick-top">
      <div class="pick-art">${deityEmblem(l)}</div>
      <div class="pick-main">
        <div class="pick-title">${esc(l.title)}</div>
        <div class="pick-meta">${esc(l.tradition)} · ${lessonMins(l)} min · ${nSeg} steps</div>
        <div class="pick-blurb">${esc(l.blurb)}</div>
      </div>
    </div>
    ${rs>0?`<div class="pick-progress"><i style="width:${Math.round(100*rs/nSeg)}%"></i></div>`:''}
    <div class="pick-cta">${ic(done&&rs<=0?'check':'play','g')} ${esc(cta)}</div>
  </div>`;
}
// Detail / preview screen shown before a journey begins
// A lesson preview — opens as a modal over the journey list (or wherever it was tapped).
function lessonDetail(code){
  const l=LESSONS.find(x=>x.code===code); if(!l)return;
  if(window.speechSynthesis)speechSynthesis.cancel();try{Sound.stop();}catch(e){}
  const nSeg=l.segments.length, rs=lessonResumeSi(l), pr=lessonProg(l.code), done=pr&&pr.count>0;
  lessonSoundPick=l.soundscape;
  const ov=el(`<div class="lmodal-ov"><div class="lmodal">
    <div class="card jdetail" style="--a:${l.accent}">
      <button class="lmodal-x" aria-label="Close">${ic('close')}</button>
      <div class="jd-eyebrow">${ic('lotus')} ${esc((TRACKS.find(x=>x.key===l.track)||{}).name||'Journey')}${l.part?' · Part '+l.part:''}</div>
      <div class="jd-art">${deityEmblem(l,'lg')}</div>
      <h1 class="jd-title" style="color:${l.accent}">${esc(l.title)}</h1>
      <div class="jd-subtitle">${esc(l.subtitle)}</div>
      <div class="jd-chips">
        <span>${ic('lotus','g')} ${esc(l.tradition)}</span>
        <span>${ic('clock','g')} ${lessonMins(l)} min</span>
        <span>${ic('target','g')} ${nSeg} steps</span>
        ${l.technique?`<span>${ic('spark','g')} ${esc(l.technique)}</span>`:''}
      </div>
      <p class="jd-desc">${esc(l.blurb)}</p>
      <div class="jd-head">What you'll move through</div>
      <ol class="jd-steps">${l.segments.map(s=>`<li>${esc(s.title)}</li>`).join('')}</ol>
      ${l.prompt?`<div class="jd-prompt">${ic('book','g')}<span>Afterward, you'll reflect: &ldquo;${esc(l.prompt)}&rdquo;</span></div>`:''}
      ${done?`<div class="lesson-done" style="justify-content:center;margin-top:12px">${ic('check')} Completed ${pr.count}×${pr.last?' · last '+ago(pr.last):''}</div>`:''}
      <button class="btn gold" id="dbegin" style="margin-top:14px">${ic('seal')} ${rs>0?('Continue · step '+(rs+1)+' of '+nSeg):(done?'Practice again':'Begin journey')}</button>
      <div class="jd-sound">
        <div class="jd-sound-lbl">Background sound</div>
        <div class="grid3" id="lsnds">${SOUNDS.map(s=>`<div class="chip snd-chip ${s[0]===l.soundscape?'sel':''}" data-s="${s[0]}"><div class="big">${ic(s[1])}</div>${s[2]}</div>`).join('')}</div>
      </div>
      <p class="muted center" style="font-size:12px;margin-top:12px">Earns Light · builds your streak</p>
    </div></div></div>`);
  const close=()=>{ov.classList.remove('show');setTimeout(()=>ov.remove(),240);};
  ov.addEventListener('click',e=>{if(e.target===ov||e.target.closest('.lmodal-x'))close();});
  ov.querySelector('#dbegin').onclick=()=>{ov.remove();lessonPlay(l, rs);};
  ov.querySelectorAll('#lsnds .snd-chip').forEach(c=>c.onclick=()=>{lessonSoundPick=c.dataset.s;
    ov.querySelectorAll('#lsnds .snd-chip').forEach(x=>x.classList.toggle('sel',x.dataset.s===lessonSoundPick));});
  document.body.appendChild(ov);requestAnimationFrame(()=>ov.classList.add('show'));
}
const LESSONS=[{
  code:'vishnu', title:'Vishnu · I', subtitle:'The Preserver',
  track:'devotion', level:'Core', focus:'Sustenance · steadiness', part:1, series:'Vishnu',
  technique:'Settling · sattva',
  tradition:'Hindu · the Preserver', img:'', soundscape:'ocean', accent:'#5fa8ff',
  prompt:'What in your life are you being asked to preserve — and what small practice, returned to daily, would truly sustain it?',
  blurb:'Part 1 of the Vishnu course. Meet the Preserver — the quiet force of sustenance between creation and dissolution — and learn what preservation really means: not a single act, but the practice of returning.',
  segments:[
    {title:'The Preserver', cue:'Breathe naturally. Let the body settle.', secs:130,
     teach:"Come and take the seat of Vishnu, the Preserver — the one who holds the whole world in balance, not by force but by steady presence. In the great trinity he stands between Brahma, who creates, and Shiva, who dissolves; his is the quiet, unglamorous middle — keeping, tending, sustaining. His quality is sattva: clarity, harmony, an even keel. So let the body grow still, and begin to notice the breath that has kept you alive all this time — quietly, faithfully, asking nothing of you. That breath is already his work in you."},
    {title:'What preservation means', cue:'Let the breath stay slow and even.', secs:200,
     teach:"We prize creation and we fear destruction, but we rarely honor the third thing — preservation, the daily sustaining that quietly holds a life together. Vishnu's name comes from a root meaning to pervade: he is said to dwell within all things, the thread of continuity running through every change. He keeps rta and dharma — the deep order, the way that holds a world together. And consider: almost nothing good is won in a single act. A marriage, a craft, a healing, a faith — none is created once, but tended, returned to, sustained. Sustenance is a practice, and practice is only returning. Let that settle as the breath moves."},
    {title:'Rest in what sustains you', cue:'Let the breath breathe itself.', secs:120,
     teach:"For these last breaths, simply rest in the quiet fact of being sustained — the heartbeat you never started, the breath that keeps arriving unasked. You do not have to hold your life together by force in this moment; something steadier already does. Let that be enough for now. And when you return, we will meet the forms Vishnu takes when the balance is lost."},
  ]
},{
  code:'vishnu_avatars', title:'Vishnu · II', subtitle:'The Ten Avatars',
  track:'devotion', level:'Core', focus:'Renewal · showing up', part:2, series:'Vishnu',
  technique:'Contemplation',
  tradition:'Hindu · the Preserver', img:'', soundscape:'ocean', accent:'#5fa8ff',
  prompt:'Where are you being asked to show up again, patiently, to restore balance?',
  blurb:'Part 2 of the Vishnu course. Walk through the dashavatara — his ten descents — and their meaning: the divine returns, age after age, to restore balance. Then bring that pattern home to your own life.',
  segments:[
    {title:'The ten descents', cue:'Rest easy. Simply listen.', secs:220,
     teach:"When balance is truly lost, Vishnu does not watch from afar — he descends, taking form. These are the avatars, the dashavatara, his ten descents. Matsya the fish carries the seeds of life safely through the flood. Kurma the turtle bears a mountain on his back while the ocean is churned. Varaha the boar lifts the drowned earth from the deep. Narasimha, man and lion, protects the faithful when nothing else can. Vamana the small one reclaims the worlds in three vast steps. Then Rama, who embodies dharma, and Krishna, who speaks the Gita; and Kalki, still to come. Ten forms for ten needs — the divine meeting the moment in whatever shape it asks for."},
    {title:'Age after age', cue:'Let the breath carry the thought, then release it.', secs:160,
     teach:"The Bhagavad Gita says it plainly, in Krishna's own voice: whenever righteousness fades and disorder rises, I come into being, age after age. Hear what that tells us about sustenance — it is not standing still, fixed and unchanging. It is returning, in whatever form the moment needs. What lasts, lasts because it is renewed, again and again. Let that settle on the breath: to preserve is not to grip, but to keep coming back."},
    {title:'Your own descent', cue:'Let one honest picture arise.', secs:170,
     teach:"Now bring it home. Where in your life is balance quietly slipping — and where are you being asked, not for one heroic act, but simply to show up again, in ordinary form, to tend what matters? You do not need to be a hero. You need only to descend, patiently, back into your own life. Picture yourself returning there — to the practice, the person, the work — once more. That willingness to return is your avatar."},
  ]
},{
  code:'vishnu_breath', title:'Vishnu · III', subtitle:'The Ocean Breath',
  track:'devotion', level:'Core', focus:'Pranayama · steadiness', part:3, series:'Vishnu',
  technique:'Dirga · Ujjayi · Sama Vritti',
  tradition:'Hindu · the Preserver', img:'', soundscape:'ocean', accent:'#5fa8ff',
  prompt:'Which of the three breaths steadied you most — and when this week could you use it on purpose?',
  blurb:'Part 3 of the Vishnu course — the techniques. Learn and practice the three pranayamas of the Preserver: the full three-part breath, the ocean breath, and the square breath.',
  segments:[
    {title:'The three-part breath · Dirga', cue:'Inhale — belly, then ribs, then chest. Exhale slowly.', secs:200,
     teach:"The first of Vishnu's breaths. He reclines on Ananta, the serpent of infinity, upon the shoreless ocean of milk — and you can let your own breath become that ocean. This is Dirga, the complete three-part breath. Breathing in, fill first the belly, then let the ribs widen, then the chest rise — a slow tide coming in. Breathing out, release in the same order, unhurried, until you are gently empty. Nothing forced here; only a tide allowed to rise and fall. This is what sustaining feels like in the body."},
    {title:'The ocean breath · Ujjayi', cue:'Soften the throat; let each breath whisper like the sea.', secs:190,
     teach:"The second breath is Ujjayi, the ocean breath. Narrow the back of the throat just slightly, as if to fog a mirror with the mouth closed, until the breath hushes like waves drawing back over sand. That soft sound gives the mind a single thread to follow, and the gentle resistance lengthens and steadies each breath. It is said to echo the shankha, Vishnu's conch — the first sound, from which all worlds arose. So ride the quiet roar of your own breathing, and let it hold you the way the ocean holds the sleeping god."},
    {title:'The square breath · Sama Vritti', cue:'In four · hold four · out four · hold four.', secs:190,
     teach:"The third breath is Sama Vritti, the square breath. In for four, hold for four, out for four, hold for four — each side the same length, calm and even. This is preservation made physical: balance kept, moment to moment, nothing rushed. And here is the whole secret of change, hidden in one simple practice — each time the mind slips from the count, you notice, and come back. That returning, repeated without a trace of judgment, is exactly how a life is sustained, and slowly made new. In, hold, out, hold. Come home to the square."},
  ]
},{
  code:'vishnu_emblems', title:'Vishnu · IV', subtitle:'Emblems & the Name',
  track:'devotion', level:'Core', focus:'Spiritual undertones · mantra', part:4, series:'Vishnu',
  technique:'Mantra japa',
  tradition:'Hindu · the Preserver', img:'', soundscape:'ocean', accent:'#5fa8ff',
  prompt:'Which do you most need right now — a call that wakes you, clear seeing, steady strength, or an unstained heart?',
  blurb:'Part 4 of the Vishnu course — the spiritual undertones. Sit with the four emblems he holds and the ancient name Om Namo Narayanaya, used for ages as a way of coming home.',
  segments:[
    {title:'The four emblems', cue:'Breathe into each: sound · clarity · strength · purity.', secs:210,
     teach:"In his four hands Vishnu holds four emblems — and each one is a power already alive in you. The conch, Panchajanya: the first sound, Om, the call that wakes you. The discus, the Sudarshana chakra: the clear mind that cuts cleanly through illusion and spinning distraction. The mace, Kaumodaki: the unshakable strength that steadies you, the power of knowing. And the lotus, Padma: awareness itself, blooming pure though it rises straight from the mud. To sustain anything worthwhile you need all four — a call that wakes you, a mind that sees, the strength to stay, and a heart that stays unstained. With each breath, let one of them quietly wake."},
    {title:'The name · Om Namo Narayanaya', cue:'Silently, or hum softly: Om Namo Narayanaya.', secs:210,
     teach:"There is a name older than memory: Om Namo Narayanaya — I bow to Narayana, the infinite that rests upon the waters and within all beings. This is the ashtakshara, the eight-syllabled mantra, repeated across ages as a way of coming home. Let it move with the breath now. Hear it inwardly, or hum it low in the chest, like the conch still sounding beneath the sea. A mantra asks for nothing; it is only a handrail for the mind. Each time attention wanders, the name is simply there, waiting, and gathers you gently back."},
    {title:'Rest in the name', cue:'Let the words dissolve into quiet.', secs:120,
     teach:"Now let even the words dissolve, and simply rest. The call, the clear mind, the strength, the unstained heart — and the name beneath them all — need no effort now. Sit in the still center they rise from, and let it hold you, the way the sea holds the sleeping god."},
  ]
},{
  code:'vishnu_reflect', title:'Vishnu · V', subtitle:'Reflect & Give Thanks',
  track:'devotion', level:'Core', focus:'Reflection · gratitude', part:5, series:'Vishnu',
  technique:'Reflection · gratitude',
  tradition:'Hindu · the Preserver', img:'', soundscape:'ocean', accent:'#5fa8ff',
  prompt:'What is already being sustained in your life that you can give thanks for?',
  blurb:'Part 5, the close of the Vishnu course. Turn everything inward — what in your own life is yours to sustain — rest in stillness, and finish with a review and a gratitude reflection.',
  segments:[
    {title:'What are you sustaining?', cue:'Let one honest answer rise on its own.', secs:200,
     teach:"Turn everything we have gathered inward. Without straining for it, let a question settle: what in my life am I being asked to preserve? Perhaps a relationship, your health, a craft, a quiet faith in yourself — something that was never made in a single day, and cannot be kept in one either. And then, gently: what have I let slip that is mine to restore? Like Vishnu, you are not asked for one grand act, but for a descent — showing up again, in ordinary form, to tend what matters. Picture the one small practice, returned to daily, that would truly sustain it. Let it rest in you like a seed."},
    {title:'The lotus from the navel', cue:'Rest. Let the breath breathe itself.', secs:150,
     teach:"Now let the question go. From Vishnu's navel, the old stories say, rises a single lotus, and upon it a whole new world is born. So let your effort soften completely, and rest in that quiet center from which everything in you arises — thoughts, breath, the very wish to be well. There is nothing to sustain by force now. Only be, for a few breaths: vast, and blue, and still as the sleeping ocean before a new world opens."},
    {title:'Review & gratitude', cue:'Gently deepen the breath; let gratitude arise.', secs:180,
     teach:"Let us gather the whole journey. We took the seat of Vishnu the Preserver, and saw that sustenance is a practice of returning. We walked his avatars — the divine descending again and again to restore the balance. We learned three breaths: the three-part Dirga, the ocean Ujjayi, the square Sama Vritti. We held his four emblems — sound, clarity, strength, purity — and his name. Now, before you rise, offer a little gratitude: for the breath that kept you without being asked, for this time you gave yourself, and for one thing in your life that is already being sustained — name it quietly. Carry the Preserver's calm with you. Real change takes root not in grand gestures, but in what you return to tomorrow, and the day after. Rest here a moment, in that gratitude."},
  ]
},{
  code:'shiva', title:'Shiva · I', subtitle:'The Still Mountain',
  track:'devotion', level:'Core', focus:'Stillness', part:1, series:'Shiva',
  technique:'Kaya Sthairyam',
  tradition:'Hindu · the Transformer', img:'', soundscape:'space', accent:'#9d7bff',
  prompt:'Where in your life are you being asked to simply be still, and stop forcing?',
  blurb:'Part 1 of the Shiva course. Meet Shiva the Transformer — the great yogi of Mount Kailash — and take the posture of absolute stillness from which all letting-go begins.',
  segments:[
    {title:'The Mountain', cue:'Sit like a mountain. Let the body become still.', secs:150,
     teach:"Shiva is the great yogi, seated unmoving on Mount Kailash. He is Mahadeva — the one who transforms the world by letting the old dissolve. Where Vishnu preserves, Shiva clears the ground for what comes next. Begin where he begins: with Kaya Sthairyam, the yoga of stillness. Settle the body and quietly resolve not to move. Let every small fidget grow quiet. Stillness here is not rigidity — it is a mountain's ease. From this seat, nothing needs to be done."},
    {title:'What transformation means', cue:'Let the breath stay slow and even.', secs:170,
     teach:"We tend to fear Shiva's side of life — the ending, the destroyer. But look closely: nothing new can grow in ground that is already full. The old leaf must fall; night must come before dawn. Shiva's destruction is not cruelty — it is clearing, the grace that makes room. To transform is not to add, but to let what is finished dissolve. For these minutes you have nowhere to get to and nothing to hold. Rest in the mountain's stillness, and let that be enough."},
    {title:'Rest in stillness', cue:'Let the body be a mountain; breath moving through it.', secs:120,
     teach:"Let the breath move on its own, and keep the body still as stone. Notice how much of your ordinary effort is just holding — bracing, managing, keeping it all together. For now, set that down. A mountain does not hold itself up; it simply rests on the earth. Let yourself be held the same way."},
  ]
},{
  code:'shiva_dance', title:'Shiva · II', subtitle:'The Dance of Dissolution',
  track:'devotion', level:'Core', focus:'The still center', part:2, series:'Shiva',
  technique:'Witnessing',
  tradition:'Hindu · the Transformer', img:'', soundscape:'space', accent:'#9d7bff',
  prompt:'What keeps spinning in your mind — and can you rest as the still point it turns around?',
  blurb:'Part 2 of the Shiva course. The cosmic dance of Nataraja — creation and dissolution in one rhythm — and the still center at its heart, the part of you that only watches.',
  segments:[
    {title:'Nataraja · the cosmic dance', cue:'Everything moves. Simply watch.', secs:180,
     teach:"As Nataraja, the Lord of the Dance, Shiva dances the universe into being and out again — creation and dissolution in one endless rhythm. In his hands: a drum that beats the pulse of creation, and a flame that dissolves it. He dances in a ring of fire, one foot raised in freedom, the other resting on the demon of forgetfulness. The dance never stops. Breath rising and falling, thoughts coming and going, worlds turning — all of it is the dance."},
    {title:'The still point', cue:'Rest your attention on the unmoving center.', secs:180,
     teach:"Yet at the very center of that whirling dance is a point of perfect stillness. The dancer turns, but the axis does not. Thoughts may move, the breath may rise and fall, the whole world may spin — rest your attention on the still center that watches it all. You are not the dance; you are the quiet ground it turns around. Each time you are swept back into the spinning, gently return to the one who is simply watching."},
    {title:'Nilakantha · holding what is hard', cue:'Breathe steadily; let difficulty be held, not fought.', secs:160,
     teach:"When the gods churned the ocean, a world-ending poison rose up before the nectar. Shiva drank it to save all beings, holding it in his throat, which turned blue — and so he is Nilakantha, the blue-throated one, who can hold what is hard without being consumed by it. You have this capacity too. A difficulty need not be swallowed or spat out; it can simply be held, steadily, until its charge settles. Breathe, and let whatever is hard today be held in the throat of your attention — neither fought nor fled."},
  ]
},{
  code:'shiva_breath', title:'Shiva · III', subtitle:'The Releasing Breath',
  track:'devotion', level:'Core', focus:'Letting go', part:3, series:'Shiva',
  technique:'Long exhale · Bhramari',
  tradition:'Hindu · the Transformer', img:'', soundscape:'space', accent:'#9d7bff',
  prompt:'What are you ready to set down with the out-breath — and not pick back up?',
  blurb:'Part 3 of the Shiva course — the techniques. The long releasing exhale and the humming Bhramari breath: its own instruments of letting go.',
  segments:[
    {title:'The long exhale', cue:'Inhale 4 · exhale long and slow, 6 to 8.', secs:200,
     teach:"Shiva's gift is release, and the body has a built-in instrument for it: the long exhale. Breathe in for a count of four, and let the out-breath run six, seven, eight — slow, soft, and complete. An exhale longer than the inhale tells the nervous system it is safe to let go; it calms you the way dusk settles a landscape. With each out-breath, set one thing down. A worry. A grip. A version of yourself you no longer need to carry. Let the out-breath do what it was made to do."},
    {title:'Bhramari · the humming breath', cue:'Breathe in; on the exhale, hum low like a bee.', secs:190,
     teach:"Now add sound. Breathe in, and on the exhale hum low and soft, like a bee — this is Bhramari, the humming breath. Feel the vibration fill the throat and skull, smoothing the edges of thought. The hum gives the restless mind something simple to rest on, and lets the charge of difficulty dissolve into sound. A few rounds: a full inhale, then a long, low hum out. Let the humming soften everything it touches."},
    {title:'The quiet after', cue:'Stop the hum. Rest in the silence it leaves.', secs:120,
     teach:"Let the humming stop, and rest in the silence it leaves behind — a silence that feels somehow fuller than before. This is the space that releasing opens. You do not have to fill it. Just breathe naturally, and let the body enjoy how much lighter it is to hold nothing at all."},
  ]
},{
  code:'shiva_name', title:'Shiva · IV', subtitle:'The Third Eye & the Name',
  track:'devotion', level:'Core', focus:'Clear seeing · mantra', part:4, series:'Shiva',
  technique:'Ajna focus · Om Namah Shivaya',
  tradition:'Hindu · the Transformer', img:'', soundscape:'space', accent:'#9d7bff',
  prompt:'What old story about yourself are you ready to see clearly — and let burn away?',
  blurb:'Part 4 of the Shiva course — the spiritual undertones. The third eye of clear seeing, the sacred ash of what passes, and the great five-syllable mantra Om Namah Shivaya.',
  segments:[
    {title:'The third eye', cue:'Rest attention gently between the brows.', secs:180,
     teach:"On Shiva's brow is a third eye — not for looking outward, but for seeing clearly. When it opens, it burns illusion to ash. Rest your attention lightly at the point between the eyebrows, the ajna center. No strain, no effort to see anything — just a soft inward gaze. Let the clear seeing of this place rest on one illusion you have carried about yourself: some old story, some quiet verdict, that was never quite true. Don't argue with it. Simply see it clearly, in the light — and that seeing alone begins to loosen its hold."},
    {title:'Ash and renewal', cue:'Let a thought arise, and let it dissolve.', secs:160,
     teach:"Shiva covers his body with vibhuti, sacred ash — a reminder that all forms pass, and that what burns away leaves something pure behind. Watch the next thought that arises. Don't fight it; simply let it dissolve, the way smoke thins into open sky. Nothing is truly lost. What falls away only makes room. This is destruction as grace: the clearing that lets the new begin."},
    {title:'Om Namah Shivaya', cue:'Silently repeat the five syllables.', secs:180,
     teach:"The great mantra of Shiva has five syllables: Om Namah Shivaya — I bow to the auspicious Self within. Let it turn slowly with the breath, each syllable a stone dropped into a still pool. When the mind wanders off, the mantra simply waits, and gently gathers it back. Let the sound, and the silence between the sounds, hold you."},
  ]
},{
  code:'shiva_reflect', title:'Shiva · V', subtitle:'Reflect & Give Thanks',
  track:'devotion', level:'Core', focus:'Reflection · gratitude', part:5, series:'Shiva',
  technique:'Reflection · gratitude',
  tradition:'Hindu · the Transformer', img:'', soundscape:'space', accent:'#9d7bff',
  prompt:'What are you ready to let dissolve — and what new space might open once you do?',
  blurb:'Part 5, the close of the Shiva course. Turn it inward — what you are ready to release — rest in the spaciousness it opens, and finish with a review and gratitude.',
  segments:[
    {title:'What are you ready to release?', cue:'Let one honest answer rise.', secs:190,
     teach:"Turn everything inward. Without forcing, let a question settle: what am I ready to let dissolve? A grudge, a fear, an old identity, a way of holding yourself too tightly — something finished, that you have been carrying out of habit. You do not have to banish it by force. Simply name it, and loosen your grip, the way you release a long exhale. And notice: what new space might open once it is gone? Let yourself glimpse that opening."},
    {title:'The spaciousness of letting go', cue:'Rest in the open space.', secs:150,
     teach:"Rest now in the spaciousness that releasing opens. Thoughts may still come, but there is more room around them. True change is not only building; it is also this — releasing, again and again, what no longer serves. You do not become new by adding more. You become new by what you are willing to let fall away. Rest in that clear, ashed-clean quiet."},
    {title:'Review & gratitude', cue:'Gently deepen the breath; let gratitude arise.', secs:170,
     teach:"Let us gather the journey. We took the mountain's stillness, and found the still point at the center of the dance. We learned to hold what is hard, like Nilakantha, and to release with the long exhale and the humming breath. We rested in the third eye's clear seeing, watched a thought dissolve like ash, and turned the mantra Om Namah Shivaya. Now offer gratitude — for the capacity to let go, for the space it opens, and for one thing you are ready to release with thanks rather than struggle. Name it quietly, and let it go."},
  ]
},{
  code:'lakshmi', title:'Lakshmi · I', subtitle:'The Lotus',
  track:'devotion', level:'Core', focus:'Receiving', part:1, series:'Lakshmi',
  technique:'Opening the posture',
  tradition:'Hindu · the Giver of Grace', img:'', soundscape:'forest', accent:'#f5a9d0',
  prompt:'What would it feel like to simply receive today, without earning it first?',
  blurb:'Part 1 of the Lakshmi course. Meet Lakshmi, goddess of abundance and grace — consort of Vishnu — and take the open, receptive posture of the lotus from which all her gifts flow.',
  segments:[
    {title:'Seated on the lotus', cue:'Soften the face. Let the posture open.', secs:150,
     teach:"Lakshmi is always seated upon a lotus — the flower that rises out of muddy water and blooms unstained. It means that fortune and grace can grow from any ground, and that you are already whole beneath whatever has muddied the surface. She is the goddess of Shri: abundance, beauty, and grace — not wealth hoarded, but prosperity that flows. Let your shoulders drop, your jaw soften, your palms rest open on your knees. Begin simply, by being willing to receive."},
    {title:'Abundance that flows', cue:'Let the breath arrive and leave freely.', secs:160,
     teach:"In her images, gold coins stream endlessly from Lakshmi's open palm — abundance that flows precisely because it is never clutched. A closed fist can hold nothing new; only the open hand both gives and receives. This is her teaching: true abundance is not a pile to defend, but a current to stay in. Let each breath arrive and depart freely, held onto nothing. Nothing needs gripping here."},
    {title:'Willing to receive', cue:'Breathe in, and simply let it land.', secs:120,
     teach:"Many of us are far better at giving than receiving. For these breaths, simply let yourself be given to. Breathe in as if drawing in warm, soft light, and let it settle in the chest. You do not have to earn this breath, this moment, this ease. It is already given. Let it land."},
  ]
},{
  code:'lakshmi_forms', title:'Lakshmi · II', subtitle:'The Eight Forms',
  track:'devotion', level:'Core', focus:'True wealth', part:2, series:'Lakshmi',
  technique:'Contemplation',
  tradition:'Hindu · the Giver of Grace', img:'', soundscape:'forest', accent:'#f5a9d0',
  prompt:'Where are you richer than you usually admit?',
  blurb:'Part 2 of the Lakshmi course. Ashta Lakshmi — her eight forms — reveal that abundance is far more than money. A contemplation of the many kinds of wealth you already hold.',
  segments:[
    {title:'Ashta Lakshmi · the eight forms', cue:'Rest easy. Simply listen.', secs:190,
     teach:"Lakshmi is honored in eight forms — Ashta Lakshmi — because abundance is far more than money. There is the wealth of health, and of knowledge; of courage, and of nourishment; the wealth of family and friendship; victory over hardship; and the wealth of the spirit. Money is only one coin among many. Most of us are quietly rich in forms we never stop to count."},
    {title:'What you already hold', cue:'Let your attention rest on what is already here.', secs:180,
     teach:"Let your attention move, without rushing, over the forms of wealth you already carry. The body that works, more or less, to carry you through a day. The people who would answer if you called. Something you know how to do well. A hardship you have already survived. Where are you richer than you usually admit? Don't manufacture gratitude — just look honestly, and let yourself feel genuinely well-resourced."},
    {title:'Enough', cue:'Breathe, and rest in sufficiency.', secs:140,
     teach:"Beneath the wish for more there is often a quiet fear of not-enough. For these breaths, try on the opposite: that right now, in this moment, there is enough — enough air, enough time, enough of you. Abundance begins the instant the grasping stops. Rest in that sufficiency, and breathe."},
  ]
},{
  code:'lakshmi_breath', title:'Lakshmi · III', subtitle:'The Open Hand',
  track:'devotion', level:'Core', focus:'Coherent breath', part:3, series:'Lakshmi',
  technique:'Heart-centered breathing',
  tradition:'Hindu · the Giver of Grace', img:'', soundscape:'forest', accent:'#f5a9d0',
  prompt:'What does your heart feel like when it stops bracing?',
  blurb:'Part 3 of the Lakshmi course — the technique. Coherent heart-centered breathing, which brings the rhythm of the heart into balance.',
  segments:[
    {title:'Hand on the heart', cue:'Hand on heart. Breathe in 5 · out 5, smooth and even.', secs:200,
     teach:"Rest a hand over your heart, and breathe at an easy, even pace — in for a slow five, out for a slow five. At this gentle rhythm, something in the body comes into tune: heart and lungs and the pulse of the blood fall into one rhythm, like a current finding its level — a physical echo of Lakshmi's flowing grace. Let each breath be smooth and round, with no hard edge between in and out. And feel the warmth gathering under your hand."},
    {title:'The breath that gives and receives', cue:'Receive on the in-breath; offer on the out-breath.', secs:170,
     teach:"Let the breath itself become the open hand. On each in-breath, receive — draw in warmth, ease, enough. On each out-breath, offer — let something soften and flow outward. In, received; out, given. Neither half is clutched. This is the whole lesson of Lakshmi carried in a single breath: abundance is a current you stay in, not a thing you keep."},
  ]
},{
  code:'lakshmi_flow', title:'Lakshmi · IV', subtitle:'Gratitude & the Flow',
  track:'devotion', level:'Core', focus:'Gratitude · generosity', part:4, series:'Lakshmi',
  technique:'Gratitude · Metta',
  tradition:'Hindu · the Giver of Grace', img:'', soundscape:'forest', accent:'#f5a9d0',
  prompt:'Who in your life could you let your abundance flow toward?',
  blurb:'Part 4 of the Lakshmi course — the heart of the practice. Gratitude for what is already here, and generosity that lets abundance move outward as grace.',
  segments:[
    {title:'What is already here', cue:'Name silently what you are grateful for.', secs:180,
     teach:"True abundance begins not with more, but with noticing what is already given. The breath, arriving without being asked. The body, carrying you. This quiet moment, yours. Let gratitude move through you in specifics — name three things, small and real. Gratitude is simply how the mind learns to see the abundance that was there all along."},
    {title:'The flow · wishing plenty outward', cue:'On each exhale, wish abundance to another.', secs:180,
     teach:"Abundance that only gathers becomes stagnant; abundance that moves becomes grace. As you breathe out, send a wish of plenty outward: May you have enough. May you be well. May you flourish. Begin with someone you love, then someone you barely know, then, if you can, someone you find difficult. Generosity is not loss — it is the open hand through which more can always flow."},
    {title:'Shri · the quiet radiance', cue:'Let yourself receive. Breathe in warmth.', secs:150,
     teach:"Lakshmi is called Shri: auspiciousness, radiance, the quiet glow of the blessed. Having given, now let yourself receive in turn. Breathe in as if drawing warm gold light into the chest; let it fill and settle. You are allowed to receive goodness, not only to hand it out. Let it land, and let yourself glow a little."},
  ]
},{
  code:'lakshmi_reflect', title:'Lakshmi · V', subtitle:'Reflect & Give Thanks',
  track:'devotion', level:'Core', focus:'Reflection · gratitude', part:5, series:'Lakshmi',
  technique:'Reflection · gratitude',
  tradition:'Hindu · the Giver of Grace', img:'', soundscape:'forest', accent:'#f5a9d0',
  prompt:'What is already abundant in your life that you often overlook — and who might you let it flow toward?',
  blurb:'Part 5, the close of the Lakshmi course. Turn it inward — the abundance you overlook and where it might flow — then rest and finish with a review and gratitude.',
  segments:[
    {title:'What you overlook', cue:'Let one honest answer rise.', secs:190,
     teach:"Turn it inward. Without reaching, let a question settle: what is already abundant in my life that I usually overlook? And then: who might I let it flow toward — a person, a cause, a small daily generosity? Picture the open hand, giving and receiving in the same motion. You do not become abundant by getting more. You become abundant the moment you notice what is here, and let it move."},
    {title:'Rest in fullness', cue:'Breathe, and rest in the open hand.', secs:150,
     teach:"Rest now with two things held lightly: a grateful eye that notices what is already here, and an open hand that lets good flow both in and out. Practiced daily, this quietly changes a life — not by adding more, but by revealing how much was always given. Breathe, and rest in that fullness."},
    {title:'Review & gratitude', cue:'Gently deepen the breath; let gratitude arise.', secs:170,
     teach:"Let us gather the journey. We took the lotus seat and the willingness to receive. We counted the eight forms of wealth already ours, and breathed the coherent breath of the open heart. We gave plenty away, and let ourselves receive in turn. Now, before you rise, offer thanks — for the abundance you so easily overlook, for the people through whom it flows, and for one specific gift in your life, named quietly and received fully. Let gratitude be the last thing you hold."},
  ]
},{
  code:'breath', title:'Breath · I', subtitle:'Arrive & Notice',
  track:'foundations', level:'Beginner', focus:'Interoception', part:1, series:'Breath',
  technique:'Natural breath',
  tradition:'Secular · science-based', img:'', soundscape:'rain', accent:'#5fd0c8',
  prompt:'What did your natural breath feel like before you changed anything?',
  blurb:'Part 1 of the Breath course. No belief required — just the science of how breath steers the nervous system. Begin by learning to feel your own breath, the skill everything else is built on.',
  segments:[
    {title:'The one lever you can reach', cue:'Breathe naturally. Just notice.', secs:150,
     teach:"Of everything the body does on its own — the heartbeat, the tide of the blood — the breath is the one you can take by the hand. That is a quiet kind of power, and it has been with you the whole time. For now, change nothing. Let the breath come as it comes, and simply feel it. Does it rise in the chest, or down in the belly? Is it quick, or slow — smooth, or a little ragged? You are not fixing anything here. You are only arriving, and letting yourself be felt from the inside."},
    {title:'Interoception · feeling from within', cue:'Follow one full breath, in and out.', secs:150,
     teach:"This feeling from within — the old teachers had a word for it, interoception — is the ground everything else grows from. It is not learned once; it deepens each time you turn toward it. So follow a single breath the whole way home, from the first faint stir of the in-breath to the last of the out. When it is gone, meet the next one. You are not steering yet. You are only learning the texture of what is already happening — and strange as it sounds, that quiet attention is already settling you."},
  ]
},{
  code:'breath_sigh', title:'Breath · II', subtitle:'The Physiological Sigh',
  track:'foundations', level:'Beginner', focus:'Fast reset', part:2, series:'Breath',
  technique:'Physiological sigh',
  tradition:'Secular · science-based', img:'', soundscape:'rain', accent:'#5fd0c8',
  prompt:'When this week could a double-inhale sigh help you reset on the spot?',
  blurb:'Part 2 of the Breath course. The fastest real-time tool for calming down — the physiological sigh — and the simple physiology behind why it works.',
  segments:[
    {title:'The double inhale', cue:'Double inhale through the nose · long exhale through the mouth.', secs:180,
     teach:"When the body is running hot and you need it to settle now, there is a breath for this — one you have taken in your sleep and after crying, your whole life, without ever being taught. Breathe in through the nose… then sip a little more air on top, filling the lungs to the brim… and let it go, long and slow, through the mouth. Let the out-breath be longer than you think you need. Try a few, unhurried: two breaths drawn in, one long breath poured out."},
    {title:'Why it works', cue:'Keep sighing gently; feel the body downshift.', secs:160,
     teach:"Here is the quiet reason it works. Through a long day the smallest chambers of the lungs sag closed; that second sip of air opens them again, and the long exhale reaches down and slows the heart itself. This is the body's own reset — no one had to teach it to you, you simply knew. The only gift is this: now you can choose it. A few sighs before the hard moment, and the whole system steps down off its toes."},
  ]
},{
  code:'breath_vagus', title:'Breath · III', subtitle:'The Long Exhale',
  track:'foundations', level:'Beginner', focus:'Vagal tone', part:3, series:'Breath',
  technique:'Long exhale · Coherent',
  tradition:'Secular · science-based', img:'', soundscape:'rain', accent:'#5fd0c8',
  prompt:'Does a longer out-breath than in-breath change how you feel?',
  blurb:'Part 3 of the Breath course. Why the exhale calms — the vagus nerve — and coherent breathing, the resonant rhythm that balances the whole system.',
  segments:[
    {title:'Why the exhale calms', cue:'Inhale 4 · exhale 6.', secs:180,
     teach:"Rest a hand somewhere on the body and feel this: breathe in, and the heart quickens a little; breathe out, and it eases. That easing has a name — the vagus nerve, the long quiet cable of your rest. So the out-breath is a brake you can press on purpose. Breathe in for four… and out for six. You are not only relaxing. With every slow exhale you are tending the very nerve that carries you home to calm."},
    {title:'Coherent breathing', cue:'In 5.5 · out 5.5. Smooth, round, even.', secs:200,
     teach:"Now let the two halves even out. Around five and a half breaths a minute — a slow count of five or six in, the same out — something lovely happens: heart, lungs, and blood fall into one rhythm, like instruments tuning to a single note. There is a word for it, resonance, and the body answers with its deepest ease and resilience. Let the breath grow round and seamless, no edge between in and out. This is the pace to come home to whenever the ground feels unsteady."},
  ]
},{
  code:'breath_box', title:'Breath · IV', subtitle:'Box Breathing',
  track:'foundations', level:'Beginner', focus:'Focus', part:4, series:'Breath',
  technique:'Box breath',
  tradition:'Secular · science-based', img:'', soundscape:'rain', accent:'#5fd0c8',
  prompt:'Where would steady focus serve you better than relaxation?',
  blurb:'Part 4 of the Breath course. Box breathing — for steadiness and sharp focus rather than sleepiness — and the held pauses that quietly train the body.',
  segments:[
    {title:'Squaring the breath', cue:'In 4 · hold 4 · out 4 · hold 4.', secs:190,
     teach:"Some moments do not call for softening — they call for steadiness, a clear and level mind. For those, draw the breath as a square. In for four… hold for four… out for four… hold for four. Soldiers and surgeons lean on this before the pressure lands, and now so can you. Let every side of the square be the same unhurried length. In. Hold. Out. Hold. And feel how steady the body becomes beneath you."},
    {title:'The gift of the pause', cue:'Rest in the held pauses, without strain.', secs:150,
     teach:"Those held pauses are not empty time. Gently, over many days, they teach the body to hold a little more stillness, until your ordinary breathing turns slower and calmer on its own. Keep the holds easy — never strained, never a struggle. And notice the quiet inside them: no breath coming, none going, just a wakeful hush. That hush is yours — always a breath away, any time you square the breath."},
  ]
},{
  code:'breath_carry', title:'Breath · V', subtitle:'Integrate & Carry',
  track:'foundations', level:'Beginner', focus:'Integration', part:5, series:'Breath',
  technique:'Natural breath · choosing',
  tradition:'Secular · science-based', img:'', soundscape:'rain', accent:'#5fd0c8',
  prompt:'Which one breath will you keep for this week, and when will you use it?',
  blurb:'Part 5, the close of the Breath course. Feel the contrast of a settled nervous system, then choose one tool to carry into your days.',
  segments:[
    {title:'Rest and notice', cue:'Let the breath go completely natural again.', secs:150,
     teach:"Now let the breath off its leash entirely. Nothing to count, nothing to shape — let it do as it pleases, and only watch. And feel the body against how it felt a few minutes ago. Slower, perhaps. Warmer. More here. Stay with that a moment, because this is the whole teaching: you did that. No app, no device, nothing bought or downloaded — only air, and your own attention. These tools never leave you. They wait for the moment you remember them."},
    {title:'Carry one tool', cue:'Choose one breath to keep for this week.', secs:140,
     teach:"So you carry four things out of here. The sigh, for stress that lands all at once. The long exhale, to unwind. The even, resonant breath, for balance. The square breath, for focus. You do not need them all — a practice is only one good tool, returned to and returned to. Choose the one that served you most today, and promise it a place this week: at a red light, before the hard conversation, in the dark before sleep. Let that small vow settle, and carry it with you."},
  ]
}];
// --- curriculum: tracks group the lessons; roadmap shows the program is growing ---
const TRACKS=[
  {key:'foundations', name:'Foundations', sub:'The practice itself — start here. Universal, secular, science-grounded.', accent:'#5fd0c8'},
  {key:'devotion', name:'Deities & Devotion', sub:'Contemplative journeys through the great figures of the Hindu tradition — myth as a mirror for the mind.', accent:'#f5c977'},
];
const ROADMAP={
  foundations:[{title:'The Body Scan', sub:'Somatic awareness, head to toe'},{title:'Loving-Kindness (Metta)', sub:'Warmth for self and others'},{title:'Noting the Mind', sub:'Labeling thought and feeling'}],
  devotion:[{title:'Ganesha', sub:'Removing inner obstacles'},{title:'Saraswati', sub:'Clarity, learning, and flow'},{title:'Durga', sub:'Courage and protective strength'}],
};
const lessonMins=(l)=>Math.max(1,Math.round(l.segments.reduce((s,x)=>s+x.secs,0)/60));
let lsSpeak=true;let lessonReflect=null;
/* The Lumen Method — every guided journey is delivered the same way:
   a calm lead-in, then for each segment the teaching is spoken one line at a time
   with reflective silences between lines and a longer guided stillness to close the
   segment, a soft bell at each threshold, and a signature return. Pacing adapts to
   each segment's length so there is always room to think, breathe, and rest. */
async function lessonPlay(lesson, startSi){
  try{await api('session/start','POST',{});}catch(e){}
  getGeo();
  lsSpeak=true;
  const nSeg=lesson.segments.length;
  startSi=Math.max(0,Math.min(parseInt(startSi||0,10)||0,nSeg-1));
  // --- build the paced timeline ---
  const steps=[];
  steps.push({kind:'seg', si:0, open:true});
  steps.push({kind:'say', si:0, lead:true, text:"Welcome. This is Lumen. Find a comfortable seat, let the body grow still, and when you're ready, let your eyes gently close."});
  steps.push({kind:'silence', si:0, dur:6, label:'Settling in', rest:true});
  steps.push({kind:'say', si:0, lead:true, text:"I'll stay beside you — speaking when it helps, and falling quiet so you can simply be. There is nowhere to be, and nothing to do, but here."});
  steps.push({kind:'silence', si:0, dur:5, label:'…', rest:true});
  lesson.segments.forEach((seg,si)=>{
    steps.push({kind:'seg', si});
    const sents=splitSents(seg.teach).map(s=>s.trim()).filter(Boolean);
    const speechEst=sents.reduce((a,s)=>a+estSay(s),0);
    const slack=Math.max((seg.secs||90)-speechEst, sents.length*2.5+6);
    const gap=Math.min(7,Math.max(2.5,(slack*0.4)/Math.max(1,sents.length)));
    const rest=Math.min(46,Math.max(7, seg.rest!=null?seg.rest:slack*0.6));
    sents.forEach((s,k)=>{
      const last=k===sents.length-1;
      steps.push({kind:'say', si, text:s});
      steps.push({kind:'silence', si, dur:last?rest:gap, cue:seg.cue, rest:last,
        label:last?(seg.restLabel||'Rest here · stay with the breath'):''});
    });
  });
  steps.push({kind:'seg', si:nSeg-1, close:true});
  steps.push({kind:'say', si:nSeg-1, lead:true, text:"Our time here is complete. Carry a little of this light with you into whatever comes next. When you're ready, take a slower, deeper breath, feel the weight of the body, and gently open your eyes."});
  steps.push({kind:'silence', si:nSeg-1, dur:5, label:'…', rest:true});
  const totalEst=Math.max(30, steps.reduce((a,st)=>a+(st.kind==='say'?estSay(st.text)+0.4:(st.kind==='silence'?st.dur:1)),0));
  const stEst=(st)=>st.kind==='say'?estSay(st.text)+0.4:(st.kind==='silence'?st.dur:1);
  let elapsed=0, ended=false, idx=0, stepTimer=null;
  // resume: jump to the segment where the user left off, with a short welcome-back
  if(startSi>0){
    const at=steps.findIndex(st=>st.kind==='seg'&&st.si===startSi&&!st.open&&!st.close);
    if(at>0){
      elapsed=Math.round(steps.slice(0,at).reduce((a,st)=>a+stEst(st),0));
      steps.splice(at,0,{kind:'say',si:startSi,lead:true,text:"Welcome back. This is Lumen — let's take up the thread just where you left it."},
                        {kind:'silence',si:startSi,dur:3,label:'Settling back in',rest:true});
      idx=at;
    }
  }
  $('#nav').classList.add('hidden');
  $('#app').innerHTML=`
  <div class="lesson-bg" style="background-image:url(${SERIES_ART[lesson.series]||lesson.img||''})"></div>
  <div class="lesson-screen">
    <div class="lesson-top">
      <div class="lesson-ttl"><span style="color:${lesson.accent}">${esc(lesson.title)}</span> · <span class="muted">${esc(lesson.subtitle)}</span></div>
      <div class="lesson-step muted" id="lstep"></div>
      <div class="jny-bar" style="margin-top:7px"><i id="lprog" style="width:0%"></i></div>
    </div>
    <div class="lesson-mid">
      <div class="orb-wrap lorb-wrap" style="height:220px;--a:${lesson.accent}"><div class="ring"></div><div class="orb" id="lorb"><div class="t" style="font-size:19px">◦</div></div><div class="breath-label" id="lcue"></div></div>
      <div class="lesson-teach" id="lteach"></div>
    </div>
    <div class="lesson-foot">
      <button class="mic on" id="lmute" title="Narration">${ic('sound')}</button>
      <div class="muted" id="lrem" style="flex:1;text-align:center;font-size:13px"></div>
      <button class="btn ghost" id="lend" style="width:auto;padding:11px 18px">End</button>
    </div>
  </div>`;
  try{Sound.start(lessonSoundPick||lesson.soundscape);}catch(e){}
  const tick=setInterval(()=>{if(ended)return;elapsed=Math.min(totalEst,elapsed+1);
    const p=$('#lprog');if(p)p.style.width=Math.round(100*elapsed/totalEst)+'%';
    const rem=Math.max(0,Math.round(totalEst-elapsed));const r=$('#lrem');if(r)r.textContent=`${Math.floor(rem/60)}:${String(rem%60).padStart(2,'0')} left`;},1000);
  function setHeader(si){const seg=lesson.segments[si]||lesson.segments[0];const s=$('#lstep');if(s)s.textContent=`Step ${si+1} of ${nSeg} · ${seg.title}`;}
  function showLine(text,lead){const tt=$('#lteach');if(tt){tt.textContent=text;tt.classList.toggle('lead',!!lead);tt.classList.remove('resting');}
    const o=$('#lorb');if(o)o.classList.remove('breathe');}
  function showSilence(cue,label,rest){const lc=$('#lcue');if(lc&&cue)lc.textContent=cue;
    const tt=$('#lteach');if(tt&&(rest||label)){tt.textContent=label||'';tt.classList.add('resting');tt.classList.remove('lead');}
    const o=$('#lorb');if(o)o.classList.add('breathe');}
  function clearStep(){if(stepTimer){clearTimeout(stepTimer);stepTimer=null;}stopNarration();}
  function nextSayText(){for(let j=idx;j<steps.length;j++){if(steps[j].kind==='say')return steps[j].text;}return null;}
  function runStep(){
    if(ended)return;
    if(idx>=steps.length){finish(true);return;}
    const st=steps[idx++];
    if(st.kind==='seg'){setHeader(st.si);const seg=lesson.segments[st.si];const lc=$('#lcue');if(lc)lc.textContent=seg.cue||'';
      if(!st.close)jnySave(lesson.code, st.si);  // remember our place for Continue
      if(!st.open){try{Sound.bell();}catch(e){}}
      stepTimer=setTimeout(runStep, st.open?700:1300);return;}
    if(st.kind==='say'){showLine(st.text, st.lead);
      if(lsSpeak){let adv=false;const go=()=>{if(adv||ended)return;adv=true;stepTimer=setTimeout(runStep,300);};
        narrate(st.text, go);
        ttsPrefetch(nextSayText());  // warm the next line so playback stays seamless
        setTimeout(go, estSay(st.text)*2200+9000);  // generous safety net (audio may run longer than estimate)
      } else {stepTimer=setTimeout(runStep, estSay(st.text)*1000);}
      return;}
    if(st.kind==='silence'){showSilence(st.cue, st.label, st.rest);
      stepTimer=setTimeout(runStep, Math.max(1,st.dur)*1000);return;}
  }
  async function finish(complete){if(ended)return;ended=true;clearStep();clearInterval(tick);try{Sound.stop();}catch(e){}stopNarration();
    if(complete){jnyClear(lesson.code);try{Sound.bell();}catch(e){}}  // finished → clear resume point
    const mins=Math.max(1,Math.round((complete?totalEst:elapsed)/60));
    const body={minutes:mins,soundscape:lesson.soundscape,mood:'',note:'Guided lesson · '+lesson.title,lesson:lesson.code,track:lesson.track};
    if(geoFix&&Date.now()-geoFix.t<3600000){body.lat=geoFix.lat;body.lon=geoFix.lon;}
    let res;try{res=await api('session/complete','POST',body);}catch(e){go('meditate');return;}
    try{const r=await api('me');ME=r.profile;}catch(e){}
    lessonReflect=complete&&lesson.prompt?lesson.prompt:null;
    showRewards(res,mins);}
  $('#lend').onclick=()=>finish(false);
  $('#lmute').onclick=()=>{lsSpeak=!lsSpeak;const m=$('#lmute');if(m){m.innerHTML=ic(lsSpeak?'sound':'mute');m.classList.toggle('on',lsSpeak);}
    if(!lsSpeak)stopNarration();};
  runStep();
}

/* ---- map ---- */
let mapScope='today';
let mapPhotos=(()=>{try{return localStorage.getItem('lumen_mapphotos')==='1';}catch(e){return false;}})();
const SS_LABEL={rain:'Rain',forest:'Forest',ocean:'Ocean',space:'Deep Space',silence:'Silence'};
function ago(iso){const s=(Date.now()-new Date(iso).getTime())/1000;if(s<90)return 'just now';if(s<3600)return Math.round(s/60)+'m ago';if(s<86400)return Math.round(s/3600)+'h ago';return Math.round(s/86400)+'d ago';}
function mapMarker(pt){
  const mine=pt.mine===1;const color=mine?'#f5c977':'#c084fc';
  let icon;
  if(mapPhotos&&pt.photo){
    const sz=mine?40:34;
    icon=L.divIcon({className:'mkr-wrap',iconSize:[sz,sz],iconAnchor:[sz/2,sz/2],
      html:`<div class="mkr-photo ${mine?'me':''}" style="--c:${color}"><img src="${esc(pt.photo)}" alt="" loading="lazy" onerror="this.parentNode.innerHTML='${ic(pt.soundscape||'silence','mkri').replace(/'/g,'&#39;')}'"></div>`});
  }else{
    icon=L.divIcon({className:'mkr-wrap',iconSize:[mine?34:28,mine?34:28],iconAnchor:[mine?17:14,mine?17:14],
      html:`<div class="mkr ${mine?'me':''}" style="--c:${color}">${ic(pt.soundscape||'silence','mkri')}</div>`});
  }
  const m=L.marker([pt.lat,pt.lon],{icon});
  m.bindPopup(`<div class="pop">${pt.photo?`<img class="pop-img" src="${esc(pt.photo)}" alt="meditation spot" onerror="this.remove()">`:''}<div class="pop-h"><span class="pop-ic" style="color:${color}">${ic(pt.soundscape||'silence')}</span><b>${esc(pt.name)||'Someone'}</b>${mine?' <span class="pop-you">you</span>':''}</div>`+
    `<div class="pop-b">${pt.minutes} min · ${SS_LABEL[pt.soundscape]||esc(pt.soundscape)}</div>`+
    `<div class="pop-m">${esc(pt.city)||'Somewhere on Earth'} · ${ago(pt.ended)}</div></div>`,
    {closeButton:false});
  return m;
}
async function renderMap(){
  journeyTok++;  // cancel any in-flight journey timelapse
  try{Sound.stop();}catch(e){}
  // A brand-new account has no places of its own — open on "My places" (empty),
  // not the community "Today" map, so it never looks like you meditated elsewhere.
  if(!window._mapScopeInit){window._mapScopeInit=1;if(ME&&(ME.total_sessions||0)===0)mapScope='mine';}
  $('#app').innerHTML=`
  <div class="brand"><span class="mark">${lumenMark('mark')}</span><b>World</b></div>
  <div class="seg" id="scope"><button class="${mapScope==='today'?'on':''}" data-s="today">Today</button><button class="${mapScope==='all'?'on':''}" data-s="all">All time</button><button class="${mapScope==='mine'?'on':''}" data-s="mine">My places</button></div>
  <div class="map-view"><button class="map-vbtn ${mapPhotos?'on':''}" id="mvphoto">${ic('camera')} Photos</button><button class="map-vbtn ${mapPhotos?'':'on'}" id="mvicon">${ic('lumen')} Icons</button></div>
  <div id="pres" class="muted center" style="margin:10px 0"></div>
  <div id="map"></div>
  <div class="card" id="legend" style="padding:12px 14px;margin-top:10px">
    <div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap;font-size:12px">
      <span style="display:flex;align-items:center;gap:7px"><span class="dotleg" style="--c:#f5c977"></span>You</span>
      <span style="display:flex;align-items:center;gap:7px"><span class="dotleg" style="--c:#c084fc"></span>Community</span>
    </div>
    <div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin-top:10px;color:var(--muted);font-size:12px">
      ${['rain','forest','ocean','space','silence'].map(s=>`<span style="display:flex;align-items:center;gap:5px">${ic(s,'p')} ${SS_LABEL[s]}</span>`).join('')}
    </div>
  </div>
  <p class="muted center" style="font-size:12px;margin-top:10px">Each glow is a real session. Locations are blurred for privacy.</p>`;
  $('#scope').querySelectorAll('button').forEach(b=>b.onclick=()=>{mapScope=b.dataset.s;renderMap();});
  const setPhotos=(v)=>{mapPhotos=v;try{localStorage.setItem('lumen_mapphotos',v?'1':'0');}catch(e){}renderMap();};
  $('#mvphoto').onclick=()=>{if(!mapPhotos)setPhotos(true);};
  $('#mvicon').onclick=()=>{if(mapPhotos)setPhotos(false);};
  map=L.map('map',{attributionControl:false,zoomControl:true,worldCopyJump:true}).setView([20,0],2);
  map.zoomControl.setPosition('topright');
  // Keyless Esri dark-gray basemap (same approach as travelog — no API key needed)
  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',{maxZoom:16}).addTo(map);
  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}',{maxZoom:16}).addTo(map);
  let data={points:[]};try{data=await api('map?scope='+mapScope);}catch(e){}
  setTimeout(()=>map.invalidateSize(),120);
  if(mapScope==='mine'){
    const n=data.points.length, cities=(data.cities||[]);
    $('#pres').innerHTML=n?`${ic('pin','g')} <b>${n}</b> ${n===1?'light':'lights'} across <b>${data.places}</b> ${data.places===1?'place':'places'}`
      :`You haven’t lit anywhere yet — meditate with location on to begin your map.`;
    if(cities.length){$('#legend').innerHTML=`<div style="font-size:12px;color:var(--muted);margin-bottom:6px">Your places</div><div style="display:flex;gap:7px;flex-wrap:wrap">${cities.map(c=>`<span class="pill" style="font-size:11px">${ic('pin','g')} ${esc(c)}</span>`).join('')}</div>`;}
    else{$('#legend').innerHTML='';}
    // overlay + play control for the journey timelapse
    document.querySelectorAll('.jny-ui').forEach(x=>x.remove());
    const mapEl=$('#map');
    const ov=el(`<div class="jny-ov jny-ui" id="jov"></div>`);mapEl.appendChild(ov);
    if(n>=1){const btn=el(`<button class="jny-play jny-ui" id="jplay">${ic('play')} Play my journey</button>`);mapEl.appendChild(btn);
      btn.onclick=()=>playJourney(data.points.slice());}
    MARKERS=L.layerGroup().addTo(map);
    data.points.forEach(pt=>mapMarker(pt).addTo(MARKERS));
    if(n){const b=L.latLngBounds(data.points.map(p=>[p.lat,p.lon]));setTimeout(()=>map.fitBounds(b.pad(0.4),{maxZoom:6,duration:1.2,animate:true}),350);}
    return;
  }
  try{const p=await api('presence');$('#pres').innerHTML=`<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--purple);box-shadow:0 0 7px var(--purple);vertical-align:middle"></span> <b>${p.now}</b> meditating now · <b>${p.today_sessions}</b> sessions · <b>${fmt(p.today_light)}</b> light today`;}catch(e){}
  let recentM=null;
  data.points.forEach((pt,i)=>{const m=mapMarker(pt).addTo(map);if(i===0)recentM=m;});
  // auto-fly to + open the most recent meditator (points are ordered newest-first)
  if(recentM){const pt=data.points[0];
    setTimeout(()=>{map.flyTo([pt.lat,pt.lon],5,{duration:1.8});},400);
    setTimeout(()=>recentM.openPopup(),2300);}
}
const sleep=(ms)=>new Promise(r=>setTimeout(r,ms));
function journeyDot(pt,color){
  return L.marker([pt.lat,pt.lon],{icon:L.divIcon({className:'mkr-wrap',iconSize:[26,26],iconAnchor:[13,13],
    html:`<div class="mkr jny-drop" style="--c:${color}">${ic(pt.soundscape||'silence','mkri')}</div>`})});
}
async function playJourney(points){
  if(!map)return;
  const tok=++journeyTok;
  points.sort((a,b)=>new Date(a.ended)-new Date(b.ended)); // oldest → newest
  if(MARKERS){MARKERS.clearLayers();}else{MARKERS=L.layerGroup().addTo(map);}
  if(JPATH){map.removeLayer(JPATH);} JPATH=L.layerGroup().addTo(map);  // holds the fading trail segments
  const btn=$('#jplay'); if(btn){btn.innerHTML=`${ic('stop')} Stop`; btn.onclick=()=>stopJourney();}
  const ov=$('#jov'); if(ov)ov.classList.add('show');
  try{Sound.bell();Sound.start('space');}catch(e){}
  const total=points.length;
  const step=total>24?650:(total>10?850:1100);
  const line=[];
  for(let i=0;i<total;i++){
    if(TAB!=='map'){try{Sound.stop();}catch(e){}return;}  // left the map → stop music
    if(tok!==journeyTok)return;                           // superseded / stopped (new loop owns sound)
    const pt=points[i];
    map.flyTo([pt.lat,pt.lon], total>1?5:4, {duration:step/1000*0.9, animate:true});
    await sleep(Math.min(step*0.55,560));
    if(tok!==journeyTok)return;
    journeyDot(pt,'#f5c977').addTo(MARKERS);
    const here=[pt.lat,pt.lon];
    if(line.length){  // draw this leg as its own segment and fade it in
      const seg=L.polyline([line[line.length-1],here],{color:'#f5c977',weight:2,opacity:.72,className:'jny-seg'}).addTo(JPATH);
      const pe=seg.getElement?seg.getElement():seg._path;
      if(pe){pe.style.opacity='0';requestAnimationFrame(()=>{requestAnimationFrame(()=>{pe.style.opacity='1';});});}
    }
    line.push(here);
    if(ov)ov.innerHTML=`<div class="jny-count">${i+1}<span>/${total}</span></div>
      <div class="jny-meta"><b>${esc(pt.city)||'Somewhere'}</b><span>${new Date(pt.ended).toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'})} · ${pt.minutes} min</span></div>
      <div class="jny-bar"><i style="width:${Math.round(100*(i+1)/total)}%"></i></div>`;
    try{if(i%4===0)Sound.bell();}catch(e){}
    await sleep(step*0.6);
  }
  if(tok!==journeyTok)return;
  // 1) pull back to the whole world and let it breathe
  if(ov)ov.classList.remove('show');
  const pb=$('#jplay'); if(pb)pb.style.display='none';
  map.flyTo([18,0],2,{duration:2.4,animate:true});
  await sleep(3800);
  if(tok!==journeyTok||TAB!=='map')return;
  // 2) the congratulations finale
  showFinale(points);
}
function showFinale(points){
  const pts=points.slice().sort((a,b)=>new Date(a.ended)-new Date(b.ended));
  const sits=pts.length;
  const places=new Set(pts.map(p=>p.city||(p.lat+','+p.lon))).size;
  const mins=pts.reduce((s,p)=>s+(p.minutes||0),0);
  const hrs=mins/60, hoursStr=hrs>=1?(hrs>=10?Math.round(hrs):hrs.toFixed(1)):mins+'m';
  const first=new Date(pts[0].ended), last=new Date(pts[pts.length-1].ended);
  const span=first.toLocaleDateString(undefined,{month:'short',year:'numeric'})+' → '+last.toLocaleDateString(undefined,{month:'short',year:'numeric'});
  const months=Math.max(1,Math.round((last-first)/2592000000));
  const dur=months>=12?`${(months/12).toFixed(months%12<2?0:1)} year${months>=24?'s':''}`:`${months} month${months>1?'s':''}`;
  const sc={};pts.forEach(p=>sc[p.soundscape]=(sc[p.soundscape]||0)+1);
  const favSc=Object.keys(sc).sort((a,b)=>sc[b]-sc[a])[0]||'silence';
  const ci={};pts.forEach(p=>{if(p.city)ci[p.city]=(ci[p.city]||0)+1;});
  const homeCity=Object.keys(ci).sort((a,b)=>ci[b]-ci[a])[0]||'the world';
  const name=(ME&&ME.name)?ME.name.split(' ')[0]:'traveler';
  const spk=[...Array(14)].map(()=>`<span class="fspark" style="left:${Math.round(Math.random()*100)}%;animation-delay:${(Math.random()*3).toFixed(2)}s;animation-duration:${(3+Math.random()*3).toFixed(2)}s"></span>`).join('');
  const tiles=[[sits,'sits'],[places,places===1?'place':'places'],[hoursStr,'hrs of stillness']];
  const lines=[
    [ic('compass','g'),`${dur} of practice`,span],
    [ic(favSc,'g'),`Your sound was ${SS_LABEL[favSc]||favSc}`,`${sc[favSc]} of ${sits} sits`],
    [ic('pin','g'),`Most at home in ${esc(homeCity)}`,`${ci[homeCity]||1} sits here`],
  ];
  if(ME){lines.push([ic('spark','g'),`Level ${ME.level} · ${fmt(ME.light)} Light`,`best streak ${ME.best_streak||ME.streak||0} days`]);}
  const ov=el(`<div class="jny-finale"><div class="fspk">${spk}</div>
    <div class="finale-card">
      <div class="finale-mark">${lumenMark('lg')}</div>
      <div class="finale-sub">Your journey around the world</div>
      <h1 class="finale-h">Congratulations,<br>${esc(name)}</h1>
      <p class="finale-poem">You carried stillness to ${places} corners of the earth — one breath at a time.</p>
      <div class="finale-stats">${tiles.map(t=>`<div class="fstat"><div class="fsn">${t[0]}</div><div class="fsl">${t[1]}</div></div>`).join('')}</div>
      <div class="finale-lines">${lines.map(l=>`<div class="fline"><span class="fli">${l[0]}</span><div><b>${l[1]}</b><span>${l[2]}</span></div></div>`).join('')}</div>
      <button class="btn gold" id="fdone" style="margin-top:4px">Return to the map</button>
      <button class="btn ghost" id="freplay" style="margin-top:9px">${ic('play')} Replay the journey</button>
    </div></div>`);
  ov.querySelector('#fdone').onclick=()=>{try{Sound.stop();}catch(e){}ov.remove();renderMap();};
  ov.querySelector('#freplay').onclick=()=>{ov.remove();renderMap().then(()=>{setTimeout(()=>{const b=$('#jplay');if(b)b.click();},400);});};
  document.body.appendChild(ov);requestAnimationFrame(()=>ov.classList.add('show'));
}
function stopJourney(){
  journeyTok++;                 // cancels the running loop
  try{Sound.stop();}catch(e){}
  renderMap();                  // restore the normal "My places" view
}

/* ---- leagues & leaderboards ---- */
let lbScope='week',lbBy='light',leagueView='league';
async function renderLeagues(){
  $('#app').innerHTML=`<div class="brand"><span class="mark">${lumenMark('mark')}</span><b>Leagues</b></div>
    <div class="seg" id="lv"><button class="${leagueView==='league'?'on':''}" data-v="league">My league</button><button class="${leagueView==='global'?'on':''}" data-v="global">Global ranks</button></div>
    <div id="lbody"></div>`;
  $('#lv').querySelectorAll('button').forEach(b=>b.onclick=()=>{leagueView=b.dataset.v;renderLeagues();});
  if(leagueView==='league'){await renderLeagueView();}else{await renderGlobalView();}
}
async function renderLeagueView(){
  let d;try{d=await api('league');}catch(e){$('#lbody').innerHTML=`<div class="card muted">${e}</div>`;return;}
  const lg=d.league;const toNext=lg.next_at?Math.max(0,lg.next_at-d.weekly_light):0;
  const prog=lg.next_at?Math.min(100,100*(d.weekly_light-lg.at)/(lg.next_at-lg.at)):100;
  $('#lbody').innerHTML=`
  <div class="card center league-hero" style="border-color:${lg.color};--lc:${lg.color};--lc2:${lg.color2||lg.color}">
    <div class="league-emblem-wrap">${leagueEmblem(lg,128)}</div>
    <div class="muted" style="font-size:12px;letter-spacing:.1em;text-transform:uppercase">Current league</div>
    <h1 style="margin:6px 0;color:${lg.color}">${lg.name}</h1>
    <div class="muted">${fmt(d.weekly_light)} light this week</div>
    ${lg.next?`<div class="bar lg-bar" style="margin:14px 0 6px"><i style="width:${prog}%"></i></div><div class="muted" style="font-size:13px">${toNext} light to <b style="color:var(--text)">${leagueIcon(lg.next,'g')} ${lg.next}</b></div>`:`<div class="pill" style="margin-top:10px;border-color:var(--gold);color:var(--gold)">${ic('spark','g glow')} Top league — keep it lit</div>`}
  </div>
  <div class="card">
    <h3 style="margin:0 0 6px;display:flex;align-items:center;gap:7px">${leagueIcon(lg.name,'g')} ${lg.name} league · this week</h3>
    <p class="muted" style="font-size:12px;margin:0 0 8px">Top 5 promote ${ic('up','g')} · resets every week</p>
    ${d.members.map(m=>`<div class="lb-row ${m.you?'you':''}"><div class="rk ${m.rank<=5?'g':''}">${m.rank<=5?ic('up','g'):''}${m.rank}</div><div class="nm">${esc(m.name)}${m.you?' (you)':''}</div><div class="vl">${fmt(m.weekly_light)}</div></div>`).join('')||'<div class="muted">No one here yet.</div>'}
  </div>`;
}
async function renderGlobalView(){
  $('#lbody').innerHTML=`
  <div class="seg" id="sc" style="margin-bottom:8px"><button class="${lbScope==='today'?'on':''}" data-s="today">Today</button><button class="${lbScope==='week'?'on':''}" data-s="week">This week</button><button class="${lbScope==='all'?'on':''}" data-s="all">All time</button></div>
  <div class="seg" id="by"><button class="${lbBy==='light'?'on':''}" data-b="light">Light</button><button class="${lbBy==='minutes'?'on':''}" data-b="minutes">Minutes</button></div>
  <div class="card" id="rows"></div>`;
  $('#sc').querySelectorAll('button').forEach(b=>b.onclick=()=>{lbScope=b.dataset.s;renderGlobalView();});
  $('#by').querySelectorAll('button').forEach(b=>b.onclick=()=>{lbBy=b.dataset.b;renderGlobalView();});
  let d;try{d=await api(`leaderboard?scope=${lbScope}&by=${lbBy}`);}catch(e){return;}
  const unit=lbBy==='light'?'light':'min';
  const medal=['#f5c977','#cbd5e1','#d9915b'];
  $('#rows').innerHTML=d.rows.map(r=>`<div class="lb-row ${r.you?'you':''}"><div class="rk">${r.rank<=3?`<span style="color:${medal[r.rank-1]}">${ic('star','medal')}</span>`:r.rank}</div><div class="nm">${esc(r.name)}${r.you?' (you)':''}</div><div class="vl">${fmt(r.value)} <span class="muted" style="font-size:11px">${unit}</span></div></div>`).join('')||'<div class="muted">No sessions yet.</div>';
}

/* ---- journal ---- */
let journalView='mine';
const SEASON_PROMPTS=["What season of your life are you in right now — and what would you name it?","What is this chapter asking of you, and what is it quietly giving back?","What are you growing toward in this season? What are you ready to let fall away?","If you looked back on this time in five years, what would you want to remember about who you were?","What feels like it’s ending, and what feels like it’s just beginning?","Where are you being asked to be patient with yourself right now?"];
let speakOn=(typeof localStorage!=='undefined'&&localStorage.getItem('lumen_speak')==='0')?false:true;
// --- Lumen's voice: ElevenLabs ONLY, played through the shared Web Audio context.
// There is NO browser-speech fallback: if ElevenLabs is unavailable we stay silent
// (pacing by reading time) rather than use the robotic device voice. ---
let _ttsOn=true;               // flips off for the session only if the service is unreachable
const _ttsBufCache={};         // text -> ArrayBuffer (dedupes repeated lines, enables prefetch)
let _voiceHandle=null;
function ttsBuf(text){
  if(_ttsBufCache[text])return Promise.resolve(_ttsBufCache[text]);
  return fetch('api/tts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})})
    .then(r=>{if(!r.ok)throw 0;return r.arrayBuffer();})
    .then(b=>{if(!b||b.byteLength<256)throw 0;_ttsBufCache[text]=b;return b;});
}
let _ttsFails=0;               // consecutive ElevenLabs failures; reset on any success
function ttsPrefetch(text){if(_ttsOn&&_ttsFails<4&&text)ttsBuf(text).catch(()=>{});}
// narrate one line; calls done() when speech ends. ElevenLabs only — if it's
// unavailable we DON'T speak (no robot voice); we advance after the line's
// estimated reading time so guided flows still pace correctly.
function narrate(text,done,rate){
  const t=(text||'').replace(/[“”"]/g,'');
  let fired=false;const go=()=>{if(fired)return;fired=true;done&&done();};
  const silent=()=>{if(!fired)setTimeout(go, Math.max(800, estSay(t)*1000));};
  if(_ttsOn && _ttsFails<4){
    ttsBuf(t).then(buf=>{ _ttsFails=0; _voiceHandle=Sound.say(buf, go, silent); })
             .catch(()=>{ _ttsFails++; silent(); });
    return null;
  }
  silent();return null;
}
function stopNarration(){try{if(_voiceHandle&&_voiceHandle.stop)_voiceHandle.stop();_voiceHandle=null;}catch(e){}
  if(window.speechSynthesis){try{speechSynthesis.cancel();}catch(e){}}}
// rough spoken-duration estimate in seconds (calm pace ~2.4 words/sec)
function estSay(text){const w=(text||'').trim().split(/\s+/).filter(Boolean).length;return w/2.4+0.9;}
function splitSents(text){return (text||'').match(/[^.!?]+[.!?]+(?:\s|$)|[^.!?]+$/g)||[text];}
const JPROMPTS=[
  "What are you carrying today that isn't yours to hold?",
  "Where did you feel most alive this week — and what were you doing?",
  "What would you do today if you weren't afraid?",
  "What is one thing you can set down right now, even for an hour?",
  "Who deserves your gratitude today — and have you told them?",
  "What does your body need that your mind keeps overruling?",
  "What story are you telling yourself that may not be true?",
  "When did you last feel truly at peace? Take yourself back there.",
  "What small, ordinary thing brought you joy recently?",
  "What are you avoiding — and what's the fear underneath it?",
  "What would 'enough' look like for you today?",
  "What are you quietly ready to begin?",
  "Where are you rushing when you could be present?",
  "If you could sit with yourself as a child for five minutes, what would you want them to know?",
  "What did today ask of you — and how did you answer?",
  "What are you proud of this week that no one else saw?",
  "Who are you becoming, and did today move you toward them or away?",
  "What's one thing you'd forgive yourself for, if you let yourself?",
  "What felt heavy today, and where did you feel it in your body?",
  "What are you holding on to that was never really yours to fix?",
  "When did you feel most like yourself lately?",
  "What would change if you believed you were already enough?",
  "What's a kindness someone showed you that you've never fully acknowledged?",
  "What are you pretending not to know?",
  "What would make tomorrow feel 2% lighter?",
  "Where did you say yes today when you meant no?",
  "What's something you're grieving, even quietly, even small?",
  "What part of today do you want to remember a year from now?",
  "What are you learning the hard way right now?",
  "If this feeling could speak, what would it be trying to tell you?",
  "What do you need to hear tonight that no one has said to you?",
  "What's one small promise you can keep to yourself this week?"];
let jPrompt='';let rec=null;let listening=false;
const niceDate=(d)=>new Date(d).toLocaleDateString(undefined,{weekday:'long',month:'long',day:'numeric'});
// ---- journaling modes: Deep (pillar work) · Daily (letter) · Season (life-chapter) ----
let journalMode='daily';     // 'deep' | 'daily' | 'season'
let journalPillar=null;      // chosen pillar when in Deep mode
let journalChapter=null;     // specific chapter to open (1-based), else next
let jSeason='';              // optional "name this season" label
let jSeasonPrompt=null;      // current Season prompt
let jRec=null;               // today's recommended mode {mode,pillar,title,reason,why}
let jWeek=null;              // weekly category coverage {counts:{deep,daily,season}}
let jScreen='home';          // journal sub-screen: 'home' | 'compose' | 'pillars'
// Open the Daily composer with a given prompt (used from Life OS / meditate home links).
function openJournalDaily(p){if(p!=null)jPrompt=p;journalMode='daily';journalPillar=null;jScreen='compose';go('journal');}

const J_MODES=[['deep','Deep','jdeep'],['daily','Daily','jdaily'],['season','Season','season']];
const J_MODE_BLURB={deep:'Guided work on one of your eight life pillars.',daily:'A letter to yourself, about today.',season:'What chapter of life are you living through right now?'};

function jWeekRing(){
  const cts=(jWeek&&jWeek.counts)||{};
  const n=['deep','daily','season'].filter(k=>(cts[k]||0)>0).length;
  const dot=(k,lbl)=>{const on=(cts[k]||0)>0;return `<span class="jwk ${on?'on':''}">${on?ic('check','g'):'<i class="jwk-o"></i>'}${lbl}</span>`;};
  return `<div class="jweekbar"><div class="jwk-row">${dot('deep','Deep')}${dot('daily','Daily')}${dot('season','Season')}</div>`
    +`<span class="jwk-cap">${n>=3?'all three tended this week ✦':n+' of 3 this week'}</span></div>`;
}
// Journal hero — the three facets as glowing medallions, lit when tended this week.
const JFACETS=[['deep','Deep','jdeep','#a855f7','#c084fc'],['daily','Daily','jdaily','#38bdf8','#0ea5e9'],['season','Season','season','#f59e0b','#f97316']];
function jWeekHero(){
  const cts=(jWeek&&jWeek.counts)||{};
  const n=JFACETS.filter(f=>(cts[f[0]]||0)>0).length;
  const facet=([k,lbl,icn,c1,c2])=>{const on=(cts[k]||0)>0;
    return `<button class="jfacet${on?' lit':''}" data-m="${k}" style="--fc:${c1};--fc2:${c2}">`
      +`<span class="jfacet-med">${ic(icn)}${on?`<span class="jfacet-check">${ic('check')}</span>`:''}</span>`
      +`<span class="jfacet-lbl">${lbl}</span></button>`;};
  return `<div class="jhero"><div class="jhero-eyebrow">${ic('book')} Your journal</div>`
    +`<div class="jhero-facets">${JFACETS.map(facet).join('')}</div>`
    +`<div class="jhero-cap">${n>=3?'all three facets tended this week':n+' of 3 facets tended this week'}</div></div>`;
}

// Today's recommended journaling — one pick (Deep · Daily · Season) chosen by the
// server, shown as a gold hero card at the top of the journal. Tapping Begin jumps
// straight into that mode (and that pillar, for Deep). Wired in renderJournal.
const J_MODE_ICON={deep:'jdeep',daily:'jdaily',season:'season'};
function jRecCard(){
  if(!jRec||!jRec.mode)return '';
  const icn=J_MODE_ICON[jRec.mode]||'spark';
  return `<div class="jrec">`
    +`<div class="jrec-ico">${ic(icn,'g')}</div>`
    +`<div class="jrec-main">`
      +`<div class="jrec-kick">${ic('spark','g')} Recommended today</div>`
      +`<div class="jrec-title">${esc(jRec.title||'')}</div>`
      +`<div class="jrec-reason">${esc(jRec.reason||'')}</div>`
    +`</div>`
    +`<button class="jrec-btn" id="jrecbtn">Begin</button>`
  +`</div>`;
}

function composerHTML(o){
  return `<div class="letter">`
    +(o.topHTML||'')
    +`<div class="letter-head"><span>${niceDate(Date.now())}</span>`
    +`<button class="lp-speak ${speakOn?'on':''}" id="jspeak" title="Read this aloud">${ic(speakOn?'sound':'mute')}</button></div>`
    +`<div class="letter-prompt"><span class="lp-q">“${esc(o.prompt||'')}”</span>`
    +(o.shuffle?`<button class="lp-shuffle" id="jshuf" title="Another prompt">${ic('spark')} another prompt</button>`:'')
    +`</div>`
    +`<textarea id="jt" class="letter-body" rows="7" placeholder="${o.placeholder||'Dear me,&#10;&#10;Today I noticed…'}"></textarea>`
    +`<div id="jprev" class="letter-interim"></div>`
    +`<div class="letter-foot">`
    +`<button class="mic" id="jmic" title="Speak your letter"><span class="mic-ring"></span>${ic('mic')}</button>`
    +`<button class="mic" id="jcam" title="Photograph your handwriting">${ic('camera')}</button>`
    +`<input type="file" id="jfile" accept="image/*" capture="environment" style="display:none">`
    +`<label class="letter-share"><input type="checkbox" id="js"> <span>Share</span></label></div>`
    +`<div class="mic-hint" id="michint"></div>`
    +`<button class="btn gold letter-seal-btn" id="jsave">${ic('seal','seal-ic')} Seal &amp; keep</button></div>`;
}

// Speak a journal prompt through Lumen's ElevenLabs voice (narrate), not the
// on-device Web Speech voice, so the journal matches the rest of the app.
function sayPrompt(t){try{stopNarration();}catch(e){}if(t)narrate(t);}
// Full-page narration for a guided sitting — reads the Keeper's opening, the
// invitation, and every step, not just the prompt line.
function composeSpeech(ex){
  if(!ex)return '';
  const strip=(s)=>(s||'').replace(/[“”"]/g,'').trim();
  const parts=[];
  if(ex.title)parts.push(strip(ex.title)+'.');
  if(ex.opening)parts.push(strip(ex.opening));
  if(ex.invitation)parts.push(strip(ex.invitation));
  (ex.steps||[]).forEach((s,i)=>parts.push('Step '+(i+1)+'. '+strip(s)));
  return parts.filter(Boolean).join(' ');
}
function wireComposerCommon(getPrompt){
  $('#jspeak').onclick=()=>{speakOn=!speakOn;try{localStorage.setItem('lumen_speak',speakOn?'1':'0');}catch(e){}
    $('#jspeak').classList.toggle('on',speakOn);$('#jspeak').innerHTML=ic(speakOn?'sound':'mute');
    if(speakOn)sayPrompt(getPrompt());else{try{stopNarration();}catch(e){}}};
  if(speakOn){clearTimeout(window._spk);window._spk=setTimeout(()=>{if(TAB==='journal')sayPrompt(getPrompt());},1100);}
  $('#jmic').onclick=toggleVoice;
  $('#jcam').onclick=()=>$('#jfile').click();
  $('#jfile').onchange=(e)=>transcribePhoto(e.target.files&&e.target.files[0]);
}

function sealHandler(payload){
  return async()=>{
    if(listening&&rec)rec.stop();
    const t=$('#jt').value.trim();if(!t){toast('Write a few words first');return;}
    const ex=payload()||{};if(ex.error){toast(ex.error);return;}
    const words=(t.match(/\S+/g)||[]).length;const share=$('#js').checked;
    const btn=$('#jsave');const orig=btn.innerHTML;btn.disabled=true;btn.innerHTML=`<span class="spinner"></span> Sealing & reflecting…`;
    try{const r=await api('journal','POST',{text:t,prompt:ex.prompt||'',share,kind:ex.kind,pillar:ex.pillar||'',place:ex.place||''});
      $('#jt').value='';if(r&&r.week)jWeek={counts:r.week.counts};showJournalSealed(r,words,share);}catch(e){toast(e);}finally{btn.disabled=false;btn.innerHTML=orig;}
  };
}

function renderDailyCompose(){
  $('#jcompose').innerHTML=composerHTML({prompt:jPrompt,shuffle:true});
  wireComposerCommon(()=>jPrompt);
  $('#jshuf').onclick=()=>{let n;do{n=JPROMPTS[Math.floor(Math.random()*JPROMPTS.length)];}while(n===jPrompt&&JPROMPTS.length>1);jPrompt=n;$('.lp-q').textContent='“'+jPrompt+'”';if(speakOn)sayPrompt(jPrompt);};
  $('#jsave').onclick=sealHandler(()=>({kind:'daily',prompt:jPrompt}));
}

// Lesson-plan progress bar — a row of chapter dots + caption, used by Deep
// (per pillar) and Season. ex carries {chapter, chapters, chapter_titles, arc, looped}.
function planBar(ex){
  if(!ex||!ex.chapters)return '';
  const cur=ex.chapter||1, tot=ex.chapters;
  const dots=Array.from({length:tot},(_,i)=>`<i class="pb-dot${i+1<cur?' done':''}${i+1===cur?' on':''}"></i>`).join('');
  const arc=ex.arc?`<div class="pb-arc">${esc(ex.arc)}</div>`:'';
  const loop=ex.looped?' · revisiting':'';
  return `<div class="planbar">${arc}<div class="pb-row"><div class="pb-dots">${dots}</div>`
    +`<span class="pb-cap">Chapter ${cur} of ${tot}${loop}</span></div></div>`;
}

async function renderSeasonCompose(){
  $('#jcompose').innerHTML=`<div class="card center muted"><span class="spinner"></span> Opening the next chapter of your season…</div>`;
  let ex;try{ex=await api('journal/season');}catch(e){ex=null;}
  if(!ex||!ex.ready){
    // graceful fallback to a single reflective prompt
    if(!jSeasonPrompt)jSeasonPrompt=SEASON_PROMPTS[0];
    const top0=`<div class="jplace-wrap">${ic('sunrise','g')}<input id="jplace" class="jplace" maxlength="80" placeholder="Name this season (optional) — e.g. “rebuilding”" value="${esc(jSeason)}"></div>`;
    $('#jcompose').innerHTML=composerHTML({prompt:jSeasonPrompt,shuffle:true,topHTML:top0,placeholder:'The chapter I’m in, what it asks of me, what it gives…'});
    wireComposerCommon(()=>jSeasonPrompt);
    const pl0=$('#jplace');if(pl0)pl0.oninput=(e)=>{jSeason=e.target.value;};
    $('#jshuf').onclick=()=>{let n;do{n=SEASON_PROMPTS[Math.floor(Math.random()*SEASON_PROMPTS.length)];}while(n===jSeasonPrompt&&SEASON_PROMPTS.length>1);jSeasonPrompt=n;$('.lp-q').textContent='“'+jSeasonPrompt+'”';if(speakOn)sayPrompt(jSeasonPrompt);};
    $('#jsave').onclick=sealHandler(()=>{const place=(($('#jplace')||{}).value||'').trim();jSeason=place;return{kind:'season',place,prompt:jSeasonPrompt};});
    return;
  }
  jSeasonPrompt=ex.invitation||ex.title||'';
  const steps=(ex.steps||[]).map(s=>`<li>${esc(s)}</li>`).join('');
  const top=`<div class="deep-head season-head">`
    +`<div><div class="deep-pill">${ic('sunrise','g')} ${esc(ex.title||'Season')}</div>`
    +`<div class="deep-title">${esc(ex.invitation||'')}</div></div></div>`
    +planBar(ex,'season')
    +`<div class="jplace-wrap">${ic('sunrise','g')}<input id="jplace" class="jplace" maxlength="80" placeholder="Name this season (optional) — e.g. “rebuilding”" value="${esc(jSeason)}"></div>`
    +(ex.opening?`<div class="keeper-note"><div class="keeper-lbl">${ic('lumen','g')} The Keeper</div><p class="keeper-refl">“${esc(ex.opening)}”</p></div>`:'')
    +(steps?`<ol class="deep-steps">${steps}</ol>`:'');
  const prompt=ex.invitation||ex.title||'';
  $('#jcompose').innerHTML=composerHTML({prompt,shuffle:false,topHTML:top,placeholder:'The chapter I’m in, what it asks of me, what it gives…'});
  wireComposerCommon(()=>composeSpeech(ex));
  const pl=$('#jplace');if(pl)pl.oninput=(e)=>{jSeason=e.target.value;};
  $('#jsave').onclick=sealHandler(()=>{const place=(($('#jplace')||{}).value||'').trim();jSeason=place;return{kind:'season',place,prompt};});
}

async function renderDeepCompose(){
  if(!journalPillar){
    let pj;try{pj=await api('pillars');}catch(e){pj=null;}
    const focus=(pj&&pj.focus)||[];
    const names=(pj&&pj.pillars&&pj.pillars.map(p=>p.name))||Object.keys(PILLAR_META);
    $('#jcompose').innerHTML=`<div class="pillar-grid">`+names.map(name=>{
      const f=focus.includes(name);
      return `<button class="pcard${f?' focus':''}" data-p="${esc(name)}" style="--pc:${pcolor(name)}">`
        +`<span class="pico">${ic(picon(name),'grad-gold')}</span>`
        +`<span class="pname">${esc(name)}</span>`
        +`<span class="pdesc">${esc(pdesc(name))}</span>`
        +(f?`<span class="pfocus">focus</span>`:'')+`</button>`;}).join('')
      +`</div><div class="muted jgrid-hint">Pick a pillar for a short, guided sitting. The Keeper opens where you last left off.</div>`;
    document.querySelectorAll('.pcard').forEach(b=>b.onclick=()=>{journalPillar=b.dataset.p;jScreen='compose';renderJournal();});
    return;
  }
  $('#jcompose').innerHTML=`<div class="card center muted"><span class="spinner"></span> Opening your ${esc(journalPillar)} sitting…</div>`;
  const chq=journalChapter?('&chapter='+journalChapter):'';
  let ex;try{ex=await api('journal/deep?pillar='+encodeURIComponent(journalPillar)+chq);}catch(e){ex=null;}
  if(!ex||!ex.ready){$('#jcompose').innerHTML=`<div class="card center muted">Couldn’t open that pillar right now. <button class="lo-btn" id="pback">${ic('compass')} Back to pillars</button></div>`;const pb=$('#pback');if(pb)pb.onclick=()=>{journalChapter=null;jScreen='plessons';renderJournal();};return;}
  const steps=(ex.steps||[]).map(s=>`<li>${esc(s)}</li>`).join('');
  const top=`<div class="deep-head" style="--pc:${pcolor(journalPillar)}">`
    +`<button class="deep-back" id="pback" title="Back to chapters">${ic('compass')}</button>`
    +`<div><div class="deep-pill">${ic(picon(journalPillar),'g')} ${esc(journalPillar)}</div>`
    +`<div class="deep-title">${esc(ex.title||'')}</div></div></div>`
    +planBar(ex,journalPillar)
    +(ex.opening?`<div class="keeper-note"><div class="keeper-lbl">${ic('lumen','g')} The Keeper</div><p class="keeper-refl">“${esc(ex.opening)}”</p></div>`:'')
    +(steps?`<ol class="deep-steps">${steps}</ol>`:'');
  const prompt=ex.invitation||ex.title||journalPillar;
  $('#jcompose').innerHTML=composerHTML({prompt,shuffle:false,topHTML:top,placeholder:'Take it one step at a time…'});
  wireComposerCommon(()=>composeSpeech(ex));
  const pb=$('#pback');if(pb)pb.onclick=()=>{journalChapter=null;jScreen='plessons';renderJournal();};
  $('#jsave').onclick=sealHandler(()=>({kind:'deep',pillar:journalPillar,prompt}));
}

async function renderJournalBody(){
  const body=$('#jbody');
  if(journalView==='insights'){
    body.innerHTML=`<div class="card center muted"><span class="spinner"></span> The Keeper is reading your letters…</div>`;
    let di;try{di=await api('journal/insights');}catch(e){di=null;}
    if(!di||!di.ready){
      body.innerHTML=`<div class="card center muted"><div style="color:var(--gold);margin-bottom:6px">${lumenMark('lg')}</div>${(di&&di.reason==='few')?'Write a couple of letters and the Keeper will start noticing the throughline.':'Insights need the companion — try again in a moment.'}</div>`;
    }else{
      body.innerHTML=`<div class="insights">
        ${(di.themes&&di.themes.length)?`<div class="ins-themes">${di.themes.map(t=>`<span class="ins-chip">${esc(t)}</span>`).join('')}</div>`:''}
        ${di.arc?`<div class="ins-block"><div class="ins-lbl">Where you've been</div><div class="ins-arc">${esc(di.arc)}</div></div>`:''}
        ${di.observation?`<div class="ins-block keeper-note"><div class="keeper-lbl">${ic('lumen','g')} The Keeper notices</div><p class="keeper-refl">${esc(di.observation)}</p></div>`:''}
        ${di.nudge?`<div class="ins-block ins-nudge"><div class="ins-lbl">${ic('spark','g')} To sit with next</div><div class="ins-arc">${esc(di.nudge)}</div><button class="lo-btn" id="insWrite" style="margin-top:10px">${ic('book')} Write about this</button></div>`:''}
      </div>`;
      const iw=$('#insWrite');if(iw)iw.onclick=()=>{journalView='mine';openJournalDaily(di.nudge);};
    }
  }else if(journalView==='mine'){
    const d=await api('journal');
    body.innerHTML=d.entries.length?d.entries.map(e=>`<div class="letter mini"><div class="letter-head"><span>${niceDate(e.created)}</span>${e.shared?`<span class="letter-tag">${ic('globe')} shared</span>`:`<span class="letter-tag">${ic('lock')} private</span>`}</div>${e.prompt?`<div class="mini-q">“${esc(e.prompt)}”</div>`:''}<div class="mini-body">${esc(e.text)}</div>${e.mood?`<div class="mini-mood">— felt ${esc(e.mood)}</div>`:''}${e.reflection?`<div class="mini-refl">${ic('lumen','g')} ${esc(e.reflection)}</div>`:''}</div>`).join(''):`<div class="card center muted"><div style="color:var(--gold);margin-bottom:6px">${ic('book','lg')}</div>Your letters will gather here. Write your first above.</div>`;
  }else{
    const d=await api('feed');
    const mine=d.me;
    const mod=f=>(f.author_id&&f.author_id!==mine)?`<div class="mini-mod"><button class="mini-modbtn" data-report="${f.id}">${ic('flag')} Report</button><button class="mini-modbtn" data-block="${f.author_id}">Block</button></div>`:'';
    const card=f=>f.type==='spot'
      ? `<div class="letter mini spot-post"><img class="spot-img" src="${esc(f.photo)}" alt="meditation spot" onerror="this.remove()"><div class="spot-meta"><div class="letter-head"><span>${esc(f.name)||'Someone'}</span><span class="letter-tag">${niceDate(f.created)}</span></div><div class="spot-where">${ic('pin','g')} ${esc(f.city)||'Somewhere on Earth'} · ${f.minutes} min · ${SS_LABEL[f.soundscape]||esc(f.soundscape)}</div>${f.text?`<div class="mini-body">${esc(f.text)}</div>`:''}${f.mood?`<div class="mini-mood">— felt ${esc(f.mood)}</div>`:''}${mod(f)}</div></div>`
      : `<div class="letter mini"><div class="letter-head"><span>${esc(f.name)}</span><span class="letter-tag">${niceDate(f.created)}</span></div><div class="mini-body">${esc(f.text)}</div>${f.mood?`<div class="mini-mood">— felt ${esc(f.mood)}</div>`:''}${mod(f)}</div>`;
    body.innerHTML=d.feed.length?d.feed.map(card).join(''):'<div class="card center muted">Nothing shared yet. Meditate, snap your spot, and be the first.</div>';
    body.querySelectorAll('.mini-modbtn[data-report]').forEach(b=>b.onclick=async()=>{await api('feed/report','POST',{id:+b.dataset.report});toast('Reported — thank you. Hidden from your feed.');renderJournal();});
    body.querySelectorAll('.mini-modbtn[data-block]').forEach(b=>b.onclick=async()=>{await api('feed/block','POST',{author_id:+b.dataset.block});toast('Blocked. You will not see their entries.');renderJournal();});
  }
}

// First-run journal welcome: explain the three modes with the research behind
// each, then a pledge the writer signs before they begin. Shown once (localStorage).
function _journalPledged(){try{return localStorage.getItem('lumen_journal_pledged')==='1';}catch(e){return true;}}
function _jwCard(icn,title,desc,stat,cite){
  return `<div class="jwc"><div class="jwc-ico">${ic(icn,'g')}</div>`
    +`<div class="jwc-body"><div class="jwc-title">${title}</div>`
    +`<div class="jwc-desc">${desc}</div>`
    +`<div class="jwc-stat">${stat}</div>`
    +`<div class="jwc-cite">${cite}</div></div></div>`;
}
function renderJournalWelcome(){
  const nm=(ME&&ME.name)?esc(ME.name):'';
  $('#app').innerHTML=`<div class="brand"><span class="mark">${lumenMark('mark')}</span><b>Journal</b></div>`
  +`<div class="jwelc">`
    +`<div class="jwelc-hero"><div class="jwelc-halo">${ic('book','g')}</div>`
      +`<h2 class="jwelc-h">Three ways to meet yourself</h2>`
      +`<p class="jwelc-sub">Putting your inner life into words is one of the most studied tools we have for a steadier mind. Here’s how your journal works — and the research behind each part.</p></div>`
    +`<div class="jwelc-cards">`
      +_jwCard('jdaily','Daily','A short, honest letter to today.','Just 15 minutes, 3–4 times is enough — a meta-analysis of expressive-writing studies found a <b>0.47 effect-size</b> gain in well-being.','Smyth, 1998 · meta-analysis of 13 studies')
      +_jwCard('jdeep','Deep','Guided sittings on your eight life pillars — the things that matter most.','People who wrote each week about what they valued and were grateful for reported <b>~25% higher well-being</b>.','Emmons &amp; McCullough, 2003')
      +_jwCard('season','Season','Step back and name the chapter of life you’re living through right now.','Writing about your life’s larger arc and goals lifted mood and <b>cut illness-related doctor visits</b> months later.','King, 2001')
    +`</div>`
    +`<div class="jwelc-note">${ic('spark','g')} Expressive and reflective writing has 40+ years of evidence behind it (James Pennebaker and others): less stress and rumination, clearer thinking, even better sleep.</div>`
    +`<div class="jwelc-pledge">`
      +`<div class="jwelc-pl-h">${ic('seal','g')} My pledge</div>`
      +`<p class="jwelc-pl-body">“I promise to show up for myself on the page — a few honest lines, most days. Not for anyone else. For the quiet it gives back.”</p>`
      +`<input id="jpl-name" class="jwelc-sign" maxlength="48" placeholder="Sign your name" value="${nm}">`
      +`<button class="btn seal-cta jwelc-seal" id="jpl-sign">${ic('seal','seal-ic grad-gold')} Sign &amp; begin</button>`
      +`<button class="jwelc-skip" id="jpl-skip">Maybe later</button>`
    +`</div>`
  +`</div>`;
  const sign=()=>{const f=$('#jpl-name');const v=((f&&f.value)||'').trim();
    if(!v){if(f){f.focus();f.classList.add('miss');}toast('Sign your name to seal it');return;}
    try{localStorage.setItem('lumen_journal_pledged','1');localStorage.setItem('lumen_journal_pledge_name',v);localStorage.setItem('lumen_journal_pledge_date',new Date().toISOString());}catch(e){}
    toast('Sealed. Welcome to your journal ✦');renderJournal();};
  $('#jpl-sign').onclick=sign;
  $('#jpl-skip').onclick=()=>{try{localStorage.setItem('lumen_journal_pledged','1');}catch(e){}renderJournal();};
  const nf=$('#jpl-name');if(nf){nf.oninput=()=>nf.classList.remove('miss');nf.onkeydown=(e)=>{if(e.key==='Enter')sign();};}
}
async function renderJournal(){
  if(!_journalPledged()){renderJournalWelcome();return;}
  if(jScreen==='compose')return renderJournalCompose();
  if(jScreen==='plessons')return renderPillarLessons();
  if(jScreen==='pillars')return renderLifeOS();
  return renderJournalHome();
}

// Journal HOME — the three modes as full-width doors, then Life OS + pillars
// links, then the community feed. "Opening your journal into each of these prompts."
async function renderJournalHome(){
  try{jWeek=await api('journal/week');}catch(e){}
  try{jRec=await api('journal/recommend');}catch(e){jRec=null;}
  let pp=null;try{pp=await api('pillars');}catch(e){}
  listening=false;rec=null;
  const recMode=jRec&&jRec.mode;
  const DOORS=[['deep','Deep','jdeep'],['daily','Daily','jdaily'],['season','Season','season']];
  const JDOOR_COL={deep:['#a855f7','#c084fc'],daily:['#38bdf8','#0ea5e9'],season:['#f59e0b','#f97316']};
  const door=([k,lbl,icn])=>{const isRec=recMode===k;
    return `<button class="jbig${isRec?' rec':''}" data-m="${k}"><span class="jbig-ico">${ic(icn)}</span>`
      +`<span class="jbig-txt"><span class="jbig-t">${lbl}${isRec?`<span class="jbig-badge">Today</span>`:''}</span>`
      +`<span class="jbig-b">${J_MODE_BLURB[k]||''}</span></span><span class="jbig-go">›</span></button>`;};
  const pillars=(pp&&pp.pillars)||[];
  const chosenNames=(pp&&pp.focus)||[];
  const chosen=chosenNames.map(nm=>pillars.find(p=>p.name===nm)).filter(Boolean);
  const others=pillars.filter(p=>!chosenNames.includes(p.name));
  const caseItem=(p)=>`<button class="pcolumn" data-p="${esc(p.name)}" style="--pc:${pcolor(p.name)}">`
    +`<span class="pcolumn-glow"></span><span class="pcolumn-art" data-pc="#d8c6a0"></span>`
    +`<span class="pcolumn-base"></span><span class="pcolumn-nm">${esc(p.name)}</span></button>`;
  const otherCard=(p)=>`<button class="pgrid-card" data-p="${esc(p.name)}" style="--pc:${pcolor(p.name)}">`
    +`<span class="pgrid-med">${ic(picon(p.name))}</span><span class="pgrid-nm">${esc(p.name)}</span></button>`;
  const jung=[['The Shadow','Meet what you suppress','jg_shadow'],['The Persona','The mask you wear','jg_persona'],['Anima &amp; Animus','Your inner opposite','jg_anima'],['The Self','Wholeness &amp; integration','jg_self']];
  const jcard=(j,i)=>`<div class="jcard"><span class="jcard-top"><span class="jcard-med">${ic(j[2])}</span><span class="jcard-n">${i+1}</span></span><span class="jcard-t">${j[0]}</span><span class="jcard-d">${j[1]}</span><span class="jcard-lk">${ic('lock')}</span></div>`;
  $('#app').innerHTML=`<div class="brand"><span class="mark">${lumenMark('mark')}</span><b>Journal</b>`
    +`<button class="lo-btn" id="talkbtn" style="margin-left:auto">${ic('chat')} Talk</button></div>`
    +`<div class="jbigs">`+DOORS.map(door).join('')+`</div>`
    +`<div class="pcase"><div class="pcase-frame"></div>`
      +`<div class="pcase-eyebrow">${ic('seal')} Your focus pillars</div>`
      +`<div class="pcols">${chosen.length?chosen.map(caseItem).join(''):'<span class="pcase-empty">Tap Edit to set your focus pillars and fill the case.</span>'}</div></div>`
    +`<div class="pcase-editrow"><button class="pcase-edit" id="loedit">${ic('compass')} Edit focus pillars</button></div>`
    +(others.length?`<div class="pgrid-h">${ic('compass','g')} More pillars</div><div class="pgrid">${others.map(otherCard).join('')}</div>`:'')
    +`<div class="jpath"><div class="jpath-h"><span class="jpath-eyebrow">${ic('lock')} The Jungian Journal</span><span class="jpath-soon">Coming soon</span></div>`
      +`<p class="jpath-sub">A guided descent through the archetypes — meeting the shadow, the persona, the anima, and the Self.</p>`
      +`<div class="jgrid">${jung.map(jcard).join('')}</div></div>`
    +`<div class="jfeed-h">${ic('globe','g')} From the community</div>`
    +`<div id="jbody"></div>`;
  // The pillar to drop straight into when Deep is tapped: the server's deep
  // recommendation, else a focus pillar with the fewest sittings, else the least-
  // worked pillar overall. So "Deep" takes you right to the next suggested sitting.
  const nextDeepPillar=()=>{
    if(jRec&&jRec.mode==='deep'&&jRec.pillar)return jRec.pillar;
    const ps=(pp&&pp.pillars)||[];const focus=(pp&&pp.focus)||[];
    if(!ps.length)return focus[0]||null;
    const byLeast=(arr)=>arr.slice().sort((a,b)=>((a.sittings||0)-(b.sittings||0)))[0];
    const fps=ps.filter(p=>focus.includes(p.name));
    const pick=byLeast(fps.length?fps:ps);
    return pick?pick.name:null;
  };
  $('#talkbtn').onclick=renderChat;
  {const le=$('#loedit');if(le)le.onclick=(e)=>{e.stopPropagation();jScreen='pillars';renderJournal();};}
  const openMode=(k)=>{journalMode=k;journalPillar=null;if(k==='season')jSeason='';
    if(k==='deep'){const pil=nextDeepPillar();if(pil){journalPillar=pil;jScreen='compose';}else{jScreen='pillars';}}
    else{jScreen='compose';}
    renderJournal();};
  document.querySelectorAll('.jbig').forEach(b=>b.onclick=()=>openMode(b.dataset.m));
  document.querySelectorAll('.pcolumn,.pgrid-card').forEach(b=>b.onclick=()=>{journalMode='deep';journalPillar=b.dataset.p;journalChapter=null;jScreen='plessons';renderJournal();});
  _mountCols();
  journalView='feed';renderJournalBody();
}

// A single pillar's lesson plan — every chapter listed (like the Journeys view),
// with completed chapters sealed and the next one flagged. Tap any chapter to open
// that specific guided sitting.
async function renderPillarLessons(){
  const name=journalPillar;
  if(!name){jScreen='home';return renderJournal();}
  const back=()=>{journalPillar=null;journalChapter=null;jScreen='home';renderJournal();};
  $('#app').innerHTML=`<div class="brand"><button class="back-btn" id="plback" title="Back to journal">‹</button><span class="mark">${lumenMark('mark')}</span><b>${esc(name)}</b></div>`
    +`<div class="card center muted" style="font-size:13px"><span class="spinner"></span> Opening your ${esc(name)} plan…</div>`;
  $('#plback').onclick=back;
  let d;try{d=await api('pillar?name='+encodeURIComponent(name));}catch(e){d=null;}
  if(!d||!d.chapters||!d.chapters.length){
    $('#app').innerHTML=`<div class="brand"><button class="back-btn" id="plb" title="Back">‹</button><span class="mark">${lumenMark('mark')}</span><b>${esc(name)}</b></div>`
      +`<div class="card center muted">No lesson plan for this pillar yet.</div>`;
    $('#plb').onclick=back;return;}
  const total=d.total,done=Math.min(d.sittings||0,total),pct=total?Math.round(100*done/total):0;
  const row=(ch)=>`<button class="lj-row${ch.done?' done':''}${ch.next?' next':''}" data-n="${ch.n}" style="--a:${pcolor(name)}">`
    +`<span class="lj-num">${ch.done?ic('check'):ch.n}</span>`
    +`<span class="lj-main"><span class="lj-title">${esc(ch.title)}</span>`
      +`<span class="lj-sub">${esc(ch.invitation)} · ${ch.steps} prompt${ch.steps===1?'':'s'}</span></span>`
    +(ch.next?`<span class="lj-badge">Next up</span>`:`<span class="lj-go">${ic('play')}</span>`)+`</button>`;
  $('#app').innerHTML=`<div class="brand"><button class="back-btn" id="plback2" title="Back to journal">‹</button><span class="mark">${lumenMark('mark')}</span><b>${esc(name)}</b></div>`
    +`<div class="plz-head"><div class="plz-pill">${ic(picon(name),'g')} ${esc(name)} · guided sittings</div>`
      +(d.arc?`<p class="plz-arc">${esc(d.arc)}</p>`:'')
      +`<div class="pp-bar"><i style="width:${pct}%"></i></div>`
      +`<div class="plz-meta">${done} of ${total} chapters walked${d.rounds>0?' · looped '+d.rounds+'×':''}</div></div>`
    +`<div class="lj-list">`+d.chapters.map(row).join('')+`</div>`
    +`<p class="muted center" style="font-size:12px;margin:16px 0 4px">Each chapter is a short guided sitting. Tap to open it.</p>`;
  $('#plback2').onclick=back;
  document.querySelectorAll('.lj-row').forEach(b=>b.onclick=()=>{journalChapter=+b.dataset.n;journalMode='deep';jScreen='compose';renderJournal();});
}

// Pillars & progress — the eight life pillars, how far you've worked through them,
// focus pillars highlighted. Tap one to open its guided Deep sitting.
async function renderPillarsProgress(){
  let pp=null;try{pp=await api('pillars');}catch(e){}
  const pillars=(pp&&pp.pillars)||[];const focus=(pp&&pp.focus)||[];
  const done=(pp&&pp.done)||0;const total=(pp&&pp.total)||pillars.length||8;
  const pct=total?Math.round(100*done/total):0;
  const row=(p)=>{const f=focus.includes(p.name);const n=p.sittings||0;const isDone=n>0;
    return `<button class="pp-row" data-p="${esc(p.name)}" style="--pc:${pcolor(p.name)}">`
      +`<span class="pp-ico">${ic(picon(p.name),'grad-gold')}</span>`
      +`<span class="pp-main"><span class="pp-name">${esc(p.name)}${f?`<span class="pp-fchip">focus</span>`:''}</span>`
      +`<span class="pp-desc">${esc(p.title||pdesc(p.name))}</span></span>`
      +`<span class="pp-stat${isDone?' done':''}"><span class="pp-dot">${isDone?ic('check'):ic(picon(p.name))}</span>`
      +`<span class="pp-sn">${n?n+(n===1?' sitting':' sittings'):'start'}</span></span></button>`;};
  $('#app').innerHTML=`<div class="brand"><span class="mark">${lumenMark('mark')}</span><b>Pillars</b>`
    +`<button class="lo-btn" id="ppback" style="margin-left:auto">${ic('book')} Journal</button></div>`
    +`<div class="pp-top"><div class="pp-count">You've explored <b>${done}</b> of ${total} pillars</div>`
      +`<div class="pp-bar"><i style="width:${pct}%"></i></div></div>`
    +`<div class="pp-list">`+pillars.map(row).join('')+`</div>`
    +`<div class="muted jgrid-hint" style="margin-top:14px;text-align:center">Each pillar is a short, guided sitting. The Keeper opens where you last left off.</div>`;
  $('#ppback').onclick=()=>{jScreen='home';renderJournal();};
  document.querySelectorAll('.pp-row').forEach(b=>b.onclick=()=>{journalMode='deep';journalPillar=b.dataset.p;jScreen='compose';renderJournal();});
}

// Compose — one door's writing surface, with a back arrow and the writer's own
// letters / Keeper insights below.
async function renderJournalCompose(){
  if(journalMode==='deep'&&!journalPillar){jScreen='pillars';return renderJournal();}
  if(journalMode!=='deep'&&!jPrompt){
    try{jPrompt=(await api('lifeos/prompts')).prompts.reflection;}catch(e){}
    if(!jPrompt){try{jPrompt=(await api('prompt')).prompt;}catch(e){jPrompt=JPROMPTS[0];}}
  }
  listening=false;rec=null;
  const lbl={deep:'Deep',daily:'Daily',season:'Season'}[journalMode]||'Journal';
  const backTo=(journalMode==='deep')?'pillars':'home';
  $('#app').innerHTML=`<div class="brand"><button class="back-btn" id="jback" title="Back">‹</button><span class="mark">${lumenMark('mark')}</span><b>${lbl}</b>`
    +`<button class="lo-btn" id="jhome" style="margin-left:auto">${ic('book')} Journal</button></div>`
    +`<div class="jmode-blurb muted">${J_MODE_BLURB[journalMode]||''}</div>`
    +`<div id="jcompose"></div>`;
  $('#jback').onclick=()=>{jScreen=backTo;journalPillar=null;renderJournal();};
  $('#jhome').onclick=()=>{jScreen='home';journalPillar=null;renderJournal();};
  if(journalMode==='deep')renderDeepCompose();
  else if(journalMode==='season')renderSeasonCompose();
  else renderDailyCompose();
}
function updateMic(){const m=$('#jmic');if(!m)return;m.classList.toggle('live',listening);
  const h=$('#michint');if(h)h.textContent=listening?'Listening… speak softly, I’m writing it down.':'';
  if(!listening){const p=$('#jprev');if(p)p.textContent='';}}
function toggleVoice(){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){toast('Voice writing isn’t supported in this browser — try Chrome or Safari.');return;}
  if(listening&&rec){rec.stop();return;}
  rec=new SR();rec.lang='en-US';rec.continuous=true;rec.interimResults=true;
  const base=$('#jt').value.replace(/\s+$/,'');let finalText='';
  rec.onresult=(e)=>{let interim='';for(let i=e.resultIndex;i<e.results.length;i++){const t=e.results[i][0].transcript;if(e.results[i].isFinal)finalText+=t+' ';else interim+=t;}
    const t=$('#jt');t.value=(base?base+' ':'')+finalText+interim;t.scrollTop=t.scrollHeight;
    const p=$('#jprev');if(p)p.textContent=interim?'… '+interim:'';};
  rec.onend=()=>{listening=false;updateMic();};
  rec.onerror=(e)=>{listening=false;updateMic();if(e&&e.error==='not-allowed')toast('Microphone permission needed for voice writing.');};
  try{rec.start();listening=true;updateMic();}catch(e){listening=false;}
}
const esc=(s)=>(s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));

/* ---- photograph + transcribe handwriting ---- */
function downscaleImage(file,maxDim,q){return new Promise((res,rej)=>{
  const img=new Image();const url=URL.createObjectURL(file);
  img.onload=()=>{let w=img.width,h=img.height;const s=Math.min(1,maxDim/Math.max(w,h));
    const cv=document.createElement('canvas');cv.width=Math.max(1,Math.round(w*s));cv.height=Math.max(1,Math.round(h*s));
    cv.getContext('2d').drawImage(img,0,0,cv.width,cv.height);URL.revokeObjectURL(url);
    try{res(cv.toDataURL('image/jpeg',q));}catch(e){rej('Could not process image');}};
  img.onerror=()=>{URL.revokeObjectURL(url);rej('Could not read image');};
  img.src=url;});}
async function transcribePhoto(file){
  if(!file)return;
  const hint=$('#michint'),cam=$('#jcam');
  if(hint)hint.textContent='Reading your handwriting…';if(cam)cam.classList.add('live');
  try{
    const dataUrl=await downscaleImage(file,1600,0.82);
    const r=await api('journal/transcribe','POST',{image:dataUrl});
    const t=$('#jt'),add=(r.text||'').trim();
    if(add){t.value=(t.value.trim()?t.value.trim()+'\n\n':'')+add;t.scrollTop=t.scrollHeight;toast('Transcribed '+ic('spark','g'));}
    else toast('No text found in that photo');
  }catch(e){toast(e);}
  finally{if(hint)hint.textContent='';if(cam)cam.classList.remove('live');const f=$('#jfile');if(f)f.value='';}
}
/* ---- journal sealed celebration ---- */
function showJournalSealed(res,words,shared){
  if(window.speechSynthesis)speechSynthesis.cancel();
  const n=(res&&res.count)||1;
  const ach=((res&&res.new_achievements)||[]).map(a=>`<div class="pill" style="border-color:var(--gold);color:var(--gold)">${ic(ACH_ICON[a.code]||'book')} ${a.title}</div>`).join(' ');
  const spk=[...Array(10)].map(()=>`<span class="fspark" style="left:${Math.round(Math.random()*100)}%;animation-delay:${(Math.random()*3).toFixed(2)}s;animation-duration:${(3+Math.random()*2.5).toFixed(2)}s"></span>`).join('');
  const ov=el(`<div class="jny-finale seal-finale"><div class="fspk">${spk}</div>
    <div class="finale-card">
      <div class="seal-stamp">${ic('seal','grad-gold')}</div>
      <div class="finale-sub">Your letter is kept</div>
      <h1 class="finale-h" style="font-size:42px">Sealed</h1>
      <p class="finale-poem">What you named today, you no longer carry alone.</p>
      ${res&&res.reflection?`<div class="keeper-note"><div class="keeper-lbl">${ic('lumen','g')} The Keeper</div><p class="keeper-refl">“${esc(res.reflection)}”</p>${res.mood?`<div class="mini-mood">— you sounded ${esc(res.mood)}</div>`:''}</div>`:''}
      <div class="finale-stats">
        <div class="fstat"><div class="fsn">${words}</div><div class="fsl">words</div></div>
        <div class="fstat"><div class="fsn">${n}</div><div class="fsl">${n===1?'letter':'letters'}</div></div>
        <div class="fstat"><div class="fsn" style="font-size:19px">${shared?'Shared':'Private'}</div><div class="fsl">kept</div></div>
      </div>
      ${ach?`<div style="margin-bottom:16px"><div class="muted" style="font-size:12px">Achievement unlocked</div><div style="margin-top:8px;display:flex;gap:8px;justify-content:center;flex-wrap:wrap">${ach}</div></div>`:''}
      <button class="btn gold" id="sdone">Done</button>
    </div></div>`);
  const close=()=>{ov.remove();jScreen='home';renderJournal();};
  ov.querySelector('#sdone').onclick=close;
  ov.addEventListener('click',e=>{if(e.target===ov)close();});
  document.body.appendChild(ov);requestAnimationFrame(()=>ov.classList.add('show'));
}

/* ---- Life OS: cardinal pillars, daily focuses, AI prompts ---- */
let LO=null, LO_PILLARS=[];
const DIRS=[['N','North'],['E','East'],['S','South'],['W','West']];
const PILLAR_ICON={Family:'p_home',Relationships:'p_rel',Career:'p_career',Finances:'p_coin',Health:'p_health',Hobbies:'p_music','Inner Growth':'p_growth',Purpose:'p_purpose'};
const picon=(p)=>PILLAR_ICON[p]||'spark';
// the eight life pillars of Lumen's deep journaling
const PILLAR_META={
  Family:['#e0953a','Where you came from — and how you carry it.'],
  Relationships:['#f472b6','The people you choose and how you show up for them.'],
  Career:['#5fb0fa','The work you’re building, seriously.'],
  Finances:['#2dd4bf','Security, freedom, and your relationship with money.'],
  Health:['#34d399','Body, energy, and the basics that hold everything up.'],
  Hobbies:['#a78bfa','The things you do for the love of doing them.'],
  'Inner Growth':['#818cf8','Who you’re becoming.'],
  Purpose:['#c084fc','Meaning, values, and the bigger why.']};
// the opening invitation of each pillar's deep exercise (mirrors the server library)
const PILLAR_LESSON={
  Family:'Turn toward one family member as a whole person — their fears, their younger self — not just their role in your life.',
  Relationships:'Sit with one relationship on your heart, and write the thing you’ve been meaning to say.',
  Career:'Name the work you’d do even if no one paid or noticed. Where did today meet — or miss — it?',
  Finances:'Look plainly at what money means to you — safety, freedom, pressure, proof — and where that belief came from.',
  Health:'Check in with your body like a friend. What has it been asking for that your mind keeps overruling?',
  Hobbies:'Describe the last time something you love made you lose track of time. What did that flow give you?',
  'Inner Growth':'Write about who you were a year ago. What would that version of you thank you for?',
  Purpose:'Reach past the daily: when did you last feel part of something larger than yourself?'};
const pcolor=(p)=>(PILLAR_META[p]||['#a855f7'])[0];
const pdesc=(p)=>(PILLAR_META[p]||['','A pillar of your life.'])[1];
const plesson=(p)=>PILLAR_LESSON[p]||'';
async function renderLifeOS(){
  if(window.speechSynthesis)speechSynthesis.cancel();
  let d;try{d=await api('lifeos');LO=d.lifeos;LO_PILLARS=d.pillars;}catch(e){toast(e);return;}
  LO.pillars=LO.pillars||{};LO.focus=LO.focus||[];
  const chosen=DIRS.map(([k])=>LO.pillars[k]).filter(Boolean);
  $('#app').innerHTML=`<div class="brand"><button class="back-btn" id="loback" title="Back to journal">‹</button><span class="mark">${lumenMark('mark')}</span><b>Pillars</b></div>
  <p class="muted" style="font-size:13px;margin:0 0 10px">Your base at the center, four pillars at the cardinal directions. Choose two to focus on day to day.</p>
  <div class="compass2" id="compass">
    <svg class="crays" viewBox="0 0 300 300" aria-hidden="true">
      <circle cx="150" cy="150" r="116" fill="none" stroke="#2e2747" stroke-width="1"/>
      <circle cx="150" cy="150" r="78" fill="none" stroke="#221c38" stroke-width="1"/>
      <line class="cray" data-k="N" x1="150" y1="150" x2="150" y2="46"/>
      <line class="cray" data-k="E" x1="150" y1="150" x2="254" y2="150"/>
      <line class="cray" data-k="S" x1="150" y1="150" x2="150" y2="254"/>
      <line class="cray" data-k="W" x1="150" y1="150" x2="46" y2="150"/>
    </svg>
    <div class="cbase2"><input id="lobase" value="${esc(LO.base||'')}" placeholder="base" maxlength="40"><span>your base</span></div>
    <div class="cnode cN" data-d="N"></div>
    <div class="cnode cE" data-d="E"></div>
    <div class="cnode cS" data-d="S"></div>
    <div class="cnode cW" data-d="W"></div>
  </div>
  <div class="card">
    <div class="muted" style="font-size:12px;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px">Daily focus — pick two</div>
    <div id="lofocus" class="lo-focus"></div>
  </div>
  <button class="btn gold" id="losave">Save my Life OS</button>
  <div id="ppsection" style="margin-top:20px"></div>`;
  $('#loback').onclick=()=>{jScreen='home';renderJournal();};
  // render the four compass nodes + rays
  function paintDirs(){DIRS.forEach(([k,label])=>{const node=$('.cnode.c'+k);if(!node)return;const p=LO.pillars[k];
    const focus=p&&LO.focus.includes(p);
    node.className='cnode c'+k+(p?' set':'')+(focus?' focus':'');
    node.innerHTML=`<div class="cbadge">${p?ic(picon(p),'pico grad-gold'):'<span class="cadd">+</span>'}</div>
      <div class="clabel">${p?esc(p):label}</div>`;
    const ray=document.querySelector('.cray[data-k="'+k+'"]');if(ray)ray.classList.toggle('set',!!p);});}
  paintDirs();
  document.querySelectorAll('.cnode').forEach(node=>node.onclick=()=>pickPillar(node.dataset.d,paintDirs,paintFocus));
  function paintFocus(){const ch=DIRS.map(([k])=>LO.pillars[k]).filter(Boolean);
    const box=$('#lofocus');
    box.innerHTML=ch.length?ch.map(p=>`<button class="fchip ${LO.focus.includes(p)?'on':''}" data-p="${esc(p)}">${ic(LO.focus.includes(p)?'check':picon(p))} ${esc(p)}</button>`).join(''):'<span class="muted" style="font-size:13px">Assign pillars above first.</span>';
    box.querySelectorAll('.fchip').forEach(b=>b.onclick=()=>{const p=b.dataset.p;
      if(LO.focus.includes(p))LO.focus=LO.focus.filter(x=>x!==p);
      else{if(LO.focus.length>=2){toast('Two focuses is the sweet spot — tap one to swap');return;}LO.focus.push(p);}
      paintFocus();});}
  paintFocus();
  $('#losave').onclick=async()=>{LO.base=$('#lobase').value.trim();
    try{await api('lifeos','POST',{base:LO.base,pillars:LO.pillars,focus:LO.focus});toast('Life OS saved '+ic('spark','g'));}catch(e){toast(e);}};
  renderPillarsSection();
}

// The pillars-&-progress list, merged into the Pillars screen below the compass.
// Each of the eight pillars shows how far you've worked its lesson plan; tap one
// to open its next guided chapter.
async function renderPillarsSection(){
  const box=$('#ppsection');if(!box)return;
  box.innerHTML=`<div class="card muted center" style="font-size:13px"><span class="spinner"></span> Loading your pillars…</div>`;
  let pp=null;try{pp=await api('pillars');}catch(e){box.innerHTML='';return;}
  const pillars=(pp&&pp.pillars)||[];
  // the pillars assigned to the compass are the "focus" pillars shown in the display case
  const chosenNames=(typeof LO!=='undefined'&&LO&&LO.pillars)?DIRS.map(([k])=>LO.pillars[k]).filter(Boolean):((pp&&pp.focus)||[]);
  const chosen=chosenNames.map(nm=>pillars.find(p=>p.name===nm)).filter(Boolean);
  const others=pillars.filter(p=>!chosenNames.includes(p.name));
  const caseItem=(p)=>`<button class="pcolumn" data-p="${esc(p.name)}" style="--pc:${pcolor(p.name)}">`
    +`<span class="pcolumn-glow"></span>`
    +`<span class="pcolumn-art" data-pc="#d8c6a0"></span>`
    +`<span class="pcolumn-base"></span>`
    +`<span class="pcolumn-nm">${esc(p.name)}</span></button>`;
  const otherCard=(p)=>`<button class="pgrid-card" data-p="${esc(p.name)}" style="--pc:${pcolor(p.name)}">`
    +`<span class="pgrid-med">${ic(picon(p.name))}</span><span class="pgrid-nm">${esc(p.name)}</span></button>`;
  const jung=[['The Shadow','Meet what you suppress'],['The Persona','The mask you wear'],['Anima &amp; Animus','Your inner opposite'],['The Self','Wholeness &amp; integration']];
  box.innerHTML=
    `<div class="pcase">`
      +`<div class="pcase-frame"></div>`
      +`<div class="pcase-eyebrow">${ic('seal')} Your focus pillars</div>`
      +`<div class="pcols">${chosen.length?chosen.map(caseItem).join(''):'<span class="pcase-empty">Assign pillars on the compass above to fill your case.</span>'}</div>`
    +`</div>`
    +(others.length?`<div class="pgrid-h">${ic('compass','g')} More pillars</div><div class="pgrid">${others.map(otherCard).join('')}</div>`:'')
    +`<div class="jpath">`
      +`<div class="jpath-h"><span class="jpath-eyebrow">${ic('lock')} The Jungian Journal</span><span class="jpath-soon">Coming soon</span></div>`
      +`<p class="jpath-sub">A guided descent through the archetypes — meeting the shadow, the persona, the anima, and the Self.</p>`
      +`<div class="jpath-rows">${jung.map(j=>`<div class="jpath-row"><span class="jpath-ico">${ic('lock')}</span><span class="jpath-main"><span class="jpath-t">${j[0]}</span><span class="jpath-d">${j[1]}</span></span><span class="jpath-lock">Locked</span></div>`).join('')}</div>`
    +`</div>`;
  box.querySelectorAll('.pcolumn,.pgrid-card').forEach(b=>b.onclick=()=>{journalMode='deep';journalPillar=b.dataset.p;jScreen='compose';renderJournal();});
  _mountCols();
}
function pickPillar(dir,paintDirs,paintFocus){openPillarCard(dir,paintDirs,paintFocus);}
function openPillarCard(dir,paintDirs,paintFocus){
  const dirName=DIRS.find(x=>x[0]===dir)[1];
  const p=LO.pillars[dir];
  const assign=(name)=>{for(const [k] of DIRS){if(LO.pillars[k]===name&&k!==dir)LO.pillars[k]=null;}
    LO.pillars[dir]=name;LO.focus=LO.focus.filter(f=>DIRS.some(([k])=>LO.pillars[k]===f));paintDirs();paintFocus();};
  const clear=()=>{LO.pillars[dir]=null;LO.focus=LO.focus.filter(f=>DIRS.some(([k])=>LO.pillars[k]===f));paintDirs();paintFocus();};
  let ov;
  function chooser(){
    const used=DIRS.map(([k])=>LO.pillars[k]);
    ov.querySelector('.ach-card').innerHTML=`
      <button class="ach-x">${ic('close')}</button><div class="ach-foil"></div>
      <div class="ach-rare" style="color:var(--purple);border-color:var(--purple)">${dirName} pillar</div>
      <div class="ach-title" style="font-size:22px;margin-top:4px">Choose a pillar</div>
      <div class="ach-desc" style="font-family:var(--serif);font-style:italic">What matters most, to the ${dirName.toLowerCase()}?</div>
      <div class="lo-pick" style="margin-top:6px">${LO_PILLARS.map(x=>`<button class="pchip ${used.includes(x)?'used':''}" data-p="${esc(x)}" style="--pc:${pcolor(x)}">${ic(picon(x))} ${esc(x)}</button>`).join('')}</div>`;
    wire();
    ov.querySelector('.ach-card').style.setProperty('--rc','#7c3aed');
    ov.querySelectorAll('.pchip').forEach(b=>b.onclick=()=>{assign(b.dataset.p);ov.remove();});
  }
  function detail(){
    const col=pcolor(p);const isFocus=LO.focus.includes(p);
    ov.querySelector('.ach-card').style.setProperty('--rc',col);
    ov.querySelector('.ach-card').innerHTML=`
      <button class="ach-x">${ic('close')}</button><div class="ach-foil"></div>
      <div class="ach-rare" style="color:${col};border-color:${col}">${dirName} pillar</div>
      <div class="ach-badge"><div class="ach-ring"></div><div class="ach-ic" style="color:${col};filter:drop-shadow(0 0 10px ${col})">${ic(picon(p),'achbig')}</div></div>
      <div class="ach-title">${esc(p)}</div>
      <div class="ach-desc" style="font-family:var(--serif);font-style:italic">${esc(pdesc(p))}</div>
      <div class="lo-lesson" style="--c:${col}">
        <div class="lo-lesson-h">${ic('book')} Writing lesson</div>
        <div class="lo-lesson-b">${esc(plesson(p))}</div>
        <button class="btn gold" id="plearn" style="width:auto;padding:9px 16px;margin-top:10px">${ic('book')} Write this</button>
      </div>
      <div class="ach-meta" style="margin-top:4px">
        <span class="ach-chip">${isFocus?ic('check','g')+' A daily focus':'Tap it on the compass to make it a daily focus'}</span>
      </div>
      <div style="display:flex;gap:8px;justify-content:center;margin-top:4px">
        <button class="btn" id="pchange" style="width:auto;padding:10px 16px">Replace</button>
        <button class="btn ghost" id="premove" style="width:auto;padding:10px 16px;border-color:#5a2e3e;color:#fda4af">Remove</button>
      </div>`;
    wire();
    ov.querySelector('#plearn').onclick=()=>{ov.remove();openJournalDaily(plesson(p));};
    ov.querySelector('#pchange').onclick=()=>chooser();
    ov.querySelector('#premove').onclick=()=>{clear();chooser();};
  }
  function wire(){ov.querySelector('.ach-x').onclick=()=>ov.remove();}
  ov=el(`<div class="ach-ov"><div class="ach-card" style="--rc:#7c3aed;--tint:#16122a;--glow:rgba(124,58,237,.25)"></div></div>`);
  ov.addEventListener('click',e=>{if(e.target===ov)ov.remove();});
  (p?detail:chooser)();
  document.body.appendChild(ov);requestAnimationFrame(()=>ov.classList.add('show'));
}
async function loadLoPrompts(regen){
  const box=$('#loprompts');if(!box)return;
  box.innerHTML=`<div class="card muted center" style="font-size:13px">${ic('spark','g glow')} ${regen?'Writing your prompts…':'Loading today’s prompts…'}</div>`;
  let p;try{p=(await api('lifeos/prompts')).prompts;}catch(e){box.innerHTML='';return;}
  const rows=[['focus','Your focus','compass'],['reflection','Daily reflection','lotus'],['gratitude','Gratitude','spark']];
  box.innerHTML=`<div class="muted" style="font-size:12px;text-transform:uppercase;letter-spacing:.1em;margin:14px 0 8px">Today’s Light ${p.ai?'· AI':''}</div>`+
    rows.map(([k,label,icn])=>`<div class="lo-prompt" data-p="${esc(p[k])}" title="Write about this in your journal"><div class="lo-pico">${ic(icn,'g')}</div>
      <div style="flex:1"><div class="muted" style="font-size:11px;text-transform:uppercase;letter-spacing:.06em">${label}</div>
      <div style="font-family:var(--serif);font-size:15.5px;margin-top:2px">${esc(p[k])}</div></div>
      <span class="lo-write">${ic('book')}</span></div>`).join('')+
    `<p class="muted center" style="font-size:12px;margin-top:10px">Tap a prompt to carry it into your journal.</p>`;
  box.querySelectorAll('.lo-prompt').forEach(row=>row.onclick=()=>{openJournalDaily(row.dataset.p);});
}

/* ---- the Keeper: voice/text chat with tools ---- */
let chatMsgs=[];let chatRec=null;let chatListening=false;let chatBusy=false;
function renderChat(){
  if(window.speechSynthesis)speechSynthesis.cancel();
  if(!chatMsgs.length)chatMsgs=[{role:'model',text:`Hello${ME&&ME.name?', '+ME.name.split(' ')[0]:''}. I'm the Keeper. Talk to me about your day, ask about your practice, or say "write this down" and I'll keep it for you.`}];
  $('#app').innerHTML=`<div class="brand"><span class="mark">${lumenMark('mark')}</span><b>The Keeper</b>
    <button class="lp-speak ${speakOn?'on':''}" id="cspeak" title="Read replies aloud" style="margin-left:auto">${ic(speakOn?'sound':'mute')}</button>
    <button class="lo-btn" id="cback" style="margin-left:8px">${ic('book')} Journal</button></div>
  <div id="chatbox" class="chatbox"></div>
  <div class="chat-input">
    <button class="mic" id="cmic" title="Speak"><span class="mic-ring"></span>${ic('mic')}</button>
    <input id="cfield" placeholder="Talk to the Keeper…" autocomplete="off">
    <button class="csend" id="csend">${ic('send')}</button>
  </div>`;
  $('#cback').onclick=()=>renderJournal();
  $('#cspeak').onclick=()=>{speakOn=!speakOn;try{localStorage.setItem('lumen_speak',speakOn?'1':'0');}catch(e){}
    $('#cspeak').classList.toggle('on',speakOn);$('#cspeak').innerHTML=ic(speakOn?'sound':'mute');if(!speakOn){try{stopNarration();}catch(e){}}};
  $('#csend').onclick=()=>sendChat();
  $('#cfield').addEventListener('keydown',e=>{if(e.key==='Enter')sendChat();});
  $('#cmic').onclick=chatVoice;
  paintChat(false);
}
function paintChat(scroll){const box=$('#chatbox');if(!box)return;
  box.innerHTML=chatMsgs.map(m=>m.role==='model'
    ? `<div class="msg k"><span class="msg-ic">${ic('lumen')}</span><div class="bub">${esc(m.text)}</div></div>`
    : `<div class="msg u"><div class="bub">${esc(m.text)}</div></div>`).join('')
    +(chatBusy?`<div class="msg k"><span class="msg-ic">${ic('lumen')}</span><div class="bub typing"><i></i><i></i><i></i></div></div>`:'');
  box.scrollTop=box.scrollHeight;
}
async function sendChat(text){
  const field=$('#cfield');const t=(text!=null?text:(field?field.value:'')).trim();
  if(!t||chatBusy)return;
  if(field)field.value='';
  chatMsgs.push({role:'user',text:t});chatBusy=true;paintChat(true);
  try{const r=await api('chat','POST',{messages:chatMsgs.map(m=>({role:m.role,text:m.text}))});
    chatBusy=false;const reply=r.reply||'…';chatMsgs.push({role:'model',text:reply});paintChat(true);
    if(speakOn){try{stopNarration();}catch(e){}narrate(reply);}
    if((r.tools||[]).some(x=>['write_journal','set_lifeos_pillar','set_focus'].includes(x))){try{const me=await api('me');ME=me.profile;}catch(e){}}
  }catch(e){chatBusy=false;chatMsgs.push({role:'model',text:'I lost that thread for a moment — try again?'});paintChat(true);}
}
function chatVoice(){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){toast('Voice isn’t supported in this browser');return;}
  if(chatListening&&chatRec){chatRec.stop();return;}
  chatRec=new SR();chatRec.lang='en-US';chatRec.interimResults=true;chatRec.continuous=false;
  let fin='';
  chatRec.onresult=(e)=>{fin='';let interim='';for(let i=0;i<e.results.length;i++){const t=e.results[i][0].transcript;if(e.results[i].isFinal)fin+=t;else interim+=t;}
    const f=$('#cfield');if(f)f.value=(fin+interim).trim();};
  chatRec.onend=()=>{chatListening=false;const b=$('#cmic');if(b)b.classList.remove('live');
    const f=$('#cfield');if(f&&f.value.trim())sendChat();};
  chatRec.onerror=()=>{chatListening=false;const b=$('#cmic');if(b)b.classList.remove('live');};
  try{chatRec.start();chatListening=true;$('#cmic').classList.add('live');}catch(e){chatListening=false;}
}

/* ---- profile ---- */
const NCATS=[['reminder','Daily reminder to sit'],['streak','Streak saves'],['progress','Milestones & celebrations'],['journal','Journal rhythm (deep · daily · season)'],['community','Community activity'],['discovery','New places to explore'],['winback','We-miss-you nudges']];
function hoursOpts(sel){let h='';for(let i=0;i<24;i++){const lbl=(i===0?'12 AM':i<12?i+' AM':i===12?'12 PM':(i-12)+' PM');h+=`<option value="${i}" ${i===sel?'selected':''}>${lbl}</option>`;}return h;}
async function renderProfile(){
  const r=await api('me');ME=r.profile;const p=ME;
  const prog=Math.min(100,100*p.level_into/(p.level_into+p.level_need));
  let ach={achievements:[]};try{ach=await api('achievements');}catch(e){}
  let horo=null;try{horo=await api('horoscope?tz='+(-new Date().getTimezoneOffset()));}catch(e){}
  let np=null;try{np=await api('notif/prefs');}catch(e){}
  const starLine = (horo&&!horo.need_sign)
    ? `<p class="muted" style="font-size:13px;margin:0 0 12px;line-height:1.6"><span class="zsym">${horo.glyph}︎</span> <b style="color:var(--text)">${esc(horo.sanskrit||'')}</b> ${esc(horo.name||'')} · lord ${esc(horo.lord||'')}${horo.janma?`<br>${ic('nova','g')} Birth star <b style="color:var(--text)">${esc(horo.janma)}</b> · daśā ${esc(horo.maha)}–${esc(horo.antar)}`:`<br><span style="opacity:.8">Add your birth time below to unlock your birth star &amp; daśā.</span>`}</p>`
    : `<p class="muted" style="font-size:13px;margin:0 0 12px">Add your birthday to receive your daily Vedic reading.</p>`;
  $('#app').innerHTML=`<div class="brand"><span class="mark">${lumenMark('mark')}</span><b>${esc(p.name)}</b></div>
  <div class="card">
    <div class="row" style="align-items:center"><div><div class="muted" style="font-size:12px">LEVEL</div><div style="font-size:40px;font-weight:800">${p.level}</div></div>
    <div style="text-align:right"><div class="pill" style="border-color:${p.league.color};color:${p.league.color}">${p.league.name} league</div></div></div>
    <div class="bar" style="margin:10px 0 6px"><i style="width:${prog}%"></i></div>
    <div class="muted" style="font-size:12px">${p.level_into} / ${p.level_into+p.level_need} light to level ${p.level+1}</div>
  </div>
  <div class="card"><div class="grid3">
    <div class="stat"><div class="n">${fmt(p.light)}</div><div class="l">Light</div></div>
    <div class="stat"><div class="n">${p.streak}</div><div class="l">Streak</div></div>
    <div class="stat"><div class="n">${p.total_sessions}</div><div class="l">Sessions</div></div>
    <div class="stat"><div class="n">${p.total_minutes}</div><div class="l">Minutes</div></div>
    <div class="stat"><div class="n">${p.best_streak}</div><div class="l">Best streak</div></div>
    <div class="stat"><div class="n">${fmt(p.weekly_light)}</div><div class="l">This week</div></div>
  </div></div>
  ${(p.tier!=='premium')?`<div class="card" id="procard" style="border:1px solid #4a3a1e;background:linear-gradient(160deg,#1c1507,#14111f)">
    <div class="row" style="align-items:center;gap:12px">
      <span style="flex:0 0 auto">${lumenMark('pro')}</span>
      <div style="flex:1">
        <div class="pill" style="border-color:#f5c977;color:#f5c977;font-size:11px">LUMEN PREMIUM</div>
        <h3 style="margin:8px 0 2px;color:#f6f1ea">Go deeper with Premium</h3>
        <p class="muted" style="font-size:13px;margin:0;line-height:1.55">The full library of journeys, deeper Vedic readings, and more ways to grow your mandala — <b style="color:#f5c977">coming soon</b>.</p>
      </div>
    </div>
    <button class="btn" id="pro" style="margin-top:12px;background:linear-gradient(135deg,#f5c977,#e0953a);color:#2a1a05;font-weight:700;border:0">${ic('spark')} Get founding-member access</button>
    <p class="muted" id="prostate" style="font-size:12px;text-align:center;margin:8px 0 0">First access + a founding price when it opens. No charge yet.</p>
  </div>`:''}
  <div class="card">
    <h3 style="margin:0 0 2px">Achievements</h3>
    <p class="muted" style="font-size:12px;margin:0 0 10px">Tap a badge to open its card</p>
    ${ach.achievements.map(a=>{const r=RARITY[rarityOf(a.code)];return `<div class="ach ${a.unlocked?'on':''}" data-ac="${a.code}"><div class="e">${ic(a.unlocked?(ACH_ICON[a.code]||'star'):'lock')}</div><div style="flex:1"><b>${a.title}</b><div class="muted" style="font-size:13px">${a.unlocked?a.desc:'Locked'}</div></div><span class="rtag" style="--c:${r[1]}">${r[0]}</span></div>`;}).join('')}
  </div>
  <div class="card">
    <h3 style="margin:0 0 6px">Home location</h3>
    <p class="muted" style="font-size:13px;margin:0 0 10px" id="locstate">${p.city?(ic('pin')+' '+esc(p.city)):'Not set — your sessions aren’t shown on the map until you set this.'}</p>
    <button class="btn ghost" id="loc">${ic('pin')} Use my current location</button>
    <p class="muted" id="lochelp" style="font-size:12px;margin:10px 0 0;display:none"></p>
  </div>
  <div class="card">
    <h3 style="margin:0 0 6px">Your stars ${ic('nova','g')}</h3>
    ${starLine}
    <label>Birthday</label><input id="pbd" type="date" value="${esc(p.birth_date||'')}">
    <label>Birth time <span class="muted" style="font-weight:400">(optional — for your birth star &amp; daśā)</span></label>
    <div style="display:flex;gap:8px"><input id="pbt" type="time" value="${esc(p.birth_time||'')}" style="flex:0 0 42%"><input id="pbp" placeholder="City of birth" value="${esc(p.birth_place||'')}" style="flex:1"></div>
    <button class="btn ghost" id="psave" style="margin-top:10px">Save birth details</button>
  </div>
  ${np?`<div class="card">
    <div class="nrow" style="border-top:0;padding-top:0">
      <div><b>Push notifications</b><div class="muted" style="font-size:12px">Gentle nudges to sit, streak saves &amp; celebrations.</div></div>
      <label class="switch"><input type="checkbox" id="nen" ${np.enabled?'checked':''}><span class="sl"></span></label>
    </div>
    <p class="muted" id="nstat" style="font-size:12px;margin:4px 0 0">${np.registered?(ic('spark','g')+' This device is set up for push.'):'To get them on your phone: open Lumen on iOS and tap <b>Allow</b> when asked (needs the latest build).'}</p>
    <div id="ncatwrap" style="margin-top:12px;${np.enabled?'':'opacity:.45;pointer-events:none'}">
      <div class="muted" style="font-size:11px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:2px">What to send</div>
      ${NCATS.map(cc=>`<div class="nrow"><span class="nl">${esc(cc[1])}</span><label class="switch"><input type="checkbox" id="nc_${cc[0]}" ${(np.cats&&np.cats[cc[0]]===0)?'':'checked'}><span class="sl"></span></label></div>`).join('')}
      <div class="nrow"><span class="nl">Quiet hours <span class="muted" style="font-size:11px">(your local time)</span></span>
        <span style="display:flex;align-items:center;gap:6px"><select id="nqs" class="nsel">${hoursOpts(np.quiet_start)}</select><span class="muted">to</span><select id="nqe" class="nsel">${hoursOpts(np.quiet_end)}</select></span></div>
    </div>
  </div>`:''}
  <div class="card">
    <div class="nrow" style="border-top:0;padding-top:0">
      <div><b>Text reminders</b><div class="muted" style="font-size:12px">Opt-in SMS for streak saves &amp; gentle nudges. Standard rates apply.</div></div>
      <label class="switch"><input type="checkbox" id="smsen" ${(p.sms_consent&&!p.sms_optout)?'checked':''}><span class="sl"></span></label>
    </div>
    <label style="margin-top:10px">Mobile number</label>
    <input id="smsph" type="tel" autocomplete="tel" placeholder="+1 555 123 4567" value="${esc(p.phone||'')}">
    ${p.sms_optout?`<p class="muted" style="font-size:12px;margin:6px 0 0;color:#ff9aa6">You texted STOP, so we won't send texts. Toggle on above to opt back in.</p>`:''}
    <button class="btn ghost" id="smssave" style="margin-top:10px">Save text settings</button>
    <p class="muted" style="font-size:11px;margin:8px 0 0">Reply STOP to any text to opt out anytime.</p>
  </div>
  <a class="btn ghost" href="survey" target="_blank" rel="noopener" style="display:block;text-align:center;text-decoration:none;margin-top:4px;border-color:rgba(245,201,119,.4);color:var(--gold)">${ic('spark','g')} Share feedback — help shape Lumen</a>
  <button class="btn ghost" id="out" style="margin-top:10px">Sign out</button>
  <button class="btn ghost" id="del" style="margin-top:10px;border-color:#5a2230;color:#ff9aa6">Delete account</button>
  <p class="muted" style="font-size:11px;text-align:center;margin:8px 20px 0">Deleting your account permanently removes your profile, sessions, journal, and progress. This can't be undone.</p>`;
  $('#loc').onclick=async()=>{
    const btn=$('#loc'),help=$('#lochelp');help.style.display='none';
    if(!navigator.geolocation){toast('Geolocation isn’t available on this device');return;}
    // iOS remembers a prior “Don’t allow” and won’t re-prompt — surface that clearly
    try{const ps=await navigator.permissions.query({name:'geolocation'});
      if(ps.state==='denied'){help.style.display='block';
        help.innerHTML='Location is blocked for this site. On iPhone: Settings → Apps → Safari → Location → Allow, then reload this page and tap again.';return;}
    }catch(e){}
    btn.disabled=true;const old=btn.innerHTML;btn.innerHTML=ic('live','g')+' Locating…';
    navigator.geolocation.getCurrentPosition(async pos=>{
      try{await api('location','POST',{lat:pos.coords.latitude,lon:pos.coords.longitude});toast(ic('pin')+' Location saved');renderProfile();}
      catch(e){toast(e);btn.disabled=false;btn.innerHTML=old;}
    },err=>{
      btn.disabled=false;btn.innerHTML=old;help.style.display='block';
      help.innerHTML=err.code===1
        ?'Location permission was denied. On iPhone: Settings → Apps → Safari → Location → Allow, then reload this page and tap again.'
        :'Couldn’t get a location fix. Make sure Location Services is on, then try again near a window.';
    },{enableHighAccuracy:true,timeout:12000,maximumAge:0});  // maximumAge:0 forces a fresh fix so a stale/wrong pin gets corrected
  };
  {const ps=$('#psave');if(ps)ps.onclick=async()=>{
    const bd=$('#pbd').value,bt=$('#pbt').value,bp=$('#pbp').value.trim();
    ps.disabled=true;ps.textContent='Saving…';
    try{await api('natal','POST',{birth_date:bd,birth_time:bt,birth_place:bp,birth_tz:-new Date().getTimezoneOffset()});
      toast('Birth details saved '+ic('spark','g'));renderProfile();}
    catch(e){ps.disabled=false;ps.textContent='Save birth details';toast(e);}
  };}
  if(np){
    const collectNotif=()=>{const cats={};NCATS.forEach(cc=>{const el=document.getElementById('nc_'+cc[0]);if(el)cats[cc[0]]=el.checked;});
      return {enabled:$('#nen').checked,cats,quiet_start:+$('#nqs').value,quiet_end:+$('#nqe').value,tz_offset_min:-new Date().getTimezoneOffset()};};
    const saveNotif=async()=>{try{await api('notif/prefs','POST',collectNotif());toast('Notifications updated');}catch(e){toast(e);}};
    const en=$('#nen');if(en)en.onchange=()=>{const w=$('#ncatwrap');if(w){w.style.opacity=en.checked?'':'.45';w.style.pointerEvents=en.checked?'':'none';}saveNotif();};
    NCATS.forEach(cc=>{const el=document.getElementById('nc_'+cc[0]);if(el)el.onchange=saveNotif;});
    ['nqs','nqe'].forEach(id=>{const el=document.getElementById(id);if(el)el.onchange=saveNotif;});
  }
  {const sb=$('#smssave');if(sb)sb.onclick=async()=>{
    const phone=$('#smsph').value.trim(),consent=$('#smsen').checked?1:0;
    if(consent&&!phone){toast('Add a mobile number to get texts');return;}
    sb.disabled=true;sb.textContent='Saving…';
    try{await api('sms/prefs','POST',{phone,sms_consent:consent});
      toast('Text settings saved '+ic('spark','g'));renderProfile();}
    catch(e){sb.disabled=false;sb.textContent='Save text settings';toast(e);}
  };}
  {const pb=$('#pro');if(pb)pb.onclick=async()=>{
    pb.disabled=true;const old=pb.innerHTML;pb.innerHTML=ic('live','g')+' Saving…';
    try{await api('premium/interest','POST',{});
      pb.style.display='none';
      const st=$('#prostate');if(st){st.innerHTML=ic('check','g')+' You’re on the founding-member list. We’ll reach out when Premium opens.';st.style.color='#f5c977';}
      toast(ic('spark','g')+' You’re on the Premium list');
    }catch(e){toast(e);pb.disabled=false;pb.innerHTML=old;}
  };}
  $('#out').onclick=async()=>{await api('logout','POST',{});ME=null;renderAuth();};
  $('#del').onclick=async()=>{const b=$('#del');
    if(b.dataset.armed!=='1'){b.dataset.armed='1';b.textContent='Tap again to permanently delete';b.style.background='#5a2230';b.style.color='#fff';
      setTimeout(()=>{if(b&&b.dataset.armed==='1'){b.dataset.armed='0';b.textContent='Delete account';b.style.background='';b.style.color='#ff9aa6';}},4000);return;}
    b.disabled=true;b.textContent='Deleting…';
    try{await api('account/delete','POST',{});}catch(e){}
    try{Object.keys(localStorage).filter(k=>k.indexOf('lumen_jny_')===0).forEach(k=>localStorage.removeItem(k));}catch(e){}
    ME=null;toast('Your account has been deleted');renderAuth();};
  window._ACH=ach.achievements;
  document.querySelectorAll('.ach').forEach(x=>x.onclick=()=>openAchCard(x.dataset.ac));
}

/* ---- achievement collectible card ---- */
function openAchCard(code){
  const a=(window._ACH||[]).find(x=>x.code===code);if(!a)return;
  const ri=rarityOf(a.code);const r=RARITY[ri];const rname=r[0],rcol=r[1],tint=r[2],glow=r[3];
  const locked=!a.unlocked;
  const date=a.created?new Date(a.created).toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric'}):'';
  const grad=locked?'':(ri===3?'grad-gold':ri===2?'grad-aur':ri===1?'grad-blue':'grad-slate');
  const ov=el(`<div class="ach-ov">
    <div class="ach-card rar-${ri} ${locked?'locked':''}" style="--rc:${rcol};--tint:${tint};--glow:${glow}">
      <button class="ach-x">${ic('close')}</button>
      <div class="ach-foil"></div>
      <div class="ach-rare" style="color:${rcol};border-color:${rcol}">${rname}</div>
      <div class="ach-badge">
        <div class="ach-ring"></div>
        <div class="ach-ic" style="${locked?'':'color:'+rcol}">${ic(locked?'lock':(ACH_ICON[code]||'star'),'achbig '+grad)}</div>
      </div>
      <div class="ach-title">${locked?'???':a.title}</div>
      <div class="ach-desc">${a.desc}</div>
      <div class="ach-meta">
        ${locked?`<span class="ach-chip">${ic('lock')} Locked</span>`:`<span class="ach-chip" style="color:var(--good)">${ic('check')} Unlocked${date?' · '+date:''}</span>`}
        <span class="ach-chip">${a.pct}% of lumens have this</span>
      </div>
    </div></div>`);
  ov.addEventListener('click',e=>{if(e.target===ov||e.target.closest('.ach-x'))ov.remove();});
  document.body.appendChild(ov);
  requestAnimationFrame(()=>ov.classList.add('show'));
}

/* ---- collection: real-world meditation items ---- */
let collectView='altar';
const GRADOF=['slate','blue','aur','gold'];
const ELEMENT_COL={Light:'#f5c977',Fire:'#fb923c',Water:'#5fb0fa',Air:'#67e8f9',Earth:'#6ee7b7',Cosmos:'#c084fc'};
// each altar piece is placed when you unlock its achievement
async function renderCollection(){
  const r=await api('me');ME=r.profile;
  const isArt=collectView==='artifacts';
  $('#app').innerHTML=`<div class="brand"><span class="mark">${lumenMark('mark')}</span><b>${isArt?'Your Artifacts':'Your Mandala'}</b>
    <span class="motebal">${ic('spark','g glow')} ${fmt(ME.motes)}</span></div>
  <div id="cbody" class="${isArt?'cbody-art':'cbody-altar'}"></div>
  <div class="ctoggle"><div class="seg" id="cv">
    <button class="${!isArt?'on':''}" data-v="altar">${ic('crystal')} Mandala</button>
    <button class="${isArt?'on':''}" data-v="artifacts">${ic('seal')} Artifacts</button>
  </div></div>`;
  $('#cv').querySelectorAll('button').forEach(b=>b.onclick=()=>{collectView=b.dataset.v;renderCollection();});
  if(collectView==='artifacts')await renderArtifacts();
  else await renderAltar();
}
/* ---- the altar: a single multi-colour rose-window whose facets are achievements ---- */
function buildAltar(achs){
  const N=achs.length, n=achs.filter(a=>a.unlocked).length, frac=n/Math.max(1,N), complete=n>=N;
  const C=150, step=360/N;
  const petalOuter='M150 150 C137 100 141 60 150 44 C159 60 163 100 150 150 Z';   // tall facet
  const petalInner='M150 150 C144 118 146 96 150 86 C154 96 156 118 150 150 Z';   // short inner frond
  const P=[`<defs>
    <radialGradient id="aglow" cx="50%" cy="50%" r="64%"><stop offset="0" stop-color="#ffffff14"/><stop offset="100%" stop-color="transparent"/></radialGradient>
    <radialGradient id="acore" cx="50%" cy="40%" r="62%"><stop offset="0" stop-color="#fff6df"/><stop offset="1" stop-color="#e0953a"/></radialGradient>
    <radialGradient id="aradiance" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#ffe7b8"/><stop offset="45%" stop-color="#e0953a" stop-opacity=".4"/><stop offset="100%" stop-color="transparent"/></radialGradient>
    <filter id="apg" x="-70%" y="-70%" width="240%" height="240%"><feGaussianBlur stdDeviation="2.3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  </defs>`,`<rect width="300" height="300" fill="url(#aglow)"/>`];
  // breathing central radiance — the mandala "inhales" like the orb
  const gLo=(0.07+0.22*frac).toFixed(2), gHi=(0.16+0.42*frac).toFixed(2);
  P.push(`<circle cx="150" cy="150" r="90" fill="url(#aradiance)">
    <animate attributeName="opacity" values="${gLo};${gHi};${gLo}" dur="6.5s" repeatCount="indefinite"/>
    <animate attributeName="r" values="66;104;66" dur="6.5s" calcMode="spline" keyTimes="0;0.5;1" keySplines="0.45 0 0.2 1;0.45 0 0.2 1" repeatCount="indefinite"/></circle>`);
  // slow rotating sun-rays behind the facets (faint gold radiance)
  let rays='';for(let i=0;i<24;i++){const a=i*15*Math.PI/180;rays+=`<line x1="${(C+30*Math.sin(a)).toFixed(1)}" y1="${(C-30*Math.cos(a)).toFixed(1)}" x2="${(C+134*Math.sin(a)).toFixed(1)}" y2="${(C-134*Math.cos(a)).toFixed(1)}" stroke="#f5c977" stroke-width="${i%2?1.1:0.5}" stroke-linecap="round" opacity="0.10"/>`;}
  P.push(`<g opacity="${(0.5+0.5*frac).toFixed(2)}">${rays}<animateTransform attributeName="transform" type="rotate" from="0 150 150" to="360 150 150" dur="120s" repeatCount="indefinite"/></g>`);
  // slowly turning outer bead ring (counter-rotates the rays)
  let dots='';for(let i=0;i<48;i++){const a=i*7.5*Math.PI/180;dots+=`<circle cx="${(C+131*Math.sin(a)).toFixed(1)}" cy="${(C-131*Math.cos(a)).toFixed(1)}" r="${i%2?1.4:0.9}" fill="#4a4168"/>`;}
  P.push(`<g><animateTransform attributeName="transform" type="rotate" from="360 150 150" to="0 150 150" dur="140s" repeatCount="indefinite"/>${dots}</g>`);
  // structural rings (stained-glass leading)
  P.push(`<circle cx="150" cy="150" r="121" fill="none" stroke="#2e2747" stroke-width="1.3"/><circle cx="150" cy="150" r="78" fill="none" stroke="#241f38"/>`);
  // radial leading lines between facets
  let leads='';for(let i=0;i<N;i++){const a=(i*step+step/2)*Math.PI/180;leads+=`<line x1="${(C+32*Math.sin(a)).toFixed(1)}" y1="${(C-32*Math.cos(a)).toFixed(1)}" x2="${(C+120*Math.sin(a)).toFixed(1)}" y2="${(C-120*Math.cos(a)).toFixed(1)}" stroke="#2a2540" stroke-width="1"/>`;}
  P.push(leads);
  // decorative inner fronds between the facets (faint, same hue family)
  achs.forEach((a,i)=>{const ang=i*step+step/2;const col=a.unlocked?catColor(a.code):'#3a3550';
    P.push(`<g transform="rotate(${ang} 150 150)"><path d="${petalInner}" fill="none" stroke="${col}" stroke-width="1" opacity="${a.unlocked?0.5:0.22}"/></g>`);});
  // the facets — one coloured petal per achievement, unlocked ones gently shimmer
  achs.forEach((a,i)=>{const ang=i*step;const on=a.unlocked;const col=catColor(a.code);
    const sh=on?`<animate attributeName="opacity" values="0.9;1;0.9" dur="${(4.5+(i%5)*0.7).toFixed(1)}s" begin="${(i*0.3).toFixed(1)}s" repeatCount="indefinite"/>`:'';
    P.push(`<g class="apiece" data-ach="${a.code}" transform="rotate(${ang} 150 150)" style="cursor:pointer">`+
      `<path d="${petalOuter}" fill="${on?col:'none'}" fill-opacity="${on?0.8:0}" stroke="${on?col:'#3a3550'}" stroke-width="${on?1.2:1.3}" stroke-linejoin="round" opacity="${on?0.98:0.45}" ${on?'filter="url(#apg)"':''}>${sh}</path>`+
      `<path d="${petalOuter}" fill="none" stroke="${on?'#ffffffaa':'transparent'}" stroke-width="0.5" opacity="0.5"/></g>`);
  });
  // twinkling motes drifting through the ring (golden-angle scatter)
  let motes='';for(let i=0;i<16;i++){const a=(i*137.5)*Math.PI/180;const rr=48+(i%5)*17;const x=(C+rr*Math.sin(a)).toFixed(1),y=(C-rr*Math.cos(a)).toFixed(1);const d=(3.4+(i%4)*0.9).toFixed(1),dl=(i*0.37).toFixed(1);
    motes+=`<circle cx="${x}" cy="${y}" r="1.2" fill="#ffe7b8"><animate attributeName="opacity" values="0;0.95;0" dur="${d}s" begin="${dl}s" repeatCount="indefinite"/><animate attributeName="r" values="0.5;1.7;0.5" dur="${d}s" begin="${dl}s" repeatCount="indefinite"/></circle>`;}
  P.push(`<g opacity="${(0.35+0.65*frac).toFixed(2)}">${motes}</g>`);
  // inner jewel ring — a coloured gem per facet
  achs.forEach((a,i)=>{const ang=i*step*Math.PI/180,r=60,x=C+r*Math.sin(ang),y=C-r*Math.cos(ang);const on=a.unlocked;
    P.push(`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${on?3:1.8}" fill="${on?catColor(a.code):'#3a3550'}" ${on?'filter="url(#apg)"':''}/>`);
  });
  // pulsing halo breathing out of the core
  P.push(`<circle cx="150" cy="150" r="30" fill="none" stroke="${complete?'#f5c977':'#8a7bbf'}" stroke-width="1">
    <animate attributeName="r" values="27;42;27" dur="4.6s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="${complete?0.55:0.3};0;${complete?0.55:0.3}" dur="4.6s" repeatCount="indefinite"/></circle>`);
  // faceted crystal core — gold, radiating with completion, gently breathing
  P.push(`<circle cx="150" cy="150" r="30" fill="#140f24" stroke="${complete?'#f5c977':'#3a3550'}" stroke-width="1.4" ${complete?'filter="url(#apg)"':''}/>`);
  const gem=(SVGP['crystal']||'').replace(/currentColor/g,'url(#acore)');
  P.push(`<g opacity="${(0.3+0.7*frac).toFixed(2)}" ${frac>0.5?'filter="url(#apg)"':''}><g transform="translate(135,134) scale(1.3)" fill="none" stroke="url(#acore)" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round">${gem}<animate attributeName="opacity" values="0.75;1;0.75" dur="5.5s" repeatCount="indefinite"/></g></g>`);
  return `<svg viewBox="0 0 300 300" class="altar-svg">${P.join('')}</svg>`;
}
function _onMandalaMsg(e){
  if(e&&e.data&&e.data.lumenMandalaHeight){
    const f=document.getElementById('mandalaFrame');
    if(f)f.style.height=(Math.ceil(e.data.lumenMandalaHeight)+6)+'px';}}
async function renderAltar(){
  // The mandala renders at full length (no inner scroll); the whole page scrolls.
  // The iframe auto-sizes to its content via the lumenMandalaHeight postMessage.
  window.removeEventListener('message',_onMandalaMsg);
  window.addEventListener('message',_onMandalaMsg);
  $('#cbody').innerHTML=`
  <div class="mandala-wrap">
    <iframe id="mandalaFrame" src="assets/mandala.html?v=5" title="Your mandala" loading="eager" scrolling="no"
      style="width:100%;height:600px;min-height:560px;border:0;display:block;background:transparent"></iframe>
  </div>`;
}
async function renderItems(){
  let d={items:[],equipped:null};try{d=await api('collection');}catch(e){}
  window._COL=d;
  const owned=d.items.filter(i=>i.owned).length,total=d.items.length;
  const claimable=d.items.filter(i=>i.eligible&&!i.owned).length;
  $('#cbody').innerHTML=`
  <div class="card center" style="padding:14px">
    <div class="muted" style="font-size:12px;text-transform:uppercase;letter-spacing:.1em">Your mandala</div>
    <div style="font-size:28px;font-weight:800;margin:3px 0">${owned}<span class="muted" style="font-size:17px">/${total}</span></div>
    <div class="bar" style="max-width:220px;margin:0 auto"><i style="width:${Math.round(100*owned/total)}%"></i></div>
    ${claimable?`<div class="pill" style="margin-top:12px;border-color:var(--gold);color:var(--gold)">${ic('spark','g glow')} ${claimable} ready to claim</div>`:''}
  </div>
  <div class="coll-grid">
    ${d.items.map(it=>{const ri=it.rarity,r=RARITY[ri];const state=it.owned?'owned':(it.eligible?'claim':'locked');
      return `<div class="coll ${state}" data-code="${it.code}" style="--rc:${r[1]}">
        <div class="coll-ic">${ic(it.owned||it.eligible?ITEM_ICON[it.code]:'lock', (it.owned?'grad-'+GRADOF[ri]:''))}</div>
        <div class="coll-nm">${it.owned||it.eligible?esc(it.name):'• • •'}</div>
        <div class="coll-st">${it.owned?(d.equipped===it.code?'Carried':'Owned'):(it.eligible?'Claim':r[0])}</div>
      </div>`;}).join('')}
  </div>`;
  document.querySelectorAll('.coll').forEach(x=>x.onclick=()=>openItemCard(x.dataset.code));
}
async function renderCompanions(){
  let d={companions:[],equipped:null,motes:0};try{d=await api('companions');}catch(e){}
  window._COMP=d;
  const have=d.companions.filter(x=>x.owned).length;
  $('#cbody').innerHTML=`
  ${have?'':'<div class="card muted center" style="font-size:13px">Adopt a companion to sit with — then feed it Motes you earn each session and watch it grow from a Spark into something Celestial.</div>'}
  <div class="comp-grid">
    ${d.companions.map(x=>{const eq=d.equipped===x.code;const col=ELEMENT_COL[x.element]||'#a855f7';
      const st=x.owned?x.stage:null;
      return `<div class="comp ${x.owned?'owned':'locked'} ${eq?'eq':''}" data-code="${x.code}" style="--el:${col}">
        ${eq?`<span class="comp-eqtag">Companion</span>`:''}
        <div class="comp-ic s${x.owned?st.index:0}">${ic(COMP_ICON[x.code])}</div>
        <div class="comp-nm">${esc(x.name)}</div>
        <div class="comp-st">${x.owned?st.name:(x.cost?`${ic('spark','g')} ${fmt(x.cost)}`:'Free')}</div>
      </div>`;}).join('')}
  </div>
  <p class="muted center" style="font-size:12px;margin-top:12px">Tap a companion to adopt, feed, or set as your own.</p>`;
  document.querySelectorAll('.comp').forEach(x=>x.onclick=()=>openCompanionCard(x.dataset.code));
}
async function renderShop(){
  let d={shop:[],motes:0,member_days:0};try{d=await api('shop');}catch(e){}
  $('#cbody').innerHTML=`
  <div class="card center" style="padding:13px">
    <div class="muted" style="font-size:12px">You hold</div>
    <div style="font-size:24px;font-weight:800;color:var(--gold)">${ic('spark','g glow')} ${fmt(d.motes)} Motes</div>
    <div class="muted" style="font-size:11px;margin-top:2px">Member for ${d.member_days} ${d.member_days===1?'day':'days'}</div>
  </div>
  ${d.shop.map(it=>{const r=RARITY[it.rarity];return `<div class="shop-row ${it.owned?'owned':''} ${it.locked?'locked':''}" style="--rc:${r[1]}">
    <div class="shop-ic">${ic(ITEM_ICON[it.code],'grad-'+GRADOF[it.rarity])}</div>
    <div style="flex:1;min-width:0">
      <div class="shop-nm">${esc(it.name)} <span class="rtag" style="--c:${r[1]};font-size:9px">${r[0]}</span></div>
      <div class="muted" style="font-size:12px;font-family:var(--serif);font-style:italic">${esc(it.flavor)}</div>
      ${it.gate?`<div style="font-size:11px;color:${it.locked?'var(--muted)':'var(--good)'};margin-top:3px">${it.locked?ic('lock'):ic('check')} ${esc(it.gate)}</div>`:''}
    </div>
    <div class="shop-buy">${it.owned?`<span class="muted" style="font-size:12px">${ic('check','g')} Owned</span>`
      :it.locked?`<span class="muted" style="font-size:12px">${ic('lock')}</span>`
      :`<button class="btn gold" data-code="${it.code}" style="width:auto;padding:9px 14px;font-size:14px">${it.price?`${ic('spark')} ${fmt(it.price)}`:'Claim'}</button>`}</div>
  </div>`;}).join('')}
  <p class="muted center" style="font-size:12px;margin-top:12px">Earn Motes every time you meditate. Founder items open as your membership grows.</p>`;
  document.querySelectorAll('.shop-buy button').forEach(b=>b.onclick=async()=>{
    try{const r=await api('shop/buy','POST',{code:b.dataset.code});toast((r.name||'Item')+' is yours '+ic('spark','g'));renderCollection();}catch(e){toast(e);}});
}
/* ---- Artifacts: real pieces + digital travel companion ---- */
async function renderArtifacts(){
  let d={artifacts:[],equipped:null};try{d=await api('nft');}catch(e){}
  window._ART=d;
  $('#cbody').innerHTML=`
  <div class="card center" style="padding:14px">
    <div class="muted" style="font-size:12px;text-transform:uppercase;letter-spacing:.12em">Artifacts</div>
    <div style="font-family:var(--serif);font-style:italic;color:#cbbfe6;font-size:14px;margin-top:6px">A companion to carry as you meditate. Each is a real, meaningful object — kept at your side and in the app — that travels with you, wherever you sit.</div>
  </div>
  ${d.artifacts.map(a=>{const r=RARITY[a.rarity];const eq=d.equipped===a.code;
    return `<div class="art-row ${a.owned?'owned':''}" data-code="${a.code}" style="--rc:${r[1]}">
      <div class="art-ic">${ic(ART_ICON[a.code],'grad-'+GRADOF[a.rarity])}${a.img?`<img src="${a.img}" class="art-img" alt="" onerror="this.remove()">`:''}</div>
      <div style="flex:1;min-width:0">
        <div class="art-nm">${esc(a.name)}</div>
        <div class="art-origin">${esc(a.origin)} · ${esc(a.material)}</div>
        <div class="art-sub">${esc(a.edition)} · <b>$${a.price}</b></div>
      </div>
      <div class="art-act">${a.owned?`<span class="art-pill" style="color:var(--good);border-color:#2e4a38">${ic('check','g')} ${eq?'carried':'reserved'}</span>`:`<span class="art-pill" style="color:${r[1]};border-color:${r[1]}">view</span>`}</div>
    </div>`;}).join('')}
  <div class="card" style="padding:14px;margin-top:4px">
    <div style="display:flex;align-items:center;gap:8px;color:var(--good);font-weight:700;font-size:13px">${ic('check','g')} Ethically sourced</div>
    <p class="muted" style="font-size:12.5px;line-height:1.6;margin:8px 0 0">Every piece comes from a <b style="color:var(--text)">trusted dealer</b> or a <b style="color:var(--text)">verified local artisan</b> — and the makers are <b style="color:var(--text)">paid fairly</b> for their craft. Antique originals arrive with <b style="color:var(--text)">provenance &amp; a certificate of authenticity</b>; handmade pieces support the maker directly. We never sell looted, faked, or endangered materials.</p>
  </div>
  <p class="muted center" style="font-size:12px;margin-top:10px">Tap a piece to see its story and reserve yours.</p>`;
  document.querySelectorAll('.art-row').forEach(row=>row.onclick=()=>openNftCard(row.dataset.code));
}
function openNftCard(code){
  const d=window._ART||{artifacts:[]};const a=d.artifacts.find(x=>x.code===code);if(!a)return;
  const r=RARITY[a.rarity],rcol=r[1],tint=r[2],glow=r[3];const eq=d.equipped===code;
  const ov=el(`<div class="ach-ov">
    <div class="ach-card rar-${a.rarity}" style="--rc:${rcol};--tint:${tint};--glow:${glow}">
      <button class="ach-x">${ic('close')}</button>
      <div class="ach-foil"></div>
      <div class="ach-rare" style="color:${rcol};border-color:${rcol}">${r[0]} · Artifact</div>
      <div class="ach-badge"><div class="ach-ring"></div>
        <div class="ach-ic" style="color:${rcol}">${ic(ART_ICON[code],'achbig grad-'+GRADOF[a.rarity])}</div>
        ${a.img?`<img src="${a.img}" class="art-cimg" alt="" onerror="this.remove()">`:''}
      </div>
      <div class="ach-title">${esc(a.name)}</div>
      <div class="ach-desc" style="font-family:var(--serif);font-style:italic">“${esc(a.flavor)}”</div>
      <div class="ach-meta">
        <span class="ach-chip">${ic('pin')} ${esc(a.origin)}</span>
        <span class="ach-chip">${esc(a.material)} · ${esc(a.edition)}</span>
        <span class="ach-chip" style="color:var(--good)">${ic('check','g')} ${esc(a.source)}</span>
        <span class="ach-chip" style="color:var(--gold)">A companion to carry as you meditate · $${a.price}</span>
      </div>
      <div id="nftact" style="margin-top:4px"></div>
    </div></div>`);
  const act=ov.querySelector('#nftact');
  if(!a.owned){
    act.innerHTML=`<button class="btn gold" style="width:auto;padding:11px 20px">Reserve yours · $${a.price}</button><div class="muted" style="font-size:11px;margin-top:7px">Reserves your numbered piece — we’ll reach out to arrange it.</div>`;
    act.querySelector('button').onclick=async()=>{try{await api('nft/reserve','POST',{code});toast('Reserved '+esc(a.name)+' '+ic('spark','g'));ov.remove();renderCollection();}catch(e){toast(e);}};
  }else if(eq){
    act.innerHTML=`<span class="ach-chip" style="color:var(--good)">${ic('check')} Carried in your sessions</span>`;
  }else{
    act.innerHTML=`<span class="ach-chip" style="color:var(--good)">${ic('check','g')} Reserved</span><button class="btn" style="width:auto;padding:10px 18px;margin-top:8px">Carry in meditation</button>`;
    act.querySelector('button').onclick=async()=>{try{await api('collection/equip','POST',{code});toast('Carrying your '+esc(a.name));ov.remove();renderCollection();}catch(e){toast(e);}};
  }
  ov.addEventListener('click',e=>{if(e.target===ov||e.target.closest('.ach-x'))ov.remove();});
  document.body.appendChild(ov);requestAnimationFrame(()=>ov.classList.add('show'));
}
function openItemCard(code){
  const d=window._COL||{items:[]};const it=d.items.find(x=>x.code===code);if(!it)return;
  const ri=it.rarity,r=RARITY[ri],rcol=r[1],tint=r[2],glow=r[3];
  const state=it.owned?'owned':(it.eligible?'claim':'locked');
  const equipped=d.equipped===code;
  const grad=(it.owned||it.eligible)?'grad-'+GRADOF[ri]:'';
  const ov=el(`<div class="ach-ov">
    <div class="ach-card rar-${ri} ${state==='locked'?'locked':''}" style="--rc:${rcol};--tint:${tint};--glow:${glow}">
      <button class="ach-x">${ic('close')}</button>
      <div class="ach-foil"></div>
      <div class="ach-rare" style="color:${rcol};border-color:${rcol}">${r[0]} · Item</div>
      <div class="ach-badge"><div class="ach-ring"></div>
        <div class="ach-ic" style="${state==='locked'?'':'color:'+rcol}">${ic(state==='locked'?'lock':ITEM_ICON[code],'achbig '+grad)}</div>
      </div>
      <div class="ach-title">${state==='locked'?'???':esc(it.name)}</div>
      <div class="ach-desc" style="font-family:var(--serif);font-style:italic">${state==='locked'?esc(it.unlock):'“'+esc(it.flavor)+'”'}</div>
      <div class="ach-meta" id="itemact"></div>
    </div></div>`);
  const act=ov.querySelector('#itemact');
  if(state==='locked'){act.innerHTML=`<span class="ach-chip">${ic('lock')} ${esc(it.unlock)}</span>`;}
  else if(state==='claim'){act.innerHTML=`<button class="btn gold" style="width:auto;padding:11px 20px">${ic('spark')} Add to collection</button>`;
    act.querySelector('button').onclick=async()=>{try{await api('collection/claim','POST',{code});toast(esc(it.name)+' claimed '+ic('spark','g'));ov.remove();renderCollection();}catch(e){toast(e);}};}
  else{act.innerHTML=equipped?`<span class="ach-chip" style="color:var(--good)">${ic('check')} Carried in sessions</span>`
      :`<button class="btn" style="width:auto;padding:11px 20px">Carry in sessions</button>`;
    const b=act.querySelector('button');if(b)b.onclick=async()=>{try{await api('collection/equip','POST',{code});toast('Carrying your '+esc(it.name));ov.remove();renderCollection();}catch(e){toast(e);}};}
  ov.addEventListener('click',e=>{if(e.target===ov||e.target.closest('.ach-x'))ov.remove();});
  document.body.appendChild(ov);requestAnimationFrame(()=>ov.classList.add('show'));
}

/* ---- companion card: adopt, feed, grow, equip ---- */
function openCompanionCard(code){
  const d=window._COMP||{companions:[]};const x=d.companions.find(c=>c.code===code);if(!x)return;
  const col=ELEMENT_COL[x.element]||'#a855f7';
  const st=x.owned?x.stage:null;
  const prog=(x.owned&&!st.max)?Math.min(100,100*(x.fed-st.at)/(st.next_at-st.at)):100;
  const ov=el(`<div class="ach-ov">
    <div class="ach-card" style="--rc:${col};--tint:#15131f;--glow:${col}33">
      <button class="ach-x">${ic('close')}</button>
      <div class="ach-foil"></div>
      <div class="ach-rare" style="color:${col};border-color:${col}">${esc(x.element)} companion</div>
      <div class="ach-badge"><div class="ach-ring"></div>
        <div class="ach-ic s${x.owned?st.index:0}" style="color:${col}">${ic(COMP_ICON[code],'achbig')}</div>
      </div>
      <div class="ach-title">${esc(x.name)}</div>
      <div class="ach-desc" style="font-family:var(--serif);font-style:italic">“${esc(x.flavor)}”</div>
      ${x.owned?`<div style="position:relative;z-index:2;margin:2px 24px 10px">
          <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--muted)"><span style="color:${col}">${st.name}</span><span>${st.max?'Fully grown':fmt(x.fed)+' / '+fmt(st.next_at)}</span></div>
          <div class="bar" style="margin-top:5px"><i style="width:${prog}%;background:linear-gradient(90deg,${col},#fff6)"></i></div>
        </div>`:''}
      <div class="ach-meta" id="compact"></div>
    </div></div>`);
  const act=ov.querySelector('#compact');
  const close=()=>ov.remove();
  if(!x.owned){
    const afford=(ME.motes||0)>=x.cost;
    act.innerHTML=`<button class="btn gold" ${afford?'':'disabled style="opacity:.5"'} style="width:auto;padding:11px 20px">${x.cost?`Adopt · ${ic('spark')} ${fmt(x.cost)}`:'Adopt — free'}</button>${afford?'':`<span class="ach-chip">Need ${fmt(x.cost-(ME.motes||0))} more Motes</span>`}`;
    const b=act.querySelector('button');if(b&&afford)b.onclick=async()=>{try{await api('companions/adopt','POST',{code});toast('You adopted '+esc(x.name)+' '+ic('spark','g'));close();renderCollection();}catch(e){toast(e);}};
  }else{
    const eq=d.equipped===code;
    const feeds=[['+50',50],['+200',200]];
    act.innerHTML=`<div style="display:flex;gap:8px;flex-wrap:wrap;justify-content:center">
      ${st.max?'':feeds.map(f=>`<button class="btn ghost feed" data-amt="${f[1]}" style="width:auto;padding:9px 14px">${ic('spark','g')} ${f[0]}</button>`).join('')}
      ${eq?`<span class="ach-chip" style="color:var(--good)">${ic('check')} Your companion</span>`:`<button class="btn equip" style="width:auto;padding:9px 16px">Set as companion</button>`}
    </div><div class="muted" style="font-size:11px;margin-top:8px">You hold ${ic('spark','g')} ${fmt(ME.motes||0)} Motes</div>`;
    act.querySelectorAll('.feed').forEach(b=>b.onclick=async()=>{
      const amt=+b.dataset.amt;if((ME.motes||0)<1){toast('Meditate to earn Motes first');return;}
      try{const r=await api('companions/feed','POST',{code,amount:amt});const me=await api('me');ME=me.profile;
        if(r.evolved)toast(esc(x.name)+' evolved to '+r.stage.name+'! '+ic('spark','g'));else toast('Fed '+esc(x.name));
        close();openCompanionCardFresh(code);}catch(e){toast(e);}});
    const eb=act.querySelector('.equip');if(eb)eb.onclick=async()=>{try{await api('companions/equip','POST',{code});toast(esc(x.name)+' walks with you now');close();renderCollection();}catch(e){toast(e);}};
  }
  ov.addEventListener('click',e=>{if(e.target===ov||e.target.closest('.ach-x'))close();});
  document.body.appendChild(ov);requestAnimationFrame(()=>ov.classList.add('show'));
}
async function openCompanionCardFresh(code){try{window._COMP=await api('companions');}catch(e){}openCompanionCard(code);}

if('serviceWorker' in navigator){window.addEventListener('load',()=>{navigator.serviceWorker.register('sw.js').catch(()=>{});});}
boot();
</script>
</body>
</html>"""

class H(BaseHTTPRequestHandler):
    server_version = "Lumen/1.0"

    def log_message(self, *a):
        pass

    # -- plumbing ----------------------------------------------------------
    def _send(self, code, body, ct="application/json", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        if extra:
            for k, v in extra:
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length", "0"))
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def _cookie(self, name):
        raw = self.headers.get("Cookie", "")
        for part in raw.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                if k == name:
                    return v
        return None

    def _me(self, c):
        tok = self._cookie("lumen_sess")
        email = session_email(tok) if tok else None
        if not email:
            return None
        return user_by_email(c, email)

    def _owner(self, c):
        u = self._me(c)
        if not u:
            return None, (401, {"error": "sign in"})
        if (u["email"] or "").lower() not in OWNER_EMAILS:
            return None, (403, {"error": "forbidden"})
        return u, None

    def _path(self):
        p = self.path
        if BASE and p.startswith(BASE):
            p = p[len(BASE):] or "/"
        q = ""
        if "?" in p:
            p, q = p.split("?", 1)
        return p, dict(urllib_parse_qsl(q))

    # -- routing -----------------------------------------------------------
    def do_GET(self):
        p, q = self._path()
        if p in ("/", "/index.html"):
            self._send(200, PAGE.replace("__SENTRY_REL__", SENTRY_REL), "text/html; charset=utf-8",
                       extra=[("Cache-Control", "no-cache, no-store, must-revalidate")]); return
        if p == "/manifest.webmanifest":
            self._send(200, MANIFEST, "application/manifest+json"); return
        if p == "/sw.js":
            self._send(200, SERVICE_WORKER, "application/javascript; charset=utf-8",
                       extra=[("Cache-Control", "no-cache, no-store, must-revalidate")]); return
        if p in ("/privacy", "/privacy.html"):
            self._send(200, PRIVACY_PAGE, "text/html; charset=utf-8"); return
        if p in ("/admin", "/admin.html"):
            self._send(200, ADMIN_PAGE, "text/html; charset=utf-8",
                       extra=[("Cache-Control", "no-cache, no-store, must-revalidate")]); return
        if p in ("/site", "/site.html", "/lp"):
            self._send(200, site_page(), "text/html; charset=utf-8"); return
        if p in ("/survey", "/survey.html", "/feedback"):
            self._send(200, SURVEY_PAGE, "text/html; charset=utf-8",
                       extra=[("Cache-Control", "no-cache")]); return
        if p == "/health":
            self._send(200, {"ok": True}); return
        if p == "/e/unsub":
            tok = (q.get("u") or "").strip()
            done = False
            if tok:
                with _dblock:
                    cc = db()
                    try:
                        r = cc.execute("SELECT id FROM users WHERE unsub_token=?", (tok,)).fetchone()
                        if r:
                            cc.execute("UPDATE users SET email_optout=1 WHERE id=?", (r["id"],)); cc.commit()
                            done = True
                    finally:
                        cc.close()
            msg = ("You're unsubscribed." if done else "This link is no longer valid.")
            sub = ("You won't receive lifecycle emails from Lumen anymore. You can still change this in the app."
                   if done else "If you meant to unsubscribe, open Lumen and adjust your email preferences.")
            page = (f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                    f"<title>Lumen</title></head><body style='margin:0;background:#0b0a12;color:#f6f1ea;"
                    f"font-family:-apple-system,Segoe UI,sans-serif;display:grid;place-items:center;min-height:100vh;text-align:center'>"
                    f"<div style='max-width:420px;padding:28px'>"
                    f"<div style='font-family:Georgia,serif;font-size:30px;font-weight:700;color:#f5c977'>lumen</div>"
                    f"<h1 style='font-size:22px;margin:22px 0 8px'>{msg}</h1>"
                    f"<p style='color:#b4acd0;line-height:1.6'>{sub}</p></div></body></html>")
            self._send(200, page, "text/html; charset=utf-8"); return
        if p == "/e/premium":
            # Landing for the upgrade email's CTA — records founding-member interest
            # (deduped) and confirms. No payment yet; RevenueCat wires that later.
            tok = (q.get("u") or "").strip()
            ok = False
            if tok:
                with _dblock:
                    cc = db()
                    try:
                        r = cc.execute("SELECT id, email FROM users WHERE unsub_token=?", (tok,)).fetchone()
                        if r:
                            cc.execute("INSERT OR IGNORE INTO premium_waitlist(user_id,email,created) VALUES(?,?,?)",
                                        (r["id"], r["email"], now_iso())); cc.commit()
                            ok = True
                    finally:
                        cc.close()
            msg = ("You're on the list ✦" if ok else "Hmm — that link expired.")
            sub = ("You'll get first access to Lumen Premium and a founding-member price when it opens. Keep practicing in the meantime."
                   if ok else "Open Lumen and tap “Go Premium” to raise your hand.")
            page = (f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                    f"<title>Lumen Premium</title></head><body style='margin:0;background:#0b0a12;color:#f6f1ea;"
                    f"font-family:-apple-system,Segoe UI,sans-serif;display:grid;place-items:center;min-height:100vh;text-align:center'>"
                    f"<div style='max-width:420px;padding:28px'>"
                    f"<div style='font-family:Georgia,serif;font-size:30px;font-weight:700;color:#f5c977'>lumen</div>"
                    f"<h1 style='font-size:22px;margin:22px 0 8px'>{msg}</h1>"
                    f"<p style='color:#b4acd0;line-height:1.6'>{sub}</p>"
                    f"<a href='{APP_STORE_URL}' style='display:inline-block;margin-top:22px;background:linear-gradient(135deg,#f5c977,#e0953a);"
                    f"color:#2a1a05;text-decoration:none;font-weight:700;padding:13px 26px;border-radius:13px'>Open Lumen</a>"
                    f"</div></body></html>")
            self._send(200, page, "text/html; charset=utf-8"); return
        rel = p.lstrip("/")
        if rel in ("assets/diya.json", "assets/orb.js", "assets/mandala.html", "assets/column.json"):
            fp = os.path.join(HERE, "assets", os.path.basename(rel))
            if os.path.isfile(fp):
                if rel.endswith(".js"): ct = "application/javascript; charset=utf-8"
                elif rel.endswith(".html"): ct = "text/html; charset=utf-8"
                else: ct = "application/json"
                # mandala html is actively iterated — always revalidate; others cache long
                cc = "no-cache, must-revalidate" if rel.endswith(".html") else "public, max-age=604800"
                with open(fp, "rb") as f:
                    self._send(200, f.read(), ct, extra=[("Cache-Control", cc)])
                return
            self._send(404, {"error": "not found"}); return
        if rel in ("icon.png", "icon-192.png", "icon-512.png", "icon.svg") or \
           (rel.startswith("art/") and re.fullmatch(r"art/[a-z0-9_-]+\.(?:png|jpg|jpeg|webp)", rel)):
            fp = os.path.join(HERE, rel)
            if os.path.isfile(fp):
                if fp.endswith(".svg"): ct = "image/svg+xml"
                elif fp.endswith((".jpg", ".jpeg")): ct = "image/jpeg"
                elif fp.endswith(".webp"): ct = "image/webp"
                else: ct = "image/png"
                with open(fp, "rb") as f:
                    self._send(200, f.read(), ct, extra=[("Cache-Control", "max-age=86400")])
                return
            self._send(404, {"error": "not found"}); return
        m = re.fullmatch(r"/spot/(\d+\.(?:jpg|png))", p)
        if m:
            fp = os.path.join(SPOT_DIR, m.group(1))
            if os.path.isfile(fp):
                ct = "image/png" if fp.endswith(".png") else "image/jpeg"
                with open(fp, "rb") as f:
                    self._send(200, f.read(), ct, extra=[("Cache-Control", "public, max-age=31536000, immutable")])
                return
            self._send(404, {"error": "not found"}); return
        if not p.startswith("/api/"):
            self._send(404, {"error": "not found"}); return
        with _dblock:
            c = db()
            try:
                self._get_api(p, q, c)
            except Exception as _e:
                sentry_capture(_e, request={"url": p, "method": "GET"})
                raise
            finally:
                c.close()

    def do_POST(self):
        p, q = self._path()
        with _dblock:
            c = db()
            try:
                self._post_api(p, q, c)
            except Exception as _e:
                sentry_capture(_e, request={"url": p, "method": "POST"})
                raise
            finally:
                c.close()

    # -- GET api -----------------------------------------------------------
    def _get_api(self, p, q, c):
        if p == "/api/me":
            u = self._me(c)
            if not u:
                self._send(200, {"authed": False}); return
            self._send(200, {"authed": True, "profile": profile_dict(c, u)}); return

        if p == "/api/prompt":
            self._send(200, {"prompt": prompt_for_today(), "date": today_str()}); return

        if p == "/api/admin/seed-demo":
            if (q.get("secret", "") or "") != "lumen-demo-seed-9f3ac21b":
                self._send(403, {"error": "nope"}); return
            try:
                out = seed_demo_account(c)
                self._send(200, {"ok": True, **out}); return
            except Exception as e:
                self._send(500, {"error": repr(e)}); return

        if p == "/api/admin/seed-live":
            if (q.get("secret", "") or "") != "lumen-demo-seed-9f3ac21b":
                self._send(403, {"error": "nope"}); return
            try:
                out = seed_live_week(c)
                self._send(200, {"ok": True, **out}); return
            except Exception as e:
                self._send(500, {"error": repr(e)}); return

        if p == "/api/admin/survey":
            if (q.get("secret", "") or "") != "lumen-demo-seed-9f3ac21b":
                self._send(403, {"error": "nope"}); return
            try:
                rows = [dict(r) for r in c.execute(
                    "SELECT id,user_id,email,nps,data,created FROM survey ORDER BY id DESC LIMIT 500")]
                for r in rows:
                    try:
                        r["answers"] = json.loads(r.pop("data") or "{}")
                    except Exception:
                        r["answers"] = {}
                npses = [r["nps"] for r in rows if isinstance(r["nps"], int)]
                nps = None
                if npses:
                    prom = sum(1 for n in npses if n >= 9); det = sum(1 for n in npses if n <= 6)
                    nps = round(100 * (prom - det) / len(npses))
                self._send(200, {"count": len(rows), "nps": nps, "responses": rows}); return
            except Exception as e:
                self._send(500, {"error": repr(e)}); return

        if p == "/api/admin/emails":
            if (q.get("secret", "") or "") != "lumen-demo-seed-9f3ac21b":
                self._send(403, {"error": "nope"}); return
            try:
                prev = (q.get("preview") or "").strip()
                if prev:
                    u = user_by_email(c, "appreview@lumen.app") or \
                        c.execute("SELECT * FROM users WHERE is_bot=0 LIMIT 1").fetchone()
                    ctx = {"sessions": 5, "light": 640} if prev == "weekly_recap" else (
                          {"subject": "Guided journeys", "headline": "Let a tradition guide you.",
                           "paras": ["Lumen has narrated Journeys from real traditions.", "Start the one that calls to you."],
                           "cta": "Explore Journeys"} if prev == "tip" else {})
                    t = _email_tpl(prev, c, u, ctx)
                    if not t:
                        self._send(404, {"error": "unknown template"}); return
                    self._send(200, t[1], "text/html; charset=utf-8"); return
                self._send(200, email_admin_stats(c)); return
            except Exception as e:
                self._send(500, {"error": repr(e)}); return

        if p == "/api/admin/africa":
            if (q.get("secret", "") or "") != "lumen-demo-seed-9f3ac21b":
                self._send(403, {"error": "nope"}); return
            if q.get("do") == "recompute":
                # self-heal: recompute every real user's aggregates from their sessions
                fixed = []
                for u in c.execute("SELECT id FROM users WHERE COALESCE(is_bot,0)=0").fetchall():
                    uid = u["id"]
                    agg = c.execute("SELECT COUNT(*) n, COALESCE(SUM(minutes),0) m, COALESCE(SUM(light),0) l "
                                    "FROM sessions WHERE user_id=?", (uid,)).fetchone()
                    last = c.execute("SELECT MAX(day) d FROM sessions WHERE user_id=?", (uid,)).fetchone()["d"]
                    c.execute("UPDATE users SET total_sessions=?, total_minutes=?, light=?, last_day=? WHERE id=?",
                              (agg["n"], agg["m"], agg["l"], last, uid))
                    if agg["n"] == 0:
                        continue
                    fixed.append({"id": uid, "sessions": agg["n"]})
                c.commit()
                self._send(200, {"recomputed": len(fixed)}); return
            afr_cities = ("Cape Town", "Nairobi", "Cairo")
            def _isafr(lat, lon, city):
                if city in afr_cities:
                    return True
                try:
                    return (lat is not None and lon is not None and -36 <= lat <= 38 and -20 <= lon <= 52)
                except Exception:
                    return False
            rows = c.execute("SELECT s.id,s.user_id,s.lat,s.lon,s.city,s.ended,u.name,u.is_bot "
                             "FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.lat IS NOT NULL").fetchall()
            afr = [r for r in rows if _isafr(r["lat"], r["lon"], r["city"])]
            bots = sorted({(r["user_id"], r["name"], r["city"]) for r in afr if r["is_bot"]})
            real = [{"sid": r["id"], "user": r["name"], "city": r["city"],
                     "lat": round(r["lat"], 2), "lon": round(r["lon"], 2), "ended": r["ended"]}
                    for r in afr if not r["is_bot"]]
            out = {"african_sessions": len(afr),
                   "bot_users": [{"id": b[0], "name": b[1], "city": b[2]} for b in bots],
                   "real_sessions": real}
            if q.get("do") == "delete":
                ids = [r["id"] for r in afr]
                for i in range(0, len(ids), 400):
                    ch = ids[i:i + 400]
                    c.execute("DELETE FROM sessions WHERE id IN (%s)" % ",".join("?" * len(ch)), ch)
                deleted_users = 0
                for uid in sorted({r["user_id"] for r in afr if r["is_bot"]}):
                    if c.execute("SELECT COUNT(*) n FROM sessions WHERE user_id=?", (uid,)).fetchone()["n"] == 0:
                        c.execute("DELETE FROM achievements WHERE user_id=?", (uid,))
                        c.execute("DELETE FROM users WHERE id=? AND is_bot=1", (uid,))
                        deleted_users += 1
                # recompute aggregates for affected REAL users so they don't over-count
                recomputed = []
                for uid in sorted({r["user_id"] for r in afr if not r["is_bot"]}):
                    agg = c.execute("SELECT COUNT(*) n, COALESCE(SUM(minutes),0) m, COALESCE(SUM(light),0) l "
                                    "FROM sessions WHERE user_id=?", (uid,)).fetchone()
                    last = c.execute("SELECT MAX(day) d FROM sessions WHERE user_id=?", (uid,)).fetchone()["d"]
                    c.execute("UPDATE users SET total_sessions=?, total_minutes=?, light=?, last_day=? WHERE id=?",
                              (agg["n"], agg["m"], agg["l"], last, uid))
                    recomputed.append({"id": uid, "sessions_left": agg["n"]})
                c.commit()
                out["deleted_sessions"] = len(ids); out["deleted_bot_users"] = deleted_users
                out["recomputed_users"] = recomputed
            self._send(200, out); return

        if p == "/api/challenge":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            try:
                tz_off = max(-840, min(840, int(q.get("tz", "0"))))
            except Exception:
                tz_off = 0
            local_day = (datetime.now(timezone.utc) + timedelta(minutes=tz_off)).date().isoformat()
            row = c.execute("SELECT * FROM challenges WHERE user_id=? AND day=?", (u["id"], local_day)).fetchone()
            photo_today = bool(row["photo"]) if row else False
            new_today = bool(row["new_place"]) if row else False
            places = distinct_places(c, u["id"])
            # this user's passport preview: their most recent spots
            thumbs = [{"photo": r["photo"], "city": r["city"]}
                      for r in c.execute("SELECT photo,city FROM sessions WHERE user_id=? AND photo IS NOT NULL "
                                         "ORDER BY id DESC LIMIT 8", (u["id"],))]
            # community hook: spots shared to the map today
            shared_today = c.execute("SELECT COUNT(*) n FROM sessions WHERE day=? AND photo IS NOT NULL "
                                     "AND photo_share=1", (local_day,)).fetchone()["n"]
            nxt = next((m for m in PILG_MILESTONES if m > places), None)
            self._send(200, {
                "title": "Atlas",
                "blurb": "Collect the places you meditate. Travel somewhere new, keep a photo of your spot, and share it with the world.",
                "day": local_day,
                "streak": u["chal_streak"] or 0,
                "best": u["chal_best"] or 0,
                "places": places,
                "next_milestone": nxt,
                "photo_today": photo_today,
                "new_today": new_today,
                "new_bonus": PILG_NEW_PLACE,
                "photo_bonus": PILG_PHOTO,
                "thumbs": thumbs,
                "shared_today": shared_today,
            }); return

        if p == "/api/horoscope":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            try:
                tz_off = max(-840, min(840, int(q.get("tz", "0"))))
            except Exception:
                tz_off = 0
            local_day = (datetime.now(timezone.utc) + timedelta(minutes=tz_off)).date().isoformat()
            sign = sign_from_birthdate(u["birth_date"]) if u["birth_date"] else (u["sun_sign"] or "").lower()
            if sign not in ZODIAC_BY_KEY:
                self._send(200, {"need_sign": True,
                    "signs": [{"key": z[0], "name": z[2], "sanskrit": z[3], "glyph": z[1]} for z in ZODIAC]}); return
            h = personal_horoscope(c, u, local_day)
            z = ZODIAC_BY_KEY[sign]
            self._send(200, {"need_sign": False, "sign": z[0], "name": z[2], "sanskrit": z[3],
                "glyph": z[1], "lord": z[4], "date": local_day,
                "text": h["text"], "theme": h["theme"], "soundscape": h["soundscape"],
                "minutes": h.get("minutes", 10), "nakshatra": h.get("nakshatra"),
                "deity": h.get("deity"), "nak_theme": h.get("nak_theme"), "pada": h.get("pada"),
                "janma": h.get("janma"), "maha": h.get("maha"), "antar": h.get("antar"),
                "has_natal": bool(u["birth_time"])}); return

        if p == "/api/presence":
            today = today_str()
            row = c.execute("SELECT COUNT(*) n, COALESCE(SUM(light),0) l, COALESCE(SUM(minutes),0) m FROM sessions WHERE day=?", (today,)).fetchone()
            live = LIVE.count()
            self._send(200, {"now": live, "today_sessions": row["n"], "today_light": row["l"], "today_minutes": row["m"]}); return

        if p == "/api/map":
            scope = q.get("scope", "today")
            me0 = self._me(c)
            meid = me0["id"] if me0 else -1
            sql = """SELECT s.id id, s.lat lat, s.lon lon, s.city city, s.minutes minutes, s.soundscape soundscape,
                            s.ended ended, s.photo photo, s.photo_share pshare, u.name name, u.is_bot bot,
                            CASE WHEN s.user_id=? THEN 1 ELSE 0 END mine
                     FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.lat IS NOT NULL"""
            args = [meid]
            mine_scope = (scope == "mine")
            if scope == "today":
                sql += " AND s.day=?"; args.append(today_str())
            elif scope == "mine":
                if not me0:
                    self._send(401, {"error": "sign in"}); return
                sql += " AND s.user_id=?"; args.append(me0["id"])
            sql += " ORDER BY s.ended DESC LIMIT 1200"
            pts = []
            for r in c.execute(sql, args):
                pt = dict(r)
                # only reveal a photo publicly if the author chose to share it;
                # on your own "My places" map you always see your own photos
                if not (mine_scope or pt.pop("pshare", 0)):
                    pt["photo"] = None
                else:
                    pt.pop("pshare", None)
                pts.append(pt)
            resp = {"scope": scope, "points": pts}
            if scope == "mine":
                resp["places"] = len({(p["city"] or f"{round(p['lat'],2)},{round(p['lon'],2)}") for p in pts})
                resp["cities"] = sorted({p["city"] for p in pts if p["city"]})
            self._send(200, resp); return

        if p == "/api/leaderboard":
            scope = q.get("scope", "week")
            by = "minutes" if q.get("by") == "minutes" else "light"
            me = self._me(c)
            if scope == "all":
                col = "u.light" if by == "light" else "u.total_minutes"
                rows = c.execute(f"SELECT u.id id,u.name name,{col} val FROM users u WHERE u.name IS NOT NULL ORDER BY val DESC LIMIT 100").fetchall()
            else:
                wk = week_str() if scope == "week" else None
                day = today_str() if scope == "today" else None
                agg = "SUM(s.light)" if by == "light" else "SUM(s.minutes)"
                cond = "s.week=?" if scope == "week" else "s.day=?"
                arg = wk if scope == "week" else day
                rows = c.execute(f"""SELECT u.id id,u.name name,{agg} val
                                     FROM sessions s JOIN users u ON u.id=s.user_id
                                     WHERE {cond} GROUP BY u.id ORDER BY val DESC LIMIT 100""", (arg,)).fetchall()
            out = []
            for i, r in enumerate(rows):
                out.append({"rank": i + 1, "name": r["name"], "value": r["val"] or 0,
                            "you": bool(me and r["id"] == me["id"])})
            self._send(200, {"scope": scope, "by": by, "rows": out}); return

        if p == "/api/league":
            me = self._me(c)
            if not me:
                self._send(401, {"error": "sign in"}); return
            wk = week_str()
            rows = c.execute("""SELECT u.id id,u.name name, COALESCE(SUM(s.light),0) wl
                                FROM users u LEFT JOIN sessions s ON s.user_id=u.id AND s.week=?
                                WHERE u.name IS NOT NULL GROUP BY u.id""", (wk,)).fetchall()
            my_wl = next((r["wl"] for r in rows if r["id"] == me["id"]), 0)
            my_lg = league_for(my_wl)["name"]
            peers = [r for r in rows if league_for(r["wl"])["name"] == my_lg]
            peers.sort(key=lambda r: r["wl"], reverse=True)
            members = [{"rank": i + 1, "name": r["name"], "weekly_light": r["wl"],
                        "you": r["id"] == me["id"]} for i, r in enumerate(peers)]
            self._send(200, {"league": league_for(my_wl), "weekly_light": my_wl,
                             "members": members, "promote_zone": 5,
                             "relegate_zone": max(0, len(members) - 5)}); return

        if p == "/api/journal":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            kind = (q.get("kind", "") or "").strip()
            if kind in JOURNAL_KINDS:
                rows = c.execute("SELECT id,prompt,text,mood,reflection,shared,created,kind,pillar,place "
                                 "FROM journal WHERE user_id=? AND kind=? ORDER BY id DESC LIMIT 200",
                                 (u["id"], kind)).fetchall()
            else:
                rows = c.execute("SELECT id,prompt,text,mood,reflection,shared,created,kind,pillar,place "
                                 "FROM journal WHERE user_id=? ORDER BY id DESC LIMIT 200", (u["id"],)).fetchall()
            self._send(200, {"entries": [dict(r) for r in rows]}); return

        if p == "/api/pillars":
            u = self._me(c)
            lo = lifeos_get(u) if u else {"focus": []}
            focus = [f for f in (lo.get("focus") or []) if f in PILLARS]
            counts = {name: 0 for name in PILLARS}
            last = {}
            if u:
                for r in c.execute("SELECT pillar, COUNT(*) n, MAX(created) last FROM journal "
                                   "WHERE user_id=? AND kind='deep' AND pillar IS NOT NULL "
                                   "GROUP BY pillar", (u["id"],)).fetchall():
                    if r["pillar"] in counts:
                        counts[r["pillar"]] = r["n"]; last[r["pillar"]] = r["last"]
            out = []
            for name in PILLARS:
                ex = PILLAR_EXERCISES.get(name)
                out.append({"name": name, "title": ex[0] if ex else name,
                            "invitation": ex[1] if ex else "", "steps": ex[2] if ex else [],
                            "sittings": counts[name], "last": last.get(name)})
            done = sum(1 for n in PILLARS if counts[n] > 0)
            self._send(200, {"pillars": out, "focus": focus, "counts": counts,
                             "done": done, "total": len(PILLARS)}); return

        if p == "/api/journal/deep":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            pillar = (q.get("pillar", "") or "").strip()
            if pillar not in PILLARS:
                self._send(400, {"error": "unknown pillar"}); return
            ex = deep_exercise(c, u, pillar, chapter=q.get("chapter"))
            if not ex:
                self._send(404, {"error": "no exercise"}); return
            self._send(200, {"ready": True, **ex}); return

        if p == "/api/pillar":
            # Full lesson plan for one pillar — all chapters, with which are done
            # and which is next — so the app can show the list (like Journeys).
            u = self._me(c)
            name = (q.get("name", "") or "").strip()
            if name not in PILLARS:
                self._send(400, {"error": "unknown pillar"}); return
            plan = PILLAR_PLANS.get(name)
            chapters = plan[1] if plan else []
            arc = plan[0] if plan else ""
            done = 0
            if u:
                done = c.execute("SELECT COUNT(*) n FROM journal WHERE user_id=? AND "
                                 "kind='deep' AND pillar=?", (u["id"], name)).fetchone()["n"]
            n = len(chapters)
            nxt = (done % n) if n else 0
            rounds = (done // n) if n else 0
            out = []
            for i, ch in enumerate(chapters):
                out.append({"n": i + 1, "title": ch[0], "invitation": ch[1],
                            "steps": len(ch[2]), "done": (i < nxt) or (rounds > 0),
                            "next": (i == nxt)})
            self._send(200, {"pillar": name, "arc": arc, "chapters": out,
                             "total": n, "sittings": done, "rounds": rounds}); return

        if p == "/api/journal/season":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            ex = season_exercise(c, u)
            self._send(200, {"ready": True, **ex}); return

        if p == "/api/journal/week":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            wk = week_str()
            today = datetime.now(timezone.utc).date()
            monday = (today - timedelta(days=today.weekday())).isoformat()  # ISO-week start (UTC)
            counts = {k: 0 for k in JOURNAL_KINDS}
            for r in c.execute("SELECT COALESCE(kind,'daily') k, COUNT(*) n FROM journal "
                               "WHERE user_id=? AND substr(created,1,10)>=? GROUP BY k",
                               (u["id"], monday)).fetchall():
                if r["k"] in counts:
                    counts[r["k"]] += r["n"]
            touched = [k for k in JOURNAL_KINDS if counts[k] > 0]
            missing = [k for k in JOURNAL_KINDS if counts[k] == 0]
            self._send(200, {"week": wk, "counts": counts, "touched": touched,
                             "missing": missing, "complete": not missing}); return

        if p == "/api/journal/recommend":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            today = datetime.now(timezone.utc).date()
            monday = (today - timedelta(days=today.weekday())).isoformat()
            counts = {k: 0 for k in JOURNAL_KINDS}
            for r in c.execute("SELECT COALESCE(kind,'daily') k, COUNT(*) n FROM journal "
                               "WHERE user_id=? AND substr(created,1,10)>=? GROUP BY k",
                               (u["id"], monday)).fetchall():
                if r["k"] in counts:
                    counts[r["k"]] += r["n"]
            di = today.toordinal()
            # prefer a category still untouched this week (depth-first); else rotate by day
            order = ["deep", "season", "daily"]
            missing = [k for k in order if counts.get(k, 0) == 0]
            mode = missing[di % len(missing)] if missing else order[di % len(order)]
            lo = lifeos_get(u) or {}
            focus = [f for f in (lo.get("focus") or []) if f in PILLARS]
            pillar = None
            if mode == "deep":
                pool = focus or list(PILLARS)
                pillar = pool[di % len(pool)]
            titles = {"deep": (f"Go deep on {pillar}" if pillar else "Go deep on a pillar"),
                      "daily": "Write today's letter",
                      "season": "Name the season you're in"}
            reasons = {
                "deep": ((f"A guided sitting on your {pillar} pillar"
                          + (" — one of your focuses right now." if pillar in focus else "."))
                         if pillar else "A guided sitting on one of your life pillars."),
                "daily": "A few honest lines about today — the simplest way to keep the habit alive.",
                "season": "Step back from the day and reflect on the larger chapter you're living through.",
            }
            why = ("You haven't tended this one yet this week." if mode in missing
                   else "A gentle rotation, to keep all three alive.")
            self._send(200, {"mode": mode, "pillar": pillar, "title": titles[mode],
                             "reason": reasons[mode], "why": why,
                             "counts": counts, "missing": missing}); return

        if p == "/api/feed":
            me = self._me(c)
            uid = me["id"] if me else 0
            # hide: entries from users I blocked, entries I reported, and any entry
            # with 2+ distinct reports (community moderation per App Store Guideline 1.2)
            # shared spot photo-posts: a picture of where someone meditated.
            # feed id is the NEGATED session id so it can't collide with journal
            # ids and still flows through the existing report/block endpoints.
            spots = c.execute("""SELECT s.id sid, s.city city, s.minutes minutes, s.soundscape soundscape,
                                        s.mood mood, s.note note, s.photo photo, s.ended created,
                                        u.name name, u.id author_id
                                 FROM sessions s JOIN users u ON u.id=s.user_id
                                 WHERE s.photo_share=1 AND s.photo IS NOT NULL
                                   AND s.user_id NOT IN (SELECT blocked_id FROM mod_blocks WHERE blocker_id=?)
                                   AND (-s.id) NOT IN (SELECT entry_id FROM mod_reports WHERE reporter_id=?)
                                   AND (SELECT COUNT(*) FROM mod_reports r WHERE r.entry_id=-s.id) < 2
                                 ORDER BY s.id DESC LIMIT 60""", (uid, uid)).fetchall()
            # shared journal letters — but skip the ones tied to a shared spot
            # post (its note is already shown as the photo's caption)
            rows = c.execute("""SELECT j.id id, j.text text, j.mood mood, j.created created,
                                       u.name name, u.id author_id
                                FROM journal j JOIN users u ON u.id=j.user_id
                                WHERE j.shared=1
                                  AND j.user_id NOT IN (SELECT blocked_id FROM mod_blocks WHERE blocker_id=?)
                                  AND j.id NOT IN (SELECT entry_id FROM mod_reports WHERE reporter_id=?)
                                  AND (SELECT COUNT(*) FROM mod_reports r WHERE r.entry_id=j.id) < 2
                                  AND (j.session_id IS NULL OR j.session_id NOT IN
                                       (SELECT id FROM sessions WHERE photo_share=1 AND photo IS NOT NULL))
                                ORDER BY j.id DESC LIMIT 60""", (uid, uid)).fetchall()
            feed = []
            for r in spots:
                d = dict(r)
                feed.append({"type": "spot", "id": -d["sid"], "name": d["name"],
                             "author_id": d["author_id"], "created": d["created"],
                             "photo": d["photo"], "city": d["city"], "minutes": d["minutes"],
                             "soundscape": d["soundscape"], "mood": d["mood"],
                             "text": (d["note"] or "").strip()})
            for r in rows:
                d = dict(r); d["type"] = "letter"; feed.append(d)
            feed.sort(key=lambda f: f["created"] or "", reverse=True)
            self._send(200, {"feed": feed[:60], "me": uid}); return

        if p == "/api/achievements":
            u = self._me(c)
            have = {}
            total = max(1, c.execute("SELECT COUNT(*) n FROM users WHERE name IS NOT NULL").fetchone()["n"])
            if u:
                have = {r["code"]: r["created"] for r in c.execute("SELECT code,created FROM achievements WHERE user_id=?", (u["id"],))}
            out = []
            for a in ACHIEVEMENTS:
                earned = c.execute("SELECT COUNT(DISTINCT user_id) n FROM achievements WHERE code=?", (a[0],)).fetchone()["n"]
                out.append({"code": a[0], "title": a[1], "desc": a[2], "emoji": a[3],
                            "unlocked": a[0] in have, "created": have.get(a[0]),
                            "pct": round(100.0 * earned / total)})
            self._send(200, {"achievements": out}); return

        if p == "/api/collection":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            self._send(200, {"items": collection_for(c, u), "equipped": u["equipped"]}); return

        if p == "/api/companions":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            self._send(200, {"companions": companions_for(c, u), "equipped": u["companion"],
                             "motes": u["motes"] or 0}); return

        if p == "/api/shop":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            self._send(200, {"shop": shop_for(c, u), "motes": u["motes"] or 0,
                             "member_days": member_days(u)}); return

        if p == "/api/nft":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            self._send(200, {"artifacts": artifacts_for(c, u), "equipped": u["equipped"]}); return

        if p == "/api/lifeos":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            self._send(200, {"lifeos": lifeos_get(u), "pillars": PILLARS}); return

        if p == "/api/lifeos/prompts":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            self._send(200, {"prompts": daily_prompts(c, u)}); return

        if p == "/api/notif/prefs":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            pr = _notif_prefs(c, u["id"])
            self._send(200, {"enabled": bool(pr["enabled"]),
                             "quiet_start": pr["quiet_start"], "quiet_end": pr["quiet_end"],
                             "tz_offset_min": pr["tz_offset_min"], "sto": bool(pr["sto"]),
                             "cats": json.loads(pr["cats"] or "{}"),
                             "registered": bool(_tokens_for(c, u["id"]))}); return

        if p == "/api/admin/notifications":
            u, err = self._owner(c)
            if err:
                self._send(*err); return
            self._send(200, notif_admin_stats(c)); return

        if p == "/api/admin/overview":
            u, err = self._owner(c)
            if err:
                self._send(*err); return
            resp = admin_overview(c)
            resp["pipeline"] = PIPELINE
            resp["materials"] = MATERIALS
            resp["outlets"] = OUTLETS
            resp["dist_cols"] = DIST_COLS
            resp["state"] = _mkt_state(c)
            resp["subtasks"] = subtasks_by_parent(c)
            self._send(200, resp); return

        if p == "/api/admin/analytics":
            u, err = self._owner(c)
            if err:
                self._send(*err); return
            try:
                days = max(1, min(90, int((q.get("days") or ["30"])[0])))
            except Exception:
                days = 30
            self._send(200, admin_analytics(c, days)); return

        self._send(404, {"error": "not found"})

    # -- POST api ----------------------------------------------------------
    def _post_api(self, p, q, c):
        if p == "/api/sms/inbound":
            # Twilio inbound webhook (form-encoded). Keeps our DB in sync with Twilio's
            # own carrier-level STOP/START handling so we never try to text an opt-out.
            import urllib.parse as _up
            try:
                n = int(self.headers.get("Content-Length", "0"))
                raw = (self.rfile.read(n) or b"").decode("utf-8", "replace")
            except Exception:
                raw = ""
            params = _up.parse_qsl(raw, keep_blank_values=True)
            # Validate X-Twilio-Signature when an auth token is configured (reject spoofs).
            tok = os.environ.get("TWILIO_AUTH_TOKEN")
            if tok:
                _b64 = base64  # hmac/hashlib/base64 are module-level; a local import here
                               # would shadow them across this whole function and break login
                url = os.environ.get("TWILIO_WEBHOOK_URL") or ("https://%s%s" % (self.headers.get("Host", ""), self.path))
                base = url + "".join(k + v for k, v in sorted(params))
                mac = _b64.b64encode(hmac.new(tok.encode(), base.encode("utf-8"), hashlib.sha1).digest()).decode()
                sig = self.headers.get("X-Twilio-Signature", "")
                if not (sig and hmac.compare_digest(mac, sig)):
                    self._send(403, '<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
                               "text/xml; charset=utf-8"); return
            form = {}
            for k, v in params:
                form.setdefault(k, v)
            frm = (form.get("From", "") or "").strip()
            body = (form.get("Body", "") or "").strip().lower()
            body = re.sub(r'[^a-z ]', '', body).strip()
            if frm:
                if body in ("stop", "stopall", "stop all", "unsubscribe", "cancel", "end", "quit", "optout", "revoke"):
                    c.execute("UPDATE users SET sms_optout=1 WHERE phone=?", (frm,)); c.commit()
                elif body in ("start", "unstop", "yes"):
                    c.execute("UPDATE users SET sms_optout=0 WHERE phone=?", (frm,)); c.commit()
            self._send(200, '<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
                       "text/xml; charset=utf-8"); return

        if p == "/api/admin/sms/test":
            u, err = self._owner(c)
            if err:
                self._send(*err); return
            d = self._body()
            to = normalize_phone(d.get("to")) or (u["phone"] if "phone" in u.keys() else None)
            if not to:
                self._send(400, {"error": "No phone to text. Pass {\"to\":\"+1...\"} or save a phone on your account."}); return
            ok = send_sms(to, "Lumen — your SMS notification engine is wired up and working. Reply STOP to opt out.")
            self._send(200, {"ok": ok, "to": to, "mode": SMS_MODE}); return

        if p == "/api/ev":
            # First-party analytics ingest (no auth — onboarding happens pre-signup).
            d = self._body()
            aid = re.sub(r"[^A-Za-z0-9_-]", "", str(d.get("aid") or ""))[:40] or None
            try:
                u = self._me(c)
            except Exception:
                u = None
            uid = u["id"] if u else None
            evs = d.get("events") or []
            if isinstance(evs, dict):
                evs = [evs]
            n = 0
            for e in evs[:25]:
                if not isinstance(e, dict):
                    continue
                name = str(e.get("name") or "")[:60]
                if not name:
                    continue
                screen = str(e.get("screen") or "")[:40] or None
                props = e.get("props")
                props = json.dumps(props)[:500] if props is not None else None
                c.execute("INSERT INTO events(anon_id,user_id,name,props,screen,created) VALUES(?,?,?,?,?,?)",
                          (aid, uid, name, props, screen, now_iso()))
                n += 1
            if n:
                c.commit()
            self._send(200, {"ok": True, "n": n}); return

        if p == "/api/waitlist":
            email = (self._body().get("email") or "").strip().lower()
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                self._send(400, {"error": "Enter a valid email."}); return
            try:
                c.execute("INSERT OR IGNORE INTO journal_waitlist(email,created) VALUES(?,?)",
                          (email, now_iso())); c.commit()
            except Exception as e:
                print('[lumen] waitlist insert failed:', e, flush=True)
                self._send(500, {"error": "Could not save — please try again."}); return
            self._send(200, {"ok": True}); return

        if p == "/api/survey":
            d = self._body()
            answers = d.get("answers")
            if not isinstance(answers, dict) or not answers:
                self._send(400, {"error": "No answers provided."}); return
            me = self._me(c)
            email = ((d.get("email") or (me["email"] if me else "")) or "").strip().lower()[:200]
            try:
                nps = int(d.get("nps")) if d.get("nps") not in (None, "") else None
            except Exception:
                nps = None
            try:
                payload = json.dumps(answers)[:60000]
                c.execute("INSERT INTO survey(user_id,email,nps,data,created) VALUES(?,?,?,?,?)",
                          ((me["id"] if me else None), email or None, nps, payload, now_iso()))
                c.commit()
            except Exception as e:
                print('[lumen] survey insert failed:', e, flush=True)
                self._send(500, {"error": "Could not save — please try again."}); return
            self._send(200, {"ok": True}); return

        if p == "/api/premium/interest":
            # In-app "I want Premium" tap. Until RevenueCat is live this records
            # intent (deduped by user) so we can gauge demand + reach out.
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            try:
                c.execute("INSERT OR IGNORE INTO premium_waitlist(user_id,email,created) VALUES(?,?,?)",
                          (u["id"], u["email"], now_iso())); c.commit()
            except Exception as e:
                print('[lumen] premium interest insert failed:', e, flush=True)
                self._send(500, {"error": "Could not save — please try again."}); return
            self._send(200, {"ok": True, "waitlisted": True}); return

        if p == "/api/feed/report":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            try:
                eid = int(self._body().get("id") or 0)
            except Exception:
                eid = 0
            if eid:
                c.execute("INSERT OR IGNORE INTO mod_reports(entry_id,reporter_id,created) VALUES(?,?,?)",
                          (eid, u["id"], now_iso()))
                c.commit()
            self._send(200, {"ok": True}); return

        if p == "/api/feed/block":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            try:
                bid = int(self._body().get("author_id") or 0)
            except Exception:
                bid = 0
            if bid and bid != u["id"]:
                c.execute("INSERT OR IGNORE INTO mod_blocks(blocker_id,blocked_id,created) VALUES(?,?,?)",
                          (u["id"], bid, now_iso()))
                c.commit()
            self._send(200, {"ok": True}); return

        if p == "/api/push/register":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            d = self._body()
            tok = (d.get("token") or "").strip()
            if not tok.startswith("ExponentPushToken"):
                self._send(400, {"error": "bad token"}); return
            plat = (d.get("platform") or "ios")[:16]
            c.execute("INSERT INTO push_tokens(user_id,token,platform,created,updated) VALUES(?,?,?,?,?) "
                      "ON CONFLICT(token) DO UPDATE SET user_id=excluded.user_id, updated=excluded.updated",
                      (u["id"], tok, plat, now_iso(), now_iso()))
            pr = _notif_prefs(c, u["id"])  # ensure defaults exist
            if d.get("tz_offset_min") is not None:
                try:
                    c.execute("UPDATE notif_prefs SET tz_offset_min=?, updated=? WHERE user_id=?",
                              (int(d["tz_offset_min"]), now_iso(), u["id"]))
                except Exception:
                    pass
            c.commit()
            self._send(200, {"ok": True}); return

        if p == "/api/notif/prefs":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            d = self._body()
            pr = _notif_prefs(c, u["id"])
            enabled = 1 if d.get("enabled", bool(pr["enabled"])) else 0
            sto = 1 if d.get("sto", bool(pr["sto"])) else 0
            cats = pr["cats"]
            if isinstance(d.get("cats"), dict):
                cats = json.dumps({k: (1 if d["cats"].get(k, 1) else 0) for k in NOTIF_CATS})
            qs = pr["quiet_start"]; qe = pr["quiet_end"]; tz = pr["tz_offset_min"]; ph = pr["pref_hour"]
            try:
                if d.get("quiet_start") is not None: qs = max(0, min(23, int(d["quiet_start"])))
                if d.get("quiet_end") is not None: qe = max(0, min(23, int(d["quiet_end"])))
                if d.get("tz_offset_min") is not None: tz = int(d["tz_offset_min"])
                if d.get("pref_hour") is not None: ph = max(0, min(23, int(d["pref_hour"])))
            except Exception:
                pass
            c.execute("UPDATE notif_prefs SET enabled=?,sto=?,cats=?,quiet_start=?,quiet_end=?,tz_offset_min=?,pref_hour=?,updated=? WHERE user_id=?",
                      (enabled, sto, cats, qs, qe, tz, ph, now_iso(), u["id"]))
            c.commit()
            self._send(200, {"ok": True}); return

        if p == "/api/sms/prefs":
            # Manage SMS reminders after signup: add/change number, opt in/out.
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            d = self._body()
            phone = normalize_phone(d.get("phone"))
            if d.get("phone") and not phone:
                self._send(400, {"error": "That doesn't look like a valid mobile number."}); return
            consent = 1 if (phone and d.get("sms_consent")) else 0
            # Explicit in-app opt-in clears any prior STOP flag; opting out sets consent off.
            optout = 0 if consent else (u["sms_optout"] if "sms_optout" in u.keys() else 0)
            c.execute("UPDATE users SET phone=?, sms_consent=?, sms_optout=? WHERE id=?",
                      (phone, consent, optout, u["id"]))
            c.commit()
            self._send(200, {"ok": True, "phone": phone, "sms_consent": consent}); return

        if p == "/api/notif/opened":
            d = self._body()
            try:
                nid = int(d.get("id") or 0)
            except Exception:
                nid = 0
            if nid:
                c.execute("UPDATE notif_log SET opened=? WHERE id=? AND opened IS NULL", (now_iso(), nid))
                c.commit()
            self._send(200, {"ok": True}); return

        if p == "/api/admin/notify/test":
            u, err = self._owner(c)
            if err:
                self._send(*err); return
            toks = _tokens_for(c, u["id"])
            if not toks:
                self._send(400, {"error": "No push token registered for your account yet. Open the app (build with push) first."}); return
            ok = expo_push_send(c, toks, "Lumen — test ✨", "Your notification service is wired up.", {"category": "test"})
            self._send(200, {"ok": ok, "tokens": len(toks)}); return

        if p == "/api/admin/notify/broadcast":
            u, err = self._owner(c)
            if err:
                self._send(*err); return
            d = self._body()
            title = (d.get("title") or "").strip()[:60]
            body = (d.get("body") or "").strip()[:160]
            if not title or not body:
                self._send(400, {"error": "title and body required"}); return
            dk = "broadcast:" + hashlib.sha1((title + body + now_iso()).encode()).hexdigest()[:10]
            sent = 0
            for r in c.execute("SELECT DISTINCT user_id FROM push_tokens").fetchall():
                toks = _tokens_for(c, r["user_id"])
                ok = expo_push_send(c, toks, title, body, {"category": "broadcast"})
                c.execute("INSERT INTO notif_log(user_id,category,title,body,dedupe_key,status,created,sent) "
                          "VALUES(?,?,?,?,?,?,?,?)",
                          (r["user_id"], "broadcast", title, body, dk, "sent" if ok else "failed",
                           now_iso(), now_iso() if ok else None))
                sent += 1 if ok else 0
            c.commit()
            self._send(200, {"ok": True, "sent": sent}); return

        if p == "/api/admin/task":
            u, err = self._owner(c)
            if err:
                self._send(*err); return
            d = self._body()
            key = (d.get("key") or "").strip()
            status = (d.get("status") or "").strip()
            if status not in ("todo", "doing", "done"):
                self._send(400, {"error": "bad request"}); return
            # key is either a task/outlet key, or a checkbox sub-step "key#idx"
            base, _, idx = key.partition("#")
            task = next((t for t in PIPELINE if t["key"] == base), None) or OUTLET_BY_KEY.get(base)
            if not task or (idx and not (idx.isdigit() and int(idx) < len(task["steps"]))):
                self._send(400, {"error": "bad request"}); return
            c.execute("INSERT INTO mkt_state(key,status,note,updated) VALUES(?,?,?,?) "
                      "ON CONFLICT(key) DO UPDATE SET status=excluded.status, updated=excluded.updated",
                      (key, status, d.get("note"), datetime.now(timezone.utc).isoformat()))
            c.commit()
            self._send(200, {"ok": True, "key": key, "status": status}); return

        if p == "/api/admin/subtask":
            u, err = self._owner(c)
            if err:
                self._send(*err); return
            d = self._body(); act = (d.get("action") or "").strip()
            if act == "add":
                parent = (d.get("parent") or "").strip()[:64]
                text = (d.get("text") or "").strip()[:200]
                if not parent or not text:
                    self._send(400, {"error": "parent + text required"}); return
                pos = (c.execute("SELECT COALESCE(MAX(pos),-1)+1 n FROM mkt_subtasks WHERE parent=?", (parent,)).fetchone()["n"])
                cur = c.execute("INSERT INTO mkt_subtasks(parent,text,status,pos,created) VALUES(?,?,?,?,?)",
                                (parent, text, "todo", pos, now_iso()))
                c.commit()
                self._send(200, {"ok": True, "id": cur.lastrowid, "parent": parent, "text": text, "status": "todo"}); return
            if act == "toggle":
                try: sid = int(d.get("id") or 0)
                except Exception: sid = 0
                status = "done" if d.get("done") else "todo"
                c.execute("UPDATE mkt_subtasks SET status=? WHERE id=?", (status, sid)); c.commit()
                self._send(200, {"ok": True, "id": sid, "status": status}); return
            if act == "delete":
                try: sid = int(d.get("id") or 0)
                except Exception: sid = 0
                c.execute("DELETE FROM mkt_subtasks WHERE id=?", (sid,)); c.commit()
                self._send(200, {"ok": True, "id": sid}); return
            self._send(400, {"error": "bad action"}); return

        if p == "/api/signup":
            d = self._body()
            email = (d.get("email") or "").strip().lower()
            pw = d.get("password") or ""
            name = (d.get("name") or "").strip() or (email.split("@")[0] if email else "")
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) or len(pw) < 6:
                self._send(400, {"error": "Enter a valid email and a password of at least 6 characters."}); return
            _fix = email_typo_fix(email)
            if _fix:
                self._send(400, {"error": "That email looks mistyped — did you mean %s?" % _fix}); return
            if user_by_email(c, email):
                self._send(400, {"error": "That email already has an account — sign in instead."}); return
            bd = (d.get("birth_date") or "").strip() or None
            sign = sign_from_birthdate(bd) if bd else None
            bt = (d.get("birth_time") or "").strip() or None
            bp = (d.get("birth_place") or "").strip()[:120] or None
            try:
                btz = int(d.get("birth_tz")) if d.get("birth_tz") is not None else None
            except Exception:
                btz = None
            phone = normalize_phone(d.get("phone"))
            sms_consent = 1 if (phone and d.get("sms_consent")) else 0
            salt = secrets.token_hex(16)
            c.execute("INSERT INTO users(email,name,salt,hash,birth_date,birth_time,birth_place,birth_tz,sun_sign,phone,sms_consent,created) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                      (email, name, salt, _hash_pw(pw, salt), bd, bt, bp, btz, sign, phone, sms_consent, now_iso()))
            c.commit()
            try:
                nu = user_by_email(c, email)
                if nu:
                    threading.Thread(target=lambda: _welcome_async(nu["id"]), daemon=True).start()
            except Exception:
                pass
            tok = new_session(email)
            self._send(200, {"ok": True}, extra=[("Set-Cookie", _cookie_hdr(tok))]); return

        if p == "/api/login":
            d = self._body()
            email = (d.get("email") or "").strip().lower()
            pw = d.get("password") or ""
            u = user_by_email(c, email)
            if not u or not u["salt"] or not hmac.compare_digest(_hash_pw(pw, u["salt"]), u["hash"] or ""):
                self._send(400, {"error": "Wrong email or password."}); return
            tok = new_session(email)
            self._send(200, {"ok": True}, extra=[("Set-Cookie", _cookie_hdr(tok))]); return

        if p == "/api/logout":
            tok = self._cookie("lumen_sess")
            SESSIONS.pop(tok, None)
            self._send(200, {"ok": True}, extra=[("Set-Cookie", "lumen_sess=; Path=/; Max-Age=0")]); return

        if p == "/api/forgot":
            # Request a reset code. Always reply ok (never reveal whether the email exists).
            d = self._body()
            email = (d.get("email") or "").strip().lower()
            if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                u = user_by_email(c, email)
                if u:
                    row = c.execute("SELECT sent FROM password_resets WHERE email=?", (email,)).fetchone()
                    # throttle: at most one code per 60s
                    if not (row and row["sent"] and time.time() - row["sent"] < 60):
                        code = "%06d" % secrets.randbelow(1000000)
                        ch = hashlib.sha256(code.encode()).hexdigest()
                        c.execute("INSERT INTO password_resets(email,code_hash,expires,tries,sent) VALUES(?,?,?,0,?) "
                                  "ON CONFLICT(email) DO UPDATE SET code_hash=excluded.code_hash,expires=excluded.expires,tries=0,sent=excluded.sent",
                                  (email, ch, time.time() + 900, time.time()))
                        c.commit()
                        send_email(email, "Your Lumen reset code",
                                   "Your Lumen password reset code is %s\n\nIt expires in 15 minutes. "
                                   "If you didn't ask to reset your password, you can ignore this email." % code,
                                   "<div style=\"font:16px/1.6 -apple-system,system-ui,sans-serif;color:#1a1326\">"
                                   "<p>Your Lumen password reset code is:</p>"
                                   "<p style=\"font-size:30px;font-weight:800;letter-spacing:4px;color:#b8860b\">%s</p>"
                                   "<p style=\"color:#666\">It expires in 15 minutes. If you didn't ask to reset your "
                                   "password, you can safely ignore this email.</p></div>" % code)
            self._send(200, {"ok": True}); return

        if p == "/api/reset":
            d = self._body()
            email = (d.get("email") or "").strip().lower()
            code = (d.get("code") or "").strip()
            pw = d.get("password") or ""
            if len(pw) < 6:
                self._send(400, {"error": "Password needs at least 6 characters."}); return
            row = c.execute("SELECT code_hash,expires,tries FROM password_resets WHERE email=?", (email,)).fetchone()
            if not row or (row["expires"] or 0) < time.time():
                self._send(400, {"error": "That code has expired. Request a new one."}); return
            if (row["tries"] or 0) >= 5:
                c.execute("DELETE FROM password_resets WHERE email=?", (email,)); c.commit()
                self._send(400, {"error": "Too many attempts. Request a new code."}); return
            if not hmac.compare_digest(hashlib.sha256(code.encode()).hexdigest(), row["code_hash"] or ""):
                c.execute("UPDATE password_resets SET tries=tries+1 WHERE email=?", (email,)); c.commit()
                self._send(400, {"error": "That code isn't right."}); return
            u = user_by_email(c, email)
            if not u:
                self._send(400, {"error": "That code isn't right."}); return
            salt = secrets.token_hex(16)
            c.execute("UPDATE users SET salt=?, hash=? WHERE id=?", (salt, _hash_pw(pw, salt), u["id"]))
            c.execute("DELETE FROM password_resets WHERE email=?", (email,))
            c.commit()
            # invalidate any existing sessions for this email, then sign them in fresh
            for t in [t for t, v in list(SESSIONS.items()) if v and v[0] == email]:
                SESSIONS.pop(t, None)
            tok = new_session(email)
            self._send(200, {"ok": True}, extra=[("Set-Cookie", _cookie_hdr(tok))]); return

        if p == "/api/tts":
            audio = eleven_tts(self._body().get("text"))
            if not audio:
                self._send(503, {"error": "tts unavailable"}); return
            self._send(200, audio, "audio/mpeg", extra=[("Cache-Control", "public, max-age=604800")]); return

        if p == "/api/account/delete":
            # App Store requirement (Guideline 5.1.1(v)): let users delete their account
            # and all associated data in-app. Irreversible.
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            uid = u["id"]
            for tbl in ("sessions", "journal", "achievements", "items", "companions", "user_notes"):
                try:
                    c.execute("DELETE FROM %s WHERE user_id=?" % tbl, (uid,))
                except Exception:
                    pass
            c.execute("DELETE FROM users WHERE id=?", (uid,))
            c.commit()
            try:
                LIVE.remove(uid)
            except Exception:
                pass
            tok = self._cookie("lumen_sess")
            SESSIONS.pop(tok, None)
            self._send(200, {"ok": True}, extra=[("Set-Cookie", "lumen_sess=; Path=/; Max-Age=0")]); return

        if p == "/api/location":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            d = self._body()
            try:
                lat = _fuzz(float(d["lat"])); lon = _fuzz(float(d["lon"]))
            except Exception:
                self._send(400, {"error": "bad coords"}); return
            city = nearest_city(lat, lon) or (d.get("city") or u["city"] or "").strip() or None
            c.execute("UPDATE users SET lat=?,lon=?,city=? WHERE id=?", (lat, lon, city, u["id"]))
            c.commit()
            self._send(200, {"ok": True, "lat": lat, "lon": lon, "city": city}); return

        if p == "/api/horoscope/sign":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            d = self._body()
            sign = (d.get("sign") or "").lower().strip()
            bd = (d.get("birth_date") or "").strip()
            if bd and not sign:
                sign = sign_from_birthdate(bd) or ""
            if sign not in ZODIAC_BY_KEY:
                self._send(400, {"error": "pick a valid sign"}); return
            c.execute("UPDATE users SET sun_sign=?, birth_date=COALESCE(?,birth_date), horo=NULL, horo_day=NULL WHERE id=?",
                      (sign, bd or None, u["id"]))
            c.commit()
            z = ZODIAC_BY_KEY[sign]
            self._send(200, {"ok": True, "sign": z[0], "name": z[2], "sanskrit": z[3], "glyph": z[1]}); return

        if p == "/api/natal":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            d = self._body()
            bd = (d.get("birth_date") or u["birth_date"] or "").strip() or None
            bt = (d.get("birth_time") or "").strip() or None
            bp = (d.get("birth_place") or "").strip()[:120] or None
            try:
                btz = int(d.get("birth_tz")) if d.get("birth_tz") is not None else u["birth_tz"]
            except Exception:
                btz = u["birth_tz"]
            sign = sign_from_birthdate(bd) if bd else (u["sun_sign"] or None)
            c.execute("UPDATE users SET birth_date=COALESCE(?,birth_date), birth_time=?, birth_place=?, "
                      "birth_tz=?, sun_sign=COALESCE(?,sun_sign), horo=NULL, horo_day=NULL WHERE id=?",
                      (bd, bt, bp, btz, sign, u["id"]))
            c.commit()
            self._send(200, {"ok": True}); return

        if p == "/api/goal":
            # The meditation pledge: how many days/week the user commits to.
            # Recorded on the profile for the notification system + record-keeping.
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            try:
                days = int(self._body().get("days"))
            except Exception:
                days = 0
            days = max(1, min(7, days))
            c.execute("UPDATE users SET goal_days=? WHERE id=?", (days, u["id"]))
            c.commit()
            self._send(200, {"ok": True, "goal_days": days}); return

        if p == "/api/session/start":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            LIVE.add(u["id"])
            self._send(200, {"ok": True, "started": now_iso()}); return

        if p == "/api/session/complete":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            LIVE.remove(u["id"])
            d = self._body()
            try:
                minutes = max(1, min(240, int(d.get("minutes") or 0)))
            except Exception:
                self._send(400, {"error": "bad minutes"}); return
            ss = (d.get("soundscape") or "silence")
            mood = (d.get("mood") or "")[:24]
            note = (d.get("note") or "")[:2000]
            lat = u["lat"]; lon = u["lon"]; city = u["city"]
            raw_lat = u["lat"]; raw_lon = u["lon"]   # pre-fuzz coords, for a stable place key
            if d.get("lat") is not None and d.get("lon") is not None:
                try:
                    raw_lat = float(d["lat"]); raw_lon = float(d["lon"])
                    lat = _fuzz(raw_lat); lon = _fuzz(raw_lon)
                    city = nearest_city(lat, lon) or d.get("city") or city
                except Exception:
                    pass
            sess_pk = place_key(raw_lat, raw_lon)
            dt = datetime.now(timezone.utc)
            try:
                tz_off = max(-840, min(840, int(d.get("tz_offset_min") or 0)))
            except Exception:
                tz_off = 0
            local_dt = dt + timedelta(minutes=tz_off)
            local_day = local_dt.date().isoformat()
            # streak
            last = u["last_day"]
            streak = u["streak"] or 0
            td = dt.date()
            if last == td.isoformat():
                pass  # already practiced today; keep streak
            elif last == (td - timedelta(days=1)).isoformat():
                streak += 1
            else:
                streak = 1
            best = max(u["best_streak"] or 0, streak)
            # light
            light = compute_light(minutes, streak, dt)
            lesson_code = (d.get("lesson") or "")[:32] or None
            cur = c.execute("""INSERT INTO sessions(user_id,minutes,soundscape,light,lat,lon,city,mood,note,started,ended,day,week,lesson,pk)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (u["id"], minutes, ss, light, lat, lon, city, mood, note,
                       dt.isoformat(), dt.isoformat(), td.isoformat(), week_str(td), lesson_code, sess_pk))
            sid = cur.lastrowid
            # spot photo: a picture of where you sat (optional). photo_share gates
            # whether it appears on the public map / community feed.
            photo_url = save_spot_photo(sid, d.get("photo")) if d.get("photo") else None
            if photo_url:
                c.execute("UPDATE sessions SET photo=?, photo_share=? WHERE id=?",
                          (photo_url, 1 if d.get("photo_share") else 0, sid))
            # Atlas: photo-streak + places passport (travel reward)
            chal_prog, chal_newly, chal_bonus, chal_fields = eval_pilgrimage(
                c, u, local_day, sess_pk, bool(photo_url))
            cs = chal_fields.get("chal_streak"); cb = chal_fields.get("chal_best"); cl = chal_fields.get("chal_last_day")
            add_light = light + (chal_bonus if chal_newly else 0)
            new_light = (u["light"] or 0) + add_light
            old_lvl = level_for(u["light"])[0]
            c.execute("""UPDATE users SET light=?,streak=?,best_streak=?,last_day=?,
                         total_minutes=total_minutes+?,total_sessions=total_sessions+?,
                         motes=COALESCE(motes,0)+?,
                         chal_streak=COALESCE(?,chal_streak),chal_best=COALESCE(?,chal_best),chal_last_day=COALESCE(?,chal_last_day),
                         lat=COALESCE(?,lat),lon=COALESCE(?,lon),city=COALESCE(?,city) WHERE id=?""",
                      (new_light, streak, best, td.isoformat(), minutes, 1, add_light,
                       cs, cb, cl, lat, lon, city, u["id"]))
            trk = (d.get("track") or "")[:32]
            if trk:
                c.execute("UPDATE users SET last_journey=? WHERE id=?", (trk, u["id"]))
            if note.strip():
                c.execute("INSERT INTO journal(user_id,prompt,text,mood,shared,session_id,created) VALUES(?,?,?,?,?,?,?)",
                          (u["id"], "", note.strip(), mood, 1 if d.get("share") else 0, sid, now_iso()))
            u2 = c.execute("SELECT * FROM users WHERE id=?", (u["id"],)).fetchone()
            new_ach = check_achievements(c, u2, minutes, dt)
            if d.get("lesson") and "pilgrim" not in {r["code"] for r in c.execute("SELECT code FROM achievements WHERE user_id=?", (u["id"],))}:
                c.execute("INSERT OR IGNORE INTO achievements(user_id,code,created) VALUES(?,?,?)", (u["id"], "pilgrim", now_iso()))
                new_ach.append("pilgrim")
            try:
                notif_on_complete(c, u2, new_ach, level_for(new_light)[0] > old_lvl, streak)
            except Exception as _e:
                print("notif_on_complete error:", _e)
            c.commit()
            new_lvl = level_for(new_light)[0]
            self._send(200, {
                "ok": True, "light_earned": light, "motes_earned": add_light, "streak": streak,
                "photo": photo_url,
                "leveled_up": new_lvl > old_lvl, "level": new_lvl,
                "new_achievements": [{"code": a, "title": ACH_BY_CODE[a][1], "emoji": ACH_BY_CODE[a][3]} for a in new_ach],
                "multiplier": round(streak_multiplier(streak), 2),
                "time_bonus": time_bonus(dt)[1],
                "challenge": {"progress": chal_prog, "newly_done": chal_newly,
                              "bonus": chal_bonus if chal_newly else 0,
                              "new_place": chal_prog.get("new_place", False),
                              "places": distinct_places(c, u["id"]),
                              "streak": cs if cs is not None else (u["chal_streak"] or 0)},
            }); return

        if p == "/api/journal":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            d = self._body()
            text = (d.get("text") or "").strip()
            if not text:
                self._send(400, {"error": "write something first"}); return
            prompt = (d.get("prompt") or "")[:300]
            kind = (d.get("kind") or "daily").strip().lower()
            if kind not in JOURNAL_KINDS:
                kind = "daily"
            pillar = (d.get("pillar") or "").strip()[:24]
            if kind != "deep" or pillar not in PILLARS:
                pillar = None
            place = (d.get("place") or "").strip()[:80] if kind == "season" else None
            # the Keeper reflects back + infers mood (best-effort; never blocks the save)
            refl = journal_reflect(prompt, text, kind=kind, pillar=pillar, place=place)
            mood = ((d.get("mood") or refl["mood"] or "")).strip()[:24]
            c.execute("INSERT INTO journal(user_id,prompt,text,mood,reflection,shared,created,kind,pillar,place) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (u["id"], prompt, text[:2000], mood, refl["reflection"],
                       1 if d.get("share") else 0, now_iso(), kind, pillar, place))
            new_ach = award_journal_ach(c, u)
            c.commit()
            total = c.execute("SELECT COUNT(*) n FROM journal WHERE user_id=?", (u["id"],)).fetchone()["n"]
            # which journaling categories are still untouched this ISO week?
            today = datetime.now(timezone.utc).date()
            monday = (today - timedelta(days=today.weekday())).isoformat()
            wkc = {k: 0 for k in JOURNAL_KINDS}
            for r in c.execute("SELECT COALESCE(kind,'daily') k, COUNT(*) n FROM journal "
                               "WHERE user_id=? AND substr(created,1,10)>=? GROUP BY k",
                               (u["id"], monday)).fetchall():
                if r["k"] in wkc:
                    wkc[r["k"]] += r["n"]
            self._send(200, {"ok": True, "count": total, "reflection": refl["reflection"], "mood": mood,
                             "kind": kind, "pillar": pillar, "place": place,
                             "week": {"counts": wkc, "missing": [k for k in JOURNAL_KINDS if wkc[k] == 0]},
                             "new_achievements": [{"code": a, "title": ACH_BY_CODE[a][1]} for a in new_ach]}); return

        if p == "/api/journal/insights":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            rows = c.execute("SELECT text,mood,created FROM journal WHERE user_id=? ORDER BY id DESC LIMIT 15",
                             (u["id"],)).fetchall()
            if len(rows) < 2:
                self._send(200, {"ready": False, "reason": "few"}); return
            ins = journal_insights(rows)
            if not ins:
                self._send(200, {"ready": False, "reason": "companion"}); return
            self._send(200, {"ready": True, **ins}); return

        if p == "/api/journal/transcribe":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            img = (self._body().get("image") or "")
            mime = "image/jpeg"
            if img.startswith("data:"):
                head, _, b64 = img.partition(",")
                m = re.search(r"data:([^;]+)", head)
                if m:
                    mime = m.group(1)
                img = b64
            if not img:
                self._send(400, {"error": "no image"}); return
            text = gemini_transcribe(img, mime)
            if text is None:
                self._send(502, {"error": "Couldn’t read that image — try better light or a closer shot."}); return
            self._send(200, {"ok": True, "text": text}); return

        if p == "/api/chat":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            if not GEMINI_KEY:
                self._send(200, {"reply": "I'm resting right now — the companion isn't available."}); return
            msgs = self._body().get("messages") or []
            contents = []
            for m in msgs[-20:]:
                role = "model" if m.get("role") == "model" else "user"
                t = str(m.get("text") or "")[:4000]
                if t:
                    contents.append({"role": role, "parts": [{"text": t}]})
            if not contents:
                self._send(400, {"error": "say something"}); return
            reply = None; used = []
            for _ in range(6):
                parts = gemini_chat(contents)
                if not parts:
                    break
                fcs = [pt["functionCall"] for pt in parts if isinstance(pt, dict) and "functionCall" in pt]
                if fcs:
                    contents.append({"role": "model", "parts": parts})
                    fresp = []
                    for fc in fcs:
                        res = chat_tool_exec(c, u, fc.get("name"), fc.get("args"))
                        used.append(fc.get("name"))
                        fr = {"name": fc.get("name"), "response": res if isinstance(res, dict) else {"result": res}}
                        if fc.get("id"):
                            fr["id"] = fc["id"]
                        fresp.append({"functionResponse": fr})
                    contents.append({"role": "user", "parts": fresp})
                    continue
                reply = "".join(pt.get("text", "") for pt in parts if isinstance(pt, dict))
                break
            if not reply:
                reply = "I'm here with you. Could you say that again?"
            self._send(200, {"reply": reply.strip(), "tools": used}); return

        if p == "/api/collection/claim":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            code = (self._body().get("code") or "")
            it = ITEM_BY_CODE.get(code)
            if not it:
                self._send(400, {"error": "no such item"}); return
            if c.execute("SELECT 1 FROM items WHERE user_id=? AND code=?", (u["id"], code)).fetchone():
                self._send(200, {"ok": True, "already": True}); return
            if not item_eligible(c, u, it[5]):
                self._send(400, {"error": "Not unlocked yet — " + it[6]}); return
            c.execute("INSERT OR IGNORE INTO items(user_id,code,created) VALUES(?,?,?)", (u["id"], code, now_iso()))
            # auto-equip the first item claimed
            if not u["equipped"]:
                c.execute("UPDATE users SET equipped=? WHERE id=?", (code, u["id"]))
            c.commit()
            self._send(200, {"ok": True, "name": it[1]}); return

        if p == "/api/collection/equip":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            code = (self._body().get("code") or "")
            if code and not c.execute("SELECT 1 FROM items WHERE user_id=? AND code=?", (u["id"], code)).fetchone():
                self._send(400, {"error": "You don't own that yet"}); return
            c.execute("UPDATE users SET equipped=? WHERE id=?", (code or None, u["id"]))
            c.commit()
            self._send(200, {"ok": True, "equipped": code or None}); return

        if p == "/api/companions/adopt":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            code = (self._body().get("code") or "")
            comp = COMP_BY_CODE.get(code)
            if not comp:
                self._send(400, {"error": "no such companion"}); return
            if c.execute("SELECT 1 FROM companions WHERE user_id=? AND code=?", (u["id"], code)).fetchone():
                self._send(200, {"ok": True, "already": True}); return
            cost = comp[4]
            if (u["motes"] or 0) < cost:
                self._send(400, {"error": f"You need {cost} Motes to adopt {comp[1]}."}); return
            c.execute("INSERT OR IGNORE INTO companions(user_id,code,fed,created) VALUES(?,?,0,?)", (u["id"], code, now_iso()))
            c.execute("UPDATE users SET motes=COALESCE(motes,0)-? WHERE id=?", (cost, u["id"]))
            if not u["companion"]:
                c.execute("UPDATE users SET companion=? WHERE id=?", (code, u["id"]))
            c.commit()
            self._send(200, {"ok": True, "name": comp[1]}); return

        if p == "/api/companions/feed":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            d = self._body(); code = (d.get("code") or "")
            try:
                amt = int(d.get("amount") or 0)
            except Exception:
                amt = 0
            row = c.execute("SELECT fed FROM companions WHERE user_id=? AND code=?", (u["id"], code)).fetchone()
            if not row:
                self._send(400, {"error": "You haven't adopted that companion."}); return
            amt = max(1, min(amt, u["motes"] or 0))
            if amt < 1:
                self._send(400, {"error": "You have no Motes to feed."}); return
            before = comp_stage(row["fed"])["index"]
            c.execute("UPDATE companions SET fed=fed+? WHERE user_id=? AND code=?", (amt, u["id"], code))
            c.execute("UPDATE users SET motes=COALESCE(motes,0)-? WHERE id=?", (amt, u["id"]))
            c.commit()
            new_fed = row["fed"] + amt
            after = comp_stage(new_fed)
            self._send(200, {"ok": True, "fed": new_fed, "stage": after,
                             "evolved": after["index"] > before}); return

        if p == "/api/companions/equip":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            code = (self._body().get("code") or "")
            if code and not c.execute("SELECT 1 FROM companions WHERE user_id=? AND code=?", (u["id"], code)).fetchone():
                self._send(400, {"error": "You haven't adopted that companion."}); return
            c.execute("UPDATE users SET companion=? WHERE id=?", (code or None, u["id"]))
            c.commit()
            self._send(200, {"ok": True, "companion": code or None}); return

        if p == "/api/lifeos":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            d = self._body()
            pillars = d.get("pillars") or {}
            pillars = {k: (str(v)[:24] if v else None) for k, v in pillars.items() if k in ("N", "E", "S", "W")}
            chosen = [v for v in pillars.values() if v]
            focus = [f for f in (d.get("focus") or []) if f in chosen][:2]
            base = (d.get("base") or u["city"] or "My base")[:40]
            lo = {"base": base, "pillars": pillars, "focus": focus}
            # config changed → clear today's cached prompts so they regenerate from new focuses
            c.execute("UPDATE users SET lifeos=?, lo_prompts=NULL, lo_prompts_day=NULL WHERE id=?",
                      (json.dumps(lo), u["id"]))
            c.commit()
            self._send(200, {"ok": True, "lifeos": {**lo, "configured": bool(chosen)}}); return

        if p == "/api/nft/reserve":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            code = (self._body().get("code") or "")
            art = ART_BY_CODE.get(code)
            if not art:
                self._send(400, {"error": "no such artifact"}); return
            if c.execute("SELECT 1 FROM items WHERE user_id=? AND code=?", (u["id"], code)).fetchone():
                self._send(200, {"ok": True, "already": True}); return
            c.execute("INSERT OR IGNORE INTO items(user_id,code,created) VALUES(?,?,?)", (u["id"], code, now_iso()))
            if not u["equipped"]:
                c.execute("UPDATE users SET equipped=? WHERE id=?", (code, u["id"]))
            c.commit()
            self._send(200, {"ok": True, "name": art[1]}); return

        if p == "/api/shop/buy":
            u = self._me(c)
            if not u:
                self._send(401, {"error": "sign in"}); return
            code = (self._body().get("code") or "")
            it = SHOP_BY_CODE.get(code)
            if not it:
                self._send(400, {"error": "no such item"}); return
            _, name, icon, rar, price, gate, flavor = it
            if c.execute("SELECT 1 FROM items WHERE user_id=? AND code=?", (u["id"], code)).fetchone():
                self._send(200, {"ok": True, "already": True}); return
            if gate and gate[0] == "days" and member_days(u) < gate[1]:
                self._send(400, {"error": f"Unlocks after {gate[1]} days of membership."}); return
            if (u["motes"] or 0) < price:
                self._send(400, {"error": f"You need {price} Motes for {name}."}); return
            c.execute("INSERT OR IGNORE INTO items(user_id,code,created) VALUES(?,?,?)", (u["id"], code, now_iso()))
            if price:
                c.execute("UPDATE users SET motes=COALESCE(motes,0)-? WHERE id=?", (price, u["id"]))
            c.commit()
            self._send(200, {"ok": True, "name": name}); return

        self._send(404, {"error": "not found"})


# live presence (in-memory): user ids currently in a session
class _Live:
    def __init__(self):
        self.m = {}  # uid -> expiry epoch
        self.lock = threading.Lock()
    def add(self, uid):
        with self.lock:
            self.m[uid] = time.time() + 3600
    def remove(self, uid):
        with self.lock:
            self.m.pop(uid, None)
    def count(self):
        now = time.time()
        with self.lock:
            dead = [k for k, v in self.m.items() if v < now]
            for k in dead:
                self.m.pop(k, None)
            # add a gentle synthetic baseline so "meditating now" is never a lonely 0
            base = 3 + int(12 * (0.5 + 0.5 * math.sin(now / 900)))
            return len(self.m) + base

LIVE = _Live()


def _cookie_hdr(tok):
    return f"lumen_sess={tok}; Path=/; Max-Age={SESSION_TTL}; HttpOnly; SameSite=Lax"


# minimal urllib query parse without importing at module scope confusion
from urllib.parse import parse_qsl as urllib_parse_qsl

MANIFEST = json.dumps({
    "name": "Lumen — light up the world", "short_name": "Lumen",
    "description": "A gamified meditation app. Light up a living world map with every sit, earn Light, build streaks, and walk guided voice journeys.",
    "start_url": ".", "scope": ".", "display": "standalone", "orientation": "portrait",
    "background_color": "#0b0a12", "theme_color": "#0b0a12",
    "categories": ["health", "lifestyle", "education"],
    "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
              {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
              {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]
})

# Service worker: makes Lumen an installable, offline-capable PWA. Strategy is
# network-first for navigations (so a new build always wins when online — this is
# what fixes the stale-page-on-iPhone problem) and cache-first for static assets.
# API requests are never intercepted. skipWaiting + clients.claim so updates apply
# immediately. Bump CACHE on any change you want to force-evict.
PRIVACY_PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lumen — Privacy Policy</title>
<style>
body{margin:0;background:#0b0a12;color:#ece9f5;font-family:ui-rounded,-apple-system,"Segoe UI",Roboto,system-ui,sans-serif;line-height:1.65}
.wrap{max-width:720px;margin:0 auto;padding:40px 22px 80px}
h1{color:#f5c977;font-size:26px;margin:0 0 4px}h2{color:#a855f7;font-size:17px;margin:28px 0 6px}
.muted{color:#9a93b8;font-size:13px}a{color:#f5c977}ul{padding-left:20px}li{margin:4px 0}
</style></head><body><div class="wrap">
<h1>Lumen — Privacy Policy</h1>
<p class="muted">Last updated: 12 October 2026</p>
<p>Lumen is a meditation app. This policy explains what it collects, why, and the control you have. We keep data collection to the minimum needed to run the app.</p>
<h2>What we collect</h2>
<ul>
<li><b>Account</b>: your email and a securely hashed password (we never store your password in plain text), and a display name you choose.</li>
<li><b>Practice data</b>: your meditation sessions (duration, soundscape, time), streaks, Light/XP, achievements, and any journal entries you write.</li>
<li><b>Approximate location (optional)</b>: only if you grant permission. Your coordinates are deliberately <b>fuzzed/coarsened</b> before storage and shown on the shared world map as an approximate glow. You can use the entire app without sharing location.</li>
</ul>
<h2>How we use it</h2>
<ul>
<li>To provide the app: your profile, progress, streaks, leagues, and the community world map.</li>
<li>Journal entries are private to you unless you explicitly choose to share one to the community feed.</li>
</ul>
<h2>Third parties</h2>
<ul>
<li><b>Google Gemini</b>: if you use the AI companion, journal transcription, or AI-generated prompts, the relevant text or image is sent to Google's Gemini API to generate a response. Don't put anything in those features you wouldn't want processed by a third-party AI.</li>
<li><b>Map tiles</b>: the world map loads background map imagery from Esri/ArcGIS.</li>
<li>We do <b>not</b> sell your data or use third-party advertising trackers.</li>
</ul>
<h2>Data retention &amp; deletion</h2>
<p>Your data is stored on Lumen's own server. You can <b>delete your account and all associated data at any time</b> from the app: open the <b>You</b> (profile) tab and tap <b>Delete account</b>. This permanently removes your profile, sessions, journal, and progress and cannot be undone.</p>
<h2>Children</h2>
<p>Lumen is not directed to children under 13 and we do not knowingly collect their data.</p>
<h2>Contact</h2>
<p>Questions or requests: <a href="mailto:CONTACT_EMAIL">CONTACT_EMAIL</a>.</p>
</div></body></html>"""

SERVICE_WORKER = r"""
const CACHE = 'lumen-v22';
const STATIC = ['icon-192.png', 'icon-512.png', 'manifest.webmanifest'];
self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(STATIC)).catch(() => {}));
});
self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)));
    await self.clients.claim();
  })());
});
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.pathname.indexOf('/api/') !== -1) return;           // never cache the API
  if (url.pathname.indexOf('/assets/mandala.html') !== -1) {  // actively iterated: network-first
    e.respondWith(fetch(req).then(r => { const cp = r.clone(); caches.open(CACHE).then(c => c.put(req, cp)); return r; })
                            .catch(() => caches.match(req)));
    return;
  }
  if (req.mode === 'navigate') {                               // app shell: network-first
    e.respondWith(
      fetch(req).then(r => { const cp = r.clone(); caches.open(CACHE).then(c => c.put(req, cp)); return r; })
                .catch(() => caches.match(req).then(m => m || caches.match('./')))
    );
    return;
  }
  e.respondWith(                                               // static: cache-first
    caches.match(req).then(m => m || fetch(req).then(r => {
      if (r && r.ok && url.origin === location.origin) { const cp = r.clone(); caches.open(CACHE).then(c => c.put(req, cp)); }
      return r;
    }).catch(() => m))
  );
});
"""


# ===========================================================================
# MARKETING — go-to-market pipeline + generated materials (owner /admin only)
# ===========================================================================
# Distilled from Matthew's growth handoff: Apple editorial/ASO levers first,
# then short-form video + niche communities + a coordinated Product Hunt spike.

APP_STORE_URL = "https://apps.apple.com/app/id6822133425"

SURVEY_PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lumen — tell us what you think</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  :root{--gold:#f5c977;--bg:#0b0a12;--panel:#15111f;--line:#2a2440;--muted:#b4acd0;--text:#f6f1ea}
  html,body{height:100%}
  body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.5;
    background-image:radial-gradient(70% 45% at 50% 0%,rgba(36,28,74,.55),transparent 70%);display:flex;flex-direction:column;min-height:100%}
  .top{position:sticky;top:0;z-index:5;background:linear-gradient(#0b0a12,rgba(11,10,18,.85));backdrop-filter:blur(6px);padding:14px 18px 10px}
  .brandrow{display:flex;align-items:center;justify-content:space-between;max-width:620px;margin:0 auto}
  .brand{font-family:Georgia,serif;font-size:22px;font-weight:700;color:var(--gold)}
  .count{font-size:12px;color:var(--muted);letter-spacing:.06em}
  .pbar{max-width:620px;margin:10px auto 0;height:5px;border-radius:99px;background:#241d3a;overflow:hidden}
  .pbar>i{display:block;height:100%;background:linear-gradient(90deg,#e0953a,var(--gold));border-radius:99px;transition:width .3s}
  .stage{flex:1;display:flex;align-items:center;justify-content:center;padding:24px 20px}
  .screen{max-width:600px;width:100%;animation:rise .32s cubic-bezier(.2,.8,.25,1) both}
  @keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
  .eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.16em;color:var(--gold);margin-bottom:12px;display:flex;align-items:center;gap:9px}
  .eyebrow .fic{font-size:20px}
  h1{font-family:Georgia,serif;font-weight:700;font-size:30px;line-height:1.22;margin-bottom:8px}
  h1 em{font-style:italic;color:var(--gold)}
  .sub{color:var(--muted);font-size:16px;margin-bottom:22px}
  .stars{display:flex;gap:12px;margin:6px 0}
  .star{font-size:46px;color:#3a3357;cursor:pointer;transition:transform .08s;user-select:none}
  .star:active{transform:scale(.9)}
  .star.on{color:var(--gold);text-shadow:0 0 16px rgba(245,201,119,.55)}
  .chips{display:flex;flex-wrap:wrap;gap:10px;margin-top:4px}
  .chip{font-size:16px;padding:13px 18px;border-radius:14px;border:1px solid var(--line);background:var(--panel);color:var(--text);cursor:pointer;transition:.12s}
  .chip:hover{border-color:#4a4270}
  .chip.on{border-color:var(--gold);background:rgba(245,201,119,.13);color:var(--gold);box-shadow:0 0 18px -6px rgba(245,201,119,.5)}
  textarea,input[type=email]{width:100%;background:#0f0b18;border:1px solid var(--line);border-radius:14px;color:var(--text);
    font-family:inherit;font-size:17px;padding:15px;resize:vertical}
  textarea{min-height:130px}
  textarea:focus,input:focus{outline:none;border-color:var(--gold)}
  .lbl{font-size:12px;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);margin:20px 0 8px}
  .nps{display:flex;flex-wrap:wrap;gap:8px}
  .np{width:50px;height:54px;display:grid;place-items:center;border-radius:12px;border:1px solid var(--line);background:var(--panel);cursor:pointer;font-weight:700;font-size:18px}
  .np.on{border-color:var(--gold);background:rgba(245,201,119,.15);color:var(--gold)}
  .npends{display:flex;justify-content:space-between;color:var(--muted);font-size:13px;margin-top:8px}
  .nav{position:sticky;bottom:0;background:linear-gradient(rgba(11,10,18,0),rgba(11,10,18,.9) 35%);padding:16px 20px calc(16px + env(safe-area-inset-bottom))}
  .navin{max-width:600px;margin:0 auto;display:flex;align-items:center;gap:12px}
  .btn{flex:1;background:linear-gradient(135deg,var(--gold),#e0953a);color:#2a1a05;font-weight:700;font-size:17px;border:0;border-radius:14px;padding:16px;cursor:pointer}
  .btn.ghost{flex:0 0 auto;background:none;border:1px solid var(--line);color:var(--text);padding:16px 20px}
  .btn:disabled{opacity:.55}
  .finish{display:block;text-align:center;color:var(--muted);font-size:13px;margin-top:12px;text-decoration:underline;cursor:pointer}
  .ok{text-align:center;padding:40px 16px}
  .ok .big{font-size:60px}
  .ok h2{font-family:Georgia,serif;font-size:30px;margin:16px 0 10px}
  .err{color:#ff9aa6;text-align:center;font-size:14px;margin-top:8px;min-height:18px}
  .hero-ic{font-size:60px;text-align:center;margin-bottom:10px}
</style></head>
<body>
<div class="top"><div class="brandrow"><span class="brand">lumen</span><span class="count" id="count"></span></div>
  <div class="pbar"><i id="pbar" style="width:0%"></i></div></div>
<div class="stage"><div class="screen" id="screen"></div></div>
<div class="nav"><div class="navin" id="nav"></div><div class="err" id="err"></div></div>
<script>
const F=[
 {k:'orb',ic:'✺',name:'Your light & progress',desc:'The home orb, your Light, levels and streaks.',
   hq:'How does tracking your progress — the orb, Light, levels and streaks — help you?',
   hopts:['Keeps me coming back','Makes it feel rewarding','Shows me I’m growing','Motivates longer sits','Doesn’t do much for me'],specs:[
   {k:'returns',q:'Does seeing your Light, level and streak make you want to come back?',opts:['Yes, a lot','A little','Not really','Haven’t noticed it']},
   {k:'clarity',q:'Is it clear how you earn Light and level up?',opts:['Totally clear','Mostly clear','A bit confusing']}]},
 {k:'map',ic:'🌍',name:'The world map',desc:'Meditating alongside a live global community.',
   hq:'What does seeing the live world map do for you?',
   hopts:['Makes me feel less alone','It’s inspiring','Adds accountability','Makes me curious about others','Not much for me'],specs:[
   {k:'belonging',q:'Does seeing a live world map give you a sense of connection that improves your practice?',opts:['Yes','Somewhat','Not really']},
   {k:'social',q:'Would you want to see friends or people near you on the map?',opts:['Yes — friends','Yes — nearby people','No — keep it anonymous']}]},
 {k:'leagues',ic:'🏆',name:'Leagues',desc:'Weekly tiers, from Ember to Supernova.',
   hq:'What do the weekly leagues do for your practice?',
   hopts:['Push me to practice more','Make it fun','Add healthy pressure','Feel stressful','Don’t affect me'],specs:[
   {k:'motivation',q:'Do the weekly leagues make you want to practice more?',opts:['Yes','A little','No','They stress me out']},
   {k:'fit',q:'Is friendly competition the right vibe for a meditation app?',opts:['Love it','It’s fine','I’d rather it be solo']}]},
 {k:'journeys',ic:'🧭',name:'Journeys',desc:'Multi-part narrated courses — each lesson teaches an idea from a real tradition (Stoic, Vedic, breathwork…), then guides you through a meditation on it.',
   hq:'What do the guided journeys give you?',
   hopts:['I’m learning something real','A deeper, guided sit','Structure to follow','A reason to return','Didn’t land for me'],specs:[
   {k:'learning',q:'Do the journeys actually teach you something — does it feel like learning, not just listening?',opts:['Yes, I’m learning a lot','A little','Not really','Haven’t gone deep yet']},
   {k:'teaching',q:'How is the teaching itself — the ideas, traditions and explanations?',opts:['Rich & insightful','Solid','A bit surface-level','Confusing']},
   {k:'medquality',q:'How are the guided meditations themselves — the pacing, depth, and how they land?',opts:['Excellent','Good','A bit flat','Needs work']},
   {k:'narration',q:'How does the narration and voice feel during the guided sits?',opts:['Calming & natural','Fine','A little off','Distracting']},
   {k:'return',q:'Are the journeys something you’d keep coming back to?',opts:['Yes','Maybe','No']},
   {k:'depth_want',q:'Where should the journeys go deeper or expand?',text:true,ph:'More traditions, longer courses, specific teachers, topics like anxiety or sleep…'}]},
 {k:'journal',ic:'📖',name:'Journal & the Keeper',desc:'Reflective writing with a warm AI companion.',
   hq:'What does journaling with the Keeper give you?',
   hopts:['Clarity on my thoughts','Feeling heard','A record to look back on','Unexpected insight','Didn’t click for me'],specs:[
   {k:'value',q:'Did writing — and the Keeper’s reflections — feel valuable?',opts:['Yes','Somewhat','Not for me','Didn’t try it']},
   {k:'keeper',q:'How did the Keeper’s responses feel?',opts:['Warm & insightful','Okay','A bit generic','Haven’t used it']}]},
 {k:'mandala',ic:'❉',name:'Wholeness mandala',desc:'A sacred artwork you restore as you practice — each achievement fills in another part, until it blooms whole.',
   hq:'How does the mandala make you feel about your progress and achievements?',
   hopts:['Proud of what I’ve built','Motivated to keep going','It makes effort visible','Rewarded for showing up','Doesn’t do much for me'],specs:[
   {k:'effective',q:'Does growing and filling in your mandala feel like a satisfying way to see your progress and achievements?',opts:['Yes, very','Somewhat','Not really']},
   {k:'metaphor',q:'Does the metaphor — restoring the mandala as restoring yourself — resonate with you?',opts:['Deeply','A little','Not really','Didn’t catch that meaning']},
   {k:'clarity',q:'Is it clear what the mandala represents and how it fills in?',opts:['Clear','Sort of','Confusing']}]},
 {k:'vedic',ic:'☾',name:'Daily Vedic reading',desc:'A personalized reading from your birth star.',
   hq:'What does the daily Vedic reading give you?',
   hopts:['A reason to open the app','Reflection & meaning','Fun & curiosity','Feels off-brand to me','I don’t read it'],specs:[
   {k:'usage',q:'Do you read the daily Vedic reading?',opts:['Most days','Sometimes','Rarely','Didn’t know it was there']},
   {k:'fit',q:'Does the astrology / Vedic angle belong in a meditation app for you?',opts:['Love it','Neutral','Not my thing']}]},
 {k:'freeform',ic:'🪷',name:'Free-form meditation',desc:'Pick a length and a soundscape, and just sit.',
   hq:'What makes free-form meditation work for you?',
   hopts:['Simplicity','The soundscapes','Control over length','I prefer guided','Didn’t use it'],specs:[
   {k:'enough',q:'Are the soundscapes and timer enough for a free sit?',opts:['Yes','Want more sounds','Want more controls']},
   {k:'sound',q:'A soundscape you’d love us to add?',text:true,ph:'e.g. gentle rain on a tent, singing bowls, a fireplace…'}]},
 {k:'sharing',ic:'↗',name:'Sharing your sit',desc:'The shareable card after a session.',
   hq:'What would make you share your sit — or hold back?',
   hopts:['Celebrate a streak','Inspire friends','Accountability','I keep practice private','Wouldn’t share'],specs:[
   {k:'would',q:'Would you share your meditation card with friends?',opts:['Yes','Maybe','No']},
   {k:'nudge',q:'What would make you more likely to share it?',text:true,ph:'A nicer card, a streak flex, a reward…'}]}
];
const FEEL=['Love it','It’s okay','Not for me','Didn’t try it'];
const WANT=['More of this','Just right','Less of this','Do it differently'];
const OVER=[['like_most','What did you like most about Lumen?','The thing that made you want to keep going…'],
 ['disliked','What frustrated you, confused you, or felt off?','Be honest — this is the most useful part for us.'],
 ['more_less','What do you want more of? What would you cut?',''],
 ['wishlist','Anything missing you’d love to see — or you’d do differently?','A feature, a change, a whole different direction…']];
const STEPS=[{t:'intro'}];
F.forEach(f=>{STEPS.push({t:'take',f});f.specs.forEach(sp=>STEPS.push({t:'spec',f,sp}));});
OVER.forEach(o=>STEPS.push({t:'text',k:'overall.'+o[0],q:o[1],ph:o[2]}));
STEPS.push({t:'nps'});STEPS.push({t:'email'});
const LAST=STEPS.length-1;
const state={};let i=0,sending=false;
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function setChip(key,val,row,multi){
  if(multi){let a=Array.isArray(state[key])?state[key]:[];
    a=a.includes(val)?a.filter(x=>x!==val):a.concat([val]);
    if(a.length)state[key]=a;else delete state[key];
    row.querySelectorAll('.chip').forEach(c=>c.classList.toggle('on',(state[key]||[]).includes(c.dataset.v)));return;}
  const on=state[key]===val;row.querySelectorAll('.chip').forEach(c=>c.classList.remove('on'));
  if(on){delete state[key];}else{state[key]=val;row.querySelectorAll('.chip').forEach(c=>{if(c.dataset.v===val)c.classList.add('on');});}}
function chipsHTML(key,opts,multi){const sel=multi?(Array.isArray(state[key])?state[key]:[]):state[key];
  return `<div class="chips" data-key="${key}"${multi?' data-multi="1"':''}>${opts.map(o=>`<span class="chip${(multi?sel.includes(o):sel===o)?' on':''}" data-v="${esc(o)}">${esc(o)}</span>`).join('')}</div>`;}
function render(){
  const s=STEPS[i];const sc=document.getElementById('screen');
  document.getElementById('count').textContent=i===0?'':`Step ${i} of ${LAST}`;
  document.getElementById('pbar').style.width=(100*i/LAST)+'%';
  document.getElementById('err').textContent='';
  let h='';
  if(s.t==='intro'){
    h=`<div class="hero-ic">🌟</div><h1 style="text-align:center">Help shape <em>Lumen</em></h1>
      <p class="sub" style="text-align:center">You’re one of the first to try it. We’ll go module by module — rate what you tried, skip what you didn’t, and tell us what you’d change. About 3–4 minutes, and you can finish early anytime.</p>`;
  } else if(s.t==='take'){
    const f=s.f;
    h=`<div class="eyebrow"><span class="fic">${f.ic}</span> ${esc(f.name)}</div>
      <h1>Your take on <em>${esc(f.name)}</em></h1><p class="sub">${esc(f.desc)}</p>
      <div class="lbl">Your rating</div>
      <div class="stars" data-stars="${f.k}.rating">${[1,2,3,4,5].map(n=>`<span class="star${(state[f.k+'.rating']>=n)?' on':''}" data-n="${n}">★</span>`).join('')}</div>
      <div class="lbl">${esc(f.hq)} <span style="text-transform:none;letter-spacing:0;opacity:.7">· pick any</span></div>${chipsHTML(f.k+'.help',f.hopts,true)}
      <div class="lbl">Would you want…</div>${chipsHTML(f.k+'.want',WANT)}
      <div class="lbl">Anything else? (optional)</div>
      <textarea data-text="${f.k}.note" placeholder="A quick note about ${esc(f.name)}…">${esc(state[f.k+'.note']||'')}</textarea>`;
  } else if(s.t==='spec'){
    const f=s.f,sp=s.sp,key=f.k+'.'+sp.k;
    h=`<div class="eyebrow"><span class="fic">${f.ic}</span> ${esc(f.name)}</div><h1>${esc(sp.q)}</h1>`;
    h+= sp.text ? `<textarea data-text="${key}" placeholder="${esc(sp.ph||'')}">${esc(state[key]||'')}</textarea>`
               : chipsHTML(key,sp.opts);
  } else if(s.t==='text'){
    h=`<div class="eyebrow">Overall</div><h1>${esc(s.q)}</h1>
      <textarea data-text="${s.k}" placeholder="${esc(s.ph||'')}">${esc(state[s.k]||'')}</textarea>`;
  } else if(s.t==='nps'){
    h=`<div class="eyebrow">Overall</div><h1>How likely are you to recommend <em>Lumen</em> to a friend?</h1>
      <div class="nps" data-nps="1">${[0,1,2,3,4,5,6,7,8,9,10].map(n=>`<span class="np${state.nps===n?' on':''}" data-np="${n}">${n}</span>`).join('')}</div>
      <div class="npends"><span>Not likely</span><span>Very likely</span></div>`;
  } else if(s.t==='email'){
    h=`<div class="eyebrow">Last one</div><h1>Open to a follow-up?</h1>
      <p class="sub">Leave your email if you’re happy for us to reach out about your feedback. Totally optional.</p>
      <input type="email" data-text="email" placeholder="you@example.com" autocomplete="email" value="${esc(state.email||'')}">`;
  }
  sc.innerHTML=h;
  // bind
  sc.querySelectorAll('[data-stars]').forEach(row=>{const key=row.dataset.stars;
    row.querySelectorAll('.star').forEach(st=>st.onclick=()=>{const n=+st.dataset.n;state[key]=n;
      row.querySelectorAll('.star').forEach(x=>x.classList.toggle('on',+x.dataset.n<=n));});});
  sc.querySelectorAll('.chips[data-key]').forEach(row=>{const key=row.dataset.key,multi=!!row.dataset.multi;
    row.querySelectorAll('.chip').forEach(ch=>ch.onclick=()=>setChip(key,ch.dataset.v,row,multi));});
  sc.querySelectorAll('.nps[data-nps]').forEach(row=>row.querySelectorAll('.np').forEach(n=>n.onclick=()=>{
    state.nps=+n.dataset.np;row.querySelectorAll('.np').forEach(x=>x.classList.toggle('on',x===n));}));
  sc.querySelectorAll('[data-text]').forEach(t=>t.oninput=()=>{const v=t.value;if(v.trim())state[t.dataset.text]=v;else delete state[t.dataset.text];});
  // nav
  const nav=document.getElementById('nav');
  const primary = i===LAST ? 'Send feedback' : (i===0 ? 'Begin' : 'Continue');
  nav.innerHTML = (i>0?`<button class="btn ghost" id="back">Back</button>`:'')+
    `<button class="btn" id="next">${primary}</button>`;
  const back=document.getElementById('back');if(back)back.onclick=()=>{i--;render();window.scrollTo(0,0);};
  document.getElementById('next').onclick=()=>{ if(i===LAST){submit();} else {i++;render();window.scrollTo(0,0);} };
  // finish-early link (after the intro)
  document.querySelectorAll('.finish').forEach(x=>x.remove());
  if(i>0 && i<LAST){const f=document.createElement('div');f.className='finish';f.textContent='Finish & send now';
    f.onclick=submit;document.querySelector('.nav').insertBefore(f,document.getElementById('err'));}
}
async function submit(){
  if(sending)return;const err=document.getElementById('err');
  const nps=(typeof state.nps==='number')?state.nps:null;
  const email=state.email||'';
  const answers={};Object.keys(state).forEach(k=>{if(k!=='nps'&&k!=='email')answers[k]=state[k];});
  if(!Object.keys(answers).length && nps==null){err.textContent='Answer at least one thing before sending.';return;}
  sending=true;document.getElementById('next').disabled=true;document.getElementById('next').textContent='Sending…';
  try{
    const r=await fetch('api/survey',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({answers,nps,email})});
    if(!r.ok){const j=await r.json().catch(()=>({}));throw new Error(j.error||'Could not send');}
    document.querySelector('.top').style.display='none';document.querySelector('.nav').style.display='none';
    document.getElementById('screen').innerHTML='<div class="ok"><div class="big">🌟</div><h2>Thank you</h2>'+
      '<p class="sub">Your feedback goes straight to the people building Lumen. It genuinely shapes what comes next.</p>'+
      '<a class="btn" href="https://apps.apple.com/app/id6822133425" style="display:inline-block;text-decoration:none;max-width:300px;margin:18px auto 0">Back to Lumen</a></div>';
    window.scrollTo(0,0);
  }catch(e){sending=false;document.getElementById('next').disabled=false;
    document.getElementById('next').textContent=i===LAST?'Send feedback':'Continue';err.textContent=e.message||'Something went wrong — try again.';}
}
render();
</script></body></html>
"""

SITE_URL      = os.environ.get("LUMEN_SITE_URL", "https://lumen.app")
IG_HANDLE     = "@lumen.meditation"

# Launch pipeline as a CHECKLIST. Each task carries impact (1-5) and effort
# (1=easiest … 5=hardest); the server auto-orders them by a priority score
# (high impact + low effort first) so the owner always sees the best next move
# at the top. Every task has explicit, checkable sub-steps (persisted per step).
PIPELINE_RAW = [
    {"key": "apple_aso", "section": "Apple", "title": "Lock in ASO (title, subtitle, keywords)",
     "impact": 5, "effort": 1,
     "why": "Free, compounding App Store search traffic. Pure copy-paste from the Materials tab.",
     "steps": [
         "Open App Store Connect → Lumen → App Information",
         "Paste the Title: “Lumen: Meditate & Glow”",
         "Paste the Subtitle: “Stoic journeys, journal & streaks”",
         "Paste the 100-char keyword field (Materials tab)",
         "Make screenshot #1 carry the hook text, not just a UI shot",
         "Rewrite the description + keywords for everything we've shipped since launch (Vedic astrology, the Atlas photo-map, journeys) — far richer than the v1 copy",
     ]},
    {"key": "website", "section": "Owned", "title": "Ship the marketing website",
     "impact": 4, "effort": 1,
     "why": "A home base every ad, bio, and press mention points to. Already built — just finish it.",
     "steps": [
         "Confirm the landing page is live at /site",
         "Point a custom domain at it (optional)",
         "Swap in 3 real app screenshots",
         "Double-check the App Store button link",
     ]},
    {"key": "apple_featuring", "section": "Apple", "title": "Submit an App Store Featuring nomination",
     "impact": 5, "effort": 2,
     "why": "Editorial features are the single biggest free spike you can get.",
     "steps": [
         "App Store Connect → Lumen → Featuring → start a nomination",
         "Write the STORY, not a feature list: “talk to Marcus Aurelius about your bad week”",
         "Note your next update/launch date (nominate 2–3 weeks ahead)",
         "Submit",
     ]},
    {"key": "instagram", "section": "Owned", "title": "Stand up the Instagram account",
     "impact": 4, "effort": 2,
     "why": "Evergreen home for Reels and a link-in-bio funnel to the App Store.",
     "steps": [
         "Create the @lumen.meditation account",
         "Set the bio + profile photo (use the Lumen icon)",
         "Add the App Store link in bio",
         "Post your first 6 posts (generated for you)",
         "Follow ~20 stoicism / meditation / Jungian accounts to seed reach",
     ]},
    {"key": "video_shortform", "section": "Short-form", "title": "Post 3–5 short-form clips / week",
     "impact": 5, "effort": 4,
     "why": "A clip of someone roasted by The Forge or advised by Marcus Aurelius is inherently shareable — your #1 channel.",
     "steps": [
         "Pick a script from the Materials tab (start with “The Forge roast”)",
         "Screen-record the voice interaction with captions on",
         "Post to TikTok, then cross-post the Reel to Instagram",
         "Batch-film weekly; keep a 3–5/week cadence",
     ]},
    {"key": "communities", "section": "Communities", "title": "Show up in niche communities",
     "impact": 4, "effort": 3,
     "why": "Niche beats broad — stoicism/Jungian subreddits and self-improvement Discords actually convert.",
     "steps": [
         "Pick 2 subreddits (start: r/Stoicism, r/Meditation)",
         "Spend a week genuinely commenting — no links yet",
         "Post the generated Reddit post once the rules allow it",
         "Offer free access; funnel warm leads to the Telegram group",
     ]},
    {"key": "apple_events", "section": "Apple", "title": "Create an In-App Event per season",
     "impact": 4, "effort": 3,
     "why": "Events surface in Search and on your product page — your seasonal challenges are a perfect fit.",
     "steps": [
         "App Store Connect → In-App Events → Create",
         "Title a seasonal challenge (“7 Days with the Stoics”)",
         "Add event art + a short hook",
         "Schedule start/end dates",
     ]},
    {"key": "apple_ads", "section": "Apple", "title": "Run Apple Ads on niche keywords (small budget)",
     "impact": 3, "effort": 2,
     "why": "Cheap on niche terms; learn what converts before spending broadly.",
     "steps": [
         "Create an Apple Ads account",
         "Start $10–20/day on: stoic, journaling, mental fitness",
         "Point each ad at its matching Custom Product Page",
         "Review conversions weekly; cut the losers",
     ]},
    {"key": "referrals", "section": "Growth loop", "title": "Turn Light into referral rewards",
     "impact": 4, "effort": 4,
     "why": "You already have the gamification layer — invites that unlock rooms/Light compound organically.",
     "steps": [
         "Add an “Invite a friend” flow with a per-user share link",
         "Reward: both people get Light + unlock a guide/room",
         "Surface the invite right after a completed session",
         "Track invites in the admin dashboard",
     ]},
    {"key": "producthunt", "section": "Spike", "title": "Coordinate a Product Hunt launch",
     "impact": 4, "effort": 4,
     "why": "Time it WITH the featuring nomination for one big coordinated spike.",
     "steps": [
         "Create the PH listing (tagline + description from Materials)",
         "Schedule a Tue/Wed 12:01am PT launch",
         "Line up the Telegram group to support in hour one",
         "Post the maker first-comment; reply to everyone all day",
     ]},
    {"key": "apple_custompages", "section": "Apple", "title": "Build Custom Product Pages per audience",
     "impact": 3, "effort": 3,
     "why": "Match the store page to the ad that drove the tap → higher conversion.",
     "steps": [
         "App Store Connect → Custom Product Pages → Create",
         "Page A — Stoic/philosophy (headline + body from Materials)",
         "Page B — Jungian/self-work (headline + body from Materials)",
         "Link each ad campaign to its matching page",
     ]},
]

# Priority score: reward impact, penalize effort. Highest score = do first.
# Tie-break: easier first, then higher impact.
def _priority(t):
    return (t["impact"] * 2 - t["effort"], -t["effort"], t["impact"])

PIPELINE = sorted(PIPELINE_RAW, key=_priority, reverse=True)
for _i, _t in enumerate(PIPELINE):
    _t["rank"] = _i + 1
    _t["quick_win"] = _t["effort"] <= 2 and _t["impact"] >= 4

# ---------------------------------------------------------------------------
# DISTRIBUTION MATRIX — every outlet we can push Lumen through, as rows; the
# four phases we run each one through, as columns (Prep → Set up → Launch →
# Follow-up). Each cell is a checkable step persisted per owner (keys o_*#idx,
# sharing the mkt_state store with the pipeline checklist).
DIST_COLS = ["Prep", "Set up", "Launch / Post", "Follow-up"]
OUTLETS = [
    # --- Apple (first-party, mostly free) ---
    {"key": "o_apple_featuring", "cat": "Apple", "name": "App Store Featuring", "cost": "Free",
     "link": "https://developer.apple.com/contact/app-store/promote/",
     "steps": ["Draft the STORY pitch (not a feature list)", "Build a press/media kit",
               "Submit via ASC → Featuring, 2–3 wks pre-launch", "Follow up before the launch date"]},
    {"key": "o_apple_events", "cat": "Apple", "name": "In-App Events", "cost": "Free",
     "link": "https://appstoreconnect.apple.com",
     "steps": ["Pick a seasonal challenge to feature", "Create event art + hook",
               "Create & schedule in ASC → In-App Events", "Renew each season"]},
    {"key": "o_apple_cpp", "cat": "Apple", "name": "Custom Product Pages", "cost": "Free",
     "link": "https://appstoreconnect.apple.com",
     "steps": ["Define 2 audiences (Stoic, Jungian)", "Write copy from Materials tab",
               "Create both pages in ASC", "Link each ad to its page"]},
    {"key": "o_apple_ads", "cat": "Apple", "name": "Apple Ads", "cost": "Paid",
     "link": "https://searchads.apple.com",
     "steps": ["Create an Apple Ads account", "Pick niche keywords (stoic, journaling…)",
               "Fund $10–20/day", "Review weekly, cut losers"]},
    {"key": "o_apple_aso", "cat": "Apple", "name": "ASO (title / subtitle / keywords)", "cost": "Free",
     "link": "https://appstoreconnect.apple.com",
     "steps": ["Finalize title/subtitle/keywords (Materials)", "Put the hook on screenshot #1",
               "Publish in ASC", "Iterate on keyword ranks"]},
    # --- Press / publications ---
    {"key": "o_press_wellness", "cat": "Press", "name": "Wellness / meditation press", "cost": "Free",
     "link": "https://www.mindful.org",
     "steps": ["Build a target list (Mindful, Well+Good…)", "Write the story angle",
               "Send personalized pitches", "Follow up in ~1 week"]},
    {"key": "o_press_tech", "cat": "Press", "name": "Tech / app press", "cost": "Free",
     "link": "https://techcrunch.com/got-a-tip/",
     "steps": ["Find the right reporter", "Draft a one-line hook", "Send with the press kit", "Follow up once"]},
    {"key": "o_press_reporters", "cat": "Press", "name": "Qwoted / Featured.com (reporter requests)", "cost": "Free",
     "link": "https://www.qwoted.com",
     "steps": ["Sign up as a source (HARO is gone)", "Set wellness + tech alerts",
               "Reply fast with a usable quote", "Track any links earned"]},
    {"key": "o_newsletters", "cat": "Press", "name": "Niche newsletters", "cost": "Free · Paid",
     "link": "https://www.dailystoic.com",
     "steps": ["List 5 relevant newsletters", "Pitch a mention / sponsor slot",
               "Offer free-access codes", "Track referral clicks"]},
    # --- Free directories / launch platforms ---
    {"key": "o_producthunt", "cat": "Directories", "name": "Product Hunt", "cost": "Free",
     "link": "https://www.producthunt.com/ship",
     "steps": ["Build listing (tagline/desc from Materials)", "Prep assets + a hunter",
               "Launch Tue/Wed 12:01 PT", "Reply all day; rally the Telegram group"]},
    {"key": "o_betalist", "cat": "Directories", "name": "BetaList", "cost": "Free",
     "link": "https://betalist.com/submit",
     "steps": ["Submit the startup", "Add screenshots + blurb", "Share the live listing", "Collect sign-up emails"]},
    {"key": "o_taaft", "cat": "Directories", "name": "There's An AI For That", "cost": "Free",
     "link": "https://theresanaiforthat.com/submit/",
     "steps": ["Submit the tool (AI guides angle)", "Choose category + media",
               "Verify the listing", "Share the badge"]},
    {"key": "o_alternativeto", "cat": "Directories", "name": "AlternativeTo", "cost": "Free",
     "link": "https://alternativeto.net",
     "steps": ["Add as alt to Headspace / Calm", "Fill description + icon",
               "Add screenshots", "Seed a few upvotes"]},
    {"key": "o_ih_hn", "cat": "Directories", "name": "Indie Hackers / Show HN", "cost": "Free",
     "link": "https://news.ycombinator.com/showhn.html",
     "steps": ["Write the build story", "Share a real metric", "Post Show HN / IH", "Reply to every comment"]},
    {"key": "o_appreview", "cat": "Directories", "name": "App review sites", "cost": "Free",
     "link": "https://appadvice.com",
     "steps": ["List sites (AppAdvice, 148Apps)", "Prepare promo codes",
               "Submit via their forms", "Follow up for coverage"]},
    # --- Social / UGC ---
    {"key": "o_instagram", "cat": "Social / UGC", "name": "Instagram (owned)", "cost": "Free",
     "link": "https://instagram.com",
     "steps": ["Create @lumen.meditation", "Bio + App Store link",
               "Post first 6 (Materials)", "Follow 20 niche accounts"]},
    {"key": "o_shortform", "cat": "Social / UGC", "name": "TikTok + Reels (short-form)", "cost": "Free",
     "link": "https://www.tiktok.com",
     "steps": ["Pick a script (Materials tab)", "Screen-record with captions",
               "Post TikTok + cross-post the Reel", "Hold a 3–5/week cadence"]},
    {"key": "o_ugc", "cat": "Social / UGC", "name": "UGC creators", "cost": "Free · Paid",
     "link": "https://instagram.com",
     "steps": ["Find 5 micro-creators", "Send free access + a brief",
               "Collect their clips", "Repost + whitelist the best"]},
    {"key": "o_communities", "cat": "Social / UGC", "name": "Niche communities (Reddit / Discord)", "cost": "Free",
     "link": "https://www.reddit.com/r/Stoicism/",
     "steps": ["Pick 2 subreddits / Discords", "Engage genuinely ~1 wk",
               "Post the generated content", "Funnel warm leads to Telegram"]},
    # --- UGC content production (hire creators/models → content → ads) ---
    {"key": "o_ugc_sourcing", "cat": "UGC content", "name": "Hire creators (UGC platforms)", "cost": "Paid",
     "link": "https://billo.app",
     "steps": ["Write the brief + set budget/rate", "Post on Billo · Insense · TikTok Creator Marketplace",
               "Shortlist & contract 3–5 creators", "Collect first content batch"]},
    {"key": "o_ugc_shoots", "cat": "UGC content", "name": "Model & location shoots", "cost": "Paid",
     "link": "",
     "steps": ["Build a shot list (nature, balcony sunrise, exotic, cozy indoor)", "Cast models + scout locations",
               "Shoot people meditating in-place with the app", "Review & pick the selects"]},
    {"key": "o_ugc_rights", "cat": "UGC content", "name": "Usage rights & whitelisting", "cost": "Free · Paid",
     "link": "",
     "steps": ["Secure paid-ads usage rights in every contract", "Get handles for Spark Ads / whitelisting",
               "Store raw footage + signed releases", "Renew / extend rights before they lapse"]},
    {"key": "o_ugc_ads", "cat": "UGC content", "name": "Turn UGC into ads", "cost": "Paid",
     "link": "",
     "steps": ["Edit Reels/TikTok cuts with captions", "Build 3–5 ad variants per concept",
               "Launch on Meta / TikTok / Apple Ads", "Scale winners, kill losers weekly"]},
    # --- Growth loop ---
    {"key": "o_referrals", "cat": "Growth loop", "name": "Referral rewards", "cost": "Free",
     "link": "",
     "steps": ["Build an invite-link flow", "Reward both sides with Light",
               "Surface it right after a session", "Track invites in this dashboard"]},
]
OUTLET_BY_KEY = {o["key"]: o for o in OUTLETS}

# Starter sub-items for outlets that benefit from a granular, editable checklist
# (owner can add/check/delete more). Seeded once per parent, then fully user-owned.
SUBTASK_SEEDS = {
    "o_ugc_sourcing": ["Shortlist 3+ candidate creators", "Send outreach DMs / emails",
                       "Agree rate + deliverables", "Sign contract incl. paid-ads usage rights"],
    "o_ugc_shoots":   ["Contact 3+ models", "Schedule the shoot", "Do the shoot",
                       "Edit the videos", "Upload them to our socials"],
    "o_ugc_rights":   ["Confirm paid-ads rights in writing", "Collect signed releases",
                       "Get Spark / whitelist handles"],
    "o_ugc_ads":      ["Cut 3–5 ad variants", "Write hooks / captions",
                       "Launch a test campaign", "Scale the winner"],
}

def seed_subtasks():
    """Insert the starter sub-items once per parent (guarded by a marker in mkt_state),
    so restarts never clobber the owner's own edits."""
    c = db()
    for parent, items in SUBTASK_SEEDS.items():
        marker = "__subinit__:" + parent
        if c.execute("SELECT 1 FROM mkt_state WHERE key=?", (marker,)).fetchone():
            continue
        for i, txt in enumerate(items):
            c.execute("INSERT INTO mkt_subtasks(parent,text,status,pos,created) VALUES(?,?,?,?,?)",
                      (parent, txt, "todo", i, now_iso()))
        c.execute("INSERT OR IGNORE INTO mkt_state(key,status,note,updated) VALUES(?,?,?,?)",
                  (marker, "done", "seed marker", now_iso()))
    c.commit(); c.close()

def subtasks_by_parent(c):
    out = {}
    for r in c.execute("SELECT id,parent,text,status FROM mkt_subtasks ORDER BY parent,pos,id"):
        out.setdefault(r["parent"], []).append({"id": r["id"], "text": r["text"], "status": r["status"]})
    return out

MATERIALS = {
    "aso": {
        "title": "Lumen: Meditate & Glow",
        "subtitle": "Stoic journeys, journal & streaks",
        "keywords": "stoic,meditation,vedic,astrology,horoscope,nakshatra,journal,mindfulness,calm,sleep,streak,habit",
        "note": "30-char title, 30-char subtitle, 100-char keyword field (no spaces, comma-separated, no plurals you can avoid). This set adds the Vedic-astrology terms we now rank for; rotate low performers out as App Store Connect shows what converts."
    },
    "app_store_description_v2": (
        "Lumen is the meditation app that finally feels worth opening every day — part calm, "
        "part practice, part living world you light up with everyone else who sits.\n\n"
        "Every morning opens with a real Vedic reading: your rāśi and the Moon's nakshatra of the "
        "day, grounded in classical Jyotish — not vague horoscope filler. Then sit for a few minutes "
        "with a guided voice journey (the Stoics, inner archetypes, gratitude, sleep), and watch your "
        "session light up your spot on a shared world map.\n\n"
        "• A daily Vedic reading (rāśi + nakshatra), with your birth star & daśā if you add a birth time\n"
        "• Atlas — photograph each place you meditate, build a photo streak, and collect new spots as you travel\n"
        "• Guided voice journeys with distinct guides and soundscapes\n"
        "• A living world map — see the world meditate in real time, with photos of real places\n"
        "• Light, levels, streaks & weekly leagues that make the habit stick\n"
        "• A private journal with prompts; share a place or entry to the community only if you choose\n\n"
        "Free to start. Your journal and birth details stay private. Light up the world."
    ),
    "custom_pages": [
        {"angle": "Stoic / Philosophy",
         "headline": "Talk to Marcus Aurelius about your bad week.",
         "body": "Lumen turns ancient Stoic practice into a daily ritual. Walk guided voice journeys with the Stoics, journal with prompts that actually land, and watch your light grow on a living world map. Build the one streak that matters."},
        {"angle": "Jungian / Self-work",
         "headline": "Meet the parts of yourself you've been avoiding.",
         "body": "Lumen is a guided path through shadow work and inner archetypes. Sit with a voice guide, journal what surfaces, and track the quiet work over weeks — not as a chore, but as a world you light up one session at a time."},
    ],
    "app_store_description": (
        "Lumen is a meditation app that finally feels worth opening every day.\n\n"
        "Sit for a few minutes with a guided voice journey — the Stoics, inner archetypes, "
        "gratitude, sleep — and every session lights up your spot on a living world map shared "
        "with everyone meditating right now. Earn Light, build a streak, climb weekly leagues, "
        "and keep a private journal of what surfaces.\n\n"
        "• Guided voice journeys with distinct guides and soundscapes\n"
        "• A living world map — see the world meditate in real time\n"
        "• Light, levels, streaks & weekly leagues that make the habit stick\n"
        "• A private journal with prompts; share an entry to the community only if you choose\n"
        "• Collect guides & companions as you go\n\n"
        "Free to start. Your journal stays private. Light up the world."
    ),
    "instagram": {
        "handle": IG_HANDLE,
        "bio": "Meditate. Glow. Grow. 🌕\nStoic journeys + a world map you light up.\nFree on iOS 👇",
        "pillars": ["Voice-clip hooks (roast/advice)", "Map/ritual aesthetic", "Stoic & Jungian quotes", "Streak/community proof", "Behind-the-build"],
        "captions": [
            "POV: you tell Marcus Aurelius about your week and he does NOT coddle you. 🫠 #stoicism #meditation",
            "The Forge doesn't do gentle. Tag someone who needs this roast. 🔥",
            "Every dot is a real person meditating right now. Add yours. 🌍",
            "You don't need motivation. You need a streak you're scared to break.",
            "Shadow work, but make it a 6-minute voice journey.",
            "Three breaths before you reply to that text. That's the whole lesson.",
            "What would a Stoic do with your inbox? Ask one. (link in bio)",
            "Your journal entry from 30 days ago is going to humble you.",
            "Light up a dot. Climb a league. Actually meditate. In that order.",
            "The app that gamified the one habit you keep abandoning.",
            "Guided journey → journal prompt → map glows. The loop that got me to day 40.",
            "Building Lumen in public: here's why every session lights up a world map. 🧵",
        ],
        "calendar": [
            "Mon — Reel: Marcus Aurelius advice clip (captioned screen-rec)",
            "Tue — Carousel: Stoic quote → how Lumen turns it into practice",
            "Wed — Reel: The Forge roast clip (the shareable one)",
            "Thu — Story: world map screen-rec + 'add your dot' CTA → link",
            "Fri — Reel: '40-day streak changed X' testimonial/POV",
            "Sat — Carousel: Jungian/shadow-work angle",
            "Sun — Behind-the-build post + week recap",
        ],
    },
    "video_scripts": [
        {"title": "The Forge roast", "hook": "I let an AI Stoic roast my excuses for 60 seconds.",
         "beats": ["Open on the chat: type a real excuse ('I'll meditate tomorrow').", "Play The Forge's blunt voice reply (captioned).", "Cut to the world map lighting up as you actually sit.", "End card: 'Lumen — free on iOS. Link in bio.'"]},
        {"title": "Marcus about your bad week", "hook": "Told Marcus Aurelius about my worst week. His reply hit different.",
         "beats": ["Type the bad-week rant.", "Marcus's measured voice reply, captioned line-by-line.", "Screen-rec the 5-min journey that follows.", "End: streak counter ticks up."]},
        {"title": "The map", "hook": "Every glowing dot is a stranger meditating with you right now.",
         "beats": ["Slow pan over the live world map.", "Tap 'begin' → your dot ignites.", "Text overlay: 'you're never sitting alone.'", "CTA."]},
        {"title": "Streak psychology", "hook": "I gamified meditation so I'd stop quitting. Day 40.",
         "beats": ["Show streak + league screen.", "Fast cuts of Light/levels.", "'turns out I just needed a number I was scared to lose.'", "CTA."]},
        {"title": "Shadow work", "hook": "A 6-minute voice journey into the part of me I avoid.",
         "beats": ["Dim aesthetic, archetype guide intro.", "Journal prompt appears post-session.", "Type a raw line.", "Soft CTA — 'this one's private unless you share it.'"]},
    ],
    "community": {
        "reddit_rules": "Read each sub's self-promo rules first. Ratio: ~9 genuine comments for every 1 mention. Lead with value, disclose you built it.",
        "reddit_post": ("Title: I built a meditation app that turns Stoic practice into a daily ritual (and a world map)\n\n"
                        "Body: Longtime lurker here. I kept abandoning meditation apps, so I built the one I'd actually keep: short guided voice journeys with the Stoics, a journal with prompts, and — the part that hooked me — every session lights up your spot on a shared world map. Streaks and weekly leagues keep me honest.\n\n"
                        "Not trying to spam — genuinely want feedback from people who take this seriously. Happy to give TestFlight/free access. What would make a Stoic-grounded practice app actually earn a place on your home screen?"),
        "discord_intro": "Hey all — I lurk here because this community actually practices, not just quotes. I've been building a Stoic-grounded meditation app (voice journeys + journaling + a bit of gamification to beat my own inconsistency). Not dropping a link unless it's welcome — mods, happy to follow your rules. Mostly here to learn.",
        "subreddits": ["r/Stoicism", "r/Meditation", "r/Jung", "r/getdisciplined", "r/selfimprovement", "r/Mindfulness"],
    },
    "product_hunt": {
        "tagline": "Meditate, glow, and grow — Stoic journeys on a living world map",
        "description": ("Lumen turns meditation into a daily ritual you won't abandon. Walk short guided voice "
                        "journeys with the Stoics and inner archetypes, journal what surfaces, and light up your "
                        "spot on a world map shared with everyone meditating right now. Light, streaks, and weekly "
                        "leagues make the habit actually stick."),
        "first_comment": ("Hey PH 👋 I'm Matthew. I built Lumen because I kept quitting every meditation app I tried. "
                          "Two things fixed it for me: (1) short guided voice journeys where you can genuinely talk to a "
                          "Stoic about your week, and (2) a world map where every session lights up a dot — so you're never "
                          "sitting alone, and the streak becomes something you're scared to break. Would love your honest take, "
                          "especially on the voice guides. AMA about the build."),
        "timing": "Launch Tue/Wed 12:01am PT, timed with the Apple featuring nomination. Rally the Telegram group in hour one.",
    },
    "website_copy": {
        "hero_h": "Light up the world, one breath at a time.",
        "hero_sub": "Lumen turns meditation into a daily ritual you'll actually keep — a real Vedic reading each morning, guided voice journeys with the Stoics, and a world map you light up with a photo of every place you sit.",
        "cta": "Download on iOS",
        "features": [
            {"t": "A reading written in the sky", "d": "Each day opens with a real Vedic reading — your rāśi and the Moon's nakshatra, grounded in classical Jyotish. Not vague horoscope filler."},
            {"t": "Atlas", "d": "Photograph every place you meditate and build a photo streak. Travel somewhere new, collect the spot, and see where the world is sitting."},
            {"t": "Talk to the Stoics", "d": "Short guided voice journeys with real guides. Tell Marcus Aurelius about your week; sit with an archetype for six minutes."},
            {"t": "A streak worth keeping", "d": "Light, levels, and weekly leagues turn the habit into something you're scared to break — in the best way."},
            {"t": "A journal that's yours", "d": "Prompts that land, entries that stay private. Share one to the community only if you choose to."},
        ],
    },
}


def _mkt_state(c):
    rows = c.execute("SELECT key,status,note,updated FROM mkt_state").fetchall()
    return {r["key"]: {"status": r["status"], "note": r["note"], "updated": r["updated"]} for r in rows}


def admin_analytics(c, days=30):
    """First-party product analytics: onboarding funnel + most-visited screens."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    out = {"days": days}
    # onboarding funnel — distinct users reaching each step
    funnel = []
    try:
        for r in c.execute(
            "SELECT CAST(json_extract(props,'$.step') AS INTEGER) step, "
            "       json_extract(props,'$.label') label, COUNT(DISTINCT anon_id) users "
            "FROM events WHERE name='onboarding_step' AND created>=? "
            "GROUP BY step ORDER BY step", (since,)).fetchall():
            if r["step"] is None:
                continue
            funnel.append({"step": r["step"], "label": r["label"] or ("Step %d" % r["step"]),
                           "users": r["users"]})
    except Exception:
        agg = {}
        for r in c.execute("SELECT props, anon_id FROM events WHERE name='onboarding_step' AND created>=?",
                           (since,)).fetchall():
            try:
                pj = json.loads(r["props"] or "{}")
            except Exception:
                continue
            st = pj.get("step")
            if st is None:
                continue
            agg.setdefault(st, {"label": pj.get("label") or ("Step %d" % st), "users": set()})
            agg[st]["users"].add(r["anon_id"])
        funnel = [{"step": s, "label": v["label"], "users": len(v["users"])}
                  for s, v in sorted(agg.items())]
    out["onboarding_funnel"] = funnel
    if funnel:
        top = funnel[0]["users"] or 1
        out["onboarding_start"] = funnel[0]["users"]
        out["onboarding_complete"] = funnel[-1]["users"]
        out["onboarding_conv_pct"] = round(100.0 * funnel[-1]["users"] / top, 1)
    # most-frequented screens
    out["screens"] = [{"screen": r["screen"] or "(none)", "views": r["views"], "users": r["users"]}
                      for r in c.execute(
        "SELECT screen, COUNT(*) views, COUNT(DISTINCT anon_id) users FROM events "
        "WHERE name='screen_view' AND created>=? GROUP BY screen ORDER BY views DESC LIMIT 25",
        (since,)).fetchall()]
    # headline counts
    out["visitors"] = (c.execute("SELECT COUNT(DISTINCT anon_id) n FROM events WHERE created>=?",
                                 (since,)).fetchone()["n"]) or 0
    out["total_events"] = (c.execute("SELECT COUNT(*) n FROM events WHERE created>=?",
                                     (since,)).fetchone()["n"]) or 0
    out["signups"] = (c.execute("SELECT COUNT(*) n FROM users WHERE is_bot=0 AND created>=?",
                                (since,)).fetchone()["n"]) or 0
    # daily active (distinct anon) last 14 days
    out["daily_active"] = [{"day": r["d"], "users": r["n"]} for r in c.execute(
        "SELECT substr(created,1,10) d, COUNT(DISTINCT anon_id) n FROM events "
        "WHERE created>=? GROUP BY d ORDER BY d DESC LIMIT 14",
        ((datetime.now(timezone.utc) - timedelta(days=14)).isoformat(),)).fetchall()]
    return out


def admin_overview(c):
    """Real, live app metrics for the owner dashboard."""
    def one(sql, args=()):
        r = c.execute(sql, args).fetchone()
        return (r[0] if r else 0) or 0
    today = today_str()
    users = one("SELECT COUNT(*) FROM users WHERE is_bot=0 AND name IS NOT NULL")
    with_email = one("SELECT COUNT(*) FROM users WHERE is_bot=0 AND email IS NOT NULL")
    sess = one("SELECT COUNT(*) FROM sessions")
    light = one("SELECT COALESCE(SUM(light),0) FROM sessions")
    minutes = one("SELECT COALESCE(SUM(minutes),0) FROM sessions")
    today_sess = one("SELECT COUNT(*) FROM sessions WHERE day=?", (today,))
    dau = one("SELECT COUNT(DISTINCT user_id) FROM sessions WHERE day=?", (today,))
    journals = one("SELECT COUNT(*) FROM journal")
    # signups per day, last 14d
    sign = {r["d"]: r["n"] for r in c.execute(
        "SELECT substr(created,1,10) d, COUNT(*) n FROM users WHERE is_bot=0 AND created IS NOT NULL GROUP BY d")}
    series = []
    base = datetime.now(timezone.utc).date()
    for i in range(13, -1, -1):
        d = (base - timedelta(days=i)).isoformat()
        series.append({"day": d[5:], "signups": sign.get(d, 0),
                       "sessions": one("SELECT COUNT(*) FROM sessions WHERE day=?", (d,))})
    top = [dict(r) for r in c.execute(
        "SELECT name, light, streak, total_sessions FROM users WHERE is_bot=0 AND name IS NOT NULL "
        "ORDER BY light DESC LIMIT 8")]
    cities = one("SELECT COUNT(DISTINCT city) FROM sessions WHERE city IS NOT NULL")
    return {
        "kpis": {"users": users, "with_email": with_email, "sessions": sess, "light": light,
                 "minutes": minutes, "today_sessions": today_sess, "dau": dau,
                 "journals": journals, "cities": cities, "live": LIVE.count()},
        "series": series, "top": top,
        "links": {"app_store": APP_STORE_URL, "site": SITE_URL, "instagram": IG_HANDLE},
    }


ADMIN_PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lumen · Admin</title>
<style>
:root{--bg:#0b0a12;--card:#161326;--ink:#ece9f5;--mut:#9a93b8;--gold:#f5c977;--purp:#a855f7;--line:#2a2540;--ok:#34d399;--go:#60a5fa}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:ui-rounded,-apple-system,"Segoe UI",Roboto,system-ui,sans-serif}
a{color:var(--gold)}.wrap{max-width:1040px;margin:0 auto;padding:22px 18px 90px}
h1{font-size:22px;margin:0;color:var(--gold)}.sub{color:var(--mut);font-size:13px;margin:2px 0 18px}
.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 18px}
.tab{background:var(--card);border:1px solid var(--line);color:var(--ink);padding:8px 14px;border-radius:999px;cursor:pointer;font-size:14px}
.tab.on{background:var(--purp);border-color:var(--purp);color:#fff}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px}
.kpi .n{font-size:26px;font-weight:700;color:var(--gold)}.kpi .l{color:var(--mut);font-size:12px;margin-top:2px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:12px 0}
.card h3{margin:0 0 8px;font-size:15px;color:var(--purp)}
.bars{display:flex;align-items:flex-end;gap:4px;height:120px;margin-top:8px}
.bar{flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;gap:3px}
.bar i{width:70%;background:linear-gradient(180deg,var(--gold),var(--purp));border-radius:3px 3px 0 0;min-height:2px;display:block}
.bar b{font-size:9px;color:var(--mut);font-weight:400}
table{width:100%;border-collapse:collapse;font-size:13px}td,th{text-align:left;padding:6px 4px;border-bottom:1px solid var(--line)}th{color:var(--mut);font-weight:500}
.pcol{display:flex;gap:12px;flex-wrap:wrap}.psec{flex:1;min-width:280px}
.task{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px;margin:10px 0}
.task.complete{border-color:var(--ok);opacity:.72}
.task .top{display:flex;justify-content:space-between;gap:10px;align-items:center}
.task .t{font-weight:600;font-size:15px}.task .why{color:var(--mut);font-size:12.5px;margin:8px 0 10px;line-height:1.45}
.rank{display:inline-grid;place-items:center;width:22px;height:22px;border-radius:7px;background:var(--purp);color:#fff;font-size:12px;font-weight:700;margin-right:8px;vertical-align:middle}
.qw{background:rgba(245,201,119,.16);color:var(--gold);border:1px solid rgba(245,201,119,.4);border-radius:999px;font-size:10.5px;padding:1px 7px;margin-left:8px;white-space:nowrap}
.prog{display:flex;align-items:center;gap:7px;font-size:11px;color:var(--mut);flex:none}
.pbar{width:60px;height:6px;border-radius:999px;background:var(--line);overflow:hidden}
.pbar i{display:block;height:100%;background:linear-gradient(90deg,var(--gold),var(--ok))}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:4px}
.chip{background:var(--line);border-radius:999px;padding:2px 9px;font-size:11px;color:var(--mut)}
.checks{display:flex;flex-direction:column;gap:2px}
.chk{display:flex;align-items:flex-start;gap:9px;padding:7px 8px;border-radius:9px;cursor:pointer;font-size:13.5px;line-height:1.45}
.chk:hover{background:#1d1933}.chk input{margin-top:2px;width:17px;height:17px;accent-color:var(--ok);flex:none;cursor:pointer}
.chk.on span{color:var(--mut);text-decoration:line-through}
.sechd{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--mut);margin:14px 0 2px}
.mat{background:#0f0d1c;border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:8px 0;white-space:pre-wrap;font-size:13px;line-height:1.55}
.copy{float:right;background:var(--line);border:0;color:var(--ink);border-radius:8px;padding:3px 9px;font-size:11px;cursor:pointer;margin-left:8px}
.pill{display:inline-block;background:var(--line);border-radius:999px;padding:2px 8px;font-size:11px;color:var(--mut);margin:2px 4px 2px 0}
.hidden{display:none}.lbl{color:var(--gold);font-weight:600;font-size:13px;margin-top:10px}
.gate{max-width:360px;margin:60px auto;text-align:center}.gate input{width:100%;padding:11px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--ink);margin:6px 0}
.gate button{width:100%;padding:11px;border-radius:10px;border:0;background:var(--purp);color:#fff;font-weight:600;cursor:pointer}
.err{color:#fda4af;font-size:13px;min-height:16px}
/* distribution matrix */
.matrix{overflow-x:auto;border:1px solid var(--line);border-radius:14px;background:var(--card)}
table.mtx{width:100%;min-width:720px;border-collapse:collapse;font-size:12.5px}
table.mtx th,table.mtx td{border-bottom:1px solid var(--line);border-right:1px solid var(--line);padding:9px 10px;vertical-align:top;text-align:left}
table.mtx th{position:sticky;top:0;background:#1b1733;color:var(--mut);font-weight:600;font-size:11.5px;z-index:1}
table.mtx th.outlet,table.mtx td.outlet{position:sticky;left:0;background:var(--card);z-index:1;min-width:190px;border-right:1px solid var(--line)}
table.mtx th.outlet{z-index:2;background:#1b1733}
.catrow td{background:#120f22;color:var(--purp);font-weight:700;font-size:11px;letter-spacing:.08em;text-transform:uppercase;position:sticky;left:0}
tr.rdone td.outlet{opacity:.65}
.outlet .onm{font-weight:600;font-size:13px}.outlet .onm a{color:var(--ink);text-decoration:none}.outlet .onm a:hover{color:var(--gold)}
.ometa{display:flex;align-items:center;gap:8px;margin-top:5px}
.cost{font-size:10px;padding:1px 7px;border-radius:999px;border:1px solid var(--line);color:var(--mut)}
.cost.free{color:var(--ok);border-color:rgba(52,211,153,.4)}.cost.paid{color:var(--gold);border-color:rgba(245,201,119,.4)}.cost.mix{color:var(--go);border-color:rgba(96,165,250,.4)}
.mini{display:flex;align-items:center;gap:5px;font-size:10.5px;color:var(--mut)}
.mbar{width:42px;height:5px;border-radius:999px;background:var(--line);overflow:hidden}.mbar i{display:block;height:100%;background:linear-gradient(90deg,var(--gold),var(--ok))}
td.cell.on{background:rgba(52,211,153,.08)}td.x{background:#100e1d}
.mcell{display:flex;gap:7px;cursor:pointer;line-height:1.4}
.mcell input{margin-top:1px;width:15px;height:15px;accent-color:var(--ok);flex:none;cursor:pointer}
.cell.on .mcell span{color:var(--mut);text-decoration:line-through}
.subx{margin-top:7px;background:#1b1733;border:1px solid var(--line);color:var(--mut);border-radius:999px;padding:3px 9px;font-size:11px;cursor:pointer;display:inline-flex;align-items:center;gap:5px}
.subx:hover{border-color:var(--purp);color:var(--ink)}
.subcount{font-size:11px}
tr.subrow>td{background:#100e1d;padding:10px 14px}
.sublist{display:flex;flex-direction:column;gap:2px;max-width:560px}
.submt{color:var(--mut);font-size:12px;padding:4px 2px}
.subitem{display:flex;align-items:center;gap:8px;padding:5px 6px;border-radius:8px}
.subitem:hover{background:#171430}
.subitem label{display:flex;align-items:center;gap:8px;flex:1;cursor:pointer;font-size:13.5px}
.subitem input{width:16px;height:16px;accent-color:var(--ok);flex:none;cursor:pointer}
.subitem.on span{color:var(--mut);text-decoration:line-through}
.subdel{background:transparent;border:0;color:#6b6388;cursor:pointer;font-size:13px;padding:2px 6px;border-radius:6px}
.subdel:hover{color:#fda4af;background:#241a2a}
.subadd{display:flex;gap:7px;margin-top:8px}
.subadd input{flex:1;background:#161326;border:1px solid var(--line);color:var(--ink);border-radius:9px;padding:7px 10px;font-size:13px;font-family:inherit}
.subadd button{background:var(--purp);border:0;color:#fff;border-radius:9px;padding:7px 14px;font-size:13px;cursor:pointer}
</style></head><body><div class="wrap" id="app"><p class="sub">Loading…</p></div>
<script>
const $=s=>document.querySelector(s), app=document.getElementById('app');
const esc=t=>(t||'').replace(/[&<>]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[m]));
let DATA=null, TAB='dashboard';
async function j(u,o){const r=await fetch(u,o||{});return r.json();}
function gate(msg){app.innerHTML=`<div class="gate"><h1>Lumen Admin</h1><p class="sub">Owner sign-in required</p>
<input id="ge" type="email" placeholder="email" autocomplete="username"><input id="gp" type="password" placeholder="password" autocomplete="current-password">
<button onclick="login()">Sign in</button><p class="err">${msg||''}</p></div>`;}
async function login(){const email=$('#ge').value.trim(), password=$('#gp').value;
 const r=await j('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password})});
 if(r.error){$('.err').textContent=r.error;return;} boot();}
async function boot(){const r=await j('/api/admin/overview'); if(r.error){gate(r.error==='forbidden'?'That account is not an owner.':'');return;}
 DATA=r; render();}
function render(){
 app.innerHTML=`<h1>🌕 Lumen Admin</h1><p class="sub">Live metrics + launch pipeline · <a href="/site" target="_blank">marketing site ↗</a></p>
 <div class="tabs">${['dashboard','analytics','pipeline','distribution','materials','notifications'].map(t=>`<button class="tab ${t==TAB?'on':''}" onclick="go('${t}')">${t[0].toUpperCase()+t.slice(1)}</button>`).join('')}</div>
 <div id="body"></div>`;
 ({dashboard:dash,analytics:analytics,pipeline:pipe,distribution:dist,materials:mats,notifications:notif}[TAB])();
}
function go(t){TAB=t;render();}
function dash(){const k=DATA.kpis, S=DATA.series, mx=Math.max(1,...S.map(d=>d.sessions));
 const kpi=(n,l)=>`<div class="kpi"><div class="n">${n}</div><div class="l">${l}</div></div>`;
 $('#body').innerHTML=`<div class="grid">
  ${kpi(k.users,'Users')}${kpi(k.live,'Live now')}${kpi(k.dau,'Active today')}${kpi(k.sessions,'Sessions')}
  ${kpi(k.light.toLocaleString(),'Light earned')}${kpi(k.minutes.toLocaleString(),'Minutes')}${kpi(k.journals,'Journal entries')}${kpi(k.cities,'Cities')}
 </div>
 <div class="card"><h3>Last 14 days · sessions</h3><div class="bars">
  ${S.map(d=>`<div class="bar" title="${d.day}: ${d.sessions} sessions, ${d.signups} signups"><i style="height:${Math.round(100*d.sessions/mx)}%"></i><b>${d.day}</b></div>`).join('')}
 </div></div>
 <div class="card"><h3>Top meditators</h3><table><tr><th>#</th><th>Name</th><th>Light</th><th>Streak</th><th>Sessions</th></tr>
  ${DATA.top.map((u,i)=>`<tr><td>${i+1}</td><td>${esc(u.name)}</td><td>${u.light}</td><td>${u.streak}🔥</td><td>${u.total_sessions}</td></tr>`).join('')||'<tr><td colspan=5>No users yet</td></tr>'}
 </table></div>`;
}
function stepDone(t,i){const s=DATA.state[t.key+'#'+i];return s&&s.status==='done';}
function pipe(){const st=DATA.state;
 const done=t=>t.steps.filter((_,i)=>stepDone(t,i)).length;
 const total=DATA.pipeline.length, allDone=DATA.pipeline.filter(t=>done(t)===t.steps.length).length;
 const dots=n=>'●'.repeat(n)+'<span style="opacity:.3">'+'●'.repeat(5-n)+'</span>';
 const taskHtml=t=>{const d=done(t),n=t.steps.length,pct=Math.round(100*d/n),complete=d===n;
  return `<div class="task ${complete?'complete':''}">
   <div class="top"><div><span class="rank">${t.rank}</span><span class="t">${esc(t.title)}</span>
     ${t.quick_win?'<span class="qw">⚡ quick win</span>':''}</div>
     <div class="prog"><span>${d}/${n}</span><div class="pbar"><i style="width:${pct}%"></i></div></div></div>
   <div class="chips"><span class="chip">${esc(t.section)}</span>
     <span class="chip">impact <b style="color:var(--gold)">${dots(t.impact)}</b></span>
     <span class="chip">effort <b style="color:var(--go)">${dots(t.effort)}</b></span></div>
   <div class="why">${esc(t.why)}</div>
   <div class="checks">${t.steps.map((s,i)=>`<label class="chk ${stepDone(t,i)?'on':''}"><input type="checkbox" ${stepDone(t,i)?'checked':''} onchange="toggleStep('${t.key}',${i},this.checked)"><span>${esc(s)}</span></label>`).join('')}</div>
  </div>`;};
 $('#body').innerHTML=`<p class="sub">${allDone}/${total} tasks complete · ordered by impact ÷ effort — start at the top.</p>`+DATA.pipeline.map(taskHtml).join('');
}
async function toggleStep(key,i,checked){const k=key+'#'+i, status=checked?'done':'todo';
 DATA.state[k]={status}; if(TAB==='distribution')dist();else pipe();
 await j('/api/admin/task',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:k,status})});}
const DIST_OPEN=new Set();
function subsFor(key){return (DATA.subtasks&&DATA.subtasks[key])||[];}
function subCountLabel(key){const s=subsFor(key);return s.length?`${s.filter(x=>x.status==='done').length}/${s.length} steps`:'+ add steps';}
function subListHTML(key){const subs=subsFor(key);
 return `<div class="sublist">${subs.map(s=>`<div class="subitem ${s.status==='done'?'on':''}"><label><input type="checkbox" ${s.status==='done'?'checked':''} onchange="subToggle(${s.id},this.checked,'${key}')"><span>${esc(s.text)}</span></label><button class="subdel" title="Delete" onclick="subDel(${s.id},'${key}')">✕</button></div>`).join('')||'<div class="submt">No steps yet — add your own below.</div>'}
  <div class="subadd"><input id="sa_${key}" placeholder="Add a step…" onkeydown="if(event.key==='Enter')subAdd('${key}')"><button onclick="subAdd('${key}')">Add</button></div></div>`;}
function subExpand(key){if(DIST_OPEN.has(key))DIST_OPEN.delete(key);else DIST_OPEN.add(key);
 const r=document.getElementById('sub_'+key);if(r)r.classList.toggle('hidden',!DIST_OPEN.has(key));
 const cr=document.getElementById('cr_'+key);if(cr)cr.textContent=DIST_OPEN.has(key)?'▾':'▸';}
function updateSubCount(key){const el=document.getElementById('cnt_'+key);if(el)el.textContent=subCountLabel(key);}
async function subToggle(id,checked,key){const it=subsFor(key).find(s=>s.id===id);if(it)it.status=checked?'done':'todo';
 const box=event.target.closest('.subitem');if(box)box.classList.toggle('on',checked);updateSubCount(key);
 try{await j('/api/admin/subtask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'toggle',id,done:checked})});}catch(e){}}
async function subDel(id,key){DATA.subtasks[key]=subsFor(key).filter(s=>s.id!==id);
 const td=document.querySelector('#sub_'+key+' td');if(td)td.innerHTML=subListHTML(key);updateSubCount(key);
 try{await j('/api/admin/subtask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'delete',id})});}catch(e){}}
async function subAdd(key){const inp=document.getElementById('sa_'+key);if(!inp)return;const text=(inp.value||'').trim();if(!text)return;inp.value='';
 try{const r=await j('/api/admin/subtask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'add',parent:key,text})});
   if(r&&r.id){DATA.subtasks[key]=subsFor(key);DATA.subtasks[key].push({id:r.id,text:r.text,status:'todo'});
     const td=document.querySelector('#sub_'+key+' td');if(td)td.innerHTML=subListHTML(key);updateSubCount(key);
     const ni=document.getElementById('sa_'+key);if(ni)ni.focus();}}catch(e){}}
function dist(){const O=DATA.outlets,COLS=DATA.dist_cols;if(!DATA.subtasks)DATA.subtasks={};
 const doneN=o=>o.steps.filter((_,i)=>stepDone(o,i)).length;
 const totSteps=O.reduce((a,o)=>a+o.steps.length,0), totDone=O.reduce((a,o)=>a+doneN(o),0);
 const costClass=c=>c==='Free'?'free':(c==='Paid'?'paid':'mix');
 const cell=(o,i)=>{const s=o.steps[i];if(!s)return '<td class="x"></td>';const on=stepDone(o,i);
   return `<td class="cell ${on?'on':''}"><label class="mcell"><input type="checkbox" ${on?'checked':''} onchange="toggleStep('${o.key}',${i},this.checked)"><span>${esc(s)}</span></label></td>`;};
 const row=o=>{const d=doneN(o),n=o.steps.length,pct=Math.round(100*d/n);
   const nm=o.link?`<a href="${esc(o.link)}" target="_blank" rel="noopener">${esc(o.name)} ↗</a>`:esc(o.name);
   const open=DIST_OPEN.has(o.key);
   const main=`<tr class="${d===n?'rdone':''}"><td class="outlet"><div class="onm">${nm}</div>
     <div class="ometa"><span class="cost ${costClass(o.cost)}">${esc(o.cost)}</span>
     <span class="mini"><span class="mbar"><i style="width:${pct}%"></i></span>${d}/${n}</span></div>
     <button class="subx" onclick="subExpand('${o.key}')"><span class="caret" id="cr_${o.key}">${open?'▾':'▸'}</span> <span class="subcount" id="cnt_${o.key}">${subCountLabel(o.key)}</span></button></td>
     ${COLS.map((_,i)=>cell(o,i)).join('')}</tr>`;
   const sub=`<tr class="subrow ${open?'':'hidden'}" id="sub_${o.key}"><td colspan="${COLS.length+1}">${subListHTML(o.key)}</td></tr>`;
   return main+sub;};
 let rows='',lastCat=null;
 O.forEach(o=>{if(o.cat!==lastCat){lastCat=o.cat;
   rows+=`<tr class="catrow"><td colspan="${COLS.length+1}">${esc(o.cat)}</td></tr>`;}
   rows+=row(o);});
 $('#body').innerHTML=`<p class="sub">${totDone}/${totSteps} steps done · ${O.length} outlets. Each row is a channel; each column is a phase. Tap <b>▸</b> on any row to add your own sub-steps. Everything saves automatically.</p>
  <div class="matrix"><table class="mtx"><thead><tr><th class="outlet">Outlet</th>${COLS.map((c,i)=>`<th>${i+1} · ${esc(c)}</th>`).join('')}</tr></thead>
  <tbody>${rows}</tbody></table></div>
  <p class="sub" style="margin-top:12px">Copy for most of these lives in the <b onclick="go('materials')" style="cursor:pointer;color:var(--gold)">Materials</b> tab. The prioritized “what to do first” order is in <b onclick="go('pipeline')" style="cursor:pointer;color:var(--gold)">Pipeline</b>.</p>`;
}
async function notif(){const b=$('#body');b.innerHTML='<p class="sub">Loading…</p>';
 const n=await j('/api/admin/notifications');
 const kpi=(v,l)=>`<div class="kpi"><div class="n">${v}</div><div class="l">${l}</div></div>`;
 const rows=(n.by_category||[]).map(r=>`<tr><td>${esc(r.category)}</td><td>${r.sent}</td><td>${r.opened||0}</td><td>${r.sent?Math.round(100*(r.opened||0)/r.sent):0}%</td></tr>`).join('')||'<tr><td colspan=4>No sends yet</td></tr>';
 const recent=(n.recent||[]).map(r=>`<tr><td>${esc(r.category)}</td><td>${esc(r.title)}</td><td><span class="chip">${esc(r.status)}</span></td><td style="color:var(--mut);font-size:11px">${esc((r.created||'').slice(5,16))}</td></tr>`).join('')||'<tr><td colspan=4>Nothing yet</td></tr>';
 b.innerHTML=`<div class="grid">${kpi(n.opt_in+' ('+n.opt_in_pct+'%)','Opted in')}${kpi(n.tokens,'Devices')}${kpi(n.sent_7d,'Sent · 7d')}${kpi(n.queued,'Queued')}</div>
  <div class="card"><h3>By category</h3><table><tr><th>Category</th><th>Sent</th><th>Opened</th><th>Open rate</th></tr>${rows}</table></div>
  <div class="card"><h3>Send a test to your device</h3><p class="sub">Pushes to the phone(s) signed in as you. Needs a push-enabled build installed.</p>
   <button class="tab on" onclick="notifTest(this)">Send test push</button></div>
  <div class="card"><h3>Broadcast to all opted-in users</h3>
   <input id="bt" placeholder="Title (≤60)" style="width:100%;padding:9px;margin:4px 0;border-radius:8px;border:1px solid var(--line);background:#0f0d1c;color:var(--ink)">
   <textarea id="bb" placeholder="Message (≤160)" rows="2" style="width:100%;padding:9px;margin:4px 0;border-radius:8px;border:1px solid var(--line);background:#0f0d1c;color:var(--ink)"></textarea>
   <button class="tab on" onclick="notifBroadcast(this)">Send broadcast</button></div>
  <div class="card"><h3>Recent activity</h3><table><tr><th>Cat</th><th>Title</th><th>Status</th><th>When</th></tr>${recent}</table></div>`;
}
async function analytics(){const b=$('#body');b.innerHTML='<p class="sub">Loading…</p>';
 const a=await j('/api/admin/analytics');
 const kpi=(v,l)=>`<div class="kpi"><div class="n">${v}</div><div class="l">${l}</div></div>`;
 const F=a.onboarding_funnel||[];const top=F.length?(F[0].users||1):1;
 const funnelRows=F.map(f=>{const pct=Math.round(100*(f.users||0)/top);
   return `<div style="margin:7px 0"><div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px"><span>${esc(f.label)}</span><span>${f.users} · ${pct}%</span></div>
   <div style="height:10px;background:#1a1730;border-radius:6px;overflow:hidden"><div style="height:100%;width:${pct}%;background:linear-gradient(90deg,#f5c977,#e0a955)"></div></div></div>`;}).join('')||'<p class="sub">No onboarding events yet — open the app in a fresh browser to generate some.</p>';
 const scr=(a.screens||[]).map(s=>`<tr><td>${esc(s.screen)}</td><td>${s.views}</td><td>${s.users}</td></tr>`).join('')||'<tr><td colspan=3>No screen views yet</td></tr>';
 const dau=(a.daily_active||[]).map(d=>`<tr><td>${esc(d.day)}</td><td>${d.users}</td></tr>`).join('')||'<tr><td colspan=2>—</td></tr>';
 b.innerHTML=`<div class="grid">${kpi(a.visitors,'Visitors · '+a.days+'d')}${kpi(a.signups,'Signups · '+a.days+'d')}${kpi((a.onboarding_conv_pct!=null?a.onboarding_conv_pct+'%':'—'),'Onboarding complete')}${kpi(a.total_events,'Events')}</div>
  <div class="card"><h3>Onboarding funnel</h3><p class="sub">Distinct visitors reaching each step (${a.onboarding_start||0} started → ${a.onboarding_complete||0} reached signup).</p>${funnelRows}</div>
  <div class="card"><h3>Most-visited screens</h3><table><tr><th>Screen</th><th>Views</th><th>Users</th></tr>${scr}</table></div>
  <div class="card"><h3>Daily active (14d)</h3><table><tr><th>Day</th><th>Visitors</th></tr>${dau}</table></div>`;
}
async function notifTest(btn){btn.textContent='Sending…';const r=await j('/api/admin/notify/test',{method:'POST'});
 btn.textContent=r.ok?('Sent ✓ ('+r.tokens+' device)'):(r.error||'Failed');}
async function notifBroadcast(btn){const title=$('#bt').value.trim(),body=$('#bb').value.trim();
 if(!title||!body){btn.textContent='Title + message needed';return;}
 btn.textContent='Sending…';const r=await j('/api/admin/notify/broadcast',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,body})});
 btn.textContent=r.ok?('Sent to '+r.sent+' ✓'):(r.error||'Failed');notif();}
function block(label,text){const id='m'+Math.random().toString(36).slice(2,8);
 return `<div class="lbl">${esc(label)}<button class="copy" onclick="cp('${id}')">copy</button></div><div class="mat" id="${id}">${esc(text)}</div>`;}
function cp(id){const t=document.getElementById(id).textContent;navigator.clipboard.writeText(t);
 event.target.textContent='copied ✓';setTimeout(()=>event.target.textContent='copy',1200);}
function mats(){const M=DATA.materials;let h='';
 h+='<div class="card"><h3>App Store · ASO</h3>'+block('Title (30)',M.aso.title)+block('Subtitle (30)',M.aso.subtitle)+block('Keyword field (100)',M.aso.keywords)+`<p class="sub">${esc(M.aso.note)}</p>`+block('Description (v1 — launch)',M.app_store_description)+(M.app_store_description_v2?block('Improved description (v2 — all new features · paste this)',M.app_store_description_v2):'')+'</div>';
 h+='<div class="card"><h3>Custom Product Pages</h3>'+M.custom_pages.map(p=>block(p.angle+' — headline',p.headline)+block(p.angle+' — body',p.body)).join('')+'</div>';
 const ig=M.instagram;
 h+='<div class="card"><h3>Instagram ('+esc(ig.handle)+')</h3>'+block('Bio',ig.bio)+'<div class="lbl">Content pillars</div><div>'+ig.pillars.map(p=>`<span class="pill">${esc(p)}</span>`).join('')+'</div>'+block('12 captions',ig.captions.map((c,i)=>(i+1)+'. '+c).join('\n\n'))+block('2-week calendar',ig.calendar.join('\n'))+'</div>';
 h+='<div class="card"><h3>Short-form video scripts</h3>'+M.video_scripts.map(v=>block(v.title+' — "'+v.hook+'"',v.beats.map((b,i)=>(i+1)+'. '+b).join('\n'))).join('')+'</div>';
 const cm=M.community;
 h+='<div class="card"><h3>Community outreach</h3><p class="sub">'+esc(cm.reddit_rules)+'</p><div>'+cm.subreddits.map(s=>`<span class="pill">${esc(s)}</span>`).join('')+'</div>'+block('Reddit post',cm.reddit_post)+block('Discord intro',cm.discord_intro)+'</div>';
 const ph=M.product_hunt;
 h+='<div class="card"><h3>Product Hunt</h3>'+block('Tagline',ph.tagline)+block('Description',ph.description)+block('Maker first comment',ph.first_comment)+`<p class="sub">${esc(ph.timing)}</p>`+'</div>';
 const w=M.website_copy;
 h+='<div class="card"><h3>Website copy (live at /site)</h3>'+block('Hero headline',w.hero_h)+block('Hero subhead',w.hero_sub)+block('Features',w.features.map(f=>f.t+' — '+f.d).join('\n\n'))+'</div>';
 $('#body').innerHTML=h;
}
boot();
</script></body></html>"""


def site_page():
    w = MATERIALS["website_copy"]
    # brand icon set (real imagery, served from /art) in place of emoji
    feat_set = [
        ("feat_vedic", "A reading written in the sky", "Each day opens with a real Vedic reading — your sidereal rāśi and the Moon's nakshatra, grounded in classical Jyotish. Add your birth time for your birth star and daśā."),
        ("feat_pilgrimage", "Atlas", "Photograph every place you sit and build a photo streak. Travel somewhere new for bonus Light, collect the spot, and watch the world's places light up together."),
        ("feat_stoic", "Walk with the Stoics", "Short guided voice journeys with real guides. Tell Marcus Aurelius about your week and actually be answered."),
        ("feat_forge", "Meet The Forge", "For when you don't want to be soothed. The Forge replies direct and unsentimental — the obstacle is the way."),
        ("feat_streak", "An unbreakable streak", "Light, levels, and weekly leagues turn the habit into a flame you're scared to let go out."),
        ("feat_inward", "Go inward", "A private journal and shadow-work journeys. Sit with what's actually there — and come out a little more whole."),
    ]
    feats = "".join(
        f'<div class="f"><div class="fi"><img src="/art/{img}.png" alt="{t}" loading="lazy" '
        f'onerror="this.closest(\'.fi\').style.display=\'none\'"></div>'
        f'<h3>{t}</h3><p>{d}</p></div>' for img, t, d in feat_set)
    steps = "".join(
        f'<div class="step"><div class="sn">{i+1}</div><h4>{t}</h4><p>{d}</p></div>'
        for i, (t, d) in enumerate([
            ("Open today's sky", "Start with your Vedic reading — your rāśi and the Moon's nakshatra — then pick a guided journey and sit for a few minutes."),
            ("Light up a place", "Your session ignites your spot on a living world map. Snap a photo of where you sat and add it to your Atlas."),
            ("Build the streak", "Earn Light, keep your photo streak, climb the weekly league, and journal what surfaced."),
        ]))
    faqs = "".join(
        f'<details class="faq"><summary>{q}</summary><p>{a}</p></details>'
        for q, a in [
            ("Is Lumen free?", "Yes — free to start. You can meditate, journal, build streaks, get your daily reading, and light up the map without paying."),
            ("Is the Vedic reading real astrology?", "Yes. Your sign is your sidereal rāśi (Lahiri ayanāṁśa) and each day centers on the Moon's nakshatra, drawn from classical Jyotish — add your birth time for your birth star and Vimśottarī daśā."),
            ("Do I have to share my location or photos?", "No. Location is optional and deliberately coarsened, and the photos of your meditation spots are yours — they only appear to others if you choose to share them."),
            ("Is my journal private?", "Completely. Entries stay yours unless you explicitly choose to share one to the community feed."),
            ("What makes it different?", "It's the one meditation app that opens with a real Vedic reading, turns every sit into a photo you collect on a world map, and gives you a streak you're actually scared to break."),
        ])
    ig_url = "https://instagram.com/" + IG_HANDLE.lstrip("@")
    return (r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lumen — meditate, glow, and grow</title>
<meta name="description" content="__SUB__">
<meta property="og:title" content="Lumen — light up the world, one breath at a time">
<meta property="og:description" content="__SUB__"><meta property="og:type" content="website">
<meta name="theme-color" content="#0b0a12"><link rel="icon" href="/icon.svg">
<style>
:root{--bg:#0b0a12;--ink:#ece9f5;--mut:#b4acd0;--gold:#f5c977;--purp:#a855f7;--line:#2a2540}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:
 radial-gradient(1200px 700px at 50% -8%,rgba(168,85,247,.30),transparent 60%),
 radial-gradient(900px 600px at 85% 15%,rgba(245,201,119,.14),transparent 55%),var(--bg);
 color:var(--ink);font-family:ui-rounded,-apple-system,"Segoe UI",Roboto,system-ui,sans-serif;line-height:1.6}
.wrap{max-width:1000px;margin:0 auto;padding:0 20px}
header{position:sticky;top:0;z-index:9;backdrop-filter:blur(10px);background:rgba(11,10,18,.55);
 padding:14px 0;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line)}
.logo{font-weight:800;color:var(--gold);font-size:19px;display:flex;align-items:center;gap:8px}
.logo img{width:26px;height:26px;border-radius:7px}
.nav{display:flex;gap:18px;align-items:center}.nav a{color:var(--mut);text-decoration:none;font-size:14px;white-space:nowrap}
.nav a:hover{color:var(--ink)}
@media(max-width:620px){
 .nav{gap:12px}.nav a.navlink{display:none}
 .btn{padding:10px 16px;font-size:14px}.logo{font-size:17px}
}
.btn{display:inline-block;background:linear-gradient(90deg,var(--gold),var(--purp));color:#140f22;font-weight:800;
 text-decoration:none;padding:12px 22px;border-radius:999px;font-size:15px;box-shadow:0 10px 30px rgba(168,85,247,.35);transition:transform .15s}
.btn:hover{transform:translateY(-2px)}.btn.lg{padding:15px 30px;font-size:16px}
.hero{text-align:center;padding:60px 0 34px}
.badge{display:inline-block;border:1px solid var(--line);background:rgba(22,19,38,.7);color:var(--mut);
 border-radius:999px;padding:5px 14px;font-size:12.5px;margin-bottom:20px}
.hero h1{font-size:clamp(32px,6.5vw,60px);margin:0 0 16px;line-height:1.08;
 background:linear-gradient(90deg,#fff,var(--gold));-webkit-background-clip:text;background-clip:text;color:transparent}
.hero p{font-size:clamp(16px,2.6vw,21px);color:var(--mut);max-width:640px;margin:0 auto 28px}
.orbit{width:96px;height:96px;margin:0 auto 10px;display:block;border-radius:24px;
 filter:drop-shadow(0 0 28px rgba(245,201,119,.6));animation:float 5s ease-in-out infinite}
@keyframes float{50%{transform:translateY(-10px)}}
.sub2{color:var(--mut);font-size:13px;margin-top:14px}
h2.sec{text-align:center;font-size:clamp(22px,4vw,32px);margin:60px 0 6px}
.lead{text-align:center;color:var(--mut);max-width:560px;margin:0 auto 26px}
.feats{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}
.f{background:rgba(22,19,38,.7);border:1px solid var(--line);border-radius:18px;padding:22px}
.fi{margin-bottom:12px}.fi img{width:68px;height:68px;border-radius:16px;object-fit:cover;
 border:1px solid var(--line);box-shadow:0 6px 18px rgba(0,0,0,.45)}
.f h3{margin:0 0 6px;color:var(--gold);font-size:18px}.f p{margin:0;color:var(--mut);font-size:14.5px}
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}
.step{background:rgba(22,19,38,.5);border:1px solid var(--line);border-radius:18px;padding:22px;position:relative}
.sn{width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,var(--gold),var(--purp));
 color:#140f22;font-weight:800;display:grid;place-items:center;margin-bottom:10px}
.step h4{margin:0 0 6px;font-size:16px}.step p{margin:0;color:var(--mut);font-size:14px}
.quote{text-align:center;max-width:720px;margin:64px auto 0;font-size:clamp(20px,3.4vw,28px);line-height:1.4}
.quote span{color:var(--gold)}.quote .by{display:block;color:var(--mut);font-size:14px;margin-top:14px}
.faqs{max-width:720px;margin:14px auto 0}
.faq{border:1px solid var(--line);border-radius:14px;padding:4px 16px;margin:10px 0;background:rgba(22,19,38,.5)}
.faq summary{cursor:pointer;padding:14px 0;font-weight:600;font-size:15px;list-style:none}
.faq summary::-webkit-details-marker{display:none}
.faq summary::after{content:'+';float:right;color:var(--gold);font-size:20px}
.faq[open] summary::after{content:'–'}.faq p{margin:0 0 14px;color:var(--mut);font-size:14.5px}
.cta2{text-align:center;padding:70px 0 20px}.cta2 h2{font-size:clamp(24px,4vw,34px);margin:0 0 20px}
footer{text-align:center;color:var(--mut);font-size:13px;padding:44px 0 64px;border-top:1px solid var(--line);margin-top:50px}
footer a{color:var(--gold);text-decoration:none}
.anchor{margin:30px 0 8px}
.anchor-wrap{display:grid;grid-template-columns:1fr 1fr;gap:34px;align-items:center;
 background:linear-gradient(160deg,rgba(245,201,119,.11),rgba(168,85,247,.09));border:1px solid var(--line);border-radius:26px;padding:28px}
.anchor-art img{width:100%;border-radius:18px;box-shadow:0 24px 60px rgba(0,0,0,.5);border:1px solid var(--line);display:block}
.abadge{display:inline-block;border:1px solid var(--line);background:rgba(22,19,38,.7);color:var(--gold);border-radius:999px;padding:5px 13px;font-size:12.5px;margin-bottom:12px}
.anchor-copy h2{font-size:clamp(26px,4vw,38px);margin:0 0 12px;line-height:1.1;
 background:linear-gradient(90deg,#fff,var(--gold));-webkit-background-clip:text;background-clip:text;color:transparent}
.anchor-copy>p{color:var(--mut);margin:0 0 16px;font-size:16px}
.alist{list-style:none;padding:0;margin:0 0 20px;display:flex;flex-direction:column;gap:9px}
.alist li{color:var(--ink);font-size:14.5px;padding-left:24px;position:relative}
.alist li:before{content:'\2726';position:absolute;left:0;color:var(--gold)}
.anchor-cta{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:0}
.anchor-cta .price{font-size:26px;font-weight:800;color:var(--ink)}
.anchor-cta input{flex:1;min-width:160px;background:rgba(11,10,18,.6);border:1px solid var(--line);
 border-radius:999px;padding:12px 18px;color:var(--ink);font-size:15px;font-family:inherit}
.anchor-cta input:focus{outline:none;border-color:var(--gold)}
@media(max-width:720px){.anchor-wrap{grid-template-columns:1fr;gap:20px;padding:20px}}
</style></head><body>
<header class="wraphd"><div class="wrap" style="display:flex;justify-content:space-between;align-items:center;padding:0">
<div class="logo"><img src="/icon.svg" alt="Lumen"> Lumen</div>
<nav class="nav"><a class="navlink" href="#journal">The Journal</a><a class="navlink" href="#how">How it works</a><a class="navlink" href="#features">Features</a><a class="navlink" href="#faq">FAQ</a><a class="btn" href="__APP__">__CTA__</a></nav>
</div></header>
<div class="wrap">
<section class="hero"><img class="orbit" src="/icon.svg" alt="Lumen">
<div class="badge">Now on the App Store</div>
<h1>__H__</h1><p>__SUB__</p><a class="btn lg" href="__APP__">__CTA__</a>
<div class="sub2">Free to start · Your journal stays private</div></section>

<section id="journal" class="anchor">
<div class="anchor-wrap">
  <div class="anchor-art"><img src="/art/lumen-journal.png" alt="The Lumen Journal" loading="lazy" onerror="this.closest('.anchor-art').style.display='none'"></div>
  <div class="anchor-copy">
    <div class="abadge">★ The anchor · a companion you can hold</div>
    <h2>The Lumen Journal</h2>
    <p>The guided practice of the app, in your hands. The eight life pillars, the season you're in, and a year of evening prompts — printed on cream dot-grid paper, bound in a linen hardcover with a gold ribbon and gilded edges.</p>
    <ul class="alist">
      <li>The 8 pillar lesson plans — the same guided chapters as in-app</li>
      <li>The Season program — name and tend the chapter you're living through</li>
      <li>A year of evening prompts, with open dot-grid pages to go deeper</li>
      <li>Linen hardcover · gilded edges · gold ribbon · ships worldwide</li>
    </ul>
    <form id="wl" class="anchor-cta">
      <span class="price">$32</span>
      <input id="wlemail" type="email" placeholder="your@email.com" required>
      <button class="btn" type="submit">Reserve yours</button>
    </form>
    <div class="sub2" id="wlmsg">Printed to order · reserve yours and we'll email you the moment it ships.</div>
  </div>
</div></section>

<section id="how"><h2 class="sec">Three minutes a day</h2><p class="lead">A loop simple enough to keep, gratifying enough to miss.</p>
<div class="steps">__STEPS__</div></section>

<section id="features"><h2 class="sec">Why it sticks</h2><p class="lead">Everything in Lumen is built around one idea: make the practice something you look forward to.</p>
<div class="feats">__FEATS__</div></section>

<div class="quote">"Talk to <span>Marcus Aurelius</span> about your bad week — then watch your light spread across the map."
<span class="by">— the one meditation app you won't quit on day 3</span></div>

<section id="faq"><h2 class="sec">Questions</h2><div class="faqs">__FAQS__</div></section>

<section class="cta2"><h2>Start your streak tonight.</h2><a class="btn lg" href="__APP__">__CTA__</a></section>
</div>
<footer>Lumen · <a href="/privacy">Privacy</a> · <a href="__IG__">Instagram</a> · <a href="__APP__">App Store</a><br>© 2026 Lumen. Light up the world.</footer>
<script>
(function(){var f=document.getElementById('wl');if(!f)return;
 f.addEventListener('submit',function(e){e.preventDefault();
  var em=(document.getElementById('wlemail').value||'').trim();var m=document.getElementById('wlmsg');
  fetch('/api/waitlist',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:em})})
   .then(function(r){return r.json();}).then(function(d){
     if(d&&d.ok){f.style.display='none';m.textContent='✦ You are on the list — we will email you the moment it ships.';m.style.color='#f5c977';}
     else{m.textContent=(d&&d.error)||'Something went wrong — please try again.';}
   }).catch(function(){m.textContent='Something went wrong — please try again.';});
 });})();
</script>
</body></html>"""
            .replace("__H__", w["hero_h"]).replace("__SUB__", w["hero_sub"])
            .replace("__CTA__", w["cta"]).replace("__APP__", APP_STORE_URL)
            .replace("__FEATS__", feats).replace("__STEPS__", steps).replace("__FAQS__", faqs)
            .replace("__IG__", ig_url))


# ===========================================================================
# NOTIFICATION SERVICE  (see NOTIFICATIONS.md)
# Two paths (event celebrations + time-based nudges) through one arbiter:
# per-user daily cap, local quiet hours, category prefs, and dedupe.
# ===========================================================================

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
NOTIF_CATS = ["reminder", "streak", "progress", "journal", "community", "discovery", "winback"]
DEFAULT_CATS = {k: 1 for k in NOTIF_CATS}
TIME_CATS = ("daily_reminder", "streak_save", "weekly_recap", "winback")  # count toward daily cap
DAILY_CAP = 1          # automatic time-based sends per local day
CELEBRATION_CAP = 3    # event celebrations per local day
MILESTONES = (7, 30, 50, 100, 365)
_ACH_DESC = {a[0]: f"{a[3]} {a[1]} — {a[2]}" for a in ACHIEVEMENTS}


def _notif_prefs(c, user_id):
    r = c.execute("SELECT * FROM notif_prefs WHERE user_id=?", (user_id,)).fetchone()
    if not r:
        c.execute("INSERT OR IGNORE INTO notif_prefs(user_id,cats,updated) VALUES(?,?,?)",
                  (user_id, json.dumps(DEFAULT_CATS), now_iso()))
        c.commit()
        r = c.execute("SELECT * FROM notif_prefs WHERE user_id=?", (user_id,)).fetchone()
    return r


def _notif_local(prefs):
    return datetime.now(timezone.utc) + timedelta(minutes=(prefs["tz_offset_min"] or 0))


def _notif_quiet(prefs, lt):
    qs, qe, h = prefs["quiet_start"], prefs["quiet_end"], lt.hour
    if qs == qe:
        return False
    return (qs <= h < qe) if qs < qe else (h >= qs or h < qe)


def _days_since(last_day):
    if not last_day:
        return 999
    try:
        return (datetime.now(timezone.utc).date() - date.fromisoformat(last_day[:10])).days
    except Exception:
        return 999


def _notif_tier(user):
    if (user["total_sessions"] or 0) == 0:
        return "new"
    ds = _days_since(user["last_day"])
    if ds <= 1:
        return "habitual"
    if ds <= 6:
        return "at_risk"
    if ds <= 29:
        return "dormant"
    return "churned"


def _modal_hour(c, user_id, off):
    from collections import Counter
    cnt = Counter()
    for r in c.execute("SELECT ended FROM sessions WHERE user_id=? AND ended IS NOT NULL "
                       "ORDER BY id DESC LIMIT 60", (user_id,)):
        try:
            cnt[(int(r["ended"][11:13]) + off // 60) % 24] += 1
        except Exception:
            pass
    return cnt.most_common(1)[0][0] if cnt else 19  # default 7pm local


def _notif_personalize(kind, user):
    name = (user["name"] or "there").split()[0]
    streak = user["streak"] or 0
    prompt = (f'Write ONE short push notification for a calm meditation app "Lumen". '
              f'User first name: {name}. Current streak: {streak} days. Intent: {kind}. '
              f'Tone: warm, calm, direct, NEVER guilt-tripping or anxious. Body under 12 words. '
              f'Return strict JSON {{"title":"...","body":"..."}} with title <= 5 words.')
    try:
        r = gemini_json(prompt, timeout=6)
    except Exception:
        r = None
    if r and r.get("title") and r.get("body"):
        return str(r["title"])[:60], str(r["body"])[:160]
    return None


def notif_copy(kind, user, ctx=None, personalize=False):
    ctx = ctx or {}
    name = (user["name"] or "there").split()[0]
    streak = user["streak"] or 0
    T = {
        "daily_reminder": ("A moment for you", f"{name}, three minutes with the breath before the day closes?"),
        "streak_save": (f"Your {streak}-day flame is still lit", "Keep it burning — just three minutes tonight."),
        "weekly_recap": ("Your week in light", f"{ctx.get('sessions',0)} sits, +{ctx.get('light',0)} Light this week. Quietly proud of you."),
        "winback": ("The map is still glowing", "No streak pressure — a 3-minute reset whenever you're ready."),
        "level_up": ("You leveled up ✨", f"Your practice is compounding, {name}. New light unlocked."),
        "achievement": ("Achievement unlocked", ctx.get("desc", "You earned something new.")),
        "milestone": (f"{streak}-day streak 🔥", "That's real consistency. Proud of you."),
        "journal_nudge": (ctx.get("title", "Your journal is waiting"),
                          ctx.get("body", "A few honest lines, whenever you're ready.")),
        "broadcast": (ctx.get("title", "Lumen"), ctx.get("body", "")),
    }
    title, body = T.get(kind, ("Lumen", ""))
    if personalize and kind in ("daily_reminder", "winback"):
        p = _notif_personalize(kind, user)
        if p:
            title, body = p
    return title, body


def expo_push_send(c, tokens, title, body, data=None):
    """Send via the Expo Push API and honour the per-ticket response.

    Expo returns HTTP 200 even when individual messages fail, with one ticket
    per message in `data`. We must read those tickets: a success is only a
    ticket with status "ok", and a `DeviceNotRegistered` ticket means the token
    is dead (app uninstalled / reinstalled / token rotated) and must be pruned
    so we stop sending to it and metrics don't record phantom deliveries.
    Returns True only if at least one message was accepted by Expo.
    """
    sent_toks = [t for t in tokens if t and t.startswith("ExponentPushToken")]
    if not sent_toks:
        return False
    msgs = [{"to": t, "title": title, "body": body, "sound": "default",
             "data": data or {}} for t in sent_toks]
    try:
        req = urllib.request.Request(EXPO_PUSH_URL, data=json.dumps(msgs).encode(),
                                     headers={"Content-Type": "application/json",
                                              "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads((r.read() or b"{}").decode() or "{}")
    except Exception:
        return False
    tickets = resp.get("data")
    if not isinstance(tickets, list):
        return False
    any_ok = False
    dead = []
    for tok, tk in zip(sent_toks, tickets):
        if not isinstance(tk, dict):
            continue
        if tk.get("status") == "ok":
            any_ok = True
        elif ((tk.get("details") or {}).get("error")) == "DeviceNotRegistered":
            dead.append(tok)
    if dead:
        try:
            c.executemany("DELETE FROM push_tokens WHERE token=?", [(t,) for t in dead])
            c.commit()
        except Exception:
            pass
    return any_ok


def _dedup_exists(c, uid, dk):
    return bool(c.execute("SELECT 1 FROM notif_log WHERE user_id=? AND dedupe_key=? LIMIT 1",
                          (uid, dk)).fetchone())


def _notif_enqueue(c, uid, category, title, body, dk):
    if _dedup_exists(c, uid, dk):
        return False
    c.execute("INSERT INTO notif_log(user_id,category,title,body,dedupe_key,status,created) "
              "VALUES(?,?,?,?,?,?,?)", (uid, category, title, body, dk, "queued", now_iso()))
    return True


def _tokens_for(c, uid):
    return [r["token"] for r in c.execute("SELECT token FROM push_tokens WHERE user_id=?", (uid,))]


def _sent_today_count(c, uid, cats):
    ph = ",".join("?" for _ in cats)
    return c.execute(f"SELECT COUNT(*) n FROM notif_log WHERE user_id=? AND status='sent' "
                     f"AND substr(created,1,10)=? AND category IN ({ph})",
                     (uid, today_str(), *cats)).fetchone()["n"]


def notif_on_complete(c, user, new_ach, leveled_up, streak):
    """Event path: enqueue celebrations right after a completed session."""
    uid = user["id"]
    if leveled_up:
        _notif_enqueue(c, uid, "progress", *notif_copy("level_up", user),
                       f"level_up:{level_for(user['light'])[0]}")
    for code in (new_ach or []):
        _notif_enqueue(c, uid, "progress", *notif_copy("achievement", user, {"desc": _ACH_DESC.get(code, "You earned something new.")}),
                       f"achievement:{code}")
    if streak in MILESTONES:
        _notif_enqueue(c, uid, "progress", *notif_copy("milestone", user), f"milestone:{streak}")


def _notif_flush_queued(c):
    """Send queued celebrations; respect quiet hours, celebration cap, 24h expiry."""
    now = datetime.now(timezone.utc)
    for n in c.execute("SELECT * FROM notif_log WHERE status='queued' ORDER BY id LIMIT 300").fetchall():
        u = c.execute("SELECT * FROM users WHERE id=?", (n["user_id"],)).fetchone()
        try:
            age_h = (now - datetime.fromisoformat(n["created"])).total_seconds() / 3600
        except Exception:
            age_h = 0
        if not u or age_h > 24:
            c.execute("UPDATE notif_log SET status='void' WHERE id=?", (n["id"],)); continue
        prefs = _notif_prefs(c, u["id"])
        cats = json.loads(prefs["cats"] or "{}")
        if not prefs["enabled"] or not cats.get("progress", 1):
            c.execute("UPDATE notif_log SET status='void' WHERE id=?", (n["id"],)); continue
        lt = _notif_local(prefs)
        if _notif_quiet(prefs, lt):
            continue  # try again after quiet hours
        if _sent_today_count(c, u["id"], ("progress",)) >= CELEBRATION_CAP:
            continue
        toks = _tokens_for(c, u["id"])
        ok = expo_push_send(c, toks, n["title"], n["body"], {"category": n["category"]}) if toks else False
        c.execute("UPDATE notif_log SET status=?, sent=? WHERE id=?",
                  ("sent" if ok else ("failed" if toks else "no_token"),
                   now_iso() if ok else None, n["id"]))
    c.commit()


_JOURNAL_NUDGE = {
    "deep": ("Deep work is waiting", "Pick a pillar and sit with it for a few lines."),
    "daily": ("A moment for your journal", "A quick daily check-in with yourself tonight?"),
    "season": ("The season you're in", "What chapter of life are you living through right now?"),
}


def _journal_week_missing(c, uid):
    """Which of the three journaling categories haven't been written this ISO week."""
    today = datetime.now(timezone.utc).date()
    monday = (today - timedelta(days=today.weekday())).isoformat()
    counts = {k: 0 for k in JOURNAL_KINDS}
    for r in c.execute("SELECT COALESCE(kind,'daily') k, COUNT(*) n FROM journal "
                       "WHERE user_id=? AND substr(created,1,10)>=? GROUP BY k",
                       (uid, monday)).fetchall():
        if r["k"] in counts:
            counts[r["k"]] += r["n"]
    return [k for k in JOURNAL_KINDS if counts[k] == 0], counts


def _notif_candidate(c, u, prefs, lt):
    """Return (category, title, body, dedupe_key) for the top time-based nudge, or None."""
    cats = json.loads(prefs["cats"] or "{}")
    off = prefs["tz_offset_min"] or 0
    h, wd = lt.hour, lt.weekday()           # Mon=0 … Sun=6
    tier = _notif_tier(u)
    sat_today = (u["last_day"] or "")[:10] == today_str()
    yesterday = (date.fromisoformat(today_str()) - timedelta(days=1)).isoformat()
    streak_alive = (u["last_day"] or "")[:10] == yesterday
    # 1) streak-save (highest)
    if cats.get("streak", 1) and (u["streak"] or 0) >= 2 and streak_alive and h >= 18:
        return ("streak_save", *notif_copy("streak_save", u), f"streak_save:{today_str()}")
    # 2) weekly recap — Sunday evening
    if cats.get("progress", 1) and wd == 6 and 18 <= h < 22:
        row = c.execute("SELECT COALESCE(SUM(light),0) s, COUNT(*) n FROM sessions "
                        "WHERE user_id=? AND week=?", (u["id"], week_str())).fetchone()
        if row["n"] > 0:
            return ("weekly_recap", *notif_copy("weekly_recap", u, {"light": row["s"], "sessions": row["n"]}),
                    f"weekly_recap:{week_str()}")
    # 2b) journal rhythm — nudge toward a journaling category still untouched this
    #     week, so Deep / Daily / Season all get visited. Only for people already
    #     journaling (never a cold nag); at most once per category per week.
    if cats.get("journal", 1) and tier in ("new", "habitual", "at_risk") and 2 <= wd <= 5 and h == 18:
        missing, counts = _journal_week_missing(c, u["id"])
        if missing and sum(counts.values()) > 0:
            cat_k = missing[0]
            title, body = _JOURNAL_NUDGE[cat_k]
            return ("journal", *notif_copy("journal_nudge", u, {"title": title, "body": body}),
                    f"journal_week:{week_str()}:{cat_k}")
    # 3) daily reminder — send-time optimized (learned modal hour once we have
    #    history, else the practice time they chose during onboarding, else 7pm)
    if cats.get("reminder", 1) and not sat_today and tier in ("new", "habitual", "at_risk"):
        pref_hour = prefs["pref_hour"] if prefs["pref_hour"] is not None else 19
        learned = (u["total_sessions"] or 0) >= 5
        target = _modal_hour(c, u["id"], off) if (prefs["sto"] and learned) else pref_hour
        if h == target:
            return ("daily_reminder", *notif_copy("daily_reminder", u, personalize=True),
                    f"reminder:{today_str()}")
    # 4) win-back — gentle, rate-limited
    if cats.get("winback", 1) and tier in ("dormant", "churned") and h == 12:
        if tier == "dormant" and (lt.timetuple().tm_yday % 3 == 0):
            return ("winback", *notif_copy("winback", u, personalize=True), f"winback:{today_str()}")
        if tier == "churned" and wd == 0:
            return ("winback", *notif_copy("winback", u, personalize=True), f"winback:{week_str()}")
    return None


def _notif_time_pass(c):
    """Evaluate every opted-in, reachable user for a time-based nudge."""
    users = c.execute("SELECT DISTINCT u.* FROM users u JOIN push_tokens p ON p.user_id=u.id "
                      "WHERE u.is_bot=0").fetchall()
    for u in users:
        prefs = _notif_prefs(c, u["id"])
        if not prefs["enabled"]:
            continue
        lt = _notif_local(prefs)
        if _notif_quiet(prefs, lt):
            continue
        if _sent_today_count(c, u["id"], TIME_CATS) >= DAILY_CAP:
            continue
        cand = _notif_candidate(c, u, prefs, lt)
        if not cand:
            continue
        cat, title, body, dk = cand
        if _dedup_exists(c, u["id"], dk):
            continue
        toks = _tokens_for(c, u["id"])
        ok = expo_push_send(c, toks, title, body, {"category": cat})
        c.execute("INSERT INTO notif_log(user_id,category,title,body,dedupe_key,status,created,sent) "
                  "VALUES(?,?,?,?,?,?,?,?)",
                  (u["id"], cat, title, body, dk, "sent" if ok else "failed",
                   now_iso(), now_iso() if ok else None))
    c.commit()


def notif_tick():
    with _dblock:
        c = db()
        try:
            _notif_flush_queued(c)
            _notif_time_pass(c)
        except Exception as e:
            print("notif_tick error:", e)
        finally:
            c.close()


def notif_loop():
    time.sleep(20)  # let the server settle on boot
    while True:
        notif_tick()
        time.sleep(900)  # every 15 minutes


def notif_admin_stats(c):
    def one(q, a=()):
        r = c.execute(q, a).fetchone(); return (r[0] if r else 0) or 0
    users = max(1, one("SELECT COUNT(*) FROM users WHERE is_bot=0 AND name IS NOT NULL"))
    optin = one("SELECT COUNT(DISTINCT user_id) FROM push_tokens")
    by_cat = [dict(r) for r in c.execute(
        "SELECT category, COUNT(*) sent, SUM(CASE WHEN opened IS NOT NULL THEN 1 ELSE 0 END) opened "
        "FROM notif_log WHERE status='sent' GROUP BY category ORDER BY sent DESC")]
    recent = [dict(r) for r in c.execute(
        "SELECT category,title,body,status,created FROM notif_log ORDER BY id DESC LIMIT 25")]
    sent7 = one("SELECT COUNT(*) FROM notif_log WHERE status='sent' AND created >= ?",
                ((datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),))
    return {"opt_in": optin, "opt_in_pct": round(100.0 * optin / users),
            "tokens": one("SELECT COUNT(*) FROM push_tokens"),
            "sent_7d": sent7, "queued": one("SELECT COUNT(*) FROM notif_log WHERE status='queued'"),
            "by_category": by_cat, "recent": recent}


# ===========================================================================
# LIFECYCLE EMAIL ENGINE — welcome + onboarding drip + win-back + weekly
# recap + free→premium upgrade nudges. Mirrors the push system: rules-based
# "next best email", de-duped via email_log, opt-out honoured, frequency
# capped. SENDING IS GATED by EMAIL_MODE so it never blasts real users until
# it's explicitly turned on:
#   EMAIL_MODE=off      -> engine idle (nothing logged or sent)
#   EMAIL_MODE=dryrun   -> decides + logs who WOULD get what; sends nothing (default)
#   EMAIL_MODE=on       -> actually sends via Resend
# ===========================================================================
EMAIL_MODE = (os.environ.get("EMAIL_MODE", "dryrun") or "dryrun").strip().lower()
PUBLIC_URL = (os.environ.get("LUMEN_PUBLIC_URL", "https://lumen-production-a8c6.up.railway.app")).rstrip("/")
EMAIL_SEND_HOUR_LOCAL = 10      # local hour marketing emails go out (recap uses 17)


def _user_tz_off(c, u):
    """Best guess of the user's UTC offset in minutes (for local-hour targeting)."""
    try:
        r = c.execute("SELECT tz_offset_min FROM notif_prefs WHERE user_id=?", (u["id"],)).fetchone()
        if r and r["tz_offset_min"] is not None:
            return int(r["tz_offset_min"])
    except Exception:
        pass
    try:
        if u["birth_tz"] is not None:
            return int(u["birth_tz"])
    except Exception:
        pass
    return -300  # default US-Eastern-ish


def _email_local(c, u):
    return datetime.now(timezone.utc) + timedelta(minutes=_user_tz_off(c, u))


def _email_has(c, uid, dk):
    return bool(c.execute("SELECT 1 FROM email_log WHERE user_id=? AND dedupe_key=? LIMIT 1",
                          (uid, dk)).fetchone())


def _email_recent_marketing(c, uid, days):
    """True if any soft/marketing email went out in the last N days (recap/welcome exempt)."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return bool(c.execute(
        "SELECT 1 FROM email_log WHERE user_id=? AND created>=? AND status IN ('sent','dryrun') "
        "AND kind IN ('first_nudge','tip','winback','upgrade') LIMIT 1", (uid, since)).fetchone())


def _unsub_token(c, u):
    tok = u["unsub_token"] if "unsub_token" in u.keys() else None
    if not tok:
        tok = secrets.token_urlsafe(18)
        c.execute("UPDATE users SET unsub_token=? WHERE id=?", (tok, u["id"]))
        c.commit()
    return tok


def _is_premium(u):
    try:
        return (u["tier"] or "free") == "premium"
    except Exception:
        return False


def _email_shell(headline, paras, cta_text, cta_url, unsub_url, preheader=""):
    """A dark, on-brand responsive HTML email + a plain-text fallback."""
    body = "".join(
        f'<p style="margin:0 0 16px;color:#d8d2e8;font-size:16px;line-height:1.6">{p}</p>' for p in paras)
    html = f"""<!doctype html><html><body style="margin:0;background:#0b0a12;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">{preheader}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0b0a12;padding:28px 12px">
<tr><td align="center">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;background:#14111f;border:1px solid #2a2440;border-radius:20px;overflow:hidden">
    <tr><td style="padding:34px 32px 8px;text-align:center">
      <div style="font-family:Georgia,'Times New Roman',serif;font-size:30px;font-weight:700;color:#f5c977;letter-spacing:.5px">lumen</div>
      <div style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#8f8a9d;margin-top:6px">light, one breath at a time</div>
    </td></tr>
    <tr><td style="padding:18px 32px 4px">
      <h1 style="margin:0 0 14px;font-family:Georgia,serif;font-size:25px;line-height:1.25;color:#f6f1ea;font-weight:700">{headline}</h1>
      {body}
    </td></tr>
    <tr><td style="padding:10px 32px 30px" align="center">
      <a href="{cta_url}" style="display:inline-block;background:linear-gradient(135deg,#f5c977,#e0953a);color:#2a1a05;text-decoration:none;font-weight:700;font-size:16px;padding:14px 30px;border-radius:14px">{cta_text}</a>
    </td></tr>
    <tr><td style="padding:0 32px 30px;text-align:center;border-top:1px solid #241f38">
      <p style="margin:18px 0 0;color:#6f6a82;font-size:12px;line-height:1.6">
        You're getting this because you have a Lumen account.<br>
        <a href="{unsub_url}" style="color:#8f8a9d;text-decoration:underline">Unsubscribe</a> from these emails anytime.
      </p>
    </td></tr>
  </table>
</td></tr></table></body></html>"""
    text = "lumen — light, one breath at a time\n\n" + headline + "\n\n" + \
        "\n\n".join(re.sub("<[^>]+>", "", p) for p in paras) + \
        f"\n\n{cta_text}: {cta_url}\n\nUnsubscribe: {unsub_url}"
    return html, text


def _email_tpl(kind, c, u, ctx=None):
    """Return (subject, html, text) for a lifecycle email kind, or None."""
    ctx = ctx or {}
    name = ((u["name"] or "there").split() or ["there"])[0]
    app = APP_STORE_URL
    unsub = f"{PUBLIC_URL}/e/unsub?u={_unsub_token(c, u)}"
    def shell(hl, paras, cta, url=app, pre=""):
        return _email_shell(hl, paras, cta, url, unsub, pre)
    if kind == "welcome":
        s = "Welcome to Lumen ✦"
        hl = f"Welcome, {name}."
        paras = [
            "You just joined a worldwide community lighting up the map — one quiet breath at a time.",
            "Your first sit is the best place to start. Even three minutes counts, and it lights your very first point on the living world map.",
            "When you're ready: open Lumen, pick a soundscape, and simply sit."]
        return (s, *shell(hl, paras, "Take your first breath", pre="Your first sit lights the map."))
    if kind == "first_nudge":
        s = "Your first point of light is waiting"
        hl = "A single breath is enough to begin."
        paras = [
            f"{name}, you haven't taken your first sit yet — and that's okay. There's no streak to protect, nothing to catch up on.",
            "Just three minutes, whenever it's quiet. The map is waiting to light up where you are."]
        return (s, *shell(hl, paras, "Sit for three minutes", pre="No pressure — just a gentle start."))
    if kind == "weekly_recap":
        sits, light = ctx.get("sessions", 0), ctx.get("light", 0)
        s = "Your week in light"
        hl = f"{sits} {'sit' if sits==1 else 'sits'} this week."
        paras = [
            f"This week you sat {sits} {'time' if sits==1 else 'times'} and earned <b style=\"color:#f5c977\">+{light} Light</b>" +
            (f", keeping a {u['streak']}-day streak alive." if (u['streak'] or 0) > 1 else "."),
            "Quietly proud of you. A few minutes tomorrow keeps the thread going."]
        return (s, *shell(hl, paras, "Continue your practice", pre=f"{sits} sits · +{light} Light"))
    if kind == "winback":
        s = "The map is still glowing for you"
        hl = "Whenever you're ready, we're here."
        paras = [
            f"It's been a little while, {name}. No streak pressure, no guilt — your place on the map is exactly where you left it.",
            "A three-minute reset is a perfectly good way back in."]
        return (s, *shell(hl, paras, "Come back for a breath", pre="No pressure — a gentle way back."))
    if kind == "tip":
        s = ctx.get("subject", "A little more from Lumen")
        hl = ctx.get("headline", "Something you might have missed")
        paras = ctx.get("paras", [])
        return (s, *shell(hl, paras, ctx.get("cta", "Open Lumen"), pre=ctx.get("pre", "")))
    if kind == "upgrade":
        s = "Go deeper with Lumen Premium"
        hl = "You've built a real practice."
        paras = [
            f"{name}, your consistency is showing — and there's more waiting when you're ready to go deeper.",
            "<b style=\"color:#f5c977\">Lumen Premium</b> (coming soon) will unlock the full library of journeys, deeper Vedic readings, and more ways to grow your mandala.",
            "Want first access and a founding-member price? Tap below to raise your hand."]
        return (s, *shell(hl, paras, "I'm interested in Premium",
                          url=f"{PUBLIC_URL}/e/premium?u={_unsub_token(c, u)}",
                          pre="Something more, when you're ready."))
    return None


def _email_candidate(c, u, lt):
    """Pick the single best lifecycle email for a user right now, or None.
    Returns (kind, subject, html, text, dedupe_key)."""
    h, wd = lt.hour, lt.weekday()
    tier = _notif_tier(u)
    sessions = u["total_sessions"] or 0
    ds_signup = _days_since(u["created"]) if u["created"] else 999
    # weekly recap — Sunday evening, for anyone who sat this week
    if wd == 6 and h == 17:
        row = c.execute("SELECT COALESCE(SUM(light),0) s, COUNT(*) n FROM sessions WHERE user_id=? AND week=?",
                        (u["id"], week_str())).fetchone()
        if row and row["n"] > 0:
            dk = f"weekly_recap:{week_str()}"
            if not _email_has(c, u["id"], dk):
                t = _email_tpl("weekly_recap", c, u, {"sessions": row["n"], "light": row["s"]})
                if t:
                    return ("weekly_recap", t[0], t[1], t[2], dk)
    if h != EMAIL_SEND_HOUR_LOCAL:
        return None
    # one soft/marketing email at a time, and never two within 3 days
    if _email_recent_marketing(c, u["id"], 3):
        return None
    # first-sit nudge — signed up, still zero sessions (once, days 2–6)
    if sessions == 0 and 2 <= ds_signup <= 6:
        dk = "first_nudge"
        if not _email_has(c, u["id"], dk):
            t = _email_tpl("first_nudge", c, u)
            if t:
                return ("first_nudge", t[0], t[1], t[2], dk)
    # onboarding tips — day ~3 and ~10, for active users
    if sessions >= 1:
        for day_at, key, ctx in (
            (3, "tip:journeys", {"subject": "Guided journeys are the heart of Lumen",
                 "headline": "Let a real tradition guide you.",
                 "paras": ["Beyond the timer, Lumen has narrated <b style=\"color:#f5c977\">Journeys</b> — guided courses drawn from Stoic, Vedic and breathwork traditions.",
                           "Open the Journeys tab and start the one that calls to you."],
                 "cta": "Explore Journeys", "pre": "There's more than the timer."}),
            (10, "tip:journal", {"subject": "Meet the Keeper — your journal companion",
                 "headline": "A few honest lines change everything.",
                 "paras": ["Lumen's <b style=\"color:#f5c977\">Journal</b> gives you a warm companion, the Keeper, who reflects back the throughline in what you write.",
                           "Try a single entry after your next sit."],
                 "cta": "Open your journal", "pre": "Reflection makes it stick."})):
            if ds_signup >= day_at and not _email_has(c, u["id"], key):
                t = _email_tpl("tip", c, u, ctx)
                if t:
                    return ("tip", t[0], t[1], t[2], key)
    # win-back — dormant/churned, gently rate-limited
    if tier in ("dormant", "churned"):
        dk = f"winback:{week_str()}"
        if not _email_has(c, u["id"], dk):
            t = _email_tpl("winback", c, u)
            if t:
                return ("winback", t[0], t[1], t[2], dk)
    # upgrade nudge — hooked free users, at most monthly
    if (not _is_premium(u)) and (sessions >= 7 or (u["streak"] or 0) >= 5):
        dk = f"upgrade:{lt.year}-{(lt.month-1)//1:02d}"  # ~once a month
        if not _email_has(c, u["id"], dk):
            t = _email_tpl("upgrade", c, u)
            if t:
                return ("upgrade", t[0], t[1], t[2], dk)
    return None


def _email_deliver(c, u, kind, subject, html, text, dk):
    """Send (or dry-run) one lifecycle email, honouring opt-out + mode, and log it."""
    if EMAIL_MODE == "off":
        return
    if not u["email"] or (u["email_optout"] if "email_optout" in u.keys() else 0):
        return
    if _email_has(c, u["id"], dk):
        return
    status = "dryrun"
    if EMAIL_MODE == "on":
        try:
            ok = send_email(u["email"], subject, text, html=html)
            status = "sent" if ok else "failed"
        except Exception:
            status = "failed"
    c.execute("INSERT INTO email_log(user_id,kind,dedupe_key,status,created,sent) VALUES(?,?,?,?,?,?)",
              (u["id"], kind, dk, status, now_iso(), now_iso() if status == "sent" else None))
    c.commit()


def email_welcome(c, u):
    """Fire the welcome email immediately on signup (deduped, mode-gated)."""
    try:
        t = _email_tpl("welcome", c, u)
        if t:
            _email_deliver(c, u, "welcome", t[0], t[1], t[2], "welcome")
    except Exception as e:
        print("[email] welcome failed:", e, flush=True)


def _welcome_async(uid):
    """Send the welcome email off the signup request thread (own db connection)."""
    with _dblock:
        c = db()
        try:
            u = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            if u:
                email_welcome(c, u)
        except Exception as e:
            print("[email] welcome_async failed:", e, flush=True)
        finally:
            c.close()


def _email_pass(c):
    if EMAIL_MODE == "off":
        return
    users = c.execute("SELECT * FROM users WHERE is_bot=0 AND email IS NOT NULL "
                      "AND COALESCE(email_optout,0)=0").fetchall()
    for u in users:
        try:
            # welcome: only genuinely-new accounts (<=2 days). Pre-existing users are
            # marked welcomed (status 'skipped') so enabling the engine never blasts a
            # "you just joined" email to the whole existing base.
            if not _email_has(c, u["id"], "welcome"):
                if u["created"] and _days_since(u["created"]) <= 2:
                    email_welcome(c, u)
                else:
                    c.execute("INSERT INTO email_log(user_id,kind,dedupe_key,status,created,sent) "
                              "VALUES(?,?,?,?,?,?)", (u["id"], "welcome", "welcome", "skipped", now_iso(), None))
                    c.commit()
                continue
            lt = _email_local(c, u)
            cand = _email_candidate(c, u, lt)
            if cand:
                _email_deliver(c, u, cand[0], cand[1], cand[2], cand[3], cand[4])
        except Exception as e:
            print("[email] pass error for", u["id"], e, flush=True)


def email_tick():
    with _dblock:
        c = db()
        try:
            _email_pass(c)
        except Exception as e:
            print("email_tick error:", e, flush=True)
        finally:
            c.close()


# ---- SMS lifecycle engine (opt-in only; mirrors the email engine) --------------
# GATED by SMS_MODE so it never texts real users until explicitly enabled:
#   SMS_MODE=off     -> idle
#   SMS_MODE=dryrun  -> decides + logs who WOULD get what; sends nothing (default)
#   SMS_MODE=live    -> actually sends via Twilio
SMS_MODE = os.environ.get("SMS_MODE", "dryrun").strip().lower()
SMS_SEND_HOUR_LOCAL = 19   # local hour the evening streak nudge goes out

def _sms_has(c, uid, dk):
    return bool(c.execute("SELECT 1 FROM sms_log WHERE user_id=? AND dedupe_key=? LIMIT 1",
                          (uid, dk)).fetchone())

def _sms_recent(c, uid, days):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return bool(c.execute(
        "SELECT 1 FROM sms_log WHERE user_id=? AND created>=? AND status IN ('sent','dryrun') LIMIT 1",
        (uid, since)).fetchone())

def _sms_candidate(c, u, lt):
    """Pick the single best SMS for a user now, or None. Returns (kind, body, dedupe_key).
    Deliberately sparse + high-value so texts never feel like spam."""
    h = lt.hour
    name = (u["name"] or "").split()[0] if u["name"] else ""
    hey = (name + ", ") if name else ""
    streak = u["streak"] or 0
    tier = _notif_tier(u)
    today = lt.strftime("%Y-%m-%d")
    yesterday = (lt - timedelta(days=1)).strftime('%Y-%m-%d')
    last = u["last_day"]
    # streak at risk: evening, a live streak, hasn't sat today — the one text people thank you for
    if h == SMS_SEND_HOUR_LOCAL and streak >= 1 and last == yesterday:
        dk = "streak_risk:" + today
        if not _sms_has(c, u["id"], dk):
            body = ("%syour %d-day streak on Lumen is still lit — one short sit before midnight keeps it going. 🔥\nReply STOP to opt out."
                    % (hey, streak))
            return ("streak_risk", body, dk)
    # win-back: dormant/churned, at most once a week, evening
    if h == SMS_SEND_HOUR_LOCAL and tier in ("dormant", "churned") and not _sms_recent(c, u["id"], 6):
        dk = "winback:" + week_str()
        if not _sms_has(c, u["id"], dk):
            body = ("%syour light has been waiting on Lumen. Two quiet minutes is a real beginning — come sit with us again.\nReply STOP to opt out."
                    % hey)
            return ("winback", body, dk)
    return None

def _sms_deliver(c, u, kind, body, dedupe_key):
    status, sent = "dryrun", None
    if SMS_MODE == "live":
        ok = send_sms(u["phone"], body)
        status = "sent" if ok else "error"
        sent = now_iso() if ok else None
    c.execute("INSERT INTO sms_log(user_id,kind,dedupe_key,status,created,sent) VALUES(?,?,?,?,?,?)",
              (u["id"], kind, dedupe_key, status, now_iso(), sent))
    c.commit()

def _sms_pass(c):
    if SMS_MODE == "off":
        return
    users = c.execute("SELECT * FROM users WHERE is_bot=0 AND phone IS NOT NULL "
                      "AND COALESCE(sms_consent,0)=1 AND COALESCE(sms_optout,0)=0").fetchall()
    for u in users:
        try:
            lt = _email_local(c, u)
            cand = _sms_candidate(c, u, lt)
            if cand:
                _sms_deliver(c, u, cand[0], cand[1], cand[2])
        except Exception as e:
            print("[sms] pass error for", u["id"], e, flush=True)

def sms_tick():
    with _dblock:
        c = db()
        try:
            _sms_pass(c)
        except Exception as e:
            print("sms_tick error:", e, flush=True)
        finally:
            c.close()


def email_admin_stats(c):
    def one(q, a=()):
        r = c.execute(q, a).fetchone(); return (r[0] if r else 0) or 0
    by_kind = [dict(r) for r in c.execute(
        "SELECT kind, status, COUNT(*) n FROM email_log GROUP BY kind, status ORDER BY kind")]
    recent = [dict(r) for r in c.execute(
        "SELECT user_id,kind,status,created FROM email_log ORDER BY id DESC LIMIT 30")]
    return {"mode": EMAIL_MODE,
            "total": one("SELECT COUNT(*) FROM email_log"),
            "sent": one("SELECT COUNT(*) FROM email_log WHERE status='sent'"),
            "dryrun": one("SELECT COUNT(*) FROM email_log WHERE status='dryrun'"),
            "optouts": one("SELECT COUNT(*) FROM users WHERE COALESCE(email_optout,0)=1"),
            "premium_interest": one("SELECT COUNT(*) FROM premium_waitlist"),
            "by_kind": by_kind, "recent": recent}


def email_loop():
    time.sleep(35)  # settle after boot, after notif_loop
    while True:
        email_tick()
        try:
            sms_tick()
        except Exception as e:
            print("sms_tick error:", e, flush=True)
        time.sleep(1800)  # every 30 minutes


def community_loop():
    """Keep the community map/leagues alive: re-seed bot activity whenever the
    current ISO week has no bot sessions (fresh boot or week rollover)."""
    while True:
        try:
            with _dblock:
                c = db()
                try:
                    wk = week_str()
                    has = c.execute("SELECT 1 FROM sessions s JOIN users u ON u.id=s.user_id "
                                    "WHERE u.is_bot=1 AND s.week=? LIMIT 1", (wk,)).fetchone()
                    if not has:
                        seed_live_week(c)
                finally:
                    c.close()
        except Exception as e:
            print("community_loop error:", e, flush=True)
        time.sleep(6 * 3600)


def main():
    init_db()
    seed_world()
    seed_subtasks()
    threading.Thread(target=notif_loop, daemon=True).start()
    threading.Thread(target=email_loop, daemon=True).start()
    threading.Thread(target=community_loop, daemon=True).start()
    httpd = ThreadingHTTPServer((HOST, PORT), H)
    print(f"Lumen on http://{HOST}:{PORT}  (BASE={BASE or '/'})")
    httpd.serve_forever()


if __name__ == "__main__":
    main()

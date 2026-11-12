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
import json, os, re, threading, time, html, uuid, hashlib, urllib.request
from urllib.parse import urlparse
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", os.environ.get("MARQUEE_PORT", "18852")))
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
FIRECRAWL_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
REFRESH_H = float(os.environ.get("MARQUEE_REFRESH_H", "12"))
CACHE_H = float(os.environ.get("MARQUEE_CACHE_H", "12"))        # scraped-content cache TTL
CRAWL_EVERY_H = float(os.environ.get("MARQUEE_CRAWL_EVERY_H", "6"))  # background crawler cadence
HOME = os.environ.get("MARQUEE_HOME", "Bushwick, Brooklyn")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("MARQUEE_DATA", os.path.join(HERE, "data"))
STORE = os.path.join(DATA, "events.json")
CACHE_DIR = os.path.join(DATA, "cache")

CATEGORIES = ["Music", "Nightlife", "Arts", "Theater", "Comedy", "Sports",
              "Food", "Festival", "Family", "Film", "Wellness"]
BOROUGHS = ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"]
STORE_PERSONAL = os.path.join(os.environ.get("MARQUEE_DATA", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data")), "personal.json")

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


# ------------------------------------------------- personal (user-added) events
# weekdays use JS getDay(): Sun=0, Mon=1 ... Sat=6.
WD_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def load_personal():
    try:
        with open(STORE_PERSONAL) as f:
            return json.load(f)
    except Exception:
        return []


def save_personal(recs):
    os.makedirs(DATA, exist_ok=True)
    tmp = STORE_PERSONAL + ".tmp"
    with open(tmp, "w") as f:
        json.dump(recs, f, indent=1)
    os.replace(tmp, STORE_PERSONAL)


def seed_personal():
    """Seed/upgrade: Matthew's Baby Cobra Yoga in Bushwick (Firecrawl-scannable)."""
    recs = load_personal()
    changed = False
    existing = next((r for r in recs if r.get("seed") == "babycobra"), None)
    if existing:
        # upgrade: Baby Cobra Bushwick runs DAILY evening classes (ClassPass is the
        # real daily schedule; Tickettailor only lists special workshops). Matthew
        # goes ~7pm, so show the daily 7pm class + layer specials on top.
        if existing.get("seed_v") != 6:
            # Show the REAL scraped studio schedule directly (every class the
            # crawl finds), not a synthetic standing class. seed_v 5 added a
            # placeholder Thu/Sat 7pm recurrence — drop it.
            existing["recurring"] = False
            existing["show_all"] = True
            existing.pop("weekdays", None)
            existing.pop("time", None)
            existing["url"] = "https://babycobrayoga.com/bushwick/"
            existing["scan_url"] = "https://babycobrayoga.com/bushwick/"
            existing["location_match"] = "Bushwick"
            existing["blurb"] = "Donation-based Bushwick loft studio — the full daily schedule, scraped live from the studio."
            existing["seed_v"] = 6
            changed = True
    else:
        changed = True
        recs.append({
            "id": uuid.uuid4().hex[:12], "seed": "babycobra", "seed_v": 6,
            "title": "Baby Cobra Yoga", "recurring": False, "show_all": True,
            "venue": "Baby Cobra Yoga, 47 Thames St #206",
            "neighborhood": "Bushwick", "borough": "Brooklyn", "near_home": True,
            "category": "Wellness", "price": "Donation-based",
            "url": "https://babycobrayoga.com/bushwick/",
            "scan_url": "https://babycobrayoga.com/bushwick/",
            "location_match": "Bushwick",
            "blurb": "Donation-based Bushwick loft studio — the full daily schedule, scraped live from the studio.",
        })
    # Williamsburg founders run — weekly Wednesday 7:30am (Luma, Firecrawl-scannable)
    if not any(r.get("seed") == "wburgrun" for r in recs):
        changed = True
        recs.append({
            "id": uuid.uuid4().hex[:12], "seed": "wburgrun",
            "title": "Williamsburg Run: Founders, Creatives & Coffee",
            "recurring": True, "weekdays": [3], "time": "7:30 AM",
            "venue": "Padel Haus Williamsburg", "neighborhood": "Williamsburg",
            "borough": "Brooklyn", "near_home": True,
            "category": "Wellness", "price": "Free · approval required",
            "url": "https://luma.com/hhndqkur",
            "scan_url": "https://luma.com/hhndqkur",
            "blurb": "Weekly Wed 5K with founders & creatives from Padel Haus; coffee & smoothies after.",
        })
    if changed:
        save_personal(recs)


def _start_time(t):
    """Normalize a time/time-range to its start token for de-duping, e.g.
    '7:30 AM - 9:00 AM' and '7:30 AM' -> '7:30AM'."""
    m = re.match(r"\s*(\d{1,2}(?::\d{2})?\s*[AaPp][Mm])", t or "")
    return (m.group(1).upper().replace(" ", "") if m else (t or "").strip().upper())


def _mins(t):
    """Minutes-since-midnight for chronological sorting of a time string
    (handles AM/PM so 8:00 AM sorts before 5:30 PM). Unknown -> end of day."""
    m = re.match(r"\s*(\d{1,2})(?::(\d{2}))?\s*([AaPp])[Mm]", t or "")
    if not m:
        return 9999
    h = int(m.group(1)) % 12
    if m.group(3).lower() == "p":
        h += 12
    return h * 60 + int(m.group(2) or 0)


def _instance(r, d):
    return {
        "id": "p_" + r["id"], "pid": r["id"], "mine": True,
        "title": r.get("title", ""), "date": d, "time": r.get("time", ""),
        "venue": r.get("venue", ""), "neighborhood": r.get("neighborhood", ""),
        "borough": _norm_boro(r.get("borough")), "near_home": bool(r.get("near_home")),
        "category": _norm_cat(r.get("category")), "price": r.get("price", ""),
        "url": r.get("url", ""), "blurb": r.get("blurb", ""),
        "recurring": bool(r.get("recurring")),
    }


def _session_from(r, s):
    """Build a dated instance from a scraped session record."""
    inst = _instance(r, s.get("date", ""))
    if s.get("time"):
        inst["time"] = s["time"]
    if s.get("url"):
        inst["url"] = s["url"]
    if s.get("title") and s["title"].lower() not in r["title"].lower():
        inst["title"] = r["title"] + " · " + s["title"]
    inst["scanned"] = True
    return inst


def expand_personal(days=32):
    """Expand personal events into the events the user actually PLANS to attend:
    their standing weekly schedule + any specific class they selected. The full
    scraped studio schedule (r['sessions']) is NOT dumped in here — it's browsable
    via /api/personal/sessions and added one class at a time."""
    out, today = [], date.today()
    tj, horizon = today.isoformat(), (today + timedelta(days=days)).isoformat()
    for r in load_personal():
        if not r.get("id"):
            continue
        excl = set(r.get("excluded") or [])
        selected = set(r.get("selected") or [])
        sess_by_key = {}
        for s in (r.get("sessions") or []):
            sess_by_key[(s.get("date", ""), _start_time(s.get("time", "")))] = s

        def _skip(inst):
            return (inst["date"] + "|" + _start_time(inst["time"])) in excl

        seen = set()
        # 1) your standing weekly schedule (what you set when you added it)
        if r.get("recurring"):
            wd = set(r.get("weekdays") or [])
            for i in range(days):
                d = today + timedelta(days=i)
                if (d.weekday() + 1) % 7 in wd:
                    inst = _instance(r, d.isoformat())
                    if _skip(inst):
                        continue
                    # enrich with the real class name/link if the scan has it
                    m = sess_by_key.get((inst["date"], _start_time(inst["time"])))
                    if m:
                        inst = _session_from(r, m)
                        if _skip(inst):
                            continue
                    out.append(inst); seen.add((inst["date"], _start_time(inst["time"])))
        # 1b) a regular that surfaces its full REAL scraped schedule directly —
        #     every class from the crawl (no synthetic standing class).
        if r.get("show_all"):
            for s in (r.get("sessions") or []):
                sd = s.get("date", "")
                if not (tj <= sd <= horizon):
                    continue
                inst = _session_from(r, s)
                k = (inst["date"], _start_time(inst["time"]))
                if _skip(inst) or k in seen:
                    continue
                # confirmed (in your calendar) only if you've added this class
                inst["mine"] = (inst["date"] + "|" + _start_time(inst["time"])) in selected
                out.append(inst); seen.add(k)
        # 2) specific classes you picked from the full schedule
        for key in selected:
            dt, _ = (key.split("|", 1) + [""])[:2]
            s = sess_by_key.get((dt, key.split("|", 1)[1] if "|" in key else ""))
            if not s or not (tj <= s.get("date", "") <= horizon):
                continue
            inst = _session_from(r, s)
            if _skip(inst) or (inst["date"], _start_time(inst["time"])) in seen:
                continue
            out.append(inst); seen.add((inst["date"], _start_time(inst["time"])))
        # 3) one-off saved event
        if not r.get("recurring") and not r.get("sessions") and r.get("date") and r["date"] >= tj:
            inst = _instance(r, r["date"])
            if not _skip(inst):
                out.append(inst)
    return out


# -------------------------------------------------- subscribable iCalendar feed
def _ics_esc(s):
    """Escape a TEXT value per RFC 5545 (backslash, comma, semicolon, newline)."""
    return (str(s or "")
            .replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;")
            .replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n"))


def _ics_fold(line):
    """Fold a content line to <=75 octets per RFC 5545 (continuation = CRLF+space)."""
    if len(line.encode("utf-8")) <= 75:
        return line
    out, cur = [], b""
    for ch in line:
        e = ch.encode("utf-8")
        if len(cur) + len(e) > 75:
            out.append(cur.decode("utf-8")); cur = b" " + e
        else:
            cur += e
    out.append(cur.decode("utf-8"))
    return "\r\n".join(out)


def _ics_time(t):
    """Parse a start time ('7:00 PM', '7:30 AM - 9:00 AM') -> (hour, minute) or None."""
    m = re.match(r"\s*(\d{1,2})(?::(\d{2}))?\s*([AaPp])[Mm]", t or "")
    if not m:
        return None
    h = int(m.group(1)) % 12
    if m.group(3).lower() == "p":
        h += 12
    return (h, int(m.group(2) or 0))


def _ics_event(e):
    """Render one event dict to a VEVENT (list of unfolded content lines)."""
    d = (e.get("date") or "")
    p = d.split("-")
    if len(p) != 3:
        return []
    y, mo, da = p
    base = (e.get("id") or hashlib.sha1((e.get("title", "") + d).encode()).hexdigest()[:10])
    L = ["BEGIN:VEVENT",
         "UID:" + base + "-" + d + "@marquee.bedrock.casa",
         "DTSTAMP:" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())]
    hm = _ics_time(e.get("time"))
    if not hm:
        L.append("DTSTART;VALUE=DATE:" + y + mo + da)
    else:
        h, mi = hm
        L.append("DTSTART:%s%s%sT%02d%02d00" % (y, mo, da, h, mi))
        L.append("DTEND:%s%s%sT%02d%02d00" % (y, mo, da, (h + 2) % 24, mi))
    L.append("SUMMARY:" + _ics_esc(e.get("title")))
    loc = ", ".join([x for x in [e.get("venue"), e.get("neighborhood")] if x])
    if loc:
        L.append("LOCATION:" + _ics_esc(loc))
    desc = "\n".join([x for x in [e.get("blurb"), e.get("url")] if x])
    if desc:
        L.append("DESCRIPTION:" + _ics_esc(desc))
    if e.get("url"):
        L.append("URL:" + _ics_esc(e.get("url")))
    L.append("END:VEVENT")
    return L


def build_ics():
    """Build a subscribable VCALENDAR from the user's regular/saved events so
    Google and Apple Calendar can auto-sync Marquee."""
    L = ["BEGIN:VCALENDAR", "VERSION:2.0",
         "PRODID:-//Marquee//NYC Events//EN", "CALSCALE:GREGORIAN",
         "METHOD:PUBLISH", "X-WR-CALNAME:Marquee",
         "X-WR-CALDESC:Your NYC events from Marquee",
         "X-WR-TIMEZONE:America/New_York",
         "X-PUBLISHED-TTL:PT6H", "REFRESH-INTERVAL;VALUE=DURATION:PT6H"]
    for e in expand_personal():
        L += _ics_event(e)
    L.append("END:VCALENDAR")
    return "\r\n".join(_ics_fold(x) for x in L) + "\r\n"


# -------------------------------------------------- Firecrawl scan of regulars
# ---- content cache: scraped pages are cached on disk and served first ----
def _cache_path(url):
    return os.path.join(CACHE_DIR, hashlib.sha1(url.encode()).hexdigest() + ".json")


def cache_get(url, max_age_h=CACHE_H):
    try:
        with open(_cache_path(url)) as f:
            c = json.load(f)
        if (time.time() * 1000 - (c.get("ts") or 0)) <= max_age_h * 3600 * 1000:
            return c.get("markdown") or ""
    except Exception:
        pass
    return None


def cache_put(url, md):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = _cache_path(url) + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"url": url, "ts": int(time.time() * 1000), "markdown": md}, f)
        os.replace(tmp, _cache_path(url))
    except Exception as e:
        print("[marquee] cache write failed:", e, flush=True)


_fc_lock = threading.Lock()
_fc_last = [0.0]
FC_MIN_INTERVAL = float(os.environ.get("MARQUEE_FC_MIN_S", "6"))


def _fc_throttle():
    """Serialize Firecrawl calls with a min interval so parallel source scrapes
    don't trip its rate limit (429). Only real (cache-miss) calls hit this."""
    with _fc_lock:
        w = FC_MIN_INTERVAL - (time.time() - _fc_last[0])
        if w > 0:
            time.sleep(w)
        _fc_last[0] = time.time()


def fc_scrape(url, max_age_h=CACHE_H, force=False, wait=0):
    """Scrape a page to markdown, CACHE-FIRST: serve fresh cached content when
    available, otherwise crawl via Firecrawl and cache it. Returns '' on failure
    (but will fall back to stale cache if the live crawl fails). `wait` (ms) lets
    JS-rendered pages (e.g. the Baby Cobra schedule widget) hydrate before scrape."""
    if not url:
        return ""
    if not force:
        hit = cache_get(url, max_age_h)
        if hit is not None:
            return hit
    if not FIRECRAWL_KEY:
        return cache_get(url, 1e9) or ""   # no key -> any cached copy
    try:
        opts = {"url": url, "formats": ["markdown"],
                "onlyMainContent": not wait}   # keep widget markup for JS pages
        if wait:
            opts["waitFor"] = int(wait)
        body = json.dumps(opts).encode()
        _fc_throttle()
        req = urllib.request.Request("https://api.firecrawl.dev/v2/scrape", data=body,
                                     headers={"Authorization": "Bearer " + FIRECRAWL_KEY,
                                              "Content-Type": "application/json"}, method="POST")
        j = json.loads(urllib.request.urlopen(req, timeout=60).read())
        md = ((j.get("data") or {}).get("markdown") or "")[:18000]
        if md:
            cache_put(url, md)
        return md
    except Exception as e:
        print("[marquee] firecrawl failed:", e, flush=True)
        return cache_get(url, 1e9) or ""   # fall back to any stale cache


def parse_babycobra(md, book_url):
    """Deterministically parse the Baby Cobra Bushwick schedule widget. Each
    class renders as: 'Ddd MM/DD/YYYY \\n H:MM am/pm \\n Bushwick \\n ## Name \\n
    (dur)'. The widget renders in UTC (headless-browser TZ), so convert to
    America/New_York (EST = UTC-5 on/after the first Sunday of Nov). Returns a
    list of {date,time,title,url}."""
    pat = re.compile(
        r"([A-Z][a-z][a-z])\s+(\d{2})/(\d{2})/(\d{4})\s*\n+\s*"
        r"(\d{1,2}:\d{2}\s*[ap]m)\s*\n+\s*"
        r"([A-Za-z ]+?)\s*\n+\s*"
        r"##\s*(.+?)\s*\n+\s*\(([^)]*)\)", re.MULTILINE)
    today = date.today().isoformat()
    out = []
    for m in pat.finditer(md):
        _, mm, dd, yyyy, tstr, _loc, name, _dur = m.groups()
        try:
            utc = datetime.strptime(
                f"{yyyy}-{mm}-{dd} {tstr.upper().replace(' ', '')}",
                "%Y-%m-%d %I:%M%p")
        except ValueError:
            continue
        est = utc - timedelta(hours=5)   # UTC -> NY (EST)
        d = est.strftime("%Y-%m-%d")
        if d < today:
            continue
        h = est.hour % 12 or 12
        t = f"{h}:{est.minute:02d} {'AM' if est.hour < 12 else 'PM'}"
        out.append({"date": d, "time": t,
                    "title": name.strip().strip("🎟").strip()[:100],
                    "url": book_url})
    out.sort(key=lambda s: (s["date"], datetime.strptime(s["time"], "%I:%M %p")))
    return out


def scan_regular(rec):
    """Firecrawl-scrape a regular's booking page, then have Gemini extract the
    REAL upcoming sessions (optionally filtered to a location). Returns a list of
    {date,time,title,url} or [] on failure."""
    url = rec.get("scan_url") or rec.get("url")
    # Baby Cobra's Bushwick schedule is a JS widget with a clean, structured
    # layout — parse it deterministically (no LLM guesswork, gets EVERY class).
    if rec.get("seed") == "babycobra" or "babycobrayoga.com" in (url or ""):
        md = fc_scrape(url, wait=6000)
        return parse_babycobra(md, rec.get("url") or url) if md else []
    md = fc_scrape(url)
    if not md or not GEMINI_KEY:
        return []
    loc = rec.get("location_match") or ""
    today = date.today().isoformat()
    prompt = (
        "From this scraped booking page, extract EVERY upcoming session of \""
        + rec.get("title", "this event") + f"\" on or after {today}. Use the exact dates, "
        "times, and booking links shown on the page — do not invent anything. For each, "
        "include the venue/location text shown. Reply with ONLY a JSON array, each item: "
        "{\"date\":\"YYYY-MM-DD\",\"time\",\"title\",\"location\",\"url\"}. url is that "
        "session's own booking link. No prose, no markdown fences.\n\nPAGE:\n" + md)
    try:
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                           "generationConfig": {"temperature": 0, "maxOutputTokens": 4000,
                                                "thinkingConfig": {"thinkingBudget": 0}}}).encode()
        u = (f"https://generativelanguage.googleapis.com/v1beta/models/"
             f"{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}")
        req = urllib.request.Request(u, data=body, headers={"Content-Type": "application/json"}, method="POST")
        j = json.loads(urllib.request.urlopen(req, timeout=60).read())
        txt = "".join(p.get("text", "") for p in
                      ((j["candidates"][0].get("content") or {}).get("parts") or []))
        a, b = txt.find("["), txt.rfind("]")
        arr = json.loads(txt[a:b + 1]) if a >= 0 and b > a else []
    except Exception as e:
        print("[marquee] scan extract failed:", e, flush=True)
        return []
    out = []
    for s in arr:
        if not (isinstance(s, dict) and re.match(r"^\d{4}-\d{2}-\d{2}$", str(s.get("date", "")))):
            continue
        if s["date"] < today:
            continue
        sloc = str(s.get("location", ""))
        if loc and sloc and loc.lower() not in sloc.lower():
            continue   # drop other locations when we have a usable location string
        out.append({"date": s["date"], "time": str(s.get("time", ""))[:40],
                    "title": str(s.get("title", ""))[:100], "url": str(s.get("url", ""))[:400] or url})
    out.sort(key=lambda s: (s["date"], s["time"]))
    return out


def scan_stale_regulars(max_age_h=24):
    """Background: refresh real sessions for any scannable regular not scanned
    within max_age_h. Keeps the calendar's real times current."""
    now = time.time() * 1000
    for r in load_personal():
        if r.get("scan_url") and (now - (r.get("scanned_at") or 0) > max_age_h * 3600 * 1000):
            try:
                scan_regular_by_id(r["id"])
            except Exception as e:
                print("[marquee] auto-scan failed:", e, flush=True)


def crawler_loop():
    """The crawl agent: on a cadence, refresh the content cache for every
    regular's source page, then re-extract sessions. The app always reads the
    cache first, so pages are served instantly and crawled in the background."""
    while True:
        try:
            for r in load_personal():
                if r.get("scan_url"):
                    fc_scrape(r["scan_url"], force=True)   # refresh cached content
            scan_stale_regulars(max_age_h=CRAWL_EVERY_H)
        except Exception as e:
            print("[marquee] crawler pass failed:", e, flush=True)
        time.sleep(max(1800, CRAWL_EVERY_H * 3600))


def scan_regular_by_id(pid):
    recs = load_personal()
    for r in recs:
        if r.get("id") == pid and (r.get("scan_url") or r.get("url")):
            sess = scan_regular(r)
            if sess:
                r["sessions"] = sess
                r["scanned_at"] = int(time.time() * 1000)
                save_personal(recs)
            return sess
    return []


# --------------------------------------------------------------- gemini fetch
def _norm_cat(c):
    c = (c or "").strip().title()
    alias = {"Concert": "Music", "Concerts": "Music", "Show": "Theater",
             "Shows": "Theater", "Club": "Nightlife", "Dj": "Nightlife",
             "Exhibition": "Arts", "Art": "Arts", "Museum": "Arts",
             "Dance": "Nightlife", "Dining": "Food", "Kids": "Family"}
    c = alias.get(c, c)
    return c if c in CATEGORIES else "Arts"


def _norm_boro(b):
    b = (b or "").strip().title()
    alias = {"Bk": "Brooklyn", "Mn": "Manhattan", "Nyc": "Manhattan",
             "New York": "Manhattan", "Si": "Staten Island"}
    b = alias.get(b, b)
    return b if b in BOROUGHS else ""


def fetch_events():
    """Ask Gemini (grounded in Google Search) for real upcoming NYC events."""
    if not GEMINI_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")
    prompt = (
        f"I live in {HOME}. Use Google Search to find 8 REAL, specific, currently-listed "
        "events happening in New York City in the next ~24 days. Include a strong share of "
        f"Brooklyn events near {HOME} (Bushwick, East Williamsburg, Williamsburg, Ridgewood, "
        "Bed-Stuy) alongside the best citywide highlights, across music, nightlife, arts, "
        "theater, comedy, sports, food, festivals, family, film.\n\n"
        "Rules: each event is a SINGLE real event (never merge two artists/listings). "
        "\"url\" should be that event's own listing/ticket page (a deep link with a path, "
        "not a homepage or search page). Use the exact title, venue and date shown. Don't "
        "invent events.\n\n"
        "Reply with ONLY a JSON array, no prose, no markdown fences. Each item: "
        "{\"title\",\"date\":\"YYYY-MM-DD\",\"time\",\"venue\",\"neighborhood\",\"borough\","
        "\"near_home\",\"category\",\"price\",\"url\",\"blurb\"}. category is one of: "
        + ", ".join(CATEGORIES) + ". borough is one of: " + ", ".join(BOROUGHS)
        + ". near_home is true ONLY if the venue is within ~2 miles of "
        f"{HOME} (Bushwick/East Williamsburg/Williamsburg/Ridgewood/Bed-Stuy). "
        "blurb <= 18 words, vivid and specific."
    )
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4000}}
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}")
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    # grounded search is slow (many live Google lookups) — a single generous
    # timeout; on failure the refresh just proceeds with the platform sources and
    # the next cycle retries. Runs in the background refresh, so users aren't blocked.
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
            "borough": _norm_boro(e.get("borough")),
            "near_home": bool(e.get("near_home")),
            "category": _norm_cat(e.get("category")),
            "price": (e.get("price") or "").strip()[:60],
            "url": (e.get("url") or "").strip()[:400],
            "blurb": (e.get("blurb") or "").strip()[:220],
            "source": "Search",
        })
    return _clean_events(out)


def _specific_url(u):
    try:
        p = urlparse(u or "")
        return p.scheme in ("http", "https") and bool(p.netloc) and len(p.path.strip("/")) > 1
    except Exception:
        return False


def _clean_events(out):
    """today-forward + only events with a specific deep-link listing URL; sorted."""
    today = time.strftime("%Y-%m-%d")
    out = [e for e in out if e.get("date", "") >= today and _specific_url(e.get("url"))]
    out.sort(key=lambda e: (e["date"], _mins(e.get("time", ""))))
    return out


# -------------------------------------------------------- event-source platforms
# Marquee pulls from "our own internet search" (Gemini grounding, source="Search")
# PLUS these real listing platforms (Firecrawl-scraped, cache-first, Gemini-
# extracted). Luma city pages are JS-only so Luma is used for specific events /
# regulars, not a listing source here.
SOURCES = [
    {"key": "ra", "name": "Resident Advisor", "url": "https://ra.co/events/us/brooklyn", "hint": "Nightlife", "on": False, "wait": 8000},
    {"key": "dice", "name": "DICE", "url": "https://dice.fm/browse/new-york", "hint": "Music", "on": True},
    {"key": "shotgun", "name": "Shotgun", "url": "https://shotgun.live/en/cities/new-york", "hint": "Nightlife", "on": True},
    {"key": "eventbrite", "name": "Eventbrite", "url": "https://www.eventbrite.com/d/ny--brooklyn/events/", "hint": "Festival", "on": True},
    {"key": "bandsintown", "name": "Bandsintown", "url": "https://www.bandsintown.com/c/new-york-ny", "hint": "Music", "on": True},
    {"key": "songkick", "name": "Songkick", "url": "https://www.songkick.com/metro-areas/7644-us-new-york", "hint": "Music", "on": True},
    {"key": "fever", "name": "Fever", "url": "https://feverup.com/en/new-york", "hint": "Arts", "on": True},
    {"key": "posh", "name": "Posh", "url": "https://posh.vip/explore/new-york", "hint": "Nightlife", "on": True},
]


_SRC_COLOR = {
    "Nightlife": ("#a855f7", "#7c3aed"), "Music": ("#ff5c8a", "#be185d"),
    "Festival": ("#ec4899", "#a855f7"), "Arts": ("#38bdf8", "#2563eb"),
    "Wellness": ("#34d399", "#059669"), "Tickets": ("#f59e0b", "#d97706"),
    "Community": ("#2dd4bf", "#0ea5e9"), "Live search": ("#fbbf24", "#f59e0b"),
}


def cache_ts(url):
    """Last-scraped timestamp (ms) for a URL's cached page, or 0."""
    try:
        with open(_cache_path(url)) as f:
            return int((json.load(f).get("ts")) or 0)
    except Exception:
        return 0


# Partner platforms used for specific events / regulars (matched to a regular by
# the domain in its scan_url). key -> (name, url, category, note, domain)
_PARTNERS = [
    ("luma", "Luma", "https://luma.com/", "Community", "Community & creator event pages", "luma.com"),
    ("classpass", "ClassPass", "https://classpass.com/", "Wellness", "Studio class schedules", "classpass.com"),
    ("tickettailor", "Tickettailor", "https://www.tickettailor.com/", "Tickets", "Independent event tickets", "tickettailor.com"),
    ("axs", "AXS", "https://www.axs.com/", "Tickets", "Venue & concert tickets", "axs.com"),
]


def public_sources():
    """The connected platforms Marquee's agents pull events from — with how many
    listings each has ingested and when it last updated, so the user can see (and
    drill into) exactly where the calendar comes from."""
    st = load_store()
    evs = st.get("events") or []
    fetched_at = st.get("fetched_at", 0)
    by_src = {}
    for e in evs:
        by_src.setdefault(e.get("source") or "", []).append(e)
    regs = load_personal()
    today = date.today().isoformat()

    out = [{"key": "search", "name": "Our internet search", "url": None, "category": "Live search",
            "active": bool(GEMINI_KEY),
            "note": "Gemini + Google Search grounding surfaces fresh NYC events",
            "count": len(by_src.get("Search", [])), "last_update": fetched_at}]
    for s in SOURCES:
        n = len(by_src.get(s["name"], []))
        out.append({"key": s["key"], "name": s["name"], "url": s["url"], "category": s["hint"],
                    "active": bool(s.get("on")), "note": "Listing platform, scanned via Firecrawl",
                    "count": n, "last_update": cache_ts(s["url"]) or (fetched_at if n else 0)})
    for key, name, url, cat, note, dom in _PARTNERS:
        matched = [r for r in regs if dom in (r.get("scan_url") or r.get("url") or "")]
        cnt = sum(len([x for x in (r.get("sessions") or []) if x.get("date", "") >= today]) for r in matched)
        lu = max([r.get("scanned_at") or 0 for r in matched] or [0])
        out.append({"key": key, "name": name, "url": url, "category": cat, "active": True,
                    "note": note, "count": cnt, "last_update": lu})
    for o in out:
        c = _SRC_COLOR.get(o["category"], ("#ff5c8a", "#a855f7"))
        o["c0"], o["c1"] = c
    return out


def source_events(key):
    """The actual listings a given source ingested (for the Sources drill-down)."""
    st = load_store()
    evs = st.get("events") or []
    name = "Search" if key == "search" else next((s["name"] for s in SOURCES if s["key"] == key), None)
    if name:
        out = [{"title": e.get("title"), "date": e.get("date"), "time": e.get("time"),
                "venue": e.get("venue"), "neighborhood": e.get("neighborhood"),
                "category": e.get("category"), "url": e.get("url")}
               for e in evs if (e.get("source") or "") == name]
    else:
        dom = next((d for k, n, u, c, nt, d in _PARTNERS if k == key), None)
        if not dom:
            return []
        today = date.today().isoformat()
        out = []
        for r in load_personal():
            if dom in (r.get("scan_url") or r.get("url") or ""):
                for s in (r.get("sessions") or []):
                    if s.get("date", "") >= today:
                        t = r.get("title", "")
                        if s.get("title"):
                            t = t + " · " + s["title"]
                        out.append({"title": t, "date": s.get("date"), "time": s.get("time"),
                                    "venue": r.get("venue"), "neighborhood": r.get("neighborhood"),
                                    "category": r.get("category"), "url": s.get("url") or r.get("url")})
    out.sort(key=lambda e: (e.get("date", ""), _mins(e.get("time", ""))))
    return out[:250]


def fetch_from_source(src, limit=6):
    """Firecrawl-scrape a platform's NYC listing (cache-first) and have Gemini
    extract its real upcoming events. Returns a list tagged with the source."""
    md = fc_scrape(src["url"], wait=src.get("wait", 0))
    if not md or not GEMINI_KEY:
        return []
    today = date.today().isoformat()
    prompt = (
        f"This is a scraped events-listing page from {src['name']} for New York City. "
        f"Extract up to {limit} REAL upcoming events on or after {today} (next ~24 days), "
        "preferring Brooklyn / near Bushwick where possible. Dates may appear relative "
        "(e.g. 'Sat, 7 Nov', 'Tonight', 'Tomorrow') — resolve each to YYYY-MM-DD using "
        f"today's date {today} and the current year. Use the exact title, date, time, venue, "
        "and that event's OWN specific listing URL shown on the page — never invent or "
        "merge. Reply ONLY a JSON array, each item: {\"title\",\"date\":"
        "\"YYYY-MM-DD\",\"time\",\"venue\",\"neighborhood\",\"borough\",\"near_home\","
        "\"category\",\"price\",\"url\",\"blurb\"}. category one of: " + ", ".join(CATEGORIES)
        + ". borough one of: " + ", ".join(BOROUGHS) + ". blurb <=16 words.\n\nPAGE:\n" + md[:16000])
    try:
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                           "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4000,
                                                "thinkingConfig": {"thinkingBudget": 0}}}).encode()
        u = (f"https://generativelanguage.googleapis.com/v1beta/models/"
             f"{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}")
        req = urllib.request.Request(u, data=body, headers={"Content-Type": "application/json"}, method="POST")
        j = json.loads(urllib.request.urlopen(req, timeout=60).read())
        txt = "".join(p.get("text", "") for p in
                      ((j["candidates"][0].get("content") or {}).get("parts") or []))
        a, b = txt.find("["), txt.rfind("]")
        arr = json.loads(txt[a:b + 1]) if a >= 0 and b > a else []
    except Exception as e:
        print(f"[marquee] source {src['key']} failed:", e, flush=True)
        return []
    out = []
    for e in arr:
        if not isinstance(e, dict):
            continue
        d = str(e.get("date", ""))
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
            continue
        t = (e.get("title") or "").strip()
        if not t:
            continue
        out.append({
            "title": t[:140], "date": d, "time": str(e.get("time", "")).strip()[:40],
            "venue": str(e.get("venue", "")).strip()[:120],
            "neighborhood": str(e.get("neighborhood", "")).strip()[:80],
            "borough": _norm_boro(e.get("borough")), "near_home": bool(e.get("near_home")),
            "category": _norm_cat(e.get("category")), "price": str(e.get("price", "")).strip()[:60],
            "url": str(e.get("url", "")).strip()[:400], "blurb": str(e.get("blurb", "")).strip()[:220],
            "source": src["name"],
        })
    return _clean_events(out)


def build_all_events():
    """Combine our internet search (Gemini grounding) with every enabled source
    platform, in parallel. Merge, de-dupe (title+date), sort."""
    results, lock = [], threading.Lock()

    def run(fn, tag):
        try:
            evs = fn()
            with lock:
                results.append(evs or [])
        except Exception as e:
            print(f"[marquee] {tag} errored:", e, flush=True)

    # 1) platform sources in parallel — cache-first + throttled Firecrawl (_fc_throttle),
    #    so cache hits return instantly and cache-misses don't burst the rate limit.
    jobs = []
    for src in [s for s in SOURCES if s.get("on")]:
        jobs.append(threading.Thread(target=run, args=((lambda s: (lambda: fetch_from_source(s)))(src), src["key"])))
    for j in jobs:
        j.start()
    for j in jobs:
        j.join(timeout=150)
    # 2) grounded Google-Search discovery runs ALONE afterwards — it's slow and gets
    #    starved if it competes with the platform extractions for the Gemini API.
    run(fetch_events, "search")
    merged, seen = [], set()
    for evs in results:
        for e in evs:
            k = (e["title"].lower(), e["date"])
            if k not in seen:
                seen.add(k); merged.append(e)
    merged.sort(key=lambda e: (e["date"], _mins(e.get("time", ""))))
    return merged


def refresh_async():
    if _refreshing["on"]:
        return
    _refreshing["on"] = True

    def work():
        try:
            events = build_all_events()
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
                        events = build_all_events()
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


# ------------------------------------------------------------------- admin
def admin_data():
    """Operational snapshot for the admin panel: agents, content cache, sources."""
    s = load_store()
    now = time.time() * 1000
    pages = []
    try:
        for fn in os.listdir(CACHE_DIR):
            if not fn.endswith(".json"):
                continue
            fp = os.path.join(CACHE_DIR, fn)
            try:
                c = json.load(open(fp))
                pages.append({"url": c.get("url", ""),
                              "age_min": int((now - (c.get("ts") or 0)) / 60000),
                              "kb": round(os.path.getsize(fp) / 1024, 1)})
            except Exception:
                pass
    except Exception:
        pass
    pages.sort(key=lambda p: p["age_min"])
    regs = []
    for r in load_personal():
        if r.get("recurring") or r.get("scan_url") or r.get("seed"):
            regs.append({"id": r.get("id"), "title": r.get("title"),
                         "scan_url": r.get("scan_url") or "", "venue": r.get("venue", ""),
                         "scanned_min": (int((now - r["scanned_at"]) / 60000)
                                         if r.get("scanned_at") else None),
                         "sessions": len(r.get("sessions") or []),
                         "weekdays": r.get("weekdays") or [], "time": r.get("time", "")})
    # per-source counts from the current feed
    from collections import Counter
    counts = Counter(e.get("source") for e in (s.get("events") or []))
    sources = [{"name": "Our internet search", "key": "search", "on": True,
                "url": "Gemini + Google Search grounding", "hint": "All",
                "count": counts.get("Search", 0)}]
    for src in SOURCES:
        sources.append({"name": src["name"], "key": src["key"], "on": bool(src.get("on")),
                        "url": src["url"], "hint": src.get("hint", ""),
                        "count": counts.get(src["name"], 0)})
    return {
        "events": {"count": len(s.get("events") or []), "fetched_at": s.get("fetched_at", 0),
                   "ttl_h": REFRESH_H, "stale": is_stale(s), "model": GEMINI_MODEL},
        "cache": {"count": len(pages), "ttl_h": CACHE_H, "pages": pages},
        "crawl": {"every_h": CRAWL_EVERY_H}, "sources": sources,
        "regulars": regs, "home": HOME,
        "llm": bool(GEMINI_KEY), "firecrawl": bool(FIRECRAWL_KEY), "ts": int(now),
    }


def clear_cache():
    n = 0
    try:
        for fn in os.listdir(CACHE_DIR):
            if fn.endswith(".json"):
                os.remove(os.path.join(CACHE_DIR, fn)); n += 1
    except Exception:
        pass
    return n


ADMIN_PAGE = r"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Marquee · Admin & Systems</title>
<style>
 :root{--bg:#0b0b12;--card:#15151f;--card2:#1b1b27;--ink:#f4f3f8;--mut:#9a98ad;--line:#262636;--accent:#ff5c8a;--accent2:#a855f7}
 *{box-sizing:border-box}
 html,body{margin:0;background:radial-gradient(1100px 520px at 82% -8%,rgba(168,85,247,.2),transparent 60%),radial-gradient(900px 480px at 8% 4%,rgba(255,92,138,.16),transparent 58%),var(--bg);
   color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,system-ui,sans-serif;-webkit-font-smoothing:antialiased}
 a{color:#c6a6f0}
 .wrap{max-width:1060px;margin:0 auto;padding:24px 18px 70px}
 header{display:flex;align-items:center;gap:12px;margin-bottom:6px}
 h1{font-size:23px;margin:0;letter-spacing:-.02em}
 .sub{color:var(--mut);font-size:13px;margin:2px 0 0}
 .back{margin-left:auto;font-size:13px;font-weight:650;text-decoration:none}
 h2{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--mut);margin:30px 0 12px}
 .diagram{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:10px;overflow-x:auto}
 .diagram svg{display:block;min-width:720px;width:100%;height:auto}
 .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
 .agent{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;position:relative;overflow:hidden}
 .agent::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:linear-gradient(180deg,var(--accent),var(--accent2))}
 .agent h3{margin:0 0 4px;font-size:15px;display:flex;align-items:center;gap:8px}
 .agent .d{color:var(--mut);font-size:12.5px;line-height:1.5}
 .agent .st{margin-top:10px;font-size:12px;font-weight:650}
 .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
 .ok{color:#34d399}.ok .dot,.pill.ok .dot{background:#34d399}
 .warn{color:#fbbf24}.warn .dot{background:#fbbf24}
 .pill{display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:700;padding:4px 9px;border-radius:999px;background:var(--card2);border:1px solid var(--line);color:var(--mut)}
 table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}
 th,td{text-align:left;padding:10px 13px;font-size:12.5px;border-bottom:1px solid var(--line)}
 th{color:var(--mut);font-weight:700;font-size:10.5px;letter-spacing:.06em;text-transform:uppercase}
 td.u{font-family:ui-monospace,Menlo,monospace;color:#b7b4c8;word-break:break-all;max-width:360px}
 tr:last-child td{border-bottom:0}
 .controls{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0 0}
 .btn{border:0;border-radius:10px;padding:10px 15px;font:inherit;font-weight:700;font-size:13px;cursor:pointer;color:#fff;background:linear-gradient(135deg,var(--accent),var(--accent2))}
 .btn.ghost{background:var(--card2);color:var(--ink);border:1px solid var(--line)}
 .btn:disabled{opacity:.6;cursor:default}
 .mini{border:0;background:var(--card2);color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:6px 10px;font:inherit;font-size:12px;font-weight:650;cursor:pointer}
 .scanbtn{border:0;background:#2a1830;color:#ff9dc0;border:1px solid #4a2740;border-radius:8px;padding:6px 10px;font:inherit;font-size:12px;font-weight:650;cursor:pointer}
</style></head><body>
<div class="wrap">
 <header>
  <svg width="40" height="40" viewBox="0 0 48 48"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff5c8a"/><stop offset="1" stop-color="#a855f7"/></linearGradient></defs><rect width="48" height="48" rx="12" fill="url(#g)"/><rect x="11" y="15" width="26" height="20" rx="3" fill="#fff"/><g fill="#a855f7"><circle cx="17" cy="27" r="2"/><circle cx="24" cy="27" r="2"/><circle cx="31" cy="27" r="2"/></g></svg>
  <div><h1>Marquee · Admin &amp; Systems</h1><p class="sub">Agents, content cache, and how it all fits together.</p></div>
  <a class="back" href="/">← App</a>
 </header>

 <h2>How Marquee works</h2>
 <div class="diagram">__DIAGRAM__</div>

 <h2>Agents</h2>
 <div class="grid" id="agents"></div>

 <h2>Event sources <span id="srcHead" class="pill ok"><span class="dot"></span>—</span></h2>
 <table id="srcTbl"><thead><tr><th>Source</th><th>Type</th><th>In feed</th><th>Listing</th><th></th></tr></thead><tbody></tbody></table>

 <h2>Content cache <span id="cacheHead" class="pill ok"><span class="dot"></span>—</span></h2>
 <div class="controls" style="margin-bottom:12px">
   <button class="btn" id="refreshBtn">↻ Refresh events now</button>
   <button class="btn" id="crawlBtn"><svg width="15" height="15" viewBox="0 0 24 24" style="vertical-align:-2px" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="13" r="3.2"/><path d="M12 9.8V7M12 16.2V19M8.8 13H5.5M18.5 13h-3.3M9.6 10.6 7.2 8.6M16.8 8.6l-2.4 2M9.6 15.4l-2.4 2M16.8 17.4l-2.4-2"/></svg> Re-crawl &amp; scan regulars</button>
   <button class="btn ghost" id="clearBtn"><svg width="15" height="15" viewBox="0 0 24 24" style="vertical-align:-2px" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13M10 11v6M14 11v6"/></svg> Clear cache</button>
 </div>
 <table id="cacheTbl"><thead><tr><th>Cached source</th><th>Age</th><th>Size</th></tr></thead><tbody></tbody></table>

 <h2>Regulars (crawled &amp; scanned)</h2>
 <table id="regTbl"><thead><tr><th>Event</th><th>Schedule</th><th>Scanned</th><th>Sessions</th><th></th></tr></thead><tbody></tbody></table>

 <p class="sub" id="foot" style="margin-top:22px"></p>
</div>
<script>
function esc(s){return (s||'').replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function ago(min){if(min==null)return 'never';if(min<60)return min+'m ago';var h=Math.floor(min/60);if(h<24)return h+'h ago';return Math.floor(h/24)+'d ago';}
var WD=['Su','Mo','Tu','We','Th','Fr','Sa'];
function sched(r){if(!r.weekdays||!r.weekdays.length)return r.time||'—';if(r.weekdays.length===7)return 'Daily · '+(r.time||'');return r.weekdays.map(function(i){return WD[i];}).join(' ')+' · '+(r.time||'');}
function load(){
 fetch('api/admin',{cache:'no-store'}).then(function(r){return r.json();}).then(function(d){
  // agents
  var ev=d.events,A=[
   {n:'<svg width="15" height="15" viewBox="0 0 24 24" style="vertical-align:-2px" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/></svg> Discovery Agent',d:'Finds real NYC events via Gemini + Google Search grounding (strict: deep-link listings only). Writes the events cache.',
    st:(d.llm?'<span class="'+(ev.stale?'warn':'ok')+'"><span class="dot"></span>'+ev.count+' events · updated '+ago(Math.round((d.ts-ev.fetched_at)/60000))+' · TTL '+ev.ttl_h+'h</span>':'<span class="warn"><span class="dot"></span>LLM key missing</span>')},
   {n:'<svg width="15" height="15" viewBox="0 0 24 24" style="vertical-align:-2px" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="13" r="3.2"/><path d="M12 9.8V7M12 16.2V19M8.8 13H5.5M18.5 13h-3.3M9.6 10.6 7.2 8.6M16.8 8.6l-2.4 2M9.6 15.4l-2.4 2M16.8 17.4l-2.4-2"/></svg> Crawl Agent',d:'Every '+d.crawl.every_h+'h, refreshes the content cache for each regular\'s source page (Firecrawl). The app reads cache-first.',
    st:(d.firecrawl?'<span class="ok"><span class="dot"></span>'+d.cache.count+' pages cached · TTL '+d.cache.ttl_h+'h</span>':'<span class="warn"><span class="dot"></span>Firecrawl key missing</span>')},
   {n:'<svg width="15" height="15" viewBox="0 0 24 24" style="vertical-align:-2px" fill="currentColor"><path d="M9 4a2.6 2.6 0 0 0-2.6 2.6c0 .2 0 .3.1.5A2.8 2.8 0 0 0 4.8 12a2.8 2.8 0 0 0 1.5 4.3A2.5 2.5 0 0 0 11 16V5.5A1.5 1.5 0 0 0 9.5 4zm6 0a2.6 2.6 0 0 1 2.6 2.6c0 .2 0 .3-.1.5A2.8 2.8 0 0 1 19.2 12a2.8 2.8 0 0 1-1.5 4.3A2.5 2.5 0 0 1 13 16V5.5A1.5 1.5 0 0 1 14.5 4z"/></svg> Extract Agent',d:'Reads cached pages and extracts the real upcoming sessions (dates/times/links) with Gemini. Writes your regulars\' schedules.',
    st:'<span class="ok"><span class="dot"></span>'+d.regulars.length+' regulars tracked</span>'}
  ];
  document.getElementById('agents').innerHTML=A.map(function(a){return '<div class="agent"><h3>'+a.n+'</h3><div class="d">'+a.d+'</div><div class="st">'+a.st+'</div></div>';}).join('');
  // sources
  var on=(d.sources||[]).filter(function(s){return s.on;}).length;
  document.getElementById('srcHead').innerHTML='<span class="dot"></span>'+on+' active';
  document.querySelector('#srcTbl tbody').innerHTML=(d.sources||[]).map(function(s){
    var pill=s.on?'<span class="ok"><span class="dot"></span>on</span>':'<span style="color:#55536a">off</span>';
    var link=s.key==='search'?esc(s.url):'<a href="'+esc(s.url)+'" target="_blank" class="u" style="font-size:11px">'+esc(s.url.replace(/^https?:\/\//,''))+'</a>';
    return '<tr><td>'+esc(s.name)+'</td><td>'+esc(s.hint||'')+'</td><td>'+(s.count||0)+'</td><td>'+link+'</td><td>'+pill+'</td></tr>';
  }).join('');
  // cache
  document.getElementById('cacheHead').innerHTML='<span class="dot"></span>'+d.cache.count+' pages';
  document.querySelector('#cacheTbl tbody').innerHTML=(d.cache.pages.length?d.cache.pages.map(function(p){
    return '<tr><td class="u">'+esc(p.url)+'</td><td>'+ago(p.age_min)+'</td><td>'+p.kb+' KB</td></tr>';}).join(''):'<tr><td colspan="3" style="color:#55536a">Cache empty — crawl runs on boot and every '+d.crawl.every_h+'h.</td></tr>');
  // regulars
  document.querySelector('#regTbl tbody').innerHTML=d.regulars.map(function(r){
    return '<tr><td>'+esc(r.title)+'<div class="u" style="font-size:11px">'+esc(r.scan_url||'(no scan source)')+'</div></td><td>'+esc(sched(r))+'</td><td>'+ago(r.scanned_min)+'</td><td>'+r.sessions+'</td><td>'+(r.scan_url?'<button class="scanbtn" data-scan="'+r.id+'">⟳ Scan</button>':'')+'</td></tr>';
  }).join('');
  document.getElementById('foot').textContent='Home: '+d.home+' · LLM '+(d.llm?'on':'off')+' · Firecrawl '+(d.firecrawl?'on':'off')+' · '+new Date(d.ts).toLocaleString();
 });
}
document.getElementById('refreshBtn').onclick=function(){this.disabled=true;this.textContent='Refreshing…';fetch('api/refresh',{method:'POST'}).then(function(){setTimeout(function(){location.reload();},1500);});};
document.getElementById('clearBtn').onclick=function(){if(!confirm('Clear all cached pages?'))return;fetch('api/admin/clear-cache',{method:'POST'}).then(function(){load();});};
document.getElementById('crawlBtn').onclick=function(){var b=this;b.disabled=true;b.textContent='Crawling…';
 fetch('api/admin',{cache:'no-store'}).then(function(r){return r.json();}).then(function(d){
  var regs=d.regulars.filter(function(r){return r.scan_url;});
  return Promise.all(regs.map(function(r){return fetch('api/personal/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:r.id})});}));
 }).then(function(){b.textContent='✓ Done';setTimeout(function(){location.reload();},800);});};
document.getElementById('regTbl').addEventListener('click',function(ev){var b=ev.target.closest('[data-scan]');if(!b)return;b.textContent='⟳ …';b.disabled=true;
 fetch('api/personal/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:b.getAttribute('data-scan')})}).then(function(r){return r.json();}).then(function(x){b.textContent='✓ '+(x.count||0);setTimeout(load,700);});});
load();setInterval(load,30000);
</script></body></html>"""

# hand-built architecture diagram (SVG)
ADMIN_DIAGRAM = r"""<svg viewBox="0 0 980 560" xmlns="http://www.w3.org/2000/svg" font-family="-apple-system,Segoe UI,Inter,sans-serif">
 <defs>
  <linearGradient id="dg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff5c8a"/><stop offset="1" stop-color="#a855f7"/></linearGradient>
  <marker id="arw" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto"><path d="M0 0L9 4.5L0 9z" fill="#6b6980"/></marker>
  <marker id="arwp" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto"><path d="M0 0L9 4.5L0 9z" fill="#ff5c8a"/></marker>
 </defs>
 <style>
  .box{fill:#15151f;stroke:#2c2c3e;stroke-width:1.5;rx:12}
  .lane{fill:#10101a;stroke:#20202e;stroke-width:1;rx:14}
  .lbl{fill:#9a98ad;font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase}
  .t{fill:#f4f3f8;font-size:13.5px;font-weight:700}
  .s{fill:#9a98ad;font-size:11px}
  .edge{stroke:#6b6980;stroke-width:1.6;fill:none}
  .edgep{stroke:#ff5c8a;stroke-width:2;fill:none}
 </style>
 <!-- lanes -->
 <text x="20" y="34" class="lbl">Client</text>
 <text x="20" y="128" class="lbl">Marquee server · :18852</text>
 <text x="20" y="300" class="lbl">Background agents</text>
 <text x="20" y="494" class="lbl">External</text>

 <!-- client -->
 <rect class="box" x="20" y="44" width="200" height="60" rx="12"/>
 <text x="40" y="72" class="t">You · Browser / PWA</text>
 <text x="40" y="92" class="s">Week · Calendar · Mine · .ics</text>

 <!-- server -->
 <rect class="lane" x="20" y="140" width="940" height="120" rx="14"/>
 <rect class="box" x="40" y="160" width="190" height="80" rx="12"/>
 <text x="58" y="188" class="t">SPA + API</text>
 <text x="58" y="208" class="s">/api/events ·/widget</text>
 <text x="58" y="224" class="s">reads CACHE-FIRST</text>
 <rect class="box" x="258" y="160" width="200" height="80" rx="12"/>
 <text x="276" y="188" class="t">events.json</text>
 <text x="276" y="208" class="s">discovered NYC events</text>
 <text x="276" y="224" class="s">TTL 12h</text>
 <rect class="box" x="486" y="160" width="200" height="80" rx="12"/>
 <text x="504" y="188" class="t">personal.json</text>
 <text x="504" y="208" class="s">your regulars + saved</text>
 <text x="504" y="224" class="s">real scanned sessions</text>
 <rect class="box" x="714" y="160" width="226" height="80" rx="12" stroke="url(#dg)"/>
 <g transform="translate(728,176) scale(0.62)" fill="none" stroke="#f4f3f8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L4 14h6l-1 8 9-12h-6z" fill="#f4f3f8" stroke="none"/></g><text x="752" y="188" class="t">content cache</text>
 <text x="732" y="208" class="s">data/cache/&lt;sha1(url)&gt;</text>
 <text x="732" y="224" class="s">pull-from-here-first · TTL 12h</text>

 <!-- agents -->
 <rect class="box" x="40" y="312" width="270" height="100" rx="12"/>
 <g transform="translate(56,328) scale(0.62)" fill="none" stroke="#f4f3f8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/></g><text x="80" y="340" class="t">Discovery Agent</text>
 <text x="58" y="360" class="s">Gemini + Google Search grounding</text>
 <text x="58" y="378" class="s">strict: real deep-link listings only</text>
 <text x="58" y="396" class="s">→ writes events.json</text>
 <rect class="box" x="340" y="312" width="270" height="100" rx="12" stroke="url(#dg)"/>
 <g transform="translate(356,328) scale(0.62)" fill="none" stroke="#f4f3f8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="13" r="3.2"/><path d="M12 9.8V7M12 16.2V19M8.8 13H5.5M18.5 13h-3.3M9.6 10.6 7.2 8.6M16.8 8.6l-2.4 2M9.6 15.4l-2.4 2M16.8 17.4l-2.4-2"/></g><text x="380" y="340" class="t">Crawl Agent · every 6h</text>
 <text x="358" y="360" class="s">Firecrawl scrape of each source</text>
 <text x="358" y="378" class="s">refreshes the content cache</text>
 <text x="358" y="396" class="s">→ writes content cache</text>
 <rect class="box" x="640" y="312" width="300" height="100" rx="12"/>
 <g transform="translate(656,328) scale(0.62)" fill="none" stroke="#f4f3f8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 4a2.6 2.6 0 0 0-2.6 2.6c0 .2 0 .3.1.5A2.8 2.8 0 0 0 4.8 12a2.8 2.8 0 0 0 1.5 4.3A2.5 2.5 0 0 0 11 16V5.5A1.5 1.5 0 0 0 9.5 4zm6 0a2.6 2.6 0 0 1 2.6 2.6c0 .2 0 .3-.1.5A2.8 2.8 0 0 1 19.2 12a2.8 2.8 0 0 1-1.5 4.3A2.5 2.5 0 0 1 13 16V5.5A1.5 1.5 0 0 1 14.5 4z" fill="#f4f3f8" stroke="none"/></g><text x="680" y="340" class="t">Extract Agent</text>
 <text x="658" y="360" class="s">reads cache → Gemini extracts</text>
 <text x="658" y="378" class="s">real dates/times/links</text>
 <text x="658" y="396" class="s">→ writes personal.json sessions</text>

 <!-- external -->
 <rect class="box" x="40" y="506" width="180" height="44" rx="10"/>
 <text x="58" y="533" class="t">Gemini API</text>
 <rect class="box" x="240" y="506" width="180" height="44" rx="10"/>
 <text x="258" y="533" class="t">Firecrawl API</text>
 <rect class="box" x="440" y="506" width="500" height="44" rx="10"/>
 <text x="458" y="527" class="t">Event sources</text>
 <text x="458" y="543" class="s">ClassPass · Tickettailor · Luma · AXS · venue &amp; org pages</text>

 <!-- edges -->
 <line class="edgep" x1="120" y1="104" x2="120" y2="158" marker-end="url(#arwp)"/>
 <text x="235" y="52" class="s" fill="#ff9dc0">↙ cache-first reads · serves instantly</text>
 <path class="edge" d="M175 312 C175 285 150 268 140 242" marker-end="url(#arw)"/>
 <path class="edge" d="M475 312 C475 285 400 262 360 242" marker-end="url(#arw)"/>
 <path class="edge" d="M790 312 C790 280 800 262 810 242" marker-end="url(#arw)"/>
 <path class="edgep" d="M560 360 C650 360 760 300 820 242" marker-end="url(#arwp)"/>
 <line class="edge" x1="130" y1="412" x2="130" y2="504" marker-end="url(#arw)"/>
 <line class="edge" x1="420" y1="412" x2="330" y2="504" marker-end="url(#arw)"/>
 <line class="edge" x1="760" y1="412" x2="150" y2="506" stroke-dasharray="4 4" opacity="0.4"/>
 <line class="edge" x1="475" y1="412" x2="520" y2="504" marker-end="url(#arw)" stroke-dasharray="4 4" opacity="0.6"/>
</svg>"""

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
 .home{color:#ffb3cb;font-weight:700}
 .ci{width:14px;height:14px;display:inline-block;vertical-align:-2px;flex:0 0 auto}
 .controls{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px}
 .near-tag{display:inline-flex;align-items:center;gap:3px;font-size:9px;font-weight:800;letter-spacing:.04em;
   text-transform:uppercase;padding:3px 7px;border-radius:6px;color:#fff;background:linear-gradient(135deg,#f59e0b,#ef4444)}
 .src{font-size:10.5px;color:#6f6d85;font-weight:600}
 .top{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:18px}
 .actions{margin-left:auto;display:flex;gap:8px}
 .refresh{border:1px solid var(--line);background:var(--card);color:var(--mut);
   border-radius:10px;padding:8px 13px;font:inherit;font-size:12.5px;font-weight:600;cursor:pointer;display:inline-flex;gap:7px;align-items:center}
 .refresh:hover{color:var(--ink);border-color:#3a3a50}
 .refresh.add{color:#fff;border-color:transparent;background:linear-gradient(135deg,var(--accent),var(--accent2));box-shadow:0 4px 16px -6px rgba(255,92,138,.6)}
 .refresh.add:hover{filter:brightness(1.07)}
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
 .cell{min-height:108px;border-radius:11px;background:var(--card2);border:1px solid transparent;padding:5px 5px 4px;cursor:default;position:relative;transition:.12s;overflow:hidden}
 .cell.pad{background:transparent}
 .cell.has{cursor:pointer}.cell.has:hover{border-color:#3a3a50}
 .cell.today{box-shadow:inset 0 0 0 1.5px var(--accent)}
 .cell.sel{border-color:var(--accent);background:#241a26}
 .cell .d{font-size:12px;font-weight:650;color:var(--mut);padding:1px 3px}
 .cell.today .d{color:var(--accent)}
 .cevs{display:flex;flex-direction:column;gap:2px;margin-top:3px}
 .evchip{display:flex;align-items:baseline;gap:4px;text-decoration:none;font-size:10.5px;line-height:1.35;
   padding:2px 5px;border-radius:4px;background:rgba(255,255,255,.055);border-left:3px solid var(--c);
   color:#dcdae8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .evchip:hover{background:color-mix(in srgb,var(--c) 26%,transparent);color:#fff}
 .evchip .ct{color:var(--c);font-weight:800;flex:0 0 auto}
 .evchip.mine{background:color-mix(in srgb,var(--c) 20%,transparent)}
 .cell .more{font-size:9.5px;color:var(--mut);font-weight:700;padding:2px 5px 0}
 @media(min-width:900px){.cell{min-height:118px}}
 /* list */
 .day-h{font-size:13px;font-weight:750;color:var(--accent);margin:22px 2px 11px;letter-spacing:.01em;
   text-transform:uppercase;display:flex;align-items:center;gap:9px}
 .day-h .ln{flex:1;height:1px;background:var(--line)}
 .day-h.today{color:#fff}.day-h.today .ln{background:linear-gradient(90deg,var(--accent),transparent)}
 .noday{color:#55536a;font-size:12px;padding:2px 2px 8px}
 .ev{display:flex;gap:14px;padding:14px 15px;border:1px solid var(--line);background:var(--card);border-radius:14px;margin-bottom:10px;transition:.15s;text-decoration:none;cursor:pointer}
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
 .ev.mine{background:linear-gradient(135deg,#1a1326,#17121f);border-color:rgba(255,92,138,.4)}
 .mine-tag{display:inline-flex;align-items:center;gap:3px;font-size:9px;font-weight:800;letter-spacing:.04em;
   text-transform:uppercase;padding:3px 7px;border-radius:6px;color:#fff;background:linear-gradient(135deg,#ff5c8a,#a855f7)}
 .acts{flex:0 0 auto;display:flex;flex-direction:column;gap:6px;align-self:center}
 .act{border:0;background:rgba(255,255,255,.06);color:var(--mut);width:30px;height:30px;border-radius:8px;
   cursor:pointer;font-size:14px;line-height:1;display:inline-flex;align-items:center;justify-content:center}
 .act:hover{background:rgba(255,255,255,.14);color:#fff}
 .act.del:hover{background:rgba(239,68,68,.28);color:#fff}
 .minebar{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin:0 0 16px;padding:14px 16px;border-radius:14px;
   background:linear-gradient(135deg,#1a1326,#17121f);border:1px solid rgba(255,92,138,.35)}
 .minebar b{display:block;font-size:14px;color:#fff}
 .minebar span{display:block;font-size:12px;color:var(--mut);margin-top:2px}
 .scanbtn{margin-left:auto;border:0;border-radius:10px;padding:10px 15px;font:inherit;font-weight:700;font-size:13px;
   cursor:pointer;color:#fff;background:linear-gradient(135deg,var(--accent),var(--accent2));box-shadow:0 4px 16px -6px rgba(255,92,138,.6)}
 .scanbtn:disabled{opacity:.7;cursor:default}
 .empty{color:var(--mut);padding:30px 4px;text-align:center;font-size:14px}
 /* add-event modal */
 /* event detail modal */
 .evm-card{position:relative;background:var(--card);border:1px solid var(--line);border-radius:18px;max-width:460px;width:100%;overflow:hidden;box-shadow:0 30px 80px -20px rgba(0,0,0,.7)}
 .apps-sheet{position:relative;background:var(--card);border:1px solid var(--line);border-radius:18px;max-width:460px;width:100%;max-height:86vh;overflow:auto;box-shadow:0 30px 80px -20px rgba(0,0,0,.7);padding:18px 16px}
 .apps-head{display:flex;align-items:center;justify-content:space-between}
 .apps-head b{font-size:18px}
 .apps-sub{color:#9a98ad;font-size:12.5px;margin:3px 0 14px}
 .apps-grid{display:flex;flex-direction:column;gap:9px}
 .app-link{text-decoration:none;color:inherit;display:block}
 .app-card{display:flex;gap:12px;align-items:center;background:#15151f;border:1px solid var(--line);border-radius:14px;padding:11px 12px;transition:.14s}
 .app-card:hover{border-color:#3a3a50;transform:translateY(-1px)}
 .app-ico{flex:0 0 auto;width:40px;height:40px;border-radius:11px;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:800;font-size:18px}
 .app-main{min-width:0}
 .app-n{font-weight:700;font-size:14.5px;display:flex;align-items:center;gap:7px}
 .app-d{color:#9a98ad;font-size:12px;margin-top:2px;line-height:1.35}
 .app-tag{font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.05em;padding:2px 6px;border-radius:999px;flex:0 0 auto}
 .app-tag.public{background:rgba(52,211,153,.16);color:#34d399}
 .app-tag.private{background:rgba(148,148,170,.18);color:#bdbccb}
 .app-tag.soon{background:rgba(245,201,119,.16);color:#f5c977}
 .src-card{width:100%;text-align:left;cursor:pointer;font:inherit}
 .src-wrap.open .src-card{border-bottom-left-radius:0;border-bottom-right-radius:0}
 .src-chev{flex:0 0 auto;color:#6f6794;font-size:18px;margin-left:2px}
 .src-det{background:#100f1a;border:1px solid var(--line);border-top:0;border-radius:0 0 14px 14px;padding:4px 10px 8px}
 .src-ev{display:flex;gap:10px;padding:7px 2px;border-bottom:1px solid rgba(255,255,255,.05);font-size:12px}
 .src-ev:last-child{border-bottom:0}
 .src-ev-d{flex:0 0 auto;color:var(--gold);font-weight:700;min-width:82px}
 .src-ev-t{min-width:0;color:var(--text)}
 .src-visit{display:inline-flex;align-items:center;gap:6px;margin-top:8px;color:#c4a0ff;font-size:12px;text-decoration:none}
 .src-visit .ci{width:13px;height:13px}
 .wk-head{display:flex;align-items:center;justify-content:space-between;margin:2px 2px 10px}
 .wk-head b{font-size:15px;font-family:var(--serif)}
 .wk-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:5px;margin:0 2px 16px}
 .wk-day{display:flex;flex-direction:column;align-items:center;gap:2px;padding:8px 2px 7px;border-radius:12px;background:#13101f;border:1px solid var(--line);color:var(--text);cursor:pointer;min-height:60px;transition:.12s}
 .wk-day:active{transform:scale(.96)}
 .wk-day.sel{border-color:var(--gold);background:rgba(245,201,119,.1)}
 .wk-day.today .wk-num{color:var(--gold)}
 .wk-dow{font-size:9.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.03em}
 .wk-num{font-size:16px;font-weight:700;line-height:1.1}
 .wk-dots{display:flex;gap:2px;flex-wrap:wrap;justify-content:center;min-height:6px;margin-top:2px;max-width:44px}
 .wk-dots i{width:5px;height:5px;border-radius:50%;display:block}
 .wk2{margin:0 2px 8px}
 .wk2-hdr{display:flex;margin:0 2px 0}
 .wk2-gutter{width:30px;flex:0 0 30px}
 .wk2-dcol{flex:1;text-align:center;padding:3px 0 6px;min-width:0;background:none;border:0;color:var(--text);cursor:pointer;font:inherit}
 .wk2-dcol.sel{background:rgba(168,85,247,.18);border-radius:10px}
 .wk2-dow{display:block;font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.02em}
 .wk2-dnum{font-size:14px;font-weight:700;line-height:1.3}
 .wk2-dcol.today .wk2-dnum{color:#1a1020;background:var(--gold);border-radius:999px;width:22px;height:22px;line-height:22px;display:inline-block}
 .wk2-dcol.today .wk2-dow{color:var(--gold)}
 .wk2-grid{display:flex;border-top:1px solid var(--line)}
 .wk2-gutter2{width:30px;flex:0 0 30px}
 .wk2-hr{font-size:8px;color:var(--muted);text-align:right;padding-right:4px;box-sizing:border-box;border-bottom:1px solid rgba(255,255,255,.045);overflow:visible}
 .wk2-cols{flex:1;display:flex;position:relative;background-image:linear-gradient(rgba(255,255,255,.05) 1px,transparent 1px);background-position:0 -1px}
 .wk2-col{flex:1;position:relative;border-left:1px solid rgba(255,255,255,.05);min-width:0}
 .wk2-col.today{background:rgba(245,201,119,.05)}
 .wk2-ev{position:absolute;border-radius:5px;padding:2px 3px;overflow:hidden;color:#fff;font-size:8.5px;line-height:1.12;cursor:pointer;background:linear-gradient(150deg,#ff5c8a,#8b5cf6);box-shadow:0 1px 3px rgba(124,58,237,.35);box-sizing:border-box;border:.5px solid rgba(255,255,255,.14)}
 .wk2-ev b{display:block;font-weight:800;font-size:8.5px;white-space:nowrap}
 .wk2-now{position:absolute;left:0;right:0;height:0;border-top:1.5px solid #ff5c8a;z-index:4;pointer-events:none}
 .wk2-now:before{content:'';position:absolute;left:-2px;top:-3.5px;width:6px;height:6px;border-radius:50%;background:#ff5c8a}
 .evm-top{height:6px}
 .evm-x{position:absolute;top:12px;right:12px;border:0;background:rgba(255,255,255,.08);color:#dcdae8;width:30px;height:30px;border-radius:9px;cursor:pointer;font-size:14px;line-height:1}
 .evm-x:hover{background:rgba(255,255,255,.16)}
 .evm-body{padding:20px}
 .evm-cat{font-size:11px;font-weight:700;letter-spacing:.03em;color:#ff9dc0;display:flex;align-items:center;gap:5px}
 .evm-cat .ci{width:13px;height:13px}
 .evm-title{margin:8px 0 6px;font-size:21px;line-height:1.25;letter-spacing:-.01em}
 .evm-when{font-size:14px;font-weight:650;color:#fff;margin-bottom:12px}
 .evm-row{font-size:13.5px;color:#c8c6d6;margin:5px 0;line-height:1.4}
 .evm-blurb{font-size:13.5px;color:#9a98ad;line-height:1.5;margin:12px 0}
 .evm-link{font-size:12px;margin:10px 0 0;word-break:break-all}
 .evm-link a{color:#c6a6f0}
 .evm-actions{display:flex;flex-direction:column;gap:9px;margin-top:18px}
 .evm-btn{display:flex;align-items:center;justify-content:center;gap:7px;text-decoration:none;border:1px solid var(--line);background:var(--card2);color:var(--ink);border-radius:11px;padding:13px;font:inherit;font-weight:700;font-size:14px;cursor:pointer}
 .evm-btn:hover{border-color:#3a3a50}
 .evm-btn.primary{border-color:transparent;color:#fff;background:linear-gradient(135deg,var(--accent),var(--accent2));box-shadow:0 4px 16px -6px rgba(255,92,138,.6)}
 .evm-btn.danger:hover{background:rgba(239,68,68,.2);border-color:#5a2730;color:#fff}
 .sch-list{max-height:52vh;overflow:auto;margin-top:6px}
 .sch-day{font-size:11px;font-weight:800;letter-spacing:.05em;text-transform:uppercase;color:#ff9dc0;margin:14px 0 6px}
 .sch-row{display:flex;align-items:center;gap:10px;padding:8px 2px;border-bottom:1px solid var(--line)}
 .sch-t{flex:0 0 66px;font-size:12.5px;font-weight:700;color:#fff;font-variant-numeric:tabular-nums}
 .sch-n{flex:1;min-width:0;font-size:13px;color:#c8c6d6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .sch-go{flex:0 0 auto;border:1px solid var(--line);background:var(--card2);color:var(--ink);border-radius:8px;padding:6px 10px;font:inherit;font-size:12px;font-weight:700;cursor:pointer}
 .sch-go.on{color:#fff;border-color:transparent;background:linear-gradient(135deg,#10b981,#0d9488)}
 .sch-go:disabled{opacity:.6;cursor:default}
 .modal-bg{position:fixed;inset:0;background:rgba(5,5,10,.7);display:flex;align-items:center;justify-content:center;z-index:60;padding:18px}
 .modal-bg[hidden]{display:none}
 .modal{background:var(--card);border:1px solid var(--line);border-radius:18px;max-width:440px;width:100%;padding:22px;box-shadow:0 30px 80px -20px rgba(0,0,0,.7)}
 .modal h3{margin:0 0 4px;font-size:18px}
 .modal .mh{color:var(--mut);font-size:12px;margin:0 0 16px}
 .modal label{display:block;font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--mut);margin:12px 0 5px}
 .modal input[type=text],.modal select{width:100%;background:var(--card2);border:1px solid var(--line);color:var(--ink);
   border-radius:10px;padding:10px 12px;font:inherit;font-size:14px}
 .modal input::placeholder{color:#6b6980}
 .wdays{display:flex;gap:5px}
 .wday{flex:1;text-align:center;border:1px solid var(--line);background:var(--card2);color:var(--mut);border-radius:9px;padding:8px 0;font:inherit;font-size:12px;font-weight:700;cursor:pointer}
 .wday.on{color:#fff;border-color:transparent;background:linear-gradient(135deg,var(--accent),var(--accent2))}
 .mrow{display:flex;gap:10px}.mrow>div{flex:1}
 .mnear{display:flex;align-items:center;gap:8px;margin-top:14px;font-size:13px;color:var(--ink);cursor:pointer}
 .mnear input{width:16px;height:16px;accent-color:var(--accent)}
 .modal-actions{display:flex;gap:10px;margin-top:20px}
 .modal-actions button{flex:1;border:0;border-radius:11px;padding:12px;font:inherit;font-weight:700;font-size:14px;cursor:pointer}
 .m-cancel{background:var(--card2);color:var(--mut)}
 .m-save{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff}
 .subbtn{display:block;text-align:center;text-decoration:none;margin-top:6px;border-radius:11px;padding:13px;font-weight:700;font-size:14px;color:#fff;background:linear-gradient(135deg,var(--accent),var(--accent2));box-shadow:0 4px 16px -6px rgba(255,92,138,.6)}
 .subbtn:hover{filter:brightness(1.07)}
 .subrow{display:flex;gap:8px;margin-top:6px}
 .subrow input{flex:1;min-width:0;border:1px solid var(--line);background:var(--card2);color:var(--ink);border-radius:10px;padding:11px;font:inherit;font-size:12.5px}
 .subrow button{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:10px;padding:0 15px;font:inherit;font-weight:700;font-size:13px;cursor:pointer}
 .subrow button:hover{border-color:#3a3a50}
 .foot{color:var(--mut);font-size:11.5px;text-align:center;margin-top:34px}
 @media(max-width:560px){
  .cell{min-height:66px;padding:3px 3px 2px}
  .ev .bl{display:none}
  .cevs{gap:2px;margin-top:2px}
  .evchip{font-size:0;line-height:0;height:5px;padding:0;border-left-width:0;border-radius:3px;background:var(--c)}
  .evchip .ct{display:none}
  .cell .d{font-size:11px}
  .cell .more{font-size:9px;padding:1px 3px 0}
 }
.mq-widgets{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:14px 0 4px}
@media(max-width:620px){.mq-widgets{grid-template-columns:1fr}}
.mqtd,.mqrp{background:#fff;border:1px solid #eceaf2;border-radius:16px;padding:14px 15px;
  box-shadow:0 1px 2px rgba(20,23,30,.04),0 14px 34px -18px rgba(124,58,237,.22);text-decoration:none;color:inherit;display:block}
.mqrp{transition:transform .1s,box-shadow .15s} .mqrp:hover{transform:translateY(-1px);box-shadow:0 18px 40px -16px rgba(124,58,237,.3)}
.mqw2-head{display:flex;align-items:center;gap:8px;margin-bottom:9px}
.mqw2-head h3{margin:0;font-size:15px;font-weight:800}
.mqw2-dot{width:9px;height:9px;border-radius:50%;flex:0 0 auto}
.mqw2-dot.td{background:linear-gradient(135deg,#6366f1,#ec4899)} .mqw2-dot.rp{background:linear-gradient(135deg,#a855f7,#6366f1)}
.mqtd-count{margin-left:auto;font-size:12px;color:#8f8da3;font-weight:600}
.mqtd-add{display:flex;gap:7px;margin-bottom:9px}
.mqtd-add input{flex:1;border:1px solid #e7e5ee;border-radius:10px;padding:9px 11px;font-size:13.5px;background:#faf9fc;outline:none;color:#241f33}
.mqtd-add input:focus{border-color:#a855f7;box-shadow:0 0 0 3px rgba(168,85,247,.13)}
.mqtd-add button{width:38px;border:none;border-radius:10px;background:linear-gradient(135deg,#6366f1,#a855f7,#ec4899);color:#fff;font-size:19px;cursor:pointer}
.mqtd-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:5px;max-height:168px;overflow:auto}
.mqtd-item{display:flex;align-items:center;gap:9px;padding:8px 9px;border-radius:10px;background:#fbfafe;cursor:pointer}
.mqtd-item .bx{width:19px;height:19px;border:2px solid #cfd2dc;border-radius:6px;flex:0 0 auto;display:flex;align-items:center;justify-content:center;color:#fff;font-size:12px}
.mqtd-item.done .bx{border-color:transparent;background:linear-gradient(135deg,#6366f1,#ec4899)}
.mqtd-item .tx{flex:1;font-size:13.5px;color:#241f33} .mqtd-item.done .tx{color:#9a97a8;text-decoration:line-through}
.mqtd-item .rm{border:none;background:none;color:#c6cad4;font-size:15px;cursor:pointer;opacity:0}
.mqtd-item:hover .rm{opacity:1} .mqtd-item .rm:hover{color:#ec4899}
.mqtd-empty{font-size:13px;color:#9a97a8;padding:4px 2px}
.mqrp-date{margin-left:auto;font-size:12px;color:#8f8da3}
.mqrp-body{font-size:13px;line-height:1.5;color:#4b4760;white-space:pre-wrap;max-height:120px;overflow:hidden;
  -webkit-mask-image:linear-gradient(#000 68%,transparent);mask-image:linear-gradient(#000 68%,transparent)}
.mqrp-all{display:inline-block;margin-top:9px;font-size:12.5px;font-weight:700;color:#6d28d9}
</style></head><body>
<div class="wrap">
 <div class="top">
  <header>
   <svg class="mk" viewBox="0 0 48 48" fill="none"><rect width="48" height="48" rx="12" fill="url(#mg)"/>
    <defs><linearGradient id="mg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff5c8a"/><stop offset="1" stop-color="#a855f7"/></linearGradient></defs>
    <rect x="11" y="15" width="26" height="20" rx="3" fill="#fff"/><rect x="11" y="15" width="26" height="6" rx="3" fill="#ffd7e4"/>
    <circle cx="16" cy="12" r="2" fill="#fff"/><circle cx="24" cy="11" r="2" fill="#fff"/><circle cx="32" cy="12" r="2" fill="#fff"/>
    <g fill="#a855f7"><circle cx="17" cy="27" r="2"/><circle cx="24" cy="27" r="2"/><circle cx="31" cy="27" r="2"/><circle cx="17" cy="32" r="2"/><circle cx="24" cy="32" r="2"/></g></svg>
   <div><h1>Marquee</h1><p class="sub">What's on in NYC · <button class="home" id="homePill" title="Set your area"><svg class="ci" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M12 21s7-6.3 7-11a7 7 0 1 0-14 0c0 4.7 7 11 7 11z"/><circle cx="12" cy="10" r="2.4" fill="currentColor" stroke="none"/></svg> Set your area</button></p></div>
  </header>
  <div class="actions">
   <button class="refresh add" id="addBtn" title="Add your own event">+ Add event</button>
   <button class="refresh" id="subBtn" title="Subscribe in Google / Apple Calendar">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="17" rx="2"/><path d="M3 9h18M8 2v4M16 2v4M12 12v6M9 15h6"/></svg>Subscribe</button>
   <button class="refresh" id="refresh" title="Refresh events">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round"><path d="M21 12a9 9 0 1 1-2.6-6.3M21 3v6h-6"/></svg>Refresh</button>
   <button class="refresh" id="appsBtn" title="Where our events come from"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="18.5" r="1.6"/><path d="M8 15a5.5 5.5 0 0 1 8 0M5 11.5a10 10 0 0 1 14 0M2 8a14.5 14.5 0 0 1 20 0"/></svg>Sources</button>
  </div>
 </div>
 <div class="mq-widgets">
  <div class="mqtd" id="mqTodo" hidden>
   <div class="mqw2-head"><span class="mqw2-dot td"></span><h3>To-do</h3><span class="mqtd-count" id="mqTdCount"></span></div>
   <form class="mqtd-add" id="mqTdForm"><input id="mqTdInput" placeholder="Add a task…" autocomplete="off"><button type="submit" aria-label="Add">＋</button></form>
   <ul class="mqtd-list" id="mqTdList"></ul>
  </div>
  <a class="mqrp" id="mqReport" href="https://reports.bedrock.casa/" target="_blank" rel="noopener" hidden>
   <div class="mqw2-head"><span class="mqw2-dot rp"></span><h3 id="mqRpTitle">Daily report</h3><span class="mqrp-date" id="mqRpDate"></span></div>
   <div class="mqrp-body" id="mqRpBody"></div>
   <span class="mqrp-all">Read today&rsquo;s report →</span>
  </a>
 </div>
 <div class="chips" id="chips"></div>
 <div class="controls">
   <span class="views" id="loc"><button data-l="mine" class="on">★ Mine</button><button data-l="near">★ Near me</button><button data-l="all">All NYC</button></span>
   <span class="views" id="views"><button data-v="week" class="on">This week</button><button data-v="cal">Calendar</button><button data-v="list">Upcoming</button></span>
 </div>
 <div id="calWrap" class="cal" hidden>
  <div class="cal-head"><button class="cal-nav" id="pm">‹</button><b id="monLbl"></b><button class="cal-nav" id="nm">›</button></div>
  <div class="grid" id="dows"></div><div class="grid" id="cells" style="margin-top:6px"></div>
 </div>
 <div id="list"></div>
 <div class="foot" id="foot"></div>
 <div class="foot" style="margin-top:6px"><a href="/admin" style="color:#8f8da3;text-decoration:none"><svg class="ci" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 2.5l1.6 2.3 2.7-.6.6 2.7 2.3 1.6-1 2.6 1 2.6-2.3 1.6-.6 2.7-2.7-.6L12 21.5l-1.6-2.3-2.7.6-.6-2.7L4.8 15.5l1-2.6-1-2.6 2.3-1.6.6-2.7 2.7.6z"/></svg> Admin &amp; systems</a></div>
</div>
<div class="modal-bg" id="addModal" hidden><div class="modal">
 <h3>Add an event</h3>
 <p class="mh">Add it to your Marquee calendar — one-off or repeating weekly.</p>
 <label>Title</label><input type="text" id="f_title" placeholder="e.g. Baby Cobra Yoga">
 <div class="mrow">
  <div><label>Category</label><select id="f_cat"></select></div>
  <div><label>Time</label><input type="text" id="f_time" placeholder="7:00 PM"></div>
 </div>
 <label>Repeat weekly on</label>
 <div class="wdays" id="f_wdays"></div>
 <div class="mrow" style="margin-top:10px">
  <div><label>…or one-time date</label><input type="text" id="f_date" placeholder="YYYY-MM-DD"></div>
 </div>
 <label>Venue / location</label><input type="text" id="f_venue" placeholder="47 Thames St, Bushwick">
 <label>Website / tickets URL</label><input type="text" id="f_url" placeholder="https://…">
 <label class="mnear"><input type="checkbox" id="f_near" checked> Near my home area</label>
 <div class="modal-actions"><button class="m-cancel" id="f_cancel">Cancel</button><button class="m-save" id="f_save">Add to calendar</button></div>
</div></div>
<div class="modal-bg" id="subModal" hidden><div class="modal">
 <h3>Subscribe in your calendar</h3>
 <p class="mh">Your regulars &amp; saved events auto-sync to Google or Apple Calendar — new sessions show up on their own.</p>
 <label>Apple Calendar / iPhone (one tap)</label>
 <a class="subbtn" id="sub_webcal" href="#">＋ Add to Apple Calendar</a>
 <label style="margin-top:14px">Google Calendar → “From URL”</label>
 <div class="subrow"><input type="text" id="sub_url" readonly><button id="sub_copy">Copy</button></div>
 <p class="mh" style="margin-top:6px">In Google Calendar: <b>Other calendars → + → From URL</b>, then paste.</p>
 <div class="modal-actions"><button class="m-cancel" id="sub_cancel">Done</button></div>
</div></div>
<div class="modal-bg" id="homeModal" hidden><div class="modal"><h3>Your home area</h3><p class="mh">Set where you live so <b>Near me</b> surfaces what&rsquo;s close to you.</p><label>Neighborhood</label><input type="text" id="home_nb" placeholder="e.g. Bushwick"><label style="margin-top:12px">Borough</label><select id="home_boro"><option value="">Select…</option><option>Manhattan</option><option>Brooklyn</option><option>Queens</option><option>Bronx</option><option>Staten Island</option></select><div class="modal-actions"><button class="m-cancel" id="home_cancel">Cancel</button><button class="m-save" id="home_save">Save</button></div></div></div>
<div class="modal-bg" id="evModal" hidden><div class="evm-card"></div></div>
<div class="modal-bg" id="appsModal" hidden><div class="apps-sheet"><div class="apps-head"><b>Where events come from</b><button class="evm-x" data-close title="Close">✕</button></div><p class="apps-sub">Marquee pulls live events from these platforms — scanned &amp; refreshed daily.</p><div class="apps-grid" id="appsGrid"></div></div></div>
<script>
var CATCOLOR={Music:'#ff5c8a',Nightlife:'#a855f7',Arts:'#38bdf8',Theater:'#f59e0b',Comedy:'#fbbf24',
  Sports:'#22c55e',Food:'#fb7185',Festival:'#ec4899',Family:'#2dd4bf',Film:'#818cf8',Wellness:'#22d3ee'};
var SERVER_HOME='';
function getHome(){try{var h=localStorage.getItem('mq_home');if(h){var o=JSON.parse(h);if(o&&(o.neighborhood||o.borough))return o;}}catch(e){}
 if(SERVER_HOME){var p=SERVER_HOME.split(',');return {neighborhood:(p[0]||'').trim(),borough:(p[1]||'').trim(),label:SERVER_HOME};}return null;}
function homeLabel(){var h=getHome();return h?(h.label||[h.neighborhood,h.borough].filter(Boolean).join(', ')):'Set your area';}
function nearMe(e){var h=getHome();if(!h)return false;var n=(e.neighborhood||'').toLowerCase(),b=(e.borough||'').toLowerCase();
 if(h.neighborhood&&n&&n===h.neighborhood.toLowerCase())return true;
 if(h.borough&&b&&b===h.borough.toLowerCase())return true;return false;}
var CAT_SVG={
 Music:'<svg class="ci" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3v10.6A4 4 0 1 0 14 17V7.3l5-1.1V3z"/></svg>',
 Nightlife:'<svg class="ci" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l1.9 6.3L20 10l-6.1 1.7L12 18l-1.9-6.3L4 10l6.1-1.7z"/></svg>',
 Arts:'<svg class="ci" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3a9 9 0 0 0 0 18c1.3 0 2-1 1.5-2.2-.5-1.3.4-2.3 1.7-2.3H17A4 4 0 0 0 20.5 9 9 9 0 0 0 12 3zM7 13a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm2-4a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm6 0a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3z"/></svg>',
 Theater:'<svg class="ci" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h16v5a8 8 0 0 1-16 0z"/><path d="M9 9h.01M15 9h.01M9.5 13c1.3 1.1 3.7 1.1 5 0"/></svg>',
 Comedy:'<svg class="ci" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="3" width="6" height="11" rx="3" fill="currentColor" stroke="none"/><path d="M6 11a6 6 0 0 0 12 0M12 17v4M9 21h6"/></svg>',
 Sports:'<svg class="ci" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3v18M5.6 5.6c3 2.4 3 10.4 0 12.8M18.4 5.6c-3 2.4-3 10.4 0 12.8"/></svg>',
 Food:'<svg class="ci" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3v5a2 2 0 0 0 4 0V3M7 3v18M18.5 3c-1.8 0-2.5 2.6-2.5 5.5s2 3.5 2 3.5V21"/></svg>',
 Festival:'<svg class="ci" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v3M12 6 4 20h16L12 6zM12 6 8.5 20M12 6l3.5 14"/></svg>',
 Family:'<svg class="ci" viewBox="0 0 24 24" fill="currentColor"><circle cx="8" cy="7" r="3"/><circle cx="16" cy="7" r="3"/><path d="M2 20a6 6 0 0 1 12 0zm8 0a6 6 0 0 1 12 0z"/></svg>',
 Film:'<svg class="ci" viewBox="0 0 24 24" fill="currentColor"><path d="M3 9h18v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/><path d="M3.3 4.5 20.4 6.8l-.4 2.7L3 7.2z"/></svg>',
 Wellness:'<svg class="ci" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="5" r="2.2" fill="currentColor" stroke="none"/><path d="M12 9c-1.5 1.4-5 2-5 2 .4 2.8 2.4 4.5 5 4.5s4.6-1.7 5-4.5c0 0-3.5-.6-5-2z" fill="currentColor" stroke="none"/><path d="M4 18c2.6 1.8 13.4 1.8 16 0"/></svg>'};
function catIcon(k){return CAT_SVG[k]||'';}
var IC={
 pin:'<svg class="ci" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M12 21s7-6.3 7-11a7 7 0 1 0-14 0c0 4.7 7 11 7 11z"/><circle cx="12" cy="10" r="2.4" fill="currentColor" stroke="none"/></svg>',
 clock:'<svg class="ci" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/></svg>',
 ticket:'<svg class="ci" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M4 8a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2 2 2 0 0 0 0 4 2 2 0 0 1-2 2H6a2 2 0 0 1-2-2 2 2 0 0 0 0-4z"/><path d="M15 6.5v11" stroke-dasharray="1.6 2.4"/></svg>',
 cal:'<svg class="ci" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="5" width="17" height="16" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/></svg>',
 link:'<svg class="ci" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10.5 13.2a4 4 0 0 0 5.7 0l2.3-2.3a4 4 0 0 0-5.7-5.7l-1.3 1.3"/><path d="M13.5 10.8a4 4 0 0 0-5.7 0l-2.3 2.3a4 4 0 0 0 5.7 5.7l1.3-1.3"/></svg>',
 list:'<svg class="ci" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="4" width="14" height="17" rx="2.5"/><path d="M9.5 3h5v3h-5zM8.5 11h7M8.5 15h7"/></svg>',
 pepper:'<svg class="ci" viewBox="0 0 24 24" fill="currentColor"><path d="M14 7c.4-2 2-3.3 4-3.3.4 0 .5.5.2.7-.8.5-1.2 1.1-1.3 2 .7.5 1.1 1.3 1.1 2.3 0 5.5-4.5 11-10.5 11A4.5 4.5 0 0 1 3 15.2c0-.5.6-.7 1-.4a3 3 0 0 0 4.3-.8C6 13.4 5 11.8 5 10c0-.4.5-.6.8-.3A5 5 0 0 0 14 7z"/></svg>'};
function schName(t){t=t||'Class';var hot=/\uD83C\uDF36/.test(t);return esc(t.replace(/\s*\uD83C\uDF36\uFE0F?/g,''))+(hot?' '+IC.pepper:'');}

var CATS=['Music','Nightlife','Arts','Theater','Comedy','Sports','Food','Festival','Family','Film','Wellness'];
var MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
var WD=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
var all=[],active=new Set(),view=(function(){try{return localStorage.getItem('mq_view2')||'week';}catch(e){return'week';}})(),curMonth=null,selDay=null,loc='mine',weekOffset=0,wkSel=null;
function evMins(t){var p=parseTime(t);return p?p.h*60+p.m:9999;}
function shortTitle(t){t=(t||'').replace(/\s*🌶️?/g,'');var i=t.lastIndexOf(' · ');return i>=0?t.slice(i+3):t;}
function esc(s){return (s||'').replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function parseD(s){var p=(s||'').split('-');return new Date(+p[0],+p[1]-1,+p[2]);}
function chipTime(t){var m=(t||'').match(/(\d{1,2})(?::(\d{2}))?\s*([ap])/i);if(!m)return '';var mm=(m[2]&&m[2]!=='00')?':'+m[2]:'';return m[1]+mm+m[3].toLowerCase();}
function matchLoc(e){return loc==='all'||(loc==='mine'?!!e.mine:nearMe(e));}
function filtered(){return all.filter(function(e){return (!active.size||active.has(e.category))&&matchLoc(e);});}
function chips(){
 var c=document.getElementById('chips');
 c.innerHTML='<span class="chip'+(!active.size?' on':'')+'" data-c="">All</span>'+
  CATS.map(function(k){return '<span class="chip'+(active.has(k)?' on':'')+'" data-c="'+k+'">'+catIcon(k)+' '+k+'</span>';}).join('');
}
function evCard(e){
 var d=parseD(e.date);
 return '<div class="ev'+(e.mine?' mine':'')+'" data-open="'+e._i+'" role="button" tabindex="0">'
  +'<div class="dte"><div class="mo">'+MON[d.getMonth()]+'</div><div class="dy">'+d.getDate()+'</div><div class="wd">'+WD[d.getDay()]+'</div></div>'
  +'<div class="body"><div class="t">'+schName(e.title)+'</div>'
  +'<div class="meta"><span class="cat" style="background:linear-gradient(135deg,'+(CATCOLOR[e.category]||'#ff5c8a')+',#a855f7)">'+catIcon(e.category)+' '+esc(e.category)+'</span>'
  +(e.mine?'<span class="mine-tag">'+(e.recurring?'★ Mine · weekly':'★ Mine')+'</span>':'')
  +(nearMe(e)&&!e.mine?'<span class="near-tag">★ Near you</span>':'')
  +(e.time?'<span>'+IC.clock+' '+esc(e.time)+'</span>':'')
  +(e.venue?'<span>'+IC.pin+' '+esc(e.venue)+(e.neighborhood?', '+esc(e.neighborhood):(e.borough?', '+esc(e.borough):''))+'</span>':'')
  +(e.price?'<span>'+IC.ticket+' '+esc(e.price)+'</span>':'')
  +(e.source&&!e.mine?'<span class="src">via '+esc(e.source)+'</span>':'')+'</div>'
  +(e.blurb?'<p class="bl">'+esc(e.blurb)+'</p>':'')+'</div>'
  +'<div class="acts">'
   +(e.mine?'<button class="act del" data-rm="'+e._i+'" title="Remove from my calendar">✕</button>'
           :'<button class="act add" data-add="'+e._i+'" title="Add to my calendar">'+IC.cal+'</button>')
  +'</div></div>';
}
function openEvent(e){
 if(!e)return;var d=parseD(e.date);var m=document.getElementById('evModal');
 var place=[e.venue,e.neighborhood||e.borough].filter(Boolean).join(', ');
 m.querySelector('.evm-card').innerHTML=
  '<div class="evm-top" style="background:linear-gradient(135deg,'+(CATCOLOR[e.category]||'#ff5c8a')+',#a855f7)"></div>'
  +'<button class="evm-x" data-close title="Close">✕</button>'
  +'<div class="evm-body">'
   +'<div class="evm-cat">'+catIcon(e.category)+' '+esc(e.category)
     +(e.mine?' · ★ Mine'+(e.recurring?' · weekly':''):'')+(nearMe(e)&&!e.mine?' · ★ Near you':'')+(e.source&&!e.mine?' · via '+esc(e.source):'')+'</div>'
   +'<h2 class="evm-title">'+schName(e.title)+'</h2>'
   +'<div class="evm-when">'+WD[d.getDay()]+', '+MON[d.getMonth()]+' '+d.getDate()+(e.time?' · '+esc(e.time):'')+'</div>'
   +(place?'<div class="evm-row">'+IC.pin+' '+esc(place)+'</div>':'')
   +(e.price?'<div class="evm-row">'+IC.ticket+' '+esc(e.price)+'</div>':'')
   +(e.blurb?'<p class="evm-blurb">'+esc(e.blurb)+'</p>':'')
   +(e.url?'<div class="evm-link">'+IC.link+' <a href="'+esc(e.url)+'" target="_blank" rel="noopener">'+esc(e.url.replace(/^https?:\/\//,'').slice(0,54))+'…</a></div>':'')
   +'<div class="evm-actions">'
    +(e.url?'<a class="evm-btn primary" href="'+esc(e.url)+'" target="_blank" rel="noopener">'+IC.ticket+' Open / Tickets</a>':'')
    +(e.mine
       ?('<button class="evm-btn danger" data-mrm>✕ Remove from my calendar</button>'
         +(e.recurring?'<button class="evm-btn danger" data-mrmall>Remove the whole series</button>':''))
       :'<button class="evm-btn primary" data-madd>'+IC.cal+' Add to my calendar</button>')
   +'</div>'
  +'</div>';
 m._ev=e;m.hidden=false;
}
function pad(n){return (n<10?'0':'')+n;}
function parseTime(t){var m=(t||'').match(/(\d{1,2}):(\d{2})\s*([ap])m/i);if(!m)return null;var h=(+m[1])%12;if(/p/i.test(m[3]))h+=12;return {h:h,m:+m[2]};}
function icsEsc(s){return (s||'').replace(/([,;\\])/g,'\\$1').replace(/\n/g,'\\n');}
function icsFor(e){
 var p=(e.date||'').split('-'),y=p[0],mo=p[1],da=p[2],t=parseTime(e.time);
 var uid=((e.id||('e'+(e._i||0)))+'-'+(e.date||''))+'@marquee';
 var L=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Marquee//NYC//EN','BEGIN:VEVENT','UID:'+uid];
 if(!t){L.push('DTSTART;VALUE=DATE:'+y+mo+da);}
 else{L.push('DTSTART:'+y+mo+da+'T'+pad(t.h)+pad(t.m)+'00');L.push('DTEND:'+y+mo+da+'T'+pad((t.h+2)%24)+pad(t.m)+'00');}
 L.push('SUMMARY:'+icsEsc(e.title));
 if(e.venue)L.push('LOCATION:'+icsEsc([e.venue,e.neighborhood].filter(Boolean).join(', ')));
 var desc=[e.blurb,e.url].filter(Boolean).join('\\n');if(desc)L.push('DESCRIPTION:'+icsEsc(desc));
 if(e.url)L.push('URL:'+e.url);
 L.push('END:VEVENT','END:VCALENDAR');return L.join('\r\n');
}
function downloadICS(e){
 var blob=new Blob([icsFor(e)],{type:'text/calendar'});var a=document.createElement('a');
 a.href=URL.createObjectURL(blob);a.download=((e.title||'event').replace(/[^\w]+/g,'-').slice(0,40))+'.ics';
 document.body.appendChild(a);a.click();setTimeout(function(){a.remove();URL.revokeObjectURL(a.href);},600);
}
function saveMine(e){
 var body={title:e.title,category:e.category,time:e.time,venue:e.venue,neighborhood:e.neighborhood,
  borough:e.borough,near_home:!!e.near_home,url:e.url,blurb:e.blurb,price:e.price,date:e.date};
 fetch('api/personal/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
  .then(function(r){return r.json();}).then(function(){load(false);});
}
function renderList(){
 var evs=filtered(),box=document.getElementById('list');
 var mineBar=(loc==='mine')?('<div class="minebar"><div><b>Your regulars &amp; saved events</b><span>Pull real class times &amp; sessions straight from the source.</span></div><button class="scanbtn">⟳ Scan for real times</button></div>'):'';
 if(!evs.length){box.innerHTML=mineBar+'<div class="empty">'+(loc==='mine'?'Nothing saved yet — tap ＋ on any event, or use <b>+ Add event</b>.':'No events in that filter yet.')+'</div>';return;}
 var byDay={},order=[];
 evs.forEach(function(e){if(!byDay[e.date]){byDay[e.date]=[];order.push(e.date);}byDay[e.date].push(e);});
 box.innerHTML=mineBar+order.map(function(dt){
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
 var MAXCHIP=3;
 for(var day=1;day<=days;day++){
  var ds=byDay[day]||[],isT=(y+'-'+m+'-'+day)===tKey,sel=(selDay===day);
  var chips=ds.slice(0,MAXCHIP).map(function(e){
   var c=CATCOLOR[e.category]||'#ff5c8a',tt=chipTime(e.time);
   return '<span class="evchip'+(e.mine?' mine':'')+'" style="--c:'+c+'" data-open="'+e._i+'" title="'+esc((tt?tt+' ':'')+e.title)+'">'
    +(tt?'<span class="ct">'+tt+'</span>':'')+esc(e.title)+'</span>';
  }).join('');
  cells+='<div class="cell'+(ds.length?' has':'')+(isT?' today':'')+(sel?' sel':'')+'" data-day="'+day+'">'
   +'<div class="d">'+day+'</div>'
   +'<div class="cevs">'+chips+'</div>'
   +(ds.length>MAXCHIP?'<div class="more">+'+(ds.length-MAXCHIP)+' more</div>':'')+'</div>';
 }
 document.getElementById('cells').innerHTML=cells;
 // selected day's events under the calendar (reuse list area)
 if(selDay&&byDay[selDay]){
  document.getElementById('list').innerHTML='<div class="day-h">'+MON[m]+' '+selDay+'<span class="ln"></span></div>'+byDay[selDay].map(evCard).join('');
 }else{renderList();}
}
function todayStr(){var d=new Date();return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate());}
function renderWeek(){
 var box=document.getElementById('list'),evs=filtered(),byDate={};
 evs.forEach(function(e){(byDate[e.date]=byDate[e.date]||[]).push(e);});
 var base=new Date(),tStr=todayStr(),nowD=new Date();
 var start=new Date(base.getFullYear(),base.getMonth(),base.getDate()-base.getDay()+weekOffset*7);
 var days=[],dks=[];
 for(var i=0;i<7;i++){var d=new Date(start.getFullYear(),start.getMonth(),start.getDate()+i);days.push(d);dks.push(d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate()));}
 if(!wkSel||dks.indexOf(wkSel)<0)wkSel=(dks.indexOf(tStr)>=0?tStr:dks[0]);
 // tight hour window around this week's events -> short, not a 24h scroll
 var wm=[];evs.forEach(function(e){if(dks.indexOf(e.date)>=0){var m=evMins(e.time);if(m<9999)wm.push(m);}});
 var sH=9,eH=21;
 if(wm.length){sH=Math.max(5,Math.floor(Math.min.apply(null,wm)/60));eH=Math.min(24,Math.ceil(Math.max.apply(null,wm)/60)+1);if(eH-sH<5)eH=Math.min(24,sH+6);}
 var HR=34,gridH=(eH-sH)*HR;
 var head='<div class="wk-head"><button class="cal-nav" id="wpm">‹</button><b>'+MON[days[0].getMonth()]+' '+days[0].getDate()+' – '+MON[days[6].getMonth()]+' '+days[6].getDate()+'</b><button class="cal-nav" id="wnm">›</button></div>';
 var hdr='<div class="wk2-hdr"><div class="wk2-gutter"></div>'+days.map(function(d,i){var isT=dks[i]===tStr,sl=dks[i]===wkSel;
   return '<button class="wk2-dcol'+(isT?' today':'')+(sl?' sel':'')+'" data-wd="'+dks[i]+'"><span class="wk2-dow">'+WD[d.getDay()]+'</span><span class="wk2-dnum">'+d.getDate()+'</span></button>';}).join('')+'</div>';
 var times='';for(var h=sH;h<eH;h++){var lab=(h===0?'12a':h<12?h+'a':h===12?'12p':(h-12)+'p');times+='<div class="wk2-hr" style="height:'+HR+'px">'+lab+'</div>';}
 var cols=days.map(function(d,i){var k=dks[i],isT=k===tStr;
   var ls=(byDate[k]||[]).slice().sort(function(a,b){return evMins(a.time)-evMins(b.time);});
   var laneEnd=[],items=ls.map(function(e){var s=evMins(e.time);if(s>=9999)s=sH*60;var en=s+55,l=0;
     while(l<laneEnd.length&&laneEnd[l]>s)l++;laneEnd[l]=en;return {e:e,s:s,en:en,lane:l};});
   var nL=Math.max(1,laneEnd.length);
   var blocks=items.map(function(o){var top=Math.max(0,(o.s-sH*60)/60*HR),hgt=Math.max(15,(o.en-o.s)/60*HR-2);
     var w=100/nL,left=o.lane*w;
     return '<div class="wk2-ev" data-open="'+o.e._i+'" style="top:'+top+'px;height:'+hgt+'px;left:'+left+'%;width:calc('+w+'% - 2px)"><b>'+esc(chipTime(o.e.time))+'</b>'+esc(shortTitle(o.e.title))+'</div>';
   }).join('');
   return '<div class="wk2-col'+(isT?' today':'')+'">'+blocks+'</div>';
 }).join('');
 var now='';if(dks.indexOf(tStr)>=0){var nm=nowD.getHours()*60+nowD.getMinutes();if(nm>=sH*60&&nm<=eH*60)now='<div class="wk2-now" style="top:'+((nm-sH*60)/60*HR)+'px"></div>';}
 var grid='<div class="wk2"><div class="wk2-grid"><div class="wk2-gutter2">'+times+'</div><div class="wk2-cols" style="height:'+gridH+'px;background-size:100% '+HR+'px">'+cols+now+'</div></div></div>';
 var list='';
 days.forEach(function(d,i){var k=dks[i],evsD=(byDate[k]||[]).slice().sort(function(a,b){return evMins(a.time)-evMins(b.time);});
   if(!evsD.length)return;
   list+='<div class="day-h'+(k===tStr?' today':'')+'" id="d-'+k+'" style="margin-top:14px">'+WD[d.getDay()]+', '+MON[d.getMonth()]+' '+d.getDate()+(k===tStr?' · Today':'')+'<span class="ln"></span></div>'+evsD.map(evCard).join('');
 });
 if(!list)list='<div class="empty" style="margin-top:16px">Nothing in your calendar this week — tap '+IC.cal+' on any event (try <b>All NYC</b>) to add it.</div>';
 var bar=(loc==='mine')?'<div class="minebar"><div><b>Your week</b><span>Only what you\'ve added. Tap '+IC.cal+' on any event (try <b>All NYC</b>) to add it.</span></div><button class="scanbtn">⟳ Scan for real times</button></div>':'';
 box.innerHTML=bar+head+hdr+grid+list;
}
function render(){chips();document.getElementById('calWrap').hidden=(view!=='cal');if(view==='cal')renderCal();else if(view==='week')renderWeek();else renderList();}
function load(force){
 var r=document.getElementById('refresh');if(force)r.classList.add('spin');
 fetch('api/events'+(force?'?force=1':''),{cache:'no-store'}).then(function(x){return x.json();}).then(function(d){
  all=d.events||[];
  all.forEach(function(e,i){e._i=i;});
  if(d.home)SERVER_HOME=d.home;document.getElementById('homePill').innerHTML=IC.pin+' '+esc(homeLabel());
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
 try{localStorage.setItem('mq_view2',view);}catch(e){}
 Array.prototype.forEach.call(this.children,function(x){x.classList.toggle('on',x===b);});
 selDay=null;render();
});
(function(){try{var vv=document.getElementById('views');Array.prototype.forEach.call(vv.children,function(x){x.classList.toggle('on',x.getAttribute('data-v')===view);});}catch(e){}})();
document.getElementById('loc').addEventListener('click',function(ev){
 var b=ev.target.closest('button');if(!b)return;loc=b.getAttribute('data-l');
 Array.prototype.forEach.call(this.children,function(x){x.classList.toggle('on',x===b);});
 selDay=null;render();
 if(loc==='near'&&!getHome()){var hm=document.getElementById('homeModal');if(hm)hm.hidden=false;}
});
document.getElementById('cells').addEventListener('click',function(ev){
 var chip=ev.target.closest('.evchip');
 if(chip){openEvent(all[+chip.getAttribute('data-open')]);return;}
 var c=ev.target.closest('.cell.has');if(!c)return;var day=+c.getAttribute('data-day');
 selDay=(selDay===day)?null:day;renderCal();
});
document.getElementById('pm').onclick=function(){curMonth=new Date(curMonth.getFullYear(),curMonth.getMonth()-1,1);selDay=null;renderCal();};
document.getElementById('nm').onclick=function(){curMonth=new Date(curMonth.getFullYear(),curMonth.getMonth()+1,1);selDay=null;renderCal();};
document.getElementById('refresh').onclick=function(){load(true);};
// ---- add-event modal ----
var modal=document.getElementById('addModal'),selWd=new Set();
(function initForm(){
 var cat=document.getElementById('f_cat');
 cat.innerHTML=CATS.map(function(k){return '<option value="'+k+'">'+k+'</option>';}).join('');
 cat.value='Wellness';
 var wd=document.getElementById('f_wdays');
 wd.innerHTML=WD.map(function(w,i){return '<button type="button" class="wday" data-wd="'+i+'">'+w[0]+'</button>';}).join('');
 wd.addEventListener('click',function(ev){var b=ev.target.closest('.wday');if(!b)return;var i=+b.getAttribute('data-wd');
  if(selWd.has(i)){selWd.delete(i);b.classList.remove('on');}else{selWd.add(i);b.classList.add('on');}});
})();
function openModal(){modal.hidden=false;}
function closeModal(){modal.hidden=true;}
var SRC_CACHE=null,SRC_OPEN=null,SRC_EV={};
function srcTag(active){return '<span class="app-tag '+(active?'public':'soon')+'">'+(active?'Active':'Standby')+'</span>';}
function agoMs(ms){if(!ms)return 'never';var s=Math.max(0,(Date.now()-ms)/1000);if(s<90)return 'just now';var m=s/60;if(m<60)return Math.round(m)+'m ago';var h=m/60;if(h<24)return Math.round(h)+'h ago';return Math.round(h/24)+'d ago';}
function niceShort(d){var x=parseD(d);return MON[x.getMonth()]+' '+x.getDate();}
function srcCard(a){
 var ico='<span class="app-ico" style="background:linear-gradient(135deg,'+(a.c0||'#ff5c8a')+','+(a.c1||'#a855f7')+')">'+esc((a.name||'?')[0])+'</span>';
 var meta=esc(a.category||'')+' · '+(a.count||0)+' listing'+(a.count===1?'':'s')+' · updated '+agoMs(a.last_update);
 var open=SRC_OPEN===a.key,det='';
 if(open){var list=SRC_EV[a.key];
  if(!list)det='<div class="app-d" style="padding:10px 12px">Loading…</div>';
  else if(!list.length)det='<div class="app-d" style="padding:10px 12px">No listings ingested yet.</div>';
  else det=list.map(function(e){var tm=(e.time&&e.time!=='None')?' · '+esc(e.time):'';return '<div class="src-ev"><span class="src-ev-d">'+esc(niceShort(e.date))+tm+'</span><span class="src-ev-t">'+esc(e.title||'')+'</span></div>';}).join('')
     +(a.url?'<a class="src-visit" href="'+esc(a.url)+'" target="_blank" rel="noopener">'+IC.link+' Open '+esc(a.name)+'</a>':'');
  det='<div class="src-det">'+det+'</div>';}
 return '<div class="src-wrap'+(open?' open':'')+'"><button class="app-card src-card" data-skey="'+esc(a.key)+'">'+ico
   +'<div class="app-main"><div class="app-n">'+esc(a.name)+srcTag(a.active)+'</div><div class="app-d">'+meta+'</div></div>'
   +'<span class="src-chev">'+(open?'▾':'›')+'</span></button>'+det+'</div>';
}
async function renderApps(){
 var g=document.getElementById('appsGrid');
 document.getElementById('appsModal').hidden=false;
 if(!SRC_CACHE){
  g.innerHTML='<div class="app-d" style="padding:18px 4px;text-align:center">Loading sources…</div>';
  try{SRC_CACHE=(await (await fetch('api/sources')).json()).sources||[];}catch(e){SRC_CACHE=[];}
 }
 g.innerHTML=SRC_CACHE.map(srcCard).join('');
}
document.getElementById('appsGrid').addEventListener('click',function(ev){
 var c=ev.target.closest('.src-card');if(!c)return;
 var k=c.getAttribute('data-skey');
 if(SRC_OPEN===k){SRC_OPEN=null;renderApps();return;}
 SRC_OPEN=k;
 if(!SRC_EV[k]){renderApps();fetch('api/source?key='+encodeURIComponent(k)).then(function(r){return r.json();}).then(function(j){SRC_EV[k]=j.events||[];renderApps();}).catch(function(){SRC_EV[k]=[];renderApps();});}
 else renderApps();
});
document.getElementById('addBtn').onclick=openModal;
(function(){var hm=document.getElementById('homeModal');
 document.getElementById('homePill').onclick=function(){var h=getHome()||{};document.getElementById('home_nb').value=h.neighborhood||'';document.getElementById('home_boro').value=h.borough||'';hm.hidden=false;};
 document.getElementById('home_cancel').onclick=function(){hm.hidden=true;};
 hm.addEventListener('click',function(e){if(e.target===hm)hm.hidden=true;});
 document.getElementById('home_save').onclick=function(){var nb=document.getElementById('home_nb').value.trim(),bo=document.getElementById('home_boro').value;
  try{localStorage.setItem('mq_home',JSON.stringify({neighborhood:nb,borough:bo,label:[nb,bo].filter(Boolean).join(', ')}));}catch(e){}
  document.getElementById('homePill').innerHTML=IC.pin+' '+esc(homeLabel());hm.hidden=true;load(false);};
})();
document.getElementById('f_cancel').onclick=closeModal;
(function(){
 var sm=document.getElementById('subModal');
 var httpsUrl=location.protocol+'//'+location.host+'/calendar.ics';
 document.getElementById('sub_url').value=httpsUrl;
 document.getElementById('sub_webcal').href='webcal://'+location.host+'/calendar.ics';
 document.getElementById('subBtn').onclick=function(){sm.hidden=false;};
 document.getElementById('appsBtn').onclick=renderApps;
 var appsM=document.getElementById('appsModal');
 appsM.addEventListener('click',function(ev){if(ev.target===appsM||ev.target.closest('[data-close]'))appsM.hidden=true;});
 document.getElementById('sub_cancel').onclick=function(){sm.hidden=true;};
 sm.addEventListener('click',function(ev){if(ev.target===sm)sm.hidden=true;});
 document.getElementById('sub_copy').onclick=function(){
  var i=document.getElementById('sub_url'),b=this;i.select();
  var ok=function(){b.textContent='Copied ✓';setTimeout(function(){b.textContent='Copy';},1400);};
  if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(i.value).then(ok,function(){try{document.execCommand('copy');ok();}catch(e){}});}
  else{try{document.execCommand('copy');ok();}catch(e){}}
 };
})();
modal.addEventListener('click',function(ev){if(ev.target===modal)closeModal();});
document.getElementById('f_save').onclick=function(){
 var title=document.getElementById('f_title').value.trim();if(!title){document.getElementById('f_title').focus();return;}
 var body={title:title,category:document.getElementById('f_cat').value,
  time:document.getElementById('f_time').value.trim(),venue:document.getElementById('f_venue').value.trim(),
  url:document.getElementById('f_url').value.trim(),near_home:document.getElementById('f_near').checked};
 if(selWd.size)body.weekdays=Array.from(selWd);else body.date=document.getElementById('f_date').value.trim();
 if(!body.weekdays&&!/^\d{4}-\d{2}-\d{2}$/.test(body.date||'')){alert('Pick weekdays to repeat, or a one-time date (YYYY-MM-DD).');return;}
 fetch('api/personal/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
  .then(function(r){return r.json();}).then(function(d){
   if(!d.ok){alert(d.error||'Could not add');return;}
   closeModal();
   ['f_title','f_time','f_venue','f_url','f_date'].forEach(function(id){document.getElementById(id).value='';});
   selWd.clear();Array.prototype.forEach.call(document.querySelectorAll('.wday'),function(x){x.classList.remove('on');});
   load(false);
  }).catch(function(){alert('Could not add');});
};
// card: quick action buttons, else tap opens the detail modal
document.getElementById('list').addEventListener('click',function(ev){
 var we=ev.target.closest('.wk2-ev');if(we){openEvent(all[+we.getAttribute('data-open')]);return;}
 var dd=ev.target.closest('.wk2-dcol');if(dd){wkSel=dd.getAttribute('data-wd');renderWeek();var s=document.getElementById('d-'+wkSel);if(s)s.scrollIntoView({behavior:'smooth',block:'start'});return;}
 var wn=ev.target.closest('#wpm,#wnm');if(wn){weekOffset+=(wn.id==='wnm'?1:-1);renderWeek();return;}
 var b=ev.target.closest('.act, .scanbtn');
 if(b){ev.preventDefault();ev.stopPropagation();
  if(b.classList.contains('scanbtn')){scanRegulars(b);return;}
  if(b.hasAttribute('data-add')){confirmEvent(all[+b.getAttribute('data-add')]);return;}
  if(b.hasAttribute('data-rm')){removeOccurrence(all[+b.getAttribute('data-rm')]);return;}
  return;}
 var card=ev.target.closest('.ev[data-open]');if(card)openEvent(all[+card.getAttribute('data-open')]);
});
// add an event to YOUR Marquee calendar (no OS popup). A regular's class ->
// confirm that occurrence; a discovered NYC event -> save it as a personal event.
function confirmEvent(e){
 if(!e)return;
 if(e.pid){
  fetch('api/personal/select',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:e.pid,date:e.date,time:e.time})}).then(function(){load(false);});
 } else {
  var body={title:e.title,category:e.category,time:e.time,venue:e.venue,neighborhood:e.neighborhood,borough:e.borough,near_home:!!e.near_home,url:e.url,blurb:e.blurb,price:e.price,date:e.date};
  fetch('api/personal/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(function(){load(false);});
 }
}
// remove ONE occurrence from your calendar (a class/recurring -> hide just it; one-off -> delete)
function removeOccurrence(e){
 if(!e||!e.pid)return;
 if(e.scanned||e.recurring){
  fetch('api/personal/exclude',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:e.pid,date:e.date,time:e.time})}).then(function(){load(false);});
 } else {
  fetch('api/personal/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:e.pid})}).then(function(){load(false);});
 }
}
function removeSeries(e){
 if(!e||!e.pid)return;
 if(!confirm('Remove the WHOLE series ('+esc(e.title)+') from your calendar?'))return;
 fetch('api/personal/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:e.pid})}).then(function(){load(false);});
}
// event detail modal: actions
var evModal=document.getElementById('evModal');
function closeEv(){evModal.hidden=true;evModal._ev=null;evModal._sched=null;}
// browse a regular's full scraped schedule and pick specific classes
function openSchedule(pid,title){
 fetch('api/personal/sessions?id='+encodeURIComponent(pid),{cache:'no-store'}).then(function(r){return r.json();}).then(function(d){
  var byDay={},order=[];
  (d.sessions||[]).forEach(function(s){if(!byDay[s.date]){byDay[s.date]=[];order.push(s.date);}byDay[s.date].push(s);});
  var body=order.map(function(dt){
   var p=dt.split('-'),dd=new Date(+p[0],+p[1]-1,+p[2]);
   return '<div class="sch-day">'+WD[dd.getDay()]+', '+MON[dd.getMonth()]+' '+dd.getDate()+'</div>'
    +byDay[dt].map(function(s){
     var on=s.selected;
     return '<div class="sch-row"><div class="sch-t">'+esc(s.time||'')+'</div><div class="sch-n">'+schName(s.title)+'</div>'
      +'<button class="sch-go'+(on?' on':'')+'" data-go="'+esc(dt)+'~'+esc(s.time||'')+'"'+(s.standing?' disabled title="your standing class"':'')+'>'+(on?'✓ Going':'+ Add')+'</button></div>';
    }).join('');
  }).join('') || '<div class="empty">No upcoming classes found — try ⟳ Scan.</div>';
  evModal.querySelector('.evm-card').innerHTML=
   '<div class="evm-top" style="background:linear-gradient(135deg,#34d399,#a855f7)"></div>'
   +'<button class="evm-x" data-close>✕</button>'
   +'<div class="evm-body"><div class="evm-cat">'+IC.list+' Full schedule</div><h2 class="evm-title">'+esc(title)+'</h2>'
   +'<p class="evm-blurb">Tap <b>+ Add</b> on any class to put it in your calendar. Your Thu/Sat 7pm is already in.</p>'
   +'<div class="sch-list">'+body+'</div></div>';
  evModal._sched=pid;evModal.hidden=false;
 });
}
evModal.addEventListener('click',function(ev){
 if(ev.target===evModal||ev.target.closest('[data-close]')){closeEv();return;}
 // schedule-browser toggles
 var go=ev.target.closest('[data-go]');
 if(go&&evModal._sched){var parts=go.getAttribute('data-go').split('~');var dt=parts[0],tm=parts.slice(1).join('~');
  var adding=!go.classList.contains('on');
  fetch('api/personal/'+(adding?'select':'exclude'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:evModal._sched,date:dt,time:tm})})
   .then(function(){go.classList.toggle('on',adding);go.textContent=adding?'✓ Going':'+ Add';load(false);});
  return;}
 var e=evModal._ev;if(!e)return;
 if(ev.target.closest('[data-madd]')){confirmEvent(e);closeEv();return;}
 var mb=ev.target.closest('[data-mbrowse]');if(mb){openSchedule(mb.getAttribute('data-mbrowse'),e.title);return;}
 if(ev.target.closest('[data-mrm]')){removeOccurrence(e);closeEv();return;}
 if(ev.target.closest('[data-mrmall]')){removeSeries(e);closeEv();return;}
});
document.addEventListener('keydown',function(e){if(e.key==='Escape'&&!evModal.hidden)closeEv();});
// scan all scannable regulars via the Firecrawl agent, then reload
function scanRegulars(btn){
 btn.textContent='⟳ Scanning…';btn.disabled=true;
 fetch('api/personal',{cache:'no-store'}).then(function(r){return r.json();}).then(function(d){
  var regs=(d.personal||[]).filter(function(r){return r.scan_url;});
  if(!regs.length){btn.textContent='No scannable regulars';return;}
  return Promise.all(regs.map(function(r){
   return fetch('api/personal/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:r.id})}).then(function(x){return x.json();});
  })).then(function(res){
   var n=res.reduce(function(a,x){return a+(x.count||0);},0);
   btn.textContent='✓ Updated '+n+' real sessions';setTimeout(function(){load(false);},900);
  });
 }).catch(function(){btn.textContent='Scan failed';btn.disabled=false;});
}
// ---- Shared widgets: To-do + Daily report (read/write Dash, same account) ----
(function(){
  var DASH='https://dash.bedrock.casa';
  var rp=document.getElementById('mqReport');
  if(rp){fetch(DASH+'/api/report-latest',{cache:'no-store'}).then(function(r){return r.json();}).then(function(d){
    var r=d&&d.report;if(!r)return;
    document.getElementById('mqRpTitle').textContent=r.title||'Daily report';
    document.getElementById('mqRpDate').textContent=r.date||'';
    document.getElementById('mqRpBody').textContent=r.text||'';
    rp.hidden=false;
  }).catch(function(){});}
  var box=document.getElementById('mqTodo');if(!box)return;
  var list=document.getElementById('mqTdList'),input=document.getElementById('mqTdInput'),
      form=document.getElementById('mqTdForm'),cnt=document.getElementById('mqTdCount');
  var todos=[],_t=null;
  function push(){clearTimeout(_t);_t=setTimeout(function(){
    fetch(DASH+'/api/todo',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({todos:todos})}).catch(function(){});
  },300);}
  function render(){
    list.innerHTML='';
    if(!todos.length){var e=document.createElement('li');e.className='mqtd-empty';e.textContent='Nothing yet — add a task.';list.appendChild(e);}
    todos.forEach(function(t,i){
      var li=document.createElement('li');li.className='mqtd-item'+(t.done?' done':'');
      li.onclick=function(){t.done=!t.done;push();render();};
      var bx=document.createElement('span');bx.className='bx';bx.textContent=t.done?'✓':'';
      var tx=document.createElement('span');tx.className='tx';tx.textContent=t.text;
      var rm=document.createElement('button');rm.className='rm';rm.innerHTML='✕';rm.onclick=function(ev){ev.stopPropagation();todos.splice(i,1);push();render();};
      li.appendChild(bx);li.appendChild(tx);li.appendChild(rm);list.appendChild(li);
    });
    var done=todos.filter(function(t){return t.done;}).length;
    cnt.textContent=todos.length?(done+'/'+todos.length):'';
  }
  form.onsubmit=function(ev){ev.preventDefault();var v=input.value.trim();if(!v)return;todos.push({text:v,done:false});input.value='';push();render();};
  fetch(DASH+'/api/todo',{cache:'no-store'}).then(function(r){return r.json();}).then(function(d){
    todos=(d&&d.todos)||[];box.hidden=false;render();
  }).catch(function(){box.hidden=false;render();});
})();
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
        elif p == "/admin":
            self._send(ADMIN_PAGE.replace("__DIAGRAM__", ADMIN_DIAGRAM), "text/html; charset=utf-8")
        elif p == "/api/admin":
            self._send(json.dumps(admin_data()))
        elif p == "/api/sources":
            self._send(json.dumps({"sources": public_sources()}))
        elif p == "/api/source":
            key = ""
            for kv in q.split("&"):
                if kv.startswith("key="):
                    key = urllib.parse.unquote(kv[4:])
            self._send(json.dumps({"events": source_events(key)}))
        elif p == "/favicon.svg":
            self._send(FAVICON, "image/svg+xml")
        elif p == "/api/events":
            store = get_events(force=("force=1" in q))
            today = time.strftime("%Y-%m-%d")
            merged = [e for e in (store.get("events") or [])] + expand_personal()
            merged = [e for e in merged if e.get("date", "") >= today]
            merged.sort(key=lambda e: (e["date"], _mins(e.get("time", ""))))
            self._send(json.dumps({"fetched_at": store.get("fetched_at", 0),
                                   "events": merged, "home": HOME,
                                   "categories": CATEGORIES}))
        elif p in ("/calendar.ics", "/api/calendar.ics"):
            self._send(build_ics(), "text/calendar; charset=utf-8")
        elif p == "/api/personal":
            self._send(json.dumps({"personal": load_personal()}))
        elif p == "/api/personal/sessions":
            pid = (q.split("id=", 1)[1].split("&")[0] if "id=" in q else "")
            today = time.strftime("%Y-%m-%d")
            rec = next((r for r in load_personal() if r.get("id") == pid), None)
            out = []
            if rec:
                sel = set(rec.get("selected") or [])
                wd = set(rec.get("weekdays") or [])
                for s in (rec.get("sessions") or []):
                    d = s.get("date", "")
                    if d < today:
                        continue
                    st = _start_time(s.get("time", ""))
                    key = d + "|" + st
                    try:
                        dd = date.fromisoformat(d)
                        standing = rec.get("recurring") and ((dd.weekday() + 1) % 7 in wd) and st == _start_time(rec.get("time", ""))
                    except Exception:
                        standing = False
                    out.append({"date": d, "time": s.get("time", ""), "title": s.get("title", ""),
                                "url": s.get("url", ""), "selected": (key in sel) or bool(standing),
                                "standing": bool(standing)})
                out.sort(key=lambda s: (s["date"], _mins(s.get("time", ""))))
            self._send(json.dumps({"id": pid, "title": (rec or {}).get("title", ""),
                                   "sessions": out[:120]}))
        elif p == "/api/widget":
            store = load_store()
            if is_stale(store) or not store.get("events"):
                get_events(force=False)
                store = load_store()
            today = time.strftime("%Y-%m-%d")
            evs = [e for e in ((store.get("events") or []) + expand_personal())
                   if e.get("date", "") >= today]
            evs.sort(key=lambda e: (e["date"], _mins(e.get("time", ""))))
            # bubble near-home events to the top of the widget, keeping date order
            near = [e for e in evs if e.get("near_home")]
            rest = [e for e in evs if not e.get("near_home")]
            picked = (near + rest)[:6]
            self._send(json.dumps({"events": picked, "home": HOME,
                                   "fetched_at": store.get("fetched_at", 0)}))
        elif p in ("/health", "/healthz"):
            s = load_store()
            try:
                cached = len([f for f in os.listdir(CACHE_DIR) if f.endswith(".json")])
            except Exception:
                cached = 0
            self._send(json.dumps({"ok": True, "events": len(s.get("events") or []),
                                   "fetched_at": s.get("fetched_at", 0),
                                   "cached_pages": cached}))
        else:
            self._send("not found", "text/plain", 404)

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def do_POST(self):
        p = self.path.split("?", 1)[0]
        if p == "/api/refresh":
            refresh_async()
            self._send(json.dumps({"ok": True, "refreshing": True}))
        elif p == "/api/personal/add":
            b = self._body()
            title = (b.get("title") or "").strip()
            if not title:
                self._send(json.dumps({"ok": False, "error": "title required"}), code=400); return
            rec = {"id": uuid.uuid4().hex[:12], "title": title[:140],
                   "time": (b.get("time") or "").strip()[:40],
                   "venue": (b.get("venue") or "").strip()[:140],
                   "neighborhood": (b.get("neighborhood") or "").strip()[:80],
                   "borough": _norm_boro(b.get("borough")),
                   "near_home": bool(b.get("near_home")),
                   "category": _norm_cat(b.get("category")),
                   "price": (b.get("price") or "").strip()[:60],
                   "url": (b.get("url") or "").strip()[:400],
                   "blurb": (b.get("blurb") or "").strip()[:220]}
            wkd = b.get("weekdays")
            if isinstance(wkd, list) and wkd:
                rec["recurring"] = True
                rec["weekdays"] = sorted({int(x) for x in wkd if 0 <= int(x) <= 6})
            else:
                d = (b.get("date") or "").strip()
                if not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
                    self._send(json.dumps({"ok": False, "error": "date or weekdays required"}), code=400); return
                rec["date"] = d
            recs = load_personal(); recs.append(rec); save_personal(recs)
            self._send(json.dumps({"ok": True, "id": rec["id"]}))
        elif p == "/api/personal/delete":
            pid = (self._body().get("id") or "").strip()
            recs = [r for r in load_personal() if r.get("id") != pid]
            save_personal(recs)
            self._send(json.dumps({"ok": True}))
        elif p == "/api/personal/exclude":
            # hide a single occurrence of a regular (don't delete the series)
            b = self._body()
            pid = (b.get("id") or "").strip()
            d = (b.get("date") or "").strip()
            key = d + "|" + _start_time(b.get("time") or "")
            recs = load_personal()
            for r in recs:
                if r.get("id") == pid:
                    ex = r.get("excluded") or []
                    if key not in ex:
                        ex.append(key)
                    r["excluded"] = ex
                    # if it was a selected class, drop that selection too
                    r["selected"] = [k for k in (r.get("selected") or []) if k != key]
            save_personal(recs)
            self._send(json.dumps({"ok": True}))
        elif p == "/api/personal/select":
            # add ONE specific class from the full schedule to your plans
            b = self._body()
            pid = (b.get("id") or "").strip()
            d = (b.get("date") or "").strip()
            key = d + "|" + _start_time(b.get("time") or "")
            recs = load_personal()
            for r in recs:
                if r.get("id") == pid:
                    sel = r.get("selected") or []
                    if key not in sel:
                        sel.append(key)
                    r["selected"] = sel
                    r["excluded"] = [k for k in (r.get("excluded") or []) if k != key]
            save_personal(recs)
            self._send(json.dumps({"ok": True}))
        elif p == "/api/personal/scan":
            pid = (self._body().get("id") or "").strip()
            sess = scan_regular_by_id(pid)
            self._send(json.dumps({"ok": bool(sess), "sessions": sess, "count": len(sess)}))
        elif p == "/api/admin/clear-cache":
            self._send(json.dumps({"ok": True, "cleared": clear_cache()}))
        else:
            self._send("not found", "text/plain", 404)


def main():
    os.makedirs(DATA, exist_ok=True)
    seed_personal()
    print(f"Marquee on 127.0.0.1:{PORT} (data={DATA}, llm={'on' if GEMINI_KEY else 'off'})", flush=True)
    # warm the event cache on boot + start the background crawl agent (keeps the
    # scraped-content cache fresh and re-extracts regulars' real times)
    threading.Thread(target=lambda: get_events(force=False), daemon=True).start()
    threading.Thread(target=crawler_loop, daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()


if __name__ == "__main__":
    main()

"""Deterministic tests for the Lumen notification engine. Run: python3 -I tests/test_notif.py
Patches the Expo sender (no network) and feeds synthetic local-times into the
candidate selector so logic is fully reproducible."""
import os, sys, json, importlib.util, tempfile
from datetime import datetime, timezone, timedelta, date

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["LUMEN_DATA"] = tempfile.mkdtemp(prefix="lumen_notif_test_")
os.environ.pop("GEMINI_API_KEY", None); os.environ.pop("GOOGLE_API_KEY", None)

spec = importlib.util.spec_from_file_location("srv", os.path.join(HERE, "server.py"))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.init_db()

SENT = []
m.expo_push_send = lambda c, toks, title, body, data=None: (SENT.append((toks, title, body, data)) or True)
m._notif_personalize = lambda kind, user: None  # force template copy, no network

c = m.db()
PASS = []; FAIL = []
def ok(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("  ok  " if cond else " FAIL ") + name)

def mkuser(email, name="T", streak=0, total=1, last_days_ago=1, bot=0):
    last = (date.today() - timedelta(days=last_days_ago)).isoformat() if last_days_ago is not None else None
    c.execute("INSERT INTO users(email,name,streak,best_streak,total_sessions,total_minutes,light,last_day,is_bot,created) "
              "VALUES(?,?,?,?,?,?,?,?,?,?)",
              (email, name, streak, streak, total, total*10, total*20, last, bot, m.now_iso()))
    c.commit()
    return c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

def addtoken(uid, tok="ExponentPushToken[test-%d]"):
    c.execute("INSERT OR IGNORE INTO push_tokens(user_id,token,platform,created,updated) VALUES(?,?,?,?,?)",
              (uid, tok % uid, "ios", m.now_iso(), m.now_iso())); c.commit()

def prefs(uid):  # ensure + return
    return m._notif_prefs(c, uid)

def lt_at(hour, weekday=0, yday_mod3=None):
    """Build a synthetic local datetime with a given hour/weekday (Mon=0)."""
    base = datetime(2026, 10, 12, hour, 0, tzinfo=timezone.utc)  # 2026-10-12 is a Monday
    d = base + timedelta(days=(weekday - base.weekday()))
    if yday_mod3 is not None:
        while d.timetuple().tm_yday % 3 != yday_mod3:
            d += timedelta(days=7)  # keep same weekday
    return d

# --- A: streak-save, evening, active streak, not sat today ---
u = mkuser("a@x", streak=5, last_days_ago=1); addtoken(u["id"]); prefs(u["id"])
cand = m._notif_candidate(c, u, prefs(u["id"]), lt_at(20))
ok("A streak_save selected for 5-day streak at 8pm", cand and cand[0] == "streak_save")

# --- B: daily reminder learns modal hour once >=5 sessions (Monday, not Sunday) ---
u = mkuser("b@x", streak=0, total=6, last_days_ago=1)   # >=5 sessions => STO learned
for _ in range(6):
    c.execute("INSERT INTO sessions(user_id,minutes,light,ended,day,week) VALUES(?,?,?,?,?,?)",
              (u["id"], 10, 20, "2026-10-01T09:30:00+00:00", "2026-10-01", "2026-W40"))
c.commit(); addtoken(u["id"]); prefs(u["id"])
cand = m._notif_candidate(c, u, prefs(u["id"]), lt_at(9, weekday=0))
ok("B daily_reminder at learned modal hour 9", cand and cand[0] == "daily_reminder")
cand_off = m._notif_candidate(c, u, prefs(u["id"]), lt_at(14, weekday=0))
ok("B no reminder at wrong hour", cand_off is None)

# --- B2: before 5 sessions, reminder uses onboarding pref_hour, not modal ---
u = mkuser("b2@x", streak=0, total=2, last_days_ago=1); addtoken(u["id"]); prefs(u["id"])
c.execute("UPDATE notif_prefs SET pref_hour=7 WHERE user_id=?", (u["id"],)); c.commit()
cand = m._notif_candidate(c, u, prefs(u["id"]), lt_at(7, weekday=0))
ok("B2 reminder fires at onboarding pref_hour 7", cand and cand[0] == "daily_reminder")
cand = m._notif_candidate(c, u, prefs(u["id"]), lt_at(19, weekday=0))
ok("B2 no reminder at default hour when pref_hour set", cand is None)

# --- C: quiet hours (21-8) ---
pr = prefs(u["id"])
ok("C quiet at 23:00", m._notif_quiet(pr, lt_at(23)))
ok("C not quiet at 10:00", not m._notif_quiet(pr, lt_at(10)))
ok("C quiet wraps to 03:00", m._notif_quiet(pr, lt_at(3)))

# --- D: category opt-out suppresses reminder ---
c.execute("UPDATE notif_prefs SET cats=? WHERE user_id=?",
          (json.dumps({**m.DEFAULT_CATS, "reminder": 0}), u["id"])); c.commit()
cand = m._notif_candidate(c, u, prefs(u["id"]), lt_at(9, weekday=0))
ok("D reminder suppressed when category off", cand is None)
c.execute("UPDATE notif_prefs SET cats=? WHERE user_id=?", (json.dumps(m.DEFAULT_CATS), u["id"])); c.commit()

# --- E: dedupe + daily cap ---
c.execute("INSERT INTO notif_log(user_id,category,title,body,dedupe_key,status,created) VALUES(?,?,?,?,?,?,?)",
          (u["id"], "daily_reminder", "t", "b", "reminder:%s" % m.today_str(), "sent", m.now_iso())); c.commit()
ok("E dedupe detects same-day reminder", m._dedup_exists(c, u["id"], "reminder:%s" % m.today_str()))
ok("E daily cap counts the sent reminder", m._sent_today_count(c, u["id"], m.TIME_CATS) >= 1)

# --- F: event path (milestone) enqueues + flush sends ---
u = mkuser("f@x", streak=7, last_days_ago=0); addtoken(u["id"]); prefs(u["id"])
c.execute("UPDATE notif_prefs SET quiet_start=0, quiet_end=0 WHERE user_id=?", (u["id"],)); c.commit()
m.notif_on_complete(c, u, [], False, 7); c.commit()
q = c.execute("SELECT COUNT(*) n FROM notif_log WHERE user_id=? AND dedupe_key='milestone:7'", (u["id"],)).fetchone()["n"]
ok("F milestone enqueued on 7-day streak", q == 1)
before = len(SENT)
m._notif_flush_queued(c)
ok("F flush sent the celebration", len(SENT) > before)
st = c.execute("SELECT status FROM notif_log WHERE user_id=? AND dedupe_key='milestone:7'", (u["id"],)).fetchone()["status"]
ok("F milestone marked sent", st == "sent")

# --- G: win-back for dormant user at noon on a yday%3==0 day ---
u = mkuser("g@x", streak=0, total=5, last_days_ago=10); addtoken(u["id"]); prefs(u["id"])
ok("G tier is dormant at 10 days", m._notif_tier(u) == "dormant")
cand = m._notif_candidate(c, u, prefs(u["id"]), lt_at(12, weekday=1, yday_mod3=0))
ok("G winback selected for dormant at noon", cand and cand[0] == "winback")

# --- H: full time pass respects quiet hours (no send when all quiet) ---
# force every prefs into quiet by setting a window covering all hours via start=0,end=23 then check a user inside
u = mkuser("h@x", streak=9, last_days_ago=1); addtoken(u["id"]); prefs(u["id"])
c.execute("UPDATE notif_prefs SET quiet_start=0, quiet_end=23 WHERE user_id=?", (u["id"],)); c.commit()
pr = prefs(u["id"])
# at hour 12 -> inside 0..23 quiet
ok("H quiet window 0-23 blocks noon", m._notif_quiet(pr, lt_at(12)))

print("\n%d passed, %d failed" % (len(PASS), len(FAIL)))
sys.exit(1 if FAIL else 0)

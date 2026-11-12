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
import os, json, sqlite3, time, threading, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---- Foreman: live subagent activity, read from OpenClaw's state DB ----
STATE_DB = os.environ.get("OPENCLAW_STATE_DB", "/root/.openclaw/state/openclaw.sqlite")
ROSTER_PATH = os.environ.get("FOREMAN_ROSTER", "/root/MonoClaw/foreman/projects.json")
_ROSTER_CACHE = {"mtime": 0, "by_slug": {}, "order": []}
_FALLBACK_COLOR = "#94a3b8"

# ---- Avatars (app icon → circular mark) + smart titles (Gemini, cached) ----
_AVATAR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "avatars")
_TITLES_PATH = os.environ.get("FOREMAN_TITLES", "/root/MonoClaw/foreman/titles.json")
_GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
_titles_cache = {"mtime": 0, "map": {}}
_title_inflight = set()
_title_lock = threading.Lock()


def _avatar_url(slug):
    if slug and os.path.exists(os.path.join(_AVATAR_DIR, slug + ".png")):
        return "avatars/" + slug + ".png"
    return None

# Foreman project slug -> dash ICONS key. When a slug has no PNG avatar, the board
# falls back to the app's branded SVG tile (defined in ICONS below) before the
# coloured-initial avatar — so every lane shows its real app icon.
_FOREMAN_ICON_KEYS = {
    "creator-cut": "creatorcut", "recilia": "recilia", "recilia-api": "recilia",
    "travelog": "travelog", "open-home": "openhome", "rolodex": "rolodex",
    "ora-health": "ora", "chase": "chase", "croppa": "croppa", "inkling": "inkling",
    "favorly": "favorly", "lumen": "lumen", "contentforge": "vantage",
    "marquee": "marquee", "foreman": "adminhub", "waypoint": "waypoint", "dropstick": "dropstick",
}

def _icon_svg(slug):
    key = _FOREMAN_ICON_KEYS.get(slug or "")
    return ICONS.get(key, "") if key else ""


def _load_titles():
    try:
        m = os.path.getmtime(_TITLES_PATH)
        if m != _titles_cache["mtime"]:
            with open(_TITLES_PATH) as f:
                _titles_cache["map"] = json.load(f)
            _titles_cache["mtime"] = m
    except Exception:
        pass
    return _titles_cache["map"]


def _title_fallback(task):
    t = (task or "").strip()
    if t.startswith("Foreman job "):
        parts = t.split("—", 1)
        if len(parts) == 2:
            t = parts[1].strip()
    t = t.replace("\n", " ").strip()
    return (t[:70] + "…") if len(t) > 72 else (t or "(no task)")


def _gen_title_async(run_id, task):
    def work():
        try:
            prompt = ("Write a concise 4 to 7 word title for this AI agent task. "
                      "Imperative mood, plain text, no markdown, no quotes, no trailing period. "
                      "Output only the title.\n\nTASK:\n" + (task or "")[:1500])
            url = ("https://generativelanguage.googleapis.com/v1beta/models/"
                   "gemini-flash-latest:generateContent?key=" + _GEMINI_KEY)
            body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                               "generationConfig": {"maxOutputTokens": 48, "temperature": 0.3,
                                                    "thinkingConfig": {"thinkingBudget": 0}}}).encode()
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
            j = json.loads(urllib.request.urlopen(req, timeout=25).read())
            parts = (j["candidates"][0].get("content") or {}).get("parts") or []
            title = "".join(p.get("text", "") for p in parts).strip()
            title = title.splitlines()[-1].strip().strip('"').strip("*").strip() if title else ""
            # drop a dangling "( ..." fragment left by truncation
            if "(" in title and ")" not in title:
                title = title.split("(")[0].strip()
            title = title.rstrip(" -—:(").strip()
            if not title or len(title) > 90 or "word" in title.lower():
                return
            with _title_lock:
                m = _load_titles()
                m[run_id] = title
                tmp = _TITLES_PATH + ".tmp"
                with open(tmp, "w") as f:
                    json.dump(m, f)
                os.replace(tmp, _TITLES_PATH)
                try:
                    _titles_cache["mtime"] = os.path.getmtime(_TITLES_PATH)
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            _title_inflight.discard(run_id)
    threading.Thread(target=work, daemon=True).start()


def _title_for(run_id, task_full, task_short):
    m = _load_titles()
    if run_id in m:
        return m[run_id]
    if _GEMINI_KEY and run_id and run_id not in _title_inflight:
        _title_inflight.add(run_id)
        _gen_title_async(run_id, task_full)
    return _title_fallback(task_short or task_full)

def _roster():
    """Load foreman/projects.json (cached by mtime): slug -> {name,color}, plus
    the column order. The roster is the single source of truth for lanes."""
    try:
        m = os.path.getmtime(ROSTER_PATH)
    except OSError:
        return _ROSTER_CACHE
    if m != _ROSTER_CACHE["mtime"]:
        by_slug, order, seen = {}, [], set()
        try:
            with open(ROSTER_PATH) as f:
                for p in (json.load(f).get("projects") or []):
                    slug, name = p.get("slug"), p.get("name") or p.get("slug")
                    color = p.get("color") or _FALLBACK_COLOR
                    if not slug:
                        continue
                    by_slug[slug] = {"name": name, "color": color,
                                     "doctorCmd": p.get("doctorCmd")}
                    if name not in seen:
                        order.append({"name": name, "color": color}); seen.add(name)
        except Exception:
            pass
        _ROSTER_CACHE.update(mtime=m, by_slug=by_slug, order=order)
    return _ROSTER_CACHE

def _project_of(label, workspace_dir):
    """Resolve a job's project (name,color,slug): prefer the 'project:jobid'
    label prefix, else the workspace folder basename, matched against the
    roster. slug is None when the job doesn't map to a known project."""
    r = _roster()["by_slug"]
    key = None
    if label and ":" in label:
        key = label.split(":", 1)[0]
    elif workspace_dir:
        key = os.path.basename(workspace_dir.rstrip("/"))
    if key and key in r:
        return r[key]["name"], r[key]["color"], key
    return (key or "—"), _FALLBACK_COLOR, None


def _fdata(name):
    """Read a foreman/data/<name>.json store (written by doctor.py / job.py).
    Tiny files, read each call. Missing/absent -> {}."""
    try:
        with open(os.path.join(os.path.dirname(ROSTER_PATH), "data", name)) as f:
            return json.load(f)
    except Exception:
        return {}

def _verdicts():
    """run_id -> rich verdict {ok,tests,acceptance,evidence,...} from doctor.py."""
    return _fdata("verdicts.json")

def _jobs():
    """label -> {task, acceptance:[...]} registered at intake by job.py."""
    return _fdata("jobs.json")

def _heartbeat():
    """Latest Foreman heartbeat summary written by doctor.py each pass."""
    return _fdata("heartbeat.json")

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
    verdicts = _verdicts()
    jobs = _jobs()
    by_slug = _roster()["by_slug"]
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
        task_full = (d.get("task") or d.get("task_name") or d.get("label") or "").strip()[:8000]
        task = task_full.replace("\n", " ")
        if len(task) > 180:
            task = task[:177] + "…"
        result_full = ""
        result = None
        if status in ("done", "failed"):
            result_full = (d.get("frozen_result_text") or "")
            if not result_full:
                try:
                    oj = json.loads(d.get("outcome_json") or "{}")
                    result_full = oj.get("summary") or oj.get("result") or ""
                except Exception:
                    result_full = ""
            result_full = (result_full or "").strip()[:8000]
            result = result_full.replace("\n", " ")
            if len(result) > 220:
                result = result[:217] + "…"
        # prefer the "project:jobid" label convention; fall back to the workspace dir
        project, color, slug = _project_of(d.get("label") or "", d.get("workspace_dir"))
        # doctor verdict: True=verified, False=failed(+note), "pending"=awaiting
        # a doctor run, None=not applicable (no doctorCmd / skipped). Only "done"
        # jobs are doctored (a failed agent run isn't worth verifying).
        doctor, doctor_note = None, ""
        has_doctor_cmd = bool(slug and by_slug.get(slug, {}).get("doctorCmd"))
        if status == "done" and has_doctor_cmd:
            v = verdicts.get(d.get("run_id"))
            if v is None:
                doctor = "pending"
            elif v.get("ok") is True:
                doctor = True
            elif v.get("ok") is False:
                doctor, doctor_note = False, v.get("note") or "doctor failed"
            # v.ok is None -> skipped -> leave doctor=None (no badge)
        # rich verification: pipeline test, photo evidence, acceptance checklist.
        v = verdicts.get(d.get("run_id")) or {}
        jobrec = jobs.get(d.get("label") or "") or {}
        criteria = jobrec.get("acceptance") or []
        # verified checklist if present, else the raw criteria as "pending".
        if v.get("acceptance"):
            acceptance = v["acceptance"]
        elif criteria:
            acceptance = [{"text": c, "ok": None, "why": ""} for c in criteria]
        else:
            acceptance = []
        tests = v.get("tests") or ({"ok": v.get("ok"), "note": v.get("note"),
                                    "cmd": v.get("cmd")} if v else None)
        out["jobs"].append({
            "id": d.get("run_id"), "project": project, "color": color,
            "title": _title_for(d.get("run_id"), task_full, task),
            "avatar": _avatar_url(slug), "icon": _icon_svg(slug),
            "status": status, "task": task, "model": d.get("model") or "",
            "mode": d.get("spawn_mode") or "", "elapsed": elapsed,
            "label": d.get("label") or d.get("task_name") or "",
            "requester": d.get("requester_display_key") or "", "result": result,
            "taskFull": task_full, "resultFull": result_full,
            "created": d.get("created_at"), "started": started, "ended": ended,
            "doctor": doctor, "doctorNote": doctor_note,
            "tests": tests, "acceptance": acceptance,
            "acceptanceOk": v.get("acceptance_ok"),
            "evidence": v.get("evidence"),
        })
    out["stats"] = counts
    out["roster"] = _roster()["order"]  # column order for the board
    out["heartbeat"] = _heartbeat()
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
 "vantage": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_vg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f472b6"/><stop offset="1" stop-color="#7c3aed"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_vg)"/><g fill="none" stroke="#fff" stroke-width="2.3" stroke-linecap="round" opacity="0.92"><circle cx="26" cy="26" r="5"/><path d="M26 14 a12 12 0 0 1 12 12"/><path d="M26 9 a17 17 0 0 1 17 17"/></g><line x1="26" y1="26" x2="37.5" y2="14.5" stroke="#fff" stroke-width="2.6" stroke-linecap="round"/><circle cx="36.5" cy="15.5" r="2.7" fill="#fff"/><circle cx="26" cy="26" r="2.4" fill="#fff"/></svg>',
 "marquee": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_mq" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff5c8a"/><stop offset="1" stop-color="#a855f7"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_mq)"/><rect x="13" y="17" width="26" height="22" rx="3.2" fill="#fff"/><rect x="13" y="17" width="26" height="6.5" rx="3.2" fill="#ffd7e4"/><g fill="#a855f7"><circle cx="19" cy="30" r="2.1"/><circle cx="26" cy="30" r="2.1"/><circle cx="33" cy="30" r="2.1"/><circle cx="19" cy="35.5" r="2.1"/><circle cx="26" cy="35.5" r="2.1"/></g><g fill="#fff"><circle cx="18" cy="13.5" r="1.8"/><circle cx="26" cy="12.5" r="1.8"/><circle cx="34" cy="13.5" r="1.8"/></g></svg>',
 "clawmap": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_cm" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7cc4ff"/><stop offset="1" stop-color="#4f46e5"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_cm)"/><g stroke="#fff" stroke-width="2.2" fill="none" opacity="0.95"><line x1="26" y1="17" x2="16" y2="28"/><line x1="26" y1="17" x2="36" y2="28"/><line x1="16" y1="28" x2="16" y2="37"/><line x1="36" y1="28" x2="36" y2="37"/></g><g fill="#fff"><rect x="21" y="12.5" width="10" height="7" rx="2"/><rect x="11" y="27" width="10" height="6.5" rx="2"/><rect x="31" y="27" width="10" height="6.5" rx="2"/><rect x="11" y="36.5" width="10" height="6" rx="2"/><rect x="31" y="36.5" width="10" height="6" rx="2"/></g></svg>',
 "adminhub": '<svg class="ai" viewBox="0 0 52 52"><defs><linearGradient id="g_ah" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f5c977"/><stop offset="1" stop-color="#7fe3ff"/></linearGradient></defs><rect width="52" height="52" rx="13" fill="url(#g_ah)"/><g fill="#1a2238"><rect x="15" y="18" width="22" height="2.8" rx="1.4"/><rect x="15" y="24.6" width="22" height="2.8" rx="1.4"/><rect x="15" y="31.2" width="22" height="2.8" rx="1.4"/></g><g fill="#fff" stroke="#1a2238" stroke-width="1.6"><circle cx="22" cy="19.4" r="3.1"/><circle cx="31" cy="26" r="3.1"/><circle cx="25" cy="32.6" r="3.1"/></g></svg>',
}

# (icon_key, name, url_or_None, description, status)  status: public | private | wip
APPS = [
    ("favorly", "Favorly", "https://dist-pi-rouge-27.vercel.app",
     "Microfavors &amp; Helping Hands — a community favor-exchange app. MVP backend built.", "public"),
    ("ora", "Ora Health", "https://ora-health-26.vercel.app",
     "Agentic-AI wellness app — dynamic conversations, daily meditations &amp; mindset work. React Native · ElevenLabs.", "public"),
    ("lumen", "Lumen", "https://lumen-production-a8c6.up.railway.app/",
     "Gamified meditation — every sit lights up a living world map, earns Light, builds streaks, and climbs weekly leagues. Guided voice journeys &amp; a reflective journal.", "public"),
    ("recilia", "Recilia", "https://recilia.bedrock.casa/",
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
    ("vantage", "Vantage", "https://vantage.bedrock.casa/",
     "Content intelligence engine — watch any competitor&rsquo;s social posts (Twitter/IG/Reddit via Xpoz), get an AI breakdown of their hooks, beats &amp; formats, then turn the winning angle into a Creator Cut video. Research &rarr; forge &rarr; distribute.", "public"),
    ("dropstick", "Dropstick", None,
     "Peer-to-peer music sharing for DJs — swap tracks &amp; crates device-to-device over local Wi-Fi, no internet. Go · SQLite.", "wip"),
]

# Claw Apps — apps Claw runs for Matthew, on permanent bedrock.casa URLs
CLAW_APPS = [
    ("reports", "Daily Reports &amp; News", "https://reports.bedrock.casa/",
     "Daily NYC news digest &amp; archive — morning briefings with inline mp3 voice notes.", "public"),
    ("adminhub", "Admin Hub", "https://admin.bedrock.casa/",
     "Every app&rsquo;s real admin dashboard, tools &amp; docs in one place — Ora, Recilia, plus the OpenClaw ops dashboards.", "public"),
    ("marquee", "Marquee", "https://marquee.bedrock.casa/",
     "What&rsquo;s on in NYC — a live calendar of concerts, shows, nightlife, art, sports &amp; festivals, refreshed daily. Browse by day or category and tap through for tickets.", "public"),
    ("clawmap", "Architecture", "https://map.bedrock.casa/",
     "Live map of the whole Claw estate — agents, edge, apps, hosts &amp; external services, layered top-down. The app roster auto-updates from Foreman.", "public"),
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
  /* Marquee — What's on in NYC widget */
  .mqw{display:block;text-decoration:none;color:inherit;position:relative;border-radius:20px;padding:20px 22px;max-width:720px;
    background:linear-gradient(135deg,#17121c,#1d1320);border:1.5px solid transparent;
    background:linear-gradient(#141019,#141019) padding-box,linear-gradient(135deg,#ff5c8a,#a855f7) border-box;
    box-shadow:0 18px 44px -16px rgba(168,85,247,.4);transition:transform .15s,box-shadow .15s}
  .mqw:hover{transform:translateY(-2px);box-shadow:0 24px 54px -18px rgba(168,85,247,.55)}
  .mqw-head{display:flex;align-items:center;gap:12px;margin-bottom:14px}
  .mqw-mk{width:34px;height:34px;flex:0 0 auto;border-radius:9px;background:linear-gradient(135deg,#ff5c8a,#a855f7)}
  .mqw-eyebrow{font-size:10.5px;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:#ff8fb0}
  .mqw-title{margin:1px 0 0;font-size:19px;color:#fff;font-weight:800;letter-spacing:-.01em}
  .mqw-all{margin-left:auto;font-size:12px;font-weight:650;color:#c6a6f0}
  .mqw-list{display:flex;flex-direction:column;gap:8px}
  .mqw-ev{display:flex;align-items:center;gap:12px;padding:9px 11px;border-radius:12px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.06)}
  .mqw-dt{flex:0 0 42px;text-align:center}
  .mqw-dt .mo{font-size:9px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:#ff8fb0}
  .mqw-dt .dy{font-size:19px;font-weight:800;color:#fff;line-height:1}
  .mqw-b{min-width:0;flex:1}
  .mqw-t{font-size:13.5px;font-weight:650;color:#f4f3f8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .mqw-m{font-size:11.5px;color:#9a98ad;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .mqw-cat{flex:0 0 auto;font-size:8.5px;font-weight:800;letter-spacing:.04em;text-transform:uppercase;padding:3px 7px;border-radius:6px;color:#fff;background:linear-gradient(135deg,#ff5c8a,#a855f7)}
  .mqw-near{font-size:9px;font-weight:800;letter-spacing:.03em;text-transform:uppercase;color:#ffcf33;margin-right:2px}
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
  /* Daily report widget */
  .rpw{position:relative;border-radius:20px;padding:20px 22px;max-width:720px;margin:0 auto;background:#fff;border:1px solid var(--line);
       box-shadow:0 1px 2px rgba(20,23,30,.04),0 18px 44px -16px rgba(99,102,241,.22)}
  .rpw-head{display:flex;align-items:center;gap:12px;margin-bottom:4px}
  .rpw-mk{width:30px;height:30px;border-radius:9px;flex:0 0 auto;background:linear-gradient(135deg,#a855f7,#6366f1);
          box-shadow:0 6px 16px -6px rgba(124,58,237,.6)}
  .rpw-eyebrow{font-size:11px;font-weight:800;letter-spacing:.16em;text-transform:uppercase;color:#8b5cf6}
  .rpw-title{margin:1px 0 0;font-size:19px}
  .rpw-edit{margin-left:auto;border:1px solid var(--line);background:#faf9fc;color:#6d28d9;font-size:12.5px;font-weight:700;
            border-radius:11px;padding:8px 12px;cursor:pointer;white-space:nowrap;transition:background .12s,border-color .12s}
  .rpw-edit:hover{background:#f3eefe;border-color:#c9b8f5}
  .rpw-date{font-size:12.5px;color:var(--muted);margin:2px 0 10px}
  .rpw-body{font-size:14px;line-height:1.5;color:var(--ink);white-space:pre-wrap;max-height:200px;overflow:hidden;
            position:relative;-webkit-mask-image:linear-gradient(#000 76%,transparent);mask-image:linear-gradient(#000 76%,transparent)}
  .rpw-foot{display:flex;align-items:center;gap:12px;margin-top:12px}
  .rpw-audio{height:34px;flex:1;min-width:0}
  .rpw-all{margin-left:auto;font-size:13px;font-weight:700;color:#6d28d9;text-decoration:none;white-space:nowrap}
  .rpw-all:hover{text-decoration:underline}
  /* Report Studio modal */
  .rs-backdrop{position:fixed;inset:0;background:rgba(24,20,38,.5);backdrop-filter:blur(3px);z-index:60;display:flex;
               align-items:flex-start;justify-content:center;padding:28px 14px;overflow:auto}
  .rs-modal{background:#fff;border-radius:22px;max-width:620px;width:100%;padding:24px;box-shadow:0 30px 80px -20px rgba(24,20,38,.5)}
  .rs-top{display:flex;align-items:flex-start;gap:12px}
  .rs-eyebrow{font-size:11px;font-weight:800;letter-spacing:.16em;text-transform:uppercase;color:#8b5cf6}
  .rs-h{margin:1px 0 0;font-size:22px}
  .rs-x{margin-left:auto;border:none;background:#f1eff6;color:#555;width:34px;height:34px;border-radius:10px;font-size:16px;cursor:pointer}
  .rs-x:hover{background:#e8e4f2}
  .rs-sub{font-size:13px;color:var(--muted);line-height:1.5;margin:8px 0 16px}
  .rs-fields{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:16px}
  .rs-f{display:flex;flex-direction:column;gap:5px;flex:1;min-width:200px}
  .rs-f.rs-f-sm{flex:0 0 130px;min-width:120px}
  .rs-f span{font-size:11px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:#8b8f9c}
  .rs-f input,.rs-f select{border:1px solid var(--line);border-radius:11px;padding:11px 12px;font-size:14px;background:#faf9fc;color:var(--ink);outline:none;width:100%;-webkit-appearance:none;appearance:none}
  .rs-f select{background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'><path d='M1 1l5 5 5-5' fill='none' stroke='%238b5cf6' stroke-width='2' stroke-linecap='round'/></svg>");background-repeat:no-repeat;background-position:right 12px center;padding-right:30px}
  .rs-f input:focus,.rs-f select:focus{border-color:#a855f7;box-shadow:0 0 0 3px rgba(168,85,247,.14)}
  .rs-hint{font-size:11px;color:#9a97a8;margin-top:5px}
  .rs-seclbl{font-size:11px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:#8b8f9c;margin:4px 0 8px}
  .rs-secs{display:flex;flex-direction:column;gap:10px}
  .rs-sec{border:1px solid var(--line);border-radius:14px;padding:12px;background:#fbfafe;transition:opacity .15s}
  .rs-sec.off{opacity:.5}
  .rs-sec-top{display:flex;align-items:center;gap:9px}
  .rs-sec-top input.rs-icon{width:40px;text-align:center;font-size:16px}
  .rs-sec-top input.rs-label{flex:1;font-weight:700}
  .rs-sec-top input{border:1px solid var(--line);border-radius:9px;padding:8px 9px;font-size:14px;background:#fff;color:var(--ink);outline:none}
  .rs-toggle{flex:0 0 auto;width:22px;height:22px;border:2px solid #cfd2dc;border-radius:7px;cursor:pointer;display:flex;align-items:center;justify-content:center;color:#fff;font-size:13px}
  .rs-sec:not(.off) .rs-toggle{border-color:transparent;background:linear-gradient(135deg,#6366f1,#ec4899)}
  .rs-mv{display:flex;flex-direction:column;gap:0}
  .rs-mv button{border:none;background:none;color:#c2c6d2;font-size:11px;line-height:.9;cursor:pointer;padding:1px 3px}
  .rs-mv button:hover:not(:disabled){color:#7c3aed} .rs-mv button:disabled{opacity:.25;cursor:default}
  .rs-del{border:none;background:none;color:#c6cad4;font-size:16px;cursor:pointer} .rs-del:hover{color:#ec4899}
  .rs-want{width:100%;margin-top:9px;border:1px solid var(--line);border-radius:10px;padding:10px;font-size:13px;line-height:1.45;
           background:#fff;color:var(--ink);outline:none;resize:vertical;min-height:52px;font-family:inherit}
  .rs-want:focus{border-color:#a855f7;box-shadow:0 0 0 3px rgba(168,85,247,.12)}
  .rs-add{margin-top:12px;border:1.5px dashed #c9b8f5;background:#faf7ff;color:#6d28d9;font-weight:700;font-size:13.5px;
          border-radius:12px;padding:11px;width:100%;cursor:pointer}
  .rs-add:hover{background:#f3eefe}
  .rs-actions{display:flex;gap:10px;justify-content:flex-end;margin-top:18px}
  .rs-cancel{border:1px solid var(--line);background:#fff;color:#555;font-weight:700;font-size:14px;border-radius:12px;padding:11px 18px;cursor:pointer}
  .rs-save{border:none;background:linear-gradient(135deg,#6366f1,#a855f7,#ec4899);color:#fff;font-weight:800;font-size:14px;
           border-radius:12px;padding:11px 22px;cursor:pointer;box-shadow:0 10px 22px -10px rgba(124,58,237,.6)}
  .rs-save:hover{filter:brightness(1.06)} .rs-save:disabled{opacity:.6;cursor:default}
  /* Foreman — live subagent mission control. Calm surface, premium gradient glow-up. */
  .foreman{position:relative;overflow:hidden;
    background:radial-gradient(130% 90% at 100% 0%,rgba(124,58,237,.05),transparent 55%),
               radial-gradient(90% 70% at 0% 0%,rgba(99,102,241,.04),transparent 50%),var(--card);
    border:1px solid #e8ecf2;border-radius:18px;padding:28px;max-width:1120px;box-shadow:var(--shadow)}
  .foreman::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;
    background:linear-gradient(90deg,#6366f1,#a855f7,#ec4899);opacity:.9}
  .fm-head{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:24px;gap:20px;flex-wrap:wrap}
  .fm-live{display:inline-flex;align-items:center;gap:7px;font-size:10px;font-weight:800;letter-spacing:.16em;text-transform:uppercase;
    background:linear-gradient(135deg,#6366f1,#a855f7,#ec4899);-webkit-background-clip:text;background-clip:text;color:transparent}
  .fm-live-dot{width:7px;height:7px;border-radius:50%;background:linear-gradient(135deg,#6366f1,#a855f7);
    box-shadow:0 0 8px -1px rgba(124,58,237,.7);animation:fmpulse 1.8s infinite}
  .fm-title{margin:10px 0 0;font-size:20px;font-weight:700;letter-spacing:-.015em;
    background:linear-gradient(120deg,var(--ink) 30%,#5b4fc7);-webkit-background-clip:text;background-clip:text;color:transparent}
  .fm-stats{display:flex;align-items:flex-start;gap:22px;flex-wrap:wrap}
  .fm-metric{display:flex;flex-direction:column;gap:3px;line-height:1}
  .fm-metric b{font-size:19px;font-weight:700;color:var(--ink);font-variant-numeric:tabular-nums}
  .fm-metric span{font-size:9.5px;font-weight:600;letter-spacing:.09em;text-transform:uppercase;color:var(--muted)}
  .fm-metric.fail b{color:#dc2626}
  .fm-empty{color:var(--muted);font-size:14px;line-height:1.55;padding:16px 2px}
  /* board: a full-width vertical list of job rows, grouped by project (no horizontal scroll) */
  .fm-board{display:flex;flex-direction:column;gap:28px}
  .fm-group{padding:0}
  .fm-col-head{display:flex;align-items:center;gap:9px;padding-bottom:11px;margin-bottom:14px;border-bottom:1px solid #eef1f6}
  .fm-chip{width:9px;height:9px;border-radius:50%;flex:0 0 auto;
    background:radial-gradient(circle at 30% 28%,rgba(255,255,255,.65),transparent 62%),var(--accent,#94a3b8);
    box-shadow:0 0 0 3px color-mix(in srgb,var(--accent,#94a3b8) 14%,transparent),0 1px 3px color-mix(in srgb,var(--accent,#94a3b8) 45%,transparent)}
  .fm-col-name{font-weight:800;font-size:11px;letter-spacing:.1em;text-transform:uppercase;
    background:linear-gradient(90deg,color-mix(in srgb,var(--accent,#94a3b8) 88%,#1b2330),color-mix(in srgb,var(--accent,#94a3b8) 55%,#8b93a3));
    -webkit-background-clip:text;background-clip:text;color:transparent}
  .fm-col-count{margin-left:auto;font-size:11px;font-weight:600;color:var(--muted);background:#f3f5f9;border-radius:999px;padding:3px 10px;font-variant-numeric:tabular-nums}
  .fm-col-body{display:flex;flex-direction:column;gap:10px}
  /* each subagent = one full-width row */
  .fm-job{position:relative;overflow:hidden;display:flex;flex-direction:column;align-items:stretch;gap:0;padding:15px 16px 15px 19px;border-radius:12px;
    background:linear-gradient(135deg,#ffffff,color-mix(in srgb,var(--accent) 5%,#ffffff));
    border:1px solid #e8ecf2;cursor:pointer;transition:border-color .15s,box-shadow .15s,transform .15s,background .2s}
  .fm-job::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;
    background:linear-gradient(180deg,var(--accent),color-mix(in srgb,var(--accent) 50%,#ffffff));opacity:.65;transition:opacity .15s}
  .fm-job:hover{border-color:color-mix(in srgb,var(--accent) 32%,#dbe1ea);
    background:linear-gradient(135deg,#ffffff,color-mix(in srgb,var(--accent) 9%,#ffffff));
    box-shadow:0 8px 22px -11px color-mix(in srgb,var(--accent) 55%,rgba(20,23,30,.35));transform:translateY(-1px)}
  .fm-job:hover::before{opacity:1}
  .fm-dot{width:9px;height:9px;border-radius:50%;flex:0 0 auto;margin-top:6px}
  .fm-dot.running{background:linear-gradient(135deg,var(--accent),color-mix(in srgb,var(--accent) 50%,#ffffff));animation:fmpulse 1.6s infinite}
  .fm-dot.queued{background:linear-gradient(135deg,#f59e0b,#fb923c);box-shadow:0 1px 5px -1px rgba(245,158,11,.6)}
  .fm-dot.done{background:linear-gradient(135deg,#10b981,#14b8a6);box-shadow:0 1px 5px -1px rgba(16,185,129,.55)}
  .fm-dot.failed{background:linear-gradient(135deg,#f43f5e,#ef4444);box-shadow:0 1px 5px -1px rgba(239,68,68,.6)}
  @keyframes fmpulse{0%{box-shadow:0 0 0 0 rgba(79,70,229,.4)}70%{box-shadow:0 0 0 6px rgba(79,70,229,0)}100%{box-shadow:0 0 0 0 rgba(79,70,229,0)}}
  .fm-main{min-width:0;flex:1}
  .fm-row1{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
  .fm-badge{font-size:9px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;padding:3.5px 9px;border-radius:7px;line-height:1;
    color:#fff;box-shadow:inset 0 1px 0 rgba(255,255,255,.18)}
  .fm-badge.running{background:linear-gradient(135deg,#4f46e5,#7c3aed);box-shadow:inset 0 1px 0 rgba(255,255,255,.2),0 2px 6px -2px rgba(99,102,241,.6)}
  .fm-badge.queued{background:linear-gradient(135deg,#b45309,#c2410c);box-shadow:inset 0 1px 0 rgba(255,255,255,.2),0 2px 6px -2px rgba(217,119,6,.5)}
  .fm-badge.done{background:linear-gradient(135deg,#047857,#0d9488);box-shadow:inset 0 1px 0 rgba(255,255,255,.2),0 2px 6px -2px rgba(13,148,136,.5)}
  .fm-badge.failed{background:linear-gradient(135deg,#be123c,#b91c1c);box-shadow:inset 0 1px 0 rgba(255,255,255,.2),0 2px 6px -2px rgba(190,18,60,.5)}
  .fm-elapsed{margin-left:auto;font-size:11.5px;color:var(--muted);font-variant-numeric:tabular-nums;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
  .fm-chev{font-size:16px;line-height:1;margin-left:4px;transition:opacity .15s,transform .15s;opacity:.4;
    background:linear-gradient(135deg,var(--accent),color-mix(in srgb,var(--accent) 55%,#c7cedb));-webkit-background-clip:text;background-clip:text;color:transparent}
  .fm-job:hover .fm-chev{opacity:1;transform:translateX(3px)}
  /* running/all filter toggle */
  .fm-filter{display:inline-flex;gap:2px;padding:3px;border-radius:10px;background:#f1f3f8;border:1px solid #e6eaf1}
  .fm-filter button{border:0;background:none;cursor:pointer;font:inherit;font-size:11.5px;font-weight:650;letter-spacing:.01em;
    color:#64748b;padding:5px 12px;border-radius:7px;transition:background .15s,color .15s,box-shadow .15s}
  .fm-filter button.on{background:#fff;color:#0f172a;box-shadow:0 1px 3px -1px rgba(20,23,30,.2)}
  /* card layout (sketch): avatar + title, status chip, progress bar */
  .fm-head{display:flex;align-items:center;gap:12px}
  .fm-avatar{width:36px;height:36px;border-radius:50%;flex:0 0 auto;display:flex;align-items:center;justify-content:center;
    font-size:15px;font-weight:800;color:#fff;letter-spacing:-.01em;
    background:linear-gradient(135deg,var(--accent),color-mix(in srgb,var(--accent) 45%,#ffffff));
    box-shadow:0 3px 10px -3px color-mix(in srgb,var(--accent) 60%,rgba(20,23,30,.45)),inset 0 1px 0 rgba(255,255,255,.35)}
  .fm-avatar.running{animation:fmpulse 1.8s infinite}
  .fm-avatar-img{width:36px;height:36px;border-radius:50%;flex:0 0 auto;object-fit:cover;background:#0b0e16;
    box-shadow:0 3px 10px -3px rgba(20,23,30,.45),inset 0 0 0 1px rgba(255,255,255,.08)}
  .fm-avatar-img.running{animation:fmpulse 1.8s infinite}
  .fm-avatar-svg{width:36px;height:36px;flex:0 0 auto;display:block}
  .fm-avatar-svg svg{width:36px;height:36px;border-radius:10px;display:block}
  .fm-avatar-svg.running svg{animation:fmpulse 1.8s infinite}
  .fm-title{flex:1;min-width:0;font-size:15px;font-weight:650;color:var(--ink);line-height:1.4;word-break:break-word;white-space:pre-wrap}
  .fm-meta{display:flex;align-items:center;gap:9px;margin-top:12px;flex-wrap:wrap}
  .fm-meta .fm-doc{margin:0}
  .fm-progress{position:relative;height:7px;border-radius:999px;background:#eef1f6;overflow:hidden;margin-top:12px;box-shadow:inset 0 1px 2px rgba(20,23,30,.08)}
  .fm-progress i{position:absolute;left:0;top:0;bottom:0;border-radius:999px;display:block;width:0}
  .fm-progress.queued i{width:12%;background:linear-gradient(90deg,#f59e0b,#fb923c)}
  .fm-progress.done i{width:100%;background:linear-gradient(90deg,#10b981,#14b8a6)}
  .fm-progress.failed i{width:100%;background:linear-gradient(90deg,#f43f5e,#ef4444)}
  .fm-progress.running i{width:100%;
    background:repeating-linear-gradient(45deg,var(--accent) 0,var(--accent) 9px,color-mix(in srgb,var(--accent) 55%,#ffffff) 9px,color-mix(in srgb,var(--accent) 55%,#ffffff) 18px);
    background-size:25.46px 25.46px;animation:fmstripe .8s linear infinite}
  @keyframes fmstripe{from{background-position:0 0}to{background-position:25.46px 0}}
  /* the full prompt, always visible and wrapping — no clamp, no side-scroll */
  .fm-task{margin:8px 0 0;font-size:14px;color:var(--ink);line-height:1.5;word-break:break-word;white-space:pre-wrap}
  .fm-result{margin:8px 0 0;font-size:12px;color:var(--muted);line-height:1.5;word-break:break-word;
    display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
  .fm-doc{margin:9px 0 0;display:inline-block;font-size:9px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;padding:3.5px 9px;border-radius:7px;color:#fff}
  .fm-doc.ok{background:linear-gradient(135deg,#059669,#0d9488);box-shadow:0 2px 6px -2px rgba(5,150,105,.5)}
  .fm-doc.bad{background:linear-gradient(135deg,#be123c,#b91c1c);box-shadow:0 2px 6px -2px rgba(190,18,60,.5)}
  .fm-doc.pending{background:linear-gradient(135deg,#eef1f6,#f3f5f9);color:#64748b}
  /* heartbeat bar — live Foreman vitals over every job */
  .fm-heart{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin:2px 0 20px;padding:11px 15px;border-radius:12px;
    background:linear-gradient(135deg,#fff,#fdf2f6);border:1px solid #f4d9e4;box-shadow:0 2px 10px -6px rgba(190,24,93,.35)}
  .fm-heart .hb{display:inline-flex;align-items:center;gap:7px;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#be185d}
  .fm-heart .hb svg{width:16px;height:16px;display:block;animation:hbeat 1.4s ease-in-out infinite;transform-origin:center}
  @keyframes hbeat{0%,100%{transform:scale(1)}15%{transform:scale(1.28)}30%{transform:scale(1)}45%{transform:scale(1.18)}}
  .fm-heart .hbv{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:650;color:#475569}
  .fm-heart .hbv i{width:8px;height:8px;border-radius:50%;display:block}
  .fm-heart .hbv.ok i{background:#10b981}.fm-heart .hbv.bad i{background:#ef4444}
  .fm-heart .hbv.run i{background:#6366f1;animation:fmpulse 1.6s infinite}.fm-heart .hbv.ver i{background:#f59e0b}
  .fm-heart .hbv b{font-variant-numeric:tabular-nums;color:#0f172a}
  .fm-heart .hbt{margin-left:auto;font-size:10.5px;color:#94a3b8;font-variant-numeric:tabular-nums}
  .fm-heart .hbstuck{color:#b91c1c;font-weight:650}
  /* per-card verification: test + acceptance pills, evidence thumb */
  .fm-checks{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-top:10px}
  .fm-pill{display:inline-flex;align-items:center;gap:4px;font-size:10px;font-weight:700;letter-spacing:.03em;padding:3px 8px;border-radius:7px;line-height:1.3}
  .fm-pill.ok{background:#e7f8f0;color:#047857;box-shadow:inset 0 0 0 1px #bfe9d6}
  .fm-pill.bad{background:#fdeaec;color:#be123c;box-shadow:inset 0 0 0 1px #f6c9d1}
  .fm-pill.pending{background:#f1f3f8;color:#64748b;box-shadow:inset 0 0 0 1px #e3e8f0}
  .fm-pill.ev{background:#eef0ff;color:#4f46e5;box-shadow:inset 0 0 0 1px #d7dcfb;cursor:pointer}
  .fm-ev-thumb{margin-top:10px;border-radius:9px;overflow:hidden;border:1px solid #e8ecf2;max-width:220px;cursor:pointer;
    box-shadow:0 3px 10px -5px rgba(20,23,30,.3);transition:transform .15s,box-shadow .15s}
  .fm-ev-thumb:hover{transform:translateY(-1px);box-shadow:0 8px 18px -8px rgba(20,23,30,.4)}
  .fm-ev-thumb img{display:block;width:100%;height:auto}
  /* acceptance checklist (card mini + modal full) */
  .fm-acc{margin-top:10px;display:flex;flex-direction:column;gap:5px}
  .fm-acc-item{display:flex;align-items:flex-start;gap:7px;font-size:12.5px;line-height:1.4;color:#2b3340}
  .fm-acc-item .mk{flex:0 0 auto;width:16px;height:16px;border-radius:5px;display:inline-flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;color:#fff;margin-top:1px}
  .fm-acc-item .mk.ok{background:#10b981}.fm-acc-item .mk.bad{background:#ef4444}.fm-acc-item .mk.pending{background:#cbd5e1;color:#64748b}
  .fm-acc-item .why{color:#94a3b8;font-size:11px}
  /* job detail modal */
  .fm-modal-backdrop{position:fixed;inset:0;background:rgba(20,23,30,.5);display:flex;align-items:center;justify-content:center;z-index:50;padding:20px}
  .fm-modal-backdrop[hidden]{display:none}
  .fm-modal{background:var(--card);border-radius:16px;max-width:660px;width:100%;max-height:86vh;overflow:auto;box-shadow:0 24px 70px -20px rgba(20,23,30,.4);border:1px solid #e8ecf2}
  .fm-m-strip{height:4px;background:linear-gradient(90deg,var(--accent,#4f46e5),color-mix(in srgb,var(--accent,#4f46e5) 45%,#a855f7))}
  .fm-m-head{display:flex;align-items:center;gap:10px;padding:16px 20px;border-bottom:1px solid #eef1f6;position:sticky;top:0;background:var(--card);z-index:1}
  .fm-m-proj{font-weight:700;font-size:15px;letter-spacing:-.01em;color:var(--ink)}
  .fm-m-x{margin-left:auto;border:none;background:#f3f5f9;color:#64748b;width:28px;height:28px;border-radius:8px;cursor:pointer;font-size:13px;flex:0 0 auto;transition:background .15s}
  .fm-m-x:hover{background:#e7ebf1}
  .fm-m-meta{display:grid;grid-template-columns:1fr 1fr;gap:14px 20px;padding:18px 20px;border-bottom:1px solid #eef1f6}
  .fm-m-kv{display:flex;flex-direction:column;gap:3px;min-width:0}
  .fm-m-kv span{font-size:9px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--muted)}
  .fm-m-kv b{font-size:13px;font-weight:600;color:var(--ink);word-break:break-word;font-variant-numeric:tabular-nums}
  .fm-m-section{padding:16px 20px}
  .fm-m-section h4{margin:0 0 8px;font-size:9px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);display:flex;align-items:center;gap:8px}
  .fm-m-section pre{margin:0;white-space:pre-wrap;word-break:break-word;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;line-height:1.55;color:#2b3340;background:#f7f8fb;border:1px solid #eceff4;border-radius:10px;padding:13px 15px}
  .fm-m-doc{font-size:9px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;padding:3.5px 9px;border-radius:7px;color:#fff}
  .fm-m-doc.ok{background:linear-gradient(135deg,#059669,#0d9488)}.fm-m-doc.bad{background:linear-gradient(135deg,#be123c,#b91c1c)}.fm-m-doc.pending{background:linear-gradient(135deg,#eef1f6,#f3f5f9);color:#64748b}
  @media (max-width:560px){
    .foreman{padding:20px 16px}
    .fm-stats{gap:16px}
    .fm-metric b{font-size:17px}
    .fm-m-meta{grid-template-columns:1fr}
  }
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

<section class="wrap" style="margin-bottom:8px">
  <a class="mqw" id="mqWidget" href="https://marquee.bedrock.casa/" target="_blank" rel="noopener" hidden>
    <div class="mqw-head">
      <span class="mqw-mk"></span>
      <div><div class="mqw-eyebrow">What&rsquo;s on in NYC</div><h2 class="mqw-title">Marquee</h2></div>
      <span class="mqw-all">Open calendar →</span>
    </div>
    <div class="mqw-list" id="mqList"></div>
  </a>
</section>

<section class="wrap" style="margin-bottom:8px">
  <div class="rpw" id="rpWidget" hidden>
    <div class="rpw-head">
      <span class="rpw-mk"></span>
      <div><div class="rpw-eyebrow">Daily report</div><h2 class="rpw-title" id="rpTitle">Report</h2></div>
      <button type="button" class="rpw-edit" id="rpEdit" title="Customize what your report contains">✎ Customize</button>
    </div>
    <div class="rpw-date" id="rpDate"></div>
    <div class="rpw-body" id="rpBody"></div>
    <div class="rpw-foot">
      <audio class="rpw-audio" id="rpAudio" controls preload="none" hidden></audio>
      <a class="rpw-all" href="https://reports.bedrock.casa/" target="_blank" rel="noopener">Open reports →</a>
    </div>
  </div>
</section>

<div id="rsModal" class="rs-backdrop" hidden>
  <div class="rs-modal">
    <div class="rs-top">
      <div><div class="rs-eyebrow">Report Studio</div><h2 class="rs-h" id="rsName">Daily report</h2></div>
      <button type="button" class="rs-x" id="rsClose" aria-label="Close">✕</button>
    </div>
    <p class="rs-sub">Tell the morning generator exactly what you want. Toggle sections, edit what each should cover, reorder, or add your own. Saved changes shape tomorrow&rsquo;s 8am report.</p>
    <div class="rs-fields">
      <label class="rs-f"><span>Opening line</span><select id="rsGreet"></select><small class="rs-hint">How the report greets you at the top.</small></label>
      <label class="rs-f"><span>Tone</span><select id="rsTone"></select><small class="rs-hint">The voice of the writing.</small></label>
      <label class="rs-f rs-f-sm"><span>Delivery time</span><select id="rsHour"></select><small class="rs-hint">When it arrives (ET).</small></label>
    </div>
    <div class="rs-seclbl">Sections</div>
    <div id="rsSecs" class="rs-secs"></div>
    <button type="button" class="rs-add" id="rsAdd">+ Add a section</button>
    <div class="rs-actions">
      <button type="button" class="rs-cancel" id="rsCancel">Cancel</button>
      <button type="button" class="rs-save" id="rsSave">Save report</button>
    </div>
  </div>
</div>

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
        <div class="fm-live"><span class="fm-live-dot"></span>Foreman · Live</div>
        <h2 class="fm-title">Subagents at work</h2>
      </div>
      <div class="fm-stats" id="fmStats"></div>
      <div class="fm-filter" id="fmFilter">
        <button type="button" data-view="running" class="on">Running</button>
        <button type="button" data-view="all">All</button>
      </div>
    </div>
    <div id="fmHeart" class="fm-heart" hidden></div>
    <div id="fmBoard" class="fm-board"></div>
  </div>
</section>

<div id="fmModal" class="fm-modal-backdrop" hidden><div class="fm-modal"></div></div>

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
  var _syncT=null;
  function pushServer(){clearTimeout(_syncT);_syncT=setTimeout(function(){
    try{fetch('api/todo',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({todos:todos})}).catch(function(){});}catch(e){}
  },300);}
  function save(){try{localStorage.setItem(KEY,JSON.stringify(todos));}catch(e){}pushServer();}
  // Shared server store is the source of truth across Dash + Marquee; migrate any
  // local-only tasks up once if the server list is empty.
  fetch('api/todo',{cache:'no-store'}).then(function(r){return r.json();}).then(function(d){
    var srv=(d&&d.todos)||[];
    if(srv.length){todos=srv;try{localStorage.setItem(KEY,JSON.stringify(todos));}catch(e){}render();}
    else if(todos.length){pushServer();}
  }).catch(function(){});
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
// ---- Marquee widget: next few NYC events (same-origin proxy to :18852) ----
(function(){
  var wrap=document.getElementById('mqWidget'),list=document.getElementById('mqList');
  if(!wrap)return;
  var MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  function esc(s){return (s||'').replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function row(e){
    var p=(e.date||'').split('-'),d=new Date(+p[0],+p[1]-1,+p[2]);
    var meta=[e.time,e.venue].filter(Boolean).join(' · ');
    return '<div class="mqw-ev"><div class="mqw-dt"><div class="mo">'+MON[d.getMonth()]+'</div><div class="dy">'+d.getDate()+'</div></div>'
      +'<div class="mqw-b"><div class="mqw-t">'+(e.near_home?'<span class="mqw-near">★ near you</span> ':'')+esc(e.title)+'</div><div class="mqw-m">'+esc(meta)+'</div></div>'
      +'<span class="mqw-cat">'+esc(e.category||'')+'</span></div>';
  }
  fetch('api/events-widget',{cache:'no-store'}).then(function(r){return r.json();}).then(function(d){
    var evs=(d.events||[]).slice(0,5);
    if(!evs.length)return;
    list.innerHTML=evs.map(row).join('');
    wrap.hidden=false;
  }).catch(function(){});
})();
// ---- Daily report widget + Report Studio editor ----
(function(){
  var wrap=document.getElementById('rpWidget');
  if(!wrap)return;
  function esc(s){return (s||'').replace(/[&<>]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;'}[c];});}
  // latest report preview
  fetch('api/report-latest',{cache:'no-store'}).then(function(r){return r.json();}).then(function(d){
    var rp=d&&d.report;if(!rp)return;
    document.getElementById('rpTitle').textContent=rp.title||'Daily report';
    document.getElementById('rpDate').textContent=rp.date||'';
    document.getElementById('rpBody').textContent=rp.text||'';
    if(rp.audio){var a=document.getElementById('rpAudio');a.src='report-audio/'+rp.audio;a.hidden=false;}
    wrap.hidden=false;
  }).catch(function(){});

  // Report Studio
  var modal=document.getElementById('rsModal'),secBox=document.getElementById('rsSecs');
  var cfg=null, rep=null;
  function uid(){return 's'+Date.now().toString(36)+Math.random().toString(36).slice(2,5);}
  function secCard(s){
    var card=document.createElement('div');card.className='rs-sec'+(s.enabled===false?' off':'');
    var top=document.createElement('div');top.className='rs-sec-top';
    var tog=document.createElement('span');tog.className='rs-toggle';tog.textContent=s.enabled===false?'':'✓';tog.title='Include this section';
    tog.onclick=function(){s.enabled=(s.enabled===false);card.classList.toggle('off',s.enabled===false);tog.textContent=s.enabled===false?'':'✓';};
    var icon=document.createElement('input');icon.className='rs-icon';icon.value=s.icon||'';icon.maxLength=4;icon.oninput=function(){s.icon=icon.value;};
    var label=document.createElement('input');label.className='rs-label';label.value=s.label||'';label.placeholder='Section name';label.oninput=function(){s.label=label.value;};
    var mv=document.createElement('span');mv.className='rs-mv';
    var up=document.createElement('button');up.innerHTML='▴';up.title='Move up';
    var dn=document.createElement('button');dn.innerHTML='▾';dn.title='Move down';
    up.onclick=function(){var i=rep.sections.indexOf(s);if(i>0){rep.sections.splice(i,1);rep.sections.splice(i-1,0,s);drawSecs();}};
    dn.onclick=function(){var i=rep.sections.indexOf(s);if(i<rep.sections.length-1){rep.sections.splice(i,1);rep.sections.splice(i+1,0,s);drawSecs();}};
    mv.appendChild(up);mv.appendChild(dn);
    var del=document.createElement('button');del.className='rs-del';del.innerHTML='✕';del.title='Remove section';
    del.onclick=function(){rep.sections.splice(rep.sections.indexOf(s),1);drawSecs();};
    top.appendChild(tog);top.appendChild(icon);top.appendChild(label);top.appendChild(mv);top.appendChild(del);
    var want=document.createElement('textarea');want.className='rs-want';want.value=s.want||'';
    want.placeholder='What should this section cover? e.g. "4-5 top headlines, one line each"';
    want.oninput=function(){s.want=want.value;};
    card.appendChild(top);card.appendChild(want);
    return card;
  }
  function drawSecs(){
    secBox.innerHTML='';
    (rep.sections||[]).forEach(function(s){var i=rep.sections.indexOf(s);
      var c=secCard(s);var ups=c.querySelectorAll('.rs-mv button');
      ups[0].disabled=(i===0);ups[1].disabled=(i===rep.sections.length-1);
      secBox.appendChild(c);});
  }
  // Preset choices for the dropdowns. Any saved value not in a list is added so
  // nothing is ever lost.
  var GREETS=['Good morning, Matthew','Rise and shine, Matthew','Morning, Matthew','Hello, Matthew','Good morning'];
  var TONES=[
    ['Tight, skimmable & friendly','tight, skimmable, and friendly — a real morning briefing, not a wall of text'],
    ['Warm & conversational','warm and conversational, like a friend catching you up'],
    ['Punchy & brief','punchy and brief — the fewest words that still inform'],
    ['Calm & reflective','calm and reflective, unhurried'],
    ['Just the facts','neutral and factual, no fluff']
  ];
  var HOURS=[[5,'5:00 AM'],[6,'6:00 AM'],[7,'7:00 AM'],[8,'8:00 AM'],[9,'9:00 AM'],[10,'10:00 AM']];
  function defaultSections(){return [
    {key:'weather',icon:'🌤️',label:'Weather',enabled:true,want:"NYC today: current temp, high/low, rain/snow chance, and a one-line 'what to wear/bring'."},
    {key:'headlines',icon:'🗞️',label:'Headlines',enabled:true,want:"4-5 top stories (US/world + anything major NYC-specific), one line each, as '• ' bullets."},
    {key:'transit',icon:'🚇',label:'Getting around',enabled:true,want:'any notable MTA subway service changes/major delays today (skip if nothing notable).'},
    {key:'nyc',icon:'🎉',label:'NYC today',enabled:true,want:'one or two notable things happening in the city today.'},
    {key:'nugget',icon:'💡',label:'Nugget',enabled:true,want:'one useful/interesting thing to start the day.'}
  ];}
  function fillSel(id,items,cur){var s=document.getElementById(id);s.innerHTML='';
    var arr=items.slice(),found=false;
    arr.forEach(function(it){if(String(it[1])===String(cur))found=true;});
    if(cur!=null&&cur!==''&&!found)arr.unshift([cur,String(cur)]);
    arr.forEach(function(it){var o=document.createElement('option');o.value=it[1];o.textContent=it[0];
      if(String(it[1])===String(cur))o.selected=true;s.appendChild(o);});}
  function open(){
    document.getElementById('rsName').textContent=rep.title||'Daily report';
    fillSel('rsGreet',GREETS.map(function(g){return [g,g];}),rep.greeting||GREETS[0]);
    fillSel('rsTone',TONES,rep.tone||TONES[0][1]);
    fillSel('rsHour',HOURS.map(function(h){return [h[1],h[0]];}),(rep.deliver_hour_et!=null?rep.deliver_hour_et:8));
    drawSecs();modal.hidden=false;
  }
  function close(){modal.hidden=true;}
  function startEdit(d){
    cfg=(d&&d.reports)?d:{version:1,reports:[]};
    rep=cfg.reports[0];
    if(!rep){rep={id:'nyc-digest',title:'NYC Daily Digest',greeting:GREETS[0],tone:TONES[0][1],deliver_hour_et:8,sections:defaultSections()};cfg.reports.push(rep);}
    if(!rep.sections||!rep.sections.length)rep.sections=defaultSections();  // never show a blank editor
    open();
  }
  document.getElementById('rpEdit').onclick=function(){
    fetch('api/report-config',{cache:'no-store'}).then(function(r){return r.json();}).then(startEdit)
      .catch(function(){startEdit(null);});  // offline/empty → seed defaults so it still works
  };
  document.getElementById('rsClose').onclick=close;
  document.getElementById('rsCancel').onclick=close;
  modal.onclick=function(e){if(e.target===modal)close();};
  document.getElementById('rsAdd').onclick=function(){
    if(!rep)return;rep.sections=rep.sections||[];
    rep.sections.push({key:uid(),icon:'•',label:'New section',enabled:true,want:''});drawSecs();
    var last=secBox.lastChild;if(last){var lbl=last.querySelector('.rs-label');if(lbl)lbl.focus();}
  };
  document.getElementById('rsSave').onclick=function(){
    rep.greeting=document.getElementById('rsGreet').value;
    rep.tone=document.getElementById('rsTone').value;
    var h=parseInt(document.getElementById('rsHour').value,10);rep.deliver_hour_et=(isNaN(h)?8:Math.max(0,Math.min(23,h)));
    var btn=document.getElementById('rsSave');btn.disabled=true;btn.textContent='Saving…';
    fetch('api/report-config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cfg)})
      .then(function(r){return r.json();}).then(function(d){
        btn.disabled=false;btn.textContent='Save report';
        if(d&&d.ok){close();}else{alert('Save failed: '+((d&&d.error)||'unknown'));}
      }).catch(function(){btn.disabled=false;btn.textContent='Save report';alert('Save failed.');});
  };
})();
// ---- Foreman mission control: per-project kanban + job detail modal ----
(function(){
  var boardEl=document.getElementById('fmBoard'),statsEl=document.getElementById('fmStats'),
      modalEl=document.getElementById('fmModal'),heartEl=document.getElementById('fmHeart');
  if(!boardEl)return;
  var rank={running:0,queued:1,failed:2,done:3};
  var byId={}, openId=null;   // latest job snapshots + which one the modal shows
  var view='running', lastD=null;   // board filter: show only running by default
  function fmt(s){s=s||0;if(s<60)return s+'s';var m=Math.floor(s/60);if(m<60)return m+'m '+(s%60)+'s';var h=Math.floor(m/60);return h+'h '+(m%60)+'m';}
  function esc(s){return (s||'').replace(/[&<>]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;'}[c];});}
  function when(ms){if(!ms)return '—';try{return new Date(ms).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'});}catch(e){return '—';}}
  function docBadge(j,cls){
    if(j.doctor===true)return '<span class="'+cls+' ok">✓ verified</span>';
    if(j.doctor===false)return '<span class="'+cls+' bad">✗ '+esc(j.doctorNote||'failed')+'</span>';
    if(j.status==='done'&&j.doctor==='pending')return '<span class="'+cls+' pending">· checking…</span>';
    return '';
  }
  var HEART='<svg viewBox="0 0 24 24" fill="#ec4899"><path d="M12 21s-7.5-4.6-10-9.3C.3 8.4 2 5 5.3 5c2 0 3.4 1.1 4.2 2.3C10.3 6.1 11.7 5 13.7 5 17 5 18.7 8.4 17 11.7 14.5 16.4 12 21 12 21z"/></svg>';
  function ago(ms){if(!ms)return '—';var s=Math.max(0,Math.round((Date.now()-ms)/1000));return s<60?s+'s ago':Math.floor(s/60)+'m ago';}
  function drawHeart(hb){
    if(!heartEl)return;
    if(!hb||!hb.ts){heartEl.hidden=true;return;}
    heartEl.hidden=false;
    function v(cls,n,lbl){return '<span class="hbv '+cls+'"><i></i><b>'+(n||0)+'</b> '+lbl+'</span>';}
    var stuck=(hb.stuck&&hb.stuck.length)?'<span class="hbstuck">⚠ '+hb.stuck.length+' stuck</span>':'';
    heartEl.innerHTML='<span class="hb">'+HEART+'Heartbeat</span>'
      +v('run',hb.running,'running')
      +v('ver',hb.verifying,'verifying')
      +v('ok',hb.healthy,'healthy')
      +v('bad',hb.failing,'failing')
      +stuck
      +'<span class="hbt">beat #'+(hb.beats||0)+' · '+ago(hb.ts)+'</span>';
  }
  function accSummary(j){
    var a=j.acceptance||[];if(!a.length)return null;
    var met=0,bad=0;a.forEach(function(x){if(x.ok===true)met++;else if(x.ok===false)bad++;});
    return {cls:bad?'bad':(met===a.length?'ok':'pending'),met:met,total:a.length};
  }
  function accList(a){
    return '<div class="fm-acc">'+a.map(function(x){
      var mk=x.ok===true?'<span class="mk ok">✓</span>':(x.ok===false?'<span class="mk bad">✗</span>':'<span class="mk pending">·</span>');
      return '<div class="fm-acc-item">'+mk+'<div>'+esc(x.text)+(x.why?' <span class="why">— '+esc(x.why)+'</span>':'')+'</div></div>';
    }).join('')+'</div>';
  }
  // --- compact card: the basics + status, click to open the full modal ---
  function card(j){
    var el=(j.status==='running')?fmt(j.elapsed):((j.status==='done'||j.status==='failed')?('took '+fmt(j.elapsed)):'');
    var doc = j.doctor===true?'<span class="fm-doc ok">✓ verified</span>'
            : j.doctor===false?'<span class="fm-doc bad">✗ '+esc(j.doctorNote||'doctor failed')+'</span>'
            : (j.status==='done'&&j.doctor==='pending')?'<span class="fm-doc pending">· checking…</span>':'';
    var ini=(((j.project||'?').trim().charAt(0))||'?').toUpperCase();
    var av=j.avatar?('<img class="fm-avatar-img '+j.status+'" src="'+esc(j.avatar)+'" alt="" loading="lazy">')
                   :j.icon?('<span class="fm-avatar-svg '+j.status+'">'+j.icon+'</span>')
                   :('<span class="fm-avatar '+j.status+'">'+esc(ini)+'</span>');
    return '<div class="fm-job" data-id="'+esc(j.id)+'" role="button" tabindex="0" aria-label="Open job details">'
      +'<div class="fm-head">'
        +av
        +'<div class="fm-title">'+esc(j.title||j.task||j.label||'(no task)')+'</div>'
        +'<span class="fm-chev" aria-hidden="true">›</span>'
      +'</div>'
      +'<div class="fm-meta">'
        +'<span class="fm-badge '+j.status+'">'+j.status+'</span>'
        +doc
        +'<span class="fm-elapsed">'+el+'</span>'
      +'</div>'
      +'<div class="fm-progress '+j.status+'"><i></i></div>'
      +checksRow(j)
      +(j.evidence?'<div class="fm-ev-thumb" data-ev="'+esc(j.id)+'"><img src="'+esc(j.evidence)+'" alt="evidence" loading="lazy"></div>':'')
      +(j.result?'<div class="fm-result">↳ '+esc(j.result)+'</div>':'')
      +'</div>';
  }
  function checksRow(j){
    var out='';
    if(j.tests&&j.tests.cmd){
      var tk=j.tests.ok===true?'ok':(j.tests.ok===false?'bad':'pending');
      var tm=j.tests.ok===true?'✓ tests pass':(j.tests.ok===false?'✗ tests fail':'· tests');
      out+='<span class="fm-pill '+tk+'" title="'+esc(j.tests.cmd||'')+'">'+tm+'</span>';
    }
    var as=accSummary(j);
    if(as){var am=as.cls==='ok'?'✓':(as.cls==='bad'?'✗':'·');
      out+='<span class="fm-pill '+as.cls+'">'+am+' '+as.met+'/'+as.total+' criteria</span>';}
    if(j.evidence)out+='<span class="fm-pill ev" data-ev="'+esc(j.id)+'">📷 evidence</span>';
    return out?'<div class="fm-checks">'+out+'</div>':'';
  }
  function draw(d){
    lastD=d;
    var jobs=d.jobs||[],s=d.stats||{};
    drawHeart(d.heartbeat);
    byId={};jobs.forEach(function(j){byId[j.id]=j;});
    function metric(n,lbl,fail){return '<div class="fm-metric'+(fail?' fail':'')+'"><b>'+(n||0)+'</b><span>'+lbl+'</span></div>';}
    statsEl.innerHTML=metric(s.running,'running')+metric(s.queued,'queued')+metric(s.done,'done')+((s.failed||0)?metric(s.failed,'failed',1):'');
    var shown=(view==='running')?jobs.filter(function(j){return j.status==='running';}):jobs;
    if(!shown.length){boardEl.innerHTML='<div class="fm-empty">'+(view==='running'?'Nothing running right now — switch to <b>All</b> to see recent jobs.':'No subagents yet — send a task in Telegram and watch them light up here.')+'</div>';}
    else{
      var groups={},colors={};
      shown.forEach(function(j){(groups[j.project]=groups[j.project]||[]).push(j);colors[j.project]=j.color||'#94a3b8';});
      var order=[],seen={};
      (d.roster||[]).forEach(function(p){if(groups[p.name]&&!seen[p.name]){order.push(p.name);seen[p.name]=1;colors[p.name]=colors[p.name]||p.color;}});
      Object.keys(groups).forEach(function(n){if(!seen[n]){order.push(n);seen[n]=1;}});
      boardEl.innerHTML=order.map(function(name){
        var g=groups[name].slice().sort(function(a,b){return (rank[a.status]-rank[b.status])||((b.created||0)-(a.created||0));});
        var live=g.filter(function(j){return j.status==='running';}).length;
        return '<div class="fm-group" style="--accent:'+esc(colors[name])+'">'
          +'<div class="fm-col-head"><span class="fm-chip"></span>'
          +'<span class="fm-col-name">'+esc(name)+'</span>'
          +'<span class="fm-col-count">'+(live?live+' live · ':'')+g.length+'</span></div>'
          +'<div class="fm-col-body">'+g.map(card).join('')+'</div></div>';
      }).join('');
    }
    if(openId&&byId[openId])renderModal(byId[openId]);  // keep an open modal live
  }
  // --- the modal: full query, full result, every status detail ---
  function kv(k,v){return '<div class="fm-m-kv"><span>'+k+'</span><b>'+v+'</b></div>';}
  function renderModal(j){
    var box=modalEl.firstElementChild;
    box.style.setProperty('--accent',j.color||'#2563eb');
    var dur=j.status==='running'?(fmt(j.elapsed)+' (running)'):(j.status==='queued'?'—':'took '+fmt(j.elapsed));
    box.innerHTML=
      '<div class="fm-m-strip"></div>'
      +'<div class="fm-m-head">'
        +'<span class="fm-chip" style="--accent:'+esc(j.color||'#2563eb')+'"></span>'
        +'<span class="fm-m-proj">'+esc(j.project)+'</span>'
        +'<span class="fm-badge '+j.status+'">'+j.status+'</span>'
        +docBadge(j,'fm-m-doc')
        +'<button class="fm-m-x" data-close="1" aria-label="Close">✕</button>'
      +'</div>'
      +'<div class="fm-m-meta">'
        +kv('Label',esc(j.label||'—'))
        +kv('Model',esc((j.model||'—').replace(/^.*\//,'')))
        +kv('Mode',esc(j.mode||'—'))
        +kv('Requester',esc(j.requester||'—'))
        +kv('Duration',dur)
        +kv('Started',when(j.started))
        +kv('Created',when(j.created))
        +kv('Ended',when(j.ended))
      +'</div>'
      +'<div class="fm-m-section"><h4>Query</h4><pre>'+esc(j.taskFull||j.task||'—')+'</pre></div>'
      +((j.acceptance&&j.acceptance.length)?'<div class="fm-m-section"><h4>Acceptance criteria'+(accSummary(j)?' · '+accSummary(j).met+'/'+accSummary(j).total+' met':'')+'</h4>'+accList(j.acceptance)+'</div>':'')
      +((j.tests&&j.tests.cmd)?'<div class="fm-m-section"><h4>Pipeline test</h4><pre>'+esc(j.tests.cmd)+'\n→ '+(j.tests.ok===true?'PASS':(j.tests.ok===false?'FAIL — '+esc(j.tests.note||''):'skipped'))+'</pre></div>':'')
      +(j.evidence?'<div class="fm-m-section"><h4>Photo evidence</h4><a href="'+esc(j.evidence)+'" target="_blank" rel="noopener" class="fm-ev-thumb" style="max-width:100%"><img src="'+esc(j.evidence)+'" alt="evidence"></a></div>':'')
      +((j.resultFull||j.result)?'<div class="fm-m-section"><h4>Result</h4><pre>'+esc(j.resultFull||j.result)+'</pre></div>'
         :(j.status==='running'?'<div class="fm-m-section"><h4>Result</h4><pre>· still running…</pre></div>':''));
    modalEl.hidden=false;
  }
  function closeModal(){openId=null;modalEl.hidden=true;}
  function openFromEl(c){if(!c)return;openId=c.getAttribute('data-id');if(byId[openId])renderModal(byId[openId]);}
  var filterEl=document.getElementById('fmFilter');
  if(filterEl)filterEl.addEventListener('click',function(ev){
    var b=ev.target.closest('button[data-view]');if(!b)return;
    view=b.getAttribute('data-view');
    Array.prototype.forEach.call(filterEl.children,function(c){c.classList.toggle('on',c===b);});
    if(lastD)draw(lastD);
  });
  boardEl.addEventListener('click',function(ev){openFromEl(ev.target.closest('.fm-job'));});
  boardEl.addEventListener('keydown',function(ev){
    if(ev.key!=='Enter'&&ev.key!==' ')return;
    var c=ev.target.closest('.fm-job');if(!c)return;
    ev.preventDefault();openFromEl(c);
  });
  modalEl.addEventListener('click',function(ev){
    if(ev.target===modalEl||ev.target.closest('[data-close]'))closeModal();
  });
  document.addEventListener('keydown',function(e){if(e.key==='Escape')closeModal();});
  function tick(){fetch('api/foreman',{cache:'no-store'}).then(function(r){return r.json();}).then(draw).catch(function(){});}
  tick();setInterval(tick,2500);
})();
</script>
</body>
</html>'''

HERE = os.path.dirname(os.path.abspath(__file__))
# Shared data (same box): the daily reports + the report template + the shared
# to-do list. Dash reads/writes these directly so widgets never depend on the
# (separately-running) reports portal service.
REPORTS_DIR   = "/root/MonoClaw/portal/reports"
REPORT_CONFIG = "/root/MonoClaw/portal/data/report_config.json"
SHARED_TODO   = "/root/MonoClaw/portal/data/todo.json"


def latest_report(kind="daily"):
    """Most-recent report JSON. kind='daily' skips the *-nightsweep.json files."""
    try:
        files = [f for f in os.listdir(REPORTS_DIR) if f.endswith(".json")]
    except OSError:
        return None
    if kind == "daily":
        files = [f for f in files if "nightsweep" not in f]
    files.sort(reverse=True)
    for fn in files:
        try:
            with open(os.path.join(REPORTS_DIR, fn)) as f:
                r = json.load(f)
            r["id"] = fn[:-5]
            return r
        except Exception:
            continue
    return None


def read_report_config():
    try:
        with open(REPORT_CONFIG) as f:
            return json.load(f)
    except Exception:
        return {"version": 1, "reports": []}


def write_report_config(cfg):
    """Validate lightly, then atomically write the report template config."""
    if not isinstance(cfg, dict) or not isinstance(cfg.get("reports"), list):
        raise ValueError("config must have a 'reports' list")
    for r in cfg["reports"]:
        if not isinstance(r, dict) or not r.get("id"):
            raise ValueError("each report needs an id")
        secs = r.get("sections")
        if secs is not None and not isinstance(secs, list):
            raise ValueError("sections must be a list")
    os.makedirs(os.path.dirname(REPORT_CONFIG), exist_ok=True)
    tmp = REPORT_CONFIG + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, REPORT_CONFIG)


def read_todos():
    try:
        with open(SHARED_TODO) as f:
            d = json.load(f)
        return d.get("todos", []) if isinstance(d, dict) else []
    except Exception:
        return []


def write_todos(todos):
    if not isinstance(todos, list):
        raise ValueError("todos must be a list")
    clean = []
    for t in todos[:200]:
        if not isinstance(t, dict):
            continue
        clean.append({"id": str(t.get("id") or int(time.time() * 1000)),
                      "text": str(t.get("text") or "")[:400],
                      "done": bool(t.get("done"))})
    os.makedirs(os.path.dirname(SHARED_TODO), exist_ok=True)
    tmp = SHARED_TODO + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"todos": clean}, f, ensure_ascii=False)
    os.replace(tmp, SHARED_TODO)
    return clean


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
        self.send_header('Cache-Control', 'no-store, must-revalidate')
        self.send_header('Access-Control-Allow-Origin', '*')
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
        elif p.startswith('/avatars/') and p.endswith('.png'):
            name = os.path.basename(p)
            try:
                with open(os.path.join(_AVATAR_DIR, name), 'rb') as f:
                    self._send(f.read(), 'image/png')
            except OSError:
                self.send_response(404); self.end_headers(); self.wfile.write(b'not found')
        elif p.startswith('/evidence/') and p.endswith('.png'):
            name = os.path.basename(p)
            try:
                with open(os.path.join(os.path.dirname(ROSTER_PATH), 'data', 'evidence', name), 'rb') as f:
                    self._send(f.read(), 'image/png')
            except OSError:
                self.send_response(404); self.end_headers(); self.wfile.write(b'not found')
        elif p == '/api/events-widget':
            # same-origin proxy to Marquee (nyc-events) so the dash widget avoids CORS
            try:
                with urllib.request.urlopen('http://127.0.0.1:18852/api/widget', timeout=6) as r:
                    self._send(r.read(), 'application/json; charset=utf-8')
            except Exception:
                self._send('{"events":[]}', 'application/json; charset=utf-8')
        elif p == '/api/foreman':
            self._send(json.dumps(foreman_data()), 'application/json; charset=utf-8')
        elif p == '/api/report-latest':
            self._send(json.dumps({"report": latest_report("daily")}), 'application/json; charset=utf-8')
        elif p.startswith('/report-audio/') and p.endswith('.mp3'):
            name = os.path.basename(p)
            try:
                with open(os.path.join('/root/MonoClaw/media/tts', name), 'rb') as f:
                    data = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'audio/mpeg')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers(); self.wfile.write(data)
            except OSError:
                self.send_response(404); self.end_headers(); self.wfile.write(b'not found')
        elif p == '/api/report-config':
            self._send(json.dumps(read_report_config()), 'application/json; charset=utf-8')
        elif p == '/api/todo':
            self._send(json.dumps({"todos": read_todos()}), 'application/json; charset=utf-8')
        elif p in ('/health', '/healthz'):
            self._send('ok', 'text/plain')
        else:
            self.send_response(404); self.end_headers(); self.wfile.write(b'not found')

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def _body(self):
        try:
            n = int(self.headers.get('Content-Length') or 0)
            return json.loads(self.rfile.read(n) or b'{}')
        except Exception:
            return {}

    def do_POST(self):
        p = self._route()
        if p == '/api/report-config':
            try:
                write_report_config(self._body())
                self._send(json.dumps({"ok": True}), 'application/json; charset=utf-8')
            except Exception as e:
                self.send_response(400); self.send_header('Content-Type', 'application/json'); self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        elif p == '/api/todo':
            try:
                saved = write_todos((self._body() or {}).get("todos", []))
                self._send(json.dumps({"ok": True, "todos": saved}), 'application/json; charset=utf-8')
            except Exception as e:
                self.send_response(400); self.send_header('Content-Type', 'application/json'); self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(404); self.end_headers(); self.wfile.write(b'not found')

if __name__ == '__main__':
    print(f"App Hub on :{PORT} base='{BASE or '/'}'")
    ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()

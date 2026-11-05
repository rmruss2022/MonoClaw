#!/usr/bin/env python3
"""Foreman doctor + heartbeat — the supervisor half of Foreman.

A subagent "finishing" only means the agent stopped. The doctor turns that into a
real, evidence-backed verdict and keeps a live heartbeat over every job:

  1. PIPELINE TEST  — run the project's doctorCmd (tsc / npm run check /
     py_compile …) in the repo. Red = not done.
  2. PHOTO EVIDENCE — screenshot the project's live URL (evidence_shot.js) and
     save it as proof the app actually runs.
  3. ACCEPTANCE     — load the job's acceptance criteria (data/jobs.json, set at
     intake by job.py) and verify EACH one against the screenshot + test output
     with Gemini vision. Every criterion must hold.

The overall verdict = tests pass AND acceptance holds. The Dash board renders the
test badge, the acceptance checklist, and the evidence thumbnail.

HEARTBEAT: every pass the doctor also writes data/heartbeat.json — a health
summary over all jobs (running / verifying / healthy / failing) plus any stuck
runs (running longer than FOREMAN_STUCK_MIN). The Dash shows a live pulse.

Design (deliberately thin, no new Python deps):
  * read-only on OpenClaw's canonical subagent_runs table (source of truth);
  * verdicts + jobs + heartbeat live in their OWN json stores under data/, keyed
    by run_id (verdicts) or label (jobs) — we never write the OpenClaw DB;
  * each finished job is doctored exactly once; the heartbeat recomputes cheaply
    every pass.

Runs as the foreman-doctor.service systemd unit (sequential — one verification at
a time so heavy tsc runs + screenshots never pile up).
"""
import base64, json, os, sqlite3, subprocess, sys, time, tempfile, urllib.request

STATE_DB   = os.environ.get("OPENCLAW_STATE_DB", "/root/.openclaw/state/openclaw.sqlite")
ROSTER     = os.environ.get("FOREMAN_ROSTER", "/root/MonoClaw/foreman/projects.json")
DATA_DIR   = os.environ.get("FOREMAN_DATA", "/root/MonoClaw/foreman/data")
HERE       = os.path.dirname(os.path.abspath(__file__))
VERDICTS   = os.path.join(DATA_DIR, "verdicts.json")
JOBS       = os.path.join(DATA_DIR, "jobs.json")
HEARTBEAT  = os.path.join(DATA_DIR, "heartbeat.json")
EVIDENCE   = os.path.join(DATA_DIR, "evidence")
SHOT_JS    = os.path.join(HERE, "evidence_shot.js")
POLL_SEC   = int(os.environ.get("FOREMAN_DOCTOR_POLL", "12"))
TIMEOUT    = int(os.environ.get("FOREMAN_DOCTOR_TIMEOUT", "300"))   # per doctor run
WINDOW_H   = float(os.environ.get("FOREMAN_DOCTOR_WINDOW_H", "12")) # only doctor jobs ended within N hours
STUCK_MIN  = float(os.environ.get("FOREMAN_STUCK_MIN", "30"))       # running longer => stuck
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def roster():
    """slug -> {name, repoDir, doctorCmd, url}. Reloaded each pass so roster
    edits take effect without a restart."""
    try:
        with open(ROSTER) as f:
            return {p["slug"]: p for p in (json.load(f).get("projects") or []) if p.get("slug")}
    except Exception as e:
        log("roster load failed:", e)
        return {}


def slug_of(label, workspace_dir, by_slug):
    """Resolve a job to a roster slug: prefer the 'slug:jobid' label prefix,
    else the workspace folder basename."""
    if label and ":" in label:
        key = label.split(":", 1)[0]
        if key in by_slug:
            return key
    if workspace_dir:
        key = os.path.basename(workspace_dir.rstrip("/"))
        if key in by_slug:
            return key
    return None


def _load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def _save(path, obj):
    os.makedirs(DATA_DIR, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)  # atomic


def db_rows(where, params):
    try:
        con = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True, timeout=1.5)
        rows = con.execute(
            "SELECT run_id, label, workspace_dir, started_at, ended_at FROM subagent_runs "
            + where, params).fetchall()
        con.close()
        return rows
    except Exception as e:
        log("state db read failed:", e)
        return []


def done_jobs():
    """Finished runs within the window, newest first."""
    cutoff = (time.time() - WINDOW_H * 3600) * 1000
    return db_rows("WHERE ended_at IS NOT NULL AND ended_at >= ? ORDER BY ended_at DESC LIMIT 100", (cutoff,))


def running_jobs():
    """Currently-running runs (not ended)."""
    return db_rows("WHERE ended_at IS NULL ORDER BY started_at DESC LIMIT 50", ())


# --------------------------------------------------------------- pipeline test
def short_note(ok, out):
    if ok:
        return "ok"
    lines = [l.strip() for l in (out or "").splitlines() if l.strip()]
    note = lines[-1] if lines else "doctor failed"
    return note[:157] + "…" if len(note) > 158 else note


def run_doctor(proj):
    """Run one project's doctorCmd in its repoDir. Returns (ok|None, note, out)."""
    repo, cmd = proj.get("repoDir"), proj.get("doctorCmd")
    if not cmd:
        return None, "no doctorCmd", ""
    if not repo or not os.path.isdir(repo):
        return None, "repo dir missing", ""
    try:
        p = subprocess.run(cmd, cwd=repo, shell=True, timeout=TIMEOUT,
                           capture_output=True, text=True)
        out = (p.stdout or "") + "\n" + (p.stderr or "")
        ok = p.returncode == 0
        return ok, short_note(ok, out), out[-4000:]
    except subprocess.TimeoutExpired:
        return False, f"timed out after {TIMEOUT}s", ""
    except Exception as e:
        return None, f"could not run: {e}"[:158], ""


# --------------------------------------------------------------- photo evidence
def capture_evidence(proj, run_id):
    """Screenshot the project's live URL as proof. Returns relative path or None."""
    url = proj.get("url")
    if not url:
        return None
    os.makedirs(EVIDENCE, exist_ok=True)
    out = os.path.join(EVIDENCE, run_id + ".png")
    try:
        subprocess.run(["node", SHOT_JS, url, out], timeout=75,
                       capture_output=True, text=True)
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            return "evidence/" + run_id + ".png"
    except Exception as e:
        log("  evidence failed:", e)
    return None


# --------------------------------------------------------------- acceptance (LLM)
def verify_acceptance(task, criteria, tests_note, evidence_abspath):
    """Verify each acceptance criterion with Gemini (vision if a screenshot
    exists). Returns (list[{text,ok,why}], acceptance_ok|None)."""
    if not criteria:
        return [], None
    if not GEMINI_KEY:
        return [{"text": c, "ok": None, "why": "LLM not configured"} for c in criteria], None
    numbered = "\n".join(f"{i+1}. {c}" for i, c in enumerate(criteria))
    prompt = (
        "You are the QA gate for a software job. Judge whether each acceptance "
        "criterion is met, using the attached screenshot of the live app plus the "
        "pipeline-test result. Be strict but fair: if the screenshot can't confirm "
        "a criterion, mark ok=false with a short reason.\n\n"
        f"JOB: {task}\n"
        f"PIPELINE TEST: {tests_note}\n\n"
        f"ACCEPTANCE CRITERIA:\n{numbered}\n\n"
        "Reply with ONLY a JSON array, one object per criterion in order: "
        '[{"ok": true|false, "why": "<=12 words"}]. No prose.'
    )
    parts = [{"text": prompt}]
    if evidence_abspath and os.path.exists(evidence_abspath):
        try:
            b64 = base64.b64encode(open(evidence_abspath, "rb").read()).decode()
            parts.append({"inline_data": {"mime_type": "image/png", "data": b64}})
        except Exception:
            pass
    try:
        url = ("https://generativelanguage.googleapis.com/v1beta/models/"
               + GEMINI_MODEL + ":generateContent?key=" + GEMINI_KEY)
        body = json.dumps({"contents": [{"parts": parts}],
                           "generationConfig": {"maxOutputTokens": 400, "temperature": 0.1,
                                                "thinkingConfig": {"thinkingBudget": 0}}}).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        j = json.loads(urllib.request.urlopen(req, timeout=50).read())
        txt = "".join(p.get("text", "") for p in
                      ((j["candidates"][0].get("content") or {}).get("parts") or []))
        s = txt.strip()
        a = s.find("["); b = s.rfind("]")
        arr = json.loads(s[a:b + 1]) if a >= 0 and b > a else []
    except Exception as e:
        log("  acceptance LLM failed:", e)
        return [{"text": c, "ok": None, "why": "verify error"} for c in criteria], None
    out = []
    for i, c in enumerate(criteria):
        v = arr[i] if i < len(arr) and isinstance(arr[i], dict) else {}
        ok = v.get("ok")
        out.append({"text": c, "ok": bool(ok) if ok is not None else None,
                    "why": str(v.get("why", ""))[:120]})
    oks = [o["ok"] for o in out]
    acc_ok = True if oks and all(x is True for x in oks) else (
        False if any(x is False for x in oks) else None)
    return out, acc_ok


def combine(tests_ok, acc_ok):
    if tests_ok is False or acc_ok is False:
        return False
    if tests_ok is True or acc_ok is True:
        return True
    return None


# ------------------------------------------------------------------- heartbeat
def write_heartbeat(by_slug, verdicts):
    """Health summary over all jobs — running / verifying / healthy / failing +
    stuck detection. Cheap; runs every pass."""
    now = time.time()
    running, stuck = 0, []
    for run_id, label, ws, started, ended in running_jobs():
        running += 1
        mins = (now - (started or now * 1000) / 1000) / 60 if started else 0
        if mins >= STUCK_MIN:
            stuck.append({"label": label or (run_id or "")[:8], "mins": round(mins)})
    healthy = sum(1 for v in verdicts.values() if v.get("ok") is True)
    failing = sum(1 for v in verdicts.values() if v.get("ok") is False)
    # verifying = finished jobs with a doctorCmd but no verdict yet (within window)
    verifying = 0
    for run_id, label, ws, started, ended in done_jobs():
        if run_id and run_id not in verdicts:
            slug = slug_of(label or "", ws or "", by_slug)
            if slug and by_slug[slug].get("doctorCmd"):
                verifying += 1
    hb = _load(HEARTBEAT, {})
    beats = int(hb.get("beats", 0)) + 1
    _save(HEARTBEAT, {
        "ts": int(now * 1000), "beats": beats,
        "running": running, "verifying": verifying,
        "healthy": healthy, "failing": failing,
        "stuck": stuck, "poll_sec": POLL_SEC,
    })


# ----------------------------------------------------------------------- pass
def verify_one(run_id, label, workspace, by_slug, verdicts, jobs):
    slug = slug_of(label or "", workspace or "", by_slug)
    if not slug:
        return False
    proj = by_slug[slug]
    criteria = (jobs.get(label or "") or {}).get("acceptance") or []
    if not proj.get("doctorCmd") and not criteria:
        return False  # nothing to verify -> leave unbadged
    job = jobs.get(label or "") or {}
    task = job.get("task") or (label or "")
    log(f"verifying {slug} :: {label or run_id[:8]}  (criteria: {len(criteria)})")

    tests_ok, tests_note, tests_out = run_doctor(proj)
    evidence = capture_evidence(proj, run_id)
    ev_abs = os.path.join(DATA_DIR, evidence) if evidence else None
    acc, acc_ok = verify_acceptance(task, criteria, tests_note, ev_abs)
    overall = combine(tests_ok, acc_ok)

    verdicts[run_id] = {
        "ok": overall, "project": proj.get("name", slug),
        "note": tests_note if tests_ok is not True else (
            "all criteria met" if acc_ok else tests_note),
        "cmd": proj.get("doctorCmd"),
        "tests": {"ok": tests_ok, "note": tests_note, "cmd": proj.get("doctorCmd")},
        "evidence": evidence,
        "acceptance": acc, "acceptance_ok": acc_ok,
        "task": task, "ts": int(time.time() * 1000),
    }
    log(f"  -> tests={tests_ok} acceptance={acc_ok} overall={overall} evidence={'yes' if evidence else 'no'}")
    return True


def pass_once():
    by_slug = roster()
    if not by_slug:
        return
    verdicts = _load(VERDICTS, {})
    jobs = _load(JOBS, {})
    changed = False
    for run_id, label, workspace, started, ended in done_jobs():
        if not run_id or run_id in verdicts:
            continue
        try:
            if verify_one(run_id, label, workspace, by_slug, verdicts, jobs):
                changed = True
                _save(VERDICTS, verdicts)  # persist each verdict as it lands
        except Exception as e:
            log("  verify error:", e)
    try:
        write_heartbeat(by_slug, verdicts)
    except Exception as e:
        log("heartbeat error:", e)


def main():
    log(f"foreman-doctor+heartbeat up — poll {POLL_SEC}s, timeout {TIMEOUT}s, "
        f"window {WINDOW_H}h, stuck>{STUCK_MIN}m, llm={'on' if GEMINI_KEY else 'off'}")
    if "--once" in sys.argv:
        pass_once(); return
    while True:
        try:
            pass_once()
        except Exception as e:
            log("pass error:", e)
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()

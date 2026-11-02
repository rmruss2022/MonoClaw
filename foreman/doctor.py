#!/usr/bin/env python3
"""Foreman doctor — the supervisor half of Foreman (Phase 2).

When a subagent job finishes, "completed" only means the agent stopped. The
doctor turns that into a real verdict: it runs the job's project `doctorCmd`
(tsc / build / py_compile / health-check from foreman/projects.json) inside the
project repo and stamps the result, which the Dash board renders as a badge on
the card: ✓ verified / ✗ <reason> / · checking…

Design (deliberately thin, no new deps):
  * read-only on OpenClaw's canonical subagent_runs table (source of truth);
  * verdicts live in their OWN store (foreman/data/verdicts.json) keyed by
    run_id, so each job is doctored exactly once and we never write to the
    OpenClaw DB;
  * the Dash endpoint (portfolio/server.py) merges this store in and shows
    "· checking…" for any done job that has a doctorCmd but no verdict yet.

Run as the foreman-doctor.service systemd unit (a gentle ~12s poll loop,
sequential — one doctor at a time so heavy tsc runs never pile up).
"""
import json, os, sqlite3, subprocess, sys, time, tempfile

STATE_DB   = os.environ.get("OPENCLAW_STATE_DB", "/root/.openclaw/state/openclaw.sqlite")
ROSTER     = os.environ.get("FOREMAN_ROSTER", "/root/MonoClaw/foreman/projects.json")
DATA_DIR   = os.environ.get("FOREMAN_DATA", "/root/MonoClaw/foreman/data")
VERDICTS   = os.path.join(DATA_DIR, "verdicts.json")
POLL_SEC   = int(os.environ.get("FOREMAN_DOCTOR_POLL", "12"))
TIMEOUT    = int(os.environ.get("FOREMAN_DOCTOR_TIMEOUT", "300"))   # per doctor run
WINDOW_H   = float(os.environ.get("FOREMAN_DOCTOR_WINDOW_H", "12")) # only doctor jobs ended within N hours


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def roster():
    """slug -> {name, repoDir, doctorCmd}. Reloaded each pass so edits to the
    roster take effect without a restart."""
    try:
        with open(ROSTER) as f:
            return {p["slug"]: p for p in (json.load(f).get("projects") or []) if p.get("slug")}
    except Exception as e:
        log("roster load failed:", e)
        return {}


def slug_of(label, workspace_dir, by_slug):
    """Resolve a job to a roster slug: prefer the 'slug:jobid' label prefix,
    else the workspace folder basename. Mirrors portfolio/server.py._project_of."""
    if label and ":" in label:
        key = label.split(":", 1)[0]
        if key in by_slug:
            return key
    if workspace_dir:
        key = os.path.basename(workspace_dir.rstrip("/"))
        if key in by_slug:
            return key
    return None


def load_verdicts():
    try:
        with open(VERDICTS) as f:
            return json.load(f)
    except Exception:
        return {}


def save_verdicts(v):
    os.makedirs(DATA_DIR, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(v, f, indent=1)
    os.replace(tmp, VERDICTS)  # atomic


def done_jobs():
    """Finished runs within the window, newest first: (run_id, label, workspace, ended_ms)."""
    cutoff = (time.time() - WINDOW_H * 3600) * 1000
    try:
        con = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True, timeout=1.5)
        rows = con.execute(
            "SELECT run_id, label, workspace_dir, ended_at FROM subagent_runs "
            "WHERE ended_at IS NOT NULL AND ended_at >= ? ORDER BY ended_at DESC LIMIT 100",
            (cutoff,)).fetchall()
        con.close()
        return rows
    except Exception as e:
        log("state db read failed:", e)
        return []


def short_note(ok, out):
    if ok:
        return ""
    lines = [l.strip() for l in (out or "").splitlines() if l.strip()]
    note = lines[-1] if lines else "doctor failed"
    return note[:157] + "…" if len(note) > 158 else note


def run_doctor(proj):
    """Run one project's doctorCmd in its repoDir. Returns (ok|None, note).
    ok=None means "skipped" (no badge) — e.g. the repo dir is gone."""
    repo, cmd = proj.get("repoDir"), proj.get("doctorCmd")
    if not cmd:
        return None, "no doctorCmd"
    if not repo or not os.path.isdir(repo):
        return None, "repo dir missing"
    try:
        p = subprocess.run(cmd, cwd=repo, shell=True, timeout=TIMEOUT,
                           capture_output=True, text=True)
        out = (p.stdout or "") + "\n" + (p.stderr or "")
        ok = p.returncode == 0
        return ok, short_note(ok, out) if not ok else "ok"
    except subprocess.TimeoutExpired:
        return False, f"timed out after {TIMEOUT}s"
    except Exception as e:
        return None, f"could not run: {e}"[:158]


def pass_once():
    by_slug = roster()
    if not by_slug:
        return
    verdicts = load_verdicts()
    changed = False
    for run_id, label, workspace, ended in done_jobs():
        if not run_id or run_id in verdicts:
            continue
        slug = slug_of(label or "", workspace or "", by_slug)
        if not slug:
            continue
        proj = by_slug[slug]
        if not proj.get("doctorCmd"):
            continue  # nothing to verify for this project -> leave unbadged
        log(f"doctoring {slug} :: {label or run_id[:8]} -> {proj['doctorCmd']}")
        ok, note = run_doctor(proj)
        verdicts[run_id] = {"ok": ok, "note": note, "project": proj.get("name", slug),
                            "cmd": proj.get("doctorCmd"), "ts": int(time.time() * 1000)}
        changed = True
        log(f"  -> {'VERIFIED' if ok else ('SKIP' if ok is None else 'FAILED')} {note}")
        save_verdicts(verdicts)  # persist each verdict as it lands (live UI)
    # prune verdicts older than the window so the file stays small
    if changed:
        save_verdicts(verdicts)


def main():
    log(f"foreman-doctor up — poll {POLL_SEC}s, timeout {TIMEOUT}s, window {WINDOW_H}h")
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

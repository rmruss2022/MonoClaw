#!/usr/bin/env python3
"""Foreman job intake — turn a plain "job <project>: <task>" line into the exact,
canonical spawn parameters for a tracked subagent, AND register the job's
acceptance criteria so the doctor/heartbeat can verify completion.

The actual dispatch is a `sessions_spawn` tool call (only the agent can make it);
this helper makes intake deterministic: it validates the project against the
roster, mints a short job id, writes a job record (task + acceptance criteria)
to data/jobs.json keyed by the `slug:jobid` label, and prints the cwd, label, and
a ready-to-use brief (task + criteria + the completion contract). The agent runs
this, then spawns with the printed params.

Usage:
  python3 foreman/job.py "creator-cut: fix the upload freeze"
  python3 foreman/job.py creator-cut "fix the upload freeze"
  python3 foreman/job.py "recilia: add streak badge" \
      --accept "Badge shows the current streak on Home" \
      --accept "Tapping the badge opens streak history"
  python3 foreman/job.py --list            # show valid project slugs

Acceptance criteria (-a/--accept, repeatable) are the definition of done. They
are appended to the job and, when the subagent finishes, the heartbeat verifies
each one against photo evidence + the pipeline test before stamping the job
VERIFIED. A job with no criteria still runs, but completion is judged on the
pipeline test alone.

Convention (document for Matthew): send
  job <project>: <task>  [accept: <criterion>; <criterion>; ...]
and Foreman spawns a subagent in that project's repo, labeled <project>:<jobid>,
mode=run, cleanup=keep — so it shows up live in the Dash board and the heartbeat
verifies it (tests + evidence + acceptance) on completion.
"""
import json, os, re, sys, time, tempfile

ROSTER = os.environ.get("FOREMAN_ROSTER", "/root/MonoClaw/foreman/projects.json")
DATA_DIR = os.environ.get("FOREMAN_DATA", "/root/MonoClaw/foreman/data")
JOBS = os.path.join(DATA_DIR, "jobs.json")


def roster():
    with open(ROSTER) as f:
        return {p["slug"]: p for p in (json.load(f).get("projects") or []) if p.get("slug")}


def jobid(task):
    """short, readable, unique-ish id from the task text + time."""
    words = re.findall(r"[a-z0-9]+", task.lower())[:3]
    stem = "-".join(words) or "job"
    return f"{stem}-{int(time.time()) % 100000}"


def load_jobs():
    try:
        with open(JOBS) as f:
            return json.load(f)
    except Exception:
        return {}


def save_jobs(d):
    os.makedirs(DATA_DIR, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(d, f, indent=1)
    os.replace(tmp, JOBS)


def parse_args(argv):
    """Pull out -a/--accept criteria (repeatable) + an inline 'accept:' tail.
    Returns (positional_str, [criteria])."""
    criteria, pos = [], []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-a", "--accept"):
            if i + 1 < len(argv):
                criteria.append(argv[i + 1].strip()); i += 2; continue
            i += 1; continue
        pos.append(a); i += 1
    raw = " ".join(pos).strip()
    # inline form:  "<slug>: <task> accept: c1; c2; c3"
    m = re.split(r"\baccept:\s*", raw, maxsplit=1, flags=re.I)
    if len(m) == 2:
        raw = m[0].strip().rstrip(".;, ")
        criteria += [c.strip() for c in re.split(r"[;\n]+", m[1]) if c.strip()]
    return raw, [c for c in criteria if c]


def brief(project, task, criteria):
    lines = [
        f"You are a Foreman worker on **{project}**. Complete this job end to end, "
        f"then stop.",
        "",
        f"TASK: {task}",
    ]
    if criteria:
        lines += ["", "ACCEPTANCE CRITERIA (this is the definition of done — every "
                  "item must be true and visible in the running app):"]
        lines += [f"  {i+1}. {c}" for i, c in enumerate(criteria)]
    lines += [
        "",
        "COMPLETION CONTRACT:",
        "  - The project's pipeline test must pass (the doctor runs it: "
        "tsc / npm run check / py_compile, etc.). Do not finish with it red.",
        "  - Each acceptance criterion must be genuinely met in the live app — "
        "the heartbeat captures a screenshot and verifies them against it.",
        "  - End your run with a short report: what changed (files), how you "
        "verified it, and one line per acceptance criterion stating it is met.",
    ]
    return "\n".join(lines)


def main(argv):
    by_slug = roster()
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__); return 0
    if argv[0] == "--list":
        for s, p in by_slug.items():
            print(f"  {s:14} {p.get('name','')}  (repo: {p.get('repoDir','?')})")
        return 0

    raw, criteria = parse_args(argv)

    if ":" in raw and not os.path.isabs(raw.split(":", 1)[0]):
        slug, task = raw.split(":", 1)
        slug, task = slug.strip(), task.strip()
    else:
        parts = raw.split(None, 1)
        slug, task = parts[0] if parts else "", (parts[1] if len(parts) > 1 else "")
    slug = slug.strip()

    if slug not in by_slug:
        print(f"unknown project '{slug}'. valid slugs:", ", ".join(sorted(by_slug)), file=sys.stderr)
        return 2
    if not task:
        print("missing task text", file=sys.stderr); return 2

    p = by_slug[slug]
    label = f"{slug}:{jobid(task)}"

    # register the job + acceptance criteria (keyed by label; the doctor joins
    # a finished run to this record via its label).
    jobs = load_jobs()
    jobs[label] = {
        "slug": slug, "project": p.get("name", slug), "task": task,
        "acceptance": criteria, "created_at": int(time.time() * 1000),
    }
    save_jobs(jobs)

    spawn = {
        "slug": slug,
        "project": p.get("name", slug),
        "cwd": p.get("repoDir"),
        "label": label,
        "task": task,
        "acceptance": criteria,
        "mode": "run",
        "cleanup": "keep",
        "doctorCmd": p.get("doctorCmd"),
        "url": p.get("url"),
        "brief": brief(p.get("name", slug), task, criteria),
    }
    print(json.dumps(spawn, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

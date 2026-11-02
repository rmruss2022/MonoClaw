#!/usr/bin/env python3
"""Foreman job intake — turn a plain "job <project>: <task>" line into the exact,
canonical spawn parameters for a tracked subagent.

The actual dispatch is a `sessions_spawn` tool call (only the agent can make it);
this helper just makes intake deterministic: it validates the project against the
roster, mints a short job id, and prints the cwd + the `slug:jobid` label the Dash
board lanes on. The agent runs this, then spawns with the printed params.

Usage:
  python3 foreman/job.py "creator-cut: fix the upload freeze"
  python3 foreman/job.py creator-cut "fix the upload freeze"
  python3 foreman/job.py --list            # show valid project slugs

Convention (document for Matthew): send
  job <project>: <task>
and Foreman spawns a subagent in that project's repo, labeled <project>:<jobid>,
mode=run, cleanup=keep — so it shows up live in the Dash board and the doctor
verifies it on completion.
"""
import json, os, re, sys, time

ROSTER = os.environ.get("FOREMAN_ROSTER", "/root/MonoClaw/foreman/projects.json")


def roster():
    with open(ROSTER) as f:
        return {p["slug"]: p for p in (json.load(f).get("projects") or []) if p.get("slug")}


def jobid(task):
    """short, readable, unique-ish id from the task text + time."""
    words = re.findall(r"[a-z0-9]+", task.lower())[:3]
    stem = "-".join(words) or "job"
    return f"{stem}-{int(time.time()) % 100000}"


def main(argv):
    by_slug = roster()
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__); return 0
    if argv[0] == "--list":
        for s, p in by_slug.items():
            print(f"  {s:14} {p.get('name','')}  (repo: {p.get('repoDir','?')})")
        return 0

    raw = " ".join(argv).strip()
    if ":" in raw and not os.path.isabs(raw.split(":", 1)[0]):
        slug, task = raw.split(":", 1)
        slug, task = slug.strip(), task.strip()
    else:
        parts = raw.split(None, 1)
        slug, task = parts[0], (parts[1] if len(parts) > 1 else "")
    slug = slug.strip()

    if slug not in by_slug:
        print(f"unknown project '{slug}'. valid slugs:", ", ".join(sorted(by_slug)), file=sys.stderr)
        return 2
    if not task:
        print("missing task text", file=sys.stderr); return 2

    p = by_slug[slug]
    spawn = {
        "slug": slug,
        "project": p.get("name", slug),
        "cwd": p.get("repoDir"),
        "label": f"{slug}:{jobid(task)}",
        "task": task,
        "mode": "run",
        "cleanup": "keep",
        "doctorCmd": p.get("doctorCmd"),
    }
    print(json.dumps(spawn, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

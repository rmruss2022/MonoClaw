#!/usr/bin/env python3
"""Build the daily-report LLM prompt from the user-editable template config.

Reads portal/data/report_config.json and prints the prompt for the report whose
id is given as argv[1] (default "nyc-digest"). generate_digest.sh captures stdout
and feeds it to the `claude` CLI. The report template (which sections, what each
should contain, tone, greeting, delivery) is edited in Dash's Report Studio — so
the daily generation is now data-driven instead of a hardcoded prompt.

The output contract is unchanged: the model must return ONE JSON object with
"briefing" and "spoken" fields, so the rest of generate_digest.sh is untouched.
Prints nothing (exit 1) if the config/report is missing, so the caller can fall
back to its built-in prompt.
"""
import os, sys, json

CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "report_config.json")


def load_report(rid):
    try:
        with open(CONFIG) as f:
            cfg = json.load(f)
    except Exception:
        return None
    for r in cfg.get("reports", []):
        if r.get("id") == rid and r.get("enabled", True):
            return r
    return None


def build(r):
    greeting = (r.get("greeting") or "Good morning").strip()
    title = (r.get("title") or "Daily Digest").strip()
    tone = (r.get("tone") or "tight, skimmable, and friendly").strip()
    intro = (r.get("intro") or "").strip()
    want_spoken = r.get("spoken", True)

    secs = [s for s in r.get("sections", []) if s.get("enabled", True) and (s.get("want") or "").strip()]

    lines = []
    lines.append(f"You are composing {title} for THIS MORNING. {intro} "
                 f"Keep it {tone}.")
    lines.append("")
    lines.append("Produce TWO things and return them as ONE JSON object only (no markdown, no")
    lines.append("code fences, no commentary outside the JSON):")
    lines.append("")
    lines.append("{")
    lines.append('  "briefing": "<the full briefing, with emoji section headers and newlines>",')
    if want_spoken:
        lines.append('  "spoken":   "<a clean spoken version: plain sentences, NO emoji, NO markdown, NO URLs, ~20-30 seconds of highlights>"')
    else:
        lines.append('  "spoken":   ""')
    lines.append("}")
    lines.append("")
    lines.append('The "briefing" field must contain, in order:')
    lines.append(f'- A short "{greeting}" line and today\'s date.')
    for s in secs:
        icon = (s.get("icon") or "").strip()
        label = (s.get("label") or s.get("key") or "").strip()
        want = (s.get("want") or "").strip()
        head = f"{icon} {label}".strip()
        lines.append(f"- {head} — {want}")
    if want_spoken:
        lines.append("")
        lines.append('The "spoken" field: a natural spoken summary of the most important items '
                     "above — plain prose a person would say out loud, ~20-30 seconds.")
    lines.append("")
    lines.append("Return ONLY the JSON object. No preamble.")
    return "\n".join(lines)


def main():
    rid = sys.argv[1] if len(sys.argv) > 1 else "nyc-digest"
    r = load_report(rid)
    if not r:
        sys.exit(1)
    sys.stdout.write(build(r))


if __name__ == "__main__":
    main()

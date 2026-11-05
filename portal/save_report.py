#!/usr/bin/env python3
"""
Persist a report into the portal. Report text on STDIN.

  echo "<briefing text>" | python3 save_report.py "NYC Daily Digest"

Writes portal/reports/<YYYY-MM-DD>.json and auto-links the newest TTS mp3
(created in the last few minutes) as the report's voice note, so the digest's
spoken version rides alongside it in the portal.
"""
import sys, os, json, time
from datetime import datetime, timezone

BASE    = "/root/.openclaw/workspace"
REPORTS = os.path.join(BASE, "portal", "reports")
TTS_DIR = os.path.join(BASE, "media", "tts")

def newest_recent_mp3(max_age_s=600):
    if not os.path.isdir(TTS_DIR):
        return None
    now = time.time()
    best, best_m = None, 0
    for fn in os.listdir(TTS_DIR):
        if not fn.lower().endswith(".mp3"):
            continue
        p = os.path.join(TTS_DIR, fn)
        m = os.path.getmtime(p)
        if now - m <= max_age_s and m > best_m:
            best, best_m = fn, m
    return best

def main():
    title = sys.argv[1] if len(sys.argv) > 1 else "Report"
    text  = sys.stdin.read().strip()
    if not text:
        print("no report text on stdin", file=sys.stderr)
        sys.exit(1)
    os.makedirs(REPORTS, exist_ok=True)
    now = datetime.now(timezone.utc)
    rid = now.strftime("%Y-%m-%d")
    date_label = now.strftime("%Y-%m-%d · %A")
    rec = {"date": date_label, "title": title, "text": text, "audio": newest_recent_mp3()}
    with open(os.path.join(REPORTS, rid + ".json"), "w") as f:
        json.dump(rec, f, indent=1)
    print(f"saved report {rid}.json (audio={rec['audio']})")

if __name__ == "__main__":
    main()

#!/usr/bin/env bash
#
# NYC Daily Digest — standalone generator.
#
# Bypasses the OpenClaw gateway's in-cron LLM routing (which fails with
# "LLM request failed") by using the `claude` CLI directly as the LLM,
# then does TTS + portal save + Telegram delivery with plain shell steps.
#
# Run by system crontab at 08:00 America/New_York. Safe to run by hand.
#
set -uo pipefail

export HOME=/root
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
cd /root || exit 1

BASE=/root/.openclaw/workspace
TTS_DIR="$BASE/media/tts"
SAVE_PY="$BASE/portal/save_report.py"
LOG=/root/MonoClaw/portal/digest.log
DATE=$(date +%F)
MP3="$TTS_DIR/digest-$DATE.mp3"
VOICE="en-US-GuyNeural"
TARGET="5574760589"

mkdir -p "$TTS_DIR"
log(){ echo "[$(date '+%F %T %Z')] $*" | tee -a "$LOG"; }

log "=== digest run start ($DATE) ==="

# Delivery-hour gate: the cron fires hourly across the morning; only the hour
# chosen in the report template (Dash → Report Studio) actually sends. FORCE=1
# bypasses the gate for manual runs.
WANT_HOUR=$(python3 -I -c "import json;print(int(json.load(open('$BASE/portal/data/report_config.json'))['reports'][0].get('deliver_hour_et',8)))" 2>/dev/null || echo 8)
NOW_HOUR=$(TZ=America/New_York date +%H)
if [ "${FORCE:-}" != "1" ] && [ "$((10#$NOW_HOUR))" -ne "$((10#$WANT_HOUR))" ]; then
  log "skip: ET hour $((10#$NOW_HOUR)) != configured delivery hour $WANT_HOUR"
  exit 0
fi
log "delivery hour matched (ET $((10#$NOW_HOUR)) == $WANT_HOUR); proceeding"

# Prompt is built from the user-editable template (portal/data/report_config.json,
# edited in Dash's Report Studio). Falls back to the built-in prompt if that
# produces nothing, so a bad/missing config can never break the morning digest.
PROMPT=$(python3 -I "$BASE/portal/build_prompt.py" nyc-digest 2>>"$LOG")
if [ -n "$PROMPT" ]; then
  log "prompt built from report template (report_config.json)"
else
  log "WARN: template prompt empty — using built-in fallback prompt"
PROMPT=$(cat <<'EOF'
You are composing Matthew's NYC Daily Digest for THIS MORNING. Use web search
for live, current data (today's real date, NYC). Keep it tight, skimmable, and
friendly — a real morning briefing, not a wall of text.

Produce TWO things and return them as ONE JSON object only (no markdown, no
code fences, no commentary outside the JSON):

{
  "briefing": "<the full briefing, with emoji section headers and newlines>",
  "spoken":   "<a clean spoken version: plain sentences, NO emoji, NO markdown, NO URLs, ~20-30 seconds of highlights>"
}

The "briefing" field must contain, in order:
- A short "Good morning, Matthew" line and today's date.
- 🌤️ Weather — NYC today: current temp, high/low, rain/snow chance, and a one-line "what to wear/bring".
- 🗞️ Headlines — 4-5 top stories (US/world + anything major NYC-specific), one line each, as "• " bullets.
- 🚇 Getting around — any notable MTA subway service changes/major delays today (skip if nothing notable).
- 🎉 NYC today — one or two notable things happening in the city today.
- 💡 Nugget — one useful/interesting thing to start the day.

The "spoken" field: weather one-liner, top 2-3 headlines, any transit heads-up,
one NYC thing. Plain prose a person would say out loud.

Return ONLY the JSON object. No preamble.
EOF
)
fi

log "calling claude CLI for briefing..."
RAW=$(timeout 280 claude -p "$PROMPT" --allowedTools "WebSearch WebFetch" 2>>"$LOG")
CLAUDE_EXIT=$?
if [ $CLAUDE_EXIT -ne 0 ] || [ -z "$RAW" ]; then
  log "ERROR: claude CLI failed (exit=$CLAUDE_EXIT, empty=$([ -z "$RAW" ] && echo yes || echo no))"
  openclaw message send --channel telegram --target "$TARGET" \
    -m "⚠️ NYC Daily Digest failed: the claude CLI generator errored (exit $CLAUDE_EXIT). Check /root/MonoClaw/portal/digest.log." >/dev/null 2>&1
  exit 1
fi

# Parse the JSON claude returned (tolerate stray prose / code fences around it).
PARSED=$(BRIEF_RAW="$RAW" python3 -I - "$TTS_DIR/.digest_tmp" <<'PY'
import os, sys, json, re
raw = os.environ["BRIEF_RAW"]
tmp = sys.argv[1]
def extract(s):
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n", "", s); s = re.sub(r"\n```$", "", s)
    try:
        return json.loads(s)
    except Exception:
        pass
    i, depth, start = 0, 0, None
    for i, ch in enumerate(s):
        if ch == "{":
            if depth == 0: start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try: return json.loads(s[start:i+1])
                except Exception: continue
    return None
obj = extract(raw)
if not obj or not obj.get("briefing"):
    sys.stderr.write("parse-failed\n"); sys.exit(2)
open(tmp + ".briefing", "w").write(obj["briefing"].strip())
open(tmp + ".spoken", "w").write((obj.get("spoken") or obj["briefing"]).strip())
print("ok")
PY
)
if [ "$PARSED" != "ok" ]; then
  log "ERROR: could not parse claude JSON output. Raw head: $(echo "$RAW" | head -c 300)"
  openclaw message send --channel telegram --target "$TARGET" \
    -m "⚠️ NYC Daily Digest: generated text but couldn't parse it. Check /root/MonoClaw/portal/digest.log." >/dev/null 2>&1
  exit 1
fi

BRIEF_FILE="$TTS_DIR/.digest_tmp.briefing"
SPOKEN_FILE="$TTS_DIR/.digest_tmp.spoken"
log "briefing composed ($(wc -c <"$BRIEF_FILE") bytes); generating voice note..."

# Voice note (best-effort — never blocks delivery of the text).
if edge-tts --voice "$VOICE" --file "$SPOKEN_FILE" --write-media "$MP3" >>"$LOG" 2>&1 && [ -s "$MP3" ]; then
  log "voice note saved: $MP3"
  HAVE_MP3=1
else
  log "WARN: edge-tts failed; delivering text only"
  HAVE_MP3=0
fi

# Archive into the portal (links the fresh mp3 automatically).
if python3 "$SAVE_PY" "NYC Daily Digest" <"$BRIEF_FILE" >>"$LOG" 2>&1; then
  log "report saved to portal"
else
  log "WARN: save_report.py failed"
fi

# Deliver to Telegram: briefing text, then the voice note.
if openclaw message send --channel telegram --target "$TARGET" -m "$(cat "$BRIEF_FILE")" >>"$LOG" 2>&1; then
  log "briefing text delivered"
else
  log "ERROR: failed to deliver briefing text"
fi
if [ "$HAVE_MP3" = "1" ]; then
  if openclaw message send --channel telegram --target "$TARGET" --media "$MP3" >>"$LOG" 2>&1; then
    log "voice note delivered"
  else
    log "WARN: failed to deliver voice note"
  fi
fi

rm -f "$TTS_DIR/.digest_tmp.briefing" "$TTS_DIR/.digest_tmp.spoken"
log "=== digest run complete ==="

#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# NIGHT SWEEP — nightly autonomous review + safe-implement + next-day plan.
#
# A GATED pipeline. Each gate is verified by a "doctor" before the next runs;
# a failed critical gate halts the sweep (and still files a report). Edits land
# on a dated branch only — never main, never pushed, never deployed — and are
# auto-reverted if the post-change doctor (typecheck) fails.
#
# Scheduled nightly by system cron. Uses the `claude` CLI headless for the
# reasoning + implementation (the Gateway in-cron LLM path is broken on this box).
#
#   DRY=1   → gather + plan + report only; no edits, prints report instead of sending.
# ─────────────────────────────────────────────────────────────────────────────
set -uo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

ROOT=/root/MonoClaw
DIR=$ROOT/nightsweep
DATE=$(TZ=America/New_York date +%F)
NOW=$(TZ=America/New_York date '+%Y-%m-%d %H:%M %Z')
WORK=$DIR/work; LOGS=$DIR/logs; REPORTS=$DIR/reports
mkdir -p "$WORK" "$LOGS" "$REPORTS"
LOG=$LOGS/sweep-$DATE.log
CTX=$WORK/context-$DATE.md
PLAN=$WORK/plan-$DATE.md
REPORT=$REPORTS/$DATE.md
# live reports app + voice-note output (same dirs the morning digest uses)
WS=/root/.openclaw/workspace
PORTAL_REPORTS=$WS/portal/reports
TTS_OUT=$WS/media/tts
MP3=$TTS_OUT/nightsweep-$DATE.mp3
BRANCH="nightsweep/$DATE"
TG=5574760589
DRY=${DRY:-0}

exec > >(tee -a "$LOG") 2>&1
echo "══════════ NIGHT SWEEP $NOW (dry=$DRY) ══════════"

GATES_PASS=(); GATES_FAIL=()
gate() {           # gate "Name" critical(0/1) cmd...
  local name="$1" crit="$2"; shift 2
  echo "──▶ GATE: $name"
  if "$@"; then echo "   ✓ PASS: $name"; GATES_PASS+=("$name"); return 0
  else echo "   ✗ FAIL: $name"; GATES_FAIL+=("$name")
       [ "$crit" = "1" ] && { echo "   ⛔ critical gate failed — halting pipeline"; finalize_fail "$name"; exit 1; }
       return 1; fi
}

# ── DOCTOR: environment ──────────────────────────────────────────────────────
doctor_env() {
  command -v claude >/dev/null || { echo "claude CLI missing"; return 1; }
  git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "not a git repo"; return 1; }
  return 0
}

# ── GATE 1: gather today's work into context ─────────────────────────────────
gather() {
  {
    echo "# Night Sweep context — $DATE"
    echo "## Commits in the last 24h"
    git -C "$ROOT" log --since='24 hours ago' --pretty='- %h %s' | head -80
    echo; echo "## Changed files (working tree)"
    git -C "$ROOT" status --short | head -120
    echo; echo "## Diff stat (last 24h)"
    git -C "$ROOT" log --since='24 hours ago' --stat --oneline | head -200
    echo; echo "## Today's memory notes"
    tail -n 150 "$ROOT/memory/$DATE.md" 2>/dev/null || echo "(none)"
  } > "$CTX"
  [ -s "$CTX" ]
}

# ── GATE 2: review + plan (read-only reasoning) ──────────────────────────────
plan() {
  local prompt
  prompt="You are the Night Sweep engineer for Matthew's MonoClaw monorepo ($ROOT). \
Review the context below (today's commits, changes, notes) and produce a report in GitHub-flavored Markdown with EXACTLY these sections and headings:

## Changes
A tight 4-8 bullet review of what was actually built/changed today.

## Suggestions for tomorrow
5-8 concrete, prioritized action items to work on next (what to finish/implement).

## Implement tonight
A fenced \`\`\`json code block ONLY, of the form:
{\"safe_changes\":[{\"title\":\"...\",\"files\":\"<paths>\",\"instructions\":\"<one concrete, self-contained change>\"}]}
Include 0-3 items you can FULLY implement tonight and that a typecheck or health-check can verify — finish in-progress work, fix real bugs, add small features, tidy copy/docs/memory. \
A later step will edit, typecheck, deploy and push these, so keep each self-contained and verifiable. \
FORBIDDEN even so: deleting user data or whole files, editing secrets/.env, DB-destructive migrations, or sweeping refactors you cannot verify. If nothing is a good candidate, use an empty array.

Write the report to $PLAN using the Write tool, then stop. Context:
---
$(cat "$CTX")"
  claude -p "$prompt" --allowedTools "Read Grep Glob Bash Write" >/dev/null 2>&1 || true
  [ -s "$PLAN" ] && grep -q '## Changes' "$PLAN" && grep -q '## Suggestions for tomorrow' "$PLAN"
}

# top-level dirs → how to deploy them (health-checked; rollback on failure)
SWEEP_SHA_FILE=$WORK/sha-$DATE
DEPLOYED=(); ROLLED_BACK=()

# DOCTOR for the staged edits: python syntax + tsc on changed TS projects.
doctor_changes() {
  local bad=0 f d proj
  for f in $(git -C "$ROOT" diff --cached --name-only); do
    case "$f" in *.py) python3 -I -c "import ast;ast.parse(open('$ROOT/$f').read())" 2>/dev/null || { echo "   ✗ py syntax: $f"; bad=1; };; esac
  done
  for proj in $(git -C "$ROOT" diff --cached --name-only | grep -E '\.tsx?$' | sed -E 's#/[^/]+$##' | sort -u); do
    d="$ROOT/$proj"
    while [ "$d" != "/" ] && [ "${d#$ROOT}" != "" -o "$d" = "$ROOT" ]; do
      if [ -f "$d/tsconfig.json" ]; then
        (cd "$d" && timeout 200 npx tsc --noEmit 2>&1 | grep -q 'error TS') && { echo "   ✗ tsc: $d"; bad=1; }; break
      fi; [ "$d" = "$ROOT" ] && break; d=$(dirname "$d")
    done
  done
  [ "$bad" = "0" ]
}

healthy() { # svc-or-url
  case "$1" in
    http*) curl -sS -o /dev/null -w '%{http_code}' -L --max-time 15 "$1" 2>/dev/null | grep -q '200';;
    *) [ "$(systemctl is-active "$1.service" 2>/dev/null)" = "active" ];;
  esac
}

deploy_dir() { # top-level dir
  case "$1" in
    portfolio|rolodex|appcatalog|waypoint|travelog|croppa|chase|inkling)
      systemctl restart "$1.service"; sleep 2; healthy "$1";;
    recilia) (cd "$ROOT/recilia" && timeout 360 npx expo export -p web >/dev/null 2>&1) && systemctl restart recilia-web.service; sleep 2; healthy "https://recilia.bedrock.casa/";;
    lumen) (cd "$ROOT/lumen" && timeout 150 railway up -d -y >/dev/null 2>&1); healthy "https://lumen-production-a8c6.up.railway.app/health";;
    recilia-api) (cd "$ROOT/recilia-api" && timeout 150 railway up -d -y >/dev/null 2>&1); healthy "https://recilia-api-production.up.railway.app/health";;
    *) echo "   (no auto-deploy for $1)"; return 0;;
  esac
}

# ── GATE 3: implement — claude edits, stages its files; doctor-gate; commit ───
implement() {
  [ "$DRY" = "1" ] && { echo "   (dry run — skipping implementation)"; return 0; }
  local changes
  changes=$(python3 -I - "$PLAN" <<'PY'
import sys,re,json
t=open(sys.argv[1]).read()
m=re.search(r'```json\s*(\{.*?\})\s*```', t, re.S)
print(json.dumps(json.loads(m.group(1)).get('safe_changes',[])) if m else "[]")
PY
)
  if [ "$changes" = "[]" ] || [ -z "$changes" ]; then echo "   nothing to implement"; : > "$SWEEP_SHA_FILE"; return 0; fi
  claude -p "In repo $ROOT, implement ONLY these changes exactly, keep each minimal. When done, run 'git add' on ONLY the files you changed, then STOP. Do NOT commit, push, deploy, restart services, run railway, or touch secrets/.env. Changes JSON: $changes" \
    --allowedTools "Read Grep Glob Edit Write Bash" >/dev/null 2>&1 || true
  if [ -z "$(git -C "$ROOT" diff --cached --name-only)" ]; then echo "   no staged changes"; : > "$SWEEP_SHA_FILE"; return 0; fi
  if ! doctor_changes; then
    echo "   DOCTOR failed — reverting the sweep's edits";
    for f in $(git -C "$ROOT" diff --cached --name-only); do git -C "$ROOT" checkout -q HEAD -- "$f" 2>/dev/null; done
    git -C "$ROOT" reset -q; : > "$SWEEP_SHA_FILE"; return 1
  fi
  git -C "$ROOT" commit -q -m "night sweep $DATE: automated changes" && git -C "$ROOT" rev-parse HEAD > "$SWEEP_SHA_FILE"
  echo "   committed $(cat "$SWEEP_SHA_FILE")"
}

# ── GATE 3b: deploy affected services (health-checked; rollback on failure) ───
deploy() {
  [ "$DRY" = "1" ] && { echo "   (dry run — skip deploy)"; return 0; }
  [ -s "$SWEEP_SHA_FILE" ] || { echo "   nothing committed — nothing to deploy"; return 0; }
  local sha; sha=$(cat "$SWEEP_SHA_FILE")
  local dirs; dirs=$(git -C "$ROOT" show --name-only --pretty='' "$sha" | awk -F/ 'NF>1{print $1}' | sort -u)
  local anyfail=0
  for d in $dirs; do
    echo "   deploy: $d"
    if deploy_dir "$d"; then DEPLOYED+=("$d"); else echo "   ✗ health check failed for $d — rolling back"; anyfail=1; ROLLED_BACK+=("$d"); fi
  done
  if [ "$anyfail" = "1" ]; then
    git -C "$ROOT" revert --no-edit "$sha" >/dev/null 2>&1 && git -C "$ROOT" rev-parse HEAD > "$SWEEP_SHA_FILE.reverted"
    for d in "${ROLLED_BACK[@]}"; do deploy_dir "$d" >/dev/null 2>&1 || true; done
    return 1
  fi
}

# ── GATE 3c: push to origin (current branch + main) ──────────────────────────
push() {
  [ "$DRY" = "1" ] && { echo "   (dry run — skip push)"; return 0; }
  local br; br=$(git -C "$ROOT" branch --show-current)
  git -C "$ROOT" push -q origin "$br" 2>&1 | tail -2 || true
  if git -C "$ROOT" push -q origin "HEAD:main" 2>/dev/null; then echo "   pushed to origin/$br and origin/main"; else echo "   pushed origin/$br (main not fast-forward — left as-is)"; fi
}

# ── GATE 4: compose + deliver report ─────────────────────────────────────────
compose() {
  local sha="" diffstat="" revert="_Nothing was implemented tonight._"
  [ -s "$SWEEP_SHA_FILE" ] && sha=$(cat "$SWEEP_SHA_FILE")
  if [ -n "$sha" ]; then
    diffstat=$(git -C "$ROOT" show --stat --oneline "$sha" 2>/dev/null | tail -n +2 | head -30)
    if [ -f "$SWEEP_SHA_FILE.reverted" ]; then
      revert="⚠️ A deploy health-check failed, so tonight's change was **auto-reverted** (commit \`$(cat "$SWEEP_SHA_FILE.reverted")\`). Nothing broken shipped."
    else
      revert="To undo everything from tonight:\n\`\`\`\ncd /root/MonoClaw && git revert --no-edit $sha && git push origin HEAD\n\`\`\`\nThen redeploy the affected app(s): ${DEPLOYED[*]:-none}."
    fi
  fi
  {
    echo "# 🌙 Night Sweep — $DATE"
    echo "_Generated ${NOW}_"; echo
    sed -n '/## Changes/,/## Implement tonight/p' "$PLAN" | sed '/## Implement tonight/d'
    echo "## Implemented, tested & deployed tonight"
    if [ -n "$sha" ]; then
      echo "Commit \`$sha\` — pushed to origin. Deployed & health-checked: **${DEPLOYED[*]:-none}**."
      echo; echo '```'; echo "$diffstat"; echo '```'
    else
      echo "_Nothing met the auto-implement + doctor bar tonight (kept as suggestions above)._"
    fi
    echo; echo "## How to revert"; printf '%b\n' "$revert"
    echo; echo "---"; echo "### Gate log"
    echo "- Passed: ${GATES_PASS[*]:-none}"
    echo "- Failed: ${GATES_FAIL[*]:-none}"
  } > "$REPORT"
  [ -s "$REPORT" ]
}

# summary-of-the-summary for the chat ping
chat_summary() {
  python3 -I - "$REPORT" "$DATE" <<'PY'
import sys,re
rep=open(sys.argv[1]).read(); date=sys.argv[2]
def section(h):
    out=[]; grab=False
    for ln in rep.splitlines():
        if ln.startswith('## '):
            grab = ln.strip().lower().startswith('## '+h.lower()); continue
        s=ln.strip()
        if grab and (s[:1] in '-*' or re.match(r'\d+[.)]\s', s)):
            out.append('- '+re.sub(r'^(\d+[.)]|[-*])\s*','',s))
    return out[:3]
ch=section('Changes'); su=section('Suggestions for tomorrow')
print(f"🌙 *Night Sweep — {date}*\n")
print("*What got done:*")
print("\n".join(ch) if ch else "- (see report)")
print("\n*Top picks for tomorrow:*")
print("\n".join(su) if su else "- (see report)")
print(f"\n_Full report: nightsweep/reports/{date}.md_")
PY
}

# Publish the report into the reports app (reports.bedrock.casa) with a spoken
# voice note alongside it — reusing the digest's edge-tts + portal mechanism.
# Writes a distinct <date>-nightsweep.json so it never clobbers the morning
# digest's <date>.json for the same day.
publish() {
  [ "$DRY" = "1" ] && { echo "(dry) would publish to reports app + attach voice note"; return 0; }
  mkdir -p "$TTS_OUT" "$PORTAL_REPORTS"
  # spoken script: the FULL report narrated (what it did + shipped + tomorrow),
  # not just the 3-bullet chat summary. No emoji / markdown / URLs / code fences.
  local spoken="$WORK/voice.txt"
  REPORT="$REPORT" python3 -I - > "$spoken" <<'PY'
import os, re
rep = open(os.environ["REPORT"]).read()
# keep only the narration-worthy sections, in spoken order
WANT = [("Changes", "Here's what got done across the day."),
        ("Implemented, tested & deployed tonight", "What the sweep itself shipped tonight:"),
        ("Suggestions for tomorrow", "And here's what I'd tackle tomorrow:")]
def grab(header):
    out, on = [], False
    for ln in rep.splitlines():
        if ln.startswith("## "):
            on = ln[3:].strip().lower().startswith(header.lower()); continue
        if on: out.append(ln)
    return "\n".join(out).strip()
parts = ["Here is tonight's Night Sweep."]
for header, lead in WANT:
    body = grab(header)
    if not body: continue
    body = re.sub(r'```.*?```', ' ', body, flags=re.S)      # drop code fences
    body = re.sub(r'`([^`]*)`', r'\1', body)                # inline code
    body = re.sub(r'https?://\S+', '', body)                # URLs
    body = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', body)    # md links -> text
    body = re.sub(r'[*_#>]+', '', body)                     # md markers
    body = ''.join(c for c in body if ord(c) < 128)         # drop emoji/non-ascii
    body = re.sub(r'(?m)^\s*[-*]\s*', '', body)             # bullet dashes
    body = re.sub(r'(?m)^\s*\d+[.)]\s*', '', body)          # numbered list markers
    body = re.sub(r'[ \t]+', ' ', body)
    body = re.sub(r'\n{1,}', '. ', body).strip()
    body = re.sub(r'(\.\s*){2,}', '. ', body)               # collapse ".. ."
    parts.append(lead + " " + body)
print("\n".join(parts).strip())
PY
  # voice note — edge-tts occasionally truncates mid-stream (writes a tiny stub
  # that passes -s). Retry a few times and KEEP THE LARGEST; require a sane size
  # so a 2-second stub never ships. Never blocks publishing the text.
  local audio="" best=0 try=0 tmp="$WORK/voice-try.mp3"
  if command -v edge-tts >/dev/null 2>&1; then
    rm -f "$MP3"
    for try in 1 2 3 4; do
      rm -f "$tmp"
      if edge-tts --voice en-US-GuyNeural --file "$spoken" --write-media "$tmp" >/dev/null 2>&1 && [ -s "$tmp" ]; then
        local sz; sz=$(wc -c < "$tmp")
        if [ "$sz" -gt "$best" ]; then best=$sz; cp -f "$tmp" "$MP3"; fi
        # a full-report narration is always well over 60KB; accept once we clear it
        [ "$sz" -gt 60000 ] && break
      fi
      sleep 2
    done
    rm -f "$tmp"
    if [ "$best" -gt 60000 ]; then
      audio=$(basename "$MP3"); echo "voice note: $MP3 (${best} bytes, try $try)"
    elif [ "$best" -gt 0 ]; then
      audio=$(basename "$MP3"); echo "WARN: voice note only ${best} bytes (edge-tts kept truncating) — shipping best effort"
    else
      echo "WARN: edge-tts produced nothing — publishing report without audio"; rm -f "$MP3"
    fi
  else
    echo "WARN: edge-tts unavailable — publishing report without audio"; rm -f "$MP3"
  fi
  # write the portal report json (audio basename auto-served from media/tts)
  REPORT="$REPORT" DATE="$DATE" AUDIO="$audio" OUT="$PORTAL_REPORTS/$DATE-nightsweep.json" \
    python3 -I - <<'PY' && echo "published to reports app" || echo "WARN: portal publish failed"
import os, json
text = open(os.environ["REPORT"]).read().strip()
rec = {"date": os.environ["DATE"] + " · Night Sweep", "title": "Night Sweep — " + os.environ["DATE"],
       "text": text, "audio": os.environ.get("AUDIO") or None}
json.dump(rec, open(os.environ["OUT"], "w"), indent=1)
PY
}

deliver() {
  local msg; msg=$(chat_summary)
  if [ "$DRY" = "1" ]; then echo "── DRY REPORT ──"; echo "$msg"; return 0; fi
  openclaw message send --channel telegram --target "$TG" --message "$msg" >/dev/null 2>&1
  # send the voice note too, if one was produced
  [ -s "$MP3" ] && openclaw message send --channel telegram --target "$TG" --media "$MP3" >/dev/null 2>&1 || true
}

# Approval quiz: after the night's changes ship (safely, via the doctor), give
# Matthew one-tap control — Approve (keep), Deny (revert that commit + redeploy),
# or Ask. Only shown when something actually shipped. Taps route back as
# "nightsweep:<action>:<date>" callbacks; see nightsweep/NIGHTSWEEP.md for how a
# session handles them (revert reads reports/<date>.md for the sha + apps).
quiz() {
  local sha=""; [ -s "$SWEEP_SHA_FILE" ] && sha=$(cat "$SWEEP_SHA_FILE")
  [ -z "$sha" ] && { echo "nothing shipped — no approval quiz"; return 0; }
  [ -f "$SWEEP_SHA_FILE.reverted" ] && { echo "change was auto-reverted — no quiz"; return 0; }
  local pres
  pres=$(DATE="$DATE" SHA="$sha" python3 -I - <<'PY'
import os, json
d, sha = os.environ["DATE"], os.environ["SHA"]
print(json.dumps({"blocks": [
  {"type": "text", "text": f"Tonight's changes shipped as commit {sha}. Your call:"},
  {"type": "buttons", "buttons": [
    {"label": "✅ Approve", "action": {"type": "callback", "value": f"nightsweep:approve:{d}"}, "style": "success"},
    {"label": "↩️ Deny & revert", "action": {"type": "callback", "value": f"nightsweep:revert:{d}"}, "style": "danger"},
    {"label": "💬 Ask about changes", "action": {"type": "callback", "value": f"nightsweep:ask:{d}"}},
  ]},
]}))
PY
)
  if [ "$DRY" = "1" ]; then echo "── DRY QUIZ ──"; echo "$pres"; return 0; fi
  # Belt-and-suspenders: buttons only route if channels.telegram.capabilities.
  # inlineButtons is enabled (owner-only). The reply line always works.
  local ask="Approve tonight's Night Sweep (commit ${sha:0:7})? Tap a button below, or just reply: approve · revert · ask"
  openclaw message send --channel telegram --target "$TG" \
    --message "$ask" --presentation "$pres" >/dev/null 2>&1 \
    && echo "approval quiz sent" || echo "WARN: approval quiz failed to send"
}

finalize_fail() { echo "SWEEP HALTED at gate: $1"; [ "$DRY" != "1" ] && openclaw message send --channel telegram --target "$TG" --message "🌙 Night Sweep $DATE halted at gate: $1 (see logs)" >/dev/null 2>&1 || true; }

# ── run the gated pipeline ───────────────────────────────────────────────────
gate "doctor: environment" 1 doctor_env
gate "gather context"      1 gather
gate "review + plan"       1 plan
gate "implement"           0 implement
gate "deploy"              0 deploy
gate "push"                0 push
gate "compose report"      1 compose
gate "publish + voice note" 0 publish
gate "deliver"             0 deliver
gate "approval quiz"       0 quiz

echo "══════════ DONE — pass: ${#GATES_PASS[@]}  fail: ${#GATES_FAIL[@]} ══════════"

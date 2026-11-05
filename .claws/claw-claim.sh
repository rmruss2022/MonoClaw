#!/usr/bin/env bash
# Durable cross-agent app claim — survives restarts (it's a file in the repo,
# synced by clawsync). Prevents the droplet and the Mac from editing the same
# app at once.
#   claw-claim.sh <app> [note]   -> claim app for THIS host
#   claw-claim.sh -r <app>       -> release
#   claw-claim.sh                -> show all claims
set -uo pipefail
F="$(cd "$(dirname "$0")" && pwd)/claims.json"
HOST="$(hostname -s)"
act="${1:-list}"

# Values are passed through argv, never interpolated into the Python source,
# so apostrophes in a note (e.g. "fixing lumen's submit flow") can't break it.
if [ "$act" = "list" ]; then
  python3 -I - "$F" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
if not d:
    print('(no active claims)')
for k, v in d.items():
    print(f'{k:16} {v["host"]:18} since {v["since"]}  {v.get("note","")}')
PY
  exit 0
fi

if [ "$act" = "-r" ]; then
  app="${2:?app}"
  python3 -I - "$F" "$app" <<'PY'
import json, sys
f, app = sys.argv[1], sys.argv[2]
d = json.load(open(f))
d.pop(app, None)
json.dump(d, open(f, 'w'), indent=2)
PY
  msg="release $app"
else
  app="$act"; note="${2:-}"
  python3 -I - "$F" "$app" "$HOST" "$note" <<'PY'
import json, sys, datetime
f, app, host, note = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
d = json.load(open(f))
prev = d.get(app)
if prev and prev.get('host') != host:
    print(f'WARNING: {app} is already claimed by {prev["host"]} since {prev["since"]} '
          f'({prev.get("note","")}) — overwriting', file=sys.stderr)
d[app] = {
    'host': host,
    'since': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'),
    'note': note,
}
json.dump(d, open(f, 'w'), indent=2)
PY
  msg="claim $app by $HOST"
fi

# Publish immediately so the other host sees it (don't wait for the 2-min timer).
# Rebase first: the other host auto-commits, so origin is a moving target and a
# bare push would silently fail, leaving the claim invisible until the next sync.
cd "$(dirname "$F")/.." || exit 1
git add .claws/claims.json
if git commit -q -m "claims: $msg" 2>/dev/null; then
  git pull --rebase -q --autostash 2>/dev/null || true
  git push -q 2>/dev/null || echo "note: claim committed locally; push deferred to clawsync" >&2
fi
echo "$msg"

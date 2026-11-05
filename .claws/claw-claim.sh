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
if [ "$act" = "list" ]; then python3 -I -c "import json;d=json.load(open('$F'));[print(f'{k:16} {v[\"host\"]:18} since {v[\"since\"]}  {v.get(\"note\",\"\")}') for k,v in d.items()] or print('(no active claims)')"; exit 0; fi
if [ "$act" = "-r" ]; then app="${2:?app}"; python3 -I -c "import json;d=json.load(open('$F'));d.pop('$app',None);json.dump(d,open('$F','w'),indent=2)"; msg="release $app"; else
  app="$act"; note="${2:-}"; python3 -I -c "import json,datetime;d=json.load(open('$F'));d['$app']={'host':'$HOST','since':datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'),'note':'$note'};json.dump(d,open('$F','w'),indent=2)"; msg="claim $app by $HOST"
fi
# publish immediately so the other host sees it (don't wait for the 2-min timer)
cd "$(dirname "$F")/.." && git add .claws/claims.json && git commit -q -m "claims: $msg" 2>/dev/null && (git push -q 2>/dev/null || true)
echo "$msg"

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
if [ "$act" = "list" ]; then CLAIMS_FILE="$F" python3 -I -c 'import json,os;d=json.load(open(os.environ["CLAIMS_FILE"]));[print("{:16} {:18} since {}  {}".format(k,v["host"],v["since"],v.get("note",""))) for k,v in d.items()] or print("(no active claims)")'; exit 0; fi
if [ "$act" = "-r" ]; then app="${2:?app}"; CLAIMS_FILE="$F" CLAIM_APP="$app" python3 -I -c 'import json,os;f=os.environ["CLAIMS_FILE"];d=json.load(open(f));d.pop(os.environ["CLAIM_APP"],None);json.dump(d,open(f,"w"),indent=2)'; msg="release $app"; else
  app="$act"; note="${2:-}"; CLAIMS_FILE="$F" CLAIM_APP="$app" CLAIM_HOST="$HOST" CLAIM_NOTE="$note" python3 -I -c 'import json,os,datetime;e=os.environ;f=e["CLAIMS_FILE"];d=json.load(open(f));d[e["CLAIM_APP"]]={"host":e["CLAIM_HOST"],"since":datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),"note":e["CLAIM_NOTE"]};json.dump(d,open(f,"w"),indent=2)'; msg="claim $app by $HOST"
fi
# publish immediately so the other host sees it (don't wait for the 2-min timer)
cd "$(dirname "$F")/.." && git add .claws/claims.json && git commit -q -m "claims: $msg" -- .claws/claims.json 2>/dev/null && (git push -q 2>/dev/null || true)
echo "$msg"

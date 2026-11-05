#!/usr/bin/env bash
# Cloudflare quick tunnel for the Daily reports web app (portal :18820).
# trycloudflare URLs rotate on every cloudflared restart, so we persist the
# live URL to data/public_url.txt AND text Matthew whenever it changes.
set -o pipefail
URLFILE="/root/MonoClaw/portal/data/public_url.txt"
TG_TARGET="5574760589"
mkdir -p "$(dirname "$URLFILE")"

LAST=""
[ -f "$URLFILE" ] && LAST="$(cat "$URLFILE" 2>/dev/null)"

notify(){
  ( timeout 90 /usr/bin/openclaw message send --channel telegram \
      --target "$TG_TARGET" --message "$1" >/dev/null 2>&1 ) &
}

/usr/local/bin/cloudflared tunnel --url http://127.0.0.1:18820 --no-autoupdate 2>&1 | \
while IFS= read -r line; do
  printf '%s\n' "$line"
  u=$(printf '%s' "$line" | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | head -1)
  if [ -n "$u" ] && [ "$u" != "$LAST" ]; then
    printf '%s' "$u" > "$URLFILE"
    LAST="$u"
    notify "📰 Your Daily reports app link rotated. New link: $u"
  fi
done

#!/usr/bin/env bash
# Cloudflare quick tunnel for the Dash (portfolio HomeDash, :18824).
# trycloudflare URLs rotate every time cloudflared restarts, which kills any
# bookmark. So: keep data/public_url.txt pointed at the live URL AND text
# Matthew the new link whenever it changes (he chose auto-notify over a
# permanent URL). The notify is backgrounded + timeout-bounded so a slow
# gateway connect can never stall the tunnel output loop.
set -o pipefail
URLFILE="/root/MonoClaw/portfolio/data/public_url.txt"
TG_TARGET="5574760589"
mkdir -p "$(dirname "$URLFILE")"

LAST=""
[ -f "$URLFILE" ] && LAST="$(cat "$URLFILE" 2>/dev/null)"

notify(){
  ( timeout 90 /usr/bin/openclaw message send --channel telegram \
      --target "$TG_TARGET" --message "$1" >/dev/null 2>&1 ) &
}

/usr/local/bin/cloudflared tunnel --url http://127.0.0.1:18824 --no-autoupdate 2>&1 | \
while IFS= read -r line; do
  printf '%s\n' "$line"
  u=$(printf '%s' "$line" | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | head -1)
  if [ -n "$u" ] && [ "$u" != "$LAST" ]; then
    printf '%s' "$u" > "$URLFILE"
    LAST="$u"
    notify "🔗 Your Dash link rotated. New link: $u"
  fi
done

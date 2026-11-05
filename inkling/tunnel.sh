#!/usr/bin/env bash
# Run the Cloudflare quick tunnel for Inkling and keep the current public URL
# written to data/public_url.txt so HomeDash can always link to the live URL
# even though trycloudflare URLs rotate when cloudflared restarts.
set -o pipefail
URLFILE="/root/MonoClaw/inkling/data/public_url.txt"
mkdir -p "$(dirname "$URLFILE")"
/usr/local/bin/cloudflared tunnel --url http://127.0.0.1:18826 --no-autoupdate 2>&1 | \
while IFS= read -r line; do
  printf '%s\n' "$line"
  u=$(printf '%s' "$line" | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | head -1)
  [ -n "$u" ] && printf '%s' "$u" > "$URLFILE"
done

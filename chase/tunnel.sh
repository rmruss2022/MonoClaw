#!/usr/bin/env bash
mkdir -p /root/MonoClaw/chase/data
/usr/local/bin/cloudflared tunnel --url http://127.0.0.1:18843 --no-autoupdate 2>&1 | while IFS= read -r line; do
  echo "$line"
  u=$(printf '%s' "$line" | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | head -1)
  [ -n "$u" ] && printf '%s\n' "$u" > /root/MonoClaw/chase/data/public_url.txt
done

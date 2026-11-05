#!/usr/bin/env bash
# LocalTunnel for Lumen — a themed, STABLE subdomain (unlike the random, rotating
# trycloudflare quick-tunnel). Keeps the live URL written to data/public_url.txt
# so HomeDash (the Dash) always links it. Auto-restarts if the tunnel drops.
# Note: loca.lt shows a one-time interstitial (enter the server's public IP) to
# first-time visitors before the app loads.
set -o pipefail
URLFILE="/root/MonoClaw/lumen/data/public_url.txt"
SUB="${LUMEN_LT_SUBDOMAIN:-lumenlight}"
mkdir -p "$(dirname "$URLFILE")"
while true; do
  npx --yes localtunnel --port 18834 --subdomain "$SUB" 2>&1 | \
  while IFS= read -r line; do
    printf '%s\n' "$line"
    u=$(printf '%s' "$line" | grep -oE 'https://[a-z0-9-]+\.loca\.lt' | head -1)
    [ -n "$u" ] && printf '%s' "$u" > "$URLFILE"
  done
  sleep 3
done

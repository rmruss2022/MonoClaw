#!/bin/bash
# Rave Planner startup script - launches API + Vite dev server

export PATH="/opt/homebrew/bin:/opt/homebrew/opt/node/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export FIRECRAWL_API_KEY="fc-d05203b38ae149b68feead94856fb92d"

API_DIR="/Users/matthew_1/.openclaw/workspace/monoclaw/projects/raves"
APP_DIR="$API_DIR/app"
LOG_DIR="/Users/matthew_1/.openclaw/logs"

mkdir -p "$LOG_DIR"

# Kill any existing processes (avoid duplicate)
pkill -f "raves/server.js" 2>/dev/null
pkill -f "rave-planner/app/node_modules/.bin/vite" 2>/dev/null
sleep 2

# Start API server (port 3004) in background
cd "$API_DIR" || exit 1
nohup /opt/homebrew/bin/node server.js > "$LOG_DIR/raves-api.log" 2>&1 &
API_PID=$!
echo "[start.sh] API started PID=$API_PID"

# Wait for API to be ready
for i in {1..15}; do
  if curl -s -o /dev/null -w "%{http_code}" http://localhost:3004/api/events 2>/dev/null | grep -q "200"; then
    echo "[start.sh] API ready"
    break
  fi
  sleep 1
done

# Start Vite dev server (port 3007)
cd "$APP_DIR" || exit 1
exec /opt/homebrew/bin/npm run dev > "$LOG_DIR/raves-vite.log" 2>&1
#!/bin/bash
# Centralized Health Check for all OpenClaw services
# Checks: Voice Server, Job Dashboard, Raves, Token Tracker, Mission Control

set -e

LOG_FILE="/Users/matthew/.openclaw/workspace/health-check.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Services to check (name:port:restart_script:health_endpoint)
SERVICES=(
    "Voice Server:18790:/Users/matthew/.openclaw/voice-server/server.js:/health"
    "Job Dashboard:18791:/Users/matthew/.openclaw/workspace/jobs/server.js:/"
    "Raves Dashboard:18793:/Users/matthew/.openclaw/workspace/raves/server.js:/"
    "Token Tracker:18794:/Users/matthew/.openclaw/workspace/tokens/server.js:/"
    "Mission Control:18795:/Users/matthew/.openclaw/workspace/mission-control/server.js:/"
)

RESTARTS=0
CHECKS=0

echo "[$TIMESTAMP] Starting health checks..." >> "$LOG_FILE"

for service in "${SERVICES[@]}"; do
    IFS=':' read -r name port script endpoint <<< "$service"
    CHECKS=$((CHECKS + 1))
    
    # Check if service responds
    if curl -s -f --max-time 2 "http://localhost:${port}${endpoint}" > /dev/null 2>&1; then
        echo "  ✅ $name (port $port) - healthy" >> "$LOG_FILE"
    else
        echo "  ❌ $name (port $port) - DOWN, restarting..." >> "$LOG_FILE"
        
        # Kill existing process on that port
        pkill -f "$script" 2>/dev/null || true
        sleep 1
        
        # Restart via LaunchAgent if available
        service_name=$(echo "$name" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
        launchctl_name="com.openclaw.${service_name}"
        
        if launchctl list | grep -q "$launchctl_name"; then
            launchctl kickstart -k "gui/$(id -u)/$launchctl_name" 2>/dev/null || true
            echo "    🔄 Restarted via LaunchAgent: $launchctl_name" >> "$LOG_FILE"
        else
            # Fallback: direct node start
            cd "$(dirname "$script")"
            /Users/matthew/.nvm/versions/node/v22.22.0/bin/node "$script" > /dev/null 2>&1 &
            echo "    🔄 Restarted directly: $script" >> "$LOG_FILE"
        fi
        
        RESTARTS=$((RESTARTS + 1))
    fi
done

# Summary
if [ $RESTARTS -eq 0 ]; then
    echo "[$TIMESTAMP] ✅ All services healthy ($CHECKS/$CHECKS)" >> "$LOG_FILE"
    echo "✅ All services healthy — no restarts needed."
    echo ""
    echo "- Voice Server (18790) ✓"
    echo "- Job Dashboard (18791) ✓"
    echo "- Raves Dashboard (18793) ✓"
    echo "- Token Tracker (18794) ✓"
    echo "- Mission Control (18795) ✓"
else
    echo "[$TIMESTAMP] ⚠️  Restarted $RESTARTS service(s)" >> "$LOG_FILE"
    echo "⚠️  Health check complete — $RESTARTS service(s) restarted."
fi

echo "" >> "$LOG_FILE"

exit 0

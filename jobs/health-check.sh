#!/bin/bash
# Dashboard services health check
PORT1=18791  # Job Dashboard
PORT2=18795  # Mission Control
PORT3=18790  # Voice Server
PORT4=18793  # Raves Dashboard

check_port() {
  local port=$1
  nc -z 127.0.0.1 $port 2>/dev/null
  return $?
}

# Check Job Dashboard
if ! check_port $PORT1; then
  echo "$(date): Port $PORT1 (Job Dashboard) down, restarting..."
  launchctl kickstart -k gui/$(id -u)/com.openclaw.job-dashboard 2>/dev/null
  sleep 2
fi

# Check Mission Control
if ! check_port $PORT2; then
  echo "$(date): Port $PORT2 (Mission Control) down, restarting..."
  launchctl kickstart -k gui/$(id -u)/com.openclaw.mission-control 2>/dev/null
  sleep 2
fi

# Check Voice Server
if ! check_port $PORT3; then
  echo "$(date): Port $PORT3 (Voice Server) down, restarting..."
  launchctl kickstart -k gui/$(id -u)/com.openclaw.voice-server 2>/dev/null
  sleep 2
fi

# Check Raves Dashboard
if ! check_port $PORT4; then
  echo "$(date): Port $PORT4 (Raves Dashboard) down, restarting..."
  cd ~/.openclaw/workspace/raves && node server.js > server.log 2>&1 &
  sleep 2
fi

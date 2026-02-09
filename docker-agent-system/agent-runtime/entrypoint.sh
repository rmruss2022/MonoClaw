#!/bin/bash
# OpenClaw Docker Agent Entrypoint
# Configures and starts OpenClaw session

set -e

echo "=========================================="
echo "OpenClaw Docker Agent"
echo "=========================================="
echo "Agent Name: ${AGENT_NAME:-unknown}"
echo "Gateway URL: ${GATEWAY_URL}"
echo "Default Model: ${DEFAULT_MODEL}"
echo "Container ID: $(hostname)"
echo "=========================================="

# Create OpenClaw config directory
mkdir -p /root/.openclaw

# Create minimal config.yml for OpenClaw
cat > /root/.openclaw/config.yml <<EOF
# OpenClaw Docker Agent Configuration
# Auto-generated on container start

gateway:
  url: ${GATEWAY_URL}
  autoConnect: true

session:
  label: ${OPENCLAW_SESSION_LABEL:-${AGENT_NAME}}
  thinking: ${THINKING_LEVEL:-low}
  
models:
  default: ${DEFAULT_MODEL}

# Copy API keys from environment
apiKeys:
  # Keys should be passed via environment variables or volume mounts
EOF

# If API keys config exists as mounted file, use it
if [ -f /etc/openclaw/api-keys.yml ]; then
  echo "  Using mounted API keys from /etc/openclaw/api-keys.yml"
  cat /etc/openclaw/api-keys.yml >> /root/.openclaw/config.yml
else
  echo "  Note: No API keys mounted. Pass via environment or volume."
fi

echo ""
echo "Starting OpenClaw session..."
echo "Session label: ${OPENCLAW_SESSION_LABEL:-${AGENT_NAME}}"
echo ""

# Start openclaw in interactive mode
# The session will connect to the gateway and wait for tasks
exec openclaw \
  --gateway "${GATEWAY_URL}" \
  --model "${DEFAULT_MODEL}" \
  --label "${OPENCLAW_SESSION_LABEL:-${AGENT_NAME}}" \
  --thinking "${THINKING_LEVEL:-low}" \
  agent

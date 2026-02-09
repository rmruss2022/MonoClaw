#!/bin/bash

set -e

# Default values
AGENT_NAME=""
AGENT_TYPE="generic"
CPU=2
MEMORY="4G"
DISK="20G"
CAPABILITIES=""
HUB_URL="ws://10.0.2.2:9090"  # Host IP from VM perspective (Multipass default)
PROFILE_PATH=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --name)
      AGENT_NAME="$2"
      shift 2
      ;;
    --type)
      AGENT_TYPE="$2"
      shift 2
      ;;
    --cpu)
      CPU="$2"
      shift 2
      ;;
    --memory)
      MEMORY="$2"
      shift 2
      ;;
    --disk)
      DISK="$2"
      shift 2
      ;;
    --capabilities)
      CAPABILITIES="$2"
      shift 2
      ;;
    --hub-url)
      HUB_URL="$2"
      shift 2
      ;;
    --profile)
      PROFILE_PATH="$2"
      shift 2
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      exit 1
      ;;
  esac
done

# Load profile if specified
if [ -n "$PROFILE_PATH" ]; then
  if [ ! -f "$PROFILE_PATH" ]; then
    echo -e "${RED}Error: Profile file not found: $PROFILE_PATH${NC}"
    exit 1
  fi
  
  echo -e "${GREEN}Loading profile: $PROFILE_PATH${NC}"
  
  # Extract profile data using jq (install if needed)
  if ! command -v jq &> /dev/null; then
    echo "Installing jq..."
    brew install jq || sudo apt-get install -y jq
  fi
  
  PROFILE_NAME=$(jq -r '.name' "$PROFILE_PATH")
  PROFILE_DESC=$(jq -r '.description' "$PROFILE_PATH")
  
  echo "Profile: $PROFILE_NAME - $PROFILE_DESC"
fi

# Validate required arguments
if [ -z "$AGENT_NAME" ]; then
  echo -e "${RED}Error: --name is required${NC}"
  echo "Usage: $0 --name <agent-name> [options]"
  echo ""
  echo "Options:"
  echo "  --name <name>          Agent name (required)"
  echo "  --type <type>          Agent type (default: generic)"
  echo "  --cpu <count>          CPU cores (default: 2)"
  echo "  --memory <size>        Memory size (default: 4G)"
  echo "  --disk <size>          Disk size (default: 20G)"
  echo "  --capabilities <list>  Comma-separated capabilities"
  echo "  --hub-url <url>        Hub WebSocket URL"
  exit 1
fi

echo -e "${GREEN}=== Creating VM Agent: $AGENT_NAME ===${NC}"
echo "Type: $AGENT_TYPE"
echo "CPU: $CPU cores"
echo "Memory: $MEMORY"
echo "Disk: $DISK"
echo "Capabilities: ${CAPABILITIES:-none}"
echo ""

# Check if Multipass is installed
if ! command -v multipass &> /dev/null; then
  echo -e "${RED}Error: Multipass is not installed${NC}"
  echo "Install it from: https://multipass.run/"
  exit 1
fi

# Check if agent already exists
if multipass list | grep -q "^$AGENT_NAME "; then
  echo -e "${YELLOW}Warning: Agent $AGENT_NAME already exists${NC}"
  read -p "Do you want to delete and recreate? (y/N) " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Deleting existing agent..."
    multipass delete "$AGENT_NAME"
    multipass purge
  else
    echo "Aborted."
    exit 1
  fi
fi

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Create temporary cloud-init file
CLOUD_INIT_FILE=$(mktemp)
cat > "$CLOUD_INIT_FILE" << 'EOF'
#cloud-config

package_update: true
package_upgrade: true

packages:
  - git
  - curl
  - build-essential

runcmd:
  # Install Node.js 18.x
  - curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
  - apt-get install -y nodejs
  
  # Create agent directory
  - mkdir -p /opt/vm-agent
  - chown ubuntu:ubuntu /opt/vm-agent
  
  # Create config directory
  - mkdir -p /etc/vm-agent
  - chown ubuntu:ubuntu /etc/vm-agent
  
  # Set up systemd service
  - |
    cat > /etc/systemd/system/vm-agent.service << 'SYSTEMD_EOF'
    [Unit]
    Description=VM Agent Client
    After=network.target

    [Service]
    Type=simple
    User=ubuntu
    WorkingDirectory=/opt/vm-agent
    Environment=NODE_ENV=production
    Environment=AGENT_CONFIG=/etc/vm-agent/config.json
    ExecStart=/usr/bin/node /opt/vm-agent/client.js
    Restart=always
    RestartSec=10
    StandardOutput=journal
    StandardError=journal

    [Install]
    WantedBy=multi-user.target
    SYSTEMD_EOF
  
  - systemctl daemon-reload
EOF

echo -e "${GREEN}Creating VM with Multipass...${NC}"
multipass launch \
  --name "$AGENT_NAME" \
  --cpus "$CPU" \
  --memory "$MEMORY" \
  --disk "$DISK" \
  --cloud-init "$CLOUD_INIT_FILE" \
  22.04

# Clean up cloud-init file
rm "$CLOUD_INIT_FILE"

# Wait for VM to be ready
echo -e "${GREEN}Waiting for VM to be ready...${NC}"
sleep 10

# Get VM IP
VM_IP=$(multipass info "$AGENT_NAME" | grep IPv4 | awk '{print $2}')
echo "VM IP: $VM_IP"

# Copy agent runtime to VM
echo -e "${GREEN}Installing agent runtime...${NC}"
multipass transfer -r "$PROJECT_ROOT/agent-runtime" "$AGENT_NAME:/tmp/"

# Install dependencies and move to /opt
multipass exec "$AGENT_NAME" -- bash << 'SETUP_EOF'
cd /tmp/agent-runtime
npm install --production
sudo cp -r /tmp/agent-runtime/* /opt/vm-agent/
sudo chown -R ubuntu:ubuntu /opt/vm-agent
rm -rf /tmp/agent-runtime
SETUP_EOF

# Apply profile if specified
if [ -n "$PROFILE_PATH" ]; then
  echo -e "${GREEN}Applying profile: $PROFILE_NAME${NC}"
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  "$SCRIPT_DIR/apply-profile.sh" "$AGENT_NAME" "$PROFILE_PATH"
fi

# Register agent with hub and get token
echo -e "${GREEN}Registering agent with hub...${NC}"

# Determine host IP for VM to connect back
# For Multipass, the host is usually accessible at 10.0.2.2
HOST_IP="10.0.2.2"

# Try to register with hub
REGISTER_RESPONSE=$(curl -s -X POST http://localhost:9091/agents/register \
  -H "Content-Type: application/json" \
  -d "{
    \"agentId\": \"$AGENT_NAME\",
    \"metadata\": {
      \"type\": \"$AGENT_TYPE\",
      \"capabilities\": \"$CAPABILITIES\",
      \"cpu\": $CPU,
      \"memory\": \"$MEMORY\",
      \"disk\": \"$DISK\",
      \"vmIp\": \"$VM_IP\"
    }
  }" 2>/dev/null) || {
  echo -e "${RED}Error: Failed to register with hub. Is the hub running?${NC}"
  echo "Start the hub with: cd $PROJECT_ROOT/hub && npm start"
  exit 1
}

# Extract token from response
AGENT_TOKEN=$(echo "$REGISTER_RESPONSE" | grep -o '"token":"[^"]*"' | cut -d'"' -f4)

if [ -z "$AGENT_TOKEN" ]; then
  echo -e "${RED}Error: Failed to get agent token${NC}"
  echo "Response: $REGISTER_RESPONSE"
  exit 1
fi

echo "Agent token: ${AGENT_TOKEN:0:16}..."

# Create agent config file
echo -e "${GREEN}Configuring agent...${NC}"

CONFIG_JSON=$(cat << CONFIG_EOF
{
  "agentId": "$AGENT_NAME",
  "token": "$AGENT_TOKEN",
  "hubUrl": "ws://$HOST_IP:9090",
  "type": "$AGENT_TYPE",
  "capabilities": "$CAPABILITIES"
}
CONFIG_EOF
)

# Write config to VM
echo "$CONFIG_JSON" | multipass transfer - "$AGENT_NAME:/tmp/config.json"
multipass exec "$AGENT_NAME" -- sudo mv /tmp/config.json /etc/vm-agent/config.json

# Start the agent service
echo -e "${GREEN}Starting agent service...${NC}"
multipass exec "$AGENT_NAME" -- sudo systemctl enable vm-agent
multipass exec "$AGENT_NAME" -- sudo systemctl start vm-agent

# Wait for agent to connect
echo -e "${GREEN}Waiting for agent to connect...${NC}"
sleep 5

# Check agent status
STATUS=$(curl -s http://localhost:9091/agents/$AGENT_NAME/status)
AGENT_STATUS=$(echo "$STATUS" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)

if [ "$AGENT_STATUS" = "online" ]; then
  echo -e "${GREEN}✓ Agent is online and connected!${NC}"
else
  echo -e "${YELLOW}⚠ Agent status: $AGENT_STATUS${NC}"
  echo "Check logs with: multipass exec $AGENT_NAME -- sudo journalctl -u vm-agent -f"
fi

# Create snapshot
echo -e "${GREEN}Creating initial snapshot...${NC}"
multipass snapshot "$AGENT_NAME" --name "initial"

echo ""
echo -e "${GREEN}=== Agent Created Successfully ===${NC}"
echo "Name: $AGENT_NAME"
echo "IP: $VM_IP"
echo "Status: $AGENT_STATUS"
echo ""
echo "Useful commands:"
echo "  multipass shell $AGENT_NAME                    # SSH into VM"
echo "  multipass exec $AGENT_NAME -- <command>        # Run command"
echo "  multipass stop $AGENT_NAME                     # Stop VM"
echo "  multipass start $AGENT_NAME                    # Start VM"
echo "  multipass delete $AGENT_NAME                   # Delete VM"
echo "  multipass exec $AGENT_NAME -- sudo journalctl -u vm-agent -f  # View logs"
echo ""

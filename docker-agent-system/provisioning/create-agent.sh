#!/bin/bash
# Create a Docker agent container
# Usage: create-agent.sh <name> [--profile <profile>] [--cpus <cpus>] [--memory <memory>]

set -e

SYSTEM_ROOT="$HOME/.openclaw/workspace/docker-agent-system"
PROFILES_DIR="$SYSTEM_ROOT/profiles"
HUB_URL="${HUB_URL:-http://localhost:9091}"

# Parse arguments
AGENT_NAME="$1"
shift

PROFILE="default"
CPUS="2"
MEMORY="4g"
DISK="30g"

while [[ $# -gt 0 ]]; do
  case $1 in
    --profile)
      PROFILE="$2"
      shift 2
      ;;
    --cpus)
      CPUS="$2"
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
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

if [ -z "$AGENT_NAME" ]; then
  echo "Usage: $0 <name> [--profile <profile>] [--cpus <cpus>] [--memory <memory>]"
  exit 1
fi

CONTAINER_NAME="openclaw-agent-$AGENT_NAME"
VOLUME_NAME="openclaw-agent-$AGENT_NAME"
NETWORK_NAME="openclaw-agents"

echo "Creating Docker agent: $AGENT_NAME"
echo "  Profile: $PROFILE"
echo "  CPUs: $CPUS"
echo "  Memory: $MEMORY"

# Create Docker network if it doesn't exist
if ! docker network inspect "$NETWORK_NAME" > /dev/null 2>&1; then
  echo "Creating Docker network: $NETWORK_NAME"
  docker network create "$NETWORK_NAME"
fi

# Create volume for agent data
echo "Creating volume: $VOLUME_NAME"
docker volume create "$VOLUME_NAME"

# Register agent with hub and get token
echo "Registering agent with hub..."
REGISTER_RESPONSE=$(curl -s -X POST "$HUB_URL/agents/register" \
  -H "Content-Type: application/json" \
  -d "{
    \"agentId\": \"$AGENT_NAME\",
    \"metadata\": {
      \"type\": \"docker\",
      \"profile\": \"$PROFILE\",
      \"cpus\": \"$CPUS\",
      \"memory\": \"$MEMORY\"
    }
  }")

AGENT_TOKEN=$(echo "$REGISTER_RESPONSE" | grep -o '"token":"[^"]*"' | cut -d'"' -f4)

if [ -z "$AGENT_TOKEN" ]; then
  echo "Error: Failed to register agent with hub"
  echo "Response: $REGISTER_RESPONSE"
  exit 1
fi

echo "Agent registered, token obtained"

# Build the Docker image with profile if specified
if [ "$PROFILE" != "default" ] && [ -f "$PROFILES_DIR/$PROFILE.json" ]; then
  echo "Building image with profile: $PROFILE"
  
  # Create temporary Dockerfile that extends base image
  TEMP_DOCKERFILE=$(mktemp)
  cat > "$TEMP_DOCKERFILE" <<EOF
FROM openclaw-agent-base

# Apply profile: $PROFILE
USER root

EOF

  # Extract and install packages from profile
  PACKAGES=$(jq -r '.packages[]?' "$PROFILES_DIR/$PROFILE.json" 2>/dev/null || echo "")
  if [ -n "$PACKAGES" ]; then
    echo "RUN apt-get update && apt-get install -y \\" >> "$TEMP_DOCKERFILE"
    for pkg in $PACKAGES; do
      echo "    $pkg \\" >> "$TEMP_DOCKERFILE"
    done
    echo "    && rm -rf /var/lib/apt/lists/*" >> "$TEMP_DOCKERFILE"
  fi

  # Add setup tasks
  TASKS_COUNT=$(jq '.setup_tasks | length' "$PROFILES_DIR/$PROFILE.json" 2>/dev/null || echo "0")
  for i in $(seq 0 $((TASKS_COUNT - 1))); do
    TASK_CMD=$(jq -r ".setup_tasks[$i].command" "$PROFILES_DIR/$PROFILE.json")
    TASK_DESC=$(jq -r ".setup_tasks[$i].description" "$PROFILES_DIR/$PROFILE.json")
    
    echo "" >> "$TEMP_DOCKERFILE"
    echo "# $TASK_DESC" >> "$TEMP_DOCKERFILE"
    echo "RUN $TASK_CMD || true" >> "$TEMP_DOCKERFILE"
  done

  echo "" >> "$TEMP_DOCKERFILE"
  echo "USER node" >> "$TEMP_DOCKERFILE"

  # Build the image
  docker build -t "openclaw-agent-$PROFILE" -f "$TEMP_DOCKERFILE" "$SYSTEM_ROOT/agent-runtime"
  rm "$TEMP_DOCKERFILE"
  
  BASE_IMAGE="openclaw-agent-$PROFILE"
else
  BASE_IMAGE="openclaw-agent-base"
fi

# Create the container
echo "Creating container: $CONTAINER_NAME"
docker create \
  --name "$CONTAINER_NAME" \
  --network "$NETWORK_NAME" \
  --cpus="$CPUS" \
  --memory="$MEMORY" \
  --volume "$VOLUME_NAME:/workspace" \
  --label "profile=$PROFILE" \
  --label "cpus=$CPUS" \
  --label "memory=$MEMORY" \
  --env "AGENT_ID=$AGENT_NAME" \
  --env "AGENT_TOKEN=$AGENT_TOKEN" \
  --env "HUB_URL=ws://host.docker.internal:9090" \
  --restart unless-stopped \
  "$BASE_IMAGE"

# Apply profile-specific environment variables and files
if [ "$PROFILE" != "default" ] && [ -f "$PROFILES_DIR/$PROFILE.json" ]; then
  echo "Applying profile configuration..."
  
  # Create config directory
  docker exec "$CONTAINER_NAME" mkdir -p /etc/agent || true
  
  # Create files from profile
  FILES_COUNT=$(jq '.files | length' "$PROFILES_DIR/$PROFILE.json" 2>/dev/null || echo "0")
  for i in $(seq 0 $((FILES_COUNT - 1))); do
    FILE_PATH=$(jq -r ".files[$i].path" "$PROFILES_DIR/$PROFILE.json")
    FILE_CONTENT=$(jq -r ".files[$i].content" "$PROFILES_DIR/$PROFILE.json")
    
    echo "  Creating file: $FILE_PATH"
    echo "$FILE_CONTENT" | docker exec -i "$CONTAINER_NAME" tee "$FILE_PATH" > /dev/null
  done
fi

# Start the container
echo "Starting container..."
docker start "$CONTAINER_NAME"

# Wait a moment for container to start
sleep 2

# Check if container is running
if docker ps --filter "name=$CONTAINER_NAME" --format "{{.Names}}" | grep -q "$CONTAINER_NAME"; then
  echo ""
  echo "✓ Agent $AGENT_NAME created and started successfully!"
  echo ""
  echo "Container ID: $(docker ps --filter "name=$CONTAINER_NAME" --format "{{.ID}}")"
  echo "Network: $NETWORK_NAME"
  echo "Volume: $VOLUME_NAME"
  echo ""
else
  echo ""
  echo "✗ Container created but failed to start"
  echo "Check logs with: docker logs $CONTAINER_NAME"
  exit 1
fi

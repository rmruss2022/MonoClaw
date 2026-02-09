#!/bin/bash
# Create an OpenClaw-native Docker agent container
# Usage: create-agent-openclaw.sh <name> [--profile <profile>] [--cpus <cpus>] [--memory <memory>] [--model <model>]

set -e

SYSTEM_ROOT="$HOME/.openclaw/workspace/docker-agent-system"
PROFILES_DIR="$SYSTEM_ROOT/profiles"
GATEWAY_URL="${GATEWAY_URL:-http://host.docker.internal:18787}"

# Parse arguments
AGENT_NAME="$1"
shift

PROFILE="default"
CPUS="2"
MEMORY="4g"
MODEL="nvidia/moonshotai/kimi-k2.5"
THINKING="low"

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
    --model)
      MODEL="$2"
      shift 2
      ;;
    --thinking)
      THINKING="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

if [ -z "$AGENT_NAME" ]; then
  echo "Usage: $0 <name> [--profile <profile>] [--cpus <cpus>] [--memory <memory>] [--model <model>]"
  exit 1
fi

CONTAINER_NAME="openclaw-agent-$AGENT_NAME"
VOLUME_NAME="openclaw-agent-$AGENT_NAME"
NETWORK_NAME="openclaw-agents"

echo "Creating OpenClaw Docker agent: $AGENT_NAME"
echo "  Profile: $PROFILE"
echo "  CPUs: $CPUS"
echo "  Memory: $MEMORY"
echo "  Model: $MODEL"
echo "  Gateway: $GATEWAY_URL"

# Create Docker network if it doesn't exist
if ! docker network inspect "$NETWORK_NAME" > /dev/null 2>&1; then
  echo "Creating Docker network: $NETWORK_NAME"
  docker network create "$NETWORK_NAME"
fi

# Create volume for agent data
echo "Creating volume: $VOLUME_NAME"
docker volume create "$VOLUME_NAME"

# Build the base OpenClaw agent image if not exists
if ! docker image inspect openclaw-agent-openclaw > /dev/null 2>&1; then
  echo "Building OpenClaw agent base image..."
  docker build -t openclaw-agent-openclaw -f "$SYSTEM_ROOT/agent-runtime/Dockerfile.openclaw" "$SYSTEM_ROOT/agent-runtime"
fi

# Build profile-specific image if needed
if [ "$PROFILE" != "default" ] && [ -f "$PROFILES_DIR/$PROFILE.json" ]; then
  echo "Building image with profile: $PROFILE"
  
  # Create temporary Dockerfile that extends OpenClaw base image
  TEMP_DOCKERFILE=$(mktemp)
  cat > "$TEMP_DOCKERFILE" <<EOF
FROM openclaw-agent-openclaw

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
  echo "USER root" >> "$TEMP_DOCKERFILE"

  # Build the image
  docker build -t "openclaw-agent-$PROFILE-oc" -f "$TEMP_DOCKERFILE" "$SYSTEM_ROOT/agent-runtime"
  rm "$TEMP_DOCKERFILE"
  
  BASE_IMAGE="openclaw-agent-$PROFILE-oc"
else
  BASE_IMAGE="openclaw-agent-openclaw"
fi

# Mount API keys if they exist on host
API_KEYS_MOUNT=""
if [ -f "$HOME/.openclaw/api-keys.yml" ]; then
  API_KEYS_MOUNT="--volume $HOME/.openclaw/api-keys.yml:/etc/openclaw/api-keys.yml:ro"
  echo "  Mounting API keys from host"
fi

# Create the container
echo "Creating container: $CONTAINER_NAME"
docker create \
  --name "$CONTAINER_NAME" \
  --network "$NETWORK_NAME" \
  --cpus="$CPUS" \
  --memory="$MEMORY" \
  --volume "$VOLUME_NAME:/workspace" \
  $API_KEYS_MOUNT \
  --label "openclaw.agent=true" \
  --label "openclaw.profile=$PROFILE" \
  --label "openclaw.cpus=$CPUS" \
  --label "openclaw.memory=$MEMORY" \
  --label "openclaw.model=$MODEL" \
  --env "AGENT_NAME=$AGENT_NAME" \
  --env "OPENCLAW_SESSION_LABEL=docker-agent-$AGENT_NAME" \
  --env "GATEWAY_URL=$GATEWAY_URL" \
  --env "DEFAULT_MODEL=$MODEL" \
  --env "THINKING_LEVEL=$THINKING" \
  --restart unless-stopped \
  "$BASE_IMAGE"

# Start the container
echo "Starting container..."
docker start "$CONTAINER_NAME"

# Wait a moment for container to start
sleep 3

# Check if container is running
if docker ps --filter "name=$CONTAINER_NAME" --format "{{.Names}}" | grep -q "$CONTAINER_NAME"; then
  echo ""
  echo "✓ OpenClaw agent $AGENT_NAME created and started successfully!"
  echo ""
  echo "Container ID: $(docker ps --filter "name=$CONTAINER_NAME" --format "{{.ID}}")"
  echo "Session Label: docker-agent-$AGENT_NAME"
  echo "Model: $MODEL"
  echo "Network: $NETWORK_NAME"
  echo "Volume: $VOLUME_NAME"
  echo ""
  echo "Check logs: docker logs -f $CONTAINER_NAME"
  echo "Check session: Look for 'docker-agent-$AGENT_NAME' in dashboard"
  echo ""
else
  echo ""
  echo "✗ Container created but failed to start"
  echo "Check logs with: docker logs $CONTAINER_NAME"
  exit 1
fi

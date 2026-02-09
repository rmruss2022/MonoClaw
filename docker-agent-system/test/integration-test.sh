#!/bin/bash
# Integration test for Docker Agent System
# Tests agent creation, execution, and cleanup

set -e

TEST_AGENT_NAME="test-agent-$(date +%s)"
PROFILE="builder"

echo "======================================"
echo "  Docker Agent System Integration Test"
echo "======================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

success() {
  echo -e "${GREEN}✓${NC} $1"
}

error() {
  echo -e "${RED}✗${NC} $1"
}

info() {
  echo -e "${YELLOW}→${NC} $1"
}

# Check prerequisites
info "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
  error "Docker not found"
  exit 1
fi
success "Docker found"

if ! command -v docker-agent &> /dev/null; then
  error "docker-agent CLI not found. Run setup.sh first."
  exit 1
fi
success "CLI found"

if ! docker network inspect openclaw-agents > /dev/null 2>&1; then
  error "Docker network 'openclaw-agents' not found"
  exit 1
fi
success "Docker network ready"

if ! docker image inspect openclaw-agent-base > /dev/null 2>&1; then
  error "Base image not found. Run setup.sh first."
  exit 1
fi
success "Base image ready"

echo ""
info "Creating test agent: $TEST_AGENT_NAME"
docker-agent create "$TEST_AGENT_NAME" --profile "$PROFILE"

echo ""
info "Waiting for agent to start..."
sleep 3

echo ""
info "Checking agent status"
docker-agent status "$TEST_AGENT_NAME"

echo ""
info "Testing command execution"
docker-agent exec "$TEST_AGENT_NAME" "echo 'Hello from Docker agent'"

echo ""
info "Testing Node.js"
docker-agent exec "$TEST_AGENT_NAME" "node --version"

echo ""
info "Testing npm"
docker-agent exec "$TEST_AGENT_NAME" "npm --version"

echo ""
info "Testing workspace access"
docker-agent exec "$TEST_AGENT_NAME" "ls -la /workspace"

echo ""
info "Listing all agents"
docker-agent list

echo ""
info "Viewing agent logs"
docker-agent logs "$TEST_AGENT_NAME" --tail 20

echo ""
info "Stopping agent"
docker-agent stop "$TEST_AGENT_NAME"

echo ""
info "Starting agent again"
docker-agent start "$TEST_AGENT_NAME"
sleep 2

echo ""
info "Cleaning up test agent"
docker-agent destroy "$TEST_AGENT_NAME" --force --volumes

echo ""
echo "======================================"
success "All tests passed!"
echo "======================================"
echo ""
echo "The Docker Agent System is working correctly."
echo ""

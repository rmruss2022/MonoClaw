#!/bin/bash
# Setup script for Docker Agent System
# Run this after cloning to set up the system

set -e

echo "======================================"
echo "  OpenClaw Docker Agent System Setup"
echo "======================================"
echo ""

# Check prerequisites
echo "Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
  echo "✗ Docker not found. Please install Docker first."
  exit 1
fi
echo "✓ Docker found: $(docker --version)"

# Check Node.js
if ! command -v node &> /dev/null; then
  echo "✗ Node.js not found. Please install Node.js 18+ first."
  exit 1
fi
echo "✓ Node.js found: $(node --version)"

# Check npm
if ! command -v npm &> /dev/null; then
  echo "✗ npm not found. Please install npm first."
  exit 1
fi
echo "✓ npm found: $(npm --version)"

# Check if hub is running
echo ""
echo "Checking hub connection..."
if curl -s http://localhost:9091/health > /dev/null 2>&1; then
  echo "✓ Hub is running on localhost:9091"
else
  echo "⚠ Hub not detected on localhost:9091"
  echo "  The system will work, but agents won't connect until hub is running."
  echo "  Start the hub from: ~/.openclaw/workspace/vm-agent-system/hub"
fi

echo ""
echo "Installing dependencies..."

# Install runtime dependencies
echo "  → Installing agent runtime dependencies..."
cd agent-runtime
npm install --production
cd ..

# Install CLI dependencies
echo "  → Installing CLI dependencies..."
cd cli
npm install
cd ..

echo ""
echo "Building base Docker image..."
cd agent-runtime
docker build -t openclaw-agent-base . || {
  echo "✗ Failed to build base image"
  exit 1
}
cd ..
echo "✓ Base image built: openclaw-agent-base"

echo ""
echo "Setting up CLI..."
cd cli
chmod +x docker-agent
npm link || {
  echo "⚠ Could not link CLI globally (may need sudo)"
  echo "  You can still run: ./cli/docker-agent"
}
cd ..

# Create Docker network
echo ""
echo "Creating Docker network..."
if docker network inspect openclaw-agents > /dev/null 2>&1; then
  echo "✓ Network 'openclaw-agents' already exists"
else
  docker network create openclaw-agents
  echo "✓ Network 'openclaw-agents' created"
fi

# Create logs directory
mkdir -p logs

echo ""
echo "======================================"
echo "  ✓ Setup complete!"
echo "======================================"
echo ""
echo "Quick start:"
echo "  docker-agent create my-builder --profile builder"
echo "  docker-agent list"
echo "  docker-agent status my-builder"
echo "  docker-agent shell my-builder"
echo ""
echo "For more information, see README.md"
echo ""

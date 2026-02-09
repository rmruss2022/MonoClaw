#!/bin/bash

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}VM Agent System Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check Node.js
echo -e "${YELLOW}Checking prerequisites...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js is not installed${NC}"
    echo "Install from: https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo -e "${RED}❌ Node.js version 18 or higher required${NC}"
    echo "Current version: $(node -v)"
    exit 1
fi

echo -e "${GREEN}✓ Node.js $(node -v)${NC}"

# Check Multipass
if ! command -v multipass &> /dev/null; then
    echo -e "${RED}❌ Multipass is not installed${NC}"
    echo "Install from: https://multipass.run/"
    echo ""
    echo "macOS: brew install --cask multipass"
    echo "Ubuntu: sudo snap install multipass"
    exit 1
fi

echo -e "${GREEN}✓ Multipass $(multipass version | head -1)${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Install hub dependencies
echo -e "${YELLOW}Installing hub dependencies...${NC}"
cd "$SCRIPT_DIR/hub"
npm install --silent
echo -e "${GREEN}✓ Hub dependencies installed${NC}"

# Install CLI dependencies
echo -e "${YELLOW}Installing CLI dependencies...${NC}"
cd "$SCRIPT_DIR/cli"
npm install --silent
echo -e "${GREEN}✓ CLI dependencies installed${NC}"

# Install agent runtime dependencies
echo -e "${YELLOW}Installing agent runtime dependencies...${NC}"
cd "$SCRIPT_DIR/agent-runtime"
npm install --silent
echo -e "${GREEN}✓ Agent runtime dependencies installed${NC}"

# Make scripts executable
echo -e "${YELLOW}Setting up executables...${NC}"
chmod +x "$SCRIPT_DIR/cli/vm-agent"
chmod +x "$SCRIPT_DIR/provisioning/create-agent.sh"
chmod +x "$SCRIPT_DIR/test/integration-test.js"
echo -e "${GREEN}✓ Scripts made executable${NC}"

# Create logs directory
mkdir -p "$SCRIPT_DIR/logs"
echo -e "${GREEN}✓ Logs directory created${NC}"

# Symlink CLI to PATH (optional)
echo ""
read -p "Add vm-agent to PATH? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    INSTALL_DIR="/usr/local/bin"
    
    if [ -w "$INSTALL_DIR" ]; then
        ln -sf "$SCRIPT_DIR/cli/vm-agent" "$INSTALL_DIR/vm-agent"
        echo -e "${GREEN}✓ vm-agent linked to $INSTALL_DIR${NC}"
        echo -e "  You can now run: ${BLUE}vm-agent${NC} from anywhere"
    else
        echo -e "${YELLOW}⚠ Need sudo to link to $INSTALL_DIR${NC}"
        sudo ln -sf "$SCRIPT_DIR/cli/vm-agent" "$INSTALL_DIR/vm-agent"
        echo -e "${GREEN}✓ vm-agent linked to $INSTALL_DIR${NC}"
        echo -e "  You can now run: ${BLUE}vm-agent${NC} from anywhere"
    fi
fi

# Setup LaunchAgent (optional)
echo ""
read -p "Setup auto-start hub on boot? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    PLIST_SRC="$SCRIPT_DIR/LaunchAgents/com.openclaw.vm-hub.plist"
    PLIST_DST="$HOME/Library/LaunchAgents/com.openclaw.vm-hub.plist"
    
    # Update paths in plist
    sed "s|/Users/matthew|$HOME|g" "$PLIST_SRC" > "$PLIST_DST"
    
    # Find node path
    NODE_PATH=$(which node)
    sed -i '' "s|/usr/local/bin/node|$NODE_PATH|g" "$PLIST_DST"
    
    # Load it
    launchctl load "$PLIST_DST"
    
    echo -e "${GREEN}✓ Hub will auto-start on login${NC}"
    echo -e "  Manage with: ${BLUE}launchctl list | grep vm-hub${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Next steps:"
echo ""
echo -e "1. Start the hub:"
echo -e "   ${BLUE}cd $SCRIPT_DIR/hub${NC}"
echo -e "   ${BLUE}npm start${NC}"
echo ""
echo -e "2. Create an agent:"
echo -e "   ${BLUE}cd $SCRIPT_DIR/cli${NC}"
echo -e "   ${BLUE}./vm-agent create my-agent${NC}"
echo ""
echo -e "3. View dashboard:"
echo -e "   ${BLUE}http://localhost:9092${NC}"
echo ""
echo -e "4. Read the quick start guide:"
echo -e "   ${BLUE}cat $SCRIPT_DIR/QUICKSTART.md${NC}"
echo ""
echo -e "Documentation:"
echo -e "  • Quick Start: QUICKSTART.md"
echo -e "  • Full Docs:   README.md"
echo -e "  • Architecture: ARCHITECTURE.md"
echo -e "  • Examples:    examples/workflows.md"
echo ""

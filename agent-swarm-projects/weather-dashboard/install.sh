#!/bin/bash
# Installation script for CLI Weather Dashboard

set -e

echo "🌤️  CLI Weather Dashboard - Installation"
echo "========================================"
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is required but not found."
    echo "   Install Python 3 and try again."
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"

# Check and install dependencies
echo ""
echo "📦 Checking dependencies..."

if python3 -c "import requests" 2>/dev/null; then
    echo "✓ requests already installed"
else
    echo "⬇️  Installing requests..."
    pip3 install --break-system-packages requests 2>/dev/null || pip3 install --user requests
fi

if python3 -c "import rich" 2>/dev/null; then
    echo "✓ rich already installed"
else
    echo "⬇️  Installing rich..."
    pip3 install --break-system-packages rich 2>/dev/null || pip3 install --user rich
fi

# Make script executable
echo ""
echo "🔧 Making weather executable..."
chmod +x weather

# Determine installation directory
INSTALL_DIR="/usr/local/bin"
USER_BIN="$HOME/.local/bin"

# Check if we can write to /usr/local/bin
if [ -w "$INSTALL_DIR" ]; then
    TARGET_DIR="$INSTALL_DIR"
elif [ ! -d "$USER_BIN" ]; then
    mkdir -p "$USER_BIN"
    TARGET_DIR="$USER_BIN"
    echo ""
    echo "⚠️  Note: Installing to $USER_BIN"
    echo "   Add this to your PATH if not already there:"
    echo "   export PATH=\"\$HOME/.local/bin:\$PATH\""
else
    TARGET_DIR="$USER_BIN"
fi

# Copy to installation directory
echo ""
echo "📂 Installing weather to $TARGET_DIR..."

if [ -w "$TARGET_DIR" ]; then
    cp weather "$TARGET_DIR/weather"
    echo "✓ Installed successfully!"
else
    echo "🔐 Need sudo permission to install to $TARGET_DIR"
    sudo cp weather "$TARGET_DIR/weather"
    echo "✓ Installed successfully!"
fi

# Verify installation
if command -v weather &> /dev/null; then
    echo ""
    echo "✅ Installation complete!"
    echo ""
    echo "📋 Next steps:"
    echo "   1. Get a free API key: https://openweathermap.org/api"
    echo "   2. Run setup: weather --setup"
    echo "   3. Test it: weather \"Your City\""
    echo ""
    echo "📚 Usage:"
    echo "   weather --help              # Show help"
    echo "   weather Seattle             # Current weather"
    echo "   weather \"Austin, TX\" -m    # Metric units"
    echo "   weather 10001 --days 3      # 3-day forecast"
else
    echo ""
    echo "⚠️  Installation succeeded but 'weather' not found in PATH."
    echo "   Installed to: $TARGET_DIR/weather"
    echo "   You may need to add $TARGET_DIR to your PATH."
fi

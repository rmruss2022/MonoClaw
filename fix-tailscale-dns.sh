#!/bin/bash
# Fix Tailscale DNS so openclaw-hub hostname works locally

set -e

echo "🔧 Fixing Tailscale DNS resolution..."

# Check if already in /etc/hosts
if grep -q "openclaw-hub" /etc/hosts; then
    echo "✅ openclaw-hub already in /etc/hosts"
else
    echo "📝 Adding openclaw-hub to /etc/hosts..."
    echo "100.107.120.47 openclaw-hub openclaw-hub.tail9d821f.ts.net" | sudo tee -a /etc/hosts
    echo "✅ Added openclaw-hub to /etc/hosts"
fi

# Enable Tailscale DNS acceptance (already done via CLI)
tailscale set --accept-dns=true

# Test resolution
echo ""
echo "🧪 Testing resolution..."
if curl -s -m 3 -o /dev/null -w "HTTP %{http_code}\n" http://openclaw-hub:18795/hub | grep -q "200"; then
    echo "✅ SUCCESS: http://openclaw-hub:18795/hub is accessible!"
else
    echo "❌ Still can't reach openclaw-hub:18795/hub"
    echo "But you can use: http://100.107.120.47:18795/hub"
fi

echo ""
echo "📱 On iPhone, use: http://100.107.120.47:18795/hub"
echo "   Or if DNS works: http://openclaw-hub:18795/hub"

#!/bin/bash
# Fix all services to bind to 0.0.0.0 instead of 127.0.0.1

echo "🔧 Fixing service bindings..."

cd ~/.openclaw/workspace

# Find and fix all server files
for file in $(find . -type f \( -name "server.js" -o -name "index.js" -o -name "app.js" \) 2>/dev/null); do
    if grep -q "listen.*127.0.0.1" "$file"; then
        echo "  Fixing: $file"
        sed -i '' "s/server.listen(PORT, '127.0.0.1'/server.listen(PORT, '0.0.0.0'/" "$file"
        sed -i '' "s/app.listen(PORT, '127.0.0.1'/app.listen(PORT, '0.0.0.0'/" "$file"
        sed -i '' "s/listen(port, '127.0.0.1'/listen(port, '0.0.0.0'/" "$file"
        sed -i '' "s/listen(PORT, \"127.0.0.1\"/listen(PORT, \"0.0.0.0\"/" "$file"
    fi
done

echo "✅ Done! Restart services for changes to take effect."
echo ""
echo "Test with:"
echo "  curl http://100.107.120.47:18791/health"
echo "  curl http://100.107.120.47:18796/health"

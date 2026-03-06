#!/bin/bash
# Quick fix to add openclaw-hub to /etc/hosts

echo "Adding openclaw-hub to /etc/hosts..."
echo "100.107.120.47 openclaw-hub openclaw-hub.tail9d821f.ts.net" | sudo tee -a /etc/hosts
echo "✅ Done! Now try: curl http://openclaw-hub:18795/hub"

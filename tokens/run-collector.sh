#!/bin/bash
# Token Cost Collector Runner
# Run data collection and alert checking

cd "$(dirname "$0")"

echo "🚀 Running Token Cost Collector..."
echo "=================================="

# Run collector
node collector.js

# Run alert service
echo ""
echo "🔔 Checking for alerts..."
node alert-service.js

echo ""
echo "✅ Collection cycle complete"

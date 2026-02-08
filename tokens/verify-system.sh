#!/bin/bash
# System Verification Script
# Tests all components of the Token Cost Tracker

echo "🔍 Token Cost Tracker - System Verification"
echo "==========================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

# Test 1: Check files exist
echo "📁 Checking required files..."
FILES=(
    "collector.js"
    "api-server.js"
    "alert-service.js"
    "dashboard.html"
    "config.json"
    "db-schema.sql"
    "run-collector.sh"
)

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  ${GREEN}✓${NC} $file"
    else
        echo -e "  ${RED}✗${NC} $file - MISSING"
        ((ERRORS++))
    fi
done
echo ""

# Test 2: Check Node modules
echo "📦 Checking dependencies..."
if [ -d "node_modules/sqlite3" ]; then
    echo -e "  ${GREEN}✓${NC} sqlite3 installed"
else
    echo -e "  ${YELLOW}⚠${NC} sqlite3 not installed - run: npm install sqlite3"
    ((ERRORS++))
fi
echo ""

# Test 3: Check database
echo "🗄️  Checking database..."
if [ -f "token-costs.db" ]; then
    echo -e "  ${GREEN}✓${NC} Database exists"
    RECORD_COUNT=$(sqlite3 token-costs.db "SELECT COUNT(*) FROM token_usage;" 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo -e "  ${GREEN}✓${NC} Database schema valid ($RECORD_COUNT records)"
    else
        echo -e "  ${RED}✗${NC} Database corrupted"
        ((ERRORS++))
    fi
else
    echo -e "  ${YELLOW}⚠${NC} Database not yet initialized - run: node collector.js"
fi
echo ""

# Test 4: Check API server
echo "🌐 Checking API server..."
if curl -s --connect-timeout 2 http://127.0.0.1:18794/api/costs > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} API server running on port 18794"
    
    # Test each endpoint
    ENDPOINTS=("costs" "budgets" "sessions" "suggestions")
    for endpoint in "${ENDPOINTS[@]}"; do
        RESPONSE=$(curl -s http://127.0.0.1:18794/api/$endpoint)
        if echo "$RESPONSE" | grep -qE "^\{|^\["; then
            echo -e "  ${GREEN}✓${NC} /api/$endpoint responding"
        else
            echo -e "  ${RED}✗${NC} /api/$endpoint failed"
            ((ERRORS++))
        fi
    done
else
    echo -e "  ${RED}✗${NC} API server not running"
    echo "     Start with: launchctl start com.openclaw.token-tracker"
    ((ERRORS++))
fi
echo ""

# Test 5: Check LaunchAgents
echo "🚀 Checking LaunchAgents..."
if launchctl list | grep -q "com.openclaw.token-tracker"; then
    echo -e "  ${GREEN}✓${NC} API server LaunchAgent loaded"
else
    echo -e "  ${YELLOW}⚠${NC} API server LaunchAgent not loaded"
    echo "     Load with: launchctl load ~/Library/LaunchAgents/com.openclaw.token-tracker.plist"
fi

if launchctl list | grep -q "com.openclaw.token-collector"; then
    echo -e "  ${GREEN}✓${NC} Collector LaunchAgent loaded (hourly schedule)"
else
    echo -e "  ${YELLOW}⚠${NC} Collector LaunchAgent not loaded"
    echo "     Load with: launchctl load ~/Library/LaunchAgents/com.openclaw.token-collector.plist"
fi
echo ""

# Test 6: Check configuration
echo "⚙️  Checking configuration..."
if [ -f "config.json" ]; then
    if grep -q "\"telegram\"" config.json && grep -q "\"user_id\"" config.json; then
        echo -e "  ${GREEN}✓${NC} Telegram configured"
    else
        echo -e "  ${YELLOW}⚠${NC} Telegram not configured"
    fi
    
    if grep -q "\"daily\"" config.json && grep -q "\"limit\"" config.json; then
        echo -e "  ${GREEN}✓${NC} Budgets configured"
    else
        echo -e "  ${RED}✗${NC} Budget configuration invalid"
        ((ERRORS++))
    fi
fi
echo ""

# Test 7: Test collector
echo "🔄 Testing collector..."
echo "   Running collector (this may take a few seconds)..."
if node collector.js 2>&1 | grep -q "Collection complete"; then
    echo -e "  ${GREEN}✓${NC} Collector runs successfully"
else
    echo -e "  ${RED}✗${NC} Collector failed - check output above"
    ((ERRORS++))
fi
echo ""

# Test 8: Check logs
echo "📋 Checking logs..."
LOGS=(
    "server-stdout.log"
    "collector-stdout.log"
)

for log in "${LOGS[@]}"; do
    if [ -f "$log" ]; then
        SIZE=$(wc -c < "$log" | tr -d ' ')
        if [ "$SIZE" -gt 0 ]; then
            echo -e "  ${GREEN}✓${NC} $log (${SIZE} bytes)"
        else
            echo -e "  ${YELLOW}⚠${NC} $log (empty)"
        fi
    fi
done
echo ""

# Summary
echo "==========================================="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ All systems operational!${NC}"
    echo ""
    echo "🎉 Token Cost Tracker is ready to use:"
    echo ""
    echo "   Dashboard: http://127.0.0.1:18794/"
    echo "   API: http://127.0.0.1:18794/api/costs"
    echo "   Export: curl -o costs.csv http://127.0.0.1:18794/export/csv"
    echo ""
    echo "   Next steps:"
    echo "   1. Open dashboard in browser"
    echo "   2. Review budgets in config.json"
    echo "   3. Test Telegram alerts (if configured)"
    echo ""
else
    echo -e "${RED}❌ Found $ERRORS issue(s)${NC}"
    echo ""
    echo "   Check the messages above and resolve issues"
    echo "   See SETUP.md for troubleshooting guide"
    echo ""
fi

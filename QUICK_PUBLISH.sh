#!/bin/bash
# Quick publish script for ActivityClaw and ContextClaw

set -e

echo "🦞 OpenClaw Plugin Publisher"
echo ""

# Check npm login
echo "Checking npm authentication..."
if ! npm whoami &> /dev/null; then
    echo "❌ Not logged in to npm"
    echo "Run: npm login"
    exit 1
fi
NPM_USER=$(npm whoami)
echo "✅ Logged in as: $NPM_USER"
echo ""

# Check ClawHub login
echo "Checking ClawHub authentication..."
if ! clawhub whoami &> /dev/null; then
    echo "❌ Not logged in to ClawHub"
    echo "Run: clawhub login"
    echo ""
    read -p "Press Enter to open browser for ClawHub login..."
    clawhub login
fi
CLAWHUB_USER=$(clawhub whoami)
echo "✅ Logged in as: $CLAWHUB_USER"
echo ""

# Publish to npm
echo "📦 Publishing to npm..."
echo ""

echo "Publishing ActivityClaw..."
cd ~/.openclaw/workspace/ActivityClaw
npm publish --access public
echo "✅ ActivityClaw published!"
echo ""

echo "Publishing ContextClaw..."
cd ~/.openclaw/workspace/ContextClaw
npm publish --access public
echo "✅ ContextClaw published!"
echo ""

# Publish skills to ClawHub
echo "📚 Publishing skills to ClawHub..."
echo ""

cd ~/.openclaw/workspace

echo "Publishing activityclaw-usage skill..."
clawhub publish skills/activityclaw-usage \
  --slug activityclaw-usage \
  --name "ActivityClaw Plugin Usage" \
  --version 1.0.0 \
  --changelog "Initial release: Skill for using ActivityClaw plugin" \
  --tags latest,plugin,monitoring,activity
echo "✅ activityclaw-usage skill published!"
echo ""

echo "Publishing contextclaw-usage skill..."
clawhub publish skills/contextclaw-usage \
  --slug contextclaw-usage \
  --name "ContextClaw Plugin Usage" \
  --version 1.0.0 \
  --changelog "Initial release: Skill for using ContextClaw plugin" \
  --tags latest,plugin,context,session,management
echo "✅ contextclaw-usage skill published!"
echo ""

# Summary
echo "🎉 All Done!"
echo ""
echo "Published packages:"
echo "  • @rmruss2022/activityclaw@1.0.0"
echo "  • @rmruss2022/contextclaw@1.0.0"
echo ""
echo "Published skills:"
echo "  • activityclaw-usage"
echo "  • contextclaw-usage"
echo ""
echo "Next steps:"
echo "  1. Post to Discord (see discord-announcements.md)"
echo "  2. Add screenshots to GitHub repos"
echo "  3. Test installation"
echo ""
echo "Verify at:"
echo "  npm: https://www.npmjs.com/package/@rmruss2022/activityclaw"
echo "  npm: https://www.npmjs.com/package/@rmruss2022/contextclaw"
echo "  ClawHub: https://clawhub.ai/skills/activityclaw-usage"
echo "  ClawHub: https://clawhub.ai/skills/contextclaw-usage"

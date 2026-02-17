#!/bin/bash
# Discord Setup Script for Agent Swarm
# Guides you through Discord bot creation and configuration

set -e

echo "🦞 Agent Swarm - Discord Setup"
echo "================================"
echo ""

# Check if .env exists
if [ -f .env ]; then
    echo "⚠️  .env file already exists"
    read -p "Overwrite? (y/N): " overwrite
    if [ "$overwrite" != "y" ]; then
        echo "Aborted."
        exit 0
    fi
fi

echo "📝 Step 1: Create Discord Application"
echo ""
echo "1. Go to: https://discord.com/developers/applications"
echo "2. Click 'New Application'"
echo "3. Name it: 'Agent Swarm Bot' (or whatever you prefer)"
echo "4. Click 'Create'"
echo ""
read -p "Press Enter when done..."

echo ""
echo "📝 Step 2: Create Bot User"
echo ""
echo "1. In your application, go to 'Bot' tab (left sidebar)"
echo "2. Click 'Add Bot'"
echo "3. Confirm 'Yes, do it!'"
echo "4. Under 'Privileged Gateway Intents', enable:"
echo "   - MESSAGE CONTENT INTENT"
echo "   - SERVER MEMBERS INTENT"
echo "5. Click 'Reset Token'"
echo "6. Copy your bot token (keep it secret!)"
echo ""
read -p "Press Enter when you have your token..."

echo ""
read -sp "Paste your Discord Bot Token: " BOT_TOKEN
echo ""

if [ -z "$BOT_TOKEN" ]; then
    echo "❌ Bot token is required"
    exit 1
fi

echo ""
echo "📝 Step 3: Invite Bot to Your Server"
echo ""
echo "1. In your application, go to 'OAuth2' > 'URL Generator'"
echo "2. Select scopes:"
echo "   - bot"
echo "   - applications.commands"
echo "3. Select bot permissions:"
echo "   - Manage Channels"
echo "   - Manage Webhooks"
echo "   - Send Messages"
echo "   - Create Public Threads"
echo "   - Manage Threads"
echo "   - Read Message History"
echo "   - Add Reactions"
echo "4. Copy the generated URL at the bottom"
echo "5. Open that URL in a browser"
echo "6. Select your Discord server and authorize"
echo ""
read -p "Press Enter when bot is in your server..."

echo ""
echo "📝 Step 4: Get Server (Guild) ID"
echo ""
echo "1. Open Discord"
echo "2. Enable Developer Mode:"
echo "   - User Settings > Advanced > Developer Mode (toggle ON)"
echo "3. Right-click your server name"
echo "4. Click 'Copy Server ID'"
echo ""
read -p "Paste your Discord Server (Guild) ID: " GUILD_ID
echo ""

if [ -z "$GUILD_ID" ]; then
    echo "❌ Guild ID is required"
    exit 1
fi

# Create .env file
cat > .env << EOF
# Discord Configuration
DISCORD_BOT_TOKEN=$BOT_TOKEN
DISCORD_GUILD_ID=$GUILD_ID

# Server Configuration
PORT=18798
EOF

echo ""
echo "✅ Configuration saved to .env"
echo ""

# Test the bot
echo "🧪 Testing Discord bot connection..."
echo ""

node -e "
const axios = require('axios');

const botToken = '$BOT_TOKEN';
const guildId = '$GUILD_ID';

axios.get('https://discord.com/api/v10/users/@me', {
  headers: { 'Authorization': \`Bot \${botToken}\` }
})
.then(res => {
  console.log('✅ Bot authenticated as:', res.data.username);
  return axios.get(\`https://discord.com/api/v10/guilds/\${guildId}\`, {
    headers: { 'Authorization': \`Bot \${botToken}\` }
  });
})
.then(res => {
  console.log('✅ Bot has access to server:', res.data.name);
  console.log('');
  console.log('🎉 Discord setup complete!');
  console.log('');
  console.log('Next steps:');
  console.log('1. Start the server: node server-enhanced.js');
  console.log('2. Create a project via dashboard');
  console.log('3. Discord channels will be auto-created!');
  console.log('');
})
.catch(err => {
  console.error('❌ Error:', err.response?.data || err.message);
  console.error('');
  console.error('Common issues:');
  console.error('- Invalid bot token');
  console.error('- Bot not in server');
  console.error('- Missing permissions');
  process.exit(1);
});
" 2>/dev/null || {
    echo "⚠️  Could not test connection (axios not installed?)"
    echo "   Run: npm install"
    echo "   Then start server to test"
}

echo ""
echo "📁 Your .env file:"
cat .env
echo ""
echo "⚠️  IMPORTANT: Add .env to .gitignore!"
echo "   Never commit your bot token to Git!"
echo ""

# Add to .gitignore if it exists
if [ -f .gitignore ]; then
    if ! grep -q "^\.env$" .gitignore; then
        echo ".env" >> .gitignore
        echo "✅ Added .env to .gitignore"
    fi
else
    echo ".env" > .gitignore
    echo "✅ Created .gitignore with .env"
fi

echo ""
echo "🚀 Setup complete!"
echo ""
echo "Start the server:"
echo "  node server-enhanced.js"
echo ""
echo "Then create a project in the dashboard - Discord channels will be auto-created!"

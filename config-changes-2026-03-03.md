# OpenClaw Config Changes - March 3, 2026

## Telegram Group Bot Configuration

### Changes Made
Added multiple bot configurations to enable bot-to-bot communication in Telegram groups:

1. **Atlas Bot** (@atlas9999bot)
   - Session: `telegram-atlas`
   - Bot token: configured
   - Chat allowlist: Matthew (5574760589) + Sage bot (8450341551)
   - Group allowlist: Big Tiger (-1003820523901)

2. **Sage Bot** (@sage99bot)
   - Session: `telegram-sage`
   - Bot token: configured
   - Chat allowlist: Matthew (5574760589) + Atlas bot (8789358633)
   - Group allowlist: Big Tiger (-1003820523901)

3. **Tiger Bot** (@tigerbot99bot) - existing
   - Session: `telegram-tiger` (main)
   - Updated chat allowlist to include both Atlas and Sage bots

### Key Implementation Details
- Added bot Telegram IDs to each other's allowlists to enable cross-bot mentions
- Configured group allowlists to permit operation in "Big Tiger" group
- Each bot runs in its own isolated session
- Router logic handles session-to-bot mapping

### File: ~/.openclaw/openclaw.json
Location: Not version controlled (local config only)

### Security Note
Bot tokens are sensitive credentials - not committed to git.

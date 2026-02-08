# Setup Guide - Token Cost Tracker

## Quick Start

### 1. Install Dependencies
```bash
cd /Users/matthew/.openclaw/workspace/tokens
npm install sqlite3
```

### 2. Configure Settings
Edit `config.json`:
```bash
nano config.json
```

Update:
- `budgets` - Set your daily/weekly/monthly budget limits
- `alerts.telegram.user_id` - Your Telegram user ID (if using alerts)
- `pricing` - Add/update model pricing as needed

### 3. Initialize Database
Run collector once to create database:
```bash
node collector.js
```

You should see:
```
✅ Database initialized
📊 Collecting token usage data...
📋 Found X active sessions
💵 Current total cost: $X.XX
✅ Stored X session records
💰 DAILY Budget: $X.XX / $X.XX (XX.X%)
✅ Collection complete
```

### 4. Start API Server
The API server should auto-start via LaunchAgent. To verify:
```bash
curl http://127.0.0.1:18794/api/budgets
```

If not running:
```bash
launchctl load ~/Library/LaunchAgents/com.openclaw.token-tracker.plist
```

### 5. View Dashboard
Open in browser:
```
http://127.0.0.1:18794/
```

### 6. Set Up Scheduled Collection

**Option A: OpenClaw Cron (Recommended)**
```bash
openclaw cron add --label token-collector \
  --schedule "0 * * * *" \
  --command "cd /Users/matthew/.openclaw/workspace/tokens && ./run-collector.sh"
```

**Option B: System Cron**
```bash
crontab -e
```
Add:
```
0 * * * * /Users/matthew/.openclaw/workspace/tokens/run-collector.sh >> /Users/matthew/.openclaw/workspace/tokens/cron.log 2>&1
```

### 7. Test Alerts (Optional)
Create a test alert:
```bash
sqlite3 token-costs.db "INSERT INTO alerts (timestamp, type, severity, message, details) VALUES ($(date +%s000), 'test', 'info', 'Test alert', '{}')"
node alert-service.js
```

Check your Telegram for the alert.

---

## Detailed Configuration

### Model Pricing

Add or update model pricing in `config.json`:

```json
"pricing": {
  "your-model-name": {
    "input": 3.00,      // Cost per 1M input tokens (USD)
    "output": 15.00,    // Cost per 1M output tokens (USD)
    "per_tokens": 1000000
  }
}
```

**Current prices (as of Feb 2026):**
- Claude Opus 4: $15/$75 per 1M tokens
- Claude Sonnet 4/3.5: $3/$15 per 1M tokens
- Kimi K2.5: Free

### Budget Configuration

```json
"budgets": {
  "daily": {
    "enabled": true,              // Enable/disable daily budget
    "limit": 5.00,                // Daily budget in USD
    "alert_thresholds": [0.8, 0.9, 1.0]  // Alert at 80%, 90%, 100%
  },
  "weekly": {
    "enabled": true,
    "limit": 30.00,               // Weekly budget in USD
    "alert_thresholds": [0.8, 0.9, 1.0]
  },
  "monthly": {
    "enabled": true,
    "limit": 120.00,              // Monthly budget in USD
    "alert_thresholds": [0.8, 0.9, 1.0]
  }
}
```

**Tips:**
- Start with conservative budgets and adjust based on usage
- Use thresholds to get warnings before budget is exceeded
- Disable periods you don't need (e.g., weekly if you only care about monthly)

### Alert Configuration

```json
"alerts": {
  "telegram": {
    "enabled": true,
    "user_id": "YOUR_TELEGRAM_USER_ID"
  },
  "email": {
    "enabled": false,             // Email alerts not yet implemented
    "to": ""
  },
  "cooldown_minutes": 60          // Min time between similar alerts
}
```

**Finding your Telegram User ID:**
1. Message @userinfobot on Telegram
2. It will reply with your user ID
3. Update `user_id` in config.json

### Collection Settings

```json
"collection": {
  "interval_minutes": 60,         // How often to collect (for cron)
  "retention_days": 90,           // How long to keep historical data
  "input_output_ratio": 0.6       // Estimated input/output token ratio
}
```

**Notes:**
- `input_output_ratio`: OpenClaw doesn't expose input/output split, so we estimate. 0.6 = 60% input, 40% output. Adjust based on your usage patterns.
- `retention_days`: Older data is auto-deleted. Increase for longer history.
- `interval_minutes`: Used for documentation only; actual schedule set in cron.

---

## LaunchAgent Setup

The API server runs automatically via macOS LaunchAgent.

**Location:** `~/Library/LaunchAgents/com.openclaw.token-tracker.plist`

**Control commands:**
```bash
# Start
launchctl start com.openclaw.token-tracker

# Stop
launchctl stop com.openclaw.token-tracker

# Restart
launchctl stop com.openclaw.token-tracker
launchctl start com.openclaw.token-tracker

# Reload after config change
launchctl unload ~/Library/LaunchAgents/com.openclaw.token-tracker.plist
launchctl load ~/Library/LaunchAgents/com.openclaw.token-tracker.plist

# Check status
launchctl list | grep token-tracker
```

**Logs:**
- stdout: `/Users/matthew/.openclaw/workspace/tokens/server-stdout.log`
- stderr: `/Users/matthew/.openclaw/workspace/tokens/server-stderr.log`

---

## Testing

### Test Data Collection
```bash
cd /Users/matthew/.openclaw/workspace/tokens
node collector.js
```

Expected output:
```
✅ Database initialized
📊 Collecting token usage data...
📋 Found X active sessions
💵 Current total cost: $X.XX
✅ Stored X session records
💰 DAILY Budget: $X.XX / $X.XX (XX.X%)
💰 WEEKLY Budget: $X.XX / $X.XX (XX.X%)
💰 MONTHLY Budget: $X.XX / $X.XX (XX.X%)
✅ Collection complete
```

### Test API Endpoints
```bash
# Check budgets
curl http://127.0.0.1:18794/api/budgets

# Check costs
curl http://127.0.0.1:18794/api/costs

# Check sessions
curl http://127.0.0.1:18794/api/sessions

# Check suggestions
curl http://127.0.0.1:18794/api/suggestions
```

### Test Alert Service
```bash
node alert-service.js
```

Expected output:
```
🔔 Alert Service Starting...
✅ No pending alerts  (or)  📬 Processing X pending alert(s)...
✅ Alert service complete
```

### Test Dashboard
1. Open: http://127.0.0.1:18794/
2. Should load within 1-2 seconds
3. Check that:
   - Spending cards show data
   - Budget bars are visible
   - Model list populated
   - Chart renders
   - Sessions table has data

---

## Troubleshooting

### Database not created
```bash
# Check if collector ran successfully
node collector.js

# Verify database exists
ls -lh token-costs.db

# Check schema
sqlite3 token-costs.db ".schema"
```

### API server not responding
```bash
# Check if running
curl http://127.0.0.1:18794/api/costs

# Check LaunchAgent
launchctl list | grep token

# Check logs
tail -50 server-stderr.log

# Restart
launchctl stop com.openclaw.token-tracker
launchctl start com.openclaw.token-tracker
```

### No data in dashboard
```bash
# Run collector manually
node collector.js

# Check database
sqlite3 token-costs.db "SELECT COUNT(*) FROM token_usage;"

# If zero, check OpenClaw status format
/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw status --sessions
```

### Alerts not sending
```bash
# Check Telegram config
cat config.json | grep -A5 telegram

# Test OpenClaw message command
/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw message send \
  --target YOUR_USER_ID \
  --message "Test" \
  --channel telegram

# Check alert service
node alert-service.js

# Check for pending alerts
sqlite3 token-costs.db "SELECT * FROM alerts WHERE sent = 0;"
```

### High memory usage
```bash
# Check database size
ls -lh token-costs.db

# If very large, reduce retention
sqlite3 token-costs.db "DELETE FROM token_usage WHERE created_at < datetime('now', '-30 days');"
sqlite3 token-costs.db "VACUUM;"
```

---

## Upgrading from Legacy Tracker

If you had the old `tracker.js` system:

1. **Backup old data:**
   ```bash
   cp usage-history.json usage-history.json.backup
   ```

2. **The new system is backward compatible** - old data is preserved but not used

3. **Dashboard automatically upgraded** - `dashboard.html` now uses new APIs

4. **Old files you can keep:**
   - `usage-history.json` (legacy data, not used)
   - `tracker.js` (old collector, not used)
   - `server.js` (replaced by `api-server.js`)

5. **New files:**
   - `collector.js` - New collector with cost tracking
   - `api-server.js` - Enhanced API with more endpoints
   - `alert-service.js` - Alert delivery system
   - `token-costs.db` - SQLite database
   - `config.json` - Configuration file

---

## Maintenance

### Daily
- Check dashboard for anomalies
- Review alerts (if any)

### Weekly
- Check optimization suggestions
- Review top sessions by cost
- Verify cron is running

### Monthly
- Export data for archiving
- Review budget allocation
- Update model pricing if needed

---

## Uninstall

To completely remove the system:

```bash
# Stop services
launchctl unload ~/Library/LaunchAgents/com.openclaw.token-tracker.plist
openclaw cron remove token-collector

# Remove files
cd /Users/matthew/.openclaw/workspace/tokens
rm token-costs.db config.json alert-state.json
rm server-*.log cron.log

# Remove LaunchAgent
rm ~/Library/LaunchAgents/com.openclaw.token-tracker.plist

# Optional: Remove entire directory
cd ..
rm -rf tokens
```

---

## Support

For issues:
1. Check logs: `server-stderr.log`, `cron.log`
2. Run collector manually to see errors
3. Check database: `sqlite3 token-costs.db`
4. Review `COST_TRACKER.md` for detailed docs
5. Check `API.md` for endpoint reference

---

**Setup Version:** 2.0.0
**Last Updated:** February 8, 2026

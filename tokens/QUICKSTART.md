# ⚡ Quick Start - 5 Minutes to Cost Tracking

## 🎯 Goal
Get your token cost tracker up and running in 5 minutes.

## ✅ Step 1: Verify Installation (30 seconds)
```bash
cd /Users/matthew/.openclaw/workspace/tokens
./verify-system.sh
```

You should see: **✅ All systems operational!**

## 📊 Step 2: Open Dashboard (10 seconds)
```bash
open http://127.0.0.1:18794/
```

Or visit in your browser: **http://127.0.0.1:18794/**

## 👀 What You'll See

### Dashboard Overview
- **Spending Cards** - Today, this week, this month
- **Budget Progress** - Visual bars showing budget usage
- **Model Costs** - Which models are costing you most
- **30-Day Trend Chart** - Spending over time
- **Optimization Tips** - Save money with suggestions
- **Session Breakdown** - Top sessions by cost

## 💰 Current Status (As of Deployment)
- **Today's Spending:** $4.34 / $5.00 (86.9%)
- **Active Sessions:** 9
- **Primary Model:** claude-sonnet-4-5
- **System Status:** 🟢 Operational

## 🔄 How It Works

1. **Every Hour** - System collects token usage from OpenClaw
2. **Calculates Costs** - Based on model pricing (Sonnet: $3/$15 per 1M tokens)
3. **Checks Budgets** - Alerts if approaching limits
4. **Updates Dashboard** - Real-time data refresh every 5 minutes

## 🚨 Test Alerts (Optional)

Want to test Telegram alerts? Create a test budget alert:

```bash
cd /Users/matthew/.openclaw/workspace/tokens
sqlite3 token-costs.db "INSERT INTO alerts (timestamp, type, severity, message, details) VALUES ($(date +%s000), 'budget_warning', 'warning', 'Test Alert: Daily budget at 90%', '{\"period\":\"daily\",\"spent\":4.5,\"limit\":5.0,\"percentage\":90}');"
node alert-service.js
```

Check your Telegram for the alert!

## 📈 Useful Commands

### Check Current Costs
```bash
curl -s http://127.0.0.1:18794/api/costs | python3 -m json.tool
```

### Check Budget Status
```bash
curl -s http://127.0.0.1:18794/api/budgets | python3 -m json.tool
```

### Export Data
```bash
curl -o my-costs.csv http://127.0.0.1:18794/export/csv
open my-costs.csv
```

### Manual Collection
```bash
cd /Users/matthew/.openclaw/workspace/tokens
node collector.js
```

### Check Logs
```bash
tail -20 /Users/matthew/.openclaw/workspace/tokens/collector-stdout.log
tail -20 /Users/matthew/.openclaw/workspace/tokens/server-stdout.log
```

## ⚙️ Customize Your Budgets

Edit `config.json`:
```bash
cd /Users/matthew/.openclaw/workspace/tokens
nano config.json
```

Change budget limits:
```json
"budgets": {
  "daily": { "enabled": true, "limit": 10.00 },
  "weekly": { "enabled": true, "limit": 60.00 },
  "monthly": { "enabled": true, "limit": 200.00 }
}
```

No restart needed - changes take effect on next collection.

## 🎓 Learn More

- **[README.md](README.md)** - Overview and features
- **[COST_TRACKER.md](COST_TRACKER.md)** - Complete system documentation
- **[API.md](API.md)** - API endpoints reference
- **[SETUP.md](SETUP.md)** - Detailed setup and troubleshooting

## 🏁 You're Done!

Your token cost tracker is now:
- ✅ Collecting data every hour
- ✅ Tracking costs per model
- ✅ Monitoring budgets
- ✅ Ready to send alerts
- ✅ Showing real-time dashboard

## 💡 Pro Tips

1. **Bookmark the dashboard:** Add http://127.0.0.1:18794/ to your bookmarks
2. **Check weekly:** Review optimization suggestions every Monday
3. **Export monthly:** Download CSV for long-term analysis
4. **Adjust budgets:** Fine-tune based on actual usage patterns
5. **Watch the trend:** Use 30-day chart to predict future costs

## 🆘 Having Issues?

Run the verification script:
```bash
./verify-system.sh
```

Or check [SETUP.md](SETUP.md) for troubleshooting.

---

**Quick Access:**
- Dashboard: http://127.0.0.1:18794/
- Export CSV: http://127.0.0.1:18794/export/csv
- API Costs: http://127.0.0.1:18794/api/costs

**Time to Production:** 5 minutes ⚡  
**System Status:** 🟢 Ready to use

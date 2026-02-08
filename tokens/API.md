# API Documentation

## Base URL
```
http://127.0.0.1:18794
```

## Endpoints

### Dashboard
```http
GET /
```
Returns the HTML dashboard interface.

---

### Cost Summary
```http
GET /api/costs
```

Returns comprehensive cost data including model breakdown and spending trends.

**Response:**
```json
{
  "modelCosts": [
    {
      "model": "claude-sonnet-4-5",
      "total_cost": 1.443,
      "total_input": 172800,
      "total_output": 115200,
      "session_count": 9,
      "last_seen": 1739025018989
    }
  ],
  "dailyTrend": [
    {
      "date": "2026-02-08",
      "cost": 1.443,
      "tokens": 288000
    }
  ],
  "spending": {
    "today": 1.443,
    "week": 1.443,
    "month": 1.443
  }
}
```

---

### Budget Status
```http
GET /api/budgets
```

Returns current budget usage for all configured periods.

**Response:**
```json
{
  "daily": {
    "spent": 1.443,
    "limit": 5.0,
    "percentage": 28.86,
    "enabled": true
  },
  "weekly": {
    "spent": 1.443,
    "limit": 30.0,
    "percentage": 4.81,
    "enabled": true
  },
  "monthly": {
    "spent": 1.443,
    "limit": 120.0,
    "percentage": 1.20,
    "enabled": true
  }
}
```

---

### Session Breakdown
```http
GET /api/sessions
```

Returns top 20 sessions by cost in the last 7 days.

**Response:**
```json
[
  {
    "session_key": "agent:main:main",
    "model": "claude-sonnet-4-5",
    "total_cost": 0.558,
    "total_tokens": 93000,
    "data_points": 26,
    "last_active": 1739025018989
  }
]
```

---

### Optimization Suggestions
```http
GET /api/suggestions
```

Returns AI-generated optimization recommendations.

**Response:**
```json
[
  {
    "type": "model_switch",
    "title": "Switch to Sonnet for routine tasks",
    "description": "Opus is costing $12.50/week. Switching appropriate tasks to Sonnet could save ~$10.00/week (80% cost reduction).",
    "impact": "high",
    "savingsEstimate": 10.0
  },
  {
    "type": "session_cleanup",
    "title": "Clean up idle sessions",
    "description": "You have 15 sessions tracked but only 3 active in the last hour. Consider closing unused sessions.",
    "impact": "medium"
  }
]
```

**Suggestion Types:**
- `model_switch` - Recommend cheaper model for certain workloads
- `session_cleanup` - Recommend closing idle sessions
- `cost_spike` - Alert to unusual cost increases
- `usage_pattern` - Insights on usage patterns

**Impact Levels:**
- `high` - Significant cost savings or critical issue
- `medium` - Moderate impact
- `low` - Minor optimization

---

### Configuration
```http
GET /api/config
```

Returns the current system configuration.

**Response:**
```json
{
  "pricing": {
    "claude-opus-4": {
      "input": 15.0,
      "output": 75.0,
      "per_tokens": 1000000
    }
  },
  "budgets": {
    "daily": {
      "enabled": true,
      "limit": 5.0,
      "alert_thresholds": [0.8, 0.9, 1.0]
    }
  },
  "alerts": {
    "telegram": {
      "enabled": true,
      "user_id": "5574760589"
    }
  }
}
```

---

### Export CSV
```http
GET /export/csv
```

Downloads all historical data as CSV.

**Response:** CSV file with headers:
```
Timestamp,Session,Model,Tokens In,Tokens Out,Tokens Total,Cost In,Cost Out,Cost Total
```

**Download:**
```bash
curl -o token-costs.csv http://127.0.0.1:18794/export/csv
```

---

### Legacy Data (Backward Compatibility)
```http
GET /data
```

Returns legacy token usage data format for backward compatibility with old dashboard.

**Response:**
```json
{
  "history": [
    {
      "timestamp": 1739025018989,
      "date": "2026-02-08T16:00:17.293Z",
      "tokensUsed": "31k",
      "tokensTotal": "1000k",
      "usagePercent": 3,
      "activeSessions": 9,
      "model": "claude-sonnet-4-5"
    }
  ],
  "summary": null
}
```

---

## Error Handling

All endpoints return JSON errors with this format:

```json
{
  "error": "Error message here"
}
```

**HTTP Status Codes:**
- `200` - Success
- `404` - Endpoint not found
- `500` - Server error (database, parsing, etc.)

---

## CORS

All API endpoints support CORS with:
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST
```

---

## Rate Limiting

No rate limiting currently implemented. All endpoints are localhost-only.

---

## Authentication

None required. Server binds to `127.0.0.1` (localhost only).

---

## Websockets

Not currently supported. Dashboard uses polling with 5-minute intervals.

---

## Example Usage

### JavaScript/Fetch
```javascript
// Get current costs
const response = await fetch('http://127.0.0.1:18794/api/costs');
const data = await response.json();
console.log('Today:', data.spending.today);

// Get budget status
const budgets = await fetch('http://127.0.0.1:18794/api/budgets');
const budgetData = await budgets.json();
console.log('Daily budget:', budgetData.daily);
```

### curl
```bash
# Get costs
curl http://127.0.0.1:18794/api/costs

# Get budgets
curl http://127.0.0.1:18794/api/budgets

# Export CSV
curl -o costs.csv http://127.0.0.1:18794/export/csv

# Pretty print JSON
curl http://127.0.0.1:18794/api/costs | python3 -m json.tool
```

### Python
```python
import requests

# Get costs
response = requests.get('http://127.0.0.1:18794/api/costs')
data = response.json()
print(f"Today's spending: ${data['spending']['today']:.2f}")

# Check budgets
budgets = requests.get('http://127.0.0.1:18794/api/budgets').json()
for period, budget in budgets.items():
    if budget['enabled']:
        print(f"{period.title()}: ${budget['spent']:.2f} / ${budget['limit']:.2f} ({budget['percentage']:.1f}%)")
```

---

## Database Direct Access

For advanced queries, you can access the SQLite database directly:

```bash
sqlite3 /Users/matthew/.openclaw/workspace/tokens/token-costs.db
```

**Useful queries:**

```sql
-- Total cost by model (all time)
SELECT model, SUM(cost_total) as total_cost
FROM token_usage
GROUP BY model
ORDER BY total_cost DESC;

-- Daily spending trend
SELECT DATE(created_at) as date, SUM(cost_total) as cost
FROM token_usage
GROUP BY date
ORDER BY date DESC
LIMIT 30;

-- Most expensive sessions
SELECT session_key, SUM(cost_total) as total_cost, COUNT(*) as records
FROM token_usage
GROUP BY session_key
ORDER BY total_cost DESC
LIMIT 10;

-- Recent alerts
SELECT * FROM alerts
WHERE sent = 1
ORDER BY timestamp DESC
LIMIT 10;
```

---

**API Version:** 2.0.0
**Last Updated:** February 8, 2026

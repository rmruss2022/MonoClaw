-- Token Cost Tracking Database Schema

-- Main token usage table
CREATE TABLE IF NOT EXISTS token_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    session_key TEXT NOT NULL,
    model TEXT NOT NULL,
    tokens_used INTEGER NOT NULL,
    tokens_total INTEGER NOT NULL,
    tokens_input INTEGER,
    tokens_output INTEGER,
    cost_input REAL DEFAULT 0,
    cost_output REAL DEFAULT 0,
    cost_total REAL DEFAULT 0,
    session_age TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_timestamp ON token_usage(timestamp);
CREATE INDEX IF NOT EXISTS idx_model ON token_usage(model);
CREATE INDEX IF NOT EXISTS idx_session ON token_usage(session_key);
CREATE INDEX IF NOT EXISTS idx_created ON token_usage(created_at);

-- Budget tracking table
CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT NOT NULL, -- 'daily', 'weekly', 'monthly'
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    limit_amount REAL NOT NULL,
    spent_amount REAL DEFAULT 0,
    model_filter TEXT, -- NULL for all models
    active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_budget_period ON budgets(period, active);
CREATE INDEX IF NOT EXISTS idx_budget_dates ON budgets(start_date, end_date);

-- Alerts table
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    type TEXT NOT NULL, -- 'budget_warning', 'cost_spike', 'unusual_pattern'
    severity TEXT NOT NULL, -- 'info', 'warning', 'critical'
    message TEXT NOT NULL,
    details TEXT, -- JSON with additional context
    acknowledged BOOLEAN DEFAULT 0,
    sent BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alert_type ON alerts(type);
CREATE INDEX IF NOT EXISTS idx_alert_sent ON alerts(sent, acknowledged);

-- Spending summary view
CREATE VIEW IF NOT EXISTS daily_spending AS
SELECT 
    DATE(created_at) as date,
    model,
    SUM(tokens_input) as total_input_tokens,
    SUM(tokens_output) as total_output_tokens,
    SUM(cost_total) as total_cost,
    COUNT(DISTINCT session_key) as session_count
FROM token_usage
GROUP BY DATE(created_at), model
ORDER BY date DESC, total_cost DESC;

-- Model efficiency view
CREATE VIEW IF NOT EXISTS model_efficiency AS
SELECT 
    model,
    COUNT(*) as data_points,
    SUM(tokens_used) as total_tokens,
    SUM(cost_total) as total_cost,
    AVG(cost_total) as avg_cost_per_sample,
    SUM(cost_total) / NULLIF(SUM(tokens_used), 0) * 1000000 as cost_per_million_tokens
FROM token_usage
WHERE created_at >= datetime('now', '-30 days')
GROUP BY model
ORDER BY total_cost DESC;

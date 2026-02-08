#!/usr/bin/env node

/**
 * Enhanced Token Cost Tracking API Server
 * Serves rich cost data, budgets, reports, and exports
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const url = require('url');
const sqlite3 = require('sqlite3').verbose();

const PORT = 18794;
const DB_FILE = path.join(__dirname, 'token-costs.db');
const CONFIG_FILE = path.join(__dirname, 'config.json');
const LEGACY_DATA_FILE = path.join(__dirname, 'usage-history.json');

let config;
try {
    config = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'));
} catch (error) {
    console.error('Failed to load config:', error.message);
    config = {};
}

function query(sql, params = []) {
    return new Promise((resolve, reject) => {
        const db = new sqlite3.Database(DB_FILE, (err) => {
            if (err) return reject(err);
            
            db.all(sql, params, (err, rows) => {
                db.close();
                if (err) return reject(err);
                resolve(rows);
            });
        });
    });
}

function queryOne(sql, params = []) {
    return new Promise((resolve, reject) => {
        const db = new sqlite3.Database(DB_FILE, (err) => {
            if (err) return reject(err);
            
            db.get(sql, params, (err, row) => {
                db.close();
                if (err) return reject(err);
                resolve(row);
            });
        });
    });
}

async function getCostSummary() {
    try {
        // Current costs by model
        const modelCosts = await query(`
            SELECT 
                model,
                SUM(cost_total) as total_cost,
                SUM(tokens_input) as total_input,
                SUM(tokens_output) as total_output,
                COUNT(DISTINCT session_key) as session_count,
                MAX(timestamp) as last_seen
            FROM token_usage
            WHERE timestamp >= ? 
            GROUP BY model
            ORDER BY total_cost DESC
        `, [Date.now() - 24 * 60 * 60 * 1000]);
        
        // Daily spending trend (last 30 days)
        const dailyTrend = await query(`
            SELECT 
                DATE(created_at) as date,
                SUM(cost_total) as cost,
                SUM(tokens_used) as tokens
            FROM token_usage
            WHERE created_at >= datetime('now', '-30 days')
            GROUP BY DATE(created_at)
            ORDER BY date ASC
        `);
        
        // Total spending periods
        const today = await queryOne(`
            SELECT SUM(cost_total) as cost FROM token_usage 
            WHERE created_at >= datetime('now', 'start of day')
        `);
        
        const thisWeek = await queryOne(`
            SELECT SUM(cost_total) as cost FROM token_usage 
            WHERE created_at >= datetime('now', '-7 days')
        `);
        
        const thisMonth = await queryOne(`
            SELECT SUM(cost_total) as cost FROM token_usage 
            WHERE created_at >= datetime('now', 'start of month')
        `);
        
        return {
            modelCosts,
            dailyTrend,
            spending: {
                today: today?.cost || 0,
                week: thisWeek?.cost || 0,
                month: thisMonth?.cost || 0
            }
        };
    } catch (error) {
        throw new Error('Database error: ' + error.message);
    }
}

async function getBudgetStatus() {
    const today = await queryOne(`
        SELECT SUM(cost_total) as cost FROM token_usage 
        WHERE created_at >= datetime('now', 'start of day')
    `);
    
    const thisWeek = await queryOne(`
        SELECT SUM(cost_total) as cost FROM token_usage 
        WHERE created_at >= datetime('now', '-7 days')
    `);
    
    const thisMonth = await queryOne(`
        SELECT SUM(cost_total) as cost FROM token_usage 
        WHERE created_at >= datetime('now', 'start of month')
    `);
    
    return {
        daily: {
            spent: today?.cost || 0,
            limit: config.budgets?.daily?.limit || 0,
            percentage: ((today?.cost || 0) / (config.budgets?.daily?.limit || 1)) * 100,
            enabled: config.budgets?.daily?.enabled || false
        },
        weekly: {
            spent: thisWeek?.cost || 0,
            limit: config.budgets?.weekly?.limit || 0,
            percentage: ((thisWeek?.cost || 0) / (config.budgets?.weekly?.limit || 1)) * 100,
            enabled: config.budgets?.weekly?.enabled || false
        },
        monthly: {
            spent: thisMonth?.cost || 0,
            limit: config.budgets?.monthly?.limit || 0,
            percentage: ((thisMonth?.cost || 0) / (config.budgets?.monthly?.limit || 1)) * 100,
            enabled: config.budgets?.monthly?.enabled || false
        }
    };
}

async function getSessionBreakdown() {
    return await query(`
        SELECT 
            session_key,
            model,
            SUM(cost_total) as total_cost,
            SUM(tokens_used) as total_tokens,
            COUNT(*) as data_points,
            MAX(timestamp) as last_active
        FROM token_usage
        WHERE timestamp >= ?
        GROUP BY session_key, model
        ORDER BY total_cost DESC
        LIMIT 20
    `, [Date.now() - 7 * 24 * 60 * 60 * 1000]);
}

async function getOptimizationSuggestions() {
    const modelUsage = await query(`
        SELECT 
            model,
            SUM(tokens_used) as total_tokens,
            SUM(cost_total) as total_cost,
            COUNT(DISTINCT session_key) as session_count
        FROM token_usage
        WHERE created_at >= datetime('now', '-7 days')
        GROUP BY model
        ORDER BY total_cost DESC
    `);
    
    const suggestions = [];
    
    // Check if expensive models are being used heavily
    const opusUsage = modelUsage.find(m => m.model.includes('opus'));
    const sonnetUsage = modelUsage.find(m => m.model.includes('sonnet'));
    
    if (opusUsage && sonnetUsage && opusUsage.total_cost > sonnetUsage.total_cost * 2) {
        const potentialSavings = opusUsage.total_cost - (opusUsage.total_tokens / 1000000 * 3);
        suggestions.push({
            type: 'model_switch',
            title: 'Switch to Sonnet for routine tasks',
            description: `Opus is costing $${opusUsage.total_cost.toFixed(2)}/week. Switching appropriate tasks to Sonnet could save ~$${potentialSavings.toFixed(2)}/week (80% cost reduction).`,
            impact: 'high',
            savingsEstimate: potentialSavings
        });
    }
    
    // Check for idle sessions
    const recentActivity = await query(`
        SELECT COUNT(DISTINCT session_key) as active_sessions
        FROM token_usage
        WHERE timestamp >= ?
    `, [Date.now() - 60 * 60 * 1000]);
    
    const allSessions = await query(`
        SELECT COUNT(DISTINCT session_key) as total_sessions
        FROM token_usage
        WHERE timestamp >= ?
    `, [Date.now() - 24 * 60 * 60 * 1000]);
    
    if (allSessions[0]?.total_sessions > recentActivity[0]?.active_sessions * 2) {
        suggestions.push({
            type: 'session_cleanup',
            title: 'Clean up idle sessions',
            description: `You have ${allSessions[0]?.total_sessions} sessions tracked but only ${recentActivity[0]?.active_sessions} active in the last hour. Consider closing unused sessions.`,
            impact: 'medium'
        });
    }
    
    return suggestions;
}

async function exportCSV() {
    const data = await query(`
        SELECT 
            datetime(created_at, 'localtime') as timestamp,
            session_key,
            model,
            tokens_input,
            tokens_output,
            tokens_used,
            cost_input,
            cost_output,
            cost_total
        FROM token_usage
        ORDER BY created_at DESC
        LIMIT 10000
    `);
    
    let csv = 'Timestamp,Session,Model,Tokens In,Tokens Out,Tokens Total,Cost In,Cost Out,Cost Total\n';
    
    data.forEach(row => {
        csv += `${row.timestamp},${row.session_key},${row.model},${row.tokens_input},${row.tokens_output},${row.tokens_used},${row.cost_input},${row.cost_output},${row.cost_total}\n`;
    });
    
    return csv;
}

const server = http.createServer(async (req, res) => {
    // CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST');
    
    const parsedUrl = url.parse(req.url, true);
    const pathname = parsedUrl.pathname;
    
    try {
        if (pathname === '/') {
            // Serve dashboard
            const html = fs.readFileSync(path.join(__dirname, 'dashboard.html'), 'utf-8');
            res.writeHead(200, { 'Content-Type': 'text/html' });
            res.end(html);
            
        } else if (pathname === '/api/costs') {
            const data = await getCostSummary();
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify(data));
            
        } else if (pathname === '/api/budgets') {
            const data = await getBudgetStatus();
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify(data));
            
        } else if (pathname === '/api/sessions') {
            const data = await getSessionBreakdown();
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify(data));
            
        } else if (pathname === '/api/suggestions') {
            const data = await getOptimizationSuggestions();
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify(data));
            
        } else if (pathname === '/api/config') {
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify(config));
            
        } else if (pathname === '/export/csv') {
            const csv = await exportCSV();
            res.writeHead(200, { 
                'Content-Type': 'text/csv',
                'Content-Disposition': 'attachment; filename="token-costs.csv"'
            });
            res.end(csv);
            
        } else if (pathname === '/data') {
            // Legacy endpoint for backwards compatibility
            if (fs.existsSync(LEGACY_DATA_FILE)) {
                const legacy = JSON.parse(fs.readFileSync(LEGACY_DATA_FILE, 'utf-8'));
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ history: legacy, summary: null }));
            } else {
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ history: [], summary: null }));
            }
            
        } else {
            res.writeHead(404);
            res.end('Not found');
        }
        
    } catch (error) {
        console.error('Request error:', error.message);
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: error.message }));
    }
});

server.listen(PORT, '127.0.0.1', () => {
    console.log(`💰 Token Cost Tracker API running at http://127.0.0.1:${PORT}`);
    console.log(`📊 Dashboard: http://127.0.0.1:${PORT}/`);
    console.log(`📈 API Endpoints:`);
    console.log(`   /api/costs      - Cost summary and trends`);
    console.log(`   /api/budgets    - Budget status`);
    console.log(`   /api/sessions   - Session breakdown`);
    console.log(`   /api/suggestions - Optimization suggestions`);
    console.log(`   /export/csv     - Export data to CSV`);
});

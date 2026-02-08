#!/usr/bin/env node

/**
 * Token Usage Dashboard Server
 * Serves token usage history and dashboard on port 18794
 * NOW USING SQLITE DATABASE
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const sqlite3 = require('sqlite3').verbose();

const PORT = 18794;
const DB_FILE = path.join(__dirname, 'token-costs.db');

function getUsageData(callback) {
    const db = new sqlite3.Database(DB_FILE, sqlite3.OPEN_READONLY, (err) => {
        if (err) {
            console.error('Error opening database:', err);
            callback({ history: [], summary: null, error: err.message });
            return;
        }
        
        // Get recent history
        db.all(`
            SELECT 
                timestamp,
                input_tokens,
                output_tokens,
                total_tokens,
                cost,
                model
            FROM token_usage
            ORDER BY timestamp DESC
            LIMIT 100
        `, [], (err, rows) => {
            if (err) {
                console.error('Error querying database:', err);
                db.close();
                callback({ history: [], summary: null, error: err.message });
                return;
            }
            
            // Get summary stats
            db.get(`
                SELECT 
                    COUNT(*) as total_requests,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost) as total_cost,
                    AVG(total_tokens) as avg_tokens,
                    MAX(total_tokens) as max_tokens
                FROM token_usage
                WHERE timestamp > ?
            `, [Date.now() - (24 * 60 * 60 * 1000)], (err, summary) => {
                db.close();
                
                if (err) {
                    console.error('Error getting summary:', err);
                    callback({ history: rows.reverse(), summary: null });
                    return;
                }
                
                const latest = rows[0];
                callback({
                    history: rows.reverse(),
                    summary: {
                        current: latest,
                        totalRequests: summary.total_requests || 0,
                        totalTokens: summary.total_tokens || 0,
                        totalCost: (summary.total_cost || 0).toFixed(4),
                        avgTokens: (summary.avg_tokens || 0).toFixed(0),
                        maxTokens: summary.max_tokens || 0,
                        dataPoints: rows.length,
                        timeRange: '24 hours'
                    }
                });
            });
        });
    });
}

const server = http.createServer((req, res) => {
    // CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET');
    
    if (req.url === '/data') {
        getUsageData((data) => {
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify(data));
        });
    } else if (req.url === '/' || req.url === '/index.html') {
        const html = fs.readFileSync(path.join(__dirname, 'dashboard.html'), 'utf-8');
        res.writeHead(200, { 'Content-Type': 'text/html' });
        res.end(html);
    } else {
        res.writeHead(404);
        res.end('Not found');
    }
});

server.listen(PORT, '127.0.0.1', () => {
    console.log(`📊 Token Usage Dashboard running at http://127.0.0.1:${PORT}`);
    console.log(`✅ Using SQLite database: ${DB_FILE}`);
});

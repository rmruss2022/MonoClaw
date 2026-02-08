#!/usr/bin/env node

/**
 * Token Usage Dashboard Server
 * Serves token usage history and dashboard on port 18794
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 18794;
const DATA_FILE = path.join(__dirname, 'usage-history.json');

function getUsageData() {
    try {
        if (!fs.existsSync(DATA_FILE)) {
            return { history: [], summary: null };
        }
        
        const history = JSON.parse(fs.readFileSync(DATA_FILE, 'utf-8'));
        
        // Calculate summary stats
        const latest = history[history.length - 1];
        const oldest = history[0];
        const avgUsage = history.reduce((sum, d) => sum + d.usagePercent, 0) / history.length;
        const maxUsage = Math.max(...history.map(d => d.usagePercent));
        const trend = latest && oldest ? 
            (latest.usagePercent > oldest.usagePercent ? 'up' : 
             latest.usagePercent < oldest.usagePercent ? 'down' : 'stable') : 'unknown';
        
        return {
            history,
            summary: {
                current: latest,
                avgUsage: avgUsage.toFixed(1),
                maxUsage,
                trend,
                dataPoints: history.length,
                timeRange: `${Math.floor((Date.now() - oldest.timestamp) / (1000 * 60 * 60))} hours`
            }
        };
    } catch (error) {
        console.error('Error loading usage data:', error);
        return { history: [], summary: null, error: error.message };
    }
}

const server = http.createServer((req, res) => {
    // CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET');
    
    if (req.url === '/data') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(getUsageData()));
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
});

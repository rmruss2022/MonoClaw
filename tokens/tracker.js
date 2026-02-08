#!/usr/bin/env node

/**
 * Token Usage Tracker
 * Collects and stores token usage data from openclaw status
 */

const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
const util = require('util');
const execPromise = util.promisify(exec);

const DATA_FILE = path.join(__dirname, 'usage-history.json');

async function collectTokenData() {
    try {
        const { stdout } = await execPromise('/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw status --sessions');
        
        // Find the main session line (agent:main:main)
        const mainSessionMatch = stdout.match(/agent:main:main.*?(\d+)k\/(\d+)k\s+\((\d+)%\)/);
        
        // Count active sessions
        const sessionLines = stdout.match(/agent:main:/g);
        const activeSessions = sessionLines ? sessionLines.length : 1;
        
        // Get model from Sessions section
        const modelMatch = stdout.match(/agent:main:main.*?│\s+([^\s]+)\s+│\s+\d+k/);
        
        if (!mainSessionMatch) {
            console.error('Could not parse token usage from openclaw status');
            console.error('Looking for main session in output...');
            return;
        }
        
        const dataPoint = {
            timestamp: Date.now(),
            date: new Date().toISOString(),
            tokensUsed: `${mainSessionMatch[1]}k`,
            tokensTotal: `${mainSessionMatch[2]}k`,
            usagePercent: parseInt(mainSessionMatch[3]),
            activeSessions: activeSessions,
            model: modelMatch ? modelMatch[1] : 'claude-sonnet-4-5'
        };
        
        // Load existing history
        let history = [];
        if (fs.existsSync(DATA_FILE)) {
            history = JSON.parse(fs.readFileSync(DATA_FILE, 'utf-8'));
        }
        
        // Add new data point
        history.push(dataPoint);
        
        // Keep only last 7 days (168 hours at hourly collection)
        const sevenDaysAgo = Date.now() - (7 * 24 * 60 * 60 * 1000);
        history = history.filter(d => d.timestamp > sevenDaysAgo);
        
        // Save
        fs.writeFileSync(DATA_FILE, JSON.stringify(history, null, 2));
        console.log(`✅ Token data collected: ${dataPoint.tokensUsed}/${dataPoint.tokensTotal} (${dataPoint.usagePercent}%) - ${activeSessions} sessions`);
        
    } catch (error) {
        console.error('Error collecting token data:', error.message);
    }
}

// Run immediately
collectTokenData();

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
        
        // Parse Sessions section - find the row with highest token usage (likely the main interactive session)
        // Format: │ agent:main:cron:... │ direct │ just now │ claude-sonnet-4-5 │ 31k/200k (15%) │
        const sessionMatches = [...stdout.matchAll(/│\s+agent:main:([^\s│]+)\s+│\s+(\w+)\s+│\s+([^│]+?)\s+│\s+([^\s│]+)\s+│\s+([\d.]+)k\/([\d.]+)k\s+\((\d+)%\)/g)];
        
        if (sessionMatches.length === 0) {
            console.error('Could not parse any session data from openclaw status');
            return;
        }
        
        // Find non-cron session with highest token usage, or fallback to any session
        const nonCronSessions = sessionMatches.filter(m => !m[1].startsWith('cron:'));
        const targetSession = (nonCronSessions.length > 0 ? nonCronSessions : sessionMatches)
            .reduce((max, curr) => parseFloat(curr[5]) > parseFloat(max[5]) ? curr : max);
        
        const activeSessions = sessionMatches.length;
        
        const dataPoint = {
            timestamp: Date.now(),
            date: new Date().toISOString(),
            tokensUsed: `${targetSession[5]}k`,
            tokensTotal: `${targetSession[6]}k`,
            usagePercent: parseInt(targetSession[7]),
            activeSessions: activeSessions,
            model: targetSession[4] || 'claude-sonnet-4-5',
            sessionType: targetSession[1].startsWith('cron:') ? 'cron' : targetSession[2]
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

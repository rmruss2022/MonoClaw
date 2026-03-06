#!/usr/bin/env node

/**
 * Generate System Summary for Command Hub Agent
 * Queries all APIs and creates a cached snapshot
 * Run manually or via cron every hour
 */

const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
const util = require('util');
const execPromise = util.promisify(exec);

const SUMMARY_PATH = path.join(__dirname, 'system-summary.json');
const CACHE_TTL_MS = 60 * 60 * 1000; // 1 hour

async function fetchJSON(url, timeoutMs = 5000) {
    try {
        const response = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) });
        return await response.json();
    } catch (error) {
        console.error(`Failed to fetch ${url}:`, error.message);
        return null;
    }
}

async function checkPort(port) {
    try {
        const response = await fetch(`http://localhost:${port}`, { 
            signal: AbortSignal.timeout(2000) 
        });
        return { port, online: true, status: response.status };
    } catch {
        return { port, online: false };
    }
}

async function generateSummary() {
    console.log('🎛️ Generating system summary...');
    
    const timestamp = Date.now();
    
    // Fetch data from all APIs
    const [missionControlData, cronData, activityDbStats] = await Promise.all([
        fetchJSON('http://localhost:18795/data'),
        fetchJSON('http://localhost:18795/api/cron'),
        fetchJSON('http://localhost:18796/api/db/stats')
    ]);
    
    // Check service health
    const servicePorts = [18789, 18790, 18794, 18795, 18796, 18799, 18802, 3004, 3005];
    const serviceHealth = await Promise.all(servicePorts.map(checkPort));
    
    // Parse cron job status
    const cronSummary = {
        total: 0,
        healthy: 0,
        failed: 0,
        disabled: 0,
        recentErrors: []
    };
    
    if (cronData && cronData.jobs) {
        cronSummary.total = cronData.jobs.length;
        cronData.jobs.forEach(job => {
            if (!job.enabled) {
                cronSummary.disabled++;
            } else if (job.state?.lastStatus === 'ok') {
                cronSummary.healthy++;
            } else if (job.state?.lastStatus === 'error') {
                cronSummary.failed++;
                if (job.state.consecutiveErrors > 0) {
                    cronSummary.recentErrors.push({
                        name: job.name,
                        consecutiveErrors: job.state.consecutiveErrors,
                        lastError: job.state.lastError,
                        lastRunAtMs: job.state.lastRunAtMs
                    });
                }
            }
        });
    }
    
    // Build summary object
    const summary = {
        generatedAt: timestamp,
        generatedAtISO: new Date(timestamp).toISOString(),
        expiresAt: timestamp + CACHE_TTL_MS,
        services: {
            total: serviceHealth.length,
            online: serviceHealth.filter(s => s.online).length,
            offline: serviceHealth.filter(s => !s.online).length,
            details: serviceHealth.reduce((acc, s) => {
                const name = {
                    18789: 'Gateway',
                    18790: 'Voice Server',
                    18794: 'Token Tracker',
                    18795: 'Mission Control',
                    18796: 'Activity Hub',
                    18799: 'Vision Controller',
                    18802: 'MonoClaw',
                    3004: 'Raves',
                    3005: 'Arbitrage Scanner'
                }[s.port] || `Port ${s.port}`;
                acc[name] = s.online;
                return acc;
            }, {})
        },
        cron: cronSummary,
        activityDb: activityDbStats ? {
            sizeInMB: activityDbStats.stats?.sizeInMB || 0,
            totalRecords: activityDbStats.stats?.totalRecords || 0,
            ageInDays: activityDbStats.stats?.ageInDays || 0
        } : null,
        session: missionControlData?.session || null,
        model: missionControlData?.model?.primary || 'unknown',
        pressure: missionControlData?.pressure || null
    };
    
    // Write to file
    fs.writeFileSync(SUMMARY_PATH, JSON.stringify(summary, null, 2));
    console.log(`✅ Summary saved to ${SUMMARY_PATH}`);
    console.log(`📊 Services: ${summary.services.online}/${summary.services.total} online`);
    console.log(`⏰ Cron: ${summary.cron.healthy}/${summary.cron.total} healthy, ${summary.cron.failed} failed`);
    if (summary.activityDb) {
        console.log(`💾 Activity DB: ${summary.activityDb.sizeInMB}MB, ${summary.activityDb.totalRecords} records`);
    }
    
    return summary;
}

// Check if summary exists and is fresh
function getSummaryAge() {
    try {
        const data = JSON.parse(fs.readFileSync(SUMMARY_PATH, 'utf-8'));
        const age = Date.now() - data.generatedAt;
        return { age, expired: age > CACHE_TTL_MS, data };
    } catch {
        return { age: Infinity, expired: true, data: null };
    }
}

// Main execution
(async () => {
    const { age, expired, data } = getSummaryAge();
    
    if (process.argv.includes('--force') || expired) {
        await generateSummary();
    } else {
        const ageMin = Math.floor(age / 60000);
        console.log(`✅ Summary is fresh (${ageMin}m old). Use --force to regenerate.`);
        process.exit(0);
    }
})();

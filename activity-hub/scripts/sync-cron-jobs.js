#!/usr/bin/env node

/**
 * Sync cron jobs from OpenClaw Gateway to Activity Hub
 * Fetches jobs via gateway API and makes them available to the UI
 */

const fs = require('fs');
const path = require('path');

const GATEWAY_URL = process.env.OPENCLAW_GATEWAY_URL || 'http://localhost:18789';
const OUTPUT_FILE = path.join(__dirname, '..', 'data', 'cron-jobs.json');

async function fetchCronJobs() {
  try {
    // Read OpenClaw config to get gateway token
    const configPath = path.join(process.env.HOME, '.openclaw', 'openclaw.json');
    let token = '';
    
    try {
      const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
      token = config.gateway?.token || '';
    } catch (e) {
      console.error('Failed to read OpenClaw config:', e.message);
    }

    // Fetch cron jobs from gateway
    const response = await fetch(`${GATEWAY_URL}/api/cron/list`, {
      headers: token ? { 'Authorization': `Bearer ${token}` } : {},
    });

    if (!response.ok) {
      throw new Error(`Gateway returned ${response.status}`);
    }

    const data = await response.json();
    const jobs = data.jobs || [];

    // Transform jobs
    const transformed = jobs.map(job => ({
      jobId: job.id || job.jobId,
      name: job.name || 'Unnamed Job',
      schedule: job.schedule || { kind: 'unknown' },
      enabled: job.enabled !== false,
      lastRun: job.lastRun,
      nextRun: job.nextRun,
      status: job.enabled === false ? 'disabled' : 
              job.schedule?.kind === 'every' ? 'active' : 'scheduled',
    }));

    // Ensure data directory exists
    const dataDir = path.dirname(OUTPUT_FILE);
    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    }

    // Write to file
    fs.writeFileSync(OUTPUT_FILE, JSON.stringify({
      synced: new Date().toISOString(),
      count: transformed.length,
      jobs: transformed,
    }, null, 2));

    console.log(`✅ Synced ${transformed.length} cron jobs`);
    return transformed;
  } catch (error) {
    console.error('❌ Failed to sync cron jobs:', error.message);
    
    // Write empty data on error
    const dataDir = path.dirname(OUTPUT_FILE);
    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    }
    
    fs.writeFileSync(OUTPUT_FILE, JSON.stringify({
      synced: new Date().toISOString(),
      count: 0,
      jobs: [],
      error: error.message,
    }, null, 2));
    
    return [];
  }
}

// Run if called directly
if (require.main === module) {
  fetchCronJobs().then(() => process.exit(0));
}

module.exports = { fetchCronJobs };

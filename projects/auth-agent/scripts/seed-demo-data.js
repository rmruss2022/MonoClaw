#!/usr/bin/env node

/**
 * Convenience wrapper — runs migration then seed.
 * Usage: node scripts/seed-demo-data.js
 */

const { execSync } = require('child_process');
const path = require('path');

const root = path.resolve(__dirname, '..');

console.log('=== AuthAgent Demo Data Setup ===\n');

try {
  console.log('Step 1: Running migrations...');
  execSync('node packages/api/src/migrations/run.js', { cwd: root, stdio: 'inherit' });

  console.log('\nStep 2: Seeding demo data...');
  execSync('node packages/api/src/seeds/seed.js', { cwd: root, stdio: 'inherit' });

  console.log('\n=== Setup complete! ===');
  console.log('Start the API: npm run dev:api');
  console.log('Start the UI:  npm run dev:ui');
} catch (err) {
  console.error('Setup failed:', err.message);
  process.exit(1);
}

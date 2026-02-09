#!/usr/bin/env node
/**
 * Skill Builder - Main Entry Point
 * Discovers services and generates OpenClaw skills
 */

const { discoverServices } = require('./lib/discover');
const { generateSkill } = require('./lib/generate');
const { createReport, getRecentReports } = require('./lib/report');

const args = process.argv.slice(2);
const isTest = args.includes('--test');
const isList = args.includes('--list');
const isDryRun = args.includes('--dry-run');

async function run() {
  console.log('🔍 Skill Builder Starting...\n');
  
  try {
    // Discover services
    console.log('🔎 Discovering services...');
    const services = await discoverServices();
    console.log(`   Found ${services.length} services\n`);
    
    // Display discovered
    for (const service of services) {
      const statusIcon = service.status === 'running' ? '🟢' : '⚪';
      console.log(`   ${statusIcon} ${service.name} (${service.type})${service.port ? ` :${service.port}` : ''}`);
    }
    console.log('');
    
    // Handle list mode
    if (isList) {
      console.log('\nDiscovered services:');
      services.forEach(s => console.log(`  - ${s.name}: ${s.status}`));
      return;
    }
    
    // Generate skills
    console.log('📝 Generating skills...\n');
    const skillResults = {};
    
    for (const service of services) {
      if (isDryRun) {
        console.log(`   Would create skill for: ${service.name}`);
        skillResults[service.name] = { success: true, dryRun: true };
      } else {
        const result = await generateSkill(service);
        skillResults[service.name] = {
          success: result.skillCreated,
          errors: result.errors,
          skillPath: result.skillPath
        };
        
        if (result.skillCreated) {
          console.log(`   ✅ ${service.name}`);
        } else {
          console.log(`   ⚠️  ${service.name} (errors: ${result.errors.length})`);
        }
      }
    }
    
    // Create report
    console.log('\n📊 Creating report...');
    const { report, reportPath } = await createReport(services, skillResults);
    
    const successCount = Object.values(skillResults).filter(r => r.success).length;
    console.log(`   Report saved: ${reportPath}`);
    console.log(`\n✅ Complete: ${successCount}/${services.length} skills created`);
    
    // Test mode output
    if (isTest) {
      console.log('\n--- TEST SUMMARY ---');
      console.log(`Services discovered: ${report.summary.totalDiscovered}`);
      console.log(`Running: ${report.summary.running}`);
      console.log(`Stopped: ${report.summary.stopped}`);
      console.log(`Skills created: ${report.summary.skillsCreated}`);
      console.log(`Errors: ${report.errors.length}`);
    }
    
    return report;
    
  } catch (error) {
    console.error('\n❌ Error:', error.message);
    process.exit(1);
  }
}

// Run if executed directly
if (require.main === module) {
  run().then(() => {
    process.exit(0);
  }).catch(err => {
    console.error('Fatal error:', err);
    process.exit(1);
  });
}

module.exports = { run };

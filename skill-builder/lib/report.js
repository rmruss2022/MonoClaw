/**
 * Report Module
 * Creates JSON reports of discovery runs
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const REPORTS_DIR = process.env.REPORTS_DIR || path.join(process.env.HOME, '.openclaw/workspace/skill-builder/reports');

async function createReport(discoveredServices, skillResults) {
  const runId = generateRunId();
  const timestamp = new Date().toISOString();
  
  const report = {
    timestamp,
    runId,
    discovered: discoveredServices.map(s => ({
      name: s.name,
      type: s.type,
      port: s.port,
      status: s.status,
      skillCreated: skillResults[s.name]?.success || false,
      skillPath: skillResults[s.name]?.skillPath || null,
      errors: skillResults[s.name]?.errors || []
    })),
    summary: {
      totalDiscovered: discoveredServices.length,
      running: discoveredServices.filter(s => s.status === 'running').length,
      stopped: discoveredServices.filter(s => s.status === 'stopped').length,
      skillsCreated: Object.values(skillResults).filter(r => r.success).length,
      skillsFailed: Object.values(skillResults).filter(r => !r.success && r.errors.length > 0).length
    },
    errors: collectErrors(skillResults)
  };
  
  // Save report
  const reportPath = path.join(REPORTS_DIR, `${runId}.json`);
  if (!fs.existsSync(REPORTS_DIR)) {
    fs.mkdirSync(REPORTS_DIR, { recursive: true });
  }
  
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  
  // Also save as latest.json
  const latestPath = path.join(REPORTS_DIR, 'latest.json');
  fs.writeFileSync(latestPath, JSON.stringify(report, null, 2));
  
  return { report, reportPath };
}

function generateRunId() {
  const date = new Date();
  const dateStr = date.toISOString().split('T')[0];
  const hash = crypto.randomBytes(4).toString('hex');
  return `${dateStr}-${hash}`;
}

function collectErrors(skillResults) {
  const errors = [];
  for (const [name, result] of Object.entries(skillResults)) {
    if (result.errors && result.errors.length > 0) {
      errors.push({
        service: name,
        errors: result.errors
      });
    }
  }
  return errors;
}

function getRecentReports(limit = 10) {
  if (!fs.existsSync(REPORTS_DIR)) {
    return [];
  }
  
  const files = fs.readdirSync(REPORTS_DIR)
    .filter(f => f.endsWith('.json') && f !== 'latest.json')
    .map(f => ({
      name: f,
      path: path.join(REPORTS_DIR, f),
      time: fs.statSync(path.join(REPORTS_DIR, f)).mtime
    }))
    .sort((a, b) => b.time - a.time)
    .slice(0, limit)
    .map(f => {
      try {
        const content = JSON.parse(fs.readFileSync(f.path, 'utf8'));
        return {
          runId: content.runId,
          timestamp: content.timestamp,
          totalDiscovered: content.summary.totalDiscovered,
          skillsCreated: content.summary.skillsCreated
        };
      } catch (e) {
        return null;
      }
    })
    .filter(Boolean);
  
  return files;
}

module.exports = {
  createReport,
  getRecentReports
};

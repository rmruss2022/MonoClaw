/**
 * Skill Generator Module
 * Generates SKILL.md and README.md files for discovered services
 */

const fs = require('fs');
const path = require('path');

const SKILLS_DIR = process.env.SKILLS_DIR || path.join(process.env.HOME, '.openclaw/workspace/skills');

async function generateSkill(service) {
  const skillDir = path.join(SKILLS_DIR, service.name);
  
  // Create skill directory
  if (!fs.existsSync(skillDir)) {
    fs.mkdirSync(skillDir, { recursive: true });
  }
  
  const results = {
    skillCreated: false,
    readmeCreated: false,
    errors: []
  };
  
  // Generate SKILL.md
  try {
    const skillContent = generateSkillMarkdown(service);
    const skillPath = path.join(skillDir, 'SKILL.md');
    fs.writeFileSync(skillPath, skillContent);
    results.skillCreated = true;
    results.skillPath = skillPath;
  } catch (e) {
    results.errors.push(`Failed to create SKILL.md: ${e.message}`);
  }
  
  // Generate README.md
  try {
    const readmeContent = generateReadmeMarkdown(service);
    const readmePath = path.join(skillDir, 'README.md');
    fs.writeFileSync(readmePath, readmeContent);
    results.readmeCreated = true;
    results.readmePath = readmePath;
  } catch (e) {
    results.errors.push(`Failed to create README.md: ${e.message}`);
  }
  
  // Try to copy existing skill if available
  if (service.path) {
    const existingSkillPath = path.join(service.path, 'SKILL.md');
    if (fs.existsSync(existingSkillPath)) {
      try {
        const existing = fs.readFileSync(existingSkillPath, 'utf8');
        fs.writeFileSync(path.join(skillDir, 'SKILL.md'), existing);
        results.copiedFromSource = true;
      } catch (e) {
        // Ignore copy errors
      }
    }
  }
  
  return results;
}

function generateSkillMarkdown(service) {
  const lines = [];
  
  lines.push(`# ${formatName(service.name)}`);
  lines.push('');
  lines.push(`Type: ${service.type}`);
  lines.push(`Status: ${service.status}`);
  if (service.port) lines.push(`Port: ${service.port}`);
  lines.push('');
  lines.push('## Overview');
  lines.push('');
  lines.push(getOverview(service));
  lines.push('');
  lines.push('## Usage');
  lines.push('');
  lines.push(getUsage(service));
  lines.push('');
  
  if (service.dependencies?.length > 0) {
    lines.push('## Dependencies');
    lines.push('');
    lines.push(service.dependencies.slice(0, 10).map(d => `- ${d}`).join('\n'));
    lines.push('');
  }
  
  lines.push('## Service Info');
  lines.push('');
  lines.push(`- **Name:** ${service.name}`);
  lines.push(`- **Type:** ${service.type}`);
  lines.push(`- **Status:** ${service.status}`);
  if (service.port) lines.push(`- **Port:** ${service.port}`);
  if (service.path) lines.push(`- **Path:** ${service.path}`);
  lines.push(`- **Discovered:** ${service.discoveredAt}`);
  lines.push('');
  
  return lines.join('\n');
}

function generateReadmeMarkdown(service) {
  const lines = [];
  
  lines.push(`# ${formatName(service.name)}`);
  lines.push('');
  lines.push(getOverview(service));
  lines.push('');
  lines.push('## Quick Start');
  lines.push('');
  lines.push(getQuickStart(service));
  lines.push('');
  
  if (service.hasReadme && service.path) {
    lines.push('## Documentation');
    lines.push('');
    lines.push(`See full documentation at: ${service.path}/README.md`);
    lines.push('');
  }
  
  return lines.join('\n');
}

function formatName(name) {
  return name
    .split(/[-_]/)
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

function getOverview(service) {
  const overviews = {
    'voice-server': 'Text-to-speech service for macOS system announcements. Provides HTTP API for speaking text through system speakers.',
    'activity-hub': 'Central dashboard for monitoring OpenClaw activity and system health. Provides real-time status of services and agents.',
    'job-dashboard': 'Job tracking and management interface for OpenClaw tasks and missions.',
    'jobs': 'Background job processing and tracking system for OpenClaw operations.',
    'docker-agent-system': 'Docker container management and orchestration for OpenClaw agents.',
    'vm-agent-system': 'Virtual machine management and provisioning for OpenClaw agents.',
    'raves': 'Music event discovery and tracking application.',
    'matts-claw-blog': 'Personal blog system powered by OpenClaw.',
    'token-collector': 'Background service for collecting cryptocurrency tokens.',
    'token-tracker': 'Background service for tracking token prices and balances.'
  };
  
  return overviews[service.name] || `A ${service.type} service discovered in the OpenClaw workspace.`;
}

function getUsage(service) {
  const usages = {
    'voice-server': '```bash\n# Speak text\ncurl -X POST http://127.0.0.1:18790/speak \\\n  -H "Content-Type: application/json" \\\n  -d \'{"text": "Hello world"}\'\n```',
    'activity-hub': '```bash\n# Access dashboard\nopen http://127.0.0.1:18796\n```',
    'job-dashboard': '```bash\n# Access dashboard\nopen http://127.0.0.1:18791\n```',
    'jobs': '```bash\n# List jobs\ncurl http://127.0.0.1:18791/api/jobs\n```',
    'raves': '```bash\n# Access app\nopen http://127.0.0.1:18800\n```'
  };
  
  return usages[service.name] || `Access at: ${service.port ? `http://127.0.0.1:${service.port}` : 'N/A (no port configured)'}`;
}

function getQuickStart(service) {
  const quickstarts = {
    'voice-server': '1. Ensure service is running: `launchctl start com.openclaw.voice-server`\n2. POST to http://127.0.0.1:18790/speak with JSON body\n3. Text will be spoken through system speakers',
    'activity-hub': '1. Open http://127.0.0.1:18796 in browser\n2. View real-time service status\n3. Check agent health and activity',
    'job-dashboard': '1. Open http://127.0.0.1:18791 in browser\n2. View active and completed jobs\n3. Monitor job progress and logs'
  };
  
  if (quickstarts[service.name]) return quickstarts[service.name];
  
  if (service.scripts?.includes('start')) {
    return `1. Navigate to service directory\n2. Run \`npm start\` or \`pnpm start\`\n3. Service will start on configured port`;
  }
  
  if (service.port) {
    return `1. Start the service (see package.json scripts)\n2. Access at http://127.0.0.1:${service.port}`;
  }
  
  return '1. Navigate to service directory\n2. Check package.json for available scripts\n3. Run appropriate start command';
}

module.exports = {
  generateSkill,
  generateSkillMarkdown,
  generateReadmeMarkdown
};

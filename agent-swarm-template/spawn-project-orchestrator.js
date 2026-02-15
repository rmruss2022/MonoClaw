#!/usr/bin/env node

/**
 * Spawn a per-project orchestrator agent
 * 
 * Usage: node spawn-project-orchestrator.js <project-id>
 */

const Database = require('better-sqlite3');
const fs = require('fs');
const path = require('path');

const projectId = parseInt(process.argv[2]);
if (!projectId) {
  console.error('❌ Usage: node spawn-project-orchestrator.js <project-id>');
  process.exit(1);
}

const db = new Database('swarm.db');

// Get project details
const project = db.prepare('SELECT * FROM projects WHERE id = ?').get(projectId);
if (!project) {
  console.error(`❌ Project ${projectId} not found`);
  process.exit(1);
}

console.log(`\n🎯 Spawning orchestrator for: ${project.name}`);

// Get project configuration
const configRow = db.prepare('SELECT configuration_json FROM projects WHERE id = ?').get(projectId);
let config = {};
try {
  config = JSON.parse(configRow.configuration_json || '{}');
} catch (e) {
  console.warn('⚠️  No valid configuration_json found, using defaults');
}

// Load orchestrator template
const templatePath = path.join(__dirname, 'orchestrator-template.md');
let template = fs.readFileSync(templatePath, 'utf-8');

// Get tasks for dependency graph
const tasks = db.prepare(`
  SELECT id, title, state, dependencies_json, estimated_hours, priority
  FROM tasks
  WHERE project_id = ?
  ORDER BY id
`).all(projectId);

// Build dependency graph
let dependencyGraph = '```\n';
tasks.forEach(task => {
  const deps = JSON.parse(task.dependencies_json || '[]');
  if (deps.length > 0) {
    dependencyGraph += `${task.id}: depends on [${deps.join(', ')}]\n`;
  } else {
    dependencyGraph += `${task.id}: no dependencies (Wave 1)\n`;
  }
});
dependencyGraph += '```\n';

// Build tech stack display
let techStack = '';
if (config.techStack) {
  techStack = Object.entries(config.techStack).map(([key, value]) => 
    `- **${key}:** ${value}`
  ).join('\n');
}

// Build agent specializations display
let agentSpecs = '';
if (config.agentSpecializations) {
  agentSpecs = config.agentSpecializations.map(spec => 
    `- **${spec.role}:** ${spec.skills.join(', ')}`
  ).join('\n');
}

// Template substitution
const dbPath = path.join(__dirname, 'swarm.db');
const outputPath = project.reference || '/path/to/output';
const specsPath = path.join(__dirname, 'projects', project.name.toLowerCase().replace(/\s+/g, '-'), 'specs');

template = template
  .replace(/\{\{PROJECT_NAME\}\}/g, project.name)
  .replace(/\{\{PROJECT_ID\}\}/g, projectId)
  .replace(/\{\{DATABASE_PATH\}\}/g, dbPath)
  .replace(/\{\{OUTPUT_PATH\}\}/g, outputPath)
  .replace(/\{\{SPECS_PATH\}\}/g, specsPath)
  .replace(/\{\{TECH_STACK\}\}/g, techStack)
  .replace(/\{\{AGENT_SPECIALIZATIONS\}\}/g, agentSpecs)
  .replace(/\{\{DEPENDENCY_GRAPH\}\}/g, dependencyGraph);

// Write instantiated template
const instancePath = path.join(__dirname, `orchestrator-${project.id}.md`);
fs.writeFileSync(instancePath, template);
console.log(`📝 Orchestrator prompt saved: ${instancePath}`);

// Build the spawn command (to be executed via OpenClaw sessions_spawn)
const spawnInstructions = `
To spawn this orchestrator, use the OpenClaw sessions_spawn tool:

\`\`\`typescript
sessions_spawn({
  task: fs.readFileSync('${instancePath}', 'utf-8'),
  label: 'orchestrator-project-${projectId}',
  model: 'kimi-k2.5',
  runTimeoutSeconds: 14400,  // 4 hours
  cleanup: 'keep'
});
\`\`\`

Or use the OpenClaw main agent:

"Spawn an orchestrator agent for project ${projectId}. Read ${instancePath} and spawn it as a long-running coordinator with a 4-hour timeout. Label it 'orchestrator-project-${projectId}'."
`;

console.log(spawnInstructions);

// Register orchestrator intention in database
db.prepare(`
  INSERT INTO activity_log (project_id, timestamp, agent_id, message, event_type)
  VALUES (?, datetime('now'), 'system', ?, 'info')
`).run(projectId, `Orchestrator template prepared: ${instancePath}`);

console.log(`\n✅ Ready to spawn orchestrator for "${project.name}"\n`);

db.close();

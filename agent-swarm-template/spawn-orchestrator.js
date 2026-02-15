#!/usr/bin/env node

/**
 * Spawn Orchestrator - Creates a persistent sub-agent orchestrator with full context
 * 
 * Usage: node spawn-orchestrator.js <project_id>
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const DB_PATH = '/Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db';
const TEMPLATE_PATH = '/Users/matthew/.openclaw/workspace/agent-swarm-template/orchestrator-prompt-template.md';
const OPENCLAW_BIN = '/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw';

// Get project ID from command line
const PROJECT_ID = parseInt(process.argv[2]);
if (!PROJECT_ID) {
  console.error('Usage: node spawn-orchestrator.js <project_id>');
  process.exit(1);
}

// Helper: Execute SQL query
function query(sql) {
  try {
    const result = execSync(`sqlite3 "${DB_PATH}" "${sql}"`, { encoding: 'utf-8' });
    return result.trim();
  } catch (e) {
    console.error('SQL Error:', e.message);
    throw e;
  }
}

// Load project from database
function loadProject(projectId) {
  const result = query(`SELECT id, name, description, reference, configuration_json FROM projects WHERE id = ${projectId};`);
  if (!result) {
    throw new Error(`Project ${projectId} not found`);
  }
  
  const [id, name, description, reference, configJson] = result.split('|');
  const config = JSON.parse(configJson || '{}');
  
  return {
    id: parseInt(id),
    name,
    description,
    reference,
    config
  };
}

// Build orchestrator prompt with full context
function buildOrchestratorPrompt(project) {
  const template = fs.readFileSync(TEMPLATE_PATH, 'utf-8');
  const config = project.config;
  
  // Extract context
  const techStack = JSON.stringify(config.tech_stack || {}, null, 2);
  const filePaths = JSON.stringify(config.file_paths || {}, null, 2);
  const agentRequirements = JSON.stringify(config.agent_requirements || {}, null, 2);
  const referenceMaterials = JSON.stringify(config.reference_materials || [], null, 2);
  const maxActiveAgents = config.max_active_agents || 3;
  const orchestratorDocsPath = config.orchestrator_docs_path || 
    `/Users/matthew/.openclaw/workspace/agent-swarm-template/projects/${project.name.toLowerCase().replace(/\s+/g, '-')}`;
  
  // Replace template variables
  let prompt = template
    .replace(/\{\{PROJECT_NAME\}\}/g, project.name)
    .replace(/\{\{PROJECT_ID\}\}/g, project.id)
    .replace(/\{\{MAX_ACTIVE_AGENTS\}\}/g, maxActiveAgents)
    .replace(/\{\{DB_PATH\}\}/g, DB_PATH)
    .replace(/\{\{TECH_STACK_JSON\}\}/g, techStack)
    .replace(/\{\{FILE_PATHS_JSON\}\}/g, filePaths)
    .replace(/\{\{AGENT_REQUIREMENTS_JSON\}\}/g, agentRequirements)
    .replace(/\{\{REFERENCE_MATERIALS_JSON\}\}/g, referenceMaterials)
    .replace(/\{\{ORCHESTRATOR_DOCS_PATH\}\}/g, orchestratorDocsPath)
    .replace(/\{\{PROJECT_ROOT\}\}/g, project.reference || '');
  
  return prompt;
}

// Main
async function main() {
  console.log('🦞 Spawning Orchestrator for Project', PROJECT_ID);
  console.log('─'.repeat(60));
  
  // 1. Load project
  const project = loadProject(PROJECT_ID);
  console.log(`✅ Loaded project: ${project.name}`);
  
  // 2. Build full prompt with context
  const prompt = buildOrchestratorPrompt(project);
  console.log(`✅ Built orchestrator prompt (${prompt.length} chars)`);
  
  // 3. Write prompt to temp file for inspection
  const promptFile = `/tmp/orchestrator-prompt-project-${PROJECT_ID}.txt`;
  fs.writeFileSync(promptFile, prompt);
  console.log(`✅ Prompt saved to: ${promptFile}`);
  
  // 4. Spawn orchestrator as persistent sub-agent
  const agentId = `orchestrator-${project.name.toLowerCase().replace(/\s+/g, '-')}`;
  const label = `${project.name} Orchestrator`;
  
  console.log('\n🚀 Spawning orchestrator sub-agent...');
  console.log(`   Agent ID: ${agentId}`);
  console.log(`   Label: ${label}`);
  console.log(`   Model: nvidia/moonshotai/kimi-k2.5`);
  console.log(`   Timeout: 4 hours (14400 seconds)`);
  
  // Use sessions_spawn via CLI (since we're running this from a script, not from within an agent)
  // Note: If running this FROM an agent, you'd use the sessions_spawn tool directly
  const spawnCmd = `${OPENCLAW_BIN} sessions spawn --agentId "${agentId}" --label "${label}" --model "nvidia/moonshotai/kimi-k2.5" --task "$(cat ${promptFile})" --runTimeoutSeconds 14400 --cleanup keep`;
  
  try {
    console.log('\n📤 Executing spawn command...');
    const output = execSync(spawnCmd, { 
      encoding: 'utf-8',
      maxBuffer: 50 * 1024 * 1024,
      stdio: ['pipe', 'pipe', 'pipe']
    });
    
    console.log('\n✅ Orchestrator spawned successfully!');
    console.log(output);
    
    // 5. Log to database
    const timestamp = new Date().toISOString().replace('T', ' ').split('.')[0];
    query(`INSERT INTO activity_log (project_id, timestamp, agent_id, event_type, message) VALUES (${PROJECT_ID}, '${timestamp}', '${agentId}', 'orchestrator_start', 'Orchestrator spawned for 4-hour run');`);
    
    console.log('\n📊 Monitor orchestrator:');
    console.log(`   Dashboard: http://localhost:5173`);
    console.log(`   Sessions: openclaw sessions list --kinds isolated`);
    console.log(`   Logs: openclaw sessions history --sessionKey ${agentId}`);
    
  } catch (e) {
    console.error('\n❌ Failed to spawn orchestrator:', e.message);
    if (e.stderr) {
      console.error('stderr:', e.stderr);
    }
    process.exit(1);
  }
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});

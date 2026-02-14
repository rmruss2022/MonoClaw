#!/usr/bin/env node

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const DB_PATH = '/Users/matthew/.openclaw/workspace/agent-swarm-template/swarm.db';
const STATE_FILE = '/Users/matthew/.openclaw/workspace/agent-swarm-template/orchestrator-state.json';
const PROJECT_ID = 3;
const MAX_ACTIVE_AGENTS = 8;
const CHECK_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes
const TOKEN_RESTART_THRESHOLD = 150000;
const MODEL = 'nvidia/moonshotai/kimi-k2.5';

// Helper: Execute SQL query
function query(sql) {
  const result = execSync(`sqlite3 "${DB_PATH}" "${sql}"`, { encoding: 'utf-8' });
  return result.trim();
}

// Helper: Parse SQL result rows
function parseRows(result) {
  if (!result) return [];
  return result.split('\n').map(row => {
    const cols = row.split('|');
    return cols;
  });
}

// Load orchestrator state
function loadState() {
  try {
    if (fs.existsSync(STATE_FILE)) {
      return JSON.parse(fs.readFileSync(STATE_FILE, 'utf-8'));
    }
  } catch (e) {
    console.error('Failed to load state:', e.message);
  }
  return {
    lastCheck: null,
    activeAgents: [],
    completedSinceRestart: 0,
    tokenUsage: 0
  };
}

// Save orchestrator state
function saveState(state) {
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

// Log activity to database
function logActivity(taskId, agentId, eventType, message) {
  const timestamp = new Date().toISOString();
  const sql = `INSERT INTO activity_log (project_id, timestamp, agent_id, task_id, event_type, message) VALUES (${PROJECT_ID}, '${timestamp}', '${agentId}', '${taskId}', '${eventType}', '${message.replace(/'/g, "''")}');`;
  try {
    query(sql);
  } catch (e) {
    console.error('Failed to log activity:', e.message);
  }
}

// Get completed agents
function getCompletedAgents() {
  const sql = `SELECT agent_id, task_id, result, completed_at FROM agents WHERE project_id = ${PROJECT_ID} AND status = 'completed' ORDER BY completed_at DESC LIMIT 20;`;
  const result = query(sql);
  return parseRows(result);
}

// Get ready tasks
function getReadyTasks(limit = 10) {
  const sql = `SELECT id, title, estimated_hours, priority FROM tasks WHERE project_id = ${PROJECT_ID} AND state = 'todo' AND (dependencies_json IS NULL OR dependencies_json = '[]') ORDER BY CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END, estimated_hours ASC LIMIT ${limit};`;
  const result = query(sql);
  return parseRows(result);
}

// Count active agents
function getActiveAgentCount() {
  const sql = `SELECT COUNT(*) FROM agents WHERE project_id = ${PROJECT_ID} AND status = 'running';`;
  return parseInt(query(sql)) || 0;
}

// Process completed agent
function processCompletedAgent(agentId, taskId, result, completedAt) {
  console.log(`✅ Processing completed agent: ${agentId} (task ${taskId})`);
  
  // Update task state
  const taskSql = `UPDATE tasks SET state = 'done', completed_at = '${completedAt}' WHERE id = '${taskId}' AND project_id = ${PROJECT_ID};`;
  query(taskSql);
  
  // Mark agent as processed
  const agentSql = `UPDATE agents SET status = 'processed' WHERE agent_id = '${agentId}' AND project_id = ${PROJECT_ID};`;
  query(agentSql);
  
  // Log activity
  logActivity(taskId, agentId, 'completed', result || 'Task completed');
  
  console.log(`   Result: ${(result || 'No summary').substring(0, 100)}...`);
}

// Spawn agent for task
function spawnAgent(taskId, title) {
  const agentId = `agent-${taskId}`;
  const timestamp = new Date().toISOString().replace('T', ' ').split('.')[0];
  
  console.log(`🚀 Spawning agent: ${agentId} for task ${taskId}`);
  
  // Register agent in database
  const registerSql = `INSERT INTO agents (project_id, agent_id, task_id, spawned_at, status, model) VALUES (${PROJECT_ID}, '${agentId}', '${taskId}', '${timestamp}', 'running', '${MODEL}');`;
  query(registerSql);
  
  // Update task state
  const taskSql = `UPDATE tasks SET state = 'in_progress', assigned_to = '${agentId}', started_at = '${timestamp}' WHERE id = '${taskId}' AND project_id = ${PROJECT_ID};`;
  query(taskSql);
  
  // Build agent prompt (minimal, no large file reads)
  const prompt = `Execute task ${taskId}: ${title}

Project root: /Users/matthew/Desktop/Feb26/ora-ai/

Steps:
1. Check for spec file: /Users/matthew/.openclaw/workspace/agent-swarm-template/projects/ora-ai/specs/${taskId}-spec.md
2. If spec exists, read and follow it. Otherwise use task description.
3. Complete the work, write files to project root
4. Update database with summary:

sqlite3 ${DB_PATH} "UPDATE tasks SET state='done', completed_at=datetime('now') WHERE id='${taskId}';"
sqlite3 ${DB_PATH} "UPDATE agents SET status='completed', completed_at=datetime('now'), result='SUMMARY: [what you built, file locations]' WHERE agent_id='${agentId}';"

Keep result summary under 500 characters.`;
  
  // Write prompt to temp file
  const promptFile = `/tmp/agent-prompt-${agentId}.txt`;
  fs.writeFileSync(promptFile, prompt);
  
  // Spawn agent via openclaw sessions send (background)
  const spawnCmd = `nohup /Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw sessions send --sessionKey "agent:swarm:${agentId}" --message "$(cat ${promptFile})" --timeoutSeconds 3600 > /tmp/${agentId}.log 2>&1 &`;
  
  try {
    execSync(spawnCmd, { shell: '/bin/bash' });
    logActivity(taskId, agentId, 'spawned', `Agent spawned for task ${taskId}`);
    console.log(`   Spawned successfully`);
    return true;
  } catch (e) {
    console.error(`   Failed to spawn: ${e.message}`);
    // Mark as failed
    query(`UPDATE agents SET status = 'failed', completed_at = datetime('now'), result = 'Spawn failed' WHERE agent_id = '${agentId}';`);
    query(`UPDATE tasks SET state = 'todo', assigned_to = NULL WHERE id = '${taskId}';`);
    return false;
  }
}

// Main orchestration loop
async function orchestrate() {
  const state = loadState();
  
  console.log('\n🦞 Orchestrator Check', new Date().toLocaleTimeString());
  console.log('─'.repeat(60));
  
  // Step 1: Process completed agents
  const completed = getCompletedAgents();
  for (const [agentId, taskId, result, completedAt] of completed) {
    processCompletedAgent(agentId, taskId, result, completedAt);
    state.completedSinceRestart++;
  }
  
  // Step 2: Check active agents
  const activeCount = getActiveAgentCount();
  console.log(`📊 Active agents: ${activeCount}/${MAX_ACTIVE_AGENTS}`);
  
  // Step 3: Spawn new agents if under limit
  if (activeCount < MAX_ACTIVE_AGENTS) {
    const readyTasks = getReadyTasks(MAX_ACTIVE_AGENTS - activeCount);
    console.log(`📋 Ready tasks: ${readyTasks.length}`);
    
    for (const [taskId, title, estimatedHours, priority] of readyTasks) {
      if (getActiveAgentCount() >= MAX_ACTIVE_AGENTS) break;
      spawnAgent(taskId, title);
    }
  }
  
  // Step 4: Update state
  state.lastCheck = new Date().toISOString();
  state.activeAgents = query(`SELECT agent_id FROM agents WHERE project_id = ${PROJECT_ID} AND status = 'running';`).split('\n').filter(Boolean);
  saveState(state);
  
  console.log(`✨ Completed since restart: ${state.completedSinceRestart}`);
  console.log('─'.repeat(60));
  
  // Step 5: Schedule next check
  setTimeout(orchestrate, CHECK_INTERVAL_MS);
}

// Start orchestrator
console.log('🚀 Starting Ora AI Orchestrator');
console.log(`   Project ID: ${PROJECT_ID}`);
console.log(`   Max agents: ${MAX_ACTIVE_AGENTS}`);
console.log(`   Check interval: ${CHECK_INTERVAL_MS / 1000}s`);
console.log(`   Model: ${MODEL}`);
console.log('');

orchestrate().catch(err => {
  console.error('❌ Orchestrator error:', err);
  process.exit(1);
});

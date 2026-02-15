#!/usr/bin/env node

const { exec } = require('child_process');
const path = require('path');

const DB_PATH = path.join(__dirname, 'swarm.db');
const CHECK_INTERVAL = 5 * 60 * 1000; // 5 minutes  
const MAX_CONCURRENT = 3;

let activeAgents = new Set();

function log(msg) {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] ${msg}`);
}

function query(sql) {
  return new Promise((resolve, reject) => {
    const cmd = `sqlite3 "${DB_PATH}" "${sql.replace(/"/g, '\\"')}"`;
    exec(cmd, (error, stdout, stderr) => {
      if (error) {
        reject(new Error(`SQL error: ${stderr || error.message}`));
      } else {
        resolve(stdout.trim());
      }
    });
  });
}

async function getDependencies(taskId) {
  const result = await query(`SELECT dependencies_json FROM tasks WHERE id = '${taskId}'`);
  if (!result) return [];
  try {
    return JSON.parse(result);
  } catch {
    return [];
  }
}

async function getTasks(projectId, state) {
  const result = await query(`SELECT id, title, state, dependencies_json FROM tasks WHERE project_id = ${projectId} AND state = '${state}' ORDER BY id ASC`);
  if (!result) return [];
  
  return result.split('\n').filter(l => l).map(line => {
    const [id, title, state, deps_json] = line.split('|');
    let dependencies = [];
    try {
      dependencies = deps_json ? JSON.parse(deps_json) : [];
    } catch {}
    return { id, title, state, dependencies };
  });
}

async function areDepsSatisfied(dependencies, projectId) {
  if (!dependencies || dependencies.length === 0) return true;
  
  for (const depId of dependencies) {
    const result = await query(`SELECT state FROM tasks WHERE id = '${depId}' AND project_id = ${projectId}`);
    if (result !== 'done') return false;
  }
  return true;
}

async function markReady(taskId) {
  await query(`UPDATE tasks SET state = 'ready' WHERE id = '${taskId}'`);
  log(`✓ Marked ${taskId} as ready`);
}

async function spawnAgent(taskId, projectId) {
  const agentKey = `agent-${taskId}`;
  activeAgents.add(agentKey);
  
  log(`Spawning agent for ${taskId}...`);
  
  // Read the spec file for context
  const specFile = `~/.openclaw/workspace/agent-swarm-template/tasks/${taskId}.md`;
  
  const cmd = `/Users/matthew/.nvm/versions/node/v22.22.0/bin/openclaw sessions spawn ` +
    `--label "Worker ${taskId}" ` +
    `--task "You are working on the Vision Controller project (ID ${projectId}). Your task: ${taskId}. Read ${specFile} for full specifications. Update swarm.db when complete: UPDATE tasks SET state='done', completed_at=datetime('now'), assigned_to='${agentKey}' WHERE id='${taskId}';" ` +
    `--model nvidia/moonshotai/kimi-k2.5 ` +
    `--timeoutSeconds 3600`;
  
  return new Promise((resolve, reject) => {
    exec(cmd, (error, stdout, stderr) => {
      activeAgents.delete(agentKey);
      
      if (error) {
        log(`✗ Error spawning ${taskId}: ${error.message}`);
        reject(error);
      } else {
        log(`✓ Spawned ${taskId}`);
        // Mark as in-progress
        query(`UPDATE tasks SET state = 'in-progress', started_at = datetime('now'), assigned_to = '${agentKey}' WHERE id = '${taskId}'`).catch(err => {
          log(`Warning: Could not update task state: ${err.message}`);
        });
        resolve(stdout);
      }
    });
  });
}

async function checkAndSpawn(projectId) {
  try {
    // Step 1: Find todo tasks with satisfied dependencies → mark as ready
    const todoTasks = await getTasks(projectId, 'todo');
    for (const task of todoTasks) {
      const depsSatisfied = await areDepsSatisfied(task.dependencies, projectId);
      if (depsSatisfied) {
        await markReady(task.id);
      }
    }
    
    // Step 2: Find ready tasks and spawn agents
    const readyTasks = await getTasks(projectId, 'ready');
    const availableSlots = MAX_CONCURRENT - activeAgents.size;
    
    log(`Check: ${readyTasks.length} ready, ${activeAgents.size}/${MAX_CONCURRENT} active`);
    
    if (availableSlots > 0 && readyTasks.length > 0) {
      const tasksToSpawn = readyTasks.slice(0, availableSlots);
      
      for (const task of tasksToSpawn) {
        try {
          await spawnAgent(task.id, projectId);
        } catch (err) {
          log(`Failed to spawn ${task.id}: ${err.message}`);
        }
      }
    }
  } catch (err) {
    log(`Error in check cycle: ${err.message}`);
  }
}

async function main() {
  const projectId = parseInt(process.argv[2] || '4');
  
  log(`🦞 Orchestrator daemon starting for project ${projectId}`);
  log(`Check interval: ${CHECK_INTERVAL / 1000}s, Max concurrent: ${MAX_CONCURRENT}`);
  log(`Database: ${DB_PATH}`);
  
  // Initial check
  await checkAndSpawn(projectId);
  
  // Periodic checks
  setInterval(() => checkAndSpawn(projectId), CHECK_INTERVAL);
  
  log(`Orchestrator running. Press Ctrl+C to stop.`);
}

main().catch(err => {
  log(`Fatal error: ${err.message}`);
  process.exit(1);
});

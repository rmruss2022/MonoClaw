const Database = require('better-sqlite3');
const fs = require('fs');
const path = require('path');

console.log('🔄 Starting migration...\n');

// Open database
const db = new Database('database.db');
db.pragma('journal_mode = WAL');

// Create tables if they don't exist
console.log('🔧 Ensuring database schema exists...');
db.exec(`
  CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    reference TEXT,
    status TEXT DEFAULT 'not-started',
    created_at TEXT NOT NULL,
    target_completion TEXT
  )
`);

db.exec(`
  CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    state TEXT DEFAULT 'todo',
    priority TEXT DEFAULT 'medium',
    estimated_hours REAL DEFAULT 0,
    actual_hours REAL DEFAULT 0,
    assigned_to TEXT,
    agent_session_key TEXT,
    started_at TEXT,
    completed_at TEXT,
    spec_file TEXT,
    dependencies_json TEXT,
    tags_json TEXT,
    code_files_json TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id)
  )
`);

db.exec(`
  CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    agent_id TEXT NOT NULL,
    session_key TEXT,
    task_id TEXT,
    spawned_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT DEFAULT 'running',
    result TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (task_id) REFERENCES tasks(id)
  )
`);

db.exec(`
  CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    agent TEXT NOT NULL,
    task_id TEXT,
    message TEXT NOT NULL,
    type TEXT DEFAULT 'info',
    FOREIGN KEY (project_id) REFERENCES projects(id)
  )
`);
console.log('✅ Database schema ready\n');

// Load kanban.json
const kanbanFile = process.argv[2] || 'kanban-demo.json';
const kanbanPath = path.join(__dirname, kanbanFile);

if (!fs.existsSync(kanbanPath)) {
  console.error(`❌ Error: ${kanbanFile} not found`);
  console.log(`Usage: node migrate.js [kanban-file.json]`);
  console.log(`Example: node migrate.js kanban-demo.json`);
  process.exit(1);
}

console.log(`📂 Loading ${kanbanFile}...`);
const data = JSON.parse(fs.readFileSync(kanbanPath, 'utf8'));

// Start transaction
const migrate = db.transaction(() => {
  // Insert project
  console.log('📊 Inserting project...');
  const projectStmt = db.prepare(`
    INSERT INTO projects (name, description, reference, status, created_at, target_completion)
    VALUES (?, ?, ?, ?, ?, ?)
  `);
  
  const projectResult = projectStmt.run(
    data.project.name,
    data.project.description || '',
    data.project.reference || '',
    data.project.status || 'not-started',
    data.project.created_at || new Date().toISOString(),
    data.project.target_completion || null
  );
  
  const projectId = projectResult.lastInsertRowid;
  console.log(`✅ Project created with ID: ${projectId}\n`);
  
  // Insert tasks
  console.log(`📋 Inserting ${data.tasks.length} tasks...`);
  const taskStmt = db.prepare(`
    INSERT INTO tasks (
      id, project_id, title, description, state, priority,
      estimated_hours, actual_hours, assigned_to, agent_session_key,
      started_at, completed_at, spec_file,
      dependencies_json, tags_json, code_files_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);
  
  for (const task of data.tasks) {
    taskStmt.run(
      task.id,
      projectId,
      task.title,
      task.description || '',
      task.state || 'todo',
      task.priority || 'medium',
      task.estimated_hours || 0,
      task.actual_hours || 0,
      task.assigned_to || null,
      task.agent_session_key || null,
      task.started_at || null,
      task.completed_at || null,
      task.spec_file || null,
      JSON.stringify(task.dependencies || []),
      JSON.stringify(task.tags || []),
      JSON.stringify(task.code_files || [])
    );
  }
  console.log(`✅ ${data.tasks.length} tasks inserted\n`);
  
  // Insert active agents
  console.log(`🤖 Inserting ${data.agents.active.length} active agents...`);
  const agentStmt = db.prepare(`
    INSERT INTO agents (
      project_id, agent_id, session_key, task_id,
      spawned_at, status
    ) VALUES (?, ?, ?, ?, ?, 'running')
  `);
  
  for (const agent of data.agents.active) {
    agentStmt.run(
      projectId,
      agent.agent_id,
      agent.session_key || null,
      agent.task_id || null,
      agent.spawned_at || new Date().toISOString()
    );
  }
  console.log(`✅ ${data.agents.active.length} active agents inserted\n`);
  
  // Insert completed agents
  console.log(`✅ Inserting ${data.agents.completed.length} completed agents...`);
  const completedAgentStmt = db.prepare(`
    INSERT INTO agents (
      project_id, agent_id, task_id, completed_at,
      spawned_at, status, result
    ) VALUES (?, ?, ?, ?, ?, 'completed', ?)
  `);
  
  for (const agent of data.agents.completed) {
    completedAgentStmt.run(
      projectId,
      agent.agent_id,
      agent.task_id || null,
      agent.completed_at || new Date().toISOString(),
      agent.spawned_at || agent.completed_at || new Date().toISOString(),
      agent.result || ''
    );
  }
  console.log(`✅ ${data.agents.completed.length} completed agents inserted\n`);
  
  // Insert activity log
  console.log(`📝 Inserting ${data.activity_log.length} activity log entries...`);
  const logStmt = db.prepare(`
    INSERT INTO activity_log (
      project_id, timestamp, agent, task_id, message, type
    ) VALUES (?, ?, ?, ?, ?, ?)
  `);
  
  for (const entry of data.activity_log) {
    logStmt.run(
      projectId,
      entry.timestamp || new Date().toISOString(),
      entry.agent,
      entry.task_id || null,
      entry.message,
      entry.type || 'info'
    );
  }
  console.log(`✅ ${data.activity_log.length} activity log entries inserted\n`);
  
  return projectId;
});

// Execute migration
try {
  const projectId = migrate();
  
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('🎉 Migration completed successfully!');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log(`\n📊 Project ID: ${projectId}`);
  console.log(`🌐 View dashboard: http://localhost:3000/dashboard.html`);
  console.log(`📡 API endpoint: http://localhost:3000/api/projects/${projectId}\n`);
  
  // Print summary
  const stats = db.prepare(`
    SELECT 
      (SELECT COUNT(*) FROM projects) as projects,
      (SELECT COUNT(*) FROM tasks WHERE project_id = ?) as tasks,
      (SELECT COUNT(*) FROM agents WHERE project_id = ?) as agents,
      (SELECT COUNT(*) FROM activity_log WHERE project_id = ?) as logs
  `).get(projectId, projectId, projectId);
  
  console.log('📈 Database Summary:');
  console.log(`   - Projects: ${stats.projects}`);
  console.log(`   - Tasks: ${stats.tasks}`);
  console.log(`   - Agents: ${stats.agents}`);
  console.log(`   - Activity Logs: ${stats.logs}\n`);
  
} catch (error) {
  console.error('❌ Migration failed:', error.message);
  process.exit(1);
} finally {
  db.close();
}

const sqlite3 = require('sqlite3').verbose();
const path = require('path');

const DB_PATH = path.join(__dirname, '..', 'jobs.db');

let db = null;

function getDb() {
  if (!db) {
    db = new sqlite3.Database(DB_PATH);
    
    // Create tables
    db.run(`
      CREATE TABLE IF NOT EXISTS job_executions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL,
        job_name TEXT,
        status TEXT,
        output TEXT,
        error TEXT,
        duration_ms INTEGER,
        executed_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);
    
    db.run(`
      CREATE TABLE IF NOT EXISTS job_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL,
        action TEXT NOT NULL,
        metadata TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);
    
    db.run(`
      CREATE INDEX IF NOT EXISTS idx_job_exec_job_id ON job_executions(job_id);
      CREATE INDEX IF NOT EXISTS idx_job_exec_date ON job_executions(executed_at);
      CREATE INDEX IF NOT EXISTS idx_job_history_job_id ON job_history(job_id);
    `);
  }
  
  return db;
}

function logExecution(execution, callback) {
  const db = getDb();
  db.run(`
    INSERT INTO job_executions (job_id, job_name, status, output, error, duration_ms)
    VALUES (?, ?, ?, ?, ?, ?)
  `, [
    execution.jobId,
    execution.jobName,
    execution.status,
    execution.output,
    execution.error,
    execution.durationMs
  ], function(err) {
    if (callback) callback(err, this.lastID);
  });
}

function getRecentExecutions(limit = 50, callback) {
  const db = getDb();
  db.all(`
    SELECT *
    FROM job_executions
    ORDER BY executed_at DESC
    LIMIT ?
  `, [limit], callback);
}

function getExecutionsByJobId(jobId, limit = 20, callback) {
  const db = getDb();
  db.all(`
    SELECT *
    FROM job_executions
    WHERE job_id = ?
    ORDER BY executed_at DESC
    LIMIT ?
  `, [jobId, limit], callback);
}

function logJobAction(jobId, action, metadata, callback) {
  const db = getDb();
  db.run(`
    INSERT INTO job_history (job_id, action, metadata)
    VALUES (?, ?, ?)
  `, [
    jobId,
    action,
    JSON.stringify(metadata || {})
  ], function(err) {
    if (callback) callback(err, this.lastID);
  });
}

function getJobStats(callback) {
  const db = getDb();
  db.get(`
    SELECT 
      COUNT(*) as total_executions,
      SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
      SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as failed,
      AVG(duration_ms) as avg_duration,
      MAX(executed_at) as last_execution
    FROM job_executions
    WHERE executed_at > ?
  `, [Date.now() - (7 * 24 * 60 * 60 * 1000)], callback); // Last 7 days
}

module.exports = {
  getDb,
  logExecution,
  getRecentExecutions,
  getExecutionsByJobId,
  logJobAction,
  getJobStats
};

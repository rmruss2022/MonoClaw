const fs = require('fs');
const path = require('path');
const os = require('os');
const { DatabaseSync } = require('node:sqlite');

const DAY_MS = 24 * 60 * 60 * 1000;
const DEFAULT_RETENTION_DAYS = Number(process.env.CONTEXT_RETENTION_DAYS || 30);
const DEFAULT_MAX_ROWS = Number(process.env.CONTEXT_MAX_ROWS || 10000);

class ContextStorage {
  constructor() {
    this.dbPath = process.env.COMMANDHUB_CONTEXT_DB_PATH ||
      path.join(os.homedir(), '.commandhub', 'data', 'context-manager.db');
    this.lastCompactAt = 0;
    this.db = null;
    this._init();
  }

  _init() {
    fs.mkdirSync(path.dirname(this.dbPath), { recursive: true });
    this.db = new DatabaseSync(this.dbPath);
    this.db.exec('PRAGMA journal_mode = WAL');
    this.db.exec('PRAGMA synchronous = NORMAL');
    this.db.exec('PRAGMA temp_store = MEMORY');
    this.db.exec('PRAGMA foreign_keys = ON');

    this.db.exec(`
      CREATE TABLE IF NOT EXISTS context_reports (
        id TEXT PRIMARY KEY,
        agent_id TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        total_sessions INTEGER,
        main_sessions INTEGER,
        subagent_sessions INTEGER,
        total_transcript_mb REAL,
        payload_json TEXT
      );
      CREATE INDEX IF NOT EXISTS idx_context_reports_agent_time
        ON context_reports(agent_id, created_at DESC);

      CREATE TABLE IF NOT EXISTS context_prune_runs (
        id TEXT PRIMARY KEY,
        agent_id TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        older_than_minutes INTEGER NOT NULL,
        apply INTEGER NOT NULL,
        pruned_count INTEGER,
        renamed_count INTEGER,
        missing_transcript_count INTEGER,
        total_size_mb REAL,
        backup_file TEXT,
        result_json TEXT
      );
      CREATE INDEX IF NOT EXISTS idx_context_prune_agent_time
        ON context_prune_runs(agent_id, created_at DESC);
    `);
  }

  saveReport(row) {
    const stmt = this.db.prepare(`
      INSERT INTO context_reports (
        id, agent_id, created_at, total_sessions, main_sessions,
        subagent_sessions, total_transcript_mb, payload_json
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `);
    stmt.run(
      row.id,
      row.agentId,
      row.createdAt,
      row.totalSessions || 0,
      row.mainSessions || 0,
      row.subAgentSessions || 0,
      row.totalTranscriptMb || 0,
      row.payloadJson || null
    );
    this._maybeCompact();
  }

  savePruneRun(row) {
    const stmt = this.db.prepare(`
      INSERT INTO context_prune_runs (
        id, agent_id, created_at, older_than_minutes, apply,
        pruned_count, renamed_count, missing_transcript_count,
        total_size_mb, backup_file, result_json
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);
    stmt.run(
      row.id,
      row.agentId,
      row.createdAt,
      row.olderThanMinutes || 0,
      row.apply ? 1 : 0,
      row.prunedCount || 0,
      row.renamedCount || 0,
      row.missingTranscriptCount || 0,
      row.totalSizeMb || 0,
      row.backupFile || null,
      row.resultJson || null
    );
    this._maybeCompact();
  }

  getTrends(agentId, rangeDays) {
    const since = Date.now() - (rangeDays * DAY_MS);
    const reportRows = this.db.prepare(`
      SELECT
        (created_at / 86400000) * 86400000 AS day_bucket,
        COUNT(*) AS run_count,
        AVG(total_sessions) AS avg_total_sessions,
        AVG(subagent_sessions) AS avg_subagent_sessions,
        AVG(total_transcript_mb) AS avg_total_transcript_mb
      FROM context_reports
      WHERE agent_id = ? AND created_at >= ?
      GROUP BY day_bucket
      ORDER BY day_bucket ASC
    `).all(agentId, since);

    const pruneRows = this.db.prepare(`
      SELECT
        (created_at / 86400000) * 86400000 AS day_bucket,
        COUNT(*) AS prune_runs,
        SUM(pruned_count) AS total_pruned,
        SUM(total_size_mb) AS total_size_mb
      FROM context_prune_runs
      WHERE agent_id = ? AND created_at >= ?
      GROUP BY day_bucket
      ORDER BY day_bucket ASC
    `).all(agentId, since);

    return {
      agentId,
      rangeDays,
      reportsByDay: reportRows,
      prunesByDay: pruneRows,
      generatedAt: Date.now(),
    };
  }

  compactNow() {
    const cutoff = Date.now() - (DEFAULT_RETENTION_DAYS * DAY_MS);
    const deletedReportsOld = this.db.prepare(
      `DELETE FROM context_reports WHERE created_at < ?`
    ).run(cutoff).changes;
    const deletedPrunesOld = this.db.prepare(
      `DELETE FROM context_prune_runs WHERE created_at < ?`
    ).run(cutoff).changes;

    const deletedReportsCap = this.db.prepare(`
      DELETE FROM context_reports
      WHERE id NOT IN (
        SELECT id FROM context_reports
        ORDER BY created_at DESC
        LIMIT ?
      )
    `).run(DEFAULT_MAX_ROWS).changes;
    const deletedPrunesCap = this.db.prepare(`
      DELETE FROM context_prune_runs
      WHERE id NOT IN (
        SELECT id FROM context_prune_runs
        ORDER BY created_at DESC
        LIMIT ?
      )
    `).run(DEFAULT_MAX_ROWS).changes;

    return {
      deletedReportsOld,
      deletedPrunesOld,
      deletedReportsCap,
      deletedPrunesCap,
      retentionDays: DEFAULT_RETENTION_DAYS,
      maxRows: DEFAULT_MAX_ROWS,
      dbPath: this.dbPath,
    };
  }

  _maybeCompact() {
    const now = Date.now();
    if (now - this.lastCompactAt < 60 * 60 * 1000) {
      return;
    }
    this.lastCompactAt = now;
    try {
      this.compactNow();
    } catch (error) {
      console.error('[context-storage] compact failed:', error.message);
    }
  }
}

module.exports = ContextStorage;

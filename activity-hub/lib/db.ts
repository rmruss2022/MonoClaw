import Database from 'better-sqlite3';
import path from 'path';

const DB_PATH = path.join(process.cwd(), 'activities.db');

let db: Database.Database | null = null;

export function getDb() {
  if (!db) {
    db = new Database(DB_PATH);
    db.pragma('journal_mode = WAL');
    
    // Create activities table
    db.exec(`
      CREATE TABLE IF NOT EXISTS activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp INTEGER NOT NULL,
        time TEXT NOT NULL,
        action TEXT NOT NULL,
        type TEXT NOT NULL,
        agentName TEXT,
        agentId TEXT,
        category TEXT,
        color TEXT,
        icon TEXT,
        metadata TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      );
      
      CREATE INDEX IF NOT EXISTS idx_timestamp ON activities(timestamp DESC);
      CREATE INDEX IF NOT EXISTS idx_agentName ON activities(agentName);
      CREATE INDEX IF NOT EXISTS idx_category ON activities(category);
    `);
  }
  
  return db;
}

export interface Activity {
  id?: number;
  timestamp: number;
  time: string;
  action: string;
  type: string;
  agentName?: string;
  agentId?: string;
  category?: string;
  color?: string;
  icon?: string;
  metadata?: any;
}

export function insertActivity(activity: Activity): number {
  const db = getDb();
  
  const stmt = db.prepare(`
    INSERT INTO activities (timestamp, time, action, type, agentName, agentId, category, color, icon, metadata)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);
  
  const info = stmt.run(
    activity.timestamp,
    activity.time,
    activity.action,
    activity.type,
    activity.agentName || null,
    activity.agentId || null,
    activity.category || null,
    activity.color || null,
    activity.icon || null,
    activity.metadata ? JSON.stringify(activity.metadata) : null
  );
  
  return info.lastInsertRowid as number;
}

export function getRecentActivities(limit: number = 100): Activity[] {
  const db = getDb();
  
  const stmt = db.prepare(`
    SELECT id, timestamp, time, action, type, agentName, agentId, category, color, icon, metadata
    FROM activities
    ORDER BY timestamp DESC
    LIMIT ?
  `);
  
  const rows = stmt.all(limit) as any[];
  
  return rows.map(row => ({
    ...row,
    metadata: row.metadata ? JSON.parse(row.metadata) : null
  }));
}

export function getActivityCount(): number {
  const db = getDb();
  const result = db.prepare('SELECT COUNT(*) as count FROM activities').get() as any;
  return result.count;
}

export function getActivitiesByTimeRange(startTime: number, endTime: number): Activity[] {
  const db = getDb();
  
  const stmt = db.prepare(`
    SELECT id, timestamp, time, action, type, agentName, agentId, category, color, icon, metadata
    FROM activities
    WHERE timestamp BETWEEN ? AND ?
    ORDER BY timestamp DESC
  `);
  
  const rows = stmt.all(startTime, endTime) as any[];
  
  return rows.map(row => ({
    ...row,
    metadata: row.metadata ? JSON.parse(row.metadata) : null
  }));
}

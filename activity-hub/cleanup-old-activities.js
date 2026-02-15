#!/usr/bin/env node

const Database = require('better-sqlite3');
const fs = require('fs');
const path = require('path');

const DB_PATH = path.join(__dirname, 'activities.db');
const SNAPSHOTS_DIR = path.join(__dirname, 'snapshots');

// Ensure snapshots directory exists
if (!fs.existsSync(SNAPSHOTS_DIR)) {
  fs.mkdirSync(SNAPSHOTS_DIR, { recursive: true });
}

function cleanupOldActivities() {
  const db = new Database(DB_PATH);
  
  try {
    // Get current timestamp
    const now = Date.now();
    const oneDayAgo = now - (24 * 60 * 60 * 1000);
    
    // Count records to be deleted
    const countStmt = db.prepare('SELECT COUNT(*) as count FROM activities WHERE timestamp < ?');
    const { count } = countStmt.get(oneDayAgo);
    
    console.log(`[${new Date().toISOString()}] Found ${count} activities older than 24 hours`);
    
    if (count > 0) {
      // Optional: Create daily snapshot before deletion
      const today = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
      const snapshotPath = path.join(SNAPSHOTS_DIR, `activities-${today}.json`);
      
      // Only create snapshot if it doesn't exist yet today
      if (!fs.existsSync(snapshotPath)) {
        console.log(`[${new Date().toISOString()}] Creating snapshot: ${snapshotPath}`);
        
        const snapshotStmt = db.prepare(`
          SELECT 
            COUNT(*) as total_activities,
            MIN(timestamp) as oldest_timestamp,
            MAX(timestamp) as newest_timestamp,
            COUNT(DISTINCT category) as unique_categories,
            COUNT(DISTINCT agentName) as unique_agents
          FROM activities
        `);
        const stats = snapshotStmt.get();
        
        // Get category breakdown
        const categoriesStmt = db.prepare(`
          SELECT category, COUNT(*) as count
          FROM activities
          GROUP BY category
          ORDER BY count DESC
        `);
        const categories = categoriesStmt.all();
        
        const snapshot = {
          date: today,
          timestamp: now,
          stats,
          categories,
          note: 'Daily snapshot before cleanup'
        };
        
        fs.writeFileSync(snapshotPath, JSON.stringify(snapshot, null, 2));
        console.log(`[${new Date().toISOString()}] Snapshot saved with ${stats.total_activities} activities`);
      }
      
      // Delete old activities
      const deleteStmt = db.prepare('DELETE FROM activities WHERE timestamp < ?');
      const result = deleteStmt.run(oneDayAgo);
      
      console.log(`[${new Date().toISOString()}] Deleted ${result.changes} old activities`);
      
      // Vacuum to reclaim space
      console.log(`[${new Date().toISOString()}] Running VACUUM to reclaim space...`);
      db.exec('VACUUM');
      
      console.log(`[${new Date().toISOString()}] Cleanup complete`);
    } else {
      console.log(`[${new Date().toISOString()}] No cleanup needed`);
    }
    
    // Show current stats
    const statsStmt = db.prepare(`
      SELECT 
        COUNT(*) as total,
        COUNT(DISTINCT category) as categories,
        COUNT(DISTINCT agentName) as agents
      FROM activities
    `);
    const currentStats = statsStmt.get();
    console.log(`[${new Date().toISOString()}] Current database: ${currentStats.total} activities, ${currentStats.categories} categories, ${currentStats.agents} agents`);
    
  } catch (error) {
    console.error(`[${new Date().toISOString()}] Cleanup error:`, error);
    process.exit(1);
  } finally {
    db.close();
  }
}

// Run cleanup
cleanupOldActivities();

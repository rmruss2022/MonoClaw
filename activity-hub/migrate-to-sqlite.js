const { getDb, insertActivity } = require('./lib/db.ts');
const fs = require('fs');
const path = require('path');

const JSON_PATH = path.join(__dirname, 'activities-store.json');

async function migrate() {
  console.log('🦞 Migrating activities from JSON to SQLite...');
  
  try {
    // Read JSON file
    const jsonData = fs.readFileSync(JSON_PATH, 'utf-8');
    const activities = JSON.parse(jsonData);
    
    console.log(`Found ${activities.length} activities in JSON file`);
    
    // Get database
    const db = getDb();
    
    // Count existing records
    const existing = db.prepare('SELECT COUNT(*) as count FROM activities').get();
    console.log(`Database currently has ${existing.count} activities`);
    
    if (existing.count > 0) {
      console.log('⚠️  Database already has data. Skipping migration to avoid duplicates.');
      console.log('   Delete activities.db if you want to re-import from JSON.');
      return;
    }
    
    // Insert all activities in a transaction
    const insert = db.transaction((activities) => {
      let count = 0;
      for (const activity of activities) {
        try {
          insertActivity(activity);
          count++;
        } catch (error) {
          console.error(`Failed to insert activity:`, error.message);
        }
      }
      return count;
    });
    
    const inserted = insert(activities);
    console.log(`✅ Successfully migrated ${inserted} activities to SQLite`);
    
    // Backup JSON file
    const backupPath = JSON_PATH + '.backup';
    fs.copyFileSync(JSON_PATH, backupPath);
    console.log(`📦 Backed up JSON file to ${backupPath}`);
    
  } catch (error) {
    console.error('❌ Migration failed:', error);
    process.exit(1);
  }
}

migrate();

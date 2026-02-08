import { query } from '../config/database';
import * as fs from 'fs';
import * as path from 'path';

async function runSchema() {
  try {
    console.log('📋 Running database schema...');

    const schemaPath = path.join(__dirname, '../db/schema.sql');
    const schema = fs.readFileSync(schemaPath, 'utf8');

    // Split by semicolons and run each statement
    const statements = schema
      .split(';')
      .map(s => s.trim())
      .filter(s => s.length > 0);

    for (const statement of statements) {
      await query(statement);
    }

    console.log('✅ Database schema created successfully');
    process.exit(0);
  } catch (error) {
    console.error('❌ Error running schema:', error);
    process.exit(1);
  }
}

runSchema();

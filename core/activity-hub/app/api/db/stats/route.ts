import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import Database from 'better-sqlite3';

const DB_PATH = path.join(process.cwd(), 'activities.db');

export async function GET() {
  try {
    // Get file size
    const stats = fs.statSync(DB_PATH);
    const sizeInBytes = stats.size;
    const sizeInMB = (sizeInBytes / (1024 * 1024)).toFixed(2);
    
    // Open database and get record counts
    const db = new Database(DB_PATH, { readonly: true });
    
    const totalQuery = db.prepare('SELECT COUNT(*) as count FROM activities');
    const total = totalQuery.get() as { count: number };
    
    const categoriesQuery = db.prepare('SELECT category, COUNT(*) as count FROM activities GROUP BY category ORDER BY count DESC');
    const categories = categoriesQuery.all() as Array<{ category: string; count: number }>;
    
    const timestampQuery = db.prepare('SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest FROM activities');
    const timestamps = timestampQuery.get() as { oldest: number; newest: number };
    
    const agentsQuery = db.prepare('SELECT COUNT(DISTINCT agentName) as count FROM activities');
    const agents = agentsQuery.get() as { count: number };
    
    db.close();
    
    return NextResponse.json({
      ok: true,
      stats: {
        sizeInBytes,
        sizeInMB: parseFloat(sizeInMB),
        totalRecords: total.count,
        uniqueAgents: agents.count,
        categories: categories,
        oldestTimestamp: timestamps.oldest,
        newestTimestamp: timestamps.newest,
        ageInDays: timestamps.oldest && timestamps.newest 
          ? ((timestamps.newest - timestamps.oldest) / (1000 * 60 * 60 * 24)).toFixed(1)
          : 0
      }
    });
  } catch (error: any) {
    return NextResponse.json(
      { ok: false, error: error.message },
      { status: 500 }
    );
  }
}

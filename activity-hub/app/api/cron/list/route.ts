import { NextRequest, NextResponse } from 'next/server';
import { readFile } from 'fs/promises';
import { join } from 'path';

export async function GET(request: NextRequest) {
  try {
    // Try to read cached cron jobs data
    const dataPath = join(process.cwd(), 'data', 'cron-jobs.json');
    
    try {
      const data = await readFile(dataPath, 'utf-8');
      const parsed = JSON.parse(data);
      
      return NextResponse.json({
        success: true,
        jobs: parsed.jobs || [],
        count: parsed.count || 0,
        synced: parsed.synced,
      });
    } catch (e) {
      // Data file doesn't exist, return mock data
    }

    // Return mock data based on known cron jobs
    const mockJobs = [
      {
        jobId: '8f10f8dd-8cff-433d-9e6b-f41da95eb8c7',
        name: 'Morning News Briefing',
        schedule: { kind: 'cron', expr: '0 8 * * *', tz: 'America/New_York' },
        enabled: true,
        status: 'scheduled',
      },
      {
        jobId: '010b8964-88ce-4ca2-a0ce-76b8b8511e6d',
        name: 'Daily Security Audit (Kimi K2.5)',
        schedule: { kind: 'cron', expr: '0 9 * * *', tz: 'America/New_York' },
        enabled: true,
        status: 'scheduled',
      },
      {
        jobId: 'token-tracker',
        name: 'Token Data Collection',
        schedule: { kind: 'every', everyMs: 3600000 },
        enabled: true,
        status: 'active',
      },
      {
        jobId: '049cbe98-3609-43c3-8745-defdea52cbc2',
        name: 'Centralized Health Check',
        schedule: { kind: 'every', everyMs: 300000 },
        enabled: true,
        status: 'active',
      },
    ];

    return NextResponse.json({
      success: true,
      jobs: mockJobs,
      count: mockJobs.length,
      mock: true,
      note: 'Using mock data - run sync-cron-jobs.js to fetch real data',
    });
  } catch (error) {
    console.error('[Cron List Error]', error);
    
    return NextResponse.json({
      success: false,
      error: 'Failed to load cron jobs',
    }, { status: 500 });
  }
}

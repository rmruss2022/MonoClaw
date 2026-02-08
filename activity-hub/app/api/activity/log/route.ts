import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';

const STORE_PATH = path.join(process.cwd(), 'activities-store.json');
const MAX_ACTIVITIES = 500; // Keep last 500 activities

async function readActivities(): Promise<any[]> {
  try {
    const data = await fs.readFile(STORE_PATH, 'utf-8');
    return JSON.parse(data);
  } catch {
    return [];
  }
}

async function writeActivities(activities: any[]): Promise<void> {
  await fs.writeFile(STORE_PATH, JSON.stringify(activities, null, 2));
}

export async function GET() {
  try {
    const activities = await readActivities();
    return NextResponse.json({
      success: true,
      activities: activities.slice(-100).reverse(), // Return last 100, newest first
      total: activities.length,
    });
  } catch (error) {
    console.error('[Activity GET Error]', error);
    return NextResponse.json(
      { error: 'Failed to fetch activities' },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { action, type, metadata } = body;

    if (!action || !type) {
      return NextResponse.json(
        { error: 'Missing required fields: action, type' },
        { status: 400 }
      );
    }

    const now = new Date();
    const timestamp = now.getTime();
    const time = now.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });

    const activity = { timestamp, time, action, type, metadata };

    // Read current activities
    const activities = await readActivities();
    
    // Add new activity
    activities.push(activity);
    
    // Trim to max size
    const trimmed = activities.slice(-MAX_ACTIVITIES);
    
    // Write back
    await writeActivities(trimmed);

    console.log('[Activity Log]', activity);

    return NextResponse.json({
      success: true,
      activity,
    });
  } catch (error) {
    console.error('[Activity Log Error]', error);
    return NextResponse.json(
      { error: 'Failed to log activity' },
      { status: 500 }
    );
  }
}

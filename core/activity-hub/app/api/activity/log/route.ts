import { NextRequest, NextResponse } from 'next/server';
import { getDb, insertActivity, getRecentActivities, getActivityCount } from '@/lib/db';

export async function GET(request: NextRequest) {
  try {
    // Get limit from query params, default to 500, max 10000
    const { searchParams } = new URL(request.url);
    const limitParam = searchParams.get('limit');
    const limit = Math.min(
      limitParam ? parseInt(limitParam, 10) : 500,
      10000
    );
    
    const activities = getRecentActivities(limit);
    const total = getActivityCount();
    
    return NextResponse.json({
      success: true,
      activities,
      total,
      limit,
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
    const { action, type, metadata, category, color, icon, agentName, agentId } = body;

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

    const activity = {
      timestamp,
      time,
      action,
      type,
      agentName,
      agentId,
      category,
      color,
      icon,
      metadata,
    };

    const id = insertActivity(activity);

    console.log('[Activity Log]', activity);

    return NextResponse.json({
      success: true,
      activity: { id, ...activity },
    });
  } catch (error) {
    console.error('[Activity Log Error]', error);
    return NextResponse.json(
      { error: 'Failed to log activity' },
      { status: 500 }
    );
  }
}

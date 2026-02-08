import { NextRequest, NextResponse } from 'next/server';

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

    // TODO: Call Convex mutation once Convex is initialized
    // For now, just log to console
    console.log('[Activity Log]', { timestamp, time, action, type, metadata });

    return NextResponse.json({
      success: true,
      activity: { timestamp, time, action, type, metadata },
    });
  } catch (error) {
    console.error('[Activity Log Error]', error);
    return NextResponse.json(
      { error: 'Failed to log activity' },
      { status: 500 }
    );
  }
}

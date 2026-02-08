import { query } from '../config/database';

export interface Meditation {
  id: string;
  title: string;
  description: string;
  duration: number;
  category: string;
  icon: string;
  audioUrl?: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface MeditationSession {
  id: string;
  userId: string;
  meditationId: string;
  startedAt: Date;
  completedAt?: Date;
  durationCompleted?: number;
}

export class MeditationService {
  async getAllMeditations(): Promise<Meditation[]> {
    const queryText = `
      SELECT
        id, title, description, duration, category, icon,
        audio_url as "audioUrl", created_at as "createdAt",
        updated_at as "updatedAt"
      FROM meditations
      ORDER BY created_at DESC
    `;

    const result = await query(queryText);
    return result.rows;
  }

  async getMeditationsByCategory(category: string): Promise<Meditation[]> {
    const queryText = `
      SELECT
        id, title, description, duration, category, icon,
        audio_url as "audioUrl", created_at as "createdAt",
        updated_at as "updatedAt"
      FROM meditations
      WHERE category = $1
      ORDER BY created_at DESC
    `;

    const result = await query(queryText, [category]);
    return result.rows;
  }

  async getMeditationById(id: string): Promise<Meditation | null> {
    const queryText = `
      SELECT
        id, title, description, duration, category, icon,
        audio_url as "audioUrl", created_at as "createdAt",
        updated_at as "updatedAt"
      FROM meditations
      WHERE id = $1
    `;

    const result = await query(queryText, [id]);
    return result.rows[0] || null;
  }

  async startSession(userId: string, meditationId: string): Promise<MeditationSession> {
    const queryText = `
      INSERT INTO meditation_sessions (user_id, meditation_id, started_at)
      VALUES ($1, $2, NOW())
      RETURNING
        id, user_id as "userId", meditation_id as "meditationId",
        started_at as "startedAt"
    `;

    const result = await query(queryText, [userId, meditationId]);
    return result.rows[0];
  }

  async completeSession(
    sessionId: string,
    durationCompleted: number
  ): Promise<MeditationSession> {
    const queryText = `
      UPDATE meditation_sessions
      SET completed_at = NOW(), duration_completed = $2
      WHERE id = $1
      RETURNING
        id, user_id as "userId", meditation_id as "meditationId",
        started_at as "startedAt", completed_at as "completedAt",
        duration_completed as "durationCompleted"
    `;

    const result = await query(queryText, [sessionId, durationCompleted]);
    return result.rows[0];
  }

  async getUserSessions(userId: string, limit = 10): Promise<MeditationSession[]> {
    const queryText = `
      SELECT
        ms.id, ms.user_id as "userId", ms.meditation_id as "meditationId",
        ms.started_at as "startedAt", ms.completed_at as "completedAt",
        ms.duration_completed as "durationCompleted",
        m.title as "meditationTitle", m.icon as "meditationIcon"
      FROM meditation_sessions ms
      JOIN meditations m ON ms.meditation_id = m.id
      WHERE ms.user_id = $1
      ORDER BY ms.started_at DESC
      LIMIT $2
    `;

    const result = await query(queryText, [userId, limit]);
    return result.rows;
  }

  async getUserStats(userId: string): Promise<{
    totalSessions: number;
    totalMinutes: number;
    currentStreak: number;
    completedThisWeek: number;
  }> {
    const statsQuery = `
      SELECT
        COUNT(*) as "totalSessions",
        COALESCE(SUM(duration_completed), 0) as "totalMinutes"
      FROM meditation_sessions
      WHERE user_id = $1 AND completed_at IS NOT NULL
    `;

    const weekQuery = `
      SELECT COUNT(*) as "completedThisWeek"
      FROM meditation_sessions
      WHERE user_id = $1
        AND completed_at IS NOT NULL
        AND started_at >= NOW() - INTERVAL '7 days'
    `;

    const [statsResult, weekResult] = await Promise.all([
      query(statsQuery, [userId]),
      query(weekQuery, [userId])
    ]);

    return {
      totalSessions: parseInt(statsResult.rows[0].totalSessions),
      totalMinutes: parseInt(statsResult.rows[0].totalMinutes),
      currentStreak: 0, // TODO: Calculate streak
      completedThisWeek: parseInt(weekResult.rows[0].completedThisWeek)
    };
  }
}

export const meditationService = new MeditationService();

import { query } from '../config/database';
import { randomUUID } from 'crypto';

export class PostgresService {
  // ===== USER OPERATIONS =====

  async createUser(user: {
    email: string;
    passwordHash: string;
    id?: string;
  }): Promise<void> {
    const userId = user.id || randomUUID();
    await query(
      'INSERT INTO users (id, email, password_hash) VALUES ($1, $2, $3)',
      [userId, user.email, user.passwordHash]
    );
  }

  async getUserById(userId: string): Promise<any | null> {
    const result = await query('SELECT * FROM users WHERE id = $1', [userId]);
    return result.rows[0] || null;
  }

  async getUserByEmail(email: string): Promise<any | null> {
    const result = await query('SELECT * FROM users WHERE email = $1', [email]);
    return result.rows[0] || null;
  }

  // ===== USER SUMMARIES (For Agent Context) =====

  async getUserSummaries(userId: string, summaryType?: string): Promise<any[]> {
    let queryText = 'SELECT * FROM user_summaries WHERE user_id = $1';
    const params: any[] = [userId];

    if (summaryType) {
      queryText += ' AND summary_type = $2';
      params.push(summaryType);
    }

    queryText += ' ORDER BY updated_at DESC';

    const result = await query(queryText, params);
    return result.rows;
  }

  async createUserSummary(data: {
    userId: string;
    summaryType: string;
    summaryText: string;
    confidenceScore?: number;
    metadata?: any;
  }): Promise<void> {
    await query(
      `INSERT INTO user_summaries
       (user_id, summary_type, summary_text, confidence_score, metadata)
       VALUES ($1, $2, $3, $4, $5)`,
      [
        data.userId,
        data.summaryType,
        data.summaryText,
        data.confidenceScore || 0.5,
        JSON.stringify(data.metadata || {}),
      ]
    );
  }

  async updateUserSummary(
    userId: string,
    summaryType: string,
    summaryText: string,
    confidenceScore?: number
  ): Promise<void> {
    await query(
      `UPDATE user_summaries
       SET summary_text = $1, confidence_score = $2, updated_at = CURRENT_TIMESTAMP
       WHERE user_id = $3 AND summary_type = $4`,
      [summaryText, confidenceScore || 0.5, userId, summaryType]
    );
  }

  // ===== JOURNAL ENTRIES =====

  async createJournalEntry(entry: {
    id?: string;
    userId: string;
    content: string;
    mood?: string;
    tags?: string[];
    behaviorContext?: string;
    metadata?: any;
  }): Promise<string> {
    const entryId = entry.id || randomUUID();
    await query(
      `INSERT INTO journal_entries
       (id, user_id, content, mood, tags, behavior_context, metadata)
       VALUES ($1, $2, $3, $4, $5, $6, $7)`,
      [
        entryId,
        entry.userId,
        entry.content,
        entry.mood || null,
        entry.tags || [],
        entry.behaviorContext || null,
        JSON.stringify(entry.metadata || {}),
      ]
    );
    return entryId;
  }

  async getJournalEntries(
    userId: string,
    limit: number = 10,
    offset: number = 0
  ): Promise<any[]> {
    const result = await query(
      `SELECT * FROM journal_entries
       WHERE user_id = $1
       ORDER BY created_at DESC
       LIMIT $2 OFFSET $3`,
      [userId, limit, offset]
    );
    return result.rows;
  }

  async getJournalEntry(entryId: string): Promise<any | null> {
    const result = await query(
      'SELECT * FROM journal_entries WHERE id = $1',
      [entryId]
    );
    return result.rows[0] || null;
  }

  async searchJournalEntries(
    userId: string,
    searchQuery: string,
    limit: number = 10
  ): Promise<any[]> {
    const result = await query(
      `SELECT * FROM journal_entries
       WHERE user_id = $1 AND content ILIKE $2
       ORDER BY created_at DESC
       LIMIT $3`,
      [userId, `%${searchQuery}%`, limit]
    );
    return result.rows;
  }

  // ===== CHAT MESSAGES =====

  async saveChatMessage(message: {
    id?: string;
    userId: string;
    role: 'user' | 'assistant';
    content: string;
    behaviorId?: string;
    metadata?: any;
  }): Promise<void> {
    const messageId = message.id || randomUUID();
    await query(
      `INSERT INTO chat_messages
       (id, user_id, role, content, behavior_id, metadata)
       VALUES ($1, $2, $3, $4, $5, $6)`,
      [
        messageId,
        message.userId,
        message.role,
        message.content,
        message.behaviorId || null,
        JSON.stringify(message.metadata || {}),
      ]
    );
  }

  async getChatHistory(
    userId: string,
    limit: number = 20
  ): Promise<any[]> {
    const result = await query(
      `SELECT * FROM chat_messages
       WHERE user_id = $1
       ORDER BY created_at DESC
       LIMIT $2`,
      [userId, limit]
    );
    // Return in chronological order
    return result.rows.reverse();
  }

  // ===== BEHAVIOR TRANSITIONS =====

  async recordBehaviorTransition(data: {
    userId: string;
    fromBehavior?: string;
    toBehavior: string;
    triggerReason?: string;
    confidenceScore?: number;
    userOverrode?: boolean;
    context?: any;
  }): Promise<void> {
    await query(
      `INSERT INTO behavior_transitions
       (user_id, from_behavior, to_behavior, trigger_reason, confidence_score, user_overrode, context)
       VALUES ($1, $2, $3, $4, $5, $6, $7)`,
      [
        data.userId,
        data.fromBehavior || null,
        data.toBehavior,
        data.triggerReason || null,
        data.confidenceScore || null,
        data.userOverrode || false,
        JSON.stringify(data.context || {}),
      ]
    );
  }

  async getBehaviorTransitions(
    userId: string,
    limit: number = 50
  ): Promise<any[]> {
    const result = await query(
      `SELECT * FROM behavior_transitions
       WHERE user_id = $1
       ORDER BY created_at DESC
       LIMIT $2`,
      [userId, limit]
    );
    return result.rows;
  }
}

export const postgresService = new PostgresService();

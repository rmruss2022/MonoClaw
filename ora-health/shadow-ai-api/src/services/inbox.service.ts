import { query } from '../config/database';

export interface InboxMessage {
  id: string;
  userId: string;
  messageType: 'prompt' | 'encouragement' | 'activity_suggestion' | 'insight' | 'community_highlight';
  subject?: string;
  content: string;
  metadata?: Record<string, any>;
  isRead: boolean;
  isArchived: boolean;
  readAt?: Date;
  archivedAt?: Date;
  createdAt: Date;
  timestamp: string;
}

export interface InboxMessageResponse {
  id: string;
  messageId: string;
  userId: string;
  responseText: string;
  createdPostId?: string;
  createdAt: Date;
}

export class InboxService {
  async getMessages(
    userId: string,
    filters: {
      unreadOnly?: boolean;
      limit?: number;
      offset?: number;
    } = {}
  ): Promise<{ messages: InboxMessage[]; unreadCount: number; totalCount: number }> {
    const { unreadOnly = false, limit = 20, offset = 0 } = filters;

    // Build WHERE clause
    const whereConditions = ['user_id = $1', 'is_archived = false'];
    if (unreadOnly) {
      whereConditions.push('is_read = false');
    }

    const whereClause = whereConditions.join(' AND ');

    // Get messages
    const queryText = `
      SELECT
        id,
        user_id as "userId",
        message_type as "messageType",
        subject,
        content,
        metadata,
        is_read as "isRead",
        is_archived as "isArchived",
        read_at as "readAt",
        archived_at as "archivedAt",
        created_at as "createdAt"
      FROM inbox_messages
      WHERE ${whereClause}
      ORDER BY created_at DESC
      LIMIT $2 OFFSET $3
    `;

    const result = await query(queryText, [userId, limit, offset]);

    // Get counts
    const countQuery = `
      SELECT
        COUNT(*) FILTER (WHERE is_read = false AND is_archived = false) as unread_count,
        COUNT(*) FILTER (WHERE is_archived = false) as total_count
      FROM inbox_messages
      WHERE user_id = $1
    `;
    const countResult = await query(countQuery, [userId]);

    const messages = result.rows.map(row => ({
      id: row.id,
      userId: row.userId,
      messageType: row.messageType,
      subject: row.subject,
      content: row.content,
      metadata: row.metadata,
      isRead: row.isRead,
      isArchived: row.isArchived,
      readAt: row.readAt,
      archivedAt: row.archivedAt,
      createdAt: row.createdAt,
      timestamp: this.formatTimestamp(row.createdAt)
    }));

    return {
      messages,
      unreadCount: parseInt(countResult.rows[0].unread_count, 10),
      totalCount: parseInt(countResult.rows[0].total_count, 10)
    };
  }

  async markAsRead(messageId: string, userId: string): Promise<void> {
    const queryText = `
      UPDATE inbox_messages
      SET is_read = true, read_at = NOW()
      WHERE id = $1 AND user_id = $2
    `;
    await query(queryText, [messageId, userId]);
  }

  async archiveMessage(messageId: string, userId: string): Promise<void> {
    const queryText = `
      UPDATE inbox_messages
      SET is_archived = true, archived_at = NOW()
      WHERE id = $1 AND user_id = $2
    `;
    await query(queryText, [messageId, userId]);
  }

  async respondToMessage(
    messageId: string,
    userId: string,
    responseText: string,
    createPost: boolean,
    isAnonymous: boolean = false,
    authorName: string = 'User',
    authorAvatar: string = '👤'
  ): Promise<{ success: boolean; postId?: string }> {
    let createdPostId: string | undefined;

    // If user wants to share as post, create the post
    if (createPost) {
      // Get message details to determine category
      const messageQuery = await query(
        'SELECT message_type, content, metadata FROM inbox_messages WHERE id = $1',
        [messageId]
      );

      if (messageQuery.rows.length === 0) {
        throw new Error('Message not found');
      }

      const message = messageQuery.rows[0];

      // Map message type to post category
      const categoryMap: Record<string, string> = {
        'prompt': 'prompt',
        'encouragement': 'progress',
        'activity_suggestion': 'progress',
        'insight': 'progress',
        'community_highlight': 'gratitude'
      };

      const category = categoryMap[message.message_type] || 'progress';

      // Create the post
      const postQuery = `
        INSERT INTO community_posts (
          user_id, type, category, content, prompt_text,
          is_anonymous, author_name, author_avatar
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
      `;

      const postResult = await query(postQuery, [
        userId,
        category, // type
        category, // category
        responseText,
        message.content, // Store original message as prompt_text
        isAnonymous,
        authorName,
        authorAvatar
      ]);

      createdPostId = postResult.rows[0].id;
    }

    // Save the response
    const responseQuery = `
      INSERT INTO inbox_message_responses (
        message_id, user_id, response_text, created_post_id
      )
      VALUES ($1, $2, $3, $4)
      RETURNING id
    `;

    await query(responseQuery, [
      messageId,
      userId,
      responseText,
      createdPostId || null
    ]);

    // Mark message as read
    await this.markAsRead(messageId, userId);

    return {
      success: true,
      postId: createdPostId
    };
  }

  async getUnreadCount(userId: string): Promise<number> {
    const queryText = `
      SELECT COUNT(*) as count
      FROM inbox_messages
      WHERE user_id = $1 AND is_read = false AND is_archived = false
    `;
    const result = await query(queryText, [userId]);
    return parseInt(result.rows[0].count, 10);
  }

  async generateDailyMessage(userId: string): Promise<InboxMessage> {
    // This is a placeholder for AI-generated personalized messages
    // In production, this would use user summaries, journal entries, etc.
    // For now, we'll create a simple encouraging message

    const messages = [
      {
        type: 'encouragement',
        subject: 'Your Progress Today',
        content: 'Every small step counts. How are you feeling about your journey today?'
      },
      {
        type: 'prompt',
        subject: 'Daily Reflection',
        content: 'What\'s one thing you\'re grateful for in this moment? Take a moment to reflect on the positive aspects of your day.'
      },
      {
        type: 'insight',
        subject: 'Mindful Moment',
        content: 'Remember: healing isn\'t linear. It\'s okay to have ups and downs. What matters is that you keep showing up for yourself.'
      }
    ];

    const randomMessage = messages[Math.floor(Math.random() * messages.length)];

    const queryText = `
      INSERT INTO inbox_messages (
        user_id, message_type, subject, content, metadata
      )
      VALUES ($1, $2, $3, $4, $5)
      RETURNING
        id,
        user_id as "userId",
        message_type as "messageType",
        subject,
        content,
        metadata,
        is_read as "isRead",
        is_archived as "isArchived",
        read_at as "readAt",
        archived_at as "archivedAt",
        created_at as "createdAt"
    `;

    const result = await query(queryText, [
      userId,
      randomMessage.type,
      randomMessage.subject,
      randomMessage.content,
      JSON.stringify({ auto_generated: true })
    ]);

    const row = result.rows[0];
    return {
      id: row.id,
      userId: row.userId,
      messageType: row.messageType,
      subject: row.subject,
      content: row.content,
      metadata: row.metadata,
      isRead: row.isRead,
      isArchived: row.isArchived,
      readAt: row.readAt,
      archivedAt: row.archivedAt,
      createdAt: row.createdAt,
      timestamp: this.formatTimestamp(row.createdAt)
    };
  }

  private formatTimestamp(date: Date): string {
    const now = new Date();
    const diffMs = now.getTime() - new Date(date).getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60) {
      return `${diffMins}m ago`;
    } else if (diffHours < 24) {
      return `${diffHours}h ago`;
    } else if (diffDays < 7) {
      return `${diffDays}d ago`;
    } else {
      return `${Math.floor(diffDays / 7)}w ago`;
    }
  }
}

export const inboxService = new InboxService();

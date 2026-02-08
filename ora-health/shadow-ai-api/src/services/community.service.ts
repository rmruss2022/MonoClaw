import { query } from '../config/database';

export interface CommunityPost {
  id: string;
  userId: string;
  author: {
    name: string;
    avatar: string;
    isAnonymous: boolean;
  };
  type: 'progress' | 'prompt' | 'resource' | 'support' | 'gratitude';
  category: string;
  content: string;
  promptText?: string;
  tags: string[];
  likes: number;
  comments: number;
  timestamp: string;
  isLiked?: boolean;
  createdAt: Date;
}

export interface PostCategory {
  id: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  displayOrder: number;
}

export interface PostComment {
  id: string;
  postId: string;
  userId: string;
  author: {
    name: string;
    avatar: string;
    isAnonymous: boolean;
  };
  content: string;
  timestamp: string;
  createdAt: Date;
}

export class CommunityService {
  async getPosts(userId: string, limit = 20, offset = 0, category?: string): Promise<CommunityPost[]> {
    // Build WHERE clause for category filter
    const whereClause = category ? 'WHERE cp.category = $4' : '';
    const params = category ? [userId, limit, offset, category] : [userId, limit, offset];

    const queryText = `
      SELECT
        cp.id,
        cp.user_id as "userId",
        cp.author_name as "authorName",
        cp.author_avatar as "authorAvatar",
        cp.is_anonymous as "isAnonymous",
        cp.type,
        cp.category,
        cp.content,
        cp.prompt_text as "promptText",
        cp.tags,
        cp.likes_count as "likesCount",
        cp.comments_count as "commentsCount",
        cp.created_at as "createdAt",
        EXISTS(
          SELECT 1 FROM post_likes pl
          WHERE pl.post_id = cp.id AND pl.user_id = $1
        ) as "isLiked"
      FROM community_posts cp
      ${whereClause}
      ORDER BY cp.created_at DESC
      LIMIT $2 OFFSET $3
    `;

    const result = await query(queryText, params);

    return result.rows.map(row => ({
      id: row.id,
      userId: row.userId,
      author: {
        name: row.isAnonymous ? 'Anonymous' : row.authorName,
        avatar: row.authorAvatar,
        isAnonymous: row.isAnonymous
      },
      type: row.type,
      category: row.category,
      content: row.content,
      promptText: row.promptText,
      tags: row.tags || [],
      likes: row.likesCount,
      comments: row.commentsCount,
      timestamp: this.formatTimestamp(row.createdAt),
      isLiked: row.isLiked,
      createdAt: row.createdAt
    }));
  }

  async getCategories(): Promise<PostCategory[]> {
    const queryText = `
      SELECT
        id,
        name,
        description,
        icon,
        color,
        display_order as "displayOrder"
      FROM post_categories
      ORDER BY display_order ASC
    `;

    const result = await query(queryText, []);

    return result.rows.map(row => ({
      id: row.id,
      name: row.name,
      description: row.description,
      icon: row.icon,
      color: row.color,
      displayOrder: row.displayOrder
    }));
  }

  async createPost(
    userId: string,
    data: {
      type: string;
      category: string;
      content: string;
      promptText?: string;
      tags?: string[];
      isAnonymous?: boolean;
      authorName?: string;
      authorAvatar?: string;
    }
  ): Promise<CommunityPost> {
    const queryText = `
      INSERT INTO community_posts (
        user_id, type, category, content, prompt_text, tags,
        is_anonymous, author_name, author_avatar
      )
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
      RETURNING
        id, user_id as "userId", type, category, content,
        prompt_text as "promptText", tags,
        is_anonymous as "isAnonymous",
        author_name as "authorName",
        author_avatar as "authorAvatar",
        likes_count as "likesCount",
        comments_count as "commentsCount",
        created_at as "createdAt"
    `;

    const result = await query(queryText, [
      userId,
      data.type,
      data.category,
      data.content,
      data.promptText || null,
      data.tags || [],
      data.isAnonymous || false,
      data.authorName || 'User',
      data.authorAvatar || '👤'
    ]);

    const row = result.rows[0];
    return {
      id: row.id,
      userId: row.userId,
      author: {
        name: row.isAnonymous ? 'Anonymous' : row.authorName,
        avatar: row.authorAvatar,
        isAnonymous: row.isAnonymous
      },
      type: row.type,
      category: row.category,
      content: row.content,
      promptText: row.promptText,
      tags: row.tags || [],
      likes: row.likesCount,
      comments: row.commentsCount,
      timestamp: this.formatTimestamp(row.createdAt),
      createdAt: row.createdAt
    };
  }

  async likePost(postId: string, userId: string): Promise<{ liked: boolean; likesCount: number }> {
    // Check if already liked
    const checkQuery = `
      SELECT id FROM post_likes
      WHERE post_id = $1 AND user_id = $2
    `;
    const checkResult = await query(checkQuery, [postId, userId]);

    if (checkResult.rows.length > 0) {
      // Unlike
      await query(
        'DELETE FROM post_likes WHERE post_id = $1 AND user_id = $2',
        [postId, userId]
      );
      await query(
        'UPDATE community_posts SET likes_count = likes_count - 1 WHERE id = $1',
        [postId]
      );

      const countResult = await query(
        'SELECT likes_count FROM community_posts WHERE id = $1',
        [postId]
      );

      return {
        liked: false,
        likesCount: countResult.rows[0].likes_count
      };
    } else {
      // Like
      await query(
        'INSERT INTO post_likes (post_id, user_id) VALUES ($1, $2)',
        [postId, userId]
      );
      await query(
        'UPDATE community_posts SET likes_count = likes_count + 1 WHERE id = $1',
        [postId]
      );

      const countResult = await query(
        'SELECT likes_count FROM community_posts WHERE id = $1',
        [postId]
      );

      return {
        liked: true,
        likesCount: countResult.rows[0].likes_count
      };
    }
  }

  async getComments(postId: string, limit = 50): Promise<PostComment[]> {
    const queryText = `
      SELECT
        id, post_id as "postId", user_id as "userId",
        author_name as "authorName", author_avatar as "authorAvatar",
        is_anonymous as "isAnonymous", content, created_at as "createdAt"
      FROM post_comments
      WHERE post_id = $1
      ORDER BY created_at ASC
      LIMIT $2
    `;

    const result = await query(queryText, [postId, limit]);

    return result.rows.map(row => ({
      id: row.id,
      postId: row.postId,
      userId: row.userId,
      author: {
        name: row.isAnonymous ? 'Anonymous' : row.authorName,
        avatar: row.authorAvatar,
        isAnonymous: row.isAnonymous
      },
      content: row.content,
      timestamp: this.formatTimestamp(row.createdAt),
      createdAt: row.createdAt
    }));
  }

  async addComment(
    postId: string,
    userId: string,
    content: string,
    isAnonymous = false,
    authorName = 'User',
    authorAvatar = '👤'
  ): Promise<PostComment> {
    const queryText = `
      INSERT INTO post_comments (
        post_id, user_id, content, is_anonymous, author_name, author_avatar
      )
      VALUES ($1, $2, $3, $4, $5, $6)
      RETURNING
        id, post_id as "postId", user_id as "userId",
        author_name as "authorName", author_avatar as "authorAvatar",
        is_anonymous as "isAnonymous", content, created_at as "createdAt"
    `;

    const result = await query(queryText, [
      postId, userId, content, isAnonymous, authorName, authorAvatar
    ]);

    // Increment comment count
    await query(
      'UPDATE community_posts SET comments_count = comments_count + 1 WHERE id = $1',
      [postId]
    );

    const row = result.rows[0];
    return {
      id: row.id,
      postId: row.postId,
      userId: row.userId,
      author: {
        name: row.isAnonymous ? 'Anonymous' : row.authorName,
        avatar: row.authorAvatar,
        isAnonymous: row.isAnonymous
      },
      content: row.content,
      timestamp: this.formatTimestamp(row.createdAt),
      createdAt: row.createdAt
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

export const communityService = new CommunityService();

import { Router } from 'express';
import { communityService } from '../services/community.service';

const router = Router();

// Get categories
router.get('/categories', async (req, res) => {
  try {
    const categories = await communityService.getCategories();
    res.json({ categories });
  } catch (error) {
    console.error('Error fetching categories:', error);
    res.status(500).json({ error: 'Failed to fetch categories' });
  }
});

// Get community posts
router.get('/posts', async (req, res) => {
  try {
    const userId = req.query.userId as string || 'default-user';
    const limit = parseInt(req.query.limit as string) || 20;
    const offset = parseInt(req.query.offset as string) || 0;
    const category = req.query.category as string | undefined;

    const posts = await communityService.getPosts(userId, limit, offset, category);
    res.json({ posts });
  } catch (error) {
    console.error('Error fetching posts:', error);
    res.status(500).json({ error: 'Failed to fetch posts' });
  }
});

// Create new post
router.post('/posts', async (req, res) => {
  try {
    const userId = req.body.userId || 'default-user';
    const { type, category, content, promptText, tags, isAnonymous, authorName, authorAvatar } = req.body;

    if (!type || !category || !content) {
      return res.status(400).json({ error: 'Type, category, and content are required' });
    }

    const post = await communityService.createPost(userId, {
      type,
      category,
      content,
      promptText,
      tags,
      isAnonymous,
      authorName,
      authorAvatar
    });

    res.status(201).json({ post });
  } catch (error) {
    console.error('Error creating post:', error);
    res.status(500).json({ error: 'Failed to create post' });
  }
});

// Like/unlike post
router.post('/posts/:postId/like', async (req, res) => {
  try {
    const { postId } = req.params;
    const userId = req.body.userId || 'default-user';

    const result = await communityService.likePost(postId, userId);
    res.json(result);
  } catch (error) {
    console.error('Error liking post:', error);
    res.status(500).json({ error: 'Failed to like post' });
  }
});

// Get post comments
router.get('/posts/:postId/comments', async (req, res) => {
  try {
    const { postId } = req.params;
    const limit = parseInt(req.query.limit as string) || 50;

    const comments = await communityService.getComments(postId, limit);
    res.json({ comments });
  } catch (error) {
    console.error('Error fetching comments:', error);
    res.status(500).json({ error: 'Failed to fetch comments' });
  }
});

// Add comment to post
router.post('/posts/:postId/comments', async (req, res) => {
  try {
    const { postId } = req.params;
    const userId = req.body.userId || 'default-user';
    const { content, isAnonymous, authorName, authorAvatar } = req.body;

    if (!content) {
      return res.status(400).json({ error: 'Content is required' });
    }

    const comment = await communityService.addComment(
      postId,
      userId,
      content,
      isAnonymous,
      authorName,
      authorAvatar
    );

    res.status(201).json({ comment });
  } catch (error) {
    console.error('Error adding comment:', error);
    res.status(500).json({ error: 'Failed to add comment' });
  }
});

export default router;

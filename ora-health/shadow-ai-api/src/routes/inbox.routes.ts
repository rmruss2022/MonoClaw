import { Router } from 'express';
import { inboxService } from '../services/inbox.service';

const router = Router();

// Get inbox messages
router.get('/messages', async (req, res) => {
  try {
    const userId = req.query.userId as string || 'default-user';
    const unreadOnly = req.query.unreadOnly === 'true';
    const limit = parseInt(req.query.limit as string) || 20;
    const offset = parseInt(req.query.offset as string) || 0;

    const result = await inboxService.getMessages(userId, {
      unreadOnly,
      limit,
      offset
    });

    res.json(result);
  } catch (error) {
    console.error('Error fetching inbox messages:', error);
    res.status(500).json({ error: 'Failed to fetch messages' });
  }
});

// Mark message as read
router.post('/messages/:messageId/read', async (req, res) => {
  try {
    const { messageId } = req.params;
    const userId = req.body.userId || 'default-user';

    await inboxService.markAsRead(messageId, userId);
    res.json({ success: true });
  } catch (error) {
    console.error('Error marking message as read:', error);
    res.status(500).json({ error: 'Failed to mark message as read' });
  }
});

// Archive message
router.post('/messages/:messageId/archive', async (req, res) => {
  try {
    const { messageId } = req.params;
    const userId = req.body.userId || 'default-user';

    await inboxService.archiveMessage(messageId, userId);
    res.json({ success: true });
  } catch (error) {
    console.error('Error archiving message:', error);
    res.status(500).json({ error: 'Failed to archive message' });
  }
});

// Respond to message
router.post('/messages/:messageId/respond', async (req, res) => {
  try {
    const { messageId } = req.params;
    const userId = req.body.userId || 'default-user';
    const { responseText, createPost, isAnonymous, authorName, authorAvatar } = req.body;

    if (!responseText) {
      return res.status(400).json({ error: 'Response text is required' });
    }

    const result = await inboxService.respondToMessage(
      messageId,
      userId,
      responseText,
      createPost || false,
      isAnonymous || false,
      authorName || 'User',
      authorAvatar || '👤'
    );

    res.json(result);
  } catch (error) {
    console.error('Error responding to message:', error);
    res.status(500).json({ error: 'Failed to respond to message' });
  }
});

// Get unread count
router.get('/unread-count', async (req, res) => {
  try {
    const userId = req.query.userId as string || 'default-user';

    const count = await inboxService.getUnreadCount(userId);
    res.json({ count });
  } catch (error) {
    console.error('Error getting unread count:', error);
    res.status(500).json({ error: 'Failed to get unread count' });
  }
});

// Generate daily message (for testing/admin use)
router.post('/generate-daily', async (req, res) => {
  try {
    const userId = req.body.userId || 'default-user';

    const message = await inboxService.generateDailyMessage(userId);
    res.json({ message });
  } catch (error) {
    console.error('Error generating daily message:', error);
    res.status(500).json({ error: 'Failed to generate daily message' });
  }
});

export default router;

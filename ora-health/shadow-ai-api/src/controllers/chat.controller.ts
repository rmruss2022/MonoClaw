import { Response } from 'express';
import { AuthRequest } from '../middleware/auth';
import { aiService } from '../services/ai.service';
import { postgresService } from '../services/postgres.service';

class ChatController {
  async sendMessage(req: AuthRequest, res: Response) {
    try {
      const { content, behaviorId } = req.body;
      const userId = req.userId!;

      if (!content || !behaviorId) {
        return res.status(400).json({ error: 'Content and behaviorId required' });
      }

      const response = await aiService.sendMessage(userId, content, behaviorId);

      res.json(response);
    } catch (error) {
      console.error('SendMessage Error:', error);
      res.status(500).json({ error: 'Failed to send message' });
    }
  }

  async getChatHistory(req: AuthRequest, res: Response) {
    try {
      const userId = req.userId!;
      const limit = parseInt(req.query.limit as string) || 50;

      const history = await postgresService.getChatHistory(userId, limit);

      res.json(history);
    } catch (error) {
      console.error('GetChatHistory Error:', error);
      res.status(500).json({ error: 'Failed to get chat history' });
    }
  }

  async switchBehavior(req: AuthRequest, res: Response) {
    try {
      const { behaviorId } = req.body;
      const userId = req.userId!;

      if (!behaviorId) {
        return res.status(400).json({ error: 'behaviorId required' });
      }

      // For now, just return success - behavior switching will be handled by AI
      // In the future, we can track this in user preferences
      res.json({ success: true });
    } catch (error) {
      console.error('SwitchBehavior Error:', error);
      res.status(500).json({ error: 'Failed to switch behavior' });
    }
  }

  async getCurrentBehavior(req: AuthRequest, res: Response) {
    try {
      // For now, always return free-form-chat as the default
      // In the agentic system, behavior is determined dynamically
      res.json({ behaviorId: 'free-form-chat' });
    } catch (error) {
      console.error('GetCurrentBehavior Error:', error);
      res.status(500).json({ error: 'Failed to get current behavior' });
    }
  }
}

export const chatController = new ChatController();

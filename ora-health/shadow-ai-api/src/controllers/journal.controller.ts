import { Response } from 'express';
import { AuthRequest } from '../middleware/auth';
import { randomUUID } from 'crypto';
import { dbService } from '../services/dynamodb.service';

class JournalController {
  async createEntry(req: AuthRequest, res: Response) {
    try {
      const userId = req.userId!;
      const { content, behaviorId, mood, tags, isShared } = req.body;

      if (!content || !behaviorId) {
        return res.status(400).json({ error: 'Content and behaviorId required' });
      }

      const entry = {
        id: randomUUID(),
        userId,
        content,
        behaviorId,
        mood,
        tags: tags || [],
        isShared: isShared || false,
      };

      await dbService.createJournalEntry(entry);

      res.status(201).json(entry);
    } catch (error) {
      console.error('CreateEntry Error:', error);
      res.status(500).json({ error: 'Failed to create entry' });
    }
  }

  async getEntries(req: AuthRequest, res: Response) {
    try {
      const userId = req.userId!;
      const limit = parseInt(req.query.limit as string) || 50;

      const entries = await dbService.getJournalEntries(userId, limit);

      res.json(entries);
    } catch (error) {
      console.error('GetEntries Error:', error);
      res.status(500).json({ error: 'Failed to get entries' });
    }
  }

  async getEntry(req: AuthRequest, res: Response) {
    try {
      const userId = req.userId!;
      const entryId = req.params.entryId as string;

      const entry = await dbService.getJournalEntry(userId, entryId);

      if (!entry) {
        return res.status(404).json({ error: 'Entry not found' });
      }

      res.json(entry);
    } catch (error) {
      console.error('GetEntry Error:', error);
      res.status(500).json({ error: 'Failed to get entry' });
    }
  }

  async updateEntry(req: AuthRequest, res: Response) {
    try {
      // Implement update logic
      res.status(501).json({ error: 'Not implemented' });
    } catch (error) {
      console.error('UpdateEntry Error:', error);
      res.status(500).json({ error: 'Failed to update entry' });
    }
  }

  async deleteEntry(req: AuthRequest, res: Response) {
    try {
      const userId = req.userId!;
      const entryId = req.params.entryId as string;

      await dbService.deleteJournalEntry(userId, entryId);

      res.json({ success: true });
    } catch (error) {
      console.error('DeleteEntry Error:', error);
      res.status(500).json({ error: 'Failed to delete entry' });
    }
  }
}

export const journalController = new JournalController();

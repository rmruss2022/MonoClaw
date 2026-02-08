import { Router } from 'express';
import { meditationService } from '../services/meditation.service';

const router = Router();

// Get all meditations
router.get('/', async (req, res) => {
  try {
    const meditations = await meditationService.getAllMeditations();
    res.json({ meditations });
  } catch (error) {
    console.error('Error fetching meditations:', error);
    res.status(500).json({ error: 'Failed to fetch meditations' });
  }
});

// Get meditations by category
router.get('/category/:category', async (req, res) => {
  try {
    const { category } = req.params;
    const meditations = await meditationService.getMeditationsByCategory(category);
    res.json({ meditations });
  } catch (error) {
    console.error('Error fetching meditations by category:', error);
    res.status(500).json({ error: 'Failed to fetch meditations' });
  }
});

// Get specific meditation
router.get('/:id', async (req, res) => {
  try {
    const { id } = req.params;
    const meditation = await meditationService.getMeditationById(id);

    if (!meditation) {
      return res.status(404).json({ error: 'Meditation not found' });
    }

    res.json({ meditation });
  } catch (error) {
    console.error('Error fetching meditation:', error);
    res.status(500).json({ error: 'Failed to fetch meditation' });
  }
});

// Start meditation session
router.post('/:id/start', async (req, res) => {
  try {
    const { id } = req.params;
    const userId = req.body.userId || 'default-user';

    const session = await meditationService.startSession(userId, id);
    res.json({ session });
  } catch (error) {
    console.error('Error starting session:', error);
    res.status(500).json({ error: 'Failed to start session' });
  }
});

// Complete meditation session
router.post('/sessions/:sessionId/complete', async (req, res) => {
  try {
    const { sessionId } = req.params;
    const { durationCompleted } = req.body;

    const session = await meditationService.completeSession(
      sessionId,
      durationCompleted
    );

    res.json({ session });
  } catch (error) {
    console.error('Error completing session:', error);
    res.status(500).json({ error: 'Failed to complete session' });
  }
});

// Get user meditation history
router.get('/sessions/user/:userId', async (req, res) => {
  try {
    const { userId } = req.params;
    const limit = parseInt(req.query.limit as string) || 10;

    const sessions = await meditationService.getUserSessions(userId, limit);
    res.json({ sessions });
  } catch (error) {
    console.error('Error fetching user sessions:', error);
    res.status(500).json({ error: 'Failed to fetch sessions' });
  }
});

// Get user meditation stats
router.get('/stats/user/:userId', async (req, res) => {
  try {
    const { userId } = req.params;
    const stats = await meditationService.getUserStats(userId);
    res.json({ stats });
  } catch (error) {
    console.error('Error fetching user stats:', error);
    res.status(500).json({ error: 'Failed to fetch stats' });
  }
});

export default router;

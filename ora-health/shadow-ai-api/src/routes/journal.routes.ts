import { Router } from 'express';
import { journalController } from '../controllers/journal.controller';
import { authenticateToken } from '../middleware/auth';

const router = Router();

router.use(authenticateToken);

router.post('/entries', journalController.createEntry);
router.get('/entries', journalController.getEntries);
router.get('/entries/:entryId', journalController.getEntry);
router.put('/entries/:entryId', journalController.updateEntry);
router.delete('/entries/:entryId', journalController.deleteEntry);

export default router;

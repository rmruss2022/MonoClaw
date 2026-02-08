import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';

import { authRoutes } from './routes/auth';
import { healthRoutes } from './routes/health';
import { metricsRoutes } from './routes/metrics';
import { aiRoutes } from './routes/ai';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors({
  origin: process.env.CORS_ORIGIN || 'http://localhost:19000',
  credentials: true
}));
app.use(express.json());

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Routes
app.use('/auth', authRoutes);
app.use('/health', healthRoutes);
app.use('/metrics', metricsRoutes);
app.use('/ai', aiRoutes);

// Error handling
app.use((err: Error, req: express.Request, res: express.Response, next: express.NextFunction) => {
  console.error(err.stack);
  res.status(500).json({ error: 'Something went wrong!' });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({ error: 'Not found' });
});

app.listen(PORT, () => {
  console.log(`🦞 Ora Health API running on port ${PORT}`);
});

export default app;

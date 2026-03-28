require('dotenv').config({ path: '../../.env' });

const express = require('express');
const cors = require('cors');
const multer = require('multer');
const path = require('path');
const db = require('./db');
const paRoutes = require('./routes/pa');
const dashboardRoutes = require('./routes/dashboard');
const payerRoutes = require('./routes/payers');
const { startPoller } = require('./jobs/statusPoller');

const app = express();
const PORT = process.env.PORT || 3011;

// Middleware
app.use(cors());
app.use(express.json({ limit: '10mb' }));

// File upload config
const upload = multer({
  dest: path.join(__dirname, '../uploads/'),
  limits: { fileSize: 20 * 1024 * 1024 }, // 20MB
  fileFilter: (req, file, cb) => {
    if (file.mimetype === 'application/pdf' || file.mimetype === 'text/plain') {
      cb(null, true);
    } else {
      cb(new Error('Only PDF and text files are allowed'));
    }
  },
});

// Make upload middleware available to routes
app.locals.upload = upload;

// Health check
app.get('/api/health', async (req, res) => {
  try {
    await db.query('SELECT 1');
    res.json({ status: 'ok', timestamp: new Date().toISOString(), db: 'connected' });
  } catch (err) {
    if (process.env.DEMO_MODE === 'true') {
      res.json({ status: 'ok', timestamp: new Date().toISOString(), db: 'unavailable (demo mode)' });
    } else {
      res.status(500).json({ status: 'error', message: 'Database connection failed' });
    }
  }
});

// Routes
app.use('/api/pa', paRoutes);
app.use('/api/dashboard', dashboardRoutes);
app.use('/api/payers', payerRoutes);

// Demo mode config
app.get('/api/config', (req, res) => {
  res.json({ demoMode: process.env.DEMO_MODE === 'true' });
});

// Practices list
app.get('/api/practices', async (req, res) => {
  try {
    const { rows } = await db.query('SELECT * FROM practices ORDER BY name');
    res.json(rows);
  } catch (err) {
    console.error('Error fetching practices:', err);
    res.status(500).json({ error: 'Failed to fetch practices' });
  }
});

// Error handler
app.use((err, req, res, next) => {
  console.error('Unhandled error:', err);
  res.status(500).json({ error: err.message || 'Internal server error' });
});

app.listen(PORT, () => {
  console.log(`AuthAgent API running on port ${PORT}`);
  console.log(`Demo mode: ${process.env.DEMO_MODE === 'true' ? 'ON' : 'OFF'}`);
  // Start background status polling job
  startPoller();
});

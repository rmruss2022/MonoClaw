const express = require('express');
const fs = require('fs');
const path = require('path');
const { randomUUID } = require('crypto');

const app = express();
const PORT = 3030;
const DB_FILE = path.join(__dirname, '../data.json');

app.use(express.json());
app.use(express.static(path.join(__dirname, '../public')));

// ── Data layer (flat JSON file) ──────────────────────────
function loadDB() {
  if (!fs.existsSync(DB_FILE)) {
    const initial = { items: [], tags: ['work', 'health', 'personal', 'finance', 'learning', 'relationships', 'side-project', 'home'] };
    fs.writeFileSync(DB_FILE, JSON.stringify(initial, null, 2));
    return initial;
  }
  return JSON.parse(fs.readFileSync(DB_FILE, 'utf8'));
}

function saveDB(db) {
  fs.writeFileSync(DB_FILE, JSON.stringify(db, null, 2));
}

// ── Routes ───────────────────────────────────────────────

// GET all items (with optional filters)
app.get('/api/items', (req, res) => {
  const db = loadDB();
  let items = db.items;
  const { list, status, tag } = req.query;
  if (list)   items = items.filter(i => i.list === list);
  if (status) items = items.filter(i => i.status === status);
  if (tag)    items = items.filter(i => i.tags?.includes(tag));
  // Sort: by priority desc, then createdAt asc
  items = items.sort((a, b) => (b.priority || 0) - (a.priority || 0) || new Date(a.createdAt) - new Date(b.createdAt));
  res.json({ items, tags: db.tags });
});

// POST create item
app.post('/api/items', (req, res) => {
  const db = loadDB();
  const { title, notes, list, status, tags, priority, dueDate } = req.body;
  if (!title) return res.status(400).json({ error: 'title required' });
  const item = {
    id: randomUUID(),
    title,
    notes: notes || '',
    list: list || 'active',          // active | backlog | cache
    status: status || 'todo',        // todo | in-progress | completed | blocked
    tags: tags || [],
    priority: priority || 0,         // 0=normal, 1=high, 2=urgent
    dueDate: dueDate || null,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    completedAt: null,
  };
  db.items.push(item);
  saveDB(db);
  res.status(201).json(item);
});

// PATCH update item
app.patch('/api/items/:id', (req, res) => {
  const db = loadDB();
  const idx = db.items.findIndex(i => i.id === req.params.id);
  if (idx === -1) return res.status(404).json({ error: 'not found' });
  const updates = req.body;
  if (updates.status === 'completed' && db.items[idx].status !== 'completed') {
    updates.completedAt = new Date().toISOString();
  }
  db.items[idx] = { ...db.items[idx], ...updates, updatedAt: new Date().toISOString() };
  saveDB(db);
  res.json(db.items[idx]);
});

// DELETE item
app.delete('/api/items/:id', (req, res) => {
  const db = loadDB();
  const idx = db.items.findIndex(i => i.id === req.params.id);
  if (idx === -1) return res.status(404).json({ error: 'not found' });
  db.items.splice(idx, 1);
  saveDB(db);
  res.json({ ok: true });
});

// POST add custom tag
app.post('/api/tags', (req, res) => {
  const db = loadDB();
  const { tag } = req.body;
  if (!tag) return res.status(400).json({ error: 'tag required' });
  if (!db.tags.includes(tag)) { db.tags.push(tag); saveDB(db); }
  res.json({ tags: db.tags });
});

// GET stats
app.get('/api/stats', (req, res) => {
  const db = loadDB();
  const stats = {
    total: db.items.length,
    byList: { active: 0, backlog: 0, cache: 0 },
    byStatus: { todo: 0, 'in-progress': 0, completed: 0, blocked: 0 },
    completedToday: 0,
  };
  const today = new Date().toDateString();
  db.items.forEach(i => {
    stats.byList[i.list] = (stats.byList[i.list] || 0) + 1;
    stats.byStatus[i.status] = (stats.byStatus[i.status] || 0) + 1;
    if (i.completedAt && new Date(i.completedAt).toDateString() === today) stats.completedToday++;
  });
  res.json(stats);
});

app.listen(PORT, () => console.log(`TodoService running at http://localhost:${PORT}`));

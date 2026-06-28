const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const initSqlJs = require('sql.js');

const app = express();
const PORT = process.env.PORT || 18810;
const DB_PATH = path.join(__dirname, 'circle.db');

app.use(cors());
app.use(express.json());
app.use(express.static(__dirname));

let db;

async function initDb() {
  const SQL = await initSqlJs();

  if (fs.existsSync(DB_PATH)) {
    const fileBuffer = fs.readFileSync(DB_PATH);
    db = new SQL.Database(fileBuffer);
  } else {
    db = new SQL.Database();
  }

  db.run(`
    CREATE TABLE IF NOT EXISTS people (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      contact TEXT,
      vibe TEXT,
      the_play TEXT,
      tags TEXT,
      met_at TEXT,
      met_datetime TEXT,
      created_at TEXT DEFAULT (datetime('now')),
      updated_at TEXT DEFAULT (datetime('now'))
    );
  `);

  // Seed if empty
  const result = db.exec("SELECT COUNT(*) as c FROM people");
  const count = result[0]?.values[0][0] || 0;
  if (count === 0) {
    db.run(`INSERT INTO people (name, contact, vibe, the_play, tags, met_at, met_datetime) VALUES (?,?,?,?,?,?,?)`, [
      'Dani Reyes',
      '@dani.reyes.dj',
      'DJ and vinyl collector. Does monthly residencies at a Bushwick warehouse called The Lot. Has a gift for reading rooms — goes from ambient to jungle without anyone noticing the shift.',
      "She's plugged into the underground venue network. Intro could unlock spaces for future events — she mentioned she's always looking for artists who bring energy, not just logos.",
      'dj, music, bushwick, events',
      'The Lot, Friday night',
      '2026-04-18T22:00'
    ]);
    db.run(`INSERT INTO people (name, contact, vibe, the_play, tags, met_at, met_datetime) VALUES (?,?,?,?,?,?,?)`, [
      'Marcus Webb',
      'marcus.webb@proton.me',
      'Photographer and zine maker. Shoots film almost exclusively — black and white street stuff plus editorial. Published three zines, sells them at the Williamsburg flea on Sundays.',
      'Wants to document the next event series from the inside. Bring him in as the embedded photographer — his aesthetic would fit perfectly and he builds community around the work.',
      'photographer, film, zines, visual',
      'Williamsburg Flea, Sunday',
      '2026-04-13T11:00'
    ]);
    db.run(`INSERT INTO people (name, contact, vibe, the_play, tags, met_at, met_datetime) VALUES (?,?,?,?,?,?,?)`, [
      'Jade Okonkwo',
      '+1 347 555 0182',
      'Ceramic artist and community organizer. Runs a studio space in Greenpoint that doubles as a gathering spot. Deeply connected to the art-activism crossover scene, shows up for everything.',
      "The studio space is the move — she's open to co-programming. Could be a venue for intimate events or pop-ups. She's also building a collective and looking for collaborators who aren't just about clout.",
      'artist, ceramics, community, greenpoint, activist',
      'Greenpoint open studios',
      '2026-04-12T15:30'
    ]);
    saveDb();
  }
}

function saveDb() {
  const data = db.export();
  fs.writeFileSync(DB_PATH, Buffer.from(data));
}

// Helper: rows from db.exec
function queryAll(sql, params) {
  const result = db.exec(sql, params);
  if (!result.length) return [];
  const cols = result[0].columns;
  return result[0].values.map(row => {
    const obj = {};
    cols.forEach((c, i) => obj[c] = row[i]);
    return obj;
  });
}

function queryOne(sql, params) {
  const rows = queryAll(sql, params);
  return rows[0] || null;
}

// GET /api/people
app.get('/api/people', (req, res) => {
  const people = queryAll('SELECT * FROM people ORDER BY created_at DESC');
  res.json(people);
});

// GET /api/people/search
app.get('/api/people/search', (req, res) => {
  const q = `%${req.query.q || ''}%`;
  const people = queryAll(
    `SELECT * FROM people WHERE name LIKE $q OR vibe LIKE $q OR tags LIKE $q OR met_at LIKE $q OR the_play LIKE $q ORDER BY created_at DESC`,
    { $q: q }
  );
  res.json(people);
});

// POST /api/people
app.post('/api/people', (req, res) => {
  const { name, contact, vibe, the_play, tags, met_at, met_datetime } = req.body;
  if (!name) return res.status(400).json({ error: 'Name is required' });
  db.run(
    `INSERT INTO people (name, contact, vibe, the_play, tags, met_at, met_datetime) VALUES (?,?,?,?,?,?,?)`,
    [name, contact || null, vibe || null, the_play || null, tags || null, met_at || null, met_datetime || null]
  );
  saveDb();
  const person = queryOne('SELECT * FROM people ORDER BY id DESC LIMIT 1');
  res.status(201).json(person);
});

// PUT /api/people/:id
app.put('/api/people/:id', (req, res) => {
  const { name, contact, vibe, the_play, tags, met_at, met_datetime } = req.body;
  db.run(
    `UPDATE people SET name=?, contact=?, vibe=?, the_play=?, tags=?, met_at=?, met_datetime=?, updated_at=datetime('now') WHERE id=?`,
    [name, contact || null, vibe || null, the_play || null, tags || null, met_at || null, req.params.id]
  );
  saveDb();
  const person = queryOne('SELECT * FROM people WHERE id=?', [req.params.id]);
  if (!person) return res.status(404).json({ error: 'Not found' });
  res.json(person);
});

// DELETE /api/people/:id
app.delete('/api/people/:id', (req, res) => {
  db.run('DELETE FROM people WHERE id=?', [req.params.id]);
  saveDb();
  res.json({ ok: true });
});

initDb().then(() => {
  app.listen(PORT, () => {
    console.log(`The Circle running on http://localhost:${PORT}`);
  });
}).catch(err => {
  console.error('DB init failed:', err);
  process.exit(1);
});

const sqlite3 = require('sqlite3').verbose();
const path = require('path');

const DB_PATH = path.join(__dirname, '..', 'raves.db');

let db = null;

function getDb() {
  if (!db) {
    db = new sqlite3.Database(DB_PATH);
    
    // Create tables
    db.run(`
      CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        venue TEXT,
        date TEXT,
        time TEXT,
        genres TEXT,
        artists TEXT,
        url TEXT,
        source TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);
    
    db.run(`
      CREATE TABLE IF NOT EXISTS event_views (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER,
        viewed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (event_id) REFERENCES events(id)
      )
    `);
    
    db.run(`
      CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);
      CREATE INDEX IF NOT EXISTS idx_events_genres ON events(genres);
    `);
  }
  
  return db;
}

function insertEvent(event, callback) {
  const db = getDb();
  db.run(`
    INSERT INTO events (name, venue, date, time, genres, artists, url, source)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `, [
    event.name,
    event.venue,
    event.date,
    event.time,
    JSON.stringify(event.genres || []),
    JSON.stringify(event.artists || []),
    event.url,
    event.source || 'manual'
  ], function(err) {
    if (callback) callback(err, this.lastID);
  });
}

function getRecentEvents(limit = 50, callback) {
  const db = getDb();
  db.all(`
    SELECT 
      id,
      name,
      venue,
      date,
      time,
      genres,
      artists,
      url,
      source,
      created_at
    FROM events
    ORDER BY date DESC, created_at DESC
    LIMIT ?
  `, [limit], (err, rows) => {
    if (err) {
      callback(err, []);
      return;
    }
    
    // Parse JSON fields
    const events = rows.map(row => ({
      ...row,
      genres: JSON.parse(row.genres || '[]'),
      artists: JSON.parse(row.artists || '[]')
    }));
    
    callback(null, events);
  });
}

function searchEvents(query, callback) {
  const db = getDb();
  const searchTerm = `%${query}%`;
  
  db.all(`
    SELECT *
    FROM events
    WHERE name LIKE ? OR venue LIKE ? OR genres LIKE ? OR artists LIKE ?
    ORDER BY date DESC
    LIMIT 50
  `, [searchTerm, searchTerm, searchTerm, searchTerm], callback);
}

function logEventView(eventId, callback) {
  const db = getDb();
  db.run('INSERT INTO event_views (event_id) VALUES (?)', [eventId], callback);
}

module.exports = {
  getDb,
  insertEvent,
  getRecentEvents,
  searchEvents,
  logEventView
};

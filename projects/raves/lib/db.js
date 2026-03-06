const Database = require('better-sqlite3');
const path = require('path');

const dbPath = path.join(__dirname, '..', 'events.db');
const db = new Database(dbPath);

// Create events table
db.exec(`
  CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    venue TEXT NOT NULL,
    date TEXT NOT NULL,
    dayOfWeek TEXT NOT NULL,
    genres TEXT NOT NULL,
    description TEXT NOT NULL,
    topPick INTEGER DEFAULT 0,
    week_start TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
  );

  CREATE INDEX IF NOT EXISTS idx_date ON events(date);
  CREATE INDEX IF NOT EXISTS idx_week_start ON events(week_start);
  CREATE INDEX IF NOT EXISTS idx_venue ON events(venue);
`);

// Helper: Get Monday of the week for a given date
function getWeekStart(dateString) {
  const date = new Date(dateString);
  const day = date.getDay();
  const diff = date.getDate() - day + (day === 0 ? -6 : 1); // Adjust when day is Sunday
  const monday = new Date(date.setDate(diff));
  return monday.toISOString().split('T')[0];
}

// Insert or update event
function upsertEvent(event) {
  const weekStart = getWeekStart(event.date);
  const stmt = db.prepare(`
    INSERT INTO events (id, name, venue, date, dayOfWeek, genres, description, topPick, week_start)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
      name = excluded.name,
      venue = excluded.venue,
      date = excluded.date,
      dayOfWeek = excluded.dayOfWeek,
      genres = excluded.genres,
      description = excluded.description,
      topPick = excluded.topPick,
      week_start = excluded.week_start
  `);
  
  stmt.run(
    event.id,
    event.name,
    event.venue,
    event.date,
    event.dayOfWeek,
    JSON.stringify(event.genres),
    event.description,
    event.topPick ? 1 : 0,
    weekStart
  );
}

// Get all events
function getAllEvents() {
  const stmt = db.prepare('SELECT * FROM events ORDER BY date ASC, name ASC');
  const rows = stmt.all();
  return rows.map(row => ({
    ...row,
    genres: JSON.parse(row.genres),
    topPick: row.topPick === 1
  }));
}

// Get events by week
function getEventsByWeek(weekStart) {
  const stmt = db.prepare('SELECT * FROM events WHERE week_start = ? ORDER BY date ASC, name ASC');
  const rows = stmt.all(weekStart);
  return rows.map(row => ({
    ...row,
    genres: JSON.parse(row.genres),
    topPick: row.topPick === 1
  }));
}

// Get all weeks
function getAllWeeks() {
  const stmt = db.prepare('SELECT DISTINCT week_start FROM events ORDER BY week_start DESC');
  return stmt.all().map(row => row.week_start);
}

// Get events grouped by week
function getEventsGroupedByWeek() {
  const weeks = getAllWeeks();
  return weeks.map(weekStart => ({
    weekStart,
    events: getEventsByWeek(weekStart)
  }));
}

module.exports = {
  db,
  getWeekStart,
  upsertEvent,
  getAllEvents,
  getEventsByWeek,
  getAllWeeks,
  getEventsGroupedByWeek
};

const Database = require('better-sqlite3');
const path = require('path');
const crypto = require('crypto');

const dbPath = process.env.DB_PATH || path.join(__dirname, '..', 'events.db');
const db = new Database(dbPath);

// Migrations first (add columns if missing on existing tables)
const colsToAdd = [
  { name: 'interest', def: 'TEXT DEFAULT NULL' },
  { name: 'notes', def: "TEXT DEFAULT ''" },
  { name: 'attended', def: 'INTEGER DEFAULT 0' },
  { name: 'vibe_tags', def: "TEXT DEFAULT '[]'" },
  { name: 'cost', def: 'REAL DEFAULT 0' },
  { name: 'is_festival', def: 'INTEGER DEFAULT 0' },
  { name: 'festival_end_date', def: 'TEXT DEFAULT NULL' },
  { name: 'location_city', def: 'TEXT DEFAULT NULL' },
  { name: 'created_at', def: "TEXT DEFAULT CURRENT_TIMESTAMP" },
  { name: 'updated_at', def: "TEXT DEFAULT CURRENT_TIMESTAMP" }
];
// Ensure table exists first
db.exec(`
  CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    venue TEXT NOT NULL,
    date TEXT NOT NULL,
    dayOfWeek TEXT NOT NULL,
    genres TEXT NOT NULL,
    description TEXT,
    topPick INTEGER DEFAULT 0,
    week_start TEXT NOT NULL,
    interest TEXT DEFAULT NULL,
    notes TEXT DEFAULT '',
    attended INTEGER DEFAULT 0,
    vibe_tags TEXT DEFAULT '[]',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
  );
`);
const existingCols = db.prepare("PRAGMA table_info(events)").all().map(c => c.name);
for (const c of colsToAdd) {
  if (!existingCols.includes(c.name)) {
    try {
      db.exec(`ALTER TABLE events ADD COLUMN ${c.name} ${c.def}`);
      console.log(`[db] Added column ${c.name}`);
    } catch (e) {
      console.error(`[db] Failed to add column ${c.name}:`, e.message);
    }
  }
}

// Now safe to create indexes (columns definitely exist)
db.exec(`
  CREATE INDEX IF NOT EXISTS idx_date ON events(date);
  CREATE INDEX IF NOT EXISTS idx_week_start ON events(week_start);
  CREATE INDEX IF NOT EXISTS idx_venue ON events(venue);
  CREATE INDEX IF NOT EXISTS idx_interest ON events(interest);
  CREATE INDEX IF NOT EXISTS idx_attended ON events(attended);
`);

// Budget config table
db.exec(`
  CREATE TABLE IF NOT EXISTS budget_config (
    id INTEGER PRIMARY KEY,
    monthly_limit REAL DEFAULT 400,
    default_ticket_price REAL DEFAULT 35
  );
`);

// Perks table - tier-based perks at Brooklyn venues
db.exec(`
  CREATE TABLE IF NOT EXISTS perks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venue TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    tier_required TEXT NOT NULL,
    code TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
  );
`);

// Users table
db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_login_at TEXT
  );
`);

// Sessions table for token-based auth
db.exec(`
  CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
  );
`);

// Scan history - global shared across all users
db.exec(`
  CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    scanned_at TEXT DEFAULT CURRENT_TIMESTAMP,
    sources TEXT NOT NULL,
    total INTEGER DEFAULT 0,
    new_count INTEGER DEFAULT 0,
    added_count INTEGER DEFAULT 0,
    results_json TEXT
  );
`);
// Migrate: drop user_id NOT NULL constraint if old schema (recreate table)
try {
  const cols = db.prepare("PRAGMA table_info(scans)").all();
  const userIdCol = cols.find(c => c.name === 'user_id');
  if (userIdCol && userIdCol.notnull === 1) {
    db.exec(`
      CREATE TABLE IF NOT EXISTS scans_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        scanned_at TEXT DEFAULT CURRENT_TIMESTAMP,
        sources TEXT NOT NULL,
        total INTEGER DEFAULT 0,
        new_count INTEGER DEFAULT 0,
        added_count INTEGER DEFAULT 0,
        results_json TEXT
      );
      INSERT INTO scans_new SELECT id, user_id, scanned_at, sources, total, new_count, added_count, results_json FROM scans;
      DROP TABLE scans;
      ALTER TABLE scans_new RENAME TO scans;
    `);
    console.log('[db] Migrated scans table to global (removed user_id NOT NULL)');
  }
} catch (e) {
  console.error('[db] Scan migration error:', e.message);
}

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
    INSERT INTO events (id, name, venue, date, dayOfWeek, genres, description, topPick, week_start, interest, notes, attended, vibe_tags, cost)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
      name = excluded.name,
      venue = excluded.venue,
      date = excluded.date,
      dayOfWeek = excluded.dayOfWeek,
      genres = excluded.genres,
      description = excluded.description,
      topPick = excluded.topPick,
      week_start = excluded.week_start,
      interest = excluded.interest,
      notes = excluded.notes,
      attended = excluded.attended,
      vibe_tags = excluded.vibe_tags,
      cost = excluded.cost,
      updated_at = CURRENT_TIMESTAMP
  `);

  stmt.run(
    event.id,
    event.name,
    event.venue,
    event.date,
    event.dayOfWeek,
    JSON.stringify(event.genres || []),
    event.description,
    event.topPick ? 1 : 0,
    weekStart,
    event.interest || null,
    event.notes || '',
    event.attended ? 1 : 0,
    JSON.stringify(event.vibe_tags || []),
    event.cost || 0
  );
}

// Update event fields (PATCH)
function updateEvent(id, patch) {
  const fields = [];
  const values = [];
  const allowed = ['name', 'venue', 'date', 'dayOfWeek', 'genres', 'description', 'topPick', 'interest', 'notes', 'attended', 'vibe_tags', 'cost', 'is_festival', 'festival_end_date', 'location_city'];
  for (const key of Object.keys(patch)) {
    if (!allowed.includes(key)) continue;
    let val = patch[key];
    if (key === 'genres' || key === 'vibe_tags') val = JSON.stringify(val || []);
    else if (key === 'topPick' || key === 'attended' || key === 'is_festival') val = val ? 1 : 0;
    else if (key === 'cost') val = Number(val) || 0;
    fields.push(`${key} = ?`);
    values.push(val);
  }
  if (fields.length === 0) return null;
  // Auto-update week_start when date changes
  if (patch.date) {
    fields.push('week_start = ?');
    values.push(getWeekStart(patch.date));
  }
  fields.push('updated_at = CURRENT_TIMESTAMP');
  values.push(id);
  const stmt = db.prepare(`UPDATE events SET ${fields.join(', ')} WHERE id = ?`);
  stmt.run(...values);
  return getEventById(id);
}

function deleteEvent(id) {
  const ev = getEventById(id);
  if (!ev) return null;
  db.prepare('DELETE FROM events WHERE id = ?').run(id);
  return ev;
}

function getEventById(id) {
  const row = db.prepare('SELECT * FROM events WHERE id = ?').get(id);
  if (!row) return null;
  return rowToEvent(row);
}

function rowToEvent(row) {
  return {
    ...row,
    genres: JSON.parse(row.genres || '[]'),
    vibe_tags: JSON.parse(row.vibe_tags || '[]'),
    topPick: row.topPick === 1,
    attended: row.attended === 1,
    cost: row.cost || 0,
    isFestival: row.is_festival === 1,
    festivalEndDate: row.festival_end_date || null,
    locationCity: row.location_city || null
  };
}

// Get all events
function getAllEvents() {
  const stmt = db.prepare('SELECT * FROM events ORDER BY date ASC, name ASC');
  const rows = stmt.all();
  return rows.map(rowToEvent);
}

// Get events by week
function getEventsByWeek(weekStart) {
  const stmt = db.prepare('SELECT * FROM events WHERE week_start = ? ORDER BY date ASC, name ASC');
  const rows = stmt.all(weekStart);
  return rows.map(rowToEvent);
}

// Get all week start dates
function getAllWeeks() {
  const stmt = db.prepare('SELECT DISTINCT week_start FROM events ORDER BY week_start ASC');
  return stmt.all().map(r => r.week_start);
}

// Get events grouped by week
function getEventsGroupedByWeek() {
  const events = getAllEvents();
  const grouped = {};
  for (const event of events) {
    const week = getWeekStart(event.date);
    if (!grouped[week]) grouped[week] = [];
    grouped[week].push(event);
  }
  return grouped;
}

// Stats
function getStats() {
  const today = new Date().toISOString().slice(0, 10);
  const going = db.prepare("SELECT COUNT(*) as c FROM events WHERE interest = 'going' AND date >= ? AND attended = 0").get(today).c;
  const maybe = db.prepare("SELECT COUNT(*) as c FROM events WHERE interest = 'maybe' AND date >= ?").get(today).c;
  const attended = db.prepare("SELECT COUNT(*) as c FROM events WHERE attended = 1").get().c;
  const upcoming = db.prepare("SELECT COUNT(*) as c FROM events WHERE date >= ?").get(today).c;
  // Total committed spend (going, not yet attended)
  const committed = db.prepare("SELECT COALESCE(SUM(cost),0) as t FROM events WHERE interest = 'going' AND attended = 0 AND date >= ?").get(today).t;
  // Total spent (attended)
  const spent = db.prepare("SELECT COALESCE(SUM(cost),0) as t FROM events WHERE attended = 1").get().t;
  return { going, maybe, attended, upcoming, committed, spent };
}

// ===================== BUDGET =====================

function getBudgetConfig() {
  let row = db.prepare("SELECT * FROM budget_config WHERE id = 1").get();
  if (!row) {
    db.prepare("INSERT INTO budget_config (id, monthly_limit, default_ticket_price) VALUES (1, 400, 35)").run();
    row = db.prepare("SELECT * FROM budget_config WHERE id = 1").get();
  }
  return row;
}

function setBudgetConfig(patch) {
  const allowed = ['monthly_limit', 'default_ticket_price'];
  const fields = [];
  const values = [];
  for (const k of allowed) {
    if (patch[k] !== undefined) {
      fields.push(`${k} = ?`);
      values.push(patch[k]);
    }
  }
  if (fields.length === 0) return getBudgetConfig();
  values.push(1);
  db.prepare(`UPDATE budget_config SET ${fields.join(', ')} WHERE id = ?`).run(...values);
  return getBudgetConfig();
}

function setEventCost(eventId, cost) {
  db.prepare("UPDATE events SET cost = ? WHERE id = ?").run(cost, eventId);
  return getEventById(eventId);
}

function getBudgetSummary() {
  const cfg = getBudgetConfig();
  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();
  const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59).toISOString();

  const today = now.toISOString().slice(0, 10);

  // Upcoming shows you've committed to (Going, not yet attended, future date)
  const upcoming = db.prepare(`
    SELECT id, name, venue, date, cost, genres, interest
    FROM events
    WHERE date >= ? AND interest = 'going' AND attended = 0
    ORDER BY date ASC
  `).all(today);

  // All going/attended events this month (for the month breakdown list)
  const thisMonthGoing = db.prepare(`
    SELECT id, name, venue, date, cost, genres, interest, attended
    FROM events
    WHERE date >= ? AND date <= ? AND (interest = 'going' OR attended = 1)
    ORDER BY date ASC
  `).all(monthStart, monthEnd);

  // SPENT = shows you actually attended (attended = 1)
  const thisMonthSpent = db.prepare(`
    SELECT COALESCE(SUM(cost), 0) as total
    FROM events
    WHERE attended = 1 AND date >= ? AND date <= ?
  `).get(monthStart, monthEnd).total;

  // COMMITTED = future Going shows (interest = going, attended = 0, date >= today)
  const thisMonthCommitted = db.prepare(`
    SELECT COALESCE(SUM(cost), 0) as total
    FROM events
    WHERE interest = 'going' AND attended = 0 AND date >= ? AND date <= ?
  `).get(today, monthEnd).total;

  // Spend by venue — any event with cost > 0 (attended, going, or just priced)
  const byVenue = db.prepare(`
    SELECT venue, COUNT(*) as count, COALESCE(SUM(cost), 0) as total,
      SUM(CASE WHEN attended = 1 THEN 1 ELSE 0 END) as attended_count
    FROM events
    WHERE cost > 0
    GROUP BY venue
    ORDER BY total DESC
    LIMIT 10
  `).all();

  // Spend by genre — any event with cost > 0
  const byGenreRaw = db.prepare(`
    SELECT genres, cost FROM events WHERE cost > 0
  `).all();
  const byGenre = {};
  for (const row of byGenreRaw) {
    try {
      const gs = JSON.parse(row.genres || '[]')
      const share = (row.cost || 0) / Math.max(gs.length, 1)
      for (const g of gs) {
        byGenre[g] = (byGenre[g] || 0) + share
      }
    } catch {}
  }
  const byGenreArr = Object.entries(byGenre).map(([name, total]) => ({ name, total }))
    .sort((a, b) => b.total - a.total).slice(0, 10)

  return {
    config: cfg,
    thisMonth: {
      spent: thisMonthSpent,
      committed: thisMonthCommitted,
      projected: thisMonthSpent + thisMonthCommitted,
      events: thisMonthGoing
    },
    byVenue,
    byGenre: byGenreArr,
    upcoming: upcoming.slice(0, 20)
  };
}

// ===================== PERKS =====================

function getPerks() {
  return db.prepare("SELECT * FROM perks ORDER BY tier_required ASC, sort_order ASC").all();
}

function getPerksByTier(tier) {
  const tierOrder = ['rookie', 'regular', 'headliner', 'legend', 'icon'];
  const tierIdx = tierOrder.indexOf(tier);
  if (tierIdx < 0) return [];
  const allowed = tierOrder.slice(0, tierIdx + 1);
  const placeholders = allowed.map(() => '?').join(',');
  return db.prepare(`SELECT * FROM perks WHERE tier_required IN (${placeholders}) ORDER BY tier_required ASC, sort_order ASC`).all(...allowed);
}

function getRaveCard() {
  const attended = db.prepare("SELECT COUNT(*) as c, MIN(date) as first, MAX(date) as last FROM events WHERE attended = 1").get();
  const going = db.prepare("SELECT COUNT(*) as c FROM events WHERE interest = 'going' AND date >= ?").get(new Date().toISOString()).c;
  const maybe = db.prepare("SELECT COUNT(*) as c FROM events WHERE interest = 'maybe' AND date >= ?").get(new Date().toISOString()).c;
  const totalSpent = db.prepare("SELECT COALESCE(SUM(cost), 0) as total FROM events WHERE attended = 1").get().total;

  // Calculate tier
  const tiers = [
    { name: 'rookie', min: 0, max: 4, color: '#888', emoji: '🌱', label: 'ROOKIE' },
    { name: 'regular', min: 5, max: 14, color: '#00aaff', emoji: '⚡', label: 'REGULAR' },
    { name: 'headliner', min: 15, max: 29, color: '#ff2d92', emoji: '🔥', label: 'HEADLINER' },
    { name: 'legend', min: 30, max: 59, color: '#a855f7', emoji: '👑', label: 'LEGEND' },
    { name: 'icon', min: 60, max: 9999, color: '#fff700', emoji: '🪩', label: 'ICON' }
  ];
  const count = attended.c || 0;
  const tier = tiers.find(t => count >= t.min && count <= t.max) || tiers[0];
  const nextTier = tiers[tiers.indexOf(tier) + 1];

  // Venue diversity (unique venues attended)
  const venues = db.prepare("SELECT DISTINCT venue FROM events WHERE attended = 1").all().map(r => r.venue);

  return {
    attended: count,
    going,
    maybe,
    totalSpent,
    tier: tier.name,
    tierLabel: tier.label,
    tierEmoji: tier.emoji,
    tierColor: tier.color,
    nextTier: nextTier ? { name: nextTier.name, label: nextTier.label, remaining: nextTier.min - count } : null,
    firstShow: attended.first,
    lastShow: attended.last,
    venueCount: venues.length,
    venues
  };
}

function getSocialFeed() {
  // "Where people are going next" — pseudo-social: shows other Going for the next 7 days
  // In real life, this would query other users' Going lists. For now, use a heuristic
  // showing what's popular this week.
  const now = new Date();
  const weekEnd = new Date(now);
  weekEnd.setDate(weekEnd.getDate() + 7);

  const upcoming = db.prepare(`
    SELECT id, name, venue, date, genres, cost, topPick
    FROM events
    WHERE date >= ? AND date <= ?
    ORDER BY date ASC
  `).all(now.toISOString(), weekEnd.toISOString());

  // Score by "popularity" (topPick gets bonus, genre diversity bonus)
  const events = upcoming.map(e => {
    let popularity = 0;
    if (e.topPick) popularity += 3;
    try {
      const gs = JSON.parse(e.genres || '[]')
      popularity += Math.min(gs.length, 2)
    } catch {}
    return { ...e, genres: e.genres ? JSON.parse(e.genres) : [], popularity }
  });

  return {
    thisWeek: events.sort((a, b) => b.popularity - a.popularity).slice(0, 10)
  };
}

// ===================== PUSH SUBSCRIPTIONS =====================
db.exec(`
  CREATE TABLE IF NOT EXISTS push_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    endpoint TEXT NOT NULL UNIQUE,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
  );
  CREATE INDEX IF NOT EXISTS idx_push_user ON push_subscriptions(user_id);
`);

// ===================== SCHEDULER RUNS =====================
db.exec(`
  CREATE TABLE IF NOT EXISTS scheduler_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT NOT NULL,
    ran_at TEXT DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL,
    details TEXT
  );
  CREATE INDEX IF NOT EXISTS idx_scheduler_job ON scheduler_runs(job_name);
  CREATE INDEX IF NOT EXISTS idx_scheduler_ran_at ON scheduler_runs(ran_at);
`);

function recordSchedulerRun(jobName, status, details) {
  const r = db.prepare(`INSERT INTO scheduler_runs (job_name, status, details) VALUES (?, ?, ?)`)
    .run(jobName, status, details || '');
  return r.lastInsertRowid;
}

function getSchedulerRuns(limit = 50) {
  return db.prepare(`SELECT id, job_name, ran_at, status, details FROM scheduler_runs ORDER BY ran_at DESC, id DESC LIMIT ?`).all(limit);
}

function getSchedulerLatestByJob(jobName) {
  return db.prepare(`SELECT id, job_name, ran_at, status, details FROM scheduler_runs WHERE job_name = ? ORDER BY ran_at DESC, id DESC LIMIT 1`).get(jobName);
}

function getSchedulerJobCounts() {
  return db.prepare(`
    SELECT job_name,
      COUNT(*) as total,
      SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as successes,
      SUM(CASE WHEN status='failed'  THEN 1 ELSE 0 END) as failures,
      SUM(CASE WHEN status='skipped' THEN 1 ELSE 0 END) as skipped
    FROM scheduler_runs GROUP BY job_name
  `).all();
}

function getPushSubscriptionCount() {
  return db.prepare(`SELECT COUNT(*) as c FROM push_subscriptions`).get().c;
}

function getUserCount() {
  return db.prepare(`SELECT COUNT(*) as c FROM users`).get().c;
}

function savePushSubscription(userId, sub) {
  db.prepare(`
    INSERT OR REPLACE INTO push_subscriptions (user_id, endpoint, p256dh, auth)
    VALUES (?, ?, ?, ?)
  `).run(userId, sub.endpoint, sub.keys.p256dh, sub.keys.auth);
}

function deletePushSubscription(endpoint) {
  db.prepare('DELETE FROM push_subscriptions WHERE endpoint = ?').run(endpoint);
}

function getPushSubscriptionsByUser(userId) {
  return db.prepare('SELECT * FROM push_subscriptions WHERE user_id = ?').all(userId);
}

function getAllPushSubscriptions() {
  return db.prepare('SELECT * FROM push_subscriptions').all();
}

function getGoingShowsForDate(datePrefix) {
  return db.prepare(`
    SELECT * FROM events
    WHERE interest = 'going' AND date LIKE ? AND attended = 0
    ORDER BY date ASC
  `).all(datePrefix + '%').map(rowToEvent);
}

module.exports = {
  upsertEvent,
  updateEvent,
  deleteEvent,
  getEventById,
  getAllEvents,
  getEventsByWeek,
  getAllWeeks,
  getEventsGroupedByWeek,
  getStats,
  getBudgetConfig,
  setBudgetConfig,
  setEventCost,
  getBudgetSummary,
  getPerks,
  getPerksByTier,
  getRaveCard,
  getSocialFeed,
  createUser,
  getUserById,
  getUserByUsername,
  login,
  getSession,
  logout,
  saveScan,
  updateScanAddedCount,
  getScanHistory,
  getScanById,
  getLatestScan,
  deleteScan,
  getWeekStart,
  savePushSubscription,
  deletePushSubscription,
  getPushSubscriptionsByUser,
  getAllPushSubscriptions,
  getPushSubscriptionCount,
  getUserCount,
  getGoingShowsForDate,
  recordSchedulerRun,
  getSchedulerRuns,
  getSchedulerLatestByJob,
  getSchedulerJobCounts
};

// Ensure budget_config row exists
const existingConfig = db.prepare("SELECT id FROM budget_config WHERE id = 1").get();
if (!existingConfig) {
  db.prepare("INSERT INTO budget_config (id, monthly_limit, default_ticket_price) VALUES (1, 400, 35)").run();
}

// Seed perks if empty
const existingPerks = db.prepare("SELECT COUNT(*) as c FROM perks").get().c;
if (existingPerks === 0) {
  const insertPerk = db.prepare("INSERT INTO perks (venue, title, description, tier_required, code, sort_order) VALUES (?, ?, ?, ?, ?, ?)");
  const perks = [
    // Rookie tier
    ['House of Yes', 'Welcome shot at the bar', 'First-time guest gets a welcome shot. Show your Rave Card at the door.', 'rookie', 'HOY-WELCOME', 1],
    // Regular tier (5+ shows)
    ['Elsewhere', '$5 off the next Elsewhere Zone 1 show', 'Regulars save on their next main-room experience.', 'regular', 'ELS-R5OFF', 1],
    ['Basement', 'Free coat check', 'Show your card at the door for complimentary coat check.', 'regular', 'BSMT-COAT', 2],
    ['Market Hotel', 'Drink token ($8 value)', 'Get a drink on the house with any ticket purchase.', 'regular', 'MKH-DRINK', 3],
    // Headliner tier (15+ shows)
    ['Knockdown Center', 'Skip-the-line entry', 'Use the dedicated Headliner+ line — never wait in queue.', 'headliner', 'KD-SKIPLINE', 1],
    ['Mirage', 'Free upgrade to main stage', 'Get bumped from side stage to main stage when available.', 'headliner', 'MRG-UPGRADE', 2],
    ['Goodroom', '20% off cloak room', 'Discounted cloak every visit.', 'headliner', 'GR-CLOAK20', 3],
    // Legend tier (30+ shows)
    ['Avant Gardner', 'Guest list priority + free drink', 'Added to the guest list with 1 complimentary drink.', 'legend', 'AG-GLIST1', 1],
    ['Brooklyn Mirage', 'Reserved lounge access', 'Access the seasonal members-only lounges.', 'legend', 'BM-LOUNGE', 2],
    // Icon tier (60+ shows)
    ['Public Arts', 'Free entry to any Public Arts event', 'Just show your Icon card — comp entry for you +1.', 'icon', 'PA-FREE2', 1],
    ['Basement', 'Annual Basement membership ($150 value)', 'Free annual membership with full perks.', 'icon', 'BSMT-ANNUAL', 2]
  ];
  for (const p of perks) {
    insertPerk.run(...p);
  }
  console.log(`[db] Seeded ${perks.length} perks`);
}
// ===================== USERS / AUTH =====================

function hashPassword(password, salt) {
  if (!salt) salt = crypto.randomBytes(16).toString('hex')
  const hash = crypto.createHash('sha256').update(salt + password).digest('hex')
  return `${salt}:${hash}`
}

function verifyPassword(password, stored) {
  if (!stored || !stored.includes(':')) return false
  const [salt] = stored.split(':')
  return hashPassword(password, salt) === stored
}

function createUser(username, password, displayName) {
  if (!username || username.length < 2) throw new Error('Username must be at least 2 characters')
  if (!password || password.length < 4) throw new Error('Password must be at least 4 characters')

  const existing = db.prepare('SELECT id FROM users WHERE username = ?').get(username.toLowerCase())
  if (existing) throw new Error('Username already taken')

  const hash = hashPassword(password)
  const result = db.prepare(`
    INSERT INTO users (username, password_hash, display_name)
    VALUES (?, ?, ?)
  `).run(username.toLowerCase(), hash, displayName || username)

  return getUserById(result.lastInsertRowid)
}

function getUserById(id) {
  return db.prepare('SELECT id, username, display_name, created_at, last_login_at FROM users WHERE id = ?').get(id)
}

function getUserByUsername(username) {
  return db.prepare('SELECT id, username, display_name, password_hash, created_at, last_login_at FROM users WHERE username = ?').get(username.toLowerCase())
}

function login(username, password) {
  const user = getUserByUsername(username)
  if (!user) throw new Error('Invalid username or password')
  if (!verifyPassword(password, user.password_hash)) throw new Error('Invalid username or password')

  db.prepare('UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?').run(user.id)

  const token = crypto.randomBytes(32).toString('hex')
  const expires = new Date(Date.now() + 30 * 24 * 3600 * 1000).toISOString()
  db.prepare('INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)').run(token, user.id, expires)

  return { token, user: { id: user.id, username: user.username, displayName: user.display_name } }
}

function getSession(token) {
  if (!token) return null
  const session = db.prepare('SELECT * FROM sessions WHERE token = ? AND expires_at > ?').get(token, new Date().toISOString())
  if (!session) return null
  return getUserById(session.user_id)
}

function logout(token) {
  if (!token) return
  db.prepare('DELETE FROM sessions WHERE token = ?').run(token)
}

// Seed default user if none exists
const userCount = db.prepare('SELECT COUNT(*) as c FROM users').get().c
if (userCount === 0) {
  createUser('matthew', 'rave2026', 'Matthew')
  console.log('[db] Seeded default user: matthew / rave2026')
}

// ===================== SCAN HISTORY =====================

function saveScan(scanResult, userId) {
  const stmt = db.prepare(`
    INSERT INTO scans (user_id, sources, total, new_count, added_count, results_json)
    VALUES (?, ?, ?, ?, ?, ?)
  `)
  const result = stmt.run(
    userId || null,
    JSON.stringify(scanResult.sources || []),
    scanResult.total || 0,
    scanResult.new || 0,
    scanResult.added || 0,
    JSON.stringify(scanResult.results || [])
  )
  return result.lastInsertRowid
}

function updateScanAddedCount(scanId, addedCount) {
  db.prepare('UPDATE scans SET added_count = ? WHERE id = ?').run(addedCount, scanId)
}

// Global scan history — not filtered by user
function getScanHistory(limit = 20) {
  return db.prepare(`
    SELECT id, user_id, scanned_at, sources, total, new_count, added_count
    FROM scans
    ORDER BY scanned_at DESC
    LIMIT ?
  `).all(limit)
}

function getScanById(scanId) {
  const row = db.prepare(`
    SELECT id, user_id, scanned_at, sources, total, new_count, added_count, results_json
    FROM scans
    WHERE id = ?
  `).get(scanId)
  if (!row) return null
  return {
    ...row,
    sources: JSON.parse(row.sources || '[]'),
    results: JSON.parse(row.results_json || '[]')
  }
}

function getLatestScan() {
  const row = db.prepare(`
    SELECT id, user_id, scanned_at, sources, total, new_count, added_count, results_json
    FROM scans
    ORDER BY scanned_at DESC
    LIMIT 1
  `).get()
  if (!row) return null
  return {
    ...row,
    sources: JSON.parse(row.sources || '[]'),
    results: JSON.parse(row.results_json || '[]')
  }
}

function deleteScan(scanId) {
  db.prepare('DELETE FROM scans WHERE id = ?').run(scanId)
}

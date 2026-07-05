/**
 * Layer 1 recommendation engine — self-affinity scoring.
 *
 * Scores all upcoming events the user has NOT marked going/maybe/skip
 * against their attended history. Returns top 10 with reasons.
 */

const Database = require('better-sqlite3');
const path = require('path');

const dbPath = process.env.DB_PATH || path.join(__dirname, '..', 'events.db');
const db = new Database(dbPath);

// Track dismissed recommendations so they don't show up again
db.exec(`
  CREATE TABLE IF NOT EXISTS dismissed_recs (
    event_id TEXT PRIMARY KEY,
    dismissed_at TEXT DEFAULT CURRENT_TIMESTAMP
  );
`);

const WEIGHTS = {
  genre: 0.35,
  venue: 0.25,
  day: 0.15,
  price: 0.10,
  artist: 0.15
};

const REASON_LABELS = {
  genre: 'GENRE MATCH',
  venue: 'VENUE YOU LOVE',
  day: 'FITS YOUR SCHEDULE',
  price: 'RIGHT PRICE',
  artist: 'SIMILAR VIBE'
};

const STOPWORDS = new Set([
  'the','a','an','and','or','but','of','to','in','at','on','for','with',
  'by','from','as','is','are','was','were','be','been','it','its','this',
  'that','these','those','will','would','could','should','can','may','one',
  'two','new','your','our','their','his','her','they','we','you','us','i',
  'feat','featuring','presents','presenting','live','set','show','event',
  'night','party','b2b'
]);

function rowToEvent(row) {
  return {
    ...row,
    genres: safeJSON(row.genres, []),
    vibe_tags: safeJSON(row.vibe_tags, []),
    topPick: row.topPick === 1,
    attended: row.attended === 1,
    cost: row.cost || 0
  };
}

function safeJSON(s, fallback) {
  try { return JSON.parse(s || ''); } catch { return fallback; }
}

function tokenize(text) {
  if (!text) return [];
  return text.toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    .filter(w => w.length > 2 && !STOPWORDS.has(w));
}

function buildAffinityProfile(attended) {
  const profile = {
    totalAttended: attended.length,
    genreCounts: {},
    totalGenreMentions: 0,
    venueCounts: {},
    dayCounts: {},
    totalDays: 0,
    avgCost: 0,
    descriptionWords: new Set()
  };

  let costSum = 0;
  let costCount = 0;

  for (const ev of attended) {
    for (const g of ev.genres || []) {
      profile.genreCounts[g] = (profile.genreCounts[g] || 0) + 1;
      profile.totalGenreMentions++;
    }
    if (ev.venue) {
      profile.venueCounts[ev.venue] = (profile.venueCounts[ev.venue] || 0) + 1;
    }
    if (ev.dayOfWeek) {
      profile.dayCounts[ev.dayOfWeek] = (profile.dayCounts[ev.dayOfWeek] || 0) + 1;
      profile.totalDays++;
    }
    if (ev.cost > 0) {
      costSum += ev.cost;
      costCount++;
    }
    const combined = `${ev.name || ''} ${ev.description || ''}`;
    for (const w of tokenize(combined)) {
      profile.descriptionWords.add(w);
    }
  }

  profile.avgCost = costCount > 0 ? costSum / costCount : 0;
  return profile;
}

function scoreEvent(event, profile) {
  const signals = { genre: 0, venue: 0, day: 0, price: 0, artist: 0 };

  // Genre match (0–WEIGHTS.genre)
  if (profile.totalGenreMentions > 0 && (event.genres || []).length > 0) {
    let bestRatio = 0;
    for (const g of event.genres) {
      const cnt = profile.genreCounts[g] || 0;
      const ratio = cnt / profile.totalGenreMentions;
      if (ratio > bestRatio) bestRatio = ratio;
    }
    signals.genre = WEIGHTS.genre * bestRatio;
  }

  // Venue loyalty (0–WEIGHTS.venue) — scale by visit count, cap at 5+ visits
  if (event.venue) {
    const visits = profile.venueCounts[event.venue] || 0;
    if (visits >= 3) {
      const scale = Math.min(visits / 5, 1);
      signals.venue = WEIGHTS.venue * scale;
    } else if (visits > 0) {
      signals.venue = WEIGHTS.venue * (visits / 5);
    }
  }

  // Day preference (0–WEIGHTS.day)
  if (profile.totalDays > 0 && event.dayOfWeek) {
    const dayCnt = profile.dayCounts[event.dayOfWeek] || 0;
    const ratio = dayCnt / profile.totalDays;
    signals.day = WEIGHTS.day * ratio;
  }

  // Price fit (0–WEIGHTS.price)
  if (profile.avgCost > 0 && event.cost > 0) {
    const diff = Math.abs(event.cost - profile.avgCost);
    if (diff <= 15) {
      signals.price = WEIGHTS.price;
    } else if (diff <= 40) {
      // linear decay 15→40 → 1→0
      signals.price = WEIGHTS.price * (1 - (diff - 15) / 25);
    }
  } else if (profile.avgCost === 0 && event.cost === 0) {
    signals.price = WEIGHTS.price;
  }

  // Artist / description word overlap (0–WEIGHTS.artist)
  if (profile.descriptionWords.size > 0) {
    const evWords = new Set(tokenize(`${event.name || ''} ${event.description || ''}`));
    let overlap = 0;
    for (const w of evWords) {
      if (profile.descriptionWords.has(w)) overlap++;
    }
    if (evWords.size > 0) {
      const ratio = Math.min(overlap / 3, 1); // 3+ shared words = full
      signals.artist = WEIGHTS.artist * ratio;
    }
  }

  const total = signals.genre + signals.venue + signals.day + signals.price + signals.artist;

  // Top reason = highest non-zero signal
  let topKey = null;
  let topVal = 0;
  for (const k of Object.keys(signals)) {
    if (signals[k] > topVal) {
      topVal = signals[k];
      topKey = k;
    }
  }

  return {
    score: total,
    signals,
    reason: topKey ? REASON_LABELS[topKey] : null
  };
}

function getRecommendations(opts = {}) {
  const limit = opts.limit || 10;
  const today = new Date().toISOString().slice(0, 10);

  const attended = db.prepare(`
    SELECT * FROM events WHERE attended = 1 ORDER BY date DESC
  `).all().map(rowToEvent);

  // Candidates: future events with no interest set + not attended + not dismissed
  const candidates = db.prepare(`
    SELECT e.* FROM events e
    WHERE e.date >= ?
      AND e.attended = 0
      AND (e.interest IS NULL OR e.interest = '')
      AND e.id NOT IN (SELECT event_id FROM dismissed_recs)
    ORDER BY e.date ASC
  `).all(today).map(rowToEvent);

  let scored = [];

  if (attended.length > 0) {
    const profile = buildAffinityProfile(attended);
    scored = candidates.map(ev => {
      const r = scoreEvent(ev, profile);
      return { event: ev, ...r };
    }).filter(r => r.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, limit);
  }

  // Fallback: < 3 scored results — fill with topPick + recent additions
  if (scored.length < 3) {
    const usedIds = new Set(scored.map(r => r.event.id));
    const fallback = candidates.filter(c => !usedIds.has(c.id));

    const topPicks = fallback.filter(c => c.topPick);
    for (const ev of topPicks) {
      if (scored.length >= limit) break;
      scored.push({
        event: ev,
        score: 0,
        signals: { genre: 0, venue: 0, day: 0, price: 0, artist: 0 },
        reason: 'TOP PICK'
      });
      usedIds.add(ev.id);
    }

    if (scored.length < limit) {
      const recent = db.prepare(`
        SELECT e.* FROM events e
        WHERE e.date >= ?
          AND e.attended = 0
          AND (e.interest IS NULL OR e.interest = '')
          AND e.id NOT IN (SELECT event_id FROM dismissed_recs)
        ORDER BY e.created_at DESC
        LIMIT ?
      `).all(today, limit * 2).map(rowToEvent);

      for (const ev of recent) {
        if (scored.length >= limit) break;
        if (usedIds.has(ev.id)) continue;
        scored.push({
          event: ev,
          score: 0,
          signals: { genre: 0, venue: 0, day: 0, price: 0, artist: 0 },
          reason: 'JUST ADDED'
        });
        usedIds.add(ev.id);
      }
    }
  }

  return {
    items: scored,
    hasHistory: attended.length > 0,
    attendedCount: attended.length
  };
}

function dismissRecommendation(eventId) {
  db.prepare(`
    INSERT OR IGNORE INTO dismissed_recs (event_id) VALUES (?)
  `).run(eventId);
}

function getExploreEvents(opts = {}) {
  const today = new Date().toISOString().slice(0, 10);
  const page = Math.max(1, opts.page || 1);
  const limit = Math.min(opts.limit || 20, 100);
  const offset = (page - 1) * limit;

  const where = [`date >= ?`, `attended = 0`, `(interest IS NULL OR interest = '')`];
  const params = [today];

  if (opts.genre) {
    where.push(`genres LIKE ?`);
    params.push(`%"${opts.genre}"%`);
  }

  if (opts.venue) {
    where.push(`venue = ?`);
    params.push(opts.venue);
  }

  if (opts.maxPrice !== undefined && opts.maxPrice !== null) {
    if (opts.maxPrice === 0) {
      // FREE — cost = 0
      where.push(`cost = 0`);
    } else {
      where.push(`cost <= ?`);
      params.push(opts.maxPrice);
    }
  }

  if (opts.dateRange === 'week') {
    const end = new Date();
    end.setDate(end.getDate() + 7);
    where.push(`date <= ?`);
    params.push(end.toISOString().slice(0, 10));
  } else if (opts.dateRange === 'month') {
    const end = new Date();
    end.setDate(end.getDate() + 30);
    where.push(`date <= ?`);
    params.push(end.toISOString().slice(0, 10));
  }

  const whereClause = where.join(' AND ');

  const totalRow = db.prepare(`SELECT COUNT(*) as c FROM events WHERE ${whereClause}`).get(...params);
  const total = totalRow.c;

  const rows = db.prepare(`
    SELECT * FROM events WHERE ${whereClause}
    ORDER BY date ASC, name ASC
    LIMIT ? OFFSET ?
  `).all(...params, limit, offset).map(rowToEvent);

  // Distinct venues for filter dropdown
  const venues = db.prepare(`
    SELECT DISTINCT venue FROM events
    WHERE date >= ? AND venue != ''
    ORDER BY venue ASC
  `).all(today).map(r => r.venue);

  // Distinct genres
  const genreRows = db.prepare(`SELECT genres FROM events WHERE date >= ?`).all(today);
  const genreSet = new Set();
  for (const r of genreRows) {
    for (const g of safeJSON(r.genres, [])) {
      if (g) genreSet.add(g);
    }
  }

  return {
    events: rows,
    page,
    limit,
    total,
    hasMore: offset + rows.length < total,
    filters: {
      venues,
      genres: Array.from(genreSet).sort()
    }
  };
}

module.exports = {
  getRecommendations,
  dismissRecommendation,
  getExploreEvents
};

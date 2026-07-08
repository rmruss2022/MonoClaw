// Direct Dice scrape - no Firecrawl needed
const Database = require('better-sqlite3');
const path = require('path');

const dbPath = path.join(__dirname, '..', 'events.db');
const db = new Database(dbPath);

const TODAY = new Date().toISOString().slice(0, 10);

const SOURCES = [
  { name: 'Dice · NYC', url: 'https://dice.fm/browse/new_york-5bbf4db0f06331478e9b2c59', type: 'dice' },
  { name: 'Dice · NYC DJ', url: 'https://dice.fm/browse/new_york-5bbf4db0f06331478e9b2c59/music/dj', type: 'dice' }
];

const VENUE_PATTERNS = [
  { match: /houseofyes|house-of-yes|onyx-room/i, venue: 'House of Yes' },
  { match: /elsewhere-the-hall|elsewhere-brooklyn|elsewhere-/i, venue: 'Elsewhere' },
  { match: /basementny|basement-/i, venue: 'Basement' },
  { match: /market-hotel|markethotel/i, venue: 'Market Hotel' },
  { match: /knockdown|ruins-at-knockdown/i, venue: 'Knockdown Center' },
  { match: /brooklynsteel|bowerypresents/i, venue: 'Brooklyn Steel' },
  { match: /brooklyn-mirage|brooklyn-mirage|the-mirage/i, venue: 'Brooklyn Mirage' },
  { match: /goodroom/i, venue: 'Goodroom' },
  { match: /outputclub/i, venue: 'Output' },
  { match: /avantgardner/i, venue: 'Avant Gardner' },
  { match: /public-records/i, venue: 'Public Records' },
  { match: /baby-s-all-right|babysallright/i, venue: "Baby's All Right" },
  { match: /k-bridge|kbridge/i, venue: 'Under The K Bridge' },
  { match: /brooklyn-army-terminal/i, venue: 'Brooklyn Army Terminal' },
  { match: /brooklyn-storehouse/i, venue: 'Brooklyn Storehouse' },
  { match: /superior-ingredients/i, venue: 'Superior Ingredients' },
  { match: /paradise-coney/i, venue: 'Paradise Coney Island' },
  { match: /public-arts|publicarts/i, venue: 'Public Arts' }
];

const GENRES = [
  'House', 'Techno', 'Trance', 'Drum & Bass', 'DnB', 'Jungle', 'Breakbeat', 'Breaks',
  'Disco', 'Tech House', 'Deep House', 'Acid', 'Hardcore', 'UK Garage', 'Garage',
  'Dubstep', 'Bass', 'Ambient', 'Experimental', 'Industrial', 'Afro House', 'Latin House',
  'Psytrance', 'Minimal', 'Microhouse', 'Electro', 'Hip-Hop', 'Rap', 'Drill', 'Trap',
  'Hard Techno', 'Afrobeats', 'Reggaeton', 'Live PA'
];

async function fetchHtml(url) {
  const r = await fetch(url, {
    headers: { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' },
    redirect: 'follow'
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.text();
}

function extractDiceEvents(html) {
  // Dice uses href like /event/<id>-<slug>-<venue>-tickets
  const events = new Map();
  const re = /href="\/event\/([a-z0-9]+)-([^"]+)"/g;
  let m;
  while ((m = re.exec(html))) {
    const id = m[1];
    if (!events.has(id)) {
      // Parse slug to extract info: name-DAY_MONTH-VENUE-tickets
      const slug = m[2];
      events.set(id, { id, slug });
    }
  }
  return Array.from(events.values());
}

function parseDiceSlug(slug) {
  // Format: name-with-dashes-15th-jul-public-records-new-york-tickets
  // or: name-15th-jul-2026-public-records-new-york-tickets
  const parts = slug.split('-');
  
  // Find date pattern (15th-jul, 23rd-aug, etc.)
  const dayMonth = parts.findIndex(p => /^\d{1,2}(st|nd|rd|th)$/.test(p));
  let dateStr = null;
  let nameEndIdx = dayMonth;
  
  if (dayMonth > 0 && dayMonth + 1 < parts.length) {
    const day = parseInt(parts[dayMonth]);
    const monthStr = parts[dayMonth + 1].toLowerCase();
    const months = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };
    const month = months[monthStr.slice(0, 3)];
    if (month) {
      // Look for year
      let year = 2026;
      if (dayMonth + 2 < parts.length && /^20\d{2}$/.test(parts[dayMonth + 2])) {
        year = parseInt(parts[dayMonth + 2]);
      }
      dateStr = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    }
  }
  
  // Venue = parts between date and "new-york" or "tickets"
  let venue = '';
  let venueEndIdx = parts.length;
  for (let i = dayMonth + 2; i < parts.length; i++) {
    if (parts[i] === 'tickets' || parts[i] === 'new' && parts[i+1] === 'york') {
      venueEndIdx = i;
      break;
    }
  }
  if (dayMonth + 2 < venueEndIdx) {
    venue = parts.slice(dayMonth + 2, venueEndIdx)
      .filter(p => p !== 'tickets' && !(p === 'new' && parts[parts.indexOf(p)+1] === 'york'))
      .join(' ');
    // Try to match known venue patterns
    for (const p of VENUE_PATTERNS) {
      if (p.match.test(slug) || p.match.test(venue)) {
        venue = p.venue;
        break;
      }
    }
    if (!venue) venue = venue.split('-').map(w => w[0]?.toUpperCase() + w.slice(1)).join(' ');
  }
  
  // Name = first part before the date
  const name = parts.slice(0, dayMonth)
    .map(w => w[0]?.toUpperCase() + w.slice(1))
    .join(' ');
  
  return { name, date: dateStr, venue };
}

function upsertEvent(ev) {
  if (!ev.name || !ev.date) return null;
  const slug = ev.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const vslug = (ev.venue || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const id = `${ev.date}-${slug}-${vslug}`;
  
  const d = new Date(ev.date + 'T12:00:00');
  const dow = d.getDay();
  const monday = new Date(d);
  monday.setDate(d.getDate() - ((dow + 6) % 7));
  const week_start = monday.toISOString().slice(0, 10);
  const dayOfWeek = d.toLocaleDateString('en-US', { weekday: 'long' });
  
  // Detect genres from name + venue
  const text = (ev.name + ' ' + ev.venue).toLowerCase();
  const genres = [];
  for (const g of GENRES) {
    if (new RegExp(`\\b${g.toLowerCase()}\\b`).test(text) && !genres.includes(g)) {
      genres.push(g);
    }
  }
  
  db.prepare(`
    INSERT INTO events (id, name, venue, date, dayOfWeek, genres, description, week_start, topPick, cost)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
      name = excluded.name,
      venue = excluded.venue,
      genres = excluded.genres,
      updated_at = CURRENT_TIMESTAMP
  `).run(id, ev.name, ev.venue || '', ev.date, dayOfWeek, JSON.stringify(genres), ev.description || '', week_start, 0, ev.cost || 0);
  
  return id;
}

async function main() {
  console.log('Scanning Dice NYC for July 2026 events...\n');
  const allEvents = new Map();
  
  for (const source of SOURCES) {
    try {
      console.log(`Scraping ${source.name}...`);
      const html = await fetchHtml(source.url);
      const events = extractDiceEvents(html);
      console.log(`  Found ${events.length} event links`);
      for (const e of events) allEvents.set(e.id, e);
    } catch (e) {
      console.log(`  ERROR: ${e.message}`);
    }
  }
  
  console.log(`\n${allEvents.size} unique events. Parsing slugs for July 2026...\n`);
  
  const julyEvents = [];
  for (const e of allEvents.values()) {
    const parsed = parseDiceSlug(e.slug);
    if (parsed.date && parsed.date >= '2026-07-01' && parsed.date <= '2026-07-31') {
      julyEvents.push({ ...parsed, url: `https://dice.fm/event/${e.id}-${e.slug}` });
    }
  }
  
  // Sort by date
  julyEvents.sort((a, b) => a.date.localeCompare(b.date));
  
  console.log(`Found ${julyEvents.length} July events:\n`);
  
  let saved = 0;
  for (const ev of julyEvents) {
    try {
      const id = upsertEvent(ev);
      if (id) {
        saved++;
        console.log(`✓ ${ev.date} | ${ev.venue.padEnd(25)} | ${ev.name}`);
      }
    } catch (e) {
      console.log(`✗ Failed: ${ev.name} - ${e.message}`);
    }
  }
  
  console.log(`\n✓ Saved ${saved} July events to local DB`);
  console.log(`\nNext step: push these to Railway DB so they appear on groundfloor-nyc-xi.vercel.app`);
}

main().catch(e => { console.error(e); process.exit(1); });
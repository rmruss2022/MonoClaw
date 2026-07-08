// Posh.vip scraper for NYC - filters to raves/electronic only
const Database = require('better-sqlite3');
const path = require('path');

const dbPath = path.join(__dirname, '..', 'events.db');
const db = new Database(dbPath);

const TODAY = new Date().toISOString().slice(0, 10);
const API = 'https://hopeful-determination-production-bbec.up.railway.app';

// Keywords that indicate RAVE content (electronic/dance)
const RAVE_KEYWORDS = [
  'rave', 'techno', 'house', 'trance', 'bass', 'dubstep', 'dnb', 'drum',
  'electronic', 'edm', 'dj ', 'deejay', 'warehouse', 'underground',
  'breakbeat', 'jungle', 'hardcore', 'hardstyle', 'psytrance', 'minimal',
  'ambient', 'acid', 'electro', 'disco', 'open air', 'open-air',
  'bpm', 'plur', 'club', 'nightlife', 'afterparty', 'after-party',
  'night party', 'late night', 'midnight', 'dance', 'clubbing'
];

// Keywords that EXCLUDE (these are clearly NOT raves - too mainstream/variety)
const EXCLUDE_KEYWORDS = [
  'tribute', 'comedy', 'stand-up', 'standup', 'concert official',
  'bar fest', 'pub crawl', 'karaoke', 'speed dating', 'bingo',
  'designer bags', 'pop-up', 'popup', 'market', 'brunch',
  'wine tasting', 'food festival', 'craft fair', 'trivia',
  'paint and sip', 'yoga', 'meditation', 'workshop', 'class',
  'networking', 'meetup', 'conference', 'seminar', 'book reading',
  'children', 'kids', 'family', 'pets', 'dog'
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
  { match: /harbor/i, venue: 'Harbor NYC' },
  { match: /industry-city|industrycity/i, venue: 'Industry City' },
  { match: /99-scott/i, venue: '99 Scott' },
  { match: /paradise-coney/i, venue: 'Paradise Coney Island' },
  { match: /circle-line/i, venue: 'Circle Line' },
  { match: /sightglass/i, venue: 'TBD Brooklyn' }
];

const GENRES = [
  'House', 'Techno', 'Trance', 'Drum & Bass', 'DnB', 'Jungle', 'Breakbeat', 'Breaks',
  'Disco', 'Tech House', 'Deep House', 'Acid', 'Hardcore', 'UK Garage', 'Garage',
  'Dubstep', 'Bass', 'Ambient', 'Experimental', 'Industrial', 'Afro House', 'Latin House',
  'Psytrance', 'Minimal', 'Microhouse', 'Electro', 'Hip-Hop', 'Trap',
  'Hard Techno', 'Afrobeats', 'Reggaeton', 'Live PA', 'Open Air'
];

async function fetchHtml(url) {
  const r = await fetch(url, {
    headers: { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' },
    redirect: 'follow'
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.text();
}

function extractPoshEvents(html) {
  const events = new Map();
  const re = /posh\.vip\/e\/([a-z0-9-]+)/g;
  let m;
  while ((m = re.exec(html))) {
    if (!events.has(m[1])) events.set(m[1], m[1]);
  }
  return Array.from(events.values());
}

function isRaveEvent(title, slug, description) {
  const text = `${title} ${slug.replace(/-/g, ' ')} ${description}`.toLowerCase();
  
  // Check exclusions first
  for (const kw of EXCLUDE_KEYWORDS) {
    if (text.includes(kw)) return false;
  }
  
  // Check rave keywords
  for (const kw of RAVE_KEYWORDS) {
    if (text.includes(kw)) return true;
  }
  
  return false;
}

async function fetchEventDetails(slug) {
  try {
    const html = await fetchHtml(`https://posh.vip/e/${slug}`);
    
    // Try to find JSON-LD structured data
    const jsonLdMatch = html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/);
    let name = '', date = '', venue = '', description = '';
    
    if (jsonLdMatch) {
      try {
        const data = JSON.parse(jsonLdMatch[1]);
        if (data.name) name = data.name;
        if (data.startDate) date = data.startDate;
        if (data.location?.name) venue = data.location.name;
        if (data.location?.address?.addressLocality) venue = venue || data.location.address.addressLocality;
        if (data.description) description = typeof data.description === 'string' ? data.description : '';
      } catch (e) {}
    }
    
    // Fallback: parse from meta tags
    const ogTitleMatch = html.match(/<meta\s+(?:property|name)="og:title"\s+content="([^"]+)"/i);
    if (ogTitleMatch && !name) name = ogTitleMatch[1].split('|')[0].trim();
    
    const ogDescMatch = html.match(/<meta\s+(?:property|name)="og:description"\s+content="([^"]+)"/i);
    if (ogDescMatch && !description) description = ogDescMatch[1].trim();
    
    // Title from h1
    const h1Match = html.match(/<h1[^>]*>([^<]+)<\/h1>/);
    if (h1Match && !name) name = h1Match[1].trim();
    
    // Parse date from title/slug/description
    const months = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };
    const dateSources = `${name} ${description} ${slug}`.toLowerCase();
    
    // Try ISO format first
    let dm = dateSources.match(/(\d{4})-(\d{2})-(\d{2})/);
    if (dm) {
      date = `${dm[1]}-${dm[2]}-${dm[3]}`;
    } else {
      // "Sat, 12 Jul" or "Jul 12"
      dm = dateSources.match(/(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)/i);
      if (dm) {
        const month = months[dm[2].slice(0, 3)];
        const day = parseInt(dm[1]);
        const year = new Date().getFullYear();
        date = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      } else {
        // Try (jan|feb|...)-(\d{1,2})
        dm = dateSources.match(/(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[- ]+(\d{1,2})/i);
        if (dm) {
          const month = months[dm[1].slice(0, 3)];
          const day = parseInt(dm[2]);
          const year = new Date().getFullYear();
          date = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        }
      }
    }
    
    // Venue detection
    if (!venue) {
      for (const p of VENUE_PATTERNS) {
        if (p.match.test(slug) || p.match.test(name) || p.match.test(description)) {
          venue = p.venue;
          break;
        }
      }
    }
    
    // Cost - look for price in HTML
    let cost = 0;
    if (!/\bfree\b/i.test(description + ' ' + html)) {
      const pm = html.match(/\$\s*(\d{1,3}(?:\.\d{1,2})?)/);
      if (pm) {
        const p = parseFloat(pm[1]);
        if (p >= 1 && p <= 500) cost = p;
      }
    }
    
    return { name, date, venue, description: description.slice(0, 500), cost };
  } catch (e) {
    return null;
  }
}

function isRave(text) {
  const lower = text.toLowerCase();
  for (const kw of EXCLUDE_KEYWORDS) {
    if (lower.includes(kw)) return false;
  }
  for (const kw of RAVE_KEYWORDS) {
    if (lower.includes(kw)) return true;
  }
  return false;
}

async function pushToRailway(ev) {
  try {
    const dayOfWeek = new Date(ev.date + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'long' });
    const r = await fetch(`${API}/api/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: ev.id, name: ev.name, venue: ev.venue || '', date: ev.date,
        dayOfWeek, genres: ev.genres, description: ev.description, topPick: 0, cost: ev.cost
      })
    });
    const d = await r.json();
    return d.success;
  } catch (e) {
    return false;
  }
}

function saveLocal(ev) {
  const slug = ev.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const vslug = (ev.venue || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const id = ev.id || `${ev.date}-${slug}-${vslug}`;
  
  const d = new Date(ev.date + 'T12:00:00');
  const dow = d.getDay();
  const monday = new Date(d);
  monday.setDate(d.getDate() - ((dow + 6) % 7));
  const week_start = monday.toISOString().slice(0, 10);
  
  try {
    db.prepare(`
      INSERT INTO events (id, name, venue, date, dayOfWeek, genres, description, week_start, topPick, cost)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET
        name = excluded.name, venue = excluded.venue, genres = excluded.genres,
        description = excluded.description, cost = excluded.cost, updated_at = CURRENT_TIMESTAMP
    `).run(id, ev.name, ev.venue || '', ev.date, ev.dayOfWeek,
      JSON.stringify(ev.genres), ev.description || '', week_start, 0, ev.cost || 0);
    return id;
  } catch (e) {
    return null;
  }
}

async function main() {
  console.log('Scraping Posh NYC for RAVE events only...\n');
  
  // Scrape explore pages + by genre
  const PAGES = [
    'https://posh.vip/explore/new-york',
    'https://posh.vip/explore/new-york/electronic',
    'https://posh.vip/explore/new-york/techno',
    'https://posh.vip/explore/new-york/house',
    'https://posh.vip/explore/new-york/dance',
  ];
  
  const allSlugs = new Set();
  for (const url of PAGES) {
    try {
      console.log(`Fetching ${url}...`);
      const html = await fetchHtml(url);
      const events = extractPoshEvents(html);
      console.log(`  Found ${events.length} events`);
      for (const e of events) allSlugs.add(e);
    } catch (e) {
      console.log(`  ERROR: ${e.message}`);
    }
  }
  
  console.log(`\n${allSlugs.size} unique event slugs. Fetching details + filtering for raves...\n`);
  
  const results = [];
  for (const slug of allSlugs) {
    const details = await fetchEventDetails(slug);
    if (!details || !details.date) continue;
    if (details.date < TODAY) continue;
    
    // Filter to raves only
    if (!isRave(`${details.name} ${slug.replace(/-/g, ' ')} ${details.description}`)) {
      continue;
    }
    
    // Detect genres from text
    const text = `${details.name} ${details.description}`.toLowerCase();
    const genres = [];
    for (const g of GENRES) {
      if (text.includes(g.toLowerCase()) && !genres.includes(g)) genres.push(g);
    }
    if (genres.length === 0) genres.push('Electronic');
    
    results.push({
      ...details,
      id: `${details.date}-${details.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}-${(details.venue || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}`,
      dayOfWeek: new Date(details.date + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'long' }),
      genres
    });
  }
  
  results.sort((a, b) => a.date.localeCompare(b.date));
  
  console.log(`Found ${results.length} RAVE events. Saving to local DB + pushing to Railway...\n`);
  
  let savedLocal = 0, pushedRailway = 0;
  for (const ev of results) {
    const localId = saveLocal(ev);
    if (localId) savedLocal++;
    
    const pushed = await pushToRailway(ev);
    if (pushed) pushedRailway++;
    
    console.log(`${pushed ? '✓' : '⚠'} ${ev.date} | ${(ev.venue || 'TBD').padEnd(25)} | ${ev.name} [${ev.genres.join(', ')}]`);
  }
  
  console.log(`\n✓ Saved ${savedLocal} locally, pushed ${pushedRailway} to Railway`);
}

main().catch(e => { console.error(e); process.exit(1); });
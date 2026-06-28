#!/usr/bin/env node
/**
 * NYC Raves Dashboard Server
 * SQLite persistence with week-based grouping
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const { getAllEvents, getEventsByWeek, getAllWeeks, getEventsGroupedByWeek, updateEvent, deleteEvent, upsertEvent, getStats, getEventById,
  getBudgetConfig, setBudgetConfig, setEventCost, getBudgetSummary,
  getPerks, getPerksByTier, getRaveCard, getSocialFeed,
  createUser, login, getSession, logout,
  saveScan, updateScanAddedCount, getScanHistory, getScanById, getLatestScan, deleteScan,
  savePushSubscription, deletePushSubscription, getPushSubscriptionsByUser, getGoingShowsForDate } = require('./lib/db');
const { sendPush, VAPID_PUBLIC } = require('./lib/push');

const PORT = process.env.PORT || 3004;
const ROOT_DIR = __dirname;
const START_TIME = Date.now();

// Helper to extract auth token from request
function getAuthToken(req) {
  const auth = req.headers['authorization'];
  if (auth && auth.startsWith('Bearer ')) return auth.slice(7);
  return null;
}

function requireAuth(req, res) {
  const token = getAuthToken(req);
  const user = getSession(token);
  if (!user) {
    res.writeHead(401, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Unauthorized' }));
    return null;
  }
  return user;
}

// Venue detection from URL/domain
const VENUE_PATTERNS = [
  { match: /houseofyes\.org|house-of-yes|onyx-room/i, venue: 'House of Yes' },
  { match: /elsewhere\.club|elsewhere-the-hall|elsewhere-brooklyn|elsewheremusic|\belsewhere-/i, venue: 'Elsewhere' },
  { match: /basement\.ny|basementny|\bbasement-/i, venue: 'Basement' },
  { match: /market-hotel|markethotel/i, venue: 'Market Hotel' },
  { match: /knockdown\.center|knockdowncenter|ruins-at-knockdown|\bknockdown-/i, venue: 'Knockdown Center' },
  { match: /brooklynsteel|bowerypresents/i, venue: 'Brooklyn Steel' },
  { match: /miragebrooklyn|brooklyn-mirage|\bthe-mirage/i, venue: 'Brooklyn Mirage' },
  { match: /goodroom/i, venue: 'Goodroom' },
  { match: /outputclub|outputclub/i, venue: 'Output' },
  { match: /avantgardner/i, venue: 'Avant Gardner' },
  { match: /publicartsnyc|public-records/i, venue: 'Public Records' },
  { match: /sightglass|sightglass/i, venue: 'TBD Brooklyn' },
  { match: /baby-s-all-right|babysallright/i, venue: "Baby's All Right" },
  { match: /ra\.co\/events/i, venue: '' },
  { match: /dice\.fm/i, venue: '' },
  { match: /eventbrite\.com/i, venue: '' }
]

// Genre detection from text
const GENRE_PATTERNS = [
  'House', 'Techno', 'Trance', 'Drum & Bass', 'DnB', 'Jungle',
  'Breakbeat', 'Breaks', 'Disco', 'Tech House', 'Deep House',
  'Acid', 'Hardcore', 'Hardstyle', 'UK Garage', 'Garage',
  'Dubstep', 'Bass', 'Ambient', 'Experimental', 'Industrial',
  'Afro House', 'Afrobeats', 'Latin House', 'Reggaeton', 'Baile Funk',
  'Psytrance', 'Goa', 'Minimal', 'Microhouse', 'Electro', 'Footwork',
  'Juke', 'Hip-Hop', 'Rap', 'Drill', 'Trap', 'Live PA', 'Live Set'
]

function extractEvent(md, url, html, meta = {}) {
  const result = {
    name: '',
    venue: '',
    date: '',
    genres: [],
    description: ''
  }

  // Combined text for searching - strip markdown image URLs first (they contain dates that confuse the parser)
  // Pattern: ![...](URL) or <img src="URL">
  const cleanMd = md.replace(/!\[[^\]]*\]\([^)]+\)/g, '').replace(/<img[^>]+>/g, '')
  const text = cleanMd + '\n' + (html || '').replace(/<img[^>]+>/g, '').replace(/<[^>]+>/g, ' ') + '\n' + (meta.description || '') + '\n' + (meta.title || '')

  // Detect venue from URL
  for (const p of VENUE_PATTERNS) {
    if (p.match.test(url)) {
      result.venue = p.venue
      break
    }
  }

  // Try to extract venue from title: "Event Name at Venue Name"
  if (!result.venue && meta.title) {
    const atMatch = meta.title.match(/\s+at\s+([^,]+?)(?:,|\s*-\s*|\s*\|\s*|$)/i)
    if (atMatch) {
      result.venue = atMatch[1].trim().slice(0, 80)
    }
  }

  // Title priority: meta.title (Firecrawl cleaned) > og:title > first heading
  if (meta.title) {
    result.name = meta.title.split('|')[0].split(' - ')[0].split(' at ')[0].trim().slice(0, 120)
  }
  if (!result.name) {
    const ogTitleMatch = html && html.match(/<meta\s+(?:property|name)="og:title"\s+content="([^"]+)"/i)
    if (ogTitleMatch) {
      result.name = ogTitleMatch[1].split('|')[0].split(' - ')[0].split(' at ')[0].trim().slice(0, 120)
    }
  }
  if (!result.name) {
    const h1Match = md.match(/^#\s+(.+)$/m)
    if (h1Match) result.name = h1Match[1].trim().slice(0, 120)
  }
  if (!result.name) {
    const titleMatch = html && html.match(/<title>([^<]+)<\/title>/i)
    if (titleMatch) result.name = titleMatch[1].split('|')[0].split(' - ')[0].trim().slice(0, 120)
  }

  // Date: try multiple formats, starting with highest priority text
  // Priority order: meta.title > meta.description > markdown body (with images stripped)
  const dateSearchText = (meta.title || '') + '\n' + (meta.description || '') + '\n' + text

  // ISO: 2026-07-04 (look only in title/description first to avoid image URL dates)
  let m = (meta.title || '').match(/\b(20\d{2})-(\d{2})-(\d{2})\b/)
  if (m) {
    result.date = `${m[1]}-${m[2]}-${m[3]}`
  } else {
    m = dateSearchText.match(/\b(20\d{2})-(\d{2})-(\d{2})\b/)
    if (m) {
      // Skip if this match is clearly from a URL (preceded by /attachments/ or similar)
      const fullMatch = m[0]
      const matchIdx = dateSearchText.indexOf(fullMatch)
      const before = dateSearchText.slice(Math.max(0, matchIdx - 30), matchIdx)
      if (!/\/attachments\/|dice-media|cloudinary|imageurl/i.test(before)) {
        result.date = `${m[1]}-${m[2]}-${m[3]}`
      }
    }
  }

  if (!result.date) {
    const months = ['January','February','March','April','May','June','July','August','September','October','November','December']
    const monthsShort = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    // Try "Sat, 14 Jun 2025" (RA format)
    let dm = dateSearchText.match(/\b(\d{1,2})\s+([A-Za-z]+)\.?\s+(20\d{2})\b/i)
    if (dm) {
      const ms = dm[2].replace(/\.$/, '').slice(0, 3)
      const mi = monthsShort.findIndex(m => m.toLowerCase() === ms.toLowerCase()) + 1
      if (mi > 0) {
        result.date = `${dm[3]}-${String(mi).padStart(2,'0')}-${String(parseInt(dm[1])).padStart(2,'0')}`
      }
    }
    // Try "Jun 14, 2026" or "Jun 14 2026"
    if (!result.date) {
      dm = dateSearchText.match(new RegExp(`\\b(${monthsShort.join('|')})\\.?\\s+(\\d{1,2}),?\\s+(20\\d{2})\\b`, 'i'))
      if (dm) {
        const ms = dm[1].replace(/\.$/, '')
        const mi = monthsShort.findIndex(m => m.toLowerCase() === ms.toLowerCase()) + 1
        if (mi > 0) {
          result.date = `${dm[3]}-${String(mi).padStart(2,'0')}-${String(parseInt(dm[2])).padStart(2,'0')}`
        }
      }
    }
    // Try "June 14, 2026"
    if (!result.date) {
      dm = dateSearchText.match(new RegExp(`\\b(${months.join('|')})\\s+(\\d{1,2}),?\\s+(20\\d{2})\\b`, 'i'))
      if (dm) {
        const mi = months.indexOf(dm[1][0].toUpperCase() + dm[1].slice(1).toLowerCase()) + 1
        result.date = `${dm[3]}-${String(mi).padStart(2,'0')}-${String(parseInt(dm[2])).padStart(2,'0')}`
      }
    }
    // Try "7/4/2026"
    if (!result.date) {
      dm = dateSearchText.match(/\b(\d{1,2})\/(\d{1,2})\/(20\d{2})\b/)
      if (dm) {
        result.date = `${dm[3]}-${String(parseInt(dm[1])).padStart(2,'0')}-${String(parseInt(dm[2])).padStart(2,'0')}`
      }
    }
    // Try URL slug patterns: "-26th-jun-" or "-jul-4-" or "-2026-07-04-"
    if (!result.date) {
      const urlDateMatch = url.match(/[/-](\d{1,2})(?:st|nd|rd|th)?[-](jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[-/]/i)
      if (urlDateMatch) {
        const mi = monthsShort.findIndex(m => m.toLowerCase() === urlDateMatch[2].toLowerCase()) + 1
        if (mi > 0) {
          // Use current year (2026) as default
          const year = new Date().getFullYear()
          result.date = `${year}-${String(mi).padStart(2,'0')}-${String(parseInt(urlDateMatch[1])).padStart(2,'0')}`
        }
      }
    }
    // Try "Mon 26 Jun" or "26 Jun" without year in title/description
    if (!result.date) {
      dm = dateSearchText.match(/\b(\d{1,2})\s+([A-Za-z]+)\b/i) || dateSearchText.match(new RegExp(`\\b(${monthsShort.join('|')})\\.?\\s+(\\d{1,2})\\b`, 'i'))
      if (dm) {
        let day, monthStr
        if (/^\d/.test(dm[1])) {
          day = parseInt(dm[1]); monthStr = dm[2]
        } else {
          monthStr = dm[1]; day = parseInt(dm[2])
        }
        const ms = monthStr.replace(/\.$/, '').slice(0, 3)
        const mi = monthsShort.findIndex(m => m.toLowerCase() === ms.toLowerCase()) + 1
        if (mi > 0 && day > 0 && day <= 31) {
          const year = new Date().getFullYear()
          result.date = `${year}-${String(mi).padStart(2,'0')}-${String(day).padStart(2,'0')}`
        }
      }
    }
  }

  // Genres: scan for known genre keywords
  for (const g of GENRE_PATTERNS) {
    const re = new RegExp(`\\b${g.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i')
    if (re.test(text) && !result.genres.includes(g)) {
      result.genres.push(g)
    }
  }
  result.genres = result.genres.slice(0, 4)

  // Description: prefer meta.description > og:description > markdown paragraphs
  if (meta.description) {
    result.description = meta.description.split('\n').filter(s => s.length > 20)[0].trim().slice(0, 300)
  } else {
    const ogDescMatch = html && html.match(/<meta\s+(?:property|name)="og:description"\s+content="([^"]+)"/i)
    if (ogDescMatch) {
      result.description = ogDescMatch[1].trim().slice(0, 300)
    } else {
      // Skip first heading line, get next 2 sentences
      const lines = cleanMd.split('\n').filter(l => l.trim() && !l.startsWith('#') && l.length > 30 && !l.startsWith('!'))
      result.description = lines.slice(0, 2).join(' ').slice(0, 300)
    }
  }

  // Top pick: heuristic
  if (/top\s*pick|headliner?|must[- ]see|featured/i.test(text)) {
    result.topPick = true
  }

  // Price extraction — look for ticket prices in the scraped text
  result.cost = extractPrice(text, url)

  return result
}

function extractPrice(text, url = '') {
  // Patterns to try in priority order:
  // "From $25", "$25", "25 USD", "tickets from 25", "£20" etc.
  const patterns = [
    // "from $25" / "tickets from $25" / "starting from $25"
    /(?:from|tickets?(?:\s+from)?|starting\s+at)\s*\$\s*(\d+(?:\.\d{1,2})?)/i,
    // "$25 - $50" (range, take lower)
    /\$\s*(\d+(?:\.\d{1,2})?)\s*[-–—]\s*\$\s*\d/i,
    // standalone "$25" or "$ 25"
    /\$\s*(\d{1,4}(?:\.\d{1,2})?)\b/,
    // "25 USD" / "25.00 USD"
    /\b(\d{1,4}(?:\.\d{1,2})?)\s*USD\b/i,
    // "price: 25" / "cost: 25" / "ticket price: 25"
    /(?:price|cost|ticket(?:\s+price)?)\s*:?\s*\$?\s*(\d{1,4}(?:\.\d{1,2})?)/i,
    // Dice/RA: "25.00" after "Tickets" line  
    /tickets?\s*\n.*?\$?\s*(\d{1,4}(?:\.\d{1,2})?)/is,
  ]

  // Skip free indicators
  if (/\bfree(?:\s+entry|\s+admission)?\b|\$\s*0\b|no(?:\s+cover|\s+charge)/i.test(text)) {
    // Still check for "free + $X after 11" patterns - take the lower price
    const afterMatch = text.match(/free\s+before.*?\$\s*(\d+)|free\s+until.*?\$\s*(\d+)/i)
    if (afterMatch) return 0
    return 0
  }

  for (const pat of patterns) {
    const m = text.match(pat)
    if (m) {
      const price = parseFloat(m[1])
      // Sanity check: valid ticket price range $1–$500
      if (price >= 1 && price <= 500) return price
    }
  }

  return 0
}

const mimeTypes = {
  '.html': 'text/html',
  '.json': 'application/json',
  '.js': 'text/javascript',
  '.css': 'text/css'
};

// ===================== WEEKLY SCAN =====================

const SCAN_SOURCES = [
  { name: 'Resident Advisor · Techno', url: 'https://ra.co/events/us/newyorkcity/techno', type: 'ra' },
  { name: 'Resident Advisor · House', url: 'https://ra.co/events/us/newyorkcity/house', type: 'ra' },
  { name: 'Resident Advisor · Tech House', url: 'https://ra.co/events/us/newyorkcity/techhouse', type: 'ra' },
  { name: 'Dice · NYC', url: 'https://dice.fm/browse/new_york-5bbf4db0f06331478e9b2c59', type: 'dice' },
  { name: 'Dice · NYC DJ', url: 'https://dice.fm/browse/new_york-5bbf4db0f06331478e9b2c59/music/dj', type: 'dice' }
]

async function scrapeFirecrawl(url, formats = ['markdown']) {
  const apiKey = process.env.FIRECRAWL_API_KEY || 'fc-d05203b38ae149b68feead94856fb92d'
  const resp = await fetch('https://api.firecrawl.dev/v1/scrape', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, formats, onlyMainContent: true })
  })
  const data = await resp.json()
  if (!data.success) throw new Error(data.error || 'Firecrawl failed')
  return data.data
}

function extractEventLinksFromMd(md, sourceType) {
  const links = new Set()
  if (sourceType === 'ra') {
    const matches = md.match(/(?:https?:\/\/ra\.co)?\/events\/(\d+)/g) || []
    for (const m of matches) {
      const idMatch = m.match(/(\d+)/)
      if (idMatch) links.add(`https://ra.co/events/${idMatch[1]}`)
    }
  } else if (sourceType === 'dice') {
    const matches = md.match(/https:\/\/dice\.fm\/event\/[a-z0-9-]+/g) || []
    for (const m of matches) links.add(m)
  }
  return Array.from(links)
}

async function scrapeOneEvent(url) {
  try {
    const data = await scrapeFirecrawl(url, ['markdown', 'html'])
    const md = data.markdown || ''
    const html = data.html || ''
    const meta = data.metadata || {}
    return { url, event: extractEvent(md, url, html, meta) }
  } catch (e) {
    return { url, error: e.message }
  }
}

async function scanAllSources(opts = {}) {
  const sources = opts.sources || SCAN_SOURCES
  const maxPerSource = opts.maxPerSource || 6
  const results = []
  const seen = new Set()
  const allCandidates = []

  for (const source of sources) {
    try {
      const data = await scrapeFirecrawl(source.url, ['markdown'])
      const links = extractEventLinksFromMd(data.markdown || '', source.type)
      const newLinks = links.filter(l => !seen.has(l)).slice(0, maxPerSource)
      newLinks.forEach(l => seen.add(l))
      allCandidates.push(...newLinks.map(url => ({ url, source: source.name, type: source.type })))
    } catch (e) {
      results.push({ source: source.name, error: e.message })
    }
  }

  // Scrape each event detail in parallel (throttled)
  const concurrency = 4
  const detailResults = []
  for (let i = 0; i < allCandidates.length; i += concurrency) {
    const batch = allCandidates.slice(i, i + concurrency)
    const batchResults = await Promise.all(batch.map(c => scrapeOneEvent(c.url)))
    detailResults.push(...batchResults.map((r, idx) => ({ ...r, source: batch[idx].source, type: batch[idx].type })))
  }

  // Mark which are new (not already in DB) and only future events
  const existingIds = new Set(getAllEvents().map(e => e.id))
  const today = new Date().toISOString().slice(0, 10)

  for (const r of detailResults) {
    if (r.error) {
      results.push({ url: r.url, error: r.error, source: r.source })
      continue
    }
    const ev = r.event
    if (!ev.date || ev.date < today) continue
    const slug = (ev.name || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
    const venueSlug = (ev.venue || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
    const id = `${ev.date}-${slug}-${venueSlug}`
    results.push({
      url: r.url,
      source: r.source,
      type: r.type,
      isNew: !existingIds.has(id),
      event: { ...ev, id }
    })
  }

  return {
    scannedAt: new Date().toISOString(),
    sources: sources.map(s => s.name),
    total: results.length,
    new: results.filter(r => r.isNew).length,
    results
  }
}

const server = http.createServer((req, res) => {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  // Handle OPTIONS preflight
  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  const cleanUrl = req.url.split('?')[0];

  // Health check
  if (cleanUrl === '/api/health' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', ts: new Date().toISOString() }));
    return;
  }

  // API: Signup
  if (cleanUrl === '/api/auth/signup' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        const { username, password, displayName } = JSON.parse(body);
        const user = createUser(username, password, displayName);
        const { token } = login(username, password);
        res.writeHead(201, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ success: true, token, user: { id: user.id, username: user.username, displayName: user.display_name } }));
      } catch (e) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // API: Login
  if (cleanUrl === '/api/auth/login' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        const { username, password } = JSON.parse(body);
        const { token, user } = login(username, password);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ success: true, token, user }));
      } catch (e) {
        res.writeHead(401, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // API: Get current session
  if (cleanUrl === '/api/auth/me' && req.method === 'GET') {
    const user = requireAuth(req, res);
    if (!user) return;
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ success: true, user: { id: user.id, username: user.username, displayName: user.display_name } }));
    return;
  }

  // API: Logout
  if (cleanUrl === '/api/auth/logout' && req.method === 'POST') {
    const token = getAuthToken(req);
    logout(token);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ success: true }));
    return;
  }

  // API: Get all events
  if (cleanUrl === '/api/events' && req.method === 'GET') {
    try {
      const events = getAllEvents();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: true, events }));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  // API: Create new event
  if (cleanUrl === '/api/events' && req.method === 'POST') {
    try {
      let body = '';
      req.on('data', chunk => body += chunk);
      req.on('end', () => {
        try {
          const event = JSON.parse(body);
          if (!event.id || !event.name || !event.venue || !event.date) {
            res.writeHead(400, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: 'id, name, venue, date are required' }));
            return;
          }
          upsertEvent(event);
          const created = getEventById(event.id);
          res.writeHead(201, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ success: true, event: created }));
        } catch (e) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: e.message }));
        }
      });
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  // API: Weekly scan — scrapes RA + Dice for new NYC events
  if (cleanUrl === '/api/scan' && req.method === 'POST') {
    const user = requireAuth(req, res);
    if (!user) return;
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', async () => {
      try {
        const opts = body ? JSON.parse(body) : {};
        const result = await scanAllSources(opts);
        // Persist scan globally
        try {
          const scanId = saveScan(result, user.id);
          result.scanId = scanId;
        } catch (e) {
          console.error('Failed to save scan:', e.message);
        }
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ success: true, ...result }));
      } catch (err) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: err.message }));
      }
    });
    return;
  }

  // API: Add a scanned event to the calendar
  if (cleanUrl === '/api/scan/add' && req.method === 'POST') {
    const user = requireAuth(req, res);
    if (!user) return;
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        const event = JSON.parse(body);
        if (!event.id || !event.name || !event.date) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'id, name, date required' }));
          return;
        }
        if (!event.dayOfWeek) {
          event.dayOfWeek = new Date(event.date + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'long' });
        }
        upsertEvent(event);
        const created = getEventById(event.id);
        res.writeHead(201, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ success: true, event: created }));
      } catch (e) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // API: Import a scan record (for syncing from local to prod)
  if (cleanUrl === '/api/scans/import' && req.method === 'POST') {
    const user = requireAuth(req, res);
    if (!user) return;
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        const scan = JSON.parse(body);
        const scanId = saveScan({
          sources: scan.sources || [],
          total: scan.total || 0,
          new: scan.new || 0,
          added: scan.added || 0,
          results: scan.results || []
        }, user.id);
        res.writeHead(201, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ success: true, scanId }));
      } catch (e) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // API: List past scans (global — all users see the same history)
  if (cleanUrl === '/api/scans' && req.method === 'GET') {
    const user = requireAuth(req, res);
    if (!user) return;
    try {
      const history = getScanHistory();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: true, scans: history }));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: e.message }));
    }
    return;
  }

  // API: Get a specific scan with full results
  if (cleanUrl.startsWith('/api/scans/') && req.method === 'GET') {
    const user = requireAuth(req, res);
    if (!user) return;
    try {
      const scanId = parseInt(cleanUrl.replace('/api/scans/', ''));
      const scan = getScanById(scanId);
      if (!scan) {
        res.writeHead(404, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Scan not found' }));
        return;
      }
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: true, scan }));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: e.message }));
    }
    return;
  }

  // API: Delete a scan from history (any auth'd user can delete)
  if (cleanUrl.startsWith('/api/scans/') && req.method === 'DELETE') {
    const user = requireAuth(req, res);
    if (!user) return;
    try {
      const scanId = parseInt(cleanUrl.replace('/api/scans/', ''));
      deleteScan(scanId);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: true }));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: e.message }));
    }
    return;
  }

  // API: Scrape event URL via Firecrawl and extract event details
  if (cleanUrl === '/api/scrape-event' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', async () => {
      try {
        const { url } = JSON.parse(body);
        if (!url) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'url required' }));
          return;
        }
        const apiKey = process.env.FIRECRAWL_API_KEY || 'fc-d05203b38ae149b68feead94856fb92d';

        // Use Firecrawl v1 scrape with structured extract
        const fcResp = await fetch('https://api.firecrawl.dev/v1/scrape', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${apiKey}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            url,
            formats: ['markdown', 'html'],
            onlyMainContent: true
          })
        });
        const fcData = await fcResp.json();
        if (!fcData.success) {
          res.writeHead(502, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: fcData.error || 'Firecrawl failed' }));
          return;
        }

        const md = fcData.data?.markdown || '';
        const html = fcData.data?.html || '';
        const meta = fcData.data?.metadata || {};

        // Heuristic extraction (passing metadata for title priority)
        const event = extractEvent(md, url, html, meta);

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          success: true,
          event,
          meta: { title: meta.title || '', description: meta.description || '' }
        }));
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // API: Get events grouped by week
  if (cleanUrl === '/api/events/by-week' && req.method === 'GET') {
    try {
      const grouped = getEventsGroupedByWeek();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: true, weeks: grouped }));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  // API: Get all week start dates
  if (cleanUrl === '/api/weeks' && req.method === 'GET') {
    try {
      const weeks = getAllWeeks();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: true, weeks }));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  // API: Get events for a specific week
  if (cleanUrl.startsWith('/api/events/week/') && req.method === 'GET') {
    try {
      const weekStart = cleanUrl.replace('/api/events/week/', '');
      const events = getEventsByWeek(weekStart);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: true, weekStart, events }));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  // API: DELETE event (requires auth)
  if (cleanUrl.startsWith('/api/events/') && cleanUrl.split('?')[0].split('/').length === 4 && req.method === 'DELETE') {
    const user = requireAuth(req, res)
    if (!user) return
    const id = cleanUrl.replace('/api/events/', '');
    try {
      const id = cleanUrl.replace('/api/events/', '');
      const ev = deleteEvent(id);
      if (!ev) {
        res.writeHead(404, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Event not found' }));
        return;
      }
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: true, event: ev }));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  // API: PATCH event fields (requires auth)
  if (cleanUrl.startsWith('/api/events/') && cleanUrl.split('?')[0].split('/').length === 4 && req.method === 'PATCH') {
    const user = requireAuth(req, res)
    if (!user) return
    try {
      const id = cleanUrl.replace('/api/events/', '');
      let body = '';
      req.on('data', chunk => body += chunk);
      req.on('end', () => {
        try {
          const patch = JSON.parse(body);
          const updated = updateEvent(id, patch);
          if (!updated) {
            res.writeHead(404, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: 'Event not found' }));
            return;
          }
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ success: true, event: updated }));
        } catch (e) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: e.message }));
        }
      });
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  // API: Stats
  if (cleanUrl === '/api/stats' && req.method === 'GET') {
    try {
      const stats = getStats();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: true, stats }));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  // API: Budget summary
  if (cleanUrl === '/api/budget' && req.method === 'GET') {
    try {
      const summary = getBudgetSummary();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: true, ...summary }));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  // API: Update budget config
  if (cleanUrl === '/api/budget/config' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        const patch = JSON.parse(body);
        const cfg = setBudgetConfig(patch);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ success: true, config: cfg }));
      } catch (e) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // API: Set event cost
  if (cleanUrl.startsWith('/api/events/') && req.url.split('?')[0].endsWith('/cost') && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        const { cost } = JSON.parse(body);
        const id = cleanUrl.split('/')[3];
        const ev = setEventCost(id, Number(cost) || 0);
        if (!ev) {
          res.writeHead(404, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Event not found' }));
          return;
        }
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ success: true, event: ev }));
      } catch (e) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // API: Perks (all)
  if (cleanUrl === '/api/perks' && req.method === 'GET') {
    try {
      const perks = getPerks();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: true, perks }));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  // API: Rave Card (membership tier)
  if (cleanUrl === '/api/rave-card' && req.method === 'GET') {
    try {
      const card = getRaveCard();
      const perks = getPerksByTier(card.tier);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: true, card, perks }));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  // API: Social feed (where people are going next)
  if (cleanUrl === '/api/social' && req.method === 'GET') {
    try {
      const feed = getSocialFeed();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: true, ...feed }));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  // ===================== PUSH NOTIFICATION ENDPOINTS =====================

  // GET /api/push/vapid-public-key
  if (cleanUrl === '/api/push/vapid-public-key' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ publicKey: VAPID_PUBLIC }));
    return;
  }

  // POST /api/push/subscribe  { endpoint, keys: { p256dh, auth } }
  if (cleanUrl === '/api/push/subscribe' && req.method === 'POST') {
    const user = requireAuth(req, res);
    if (!user) return;
    let body = '';
    req.on('data', d => body += d);
    req.on('end', () => {
      try {
        const sub = JSON.parse(body);
        if (!sub.endpoint || !sub.keys?.p256dh || !sub.keys?.auth) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Invalid subscription object' }));
          return;
        }
        savePushSubscription(user.id, sub);
        res.writeHead(201, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ success: true }));
      } catch(e) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // DELETE /api/push/subscribe  { endpoint }
  if (cleanUrl === '/api/push/subscribe' && req.method === 'DELETE') {
    const user = requireAuth(req, res);
    if (!user) return;
    let body = '';
    req.on('data', d => body += d);
    req.on('end', () => {
      try {
        const { endpoint } = JSON.parse(body);
        deletePushSubscription(endpoint);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ success: true }));
      } catch(e) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // POST /api/push/notify-today  (internal / cron)  sends day-of reminders
  if (cleanUrl === '/api/push/notify-today' && req.method === 'POST') {
    const user = requireAuth(req, res);
    if (!user) return;
    let body = '';
    req.on('data', d => body += d);
    req.on('end', async () => {
      try {
        const { mode = 'morning' } = body ? JSON.parse(body) : {};
        const today = new Date().toISOString().slice(0, 10);
        const shows = getGoingShowsForDate(today);
        if (shows.length === 0) {
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ sent: 0, message: 'No going shows today' }));
          return;
        }
        const subs = getPushSubscriptionsByUser(user.id);
        if (subs.length === 0) {
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ sent: 0, message: 'No push subscriptions' }));
          return;
        }
        let totalSent = 0;
        for (const show of shows) {
          const costLine = show.cost > 0 ? `$${show.cost} ticket` : 'no ticket logged';
          const payload = mode === 'evening'
            ? { title: `How was ${show.name}?`, body: `${show.venue} · ${costLine} · mark attended`, url: '/', tag: `wrap-${show.id}` }
            : { title: `Tonight: ${show.name} 🎉`, body: `${show.venue}${show.cost > 0 ? ` · $${show.cost} paid` : ''}`, url: '/', tag: `show-${show.id}` };
          const result = await sendPush(payload, subs);
          totalSent += result.sent;
        }
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ sent: totalSent, shows: shows.length }));
      } catch(e) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // Serve static files
  let filePath = path.join(ROOT_DIR, cleanUrl === '/' ? 'dashboard.html' : cleanUrl);
  const extname = path.extname(filePath);
  const contentType = mimeTypes[extname] || 'application/octet-stream';

  fs.readFile(filePath, (err, content) => {
    if (err) {
      if (err.code === 'ENOENT') {
        res.writeHead(404, { 'Content-Type': 'text/plain' });
        res.end('404 Not Found');
      } else {
        res.writeHead(500, { 'Content-Type': 'text/plain' });
        res.end('500 Internal Server Error');
      }
    } else {
      res.writeHead(200, {
        'Content-Type': contentType,
        'Access-Control-Allow-Origin': '*'
      });
      res.end(content);
    }
  });
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`🎵 NYC Raves Dashboard running at http://127.0.0.1:${PORT}`);
  console.log(`✅ SQLite persistence enabled`);
  console.log(`📅 Week-based grouping active`);
  console.log(`   Uptime: ${Math.floor((Date.now() - START_TIME) / 1000)}s`);
});

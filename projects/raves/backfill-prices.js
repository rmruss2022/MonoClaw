#!/usr/bin/env node
/**
 * backfill-prices.js
 * Re-scrapes stored event URLs from scan history to find ticket prices.
 * Updates local DB. Run: node backfill-prices.js
 */

const https = require('https')
const http = require('http')
const Database = require('better-sqlite3')
const path = require('path')
const fs = require('fs')

const DB_PATH = process.env.DB_PATH || path.join(__dirname, 'events.db')

function getFcKey() {
  try {
    const cfg = JSON.parse(fs.readFileSync('/Users/matthew_1/.openclaw/openclaw.json', 'utf8'))
    // Check various locations
    return process.env.FIRECRAWL_API_KEY 
      || cfg?.env?.FIRECRAWL_API_KEY 
      || cfg?.plugins?.firecrawl?.apiKey
      || ''
  } catch { return process.env.FIRECRAWL_API_KEY || '' }
}

const FIRECRAWL_KEY = getFcKey()
const db = new Database(DB_PATH)

function extractPrice(text) {
  if (!text) return 0
  // Free checks first
  if (/\bfree\s+(?:entry|admission|event|show)\b|no\s+(?:cover|charge)\b|\$\s*0\b/i.test(text)) return 0
  
  const patterns = [
    // "from $25" / "tickets from $25" / "starting from $25"
    /(?:from|tickets?(?:\s+from)?|starting(?:\s+from|\s+at)?)\s*\$\s*(\d+(?:\.\d{1,2})?)/i,
    // "$25 - $50" range → take lower
    /\$\s*(\d+(?:\.\d{1,2})?)\s*[–—-]\s*\$\s*\d+/,
    // "tickets: $25" / "price: $25"
    /(?:tickets?|price|admission|cover)\s*:?\s*\$\s*(\d+(?:\.\d{1,2})?)/i,
    // "$25 + fees" / "$25 incl."
    /\$\s*(\d+(?:\.\d{1,2})?)\s*(?:\+\s*(?:fees?|booking)|incl)/i,
    // standalone "$25"
    /\$\s*(\d{1,4}(?:\.\d{1,2})?)\b/,
    // "25 USD"
    /\b(\d{1,4}(?:\.\d{1,2})?)\s*USD\b/i,
  ]
  
  for (const pat of patterns) {
    const m = text.match(pat)
    if (m) {
      const price = parseFloat(m[1])
      if (price >= 1 && price <= 500) return price
    }
  }
  return 0
}

async function scrapeFirecrawl(url) {
  if (!FIRECRAWL_KEY) throw new Error('No Firecrawl key')
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({ url, formats: ['markdown'] })
    const req = https.request({
      hostname: 'api.firecrawl.dev',
      path: '/v1/scrape',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${FIRECRAWL_KEY}`,
        'Content-Length': Buffer.byteLength(body)
      }
    }, res => {
      let d = ''; res.on('data', c => d += c)
      res.on('end', () => { try { resolve(JSON.parse(d)) } catch(e) { reject(e) } })
    })
    req.on('error', reject)
    req.write(body); req.end()
  })
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)) }

async function main() {
  console.log(`DB: ${DB_PATH}`)
  console.log(`Firecrawl key: ${FIRECRAWL_KEY ? FIRECRAWL_KEY.slice(0,12) + '...' : 'NOT FOUND'}`)

  // Get all upcoming events that need prices
  const needsPrice = db.prepare(`
    SELECT id, name, venue, date, description
    FROM events
    WHERE date >= date('now') AND (cost IS NULL OR cost = 0)
    ORDER BY date ASC
  `).all()
  console.log(`\nEvents needing prices: ${needsPrice.length}`)

  // Build a map of event name/date → URL from all scan results
  const urlMap = new Map() // eventId → url
  const scans = db.prepare('SELECT results_json FROM scans WHERE results_json IS NOT NULL ORDER BY id DESC').all()
  for (const scan of scans) {
    try {
      const results = JSON.parse(scan.results_json || '[]')
      for (const r of results) {
        const url = r.url
        const ev = r.event
        if (!url || !ev?.name || !ev?.date) continue
        // Build ID the same way the server does
        const slug = (ev.name || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
        const venueSlug = (ev.venue || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
        const id = `${ev.date}-${slug}-${venueSlug}`
        if (!urlMap.has(id)) urlMap.set(id, url)
      }
    } catch {}
  }
  console.log(`URL map built: ${urlMap.size} events have source URLs`)

  // First pass: try extracting price from existing description
  let fromDesc = 0
  for (const event of needsPrice) {
    const price = extractPrice(event.description || '')
    if (price > 0) {
      db.prepare('UPDATE events SET cost = ? WHERE id = ?').run(price, event.id)
      console.log(`  [desc] $${price} → ${event.name.slice(0, 50)}`)
      fromDesc++
    }
  }
  console.log(`\nPrices from description: ${fromDesc}`)

  // Second pass: scrape source URLs for events still missing price
  if (!FIRECRAWL_KEY) {
    console.log('No Firecrawl key — skipping URL scraping')
  } else {
    const stillMissing = db.prepare(`
      SELECT id, name, venue, date FROM events
      WHERE date >= date('now') AND (cost IS NULL OR cost = 0)
      ORDER BY date ASC
    `).all()

    const toScrape = stillMissing.filter(e => urlMap.has(e.id))
    console.log(`\nEvents with source URLs to scrape: ${toScrape.length} of ${stillMissing.length}`)

    let scraped = 0, pricesFound = 0
    for (const event of toScrape) {
      const url = urlMap.get(event.id)
      try {
        process.stdout.write(`  Scraping ${event.name.slice(0, 45).padEnd(45)} ... `)
        const data = await scrapeFirecrawl(url)
        const md = data?.data?.markdown || ''
        const price = extractPrice(md)
        if (price > 0) {
          db.prepare('UPDATE events SET cost = ? WHERE id = ?').run(price, event.id)
          console.log(`$${price}`)
          pricesFound++
        } else {
          // Check if page says "free"
          if (/\bfree\b/i.test(md.slice(0, 2000))) {
            console.log(`free`)
          } else {
            console.log(`not found`)
          }
        }
        scraped++
        await sleep(300) // rate limit
      } catch (e) {
        console.log(`error: ${e.message.slice(0, 40)}`)
      }
    }
    console.log(`\nScraped: ${scraped}, Prices found: ${pricesFound}`)
  }

  // Final summary
  const stats = db.prepare(`
    SELECT 
      COUNT(*) total,
      SUM(CASE WHEN cost > 0 THEN 1 ELSE 0 END) with_price
    FROM events WHERE date >= date('now')
  `).get()
  
  console.log(`\n=== Summary ===`)
  console.log(`Upcoming events: ${stats.total}`)
  console.log(`With price: ${stats.with_price} (${Math.round(stats.with_price/stats.total*100)}%)`)
  console.log(`No price: ${stats.total - stats.with_price}`)

  const priced = db.prepare(`
    SELECT name, date, cost FROM events 
    WHERE date >= date('now') AND cost > 0 
    ORDER BY date ASC
  `).all()
  if (priced.length) {
    console.log(`\nPriced events:`)
    priced.forEach(e => console.log(`  $${String(Math.round(e.cost)).padStart(3)} | ${e.date} | ${e.name.slice(0, 55)}`))
  }
}

main().catch(e => { console.error('Fatal:', e); process.exit(1) })

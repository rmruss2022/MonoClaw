#!/usr/bin/env node
/**
 * Seed the DB with real events from RA + Dice via Firecrawl scrape
 */

const http = require('http')

const events = [
  // Real Brooklyn events found via web search
  { url: 'https://dice.fm/event/avw7y7-mgmt-dj-set-26th-jun-ruins-at-knockdown-center-new-york-tickets', note: 'MGMT DJ Set at Ruins, Knockdown Center' },
  { url: 'https://dice.fm/event/lpykb-kiasmos-ben-lukas-boysen-12th-nov-elsewhere-the-hall-new-york-tickets', note: 'Kiasmos + Ben Lukas Boysen at Elsewhere' },
  { url: 'https://dice.fm/event/ry9ybw-lp-giobbi-presents-yes-yes-yes-open-air-5th-jun-ruins-at-knockdown-center-new-york-tickets', note: 'LP Giobbi YES YES YES at Ruins' },
  // We'll add more as we find them
]

async function scrape(url) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({ url })
    const req = http.request({
      hostname: 'localhost',
      port: 3004,
      path: '/api/scrape-event',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body)
      }
    }, res => {
      let data = ''
      res.on('data', chunk => data += chunk)
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, body: JSON.parse(data) })
        } catch (e) {
          resolve({ status: res.statusCode, body: data })
        }
      })
    })
    req.on('error', reject)
    req.write(body)
    req.end()
  })
}

async function createEvent(event) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify(event)
    const req = http.request({
      hostname: 'localhost',
      port: 3004,
      path: '/api/events',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body)
      }
    }, res => {
      let data = ''
      res.on('data', chunk => data += chunk)
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, body: JSON.parse(data) })
        } catch (e) {
          resolve({ status: res.statusCode, body: data })
        }
      })
    })
    req.on('error', reject)
    req.write(body)
    req.end()
  })
}

function slugify(s) {
  return (s || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
}

function dayOfWeek(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr + 'T12:00:00')
  return d.toLocaleDateString('en-US', { weekday: 'long' })
}

;(async () => {
  console.log(`Scraping ${events.length} events...\n`)
  let created = 0, skipped = 0, failed = 0

  for (const { url, note } of events) {
    process.stdout.write(`• ${note}... `)
    try {
      const scrapeResult = await scrape(url)
      if (!scrapeResult.body.success) {
        console.log(`SCRAPE FAILED: ${scrapeResult.body.error}`)
        failed++
        continue
      }
      const ev = scrapeResult.body.event
      if (!ev.name || !ev.date) {
        console.log(`INCOMPLETE (no name or date)`)
        skipped++
        continue
      }
      const id = `${ev.date}-${slugify(ev.name)}-${slugify(ev.venue)}`
      const payload = {
        id,
        name: ev.name,
        venue: ev.venue || 'TBA',
        date: ev.date,
        dayOfWeek: dayOfWeek(ev.date),
        genres: ev.genres || [],
        description: ev.description || '',
        topPick: !!ev.topPick
      }
      const createResult = await createEvent(payload)
      if (createResult.body.success) {
        console.log(`✓ ${ev.date} @ ${ev.venue}`)
        created++
      } else if (createResult.body.error && createResult.body.error.includes('UNIQUE')) {
        console.log(`(already exists)`)
        skipped++
      } else {
        console.log(`CREATE FAILED: ${JSON.stringify(createResult.body)}`)
        failed++
      }
    } catch (e) {
      console.log(`ERROR: ${e.message}`)
      failed++
    }
  }

  console.log(`\n✅ Created: ${created}, Skipped: ${skipped}, Failed: ${failed}`)
})()
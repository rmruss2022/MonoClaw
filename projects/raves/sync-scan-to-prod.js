#!/usr/bin/env node
/**
 * Syncs the latest scan results + events from local to Railway prod.
 * Usage: node sync-scan-to-prod.js [scanId]
 */
const https = require('https')
const sqlite3 = require('better-sqlite3')
const path = require('path')

const db = new sqlite3(path.join(__dirname, 'events.db'))
const API = 'hopeful-determination-production-bbec.up.railway.app'
const SCAN_ID = process.argv[2] ? parseInt(process.argv[2]) : null

function request(method, urlPath, body, token) {
  return new Promise((resolve, reject) => {
    const data = body ? JSON.stringify(body) : ''
    const opts = {
      hostname: API, port: 443, path: urlPath, method,
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(data),
        ...(token ? { 'Authorization': 'Bearer ' + token } : {})
      }
    }
    const req = https.request(opts, res => {
      let r = ''
      res.on('data', c => r += c)
      res.on('end', () => {
        try { resolve({ status: res.statusCode, body: JSON.parse(r) }) }
        catch (e) { resolve({ status: res.statusCode, body: r }) }
      })
    })
    req.on('error', reject)
    if (data) req.write(data)
    req.end()
  })
}

;(async () => {
  // Login to prod
  console.log('[sync] Logging in to Railway...')
  const login = await request('POST', '/api/auth/login', { username: 'matthew', password: 'rave2026' })
  if (!login.body.success) { console.error('Login failed:', login.body); process.exit(1) }
  const token = login.body.token
  console.log('[sync] Logged in.')

  // Get scan from local DB
  const scanRow = SCAN_ID
    ? db.prepare('SELECT * FROM scans WHERE id = ?').get(SCAN_ID)
    : db.prepare('SELECT * FROM scans ORDER BY scanned_at DESC LIMIT 1').get()

  if (!scanRow) { console.error('No scan found'); process.exit(1) }
  const results = JSON.parse(scanRow.results_json || '[]')
  console.log(`[sync] Scan #${scanRow.id} from ${scanRow.scanned_at}: ${scanRow.total} events, ${scanRow.new_count} new`)

  // 1. Push scan metadata to prod (as a saved scan record)
  const scanPayload = {
    scanId: scanRow.id,
    scanned_at: scanRow.scanned_at,
    sources: JSON.parse(scanRow.sources || '[]'),
    total: scanRow.total,
    new: scanRow.new_count,
    added: scanRow.added_count,
    results
  }
  console.log('[sync] Saving scan record to prod...')
  const scanRes = await request('POST', '/api/scans/import', scanPayload, token)
  if (scanRes.status === 200 || scanRes.status === 201) {
    console.log('[sync] Scan record saved to prod (id: ' + (scanRes.body.scanId || '?') + ')')
  } else {
    console.log('[sync] Scan record save: ' + JSON.stringify(scanRes.body).substring(0, 100))
  }

  // 2. Push all NEW events from this scan to prod
  const newEvents = results.filter(r => r.isNew && !r.error && r.event)
  console.log('[sync] Pushing ' + newEvents.length + ' new events to prod...')
  let pushed = 0, skipped = 0, failed = 0

  for (const r of newEvents) {
    const e = r.event
    const payload = {
      id: e.id,
      name: e.name,
      venue: e.venue || '',
      date: e.date,
      dayOfWeek: e.dayOfWeek || new Date(e.date + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'long' }),
      genres: e.genres || [],
      description: e.description || null,
      topPick: !!e.topPick,
      cost: e.cost || 0,
      sourceUrl: e.sourceUrl || null
    }
    const res = await request('POST', '/api/events', payload, token)
    if (res.body.success) pushed++
    else if (res.body.error && res.body.error.includes('UNIQUE')) { skipped++; }
    else { failed++; console.error('  Failed ' + e.name + ': ' + (res.body.error || '')) }
  }
  console.log('[sync] Events: ' + pushed + ' pushed, ' + skipped + ' already existed, ' + failed + ' failed')

  // 3. Verify prod event count
  const evList = await request('GET', '/api/events', null, token)
  const prodCount = (evList.body.events || []).length
  console.log('[sync] Prod DB now has ' + prodCount + ' events total')

  process.exit(failed > 0 ? 1 : 0)
})().catch(e => { console.error('[sync] Fatal:', e); process.exit(1) })
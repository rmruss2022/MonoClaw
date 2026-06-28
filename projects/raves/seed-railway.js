const https = require('https')
const sqlite3 = require('better-sqlite3')
const path = require('path')

const db = new sqlite3(path.join(__dirname, 'events.db'))
const API = 'hopeful-determination-production-bbec.up.railway.app'

function request(method, urlPath, body, token) {
  return new Promise((resolve, reject) => {
    const data = body ? JSON.stringify(body) : ''
    const opts = {
      hostname: API,
      port: 443,
      path: urlPath,
      method,
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
  console.log('Logging in to Railway...')
  const login = await request('POST', '/api/auth/login', { username: 'matthew', password: 'rave2026' })
  if (!login.body.success) {
    console.error('Login failed:', login.body)
    process.exit(1)
  }
  const token = login.body.token
  console.log('Logged in.')

  const events = db.prepare("SELECT * FROM events WHERE date >= '2026-06-01'").all()
  console.log('Found ' + events.length + ' events to push.')

  let pushed = 0, failed = 0
  for (const e of events) {
    const payload = {
      id: e.id,
      name: e.name,
      venue: e.venue,
      date: e.date,
      dayOfWeek: e.dayOfWeek,
      genres: JSON.parse(e.genres || '[]'),
      description: e.description || null,
      topPick: !!e.topPick,
      cost: e.cost || 0,
      interest: e.interest || null,
      notes: e.notes || null,
      attended: !!e.attended,
      vibe_tags: JSON.parse(e.vibe_tags || '[]')
    }
    const r = await request('POST', '/api/events', payload, token)
    if (r.body.success) pushed++
    else { failed++; console.error('Failed ' + e.name + ': ' + (r.body.error || JSON.stringify(r.body))) }
  }
  console.log('\nDone: ' + pushed + ' pushed, ' + failed + ' failed.')
  process.exit(failed > 0 ? 1 : 0)
})().catch(e => { console.error(e); process.exit(1) })
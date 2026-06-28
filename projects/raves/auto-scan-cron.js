#!/usr/bin/env node
/**
 * Auto-scan cron — runs on Railway prod (or locally against prod API).
 * Scans RA + Dice for NYC events, auto-adds all NEW future events to the DB.
 * No user interaction needed. Designed to run weekly via openclaw cron.
 *
 * Usage: node auto-scan-cron.js
 * Env:   RAVES_API=https://... (defaults to Railway prod)
 *        RAVES_USER / RAVES_PASSWORD
 *        TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID (optional, for summary DM)
 */

const https = require('https')
const http = require('http')
const fs = require('fs')

const API_BASE = process.env.RAVES_API || 'https://hopeful-determination-production-bbec.up.railway.app'
const USERNAME = process.env.RAVES_USER || 'matthew'
const PASSWORD = process.env.RAVES_PASSWORD || 'rave2026'
const TELEGRAM_CHAT_ID = process.env.TELEGRAM_CHAT_ID || '5574760589'

function loadTelegramToken() {
  try {
    const cfg = JSON.parse(fs.readFileSync('/Users/matthew_1/.openclaw/openclaw.json', 'utf8'))
    return cfg?.channels?.telegram?.botToken || ''
  } catch (e) { return '' }
}
const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || loadTelegramToken()

function request(baseUrl, method, path, body, token) {
  return new Promise((resolve, reject) => {
    const url = new URL(baseUrl + path)
    const data = body ? JSON.stringify(body) : ''
    const lib = url.protocol === 'https:' ? https : http
    const opts = {
      hostname: url.hostname,
      port: url.port || (url.protocol === 'https:' ? 443 : 80),
      path: url.pathname + url.search,
      method,
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(data),
        ...(token ? { 'Authorization': 'Bearer ' + token } : {})
      }
    }
    const req = lib.request(opts, res => {
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

async function telegramSend(message) {
  if (!TELEGRAM_BOT_TOKEN) { console.log('[telegram skipped - no token]'); return }
  try {
    const r = await fetch(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: TELEGRAM_CHAT_ID, text: message, parse_mode: 'HTML', disable_web_page_preview: true })
    })
    const d = await r.json()
    if (!d.ok) console.error('[telegram]', d.description)
  } catch (e) { console.error('[telegram error]', e.message) }
}

function fmtDate(dateStr) {
  if (!dateStr) return '?'
  const dt = new Date(dateStr + 'T12:00:00')
  return dt.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
}

;(async () => {
  const start = Date.now()
  console.log('[auto-scan] Starting against', API_BASE)

  // 1. Login
  const { body: loginBody } = await request(API_BASE, 'POST', '/api/auth/login', { username: USERNAME, password: PASSWORD })
  if (!loginBody.success) { console.error('[auto-scan] Login failed:', loginBody); process.exit(1) }
  const token = loginBody.token
  console.log('[auto-scan] Logged in')

  // 2. Run scan
  console.log('[auto-scan] Running scan (60-90s)...')
  const { body: scanBody } = await request(API_BASE, 'POST', '/api/scan', {}, token)
  if (!scanBody.success) { console.error('[auto-scan] Scan failed:', scanBody); process.exit(1) }

  const { total, new: newCount, results = [], scanId } = scanBody
  console.log(`[auto-scan] Scan complete: ${total} found, ${newCount} new (scanId: ${scanId})`)

  // 3. Auto-add all NEW future events
  const toAdd = results.filter(r => r.isNew && !r.error && r.event?.id && r.event?.date)
  console.log(`[auto-scan] Auto-adding ${toAdd.length} events...`)

  let added = 0, failed = 0
  const addedNames = []

  for (const r of toAdd) {
    const e = r.event
    if (!e.dayOfWeek) e.dayOfWeek = new Date(e.date + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'long' })
    const { body: addBody } = await request(API_BASE, 'POST', '/api/scan/add', e, token)
    if (addBody.success) {
      added++
      addedNames.push({ name: e.name, venue: e.venue, date: e.date })
    } else {
      failed++
      console.error(`  ✗ ${e.name}: ${addBody.error}`)
    }
  }
  console.log(`[auto-scan] Added: ${added}, Failed: ${failed}`)

  const elapsed = Math.round((Date.now() - start) / 1000)

  // 4. Send Telegram summary
  let msg = `🔍 <b>Weekly Rave Scan Complete</b>\n`
  msg += `<i>${total} events scanned · ${newCount} new · ${added} auto-added · ${elapsed}s</i>\n\n`

  if (addedNames.length > 0) {
    msg += `<b>Added to your calendar:</b>\n`
    for (const e of addedNames.slice(0, 15)) {
      msg += `  • <b>${e.name}</b>\n    ${fmtDate(e.date)} @ ${e.venue || 'TBA'}\n`
    }
    if (addedNames.length > 15) msg += `  · and ${addedNames.length - 15} more\n`
    msg += `\n🌐 <a href="https://app-nu-five-14.vercel.app">Open Rave Planner</a> to tag Going / Maybe`
  } else {
    msg += `No new events this week — you're all caught up! 🪩`
  }

  if (msg.length > 4000) msg = msg.slice(0, 3950) + '\n<i>... (truncated)</i>'
  await telegramSend(msg)

  console.log('[auto-scan] Done ✓')
  process.exit(0)
})().catch(e => { console.error('[auto-scan] Fatal:', e); process.exit(1) })
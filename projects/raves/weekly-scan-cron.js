#!/usr/bin/env node
/**
 * Weekly Rave Scan Cron
 * Runs the RA + Dice scanner and DMs the user via Telegram with new picks.
 *
 * Usage: node weekly-scan-cron.js
 */

const http = require('http')
const fs = require('fs')
const path = require('path')

// Load Telegram token from openclaw.json
function loadTelegramToken() {
  try {
    const cfg = JSON.parse(fs.readFileSync('/Users/matthew_1/.openclaw/openclaw.json', 'utf8'))
    return cfg?.channels?.telegram?.botToken || ''
  } catch (e) {
    return ''
  }
}

const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || loadTelegramToken()
const TELEGRAM_CHAT_ID = process.env.TELEGRAM_CHAT_ID || '5574760589' // Matthew
const API_HOST = '127.0.0.1'
const API_PORT = 3004
const USERNAME = process.env.RAVES_USER || 'matthew'
const PASSWORD = process.env.RAVES_PASSWORD || 'rave2026'

// Helper: HTTP JSON request
function httpJson(method, path, body, headers = {}) {
  return new Promise((resolve, reject) => {
    const data = body ? JSON.stringify(body) : ''
    const req = http.request({
      hostname: API_HOST, port: API_PORT, path, method,
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(data),
        ...headers
      }
    }, res => {
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

// Helper: Telegram API call
async function telegramSend(message) {
  if (!TELEGRAM_BOT_TOKEN) {
    console.log('[telegram] No bot token, printing message instead')
    console.log(message)
    return null
  }
  try {
    const url = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: TELEGRAM_CHAT_ID,
        text: message,
        parse_mode: 'HTML',
        disable_web_page_preview: true
      })
    })
    return await r.json()
  } catch (e) {
    console.error('Telegram send failed:', e.message)
    return null
  }
}

function dayOfWeek(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'short' })
}

function fmtDate(dateStr) {
  if (!dateStr) return '?'
  const dt = new Date(dateStr + 'T12:00:00')
  return `${dayOfWeek(dateStr)} ${dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`
}

;(async () => {
  console.log('[weekly-scan] Starting...')
  const startTime = Date.now()

  // 1. Login
  const loginRes = await httpJson('POST', '/api/auth/login', { username: USERNAME, password: PASSWORD })
  if (!loginRes.body.success) {
    console.error('Login failed:', loginRes.body)
    process.exit(1)
  }
  const token = loginRes.body.token
  console.log('[weekly-scan] Logged in')

  // 2. Run scan
  console.log('[weekly-scan] Running scan (this takes ~60-90s)...')
  const scanRes = await httpJson('POST', '/api/scan', {}, { 'Authorization': `Bearer ${token}` })
  if (!scanRes.body.success) {
    console.error('Scan failed:', scanRes.body)
    process.exit(1)
  }
  const scan = scanRes.body
  console.log(`[weekly-scan] Found ${scan.total} events, ${scan.new} new`)

  // 3. Build Telegram message
  const newOnes = (scan.results || []).filter(r => r.isNew && !r.error)

  if (newOnes.length === 0) {
    await telegramSend(`🔍 <b>Weekly Rave Scan</b>\n\nNo new events this week — you're all caught up on the scene. 🪩`)
    console.log('[weekly-scan] Done, no new events')
    process.exit(0)
  }

  // Group by week
  const thisWeek = []
  const nextWeek = []
  const later = []
  const now = new Date()
  const weekFromNow = new Date(now.getTime() + 7 * 24 * 3600 * 1000)

  for (const r of newOnes) {
    const e = r.event
    if (!e.date) continue
    const dt = new Date(e.date + 'T12:00:00')
    if (dt < now) continue
    if (dt < weekFromNow) thisWeek.push(r)
    else if (dt < new Date(now.getTime() + 14 * 24 * 3600 * 1000)) nextWeek.push(r)
    else later.push(r)
  }

  let message = `🔍 <b>Weekly Rave Scan</b>\n`
  message += `<i>${scan.total} events scanned · ${scan.new} new · ${newOnes.length} future</i>\n\n`

  if (thisWeek.length > 0) {
    message += `🔥 <b>THIS WEEK (${thisWeek.length})</b>\n`
    for (const r of thisWeek.slice(0, 8)) {
      const e = r.event
      message += `  • <b>${e.name}</b>\n`
      message += `    ${fmtDate(e.date)} @ ${e.venue || 'TBA'}\n`
      if (e.genres && e.genres.length) message += `    <i>${e.genres.slice(0, 3).join(' · ')}</i>\n`
    }
    message += '\n'
  }

  if (nextWeek.length > 0) {
    message += `📅 <b>NEXT WEEK (${nextWeek.length})</b>\n`
    for (const r of nextWeek.slice(0, 6)) {
      const e = r.event
      message += `  • <b>${e.name}</b> — ${fmtDate(e.date)} @ ${e.venue || 'TBA'}\n`
    }
    message += '\n'
  }

  if (later.length > 0) {
    message += `🎪 <b>LATER</b> (${later.length} more)\n`
    for (const r of later.slice(0, 4)) {
      const e = r.event
      message += `  • ${e.name} — ${fmtDate(e.date)}\n`
    }
    if (later.length > 4) message += `  · and ${later.length - 4} more\n`
    message += '\n'
  }

  message += `🌐 Open the app to tag Going / Maybe → http://localhost:3007/`

  // Telegram has 4096 char limit — truncate if needed
  if (message.length > 4000) {
    message = message.slice(0, 3950) + '\n\n<i>... (truncated, see app for full list)</i>'
  }

  // 4. Send
  const elapsed = Math.round((Date.now() - startTime) / 1000)
  console.log(`[weekly-scan] Scan took ${elapsed}s, sending Telegram DM...`)
  const tgRes = await telegramSend(message)
  if (tgRes && tgRes.ok) {
    console.log('[weekly-scan] Telegram sent ✓')
  } else {
    console.log('[weekly-scan] Telegram failed:', tgRes?.description || 'unknown')
  }
  console.log('[weekly-scan] Done')
  process.exit(0)
})().catch(e => {
  console.error('[weekly-scan] Fatal:', e)
  process.exit(1)
})
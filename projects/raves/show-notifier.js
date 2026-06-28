#!/usr/bin/env node
/**
 * show-notifier.js
 * Checks today's Going shows and sends Telegram notifications.
 * Run via cron — handles both morning (day-of) and evening (show time) alerts.
 */

const http = require('http');
const https = require('https');

const API_BASE = process.env.RAVES_API || 'http://localhost:3004';
const AUTH_TOKEN = process.env.RAVES_TOKEN || '22b02ae68c1d0827b262cf1d0d09621a238ec7670b724b78f63d494be42617d4';
const TG_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const TG_CHAT = process.env.TELEGRAM_CHAT_ID || '5574760589';

function apiGet(path) {
  return new Promise((resolve, reject) => {
    const url = `${API_BASE}${path}`;
    const mod = url.startsWith('https') ? https : http;
    const req = mod.get(url, { headers: { Authorization: `Bearer ${AUTH_TOKEN}` } }, res => {
      let body = '';
      res.on('data', d => body += d);
      res.on('end', () => {
        try { resolve(JSON.parse(body)); } catch(e) { reject(e); }
      });
    });
    req.on('error', reject);
  });
}

function sendTelegram(text) {
  if (!TG_TOKEN) { console.log('[NO TG TOKEN] Would send:', text); return Promise.resolve(); }
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify({ chat_id: TG_CHAT, text, parse_mode: 'Markdown' });
    const req = https.request({
      hostname: 'api.telegram.org',
      path: `/bot${TG_TOKEN}/sendMessage`,
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payload) }
    }, res => {
      let b = ''; res.on('data', d => b += d);
      res.on('end', () => { console.log('TG sent:', res.statusCode); resolve(b); });
    });
    req.on('error', reject);
    req.end(payload);
  });
}

async function main() {
  const mode = process.argv[2] || 'morning'; // 'morning' | 'evening'
  const today = new Date().toISOString().slice(0, 10);

  let data;
  try {
    data = await apiGet('/api/events');
  } catch(e) {
    console.error('Failed to fetch events:', e.message);
    process.exit(1);
  }

  const events = Array.isArray(data) ? data : (data.events || []);
  const todayShows = events.filter(e => {
    if (e.interest !== 'going') return false;
    return e.date && e.date.startsWith(today);
  });

  if (todayShows.length === 0) {
    console.log(`No Going shows today (${today}), skipping.`);
    return;
  }

  for (const show of todayShows) {
    const hasCost = show.cost > 0;
    const attended = show.attended;

    if (mode === 'morning') {
      // Day-of morning reminder
      const costLine = hasCost
        ? `💳 Ticket: *$${show.cost}* — paid`
        : `🎟 Ticket status: *not logged* — did you pay?`;

      const msg = [
        `🎉 *Tonight: ${show.name}*`,
        `📍 ${show.venue}`,
        show.genres && show.genres.length ? `🎵 ${show.genres.join(', ')}` : null,
        ``,
        costLine,
        show.notes ? `📝 ${show.notes}` : null,
        ``,
        `_Have a great night_ 🖤`,
      ].filter(l => l !== null).join('\n');

      await sendTelegram(msg);

    } else if (mode === 'evening') {
      // Evening wrap-up / post-show check-in
      if (attended) {
        console.log(`${show.name} already marked attended, skipping evening alert.`);
        continue;
      }

      const costLine = hasCost
        ? `💰 You spent *$${show.cost}* on this`
        : `💳 No ticket cost logged`;

      const msg = [
        `🌙 *How was ${show.name}?*`,
        `📍 ${show.venue}`,
        ``,
        costLine,
        ``,
        `Mark it attended in Groundfloor to track your spend → https://groundfloor-nyc.vercel.app`,
      ].filter(l => l !== null).join('\n');

      await sendTelegram(msg);
    }
  }

  console.log(`Done — notified ${todayShows.length} show(s) for ${today} (mode: ${mode})`);
}

main().catch(e => { console.error(e); process.exit(1); });

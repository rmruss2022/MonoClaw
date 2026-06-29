/**
 * In-process scheduler for Groundfloor.
 * Ticks every minute and fires jobs gated on America/New_York wall time.
 * Each job runs at most once per ET calendar day.
 *
 * Jobs:
 *   morning_notify        — daily 10:00 ET, push "Tonight: …"
 *   evening_wrap          — daily 23:00 ET, push "How was …?"
 *   weekly_scan_reminder  — Monday 09:00 ET, push "New week! Scan…"
 */

const {
  getGoingShowsForDate,
  getAllPushSubscriptions,
  recordSchedulerRun,
  getSchedulerLatestByJob
} = require('./db');
const { sendPush } = require('./push');

const ET_FORMATTER = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York',
  year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', weekday: 'long',
  hour12: false, hourCycle: 'h23'
});

function nowInET() {
  const parts = ET_FORMATTER.formatToParts(new Date());
  const map = {};
  for (const p of parts) if (p.type !== 'literal') map[p.type] = p.value;
  return {
    date: `${map.year}-${map.month}-${map.day}`,
    hour: parseInt(map.hour, 10) % 24,
    minute: parseInt(map.minute, 10),
    dayOfWeek: map.weekday
  };
}

async function runMorningNotify() {
  const et = nowInET();
  const shows = getGoingShowsForDate(et.date);
  if (shows.length === 0) {
    return { status: 'skipped', details: `no going shows for ${et.date}` };
  }
  const subs = getAllPushSubscriptions();
  if (subs.length === 0) {
    return { status: 'skipped', details: `${shows.length} show(s) but no push subs` };
  }
  let sent = 0, failed = 0;
  for (const show of shows) {
    const body = `${show.venue}${show.cost > 0 ? ` · $${show.cost} paid` : ' · no ticket logged'}`;
    const r = await sendPush({ title: `Tonight: ${show.name} 🎉`, body, url: '/', tag: `show-${show.id}` }, subs);
    sent += r.sent; failed += r.failed;
  }
  return { status: 'success', details: `${shows.length} show(s), pushed to ${subs.length} sub(s), sent=${sent} failed=${failed}` };
}

async function runEveningWrap() {
  const et = nowInET();
  const shows = getGoingShowsForDate(et.date);
  if (shows.length === 0) {
    return { status: 'skipped', details: `no going shows for ${et.date}` };
  }
  const subs = getAllPushSubscriptions();
  if (subs.length === 0) {
    return { status: 'skipped', details: `${shows.length} show(s) but no push subs` };
  }
  let sent = 0, failed = 0;
  for (const show of shows) {
    const costLine = show.cost > 0 ? `$${show.cost} ticket` : 'no ticket logged';
    const body = `${show.venue} · ${costLine} · mark attended`;
    const r = await sendPush({ title: `How was ${show.name}?`, body, url: '/', tag: `wrap-${show.id}` }, subs);
    sent += r.sent; failed += r.failed;
  }
  return { status: 'success', details: `${shows.length} show(s), pushed to ${subs.length} sub(s), sent=${sent} failed=${failed}` };
}

async function runWeeklyScanReminder() {
  const subs = getAllPushSubscriptions();
  if (subs.length === 0) {
    return { status: 'skipped', details: 'no push subs' };
  }
  const r = await sendPush({
    title: 'New week! Scan for fresh events 🔍',
    body:  'Tap to pull this week’s NYC drops from RA + Dice.',
    url:   '/',
    tag:   'weekly-scan-reminder'
  }, subs);
  return { status: 'success', details: `pushed to ${subs.length} sub(s), sent=${r.sent} failed=${r.failed}` };
}

const JOBS = {
  morning_notify: {
    label: 'MORNING NOTIFY',
    description: 'Daily 10:00 AM ET',
    hour: 10, minute: 0, dayOfWeek: null,
    handler: runMorningNotify
  },
  evening_wrap: {
    label: 'EVENING WRAP-UP',
    description: 'Daily 11:00 PM ET',
    hour: 23, minute: 0, dayOfWeek: null,
    handler: runEveningWrap
  },
  weekly_scan_reminder: {
    label: 'WEEKLY SCAN',
    description: 'Monday 9:00 AM ET',
    hour: 9, minute: 0, dayOfWeek: 'Monday',
    handler: runWeeklyScanReminder
  }
};

const lastAutoRanET = {};

function shouldFire(job, et) {
  if (job.dayOfWeek && et.dayOfWeek !== job.dayOfWeek) return false;
  return et.hour === job.hour;
}

async function runJob(jobName, { manual = false } = {}) {
  const job = JOBS[jobName];
  if (!job) throw new Error(`Unknown job: ${jobName}`);
  let result;
  try {
    result = await job.handler();
  } catch (e) {
    result = { status: 'failed', details: e.message };
  }
  const detailWithMode = `${manual ? '[manual] ' : ''}${result.details || ''}`;
  recordSchedulerRun(jobName, result.status, detailWithMode);
  return { ...result, details: detailWithMode };
}

async function tick() {
  const et = nowInET();
  for (const [jobName, job] of Object.entries(JOBS)) {
    if (!shouldFire(job, et)) continue;
    if (lastAutoRanET[jobName] === et.date) continue;
    lastAutoRanET[jobName] = et.date;
    try {
      await runJob(jobName, { manual: false });
    } catch (e) {
      console.error(`[scheduler] ${jobName} crashed:`, e.message);
    }
  }
}

function hydrateLastRan() {
  for (const jobName of Object.keys(JOBS)) {
    const latest = getSchedulerLatestByJob(jobName);
    if (!latest) continue;
    const ranAtEt = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/New_York',
      year: 'numeric', month: '2-digit', day: '2-digit'
    }).format(new Date(latest.ran_at + (latest.ran_at.endsWith('Z') ? '' : 'Z')));
    lastAutoRanET[jobName] = ranAtEt;
  }
}

function nextRunET(jobName) {
  const job = JOBS[jobName];
  if (!job) return null;
  const et = nowInET();
  const todayMatchesDow = !job.dayOfWeek || job.dayOfWeek === et.dayOfWeek;
  const beforeWindow = et.hour < job.hour;
  const alreadyRanToday = lastAutoRanET[jobName] === et.date;
  if (todayMatchesDow && beforeWindow && !alreadyRanToday) {
    return `${et.date} ${String(job.hour).padStart(2,'0')}:${String(job.minute).padStart(2,'0')} ET (today)`;
  }
  if (!job.dayOfWeek) {
    return `tomorrow ${String(job.hour).padStart(2,'0')}:${String(job.minute).padStart(2,'0')} ET`;
  }
  const daysOfWeek = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  const todayIdx = daysOfWeek.indexOf(et.dayOfWeek);
  const targetIdx = daysOfWeek.indexOf(job.dayOfWeek);
  let delta = (targetIdx - todayIdx + 7) % 7;
  if (delta === 0) delta = 7;
  return `${job.dayOfWeek} in ${delta} day${delta === 1 ? '' : 's'} ${String(job.hour).padStart(2,'0')}:${String(job.minute).padStart(2,'0')} ET`;
}

function listJobs() {
  return Object.entries(JOBS).map(([name, job]) => ({
    name,
    label: job.label,
    description: job.description,
    nextRun: nextRunET(name),
    lastAutoRanET: lastAutoRanET[name] || null
  }));
}

let tickHandle = null;
function start() {
  if (tickHandle) return;
  hydrateLastRan();
  tick().catch(e => console.error('[scheduler] initial tick error:', e.message));
  tickHandle = setInterval(() => {
    tick().catch(e => console.error('[scheduler] tick error:', e.message));
  }, 60 * 1000);
  console.log('[scheduler] started — morning_notify, evening_wrap, weekly_scan_reminder');
}

function stop() {
  if (tickHandle) { clearInterval(tickHandle); tickHandle = null; }
}

module.exports = { start, stop, runJob, listJobs, nowInET, JOBS };

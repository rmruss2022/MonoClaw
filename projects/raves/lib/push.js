const webpush = require('web-push');
const { getAllPushSubscriptions, deletePushSubscription } = require('./db');

const VAPID_PUBLIC  = process.env.VAPID_PUBLIC_KEY  || 'BGuXKKtbvv8ldpJw7WWZcVDEembRyZdHVb3BQRp9tcG1TgVcdac2s1Umgvgw7VAQ-ltU8oOLJJ2RVdXdwvfsQfw';
const VAPID_PRIVATE = process.env.VAPID_PRIVATE_KEY || 'tGofMLaKJhQTXAym26Cvey1zZm1N2dLF8_KhTvtfAgg';
const VAPID_EMAIL   = 'mailto:admin@groundfloor.nyc';

webpush.setVapidDetails(VAPID_EMAIL, VAPID_PUBLIC, VAPID_PRIVATE);

/**
 * Send a push notification to all subscribers (or a specific user's subs).
 * @param {object} payload  { title, body, icon, url, tag }
 * @param {Array}  subs     optional array of sub rows; defaults to all
 */
async function sendPush(payload, subs) {
  const targets = subs || getAllPushSubscriptions();
  const notification = JSON.stringify({
    title: payload.title,
    body:  payload.body,
    icon:  payload.icon  || '/icons/icon-192.png',
    badge: payload.badge || '/icons/icon-72.png',
    url:   payload.url   || '/',
    tag:   payload.tag   || 'groundfloor',
  });

  const results = { sent: 0, failed: 0, removed: 0 };
  for (const sub of targets) {
    try {
      await webpush.sendNotification(
        { endpoint: sub.endpoint, keys: { p256dh: sub.p256dh, auth: sub.auth } },
        notification
      );
      results.sent++;
    } catch (err) {
      if (err.statusCode === 410 || err.statusCode === 404) {
        // Subscription expired/gone — clean up
        deletePushSubscription(sub.endpoint);
        results.removed++;
      } else {
        console.error('[push] Failed:', err.message);
        results.failed++;
      }
    }
  }
  return results;
}

module.exports = { sendPush, VAPID_PUBLIC };

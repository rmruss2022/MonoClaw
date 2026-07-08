const { sendPush } = require('./push');
const { getChatMembersWithSubs, getPushSubscriptionsByUser } = require('./db');

async function notifyChatSubscribers(threadId, eventId, eventName, authorName, messageBody, excludeUserId) {
  const members = getChatMembersWithSubs(threadId);
  const targets = [];
  for (const m of members) {
    if (excludeUserId != null && m.user_id === excludeUserId) continue;
    const subs = getPushSubscriptionsByUser(m.user_id);
    for (const s of subs) targets.push(s);
  }
  if (targets.length === 0) return { sent: 0, failed: 0, removed: 0 };
  const preview = (messageBody || '').slice(0, 80);
  const payload = {
    title: `New message in ${eventName} chat`,
    body: `${authorName}: ${preview}`,
    url: `/?event=${encodeURIComponent(eventId)}`,
    tag: `chat-${threadId}`
  };
  return sendPush(payload, targets);
}

module.exports = { notifyChatSubscribers };

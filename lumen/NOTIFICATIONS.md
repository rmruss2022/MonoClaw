# Lumen — Intelligent Notification Service

Design spec. Goal: the #1 retention lever, built so it never contradicts a calm
brand. Every notification does one of three jobs: **help them sit today**,
**celebrate/reflect**, or **gently reconnect**. If it does none, it doesn't send.

## 1. Architecture (two paths, one arbiter)

```
 session/complete ──▶ EVENT path ──┐
                                    ├─▶ notif_log (queued) ─▶ ARBITER ─▶ Expo push
 scheduler tick (15m) ─ TIME path ─┘        (caps · quiet hours · dedupe · prefs)
```

- **Event path** (immediate, positive): on a completed session we enqueue
  celebrations — level-up, achievement unlocked, streak milestone, league
  promotion. Written to `notif_log` as `queued`.
- **Time path** (periodic): every 15 min a daemon thread evaluates each opted-in
  user for time-based candidates — daily reminder (send-time optimized),
  streak-save, weekly recap, tiered win-back.
- **Arbiter**: both paths funnel through one gate — per-user daily cap, quiet
  hours (local), per-category dedupe key, and user category prefs. Highest
  priority candidate wins; the rest are dropped or deferred.

## 2. Data model

- `push_tokens(user_id, token UNIQUE, platform, created, updated)` — Expo push tokens.
- `notif_prefs(user_id PK, enabled, quiet_start=21, quiet_end=8, tz_offset_min,
  cats JSON, sto=1, updated)` — per-user controls; category mutes.
- `notif_log(id, user_id, category, title, body, dedupe_key, status, created,
  sent, opened)` — every candidate; powers dedupe, caps, and admin metrics.

## 3. Intelligence — the "what & when"

- **Engagement tier** from `last_day`/sessions: `new · habitual · at_risk (3-6d)
  · dormant (7-29d) · churned (30d+)`. Drives both content and frequency.
- **Send-Time Optimization**: target hour = the user's modal session hour
  (from history); fall back to a 19:00-local default until data exists. The
  daily reminder fires only near that hour.
- **State awareness**: never send "time to meditate" if they already sat today.
- **Responsiveness**: open rate per category feeds fatigue back-off (future).

## 4. Catalog (priority — higher sends first)

| category | prio | trigger | dedupe |
|---|---|---|---|
| streak_save | 100 | active streak ≥2, not sat today, evening | per day |
| progress (event) | 90 | level-up / achievement / milestone | per event |
| weekly_recap | 80 | Sun evening, sat ≥1 this week | per week |
| daily_reminder | 60 | not sat today, at STO hour | per day |
| winback | 40 | dormant/churned, rate-limited | per period |

## 5. Governance (protects the brand)

- **Caps**: ≤1 automatic/day, celebrations get a small separate allowance; ≤7/wk.
- **Quiet hours**: default 21:00–08:00 local; never wake anyone.
- **Granular opt-out** by category (keeps full unsubscribes low).
- **Permission prompt** timed after the first good session, not on first launch.
- **Holdout**: a never-notify control cohort to measure true incremental lift.

## 6. Voice

Calm, warm, direct, short, second-person — never guilt. Personalized with name,
streak, guide, local time-of-day. Copy is **template-first** (predictable) with
an optional **Gemini personalization** layer (best-effort, 6s timeout, template
fallback) for the daily reminder and win-back.

## 7. Channels

- **Push** (primary) via Expo Push API (`exp.host/--/api/v2/push/send`). The
  native app obtains the Expo token and hands it to the web layer, which
  registers it against the logged-in account (`/api/push/register`).
- **In-app** cards + **email** digests are future channels.

## 8. Delivery wiring (Expo ↔ web ↔ server)

1. Native app (`expo-notifications`) requests permission, gets `ExponentPushToken`.
2. Native injects it into the WebView → `window.__onPushToken(token)`.
3. Web posts it to `/api/push/register` (associates with the session's user).
4. Tapping a push deep-links into the relevant screen.

## 9. Metrics

Opt-in rate · per-category open/CTR · notification-attributed sessions ·
D1/D7/D30 retention lift vs holdout · mute/unsubscribe rate. Surfaced in the
admin **Notifications** tab.

## 10. Roadmap

- **v1 (this build)**: schema, engine (all 5 categories), caps + quiet hours +
  dedupe, Expo push send, registration plumbing, admin tab, template copy +
  optional Gemini. Rules-based and explainable.
- **v2**: multi-armed bandit on copy/time, churn-propensity win-back tiering.
- **v3**: predictive churn model, fully Gemini-personalized copy grounded in the
  user's journal/journey history.

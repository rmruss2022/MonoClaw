# Lumen 1.0 — App Review Notes (resubmit after Guideline 2.1 Information Needed)

Paste the block below into **App Store Connect → Lumen → 1.0 → App Review Information → Notes**,
re-attach the demo account, add the screen recording (see bottom), then **resubmit** (no new build required).

---

## DEMO ACCOUNT
Email: appreview@lumen.app
Password: LumenReview!2026
(Single account type. You may also tap "Create an account" to make a fresh one.)

---

## NOTES FIELD (paste verbatim)

PURPOSE & AUDIENCE
Lumen is a meditation and mindfulness app. It helps people build a calm daily
meditation habit and feel less alone in it: alongside timed sessions, guided
audio journeys, and a private journal, Lumen shows a live world map where each
meditation appears as an anonymized point of light, so users can see they are
part of a global community meditating at the same time. Target audience is a
general 4+ wellness audience; no account of a specific organization is required.

HOW TO SET UP & ACCESS MAIN FEATURES
1. Launch the app. Sign in with the demo account above, or tap "Create an account".
2. Meditate tab — choose a duration and tap Begin to run a timed session.
3. Map tab — a world map of anonymized glows from recent sessions worldwide.
4. Journeys tab — guided audio lessons; tap one to play the narrated audio.
5. Journal tab — write and review private reflection entries.
6. Community feed — optional social feed. Posts include a Report control and a
   Block control on each item (report sends content for moderation; block hides
   a user). Endpoints: /api/feed/report and /api/feed/block.
7. You (profile) tab — settings, notification preferences, and "Delete account",
   which permanently deletes the account and all associated data (profile,
   sessions, journal, progress) and cannot be undone.

Location, camera, and photo access are all OPTIONAL. Location only places an
anonymized glow on the map; the app is fully functional with all of them denied.

EXTERNAL SERVICES USED
- Railway — cloud hosting for Lumen's own first-party backend, which stores
  accounts, sessions, and journal data. Authentication is email/password handled
  by our own server (no third-party login provider).
- Google Gemini API — generates personalized guided-meditation and reflection
  text content.
- ElevenLabs — AI text-to-speech that voices the guided audio.
- Leaflet with OpenStreetMap map tiles — renders the world map.
- Expo Push Notifications / Apple APNs — optional reminder notifications.
No in-app purchases, no payment processor, no third-party ads, and no analytics
SDKs are used.

REGIONAL DIFFERENCES
The app functions consistently across all regions. There is no region-locked
content and no regional feature gating. UI is English.

REGULATED INDUSTRY / THIRD-PARTY MATERIAL
Lumen is a general wellness app and does not operate in a regulated industry
(it is not a medical, financial, or similar regulated service) and makes no
medical claims. All meditation content is either self-produced or AI-generated;
it contains no protected third-party material requiring authorization.

ACCOUNT DELETION
Supported in-app: You (profile) tab → Delete account. This permanently removes
the account and all associated data and cannot be undone.

---

## SCREEN RECORDING (item 1 — the one thing that needs your iPhone)
Record on a physical iPhone running the latest iOS, from the installed TestFlight
build. Start by launching the app, then show this flow in one take:
1. App launch from the Home screen (tap icon → load).
2. Sign in with the demo account (or Create an account) — show the login/registration.
3. Meditate tab: pick a duration, tap Begin, show the session running.
4. Map tab: show the world map with glows.
5. Journeys tab: open a guided lesson, show the audio playing.
6. Journal tab: add/view an entry.
7. Community feed: open a post and SHOW the Report and Block controls.
8. You (profile) tab: tap Delete account and show the confirm step (you can
   cancel before it actually deletes, but show that the control is real).

Attach the video via App Store Connect's App Review Information attachment, or
upload it somewhere and paste a direct link at the top of the Notes field.

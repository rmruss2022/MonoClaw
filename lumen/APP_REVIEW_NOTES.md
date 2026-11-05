# Lumen — App Review Notes (Guideline 2.1 resubmission)

Paste the block below into **App Store Connect → App Review Information → Notes**,
add the demo-video link, and resubmit the existing build (no new build required).

---

Demo account (required): appreview@lumen.app  /  LumenReview!2026
(You can also tap "Create an account" to make a fresh one.)

DEMO VIDEO (screen recording, physical device, latest iOS): <PASTE UNLISTED LINK HERE>

1) PURPOSE & AUDIENCE
Lumen is a meditation & mindfulness app for anyone building a calm daily practice —
from first-timers to experienced meditators. It lowers the friction of a daily habit
with quick-to-start timed sessions, ambient soundscapes, guided audio journeys, a
reflective journal, and light gamification (streaks, collectibles, and a world map of
recent sessions). Value: a beautiful, low-pressure way to meditate consistently and
see your progress.

2) SETTING UP & ACCESSING MAIN FEATURES
- Sign in with the demo account above, or tap "Create an account" (email + password).
- Meditate: choose a duration, tap Begin; a timed session runs with a soundscape.
- Map: a world map of recent meditation sessions (approximate city-level only; precise
  location is optional and never required).
- Journeys: guided audio lessons/courses.
- Journal: write reflections; optionally photograph handwritten notes (AI transcribes).
- Profile ("You" tab): streaks/stats, collectibles, and "Delete account".
- Account deletion: "You" tab → "Delete account" → confirm. Permanently removes the
  account and all associated data (profile, sessions, journal, progress).

3) EXTERNAL SERVICES USED
- Lumen's own backend + SQLite database (hosted on Railway): accounts, sessions,
  journal, progress.
- Google Gemini (AI): generates short reflective text and transcribes handwritten
  journal photos.
- ElevenLabs (AI text-to-speech): server-side narration audio for guided content.
- Esri/ArcGIS public basemap tiles: the map background (keyless, no account).
No third-party ads or analytics SDKs; no third-party/social login.

4) USER CONTENT — REPORTING & BLOCKING
Where a user can see another user's content, each item provides Report and Block
controls; a blocked user's content is hidden from the blocker.

5) REGIONAL DIFFERENCES
None — the app behaves identically in all regions. Interface is in English. No
region-locked features or content.

6) REGULATED INDUSTRY / THIRD-PARTY MATERIAL
Lumen is a general wellness/relaxation app. It makes no medical claims and does not
diagnose, treat, or cure any condition. All audio, text, imagery, and music are
original/owned or app-generated; no protected third-party material is used.

IN-APP PURCHASES: none. Cosmetic items and companions are unlocked with an in-app
earned currency ("Motes"), not real money. There is no real-money purchase flow.

---

## Recording shot-list (≈60–120s, start from a cold launch, physical device)
1. Launch the app (cold) → onboarding / welcome screen.
2. Create an account (or log in with the demo account) → allow/skip location.
3. Meditate: pick a duration → Begin → show the session running → finish.
4. Map: open the world map of sessions.
5. Journeys: open a guided lesson.
6. Journal: add an entry.
7. If others' content is visible: show the Report and Block controls on an item.
8. Profile ("You") → Delete account → confirm → show it returns to signed-out.

## How to send the video
The Notes field is text-only — you cannot attach a video there. Upload the recording
to an unlisted link (unlisted YouTube / Dropbox / Google Drive with link-sharing) and
paste that URL into the Notes field (and/or reply in Resolution Center with the file
attached). Then tap Resubmit on the rejected version.

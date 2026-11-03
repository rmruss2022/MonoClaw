# Trip Sync (Travelog) — App Review Notes

Paste into **App Store Connect → App Review Information → Notes** when submitting.
Privacy Policy URL (already set in ASC): https://travelog-production.up.railway.app/privacy

---

PURPOSE & AUDIENCE
Trip Sync (Travelog) is a travel journal. You create a trip, add the places you
go and journal entries, and attach photos — and the app maps your trip from the
photos' locations and helps you write it up. For travelers who want a beautiful,
living record of a trip and, optionally, to keep it with the people they
travelled with.

NO LOGIN / NO ACCOUNT
There is no account system or password — you just pick a display name. So no
demo credentials are needed to review the app; it opens straight into use. (A
device-based identity tags the content you add so a shared trip can credit each
contributor.)

HOW TO USE THE MAIN FEATURES
1. Launch → you land on Places. Tap "New trip", give it a title.
2. Add a place (Places tab) or upload photos (Photos tab). Photos taken with
   location on are auto-placed on the Map.
3. Map tab: see your trip plotted from your places/photos.
4. Memories tab: AI-written recaps and a shareable trip card.
5. Chat tab: an AI travel companion for the trip.
6. Split tab: track shared trip expenses and who owes whom (real-world costs,
   not digital goods).
7. Share: invite others by link to co-author a trip (each contribution credited).
8. You (in the share/crew sheet): edit your name, Sign out, or Delete my data
   (permanently removes you from your trips and erases the photos + entries you
   added).

NATIVE DEVICE FEATURES (re: Guideline 4.2)
Trip Sync integrates directly with the device: Camera and Photo Library (add
trip photos), Location (place entries/photos on the map; fully optional),
Microphone (voice notes), and it installs as a home-screen app with offline
caching. It is not a generic web page — it is a photo/location journaling tool
that uses these native capabilities as its core.

EXTERNAL SERVICES
- Our own server + SQLite database (hosted on Railway) — trips, entries, photos.
- Google Gemini (AI) — generates trip recaps and reads text from photos you add.
- ElevenLabs (AI text-to-speech) — optional narration.
- Esri/ArcGIS public map tiles — the map background (keyless).
No third-party ads or analytics SDKs; no third-party/social login.

IN-APP PURCHASES
None. There are no purchases of digital content. (Expense splitting tracks
real-world trip costs between friends.)

REGIONS
Functions identically in all regions; interface in English.

CONTENT SHARING
Trips are private to you unless you create a share link and give it to people
you choose. There is no public feed or discovery of strangers' content.

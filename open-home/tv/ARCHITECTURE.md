# openhome TV — architecture

**One box. Your whole living room. One search across everything.**

openhome TV is a Fire-Stick-class **streaming stick** you own, plus the clients and
cloud glue that make it a *universal* remote for content: one search that spans
Netflix, Prime, Disney+, YouTube, Spotify, Plex, Jellyfin, … and launches the right
app to the right title — from the TV or your phone.

It is a sibling of the openhome hub, and reuses the same account + routing model
(sign in once at the control-plane, get routed to *your* devices).

---

## The hard truth that shapes the design

Streaming services **do not** expose open "search the catalog and press play" APIs,
and scraping their private ones gets you blocked and is against ToS. So the system
is built on the pattern every universal-search product actually uses:

1. **Metadata** — titles, posters, cast, year, overview, ratings — from an open
   metadata provider (**TMDB**).
2. **Availability + deep links** — *which* services carry a title in the user's
   region, and the **deep-link URI** to open it — from an availability aggregator
   (**Watchmode** / JustWatch-class).
3. **Launch** — open the chosen app **on the stick** to that exact title via an
   **Android deep-link intent** (the stick is Android TV), falling back to opening
   the app's search if no title-level deep link exists.

We never store or proxy copyrighted streams. We route *intent*, not content.

---

## Components

```
                       ┌───────────────────────────────┐
                       │   openhome-cloud control-plane │  (existing)
                       │   accounts · device directory  │
                       └───────────────┬───────────────┘
                                       │ routing grant (home/stick token)
         ┌─────────────────────────────┼──────────────────────────────┐
         │                             │                               │
┌────────▼─────────┐        ┌──────────▼───────────┐         ┌─────────▼────────┐
│  iOS app          │        │  content-router svc   │         │  TV stick client │
│ (phone remote +   │  REST  │ (this repo)           │   WS    │ (Android TV app) │
│  search + cast)   ├───────►│ search · details ·    │◄───────►│ browse · play ·  │
│                   │        │ availability · route  │ control │ now-playing      │
└───────────────────┘        │ · sessions · sticks   │         └──────────────────┘
                             └───────┬───────┬───────┘
                            TMDB ◄───┘       └───► Watchmode / JustWatch
                          (metadata)             (availability + deep links)
```

- **content-router service** (`tv/services/router`) — the engine. Unified search
  across providers, title detail + availability + deep-link resolution, the
  **routing algorithm** (pick the best source for *this* user on *this* stick),
  user sessions, stick registry, and a **control channel** (WebSocket) so the phone
  can "cast" a title to the stick and see now-playing. Zero-dependency Node 22 +
  `node:sqlite`, deploys on Railway next to `openhome-cloud`.

- **TV stick client** (`tv/apps/stick`) — the on-device app the stick boots into.
  Android TV (Leanback-style) so it runs on real stick hardware (Amlabs/Rockchip
  boxes, or sideloaded onto a Fire TV). Built with **react-native-tvos** to share
  TypeScript + design tokens with the phone app. Renders the home rails, the
  universal search, title pages, and executes **deep-link intents** to launch the
  streaming apps. Holds a persistent WS to the router for remote "cast" + control.

- **iOS app** (`tv/apps/ios`) — the phone as a **remote + search surface**: type
  (or dictate) a search, see unified results with availability, tap a title → it
  **casts to the stick** (router tells the stick to launch it), plus a D-pad/remote
  and now-playing. Reuses the openhome account + theme.

---

## Data flow — "find and play Dune on the living-room stick"

1. Phone/stick calls `GET /search?q=dune` → router fans out to TMDB (metadata) +
   Watchmode (availability), merges, returns ranked `Title[]` with a `sources[]`
   array (service, type: sub|rent|buy|free, price, deepLink).
2. User selects a title → `GET /title/:id` → full detail + the resolved
   `sources[]` filtered to the user's **owned apps/subscriptions** and region.
3. **Route**: `POST /route { titleId, stickId }` → the router runs the routing
   algorithm (below) to pick one source, then pushes a `launch` command over the
   stick's WS with the deep-link intent.
4. Stick fires the Android intent → the streaming app opens to the title. Stick
   reports `now-playing` back up the WS; phone shows it.

### Routing algorithm (pick the best source)
Given a title's `sources[]`, the user's `ownedServices`, prefs, and the stick's
`installedApps`:
1. Filter to sources whose app is **installed on the stick** and **in region**.
2. Prefer **included-with-subscription** the user already pays for (cost 0).
3. Else free-with-ads, else cheapest rent, else buy — respecting a user
   preference order (e.g. "prefer Plex/Jellyfin for owned media first").
4. Prefer a **title-level deep link**; fall back to app search deep link.
5. Ties broken by quality (4K/HDR flag) then provider preference list.

---

## Sessions & routing (reuses openhome identity)

- A **stick** pairs to an account with a short code (like the hub claim flow):
  stick shows a code → entered in the phone app → control-plane binds
  `account → stick{ id, name:"Living Room", region }`.
- The phone and stick both authenticate to the router with the account's grant;
  the router authorizes "this account may control these sticks."
- The **control channel** is a per-stick WebSocket room; only grants for that
  account's stick may join.

## Backend API (content-router)

| Route | Method | Purpose |
|-------|--------|---------|
| `/health` | GET | liveness + provider readiness |
| `/search?q=&type=&region=` | GET | unified ranked results across providers |
| `/title/:id` | GET | full detail + resolved sources/deep links |
| `/trending?type=` | GET | home-rail content |
| `/sticks` | GET | this account's paired sticks + online state |
| `/sticks/pair` | POST | begin/complete stick pairing (code) |
| `/route` | POST | choose a source + cast to a stick |
| `/stick/:id/command` | POST | remote keys / play / pause / home |
| `/ws` | WS | stick control channel (launch, now-playing, keys) |

## Providers (pluggable)
`providers/*.ts` implement a common `MetadataProvider` / `AvailabilityProvider`
interface. **TMDB** (metadata) and **Watchmode** (availability) activate with API
keys; a built-in **sample** provider returns a small real dataset so the system
runs and demos with **zero keys**.

## Tech choices
- **Stick OS: Android TV** — it's what a Fire-Stick-class device actually runs,
  supports sideloading + deep-link intents, and is open enough for the openhome
  ethos. (A locked tvOS/Apple TV couldn't be our "own" stick.)
- **Clients: react-native-tvos** — one language/design system across stick + phone.
- **Backend: zero-dep Node 22 + node:sqlite** — matches the hub/cloud, trivial
  Railway deploy.
- **Deep-link registry** (`deeplinks.ts`) — per-app package ids + URI templates,
  the part that makes "launch to the exact title" real.

## Phases
- **P1 (this commit):** content-router engine — search/details/trending across a
  provider abstraction (TMDB + sample), availability + deep-link resolution, the
  routing algorithm, stick registry + WS control channel, sessions. Client
  scaffolds wired to it.
- **P2:** real Watchmode/JustWatch availability + region handling; stick pairing
  UX; phone "cast" flow end-to-end; now-playing.
- **P3:** on-stick app-inventory detection; voice search; personal media (Plex/
  Jellyfin) first-class; subscription tracking; recommendations.
- **P4:** reference stick hardware image + one-command flash (sibling of the
  openhome box).

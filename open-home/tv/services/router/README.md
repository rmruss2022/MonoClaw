# openhome content-router

The engine behind openhome TV: **one search across every platform**, availability
+ deep-link resolution, a routing algorithm that casts a title to the right app on
your stick, and a per-stick control channel. Zero-dependency Node 22 + `node:sqlite`.

## Run

```bash
cd open-home/tv/services/router
HOME_TOKEN_SECRET=<same-as-cloud-and-hub> npm start   # :8090
# optional live data:
TMDB_API_KEY=... npm start
```

With no provider keys it serves a built-in **sample** catalog so everything runs
and demos. Set `TMDB_API_KEY` and metadata + availability go live automatically.

## API

| Route | Auth | Purpose |
|-------|------|---------|
| `GET /health` | — | liveness + which providers are active |
| `GET /search?q=&type=&region=` | — | unified ranked results with `sources[]` |
| `GET /title/:id` | — | full detail + resolved sources |
| `GET /trending?type=` | — | home-rail content |
| `POST /sticks/pair/begin` `{stickId,name}` | — (stick) | start pairing → 6-digit code |
| `POST /sticks/pair/claim` `{code}` | account | phone binds the stick to the account |
| `GET /sticks` | account | this account's sticks + online state |
| `POST /stick/:id/apps` `{installed,owned}` | account | stick reports installed apps / subs |
| `POST /route` `{titleId,stickId,prefer?}` | account | choose a source + cast to the stick |
| `POST /stick/:id/command` `{cmd}` | account | remote keys / transport → stick |
| `GET /stick/:id/stream` (SSE) | account | stick control channel (`launch`, `command`) |
| `POST /stick/:id/event` | account | stick → server now-playing |
| `GET /stick/:id/nowplaying` | account | latest now-playing + online |

**Auth** reuses the openhome account grant: present the control-plane home token
as `Authorization: Bearer <token>` (verified locally via the shared
`HOME_TOKEN_SECRET`). Content endpoints are public; stick control requires the grant.

## Routing algorithm (`engine.chooseSource`)
Given a title's `sources[]`, the stick's installed apps, and the account's owned
subscriptions: filter to installed → prefer an **owned subscription** → then
cheapest offer (sub < free < rent < buy) → then price → then a **title-level deep
link** over app-search → then user preference order. Emits a launchable deep-link
URI + Android package.

## Integrations — how "real" each one is

A streaming stick doesn't have a secret "play Netflix" API — neither does Fire TV.
It runs the **real apps** and **deep-links** into them, driven by an availability
database. So integrations come in two honest tiers:

**Tier 1 — deep-link + the real installed app** (Netflix, Hulu, Disney+, Max,
Prime, Peacock, Paramount+, Tubi, Apple TV). Identical to how Fire TV works. The
stick runs the real Android-TV app; we open it to the exact title.
- `TMDB_API_KEY` → metadata (titles, posters, cast, trending).
- `WATCHMODE_API_KEY` → **availability + title-level Android deep links** (`android_url`).
  This is the integration that makes universal search *accurate* ("open Dune in Max
  directly" vs. "open Max's search"). Without it we fall back to app-search links.

**Tier 2 — full-API services** (`SearchContributor`s — real search *and* play,
because these expose open APIs):
- **YouTube** (`YOUTUBE_API_KEY`) — Data API search → opens the YouTube app to the video.
- **Plex** (`PLEX_URL`,`PLEX_TOKEN`) / **Jellyfin** (`JELLYFIN_URL`,`JELLYFIN_TOKEN`,
  `JELLYFIN_USER`) — *your own* media server: true browse/search/play, no walled garden.
- **Spotify** — already integrated in the openhome hub (Connect/Web API).

`providers/*.ts`: `sample` (keyless demo), `tmdb`, `watchmode`, `youtube`, `plex`,
`jellyfin`. Each activates automatically when its key/config is present; the engine
prefers Watchmode deep links and merges contributor results into search.

## Deploy
Mirror `openhome-cloud`: Railway, Nixpacks (Node 22), a volume at `/data`
(`DATA_DIR=/data`), and the shared `HOME_TOKEN_SECRET`.

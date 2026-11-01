# openhome · mobile

The native iOS/Android client for the openhome hub — an [Expo](https://expo.dev)
(SDK 49, React Native 0.72) app that talks to the same hub HTTP API the web
control surface uses. One codebase, your phone in your pocket, your house.

## What's here

| Tab | Backs onto | What it does |
|-----|-----------|--------------|
| **Home** | `/hub/status`, `/devices`, `/scenes` | Greeting, status chips, scene buttons, overview |
| **Lights** | `/lights/state`, `/lights/command` | Per-room toggle, brightness levels, all-on/off |
| **Climate** | `/climate/state`, `/climate/command` | Setpoint +/‑, mode (off/heat/cool/auto) |
| **Speakers** | `/audio/state`, `/audio/command` | Now playing, transport, play-to-room |
| **Settings** | `/health` | Hub address, connection status, sign out |

The fancy radial gesture surface and live voice capture from `control.html`
are **not** ported yet (tracked below) — those lean on web touch/mic APIs and
need native equivalents (`react-native-gesture-handler` + `expo-av`).

## Auth (cloud-routed, matches the web /sso flow)

The app signs in to the **openhome-cloud** control-plane, not the hub directly:

1. `POST {control-plane}/api/login` with email + password → session token.
2. `GET {control-plane}/api/home` (Bearer session) → `{ endpoint, homeToken }`.
3. The app talks **directly** to the hub at `endpoint`, carrying `homeToken` as
   both an `Authorization: Bearer` header and the `oh_auth` cookie. The hub
   verifies the grant locally (`validHomeToken`) — the cloud is never in the
   data path.

Home tokens live ~12h; the client silently refreshes via `/api/home` (using the
30-day control-plane session) on a 401. Control-plane URL is configurable in
Settings. See `src/api/client.ts`.

## Run it

```bash
cd open-home/apps/mobile
npm install
npm start          # Expo dev server — scan the QR with Expo Go
# or: npm run ios / npm run android / npm run web
```

On first launch, set the **Hub address** on the login screen (defaults to the
current Cloudflare tunnel; override with your LAN URL or a stable tunnel).

## Still to do

- [ ] Radial gesture control surface (native port of `control.html`)
- [ ] Voice agent — mic capture → `/agent/audio` (needs `expo-av`)
- [ ] Music browser (Spotify playlists/search) — `/audio/spotify/*`
- [ ] Push notifications (hub event feed → `expo-notifications`)
- [ ] Device pairing flows (lights/climate/speakers discover + onboard)
- [ ] App icon + splash art

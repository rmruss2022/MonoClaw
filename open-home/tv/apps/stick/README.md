# openhome TV — stick client (Android TV)

The app the stick boots into. Pairs to your account with a 6-digit code, then
listens on the content-router's SSE channel and **launches the right streaming
app to the exact title** via Android deep-link intents.

## Why Android TV / react-native-tvos
A Fire-Stick-class device runs Android TV. `react-native-tvos` is the RN fork with
TV focus/remote support, letting the stick share TypeScript + the openhome design
tokens with the phone app. Deep-link launching is just `Linking.openURL(uri)` —
Android resolves the intent to the target app (no custom native module needed for
the common services).

## Toolchain (one-time, on a machine with Android SDK)
```bash
cd open-home/tv/apps/stick
npm install                 # pulls react-native-tvos + react-native-sse
export EXPO_TV=1            # enable the TV variant
npx expo run:android        # build + install to an Android TV emulator or a stick over adb
```
Sideload onto a real stick / Fire TV with `adb connect <ip>` then `adb install`.

## What it does
- **Pairing** — on first boot (or until claimed) shows a code from
  `POST /sticks/pair/begin`, which also returns the **stick token** it uses to
  authenticate its own channel. Enter the code in the phone app.
- **Control channel** — `GET /stick/:id/stream` (SSE). Handles:
  - `launch` → `Linking.openURL(deepLink)` opens the streaming app to the title
  - `command` → remote keys / transport (P2: map to Android key events)
- **App inventory** — reports installed streaming apps via `POST /stick/:id/apps`
  so the router only routes to apps that are actually on the stick. (P3: auto-detect
  via `PackageManager`; today it's the `INSTALLED` list in `App.tsx`.)

## Config
- `ROUTER_URL` in `App.tsx` → your deployed content-router (e.g. `https://tv.bedrock.casa`).

## Still to do (P2/P3)
- [ ] Native key-event mapping for remote `command`s
- [ ] Auto-detect installed packages (PackageManager)
- [ ] On-stick search UI (D-pad) + title pages
- [ ] now-playing reporting via `POST /stick/:id/event`
- [ ] Reference stick hardware image + one-command flash

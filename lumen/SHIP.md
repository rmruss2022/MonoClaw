# Shipping Lumen — PWA today, TestFlight / App Store next

Lumen is a web app (Python stdlib server + HTML/JS). This is the path to phones.

## 0. What's already done (2026-10-12)
- Installable **PWA**: complete manifest, Apple meta tags, apple-touch-icon,
  `display: standalone`, portrait, maskable icon.
- **Service worker** (`/sw.js`): offline-capable + network-first for the app shell
  (so new builds always win online — this also fixes the stale-page-on-iPhone issue).
- → **On phones today:** open the live URL in Safari → Share → **Add to Home Screen**.
  Runs full-screen like an app. No Apple account needed.

## 1. Blockers that need YOU (gate TestFlight)
- [ ] **Apple Developer Program** membership ($99/yr). Enrollment/verification can
      take 24–48h — if not already enrolled, TestFlight cannot happen same-day.
- [ ] **Stable HTTPS host** for the backend. A shipped app CANNOT depend on the
      `loca.lt` tunnel (its interstitial + instability = instant rejection / broken app).
      Deploy `server.py` to a real host with a real domain (VPS / Railway / the droplet).
- [ ] A **Mac with Xcode** (your MacBook Pro) for the signed build + upload.

## 2. Native wrapper (Capacitor — thin WKWebView around the hosted app)
Run on the Mac, in a new folder (not inside this repo):
```
npm init -y
npm i @capacitor/core @capacitor/cli @capacitor/ios
npx cap init Lumen ai.lumen.app --web-dir=www
mkdir www && echo "redirect" > www/index.html   # placeholder; we load remote URL
```
In `capacitor.config.json` point the webview at the hosted app:
```json
{ "appId": "ai.lumen.app", "appName": "Lumen",
  "webDir": "www",
  "server": { "url": "https://<your-lumen-domain>", "cleartext": false } }
```
Then:
```
npx cap add ios
npx cap open ios   # opens Xcode
```

## 3. Xcode
- Signing & Capabilities → select your Team (from the Apple Developer account).
- Bundle Identifier: `ai.lumen.app` (or your reverse-domain).
- Set app icon (1024px) + launch screen (dark `#0b0a12` with the Lumen mark).
- Info.plist: add **`NSLocationWhenInUseUsageDescription`** (Lumen uses location for
  the world map) — required or the app crashes/rejects on the location prompt.
- Set Version (1.0) and Build (1).
- Product → Archive → Distribute App → App Store Connect → Upload.

## 4. App Store Connect
- Create the app record (same bundle id). Fill name, subtitle, description, keywords.
- **Screenshots** (6.7" + 6.1" iPhone at minimum).
- **Privacy**: Lumen collects email/password (account) + coarse location. Fill the
  privacy "nutrition label" and provide a **Privacy Policy URL** (required).
- TestFlight tab → add internal testers (your Apple ID) → they install TestFlight app
  and get the build. External testers need a light Beta App Review.

## 5. App Store review MUST-DOs (do before submitting)
- [ ] **In-app account deletion** — Guideline 5.1.1(v): any app with account signup
      MUST let users delete their account in-app. Lumen has signup but no delete yet.
      → add a "Delete account" action (profile screen + a `DELETE /api/account` route).
- [ ] **Privacy Policy** page (host a URL).
- [ ] Location permission string (step 3).
- [ ] Thin-wrapper risk (Guideline 4.2 "minimum functionality"): Lumen has real,
      native-feeling features (journeys, journal, map, leagues) so it should pass, but
      make sure it works fully offline-degraded and doesn't look like "just a website."

## Notes
- Alternative to Capacitor: **PWABuilder.com** can package the PWA into an iOS
  project too — but you still need the Apple account, hosting, and the review must-dos.
- The service worker makes either path (PWA install or webview) behave like an app.

---
name: ios-testflight
description: "Standardized non-interactive iOS build + TestFlight submit for OpenClaw Expo/EAS apps. One shared Apple Distribution cert, per-app provisioning profile, shared ASC key. Use when shipping any Claw app to TestFlight/App Store."
metadata: {"openclaw":{"emoji":"📱","requires":{"bins":["node","python3","openssl"]}}}
---

# ios-testflight

Ship any OpenClaw Expo/EAS app to TestFlight **non-interactively**. Apple's signing
model is **one distribution certificate → many per-app provisioning profiles**, so the
estate keeps ONE shared Apple Distribution cert and mints a profile per app.

## Shared assets (already provisioned — do not recreate)
- **Shared cert dir:** `/root/.openclaw/ios-creds/` → `dist.p12` (password `openclawp12`),
  `meta.json` (ids/coords), `README.md` (source of truth). Apple Distribution cert
  `U433Y79S5A`, **expires 2027-11-03**.
- **ASC API key:** `/root/.lumen-asc-api-key.p8` — id `4M5SWS426L`,
  issuer `182c0a6f-d589-4013-a89b-ec1c62ab8097`, team `CKYAQ94KAH`, seed `5RDPA99DY5`.
- **Minting script:** `/root/asc-tools/make_ios_creds.py`.
- EAS login is via `EXPO_TOKEN` (owner `tigertroll14`).

## Per-app steps

### 1. Mint build credentials (reuses the shared cert)
```bash
python3 /root/asc-tools/make_ios_creds.py <bundleId> "<App Name>" <appDir>
```
Finds/creates the ASC bundle id, mints an `IOS_APP_STORE` provisioning profile bound to
the shared cert, writes `<appDir>/credentials.json` + `<appDir>/creds/profile.mobileprovision`.
Gitignore `credentials.json` and `creds/`.

### 2. eas.json
```json
{
  "cli":    { "version": ">= 12.0.0", "appVersionSource": "remote" },
  "build":  { "production": { "autoIncrement": true,
              "ios": { "credentialsSource": "local" } } },
  "submit": { "production": { "ios": {
              "ascAppId": "<APP_STORE_CONNECT_APP_ID>",
              "ascApiKeyPath": "/root/.lumen-asc-api-key.p8",
              "ascApiKeyId": "4M5SWS426L",
              "ascApiKeyIssuerId": "182c0a6f-d589-4013-a89b-ec1c62ab8097",
              "appleTeamId": "CKYAQ94KAH" } } } }
}
```

### 3. Create the ASC app record — THE ONE MANUAL STEP
The ASC key role cannot CREATE app records (Apple returns 403). Once per new app, create
it in the ASC web UI (My Apps → **+** → New App → bundle id, name, SKU), then paste its
numeric **App ID** into `ascAppId`. After that every submit is non-interactive. (A human
with the Apple login does this, or an agent drives the ASC web UI with the user's browser.)

### 4. Build + ship
```bash
cd <appDir>
EAS_NO_VCS=1 npx eas build -p ios --profile production --auto-submit --non-interactive
```
Signing is automatic. With `ascAppId` set it uploads to TestFlight. Watch with
`npx eas build:view <buildId>` (don't block — iOS builds take 3–20 min). If you built
before the app record existed, the .ipa is still produced — submit later with
`npx eas submit -p ios --profile production --path <ipa-url>`.

## Gotchas
- `EAS_NO_VCS=1` avoids the git-worktree requirement in the shared monorepo.
- Cert nearing expiry: mint a fresh **Apple Distribution** (`DISTRIBUTION`) cert — it
  coexists with the old iOS Distribution cert, bypassing Apple's 1-cert limit — rebuild
  `dist.p12`, update `meta.json`.

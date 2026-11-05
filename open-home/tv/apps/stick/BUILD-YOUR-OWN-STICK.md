# Build your own openhome stick

The goal: a streaming stick **you own end-to-end** — your hardware, your OS image,
your launcher (openhome), and your brain/data (the self-hosted router + hub). It
launches the real native streaming apps, and talks only to *your* servers.

## The one hard constraint (read first)

The licensed DRM apps (Netflix, Hulu, Disney+, Max…) only run **natively** on
**Android TV / Fire OS** with a **Widevine L1** hardware cert. This is a studio
requirement, not an openhome one — it's true for Roku and Amazon too; nobody
"owns" those apps, they're licensed to the platform.

- **Widevine L1** → native apps, HD/4K. Comes from the board/OEM image.
- **Widevine L3** (stock Raspberry Pi, most DIY Linux) → Netflix caps at ~480p
  and Hulu/Disney often refuse. Fine for Plex/Jellyfin/YouTube/IPTV/local media.

So pick your flavor:

| Flavor | Hardware | Netflix/Hulu natively? | Ownership |
|---|---|---|---|
| **Recommended** | A **Google-certified Amlogic S905X4** box (e.g. KinHank G1, ~$70–90) — ships Widevine **L1** from the factory | ✅ yes, HD/4K | launcher + brain + data yours; OS is the vendor's certified image |
| **Purist** | Rockchip **RK3588** SBC (Orange Pi 5 / Radxa Rock 5) or **Raspberry Pi 5** + Linux | ⚠️ ~480p (**L3**) | fully open OS, most sovereign |

> ⚠️ **Correction / reality check:** bare Rockchip **RK3588 SBCs (Orange Pi 5,
> Radxa Rock 5) are Widevine *L3*, not L1** — their Android builds aren't
> Google-certified, so Netflix/Disney cap at ~480p. L1 is **not** something you
> flash on; it's a factory-provisioned hardware cert. See **WIDEVINE-L1.md** in
> this folder for how L1 actually works and how to get it. Pick the certified
> Amlogic path if you want native HD apps; pick the RK3588/Pi path if "fully open
> OS" matters more than big-studio HD (it's great for Plex/Jellyfin/YouTube/Kodi).

The rest of this guide targets the **Recommended** (certified Android TV) path.
Everything non-DRM (Plex, Jellyfin, YouTube, your own media) plays on either.

## Hardware

- A **Rockchip RK3566** (e.g. a bare board, or a cheap "H96/X96-class" box you
  repurpose) **that advertises Widevine L1 + Android TV**. Verify L1 with the
  "DRM Info" app after flashing.
- microSD / eMMC, HDMI, USB-C power, a cheap Bluetooth/IR remote (Android TV
  pairs any HID remote).
- Optional: a 3D-printed HDMI-stick enclosure for the real "stick" form factor.

## 1. Flash Android TV (AOSP)

1. Grab the Android TV image for your exact board (vendor site or the Armbian /
   KowBits / community AOSP-TV builds for RK3566).
2. Flash with the Rockchip tool (`rkdeveloptool` / the vendor "Factory Tool") or
   balenaEtcher for SD images.
3. First boot → finish Android TV setup. **Skip** signing into Google if you want
   zero Google account; you'll sideload apps instead (step 3).

## 2. Build the openhome stick APK

The droplet can't build Android — do this on a Mac/PC with the Android SDK, or in
the cloud with EAS.

```bash
cd open-home/tv/apps/stick
npm install
# Option A — EAS cloud build (no local Android SDK):
npx eas build -p android --profile preview      # returns an installable .apk
# Option B — local:
export EXPO_TV=1
npx expo run:android                            # to a connected device/emulator
```

`ROUTER_URL` in `App.tsx` already points at your router
(`https://openhome-tv-production.up.railway.app`). Change it if you give the
router its own domain (e.g. `https://tv.bedrock.casa`).

### Make it the HOME launcher (so the stick boots into openhome)

After `expo prebuild` (or in the EAS build), the stick activity needs these
intent-filters in `android/app/src/main/AndroidManifest.xml` (add via an Expo
config plugin, or edit post-prebuild):

```xml
<!-- appear as a TV app -->
<intent-filter>
  <action android:name="android.intent.action.MAIN" />
  <category android:name="android.intent.category.LEANBACK_LAUNCHER" />
</intent-filter>
<!-- be selectable as the device home screen -->
<intent-filter>
  <action android:name="android.intent.action.MAIN" />
  <category android:name="android.intent.category.HOME" />
  <category android:name="android.intent.category.DEFAULT" />
</intent-filter>
```

Then on the device: **Settings → Apps → Default apps → Home app → openhome TV**.
Now it boots straight into your UI. (On Fire TV you can't fully replace Home;
on a generic Android TV box you can — that's why we don't use Fire TV for the
product build.)

## 3. Sideload the native streaming apps

These are licensed guests that handle their own login + DRM playback:

```bash
adb connect <stick-ip>:5555
adb install netflix.apk    # from the device's store, or Aurora Store / APKMirror
```

openhome never touches their streams — it only fires a **deep-link intent** to
launch the right app to the right title (`androidPackage` + `deepLink` from the
router). Sign into each app once, on the device, exactly like any stick.

## 4. Pair to your network

1. Boot the stick → openhome shows a 6-digit pairing code (`POST /sticks/pair/begin`).
2. In the phone app → **TV** tab → **＋ Pair a TV** → enter the code.
3. Cast a title → the router sends `launch` over the stick's SSE channel →
   openhome fires the intent → the native app opens to that title.

## What's already done vs. left

- ✅ Stick app (`App.tsx` + `src/router.ts`): pairing, SSE control channel,
  intent-launch, app-inventory reporting.
- ✅ Router (deployed), phone remote, cross-app search/routing.
- ⏳ Launcher intent-filters (above) — wire during the Android build.
- ⏳ P2: map remote `command` events to Android key events (play/pause/seek).
- ⏳ P3: auto-detect installed packages via `PackageManager` instead of the
  static `INSTALLED` list.

## Data ownership

Nothing here phones home to Roku/Amazon/Google (if you skip the Google sign-in).
The stick authenticates to **your** router with its own token, the brain/history
live on **your** droplet + Pi, and streams go app↔studio directly. You own the
hardware, the OS image, the launcher, and the data.

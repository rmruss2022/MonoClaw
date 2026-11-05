# Widevine L1 — how it actually works, and how we get it

> Deep-dive for the openhome "own-your-own-stick" project. The question:
> *"We want to own everything — how do we get Widevine L1 so Netflix/Disney play
> in HD instead of 480p?"* This is the honest answer, with sources.

## TL;DR

- **L1 is not software you install or a keybox you buy.** It's a per-device
  cryptographic root of trust (a **keybox**) **burned into the chip's secure area
  (TEE/TrustZone) at the factory**, issued only to a **registered Widevine device
  licensee**.
- **The chip decides eligibility, not the board.** The SoC vendor must ship a
  **Google-approved OEMCrypto** in its TEE. No approved TEE → L3 (480p), forever.
- **Three legitimate doors:** (1) become a Widevine licensee with Google directly,
  (2) go through a **Third-Party Lab (3PL)** like castLabs, or (3) **ride a SoC/box
  that's already L1-provisioned** — the only DIY-feasible path today.
- **For us, right now:** buy a **Google-certified Amlogic S905X4 box** (ships L1),
  keep its signed image, add openhome as launcher. **Do not** expect L1 from a bare
  RK3588 SBC — those are L3.

## What an L1 keybox is

A keybox = unique device ID + secret keys, provisioned once into the TEE during
manufacturing. It lets the studio's license server trust that decryption happens
inside hardware Google/the studios have approved. Consequences:

1. **Can't buy one off the shelf.** Anything selling "L1 keyboxes" is the piracy
   scene (ripped from eMMC dumps) — gets revoked, breaks constantly, non-starter.
2. **Lives in the SoC TEE.** OEMCrypto **v12+ / Widevine Provisioning 3.0+** in a
   real TrustZone/OP-TEE is required.
3. **Unlocking the bootloader often wipes/invalidates it** — the core tension with
   "flash my own OS." Reflash bare AOSP and you typically drop L1 → L3.
4. **Provisioning 4.0** (newer) moves away from injected per-device keyboxes toward
   a **TEE-derived root key + attestation** — nothing to leak/revoke. Target this
   for any future in-house device.

## The three doors to L1

### Door 1 — Direct Widevine device licensee (Google)
Google's docs: Provisioning / Keybox / OEMCrypto are device-integration components;
you must contact Widevine to integrate. The device **certificate is free**, but you
sign the Widevine license agreement, register as a manufacturer, pass CDM
compliance testing, then keyboxes are provisioned (in volume) for your devices.
This is the Roku/Nvidia/Onn path — a legal/business relationship, and Google is
selective. Not realistic for a hobbyist shipping one unit.

### Door 2 — Third-Party Lab (3PL) — realistic for a small brand
Google authorized partner labs to certify + provision **on its behalf**. Clearest
one: **castLabs** — they explicitly do, for STBs/TVs/streaming dongles:
*registering devices with Google, CDM testing & compliance, acquiring keyboxes for
testing and provisioning, integration assistance.* You still need an approved TEE on
your chip; they shepherd registration + keybox + compliance. **This is the door for
a real openhome-branded device at small scale.**

### Door 3 — Ride an already-provisioned SoC/box (DIY today)
Chip vendors — **Amlogic**, **Rockchip** (`rockchip-android/vendor-widevine`),
**NXP** (i.MX 8M Plus) — are themselves licensees who integrate OEMCrypto. Buy an
**L1-provisioned box + its signed image**, keep that image, and bolt openhome on as
launcher. You own the UX, launcher, brain, and data, and inherit the vendor's L1.
**Only path that gives L1 without a corporate contract.**

## Live hardware reality (scraped 2026-11-01)

### ✅ L1, buy today — certified Amlogic S905X4
- **KinHank G1** (Amlogic S905X4, 4GB/32GB) — **Google + Netflix dual-certified,
  Widevine L1, Dolby Vision, AV1**. ~**$70–90** (open-box seen ~$70; EU ~€90).
  - Caveat: recent (Sept-2024+) firmware **locks the bootloader** — great for L1
    integrity, but it constrains replacing the Home launcher. Test the
    launcher-override (Settings → Apps → Default apps → Home) before counting on it;
    worst case openhome runs as a normal app, not the boot launcher.
- Avoid no-name "X96 / H96 / 8K / 2GB" S905X4 boxes — usually **uncertified / L3**
  despite the listing claims. Verify with the **DRM Info** app (must read
  `Widevine security level: L1`) and check **androidtv-guide.com** for the model.

### ✅ L1 + the ODM door — SEI Robotics / DroidLogic
- **SEI Robotics** (brand **DroidLogic**) is a **Google-certified Android TV ODM** —
  the company you'd actually talk to to manufacture an **openhome-branded** certified
  stick. Their S905X4 developer kit ran ~**$199** (not a consumer product).
- **Google's own ADT dev kits:** ADT-3 was $79 (Askey, 2020); **ADT-4 was never sold
  publicly; ADT-5 (S905X5)** is dev-only. So Google's reference kits are **not** a
  reliable retail path — go KinHank (prototype) or SEI Robotics (manufacture).

### ⚠️ L3 only — the "fully open" boards (correction)
- **Orange Pi 5 / Orange Pi 5 Plus / Radxa Rock 5 (RK3588/RK3588S)** — powerful,
  4K60/HDR10/AV1, **but their Android is uncertified → Widevine L3**. Widevine can be
  added on Ubuntu-rockchip images, still **L3** → Netflix ~480p, Disney may refuse.
  **Excellent** for Plex/Jellyfin/YouTube/Kodi/IPTV/local media and maximum OS
  ownership — just not for big-studio HD.
- **Raspberry Pi 5** — same story: L3, browser-only for most DRM services.

## Recommendation for openhome

| Goal | Buy | Why |
|---|---|---|
| **Prototype native-HD apps + openhome launcher now** | **KinHank G1** (~$70–90) | Cheapest verified L1 + certified; prove the launcher-override + deep-link loop on real L1 |
| **Maximum OS ownership, apps second** | **Orange Pi 5 / Radxa Rock 5** | Fully open; L3 is fine for Plex/Jellyfin/YouTube/your media |
| **Ship our own branded device** | **SEI Robotics (DroidLogic)** via a **3PL (castLabs)** | Certified ODM + the lab that handles Google registration + keybox provisioning |

**The key mental model:** the keybox was never the thing you engineer — it's the
thing a **licensing relationship grants you**, and the **SoC's TEE is what makes you
eligible**. So: *pick certified silicon, keep the signed image, own the layer that's
actually yours — the launcher, the graph, the brain, the data.*

## Sources
- Google — Widevine DRM overview (device integration / keybox / OEMCrypto):
  https://developers.google.com/widevine/drm/overview
- castLabs — Widevine certification & keybox provisioning (Google 3PL partner):
  https://castlabs.com/security/widevine-certification/
- NXP — Provisioning Widevine L1 keybox (SoC-level process):
  https://docs.nxp.com/bundle/UG10158/page/topics/provisioning_widevine_l1_keybox.html
- Rockchip — vendor/widevine: https://github.com/rockchip-android/vendor-widevine
- Widevine L1 vs L3 (2026): https://www.forasoft.com/learn/video-streaming/articles-streaming/widevine-l1-l2-l3
- SEI Robotics (DroidLogic) certified ODM: https://www.seirobotics.net/
- androidtv-guide.com — list of actually-certified devices: https://www.androidtv-guide.com/

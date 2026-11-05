# Starter Loadout — a $300 openhome build

You bring a Raspberry Pi to run the hub. This is the shopping list for everything it
controls: the radios that turn the Pi into a protocol hub, a set of **ESPHome** lights,
and two rooms of **synced Snapcast** audio. Everything here is chosen to plug straight
into what the app already drives — `/setup` → `/lights` → `/speakers`.

> Prices are ballparks (street price / our [build guide](/docs/build)) — verify at
> checkout. Links are starting points, not endorsements.

## What you're building

```
                 ┌─────────────── your Pi (the hub) ───────────────┐
 ESPHome bulbs ──┤  openhome hub  +  snapserver  +  librespot        ├── Spotify / library
 (Wi-Fi, local)  │  Matter/Thread via USB stick                      │
                 └───────┬───────────────────────────────┬──────────┘
                         │ Snapcast (synced)             │ Snapcast (synced)
                   Living Room                       Bedroom
                 Pi Zero 2 W + amp                Pi Zero 2 W + amp
                 + powered speaker                + powered speaker
```

- **Lights** → ESPHome bulbs, discovered and controlled locally by the hub. Zero cloud.
- **Climate** → an ESPHome thermostat wired to your HVAC; setpoint/mode logic runs on-device.
- **Speakers** → Wi-Fi rooms run a snapclient each, time-aligned by the hub's calibration
  and grouped for sample-synced multi-room playback; Bluetooth speakers onboard for casual
  rooms with auto-reconnect.
- **Radios** → a Zigbee/Thread stick future-proofs you for Matter-over-Thread and the
  cheap Zigbee catalog.

## Your build — bill of materials

> **Matthew's config:** 5 color bulbs (incl. warm orange), hub add-ons, an ESPHome
> thermostat, and a **2 Wi-Fi + 2 Bluetooth** speaker mix. Links are Amazon **search**
> pages — pick the current best price/rating. A couple of items are cheaper bought direct;
> noted inline. Prices are ballparks — verify at checkout.

### 🧠 Hub add-ons (Pi already owned) — ~$45
| # | Part | Why | Price | Link |
|---|------|-----|-------|------|
| 1 | SONOFF ZBDongle-E (Zigbee + Thread) | Matter-over-Thread + Zigbee later | ~$20 | [Amazon](https://www.amazon.com/s?k=SONOFF+ZBDongle-E) |
| 2 | USB-C PSU 5.1 V/3 A | clean power (skip if kitted) | ~$10 | [Amazon](https://www.amazon.com/s?k=raspberry+pi+official+usb-c+power+supply) |
| 3 | 32 GB A2 microSD | hub OS (skip if kitted) | ~$8 | [Amazon](https://www.amazon.com/s?k=SanDisk+Extreme+32GB+microSD+A2) |
| 4 | Heatsink + fan | keeps the hub cool under load | ~$7 | [Amazon](https://www.amazon.com/s?k=raspberry+pi+4+heatsink+fan) |

*If your Pi already has power + SD, skip items 2–3 (−$18).*

### 🟠 Lights — 5× RGBCW (full color + warm orange) — ~$70
| # | Part | Why | Price | Link |
|---|------|-----|-------|------|
| 5 | **5× Athom RGBCW bulb, pre-flashed ESPHome** | our exact backend — instant, local | ~$70 | [Athom (direct)](https://www.athom.tech/) |

> RGBCW = full RGB color **+** tunable white, so you get every color *and* a warm orange
> glow (~2200 K white, or an RGB amber). **Buy direct from Athom** and pick "ESPHome" at
> checkout — Amazon's cheap "smart bulbs" are cloud Tuya, **not** our local backend. They
> appear in the Lights wizard under **ESPHome → Find on my network**.

### 🌡️ Thermostat — ESPHome, wired to your HVAC — ~$37
| # | Part | Why | Price | Link |
|---|------|-----|-------|------|
| 6 | Sonoff TH Elite (THR320D) | the controller, flashed with ESPHome | ~$18 | [Amazon](https://www.amazon.com/s?k=SONOFF+TH+Elite+THR320D) |
| 7 | AHT20 temp + humidity sensor | reads the room | ~$5 | [Amazon](https://www.amazon.com/s?k=AHT20+temperature+humidity+sensor) |
| 8 | 3-channel 5 V relay board (heat / cool / fan) | switches your 24 V HVAC | ~$8 | [Amazon](https://www.amazon.com/s?k=3+channel+5V+relay+module) |
| 9 | 24 V→5 V buck converter + wire | power from the HVAC's C-wire | ~$6 | [Amazon](https://www.amazon.com/s?k=24V+to+5V+buck+converter) |

> Runs ESPHome's on-device `climate` controller — setpoint, mode and hysteresis live
> **on the thermostat**, so heating/cooling keeps working even if the hub reboots. Shows up
> in the **Climate** tab under ESPHome. Prefer no wiring? A **Matter-over-Thread thermostat**
> pairs via the ZBDongle-E (item 1) — the bring-your-own path.
>
> Minimal ESPHome climate config:
> ```yaml
> climate:
>   - platform: thermostat
>     name: "HVAC"
>     sensor: room_temp
>     default_target_temperature_low: 20 °C
>     heat_action: { switch.turn_on: relay_heat }
>     cool_action: { switch.turn_on: relay_cool }
>     idle_action: { switch.turn_off: relay_heat }
> ```

### 🔊 Speakers — 2 Wi-Fi (synced) + 2 Bluetooth — ~$166

**Wi-Fi — 2 synced rooms (Snapcast):**
| # | Part | Why | Price | Link |
|---|------|-----|-------|------|
| 10 | 2× Raspberry Pi Zero 2 W | one snapclient per room | ~$30 | [Amazon](https://www.amazon.com/s?k=Raspberry+Pi+Zero+2+W) · cheaper: [PiShop](https://www.pishop.us/product/raspberry-pi-zero-2-w/) |
| 11 | 2× 16 GB microSD | client OS | ~$12 | [Amazon](https://www.amazon.com/s?k=SanDisk+16GB+microSD) |
| 12 | 2× MAX98357A I2S amp (or USB DAC) | digital audio out | ~$12 | [Amazon](https://www.amazon.com/s?k=MAX98357A+I2S+amplifier) |
| 13 | 2× powered bookshelf speaker | the actual sound | ~$56 | [Amazon](https://www.amazon.com/s?k=powered+bookshelf+speakers) |

**Bluetooth — 2 speakers:**
| # | Part | Why | Price | Link |
|---|------|-----|-------|------|
| 14 | 2× Anker Soundcore (or similar) | onboard via Speakers → + Bluetooth | ~$56 | [Amazon](https://www.amazon.com/s?k=Anker+Soundcore+bluetooth+speaker) |

> The Wi-Fi pair plays in **sample-sync** (calibrate + ⇄ Sync). Bluetooth speakers onboard
> with auto-reconnect but aren't part of the synced group. Prefer zero assembly for Wi-Fi?
> Swap each Pi-Zero kit for a **plug-and-play AirPlay speaker (~$40)** — the app still sees
> it over the network, you just lose sample-sync.

### Total ≈ **$318** — 5 color lights + hub radios + ESPHome thermostat + 2 Wi-Fi & 2 Bluetooth speakers.
### Lean version ≈ **$220** — skip PSU/SD (−$18), 1 Wi-Fi room (−$55), 1 Bluetooth (−$28).

## Two honest calls

- **Multi-room audio is DIY here.** A snapclient per room (Pi Zero + amp) is ~$40/room and
  is exactly what our Snapcast layer targets. Off-the-shelf *synced* speakers (Sonos) are
  $150+ **each** and would eat the whole budget on one room. If you want v1 dead-simple,
  swap items 7–11 for **one good Bluetooth/AirPlay powered speaker (~$60)** — you lose sync
  but everything else works, and you can add snapclients later.
- **Go all-ESPHome for the first lights.** It's our own-firmware path, so onboarding is
  instant and fully local. Add a Matter/Thread bulb later once the ZBDongle-E is in.

---

## Turnkey: the two-room synced audio

### Hub side (once) — snapserver + librespot
Follow [Run on your Pi](/docs/run-hub) to install `snapserver` + `librespot` on the hub.
In short, librespot writes to a FIFO that snapserver streams:

```bash
sudo apt install -y snapserver
# /etc/snapserver.conf
[stream]
source = pipe:///tmp/snapfifo?name=openhome&sampleformat=48000:16:2&codec=flac
```

The hub talks to snapserver's control port on `127.0.0.1:1705` (override with
`SNAPCAST_HOST`/`SNAPCAST_PORT`). Once it's up, `/speakers` shows **🔗 sync active**.

### Client side — flash each Pi Zero 2 W
Repeat for each room (name them per room, e.g. `living-room`, `bedroom`):

1. **Flash Raspberry Pi OS Lite (64-bit)** with Raspberry Pi Imager. In the gear/⚙️
   settings: set **hostname** to the room (`living-room`), enable **SSH**, and enter your
   **Wi-Fi**. Boot it.
2. **Install snapclient:**
   ```bash
   ssh pi@living-room.local
   sudo apt update && sudo apt install -y snapclient
   ```
3. **Wire the audio out.**
   - *MAX98357A (I2S):* add to `/boot/firmware/config.txt`:
     ```
     dtparam=audio=off
     dtoverlay=max98357a
     ```
     then `sudo reboot`. Speaker to the amp's screw terminals.
   - *USB DAC:* just plug it in (no config needed).
4. **Point the client at the hub** — edit `/etc/default/snapclient`:
   ```
   SNAPCLIENT_OPTS="-h <HUB_IP> --hostID living-room --player alsa"
   ```
   Use the **same name you'll give the speaker in the app** so calibration/sync map to the
   right client.
5. **Start it on boot:**
   ```bash
   sudo systemctl enable --now snapclient
   ```

### Finish in the app
1. Open **`/speakers`** — each Pi Zero appears as a live speaker.
2. Assign each to its **room** (Living Room, Bedroom).
3. Tap **✨ Calibrate** per room → set distances → the hub pushes per-client **delay + trim**
   to snapclient.
4. Tap **⇄ Sync** to group a room → both endpoints play the **same audio, sample-synced**.

That's the whole chain: **discover → onboard → room → calibrate (spatial) → sync**, running
on ~$265 of hardware plus the Pi you already own.

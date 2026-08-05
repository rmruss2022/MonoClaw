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
- **Speakers** → one snapclient per room, time-aligned by the hub's calibration and
  grouped for sample-synced multi-room playback.
- **Radios** → a Zigbee/Thread stick future-proofs you for Matter-over-Thread and the
  cheap Zigbee catalog.

## Bill of materials

### 🧠 Hub add-ons (Pi already owned) — ~$45
| # | Part | Why | Price | Link |
|---|------|-----|-------|------|
| 1 | SONOFF ZBDongle-E (Zigbee + Thread) | Matter-over-Thread + Zigbee later | ~$20 | [buy](https://itead.cc/product/sonoff-zigbee-3-0-usb-dongle-plus-e/) |
| 2 | USB-C PSU 5.1 V/3 A + 32 GB A2 microSD | clean power + OS (skip if kitted) | ~$18 | [buy](https://www.raspberrypi.com/products/type-c-power-supply/) |
| 3 | Heatsink + fan | keeps the hub cool under load | ~$7 | [buy](https://www.amazon.com/dp/B07VVDN9K3) |

*If your Pi is already fully set up, skip this section and put the ~$45 into more bulbs or a third audio room.*

### 💡 Lights — ESPHome, pure Wi-Fi, zero cloud — ~$85
| # | Part | Why | Price | Link |
|---|------|-----|-------|------|
| 4 | 4× Athom RGBCW bulb, pre-flashed ESPHome | our exact backend — instant, local | ~$56 | [buy](https://www.athom.tech/product-page/rgbcw-bulb) |
| 5 | 1× Athom ESPHome smart plug | makes a lamp smart | ~$11 | [buy](https://www.athom.tech/) |
| 6 | 1× Athom/ESPHome RGB LED strip | accent lighting | ~$18 | [buy](https://www.athom.tech/) |

> Athom ships bulbs **pre-flashed with ESPHome** (opt at checkout) — no soldering, no
> cloud account. They appear in the Lights wizard under **ESPHome → Find on my network**.

### 🌡️ Thermostat — ESPHome, wired to your HVAC — ~$35
| # | Part | Why | Price | Link |
|---|------|-----|-------|------|
| 7 | Sonoff TH Elite (THR320D) **or** ESP32 dev board | the controller, flashed with ESPHome | ~$18 | [buy](https://itead.cc/product/sonoff-thr320d-elite/) |
| 8 | AHT20 / Si7021 temp + humidity sensor | reads the room | ~$5 | [buy](https://www.adafruit.com/product/4566) |
| 9 | 2–3 channel relay board (heat / cool / fan) | switches your 24 V HVAC | ~$8 | [buy](https://www.amazon.com/dp/B07FCUYX2X) |
| 10 | 24 V→5 V buck + wire | power from the HVAC's C-wire | ~$6 | [buy](https://www.amazon.com/dp/B076H3XHXP) |

> Runs ESPHome's on-device `climate` controller — setpoint, mode and hysteresis live
> **on the thermostat**, so heating/cooling keeps working even if the hub reboots. It
> appears in the **Climate** tab under ESPHome. Prefer no wiring? A **Matter-over-Thread
> thermostat** pairs via the ZBDongle-E (item 1) — that's the bring-your-own path.
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

### 🔊 Speakers — 2 rooms, truly synced (Snapcast) — ~$135
| # | Part | Why | Price | Link |
|---|------|-----|-------|------|
| 11 | 2× Raspberry Pi Zero 2 W | one snapclient per room | ~$30 | [buy](https://www.adafruit.com/product/5291) |
| 12 | 2× 16 GB microSD | client OS | ~$12 | [buy](https://www.amazon.com/dp/B073K14CVB) |
| 13 | 2× MAX98357A I2S amp (or USB DAC) | digital audio out | ~$12 | [buy](https://www.adafruit.com/product/3006) |
| 14 | 2× powered bookshelf/desktop speaker | the actual sound | ~$60 | your pick |
| 15 | Power + cables for the two endpoints | — | ~$20 | — |

### Total ≈ **$300** — hub radios + 4 ESPHome lights + a thermostat + two synced audio rooms.

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

# Running the Hub on Your Pi (so speakers actually appear)

The openhome hub is a **local service** — it runs on a box that lives on *your*
network (a Raspberry Pi, an old Mac mini, any always-on Linux/macOS machine).
Speaker discovery, Bluetooth pairing, and reconnection all happen from there.

**Why it has to be local.** Finding speakers uses two things that only work on
the same network as the speakers:

- **Wi-Fi discovery = mDNS** (multicast to `224.0.0.251:5353`). Multicast does
  not cross the internet or most VLANs — the hub and the speaker must share a
  subnet.
- **Bluetooth = BlueZ** on a real **Bluetooth radio**. No radio, no BT.

A cloud server has neither (it's in a datacenter, not your living room), so a
scan there correctly returns *"no speakers found."* On the Pi, it lights up.

---

## 1. Prerequisites on the Pi

```bash
# Raspberry Pi OS / Debian / Ubuntu
sudo apt update
sudo apt install -y nodejs npm avahi-daemon avahi-utils bluez

# sanity checks
node --version            # v20+ (the hub uses --experimental-strip-types)
avahi-browse -a -t        # should list mDNS services on your LAN
bluetoothctl list         # should show a Controller (the BT adapter)
```

- **avahi-daemon** answers/relays mDNS. The hub does its own mDNS query, but
  having Avahi running makes the network chatty enough that speakers respond
  reliably.
- **bluez** provides `bluetoothctl`, which the hub shells out to for BT scan,
  pair, and reconnect.

---

## 2. Run the hub as a service

The hub is `services/hub/src/index.ts`. Run it under systemd so it starts on
boot and restarts on failure.

`/etc/systemd/system/open-home-hub.service`:

```ini
[Unit]
Description=openhome hub
After=network-online.target bluetooth.service avahi-daemon.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/pi/openhome/open-home
Environment=OPEN_HOME_PORT=4700
# credentials (Spotify client id/secret/redirect, Gemini key) — keep out of the repo
EnvironmentFile=-/home/pi/.openhome/spotify.env
EnvironmentFile=-/home/pi/.openhome/google-genai.env
ExecStart=/usr/bin/node --experimental-strip-types services/hub/src/index.ts
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now open-home-hub
systemctl status open-home-hub
```

> **Networking gotcha:** if you ever containerize the hub, run it with
> `--network host`. mDNS **does not work** across Docker's default bridge —
> the multicast never leaves the container. Host networking (or a macvlan) is
> required for Wi-Fi speaker discovery.

---

## 3. Bluetooth permissions

`bluetoothctl` talks to BlueZ over D-Bus. When the hub runs as a systemd
service, give its user access:

```bash
sudo usermod -aG bluetooth pi        # the user the service runs as
sudo systemctl restart bluetooth
```

If pairing needs a PIN/confirmation, do the first pair once by hand
(`bluetoothctl` → `scan on` → `pair <MAC>` → `trust <MAC>`); after `trust`, the
hub's reconnect loop can bring it back on its own.

---

## 4. Onboarding a speaker (in the app)

1. Open **/music → Speakers & rooms**.
2. Tap **+ Wi-Fi** or **+ Bluetooth** → the hub scans for a few seconds.
3. Discovered speakers appear — tap **add**. It's saved with a room (Living
   Room by default).
4. Set its **room** from the dropdown; use **✕** to remove it.

Onboarded speakers persist to `services/hub/.data/local-speakers.json`, so they
survive restarts.

---

## 5. Reconnection maintenance

A supervisor runs every **15 seconds** and keeps each onboarded speaker alive:

| Kind | Check | Reconnect |
|------|-------|-----------|
| Wi-Fi | TCP reach to the device's `ip:port` | marks `reconnecting → offline` after repeated misses |
| Bluetooth | `bluetoothctl info <mac>` connected? | runs `bluetoothctl connect <mac>` on drop |

Status shows in the UI as **connected / reconnecting… / offline**, with a manual
**reconnect** button. Attempts back off and settle to `offline` after a few
failures so a dead speaker doesn't thrash the loop.

---

## 6. Troubleshooting

- **"No speakers answered on this network."** The hub isn't on the same subnet
  as the speakers, or multicast is blocked. Confirm with `avahi-browse -a -t`.
  Guest/IoT VLANs often block mDNS — put the hub on the same VLAN, or run an
  mDNS reflector on the router.
- **Bluetooth scan says "no adapter."** `bluetoothctl list` shows no Controller.
  On a Pi, the built-in adapter needs `bluez` running (`systemctl status
  bluetooth`); on a headless box you may need a USB BT dongle.
- **A speaker keeps flapping to `reconnecting`.** It's dropping off Wi-Fi/BT, or
  (Wi-Fi) the guessed port is wrong for that brand — most AirPlay is `:7000`,
  Chromecast `:8009`, Snapcast `:1704`.

---

## Where this is going

Today each onboarded speaker is discovered, roomed, and kept connected.
**Synchronized multi-room** (the same audio playing in time across rooms) is the
next layer — a **Snapcast** server on the hub with one client per speaker. The
speaker service is built to plug straight into it. See [Sound](/docs/sound).

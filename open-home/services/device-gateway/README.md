# services/device-gateway

The hands of open-home. Adapter processes that bridge physical device protocols to the
hub's event bus using the shared device schema (`packages/shared`).

## Planned adapters
- **Matter / Thread** (`matter.js`) — strategic default for new devices.
- **Zigbee** via zigbee2mqtt.
- **Z-Wave** via Z-Wave JS.
- **Cameras** — ONVIF discovery + RTSP ingest; snapshots + event clips to `storage`.
- **Generic MQTT / ESPHome** for DIY devices.

Each adapter: discovers devices → normalizes them to `Device` → publishes `DeviceEvent`s
to MQTT → accepts commands on a command topic. Nothing vendor-specific leaks into the hub.

Status: stub. First target is a single ONVIF/RTSP camera end-to-end (ROADMAP Phase 1).

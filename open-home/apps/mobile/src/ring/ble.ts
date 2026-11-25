/**
 * The ring over Bluetooth, from the phone.
 *
 * WHY THE PHONE AND NOT THE PI — this changed on evidence, not preference.
 * The Pi can see the ring but only at -71 to -75 dBm, and at that signal the
 * GATT handshake does not survive: measured on the Pi, each ATT round trip took
 * 100-300 ms and the link supervision timeout fired before discovery finished.
 * A USB dongle made it worse (9 devices visible vs the built-in radio's 18, and
 * it could not hear the ring at all). The phone is inches from your hand rather
 * than metres, which removes the problem instead of working around it.
 *
 * EVERY CONSTANT HERE WAS VERIFIED AGAINST THE REAL RING (COLMI Ring 2,
 * firmware RT12CR2_1.00.00_260709) on 2026-11-25:
 *   - the UART service and both characteristics are present
 *   - the checksum is the LOW BYTE of the sum of the first 15 (modulo 256).
 *     Both reference implementations do this and both DOCUMENT it as
 *     "modulus 255", which is wrong — see services/ring-bridge/AUDIT.md
 *   - `a1 03` asks for ONE sensor snapshot without powering the PPG sensor, so
 *     the LEDs stay off. `a1 04` is the trap: it starts the "real" stream, turns
 *     the LEDs on and drains the battery in hours for a tenth of the rate
 *
 * NOT YET VERIFIED: anything in this file running on iOS. It needs a dev build
 * (react-native-ble-plx cannot run in Expo Go), and the sample rate this
 * achieves over a strong link is the one number the gesture feature depends on.
 */
import { Buffer } from "buffer";

import { Engine, type Gesture, type Sample } from "./gestures";

export const RING_SERVICE = "6e40fff0-b5a3-f393-e0a9-e50e24dcca9e";
export const RING_WRITE = "6e400002-b5a3-f393-e0a9-e50e24dcca9e";
export const RING_NOTIFY = "6e400003-b5a3-f393-e0a9-e50e24dcca9e";

const CMD_RAW_SENSOR = 0xa1;
const SUB_POLL_ONCE = 0x03;    // one snapshot, PPG untouched, LEDs stay OFF
const SUB_DISABLE_RAW = 0x02;  // stop the raw block on the way out
const CMD_BATTERY = 0x03;
const ACCEL_SUBTYPE = 0x03;

/** Names the Colmi family ships under. "COLMI Ring 2" is not "R02", which is
 *  how our first scanner missed it entirely. */
const NAME_HINTS = ["colmi", "r02", "r03", "r06", "r10", "ring"];

export function buildPacket(command: number, payload: number[] = []): Buffer {
  if (payload.length > 14) throw new Error("payload too long for a 16-byte packet");
  const p = Buffer.alloc(16);
  p[0] = command;
  for (let i = 0; i < payload.length; i++) p[i + 1] = payload[i];
  let sum = 0;
  for (let i = 0; i < 15; i++) sum += p[i];
  p[15] = sum & 0xff;
  return p;
}

function i16be(hi: number, lo: number): number {
  const v = (hi << 8) | lo;
  return v >= 0x8000 ? v - 0x10000 : v;
}

/** Big-endian signed 16-bit per axis, ~8192 counts per g. */
export function parseAccel(d: Buffer): [number, number, number] | null {
  if (d.length < 8 || d[0] !== CMD_RAW_SENSOR || d[1] !== ACCEL_SUBTYPE) return null;
  return [i16be(d[2], d[3]), i16be(d[4], d[5]), i16be(d[6], d[7])];
}

export function parseBattery(d: Buffer): { level: number; charging: boolean } | null {
  if (d.length < 3 || d[0] !== CMD_BATTERY) return null;
  return { level: d[1], charging: Boolean(d[2]) };
}

export interface RingTelemetry {
  battery?: number;
  charging?: boolean;
  rssi?: number;
  /** samples per second actually achieved — the number that decides the feature */
  hz?: number;
  connected: boolean;
}

export interface RingCallbacks {
  onGesture: (g: Gesture) => void;
  onTelemetry: (t: RingTelemetry) => void;
  onLog?: (line: string) => void;
}

/**
 * Drives one ring. Deliberately dependency-injected with the ble-plx manager
 * rather than importing it, so this module can be unit tested with a fake and
 * so the app does not pay for the native module until the ring screen is used.
 */
export class RingLink {
  private cfg: RingCallbacks;
  private manager: any;
  private device: any = null;
  private engine: Engine;
  private sub: any = null;
  private polling = false;
  private sampleTimes: number[] = [];
  private stopped = false;

  constructor(manager: any, cfg: RingCallbacks) {
    this.manager = manager;
    this.cfg = cfg;
    this.engine = new Engine((g) => this.cfg.onGesture(g));
  }

  private log(line: string): void {
    this.cfg.onLog?.(line);
  }

  /** Scan until the ring appears. Matches the service UUID first, then names. */
  async find(timeoutMs = 20000): Promise<any> {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.manager.stopDeviceScan();
        reject(new Error("ring not found — is it connected to another device?"));
      }, timeoutMs);

      // Scanning WITHOUT a UUID filter on purpose: the ring advertises the
      // short 0xFEE7 id, not its 128-bit UART service, so filtering on the
      // service we actually want finds nothing. That cost us an hour.
      this.manager.startDeviceScan(null, null, (err: any, dev: any) => {
        if (err) {
          clearTimeout(timer);
          this.manager.stopDeviceScan();
          reject(err);
          return;
        }
        const name: string = (dev?.name ?? dev?.localName ?? "").toLowerCase();
        const hit =
          (dev?.serviceUUIDs ?? []).some((u: string) => u.toLowerCase() === RING_SERVICE) ||
          NAME_HINTS.some((h) => name.includes(h));
        if (hit) {
          clearTimeout(timer);
          this.manager.stopDeviceScan();
          this.log(`found ${dev.name ?? "(unnamed)"} at ${dev.rssi} dBm`);
          resolve(dev);
        }
      });
    });
  }

  async connect(dev?: any): Promise<void> {
    const target = dev ?? (await this.find());
    this.device = await target.connect({ requestMTU: 185 });
    // iOS will not bond unless asked, which is what we want: on the Pi, BlueZ
    // offering to bond is what the ring rejected with "invalid parameters",
    // killing every connection until we disabled it.
    this.device = await this.device.discoverAllServicesAndCharacteristics();
    this.log("connected");
    this.cfg.onTelemetry({ connected: true, rssi: target.rssi ?? undefined });

    this.sub = this.device.monitorCharacteristicForService(
      RING_SERVICE,
      RING_NOTIFY,
      (err: any, ch: any) => {
        if (err || !ch?.value) return;
        const d = Buffer.from(ch.value, "base64");

        const bat = parseBattery(d);
        if (bat) {
          this.cfg.onTelemetry({ connected: true, battery: bat.level, charging: bat.charging });
          return;
        }
        const a = parseAccel(d);
        if (a) {
          const now = Date.now() / 1000;
          this.sampleTimes.push(now);
          if (this.sampleTimes.length > 100) this.sampleTimes.shift();
          const s: Sample = { x: a[0], y: a[1], z: a[2], t: now };
          this.engine.feed(s);
        }
      },
    );

    await this.write(buildPacket(CMD_BATTERY));
  }

  private async write(p: Buffer): Promise<void> {
    if (!this.device) throw new Error("not connected");
    await this.device.writeCharacteristicWithoutResponseForService(
      RING_SERVICE,
      RING_WRITE,
      p.toString("base64"),
    );
  }

  /**
   * Poll `a1 03` in a loop. This is the whole data path: one snapshot per
   * request, PPG untouched, LEDs off. The achieved rate is reported because it
   * is the number that decides whether a double tap is detectable — our own
   * harness measured 12 Hz catching one 10% of the time and 50 Hz every time.
   */
  async startPolling(intervalMs = 10): Promise<void> {
    if (this.polling) return;
    this.polling = true;
    this.stopped = false;
    let lastReport = 0;
    while (this.polling && !this.stopped) {
      try {
        await this.write(buildPacket(CMD_RAW_SENSOR, [SUB_POLL_ONCE]));
      } catch (e) {
        this.log(`poll write failed: ${(e as Error).message}`);
        break;
      }
      // Let the engine close a trailing burst even when samples stop.
      this.engine.tick(Date.now() / 1000);

      const now = Date.now();
      if (now - lastReport > 2000 && this.sampleTimes.length > 5) {
        lastReport = now;
        const span = this.sampleTimes[this.sampleTimes.length - 1] - this.sampleTimes[0];
        if (span > 0) {
          this.cfg.onTelemetry({
            connected: true,
            hz: Math.round(((this.sampleTimes.length - 1) / span) * 10) / 10,
          });
        }
      }
      await new Promise((r) => setTimeout(r, intervalMs));
    }
    this.polling = false;
  }

  async stop(): Promise<void> {
    this.stopped = true;
    this.polling = false;
    try {
      // Turn the raw block off explicitly, or the LEDs can be left on.
      await this.write(buildPacket(CMD_RAW_SENSOR, [SUB_DISABLE_RAW]));
    } catch {
      /* already gone */
    }
    try {
      this.sub?.remove();
    } catch {
      /* no subscription */
    }
    try {
      await this.device?.cancelConnection();
    } catch {
      /* already disconnected */
    }
    this.device = null;
    this.cfg.onTelemetry({ connected: false });
    this.log("disconnected");
  }
}

/**
 * PipeWire output router — openhome owns audio routing locally.
 *
 * This is the heart of the internal audio router: instead of asking Spotify's
 * cloud to pick an output device, the hub enumerates the PipeWire sinks on the
 * machine (Bluetooth A2DP, built-in, HDMI, future Snapcast bridges) and routes
 * the audio to whichever sink a room maps to. Source stays whatever is feeding
 * PipeWire (librespot for Spotify today; AirPlay/line-in/TTS later) — openhome
 * decides where it comes out. No Spotify device-picker dance.
 *
 * Zero new dependencies: drives the PipeWire CLI already on the host
 *   - pw-dump   → enumerate sinks + the default-sink metadata (JSON)
 *   - wpctl     → set default sink, per-sink volume/mute
 *   - pw-play   → push a test tone to a specific sink (proves a room works)
 *
 * Capability-aware: if PipeWire isn't reachable (e.g. a cloud host with no audio
 * pipeline) every call degrades to "unavailable" and the hub falls back to the
 * Spotify-Connect path. The audible layer needs PipeWire running on the hub.
 */
import { execFile } from "node:child_process";
import { writeFile, access } from "node:fs/promises";

const UID = typeof process.getuid === "function" ? process.getuid() : 1000;
const ENV = { ...process.env, XDG_RUNTIME_DIR: process.env.XDG_RUNTIME_DIR || `/run/user/${UID}` };
const TONE = "/tmp/oh_tone.wav";

function run(cmd: string, args: string[], timeoutMs = 4000): Promise<{ ok: boolean; out: string }> {
  return new Promise((resolve) => {
    execFile(cmd, args, { timeout: timeoutMs, env: ENV, maxBuffer: 8 * 1024 * 1024 }, (err, stdout) =>
      resolve({ ok: !err, out: String(stdout || "") }));
  });
}

export interface Sink {
  id: number;          // PipeWire node id (what wpctl acts on)
  nodeName: string;    // e.g. bluez_output.18_90_67_DF_1C_70.1
  name: string;        // human description, e.g. "JBL Go 4"
  kind: "bluetooth" | "hdmi" | "analog" | "other";
  mac?: string;        // for bluetooth sinks
  isDefault: boolean;
}

let available = false;
export function availableCached(): boolean { return available; }

function classify(nodeName: string): Sink["kind"] {
  if (/^bluez_output/.test(nodeName)) return "bluetooth";
  if (/hdmi/i.test(nodeName)) return "hdmi";
  if (/^alsa_output/.test(nodeName)) return "analog";
  return "other";
}
function macFrom(nodeName: string): string | undefined {
  const m = nodeName.match(/bluez_output\.([0-9A-Fa-f_]+)\./);
  return m ? m[1].replace(/_/g, ":") : undefined;
}

/** Enumerate PipeWire audio sinks + which one is the current default. */
export async function listSinks(): Promise<Sink[]> {
  const r = await run("pw-dump", []);
  if (!r.ok) { available = false; return []; }
  let objs: any[];
  try { objs = JSON.parse(r.out); } catch { available = false; return []; }
  available = true;

  // default sink node.name lives in the "default" metadata object
  let defaultName = "";
  for (const o of objs) {
    if (o?.type === "PipeWire:Interface:Metadata" && o?.metadata) {
      for (const m of o.metadata) {
        if (m.key === "default.audio.sink") {
          try { defaultName = (typeof m.value === "string" ? JSON.parse(m.value) : m.value)?.name || ""; } catch {}
        }
      }
    }
  }

  const sinks: Sink[] = [];
  for (const o of objs) {
    const p = o?.info?.props;
    if (!p || p["media.class"] !== "Audio/Sink") continue;
    const nodeName = p["node.name"] || "";
    if (!nodeName || /\.monitor$/.test(nodeName)) continue;
    sinks.push({
      id: o.id,
      nodeName,
      name: p["node.description"] || p["node.nick"] || nodeName,
      kind: classify(nodeName),
      mac: macFrom(nodeName),
      isDefault: nodeName === defaultName,
    });
  }
  return sinks;
}

export async function defaultSink(): Promise<Sink | null> {
  return (await listSinks()).find((s) => s.isDefault) || null;
}

/** Make `sinkId` the default output — new streams (and well-behaved existing
 *  ones) follow it. Returns true on success. */
export async function route(sinkId: number): Promise<boolean> {
  const r = await run("wpctl", ["set-default", String(sinkId)]);
  return r.ok;
}

/** Route by node name (what we persist against a room). */
export async function routeByNode(nodeName: string): Promise<boolean> {
  const s = (await listSinks()).find((x) => x.nodeName === nodeName);
  if (!s) return false;
  return route(s.id);
}

export async function setVolume(sinkId: number, pct: number): Promise<boolean> {
  const v = Math.max(0, Math.min(1, pct / 100));
  const r = await run("wpctl", ["set-volume", String(sinkId), v.toFixed(2)]);
  return r.ok;
}
export async function setMute(sinkId: number, muted: boolean): Promise<boolean> {
  const r = await run("wpctl", ["set-mute", String(sinkId), muted ? "1" : "0"]);
  return r.ok;
}

async function ensureTone(): Promise<void> {
  try { await access(TONE); return; } catch {}
  // 1.6s 440Hz stereo sine, 16-bit PCM WAV, gentle decay
  const sr = 44100, dur = 1.6, f = 440, n = Math.floor(sr * dur);
  const data = Buffer.alloc(n * 4);
  for (let i = 0; i < n; i++) {
    const v = Math.round(32767 * 0.3 * Math.sin(2 * Math.PI * f * i / sr) * Math.exp(-i / (sr * dur * 1.5)));
    data.writeInt16LE(v, i * 4); data.writeInt16LE(v, i * 4 + 2);
  }
  const header = Buffer.alloc(44);
  header.write("RIFF", 0); header.writeUInt32LE(36 + data.length, 4); header.write("WAVE", 8);
  header.write("fmt ", 12); header.writeUInt32LE(16, 16); header.writeUInt16LE(1, 20);
  header.writeUInt16LE(2, 22); header.writeUInt32LE(sr, 24); header.writeUInt32LE(sr * 4, 28);
  header.writeUInt16LE(4, 32); header.writeUInt16LE(16, 34);
  header.write("data", 36); header.writeUInt32LE(data.length, 40);
  await writeFile(TONE, Buffer.concat([header, data]));
}

/** Push a short test tone to a specific sink — proves the room physically plays,
 *  independent of any music source. */
export async function testTone(nodeName: string): Promise<boolean> {
  await ensureTone();
  const r = await run("pw-play", ["--target", nodeName, TONE], 8000);
  return r.ok;
}

/** Light status for the dashboard/music state. */
export async function status(): Promise<{ available: boolean; sinks: Sink[]; default: string }> {
  const sinks = await listSinks();
  return { available, sinks, default: sinks.find((s) => s.isDefault)?.nodeName || "" };
}

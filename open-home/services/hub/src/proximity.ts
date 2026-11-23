/**
 * Room presence — "which room am I in, and which speaker is nearest?"
 *
 * The honest constraint: a single hub can measure how strong a Bluetooth signal
 * is, but not where it came from. One receiver cannot triangulate. So rather
 * than pretend, we invert the problem — the PHONE is already in the room, and it
 * can see every speaker and beacon around it. It reports what it hears; the hub
 * decides what that means.
 *
 *   phone  ──POST /rooms/proximity──►  hub  ──►  nearest room  ──►  agent/audio
 *   {readings:[{id, rssi}]}                      (sticky, hysteresis)
 *
 * Two things stop this flapping between rooms, which is what makes naive RSSI
 * useless in practice:
 *
 *   1. SMOOTHING — RSSI is extremely noisy (±10 dBm at rest). Each beacon keeps
 *      an exponential moving average rather than a raw last-value.
 *   2. HYSTERESIS — we only switch rooms when the new best beats the current one
 *      by SWITCH_MARGIN_DB. Without this you ping-pong on the boundary between
 *      two rooms all evening.
 *
 * Readings also expire: a phone that left the house should not still "be" in the
 * kitchen an hour later.
 *
 * Designed so swapping in fixed per-room scanners (ESP32/ESPresense) later means
 * only changing who calls report() — the room logic is identical, and better,
 * because the receivers stop moving.
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";

const FILE = new URL("../.data/proximity.json", import.meta.url);
const DATA_DIR = new URL("../.data/", import.meta.url);

/** How much stronger a room must look before we move the user into it. */
const SWITCH_MARGIN_DB = 6;
/** Weight of each new sample in the moving average (0..1). Lower = smoother. */
const EMA_ALPHA = 0.35;
/** A reading older than this is ignored when picking a room. */
const READING_TTL_MS = 90_000;
/** Presence older than this is dropped entirely — they've left. */
const PRESENCE_TTL_MS = 15 * 60_000;

export interface Beacon {
  /** Stable id — a BT MAC, a speaker id, or an ESPresense node name. */
  id: string;
  /** Which room this beacon physically lives in. */
  room: string;
  /** Optional friendly name for the UI. */
  name?: string;
  /** Speaker this beacon implies, so "play here" knows where to send audio. */
  speakerId?: string;
}

interface Smoothed { rssi: number; at: number }
interface Presence {
  client: string;
  room: string | null;
  confidence: number;
  since: number;
  at: number;
  beacons: Record<string, Smoothed>;
}

interface Store { beacons: Beacon[]; presence: Record<string, Presence> }

function load(): Store {
  try { return JSON.parse(readFileSync(FILE, "utf8")); }
  catch { return { beacons: [], presence: {} }; }
}
function save(s: Store) {
  try { mkdirSync(DATA_DIR, { recursive: true }); } catch {}
  writeFileSync(FILE, JSON.stringify(s, null, 2));
}

/** Register (or update) a beacon and the room it sits in. */
export function setBeacon(b: Beacon): Beacon[] {
  const s = load();
  const i = s.beacons.findIndex(x => x.id.toLowerCase() === b.id.toLowerCase());
  if (i >= 0) s.beacons[i] = { ...s.beacons[i], ...b };
  else s.beacons.push(b);
  save(s);
  return s.beacons;
}

export function removeBeacon(id: string): Beacon[] {
  const s = load();
  s.beacons = s.beacons.filter(b => b.id.toLowerCase() !== id.toLowerCase());
  save(s);
  return s.beacons;
}

export function beacons(): Beacon[] { return load().beacons; }

/**
 * A client reports what it can hear. Returns the room we now believe it is in.
 *
 * `readings` are raw RSSI in dBm (negative; closer to 0 is nearer).
 */
export function report(client: string, readings: { id: string; rssi: number }[]): Presence {
  const s = load();
  const now = Date.now();
  const prev: Presence = s.presence[client] ?? {
    client, room: null, confidence: 0, since: now, at: now, beacons: {},
  };

  // 1. Smooth each beacon's RSSI rather than trusting a single noisy sample.
  for (const r of readings) {
    if (typeof r?.rssi !== "number" || !r?.id) continue;
    const key = String(r.id).toLowerCase();
    const old = prev.beacons[key];
    const fresh = !old || now - old.at > READING_TTL_MS;
    prev.beacons[key] = {
      rssi: fresh ? r.rssi : old.rssi + EMA_ALPHA * (r.rssi - old.rssi),
      at: now,
    };
  }

  // 2. Best (strongest) live beacon per room.
  const known = new Map(s.beacons.map(b => [b.id.toLowerCase(), b]));
  const byRoom = new Map<string, number>();
  for (const [id, sm] of Object.entries(prev.beacons)) {
    if (now - sm.at > READING_TTL_MS) continue;
    const b = known.get(id);
    if (!b) continue;                       // unmapped beacon tells us nothing
    const cur = byRoom.get(b.room);
    if (cur === undefined || sm.rssi > cur) byRoom.set(b.room, sm.rssi);
  }

  const ranked = [...byRoom.entries()].sort((a, b) => b[1] - a[1]);
  const best = ranked[0];
  const runnerUp = ranked[1];

  // 3. Only move rooms on a clear win — otherwise we flap on the boundary.
  let room = prev.room;
  if (best) {
    const currentScore = prev.room ? (byRoom.get(prev.room) ?? -999) : -999;
    if (prev.room !== best[0] && best[1] > currentScore + SWITCH_MARGIN_DB) room = best[0];
    else if (!prev.room) room = best[0];
  }

  // Confidence = how decisively the winner beat second place.
  const confidence = best
    ? Math.max(0, Math.min(1, runnerUp ? (best[1] - runnerUp[1]) / 20 : 0.75))
    : 0;

  const next: Presence = {
    client, room, confidence,
    since: room === prev.room ? prev.since : now,
    at: now,
    beacons: prev.beacons,
  };
  s.presence[client] = next;

  // Forget clients that stopped reporting — they left.
  for (const [k, p] of Object.entries(s.presence)) {
    if (now - p.at > PRESENCE_TTL_MS) delete s.presence[k];
  }
  save(s);
  return next;
}

/** Everyone we currently believe is somewhere. */
export function presence(): Presence[] {
  const now = Date.now();
  return Object.values(load().presence).filter(p => now - p.at <= PRESENCE_TTL_MS);
}

/**
 * The room to act on when someone says "here" / "in this room".
 * Falls back to the most recently seen client if none is named.
 */
export function hereRoom(client?: string): { room: string | null; speakerId?: string; confidence: number } {
  const s = load();
  const now = Date.now();
  const list = Object.values(s.presence)
    .filter(p => now - p.at <= PRESENCE_TTL_MS)
    .sort((a, b) => b.at - a.at);
  const p = client ? s.presence[client] : list[0];
  if (!p || !p.room) return { room: null, confidence: 0 };
  const b = s.beacons.find(x => x.room === p.room && x.speakerId);
  return { room: p.room, speakerId: b?.speakerId, confidence: p.confidence };
}

/** Rooms that have at least one beacon mapped. */
export function rooms(): string[] {
  return [...new Set(load().beacons.map(b => b.room))].sort();
}

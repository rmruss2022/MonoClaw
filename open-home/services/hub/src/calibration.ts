/**
 * Room calibration + spatial audio engine.
 *
 * Turns a room full of speakers into a time-aligned, level-matched, spatial
 * soundstage — the same math Trueplay/Audyssey/Dirac use, mapped onto our
 * Snapcast multi-room layer:
 *
 *   1. Time-align — sound from the farthest speaker takes the longest to reach
 *      the seat, so every closer speaker is DELAYED by (dFar − d)/c. Applied as
 *      each Snapcast client's `latency`.
 *   2. Level-match — closer speakers are louder (inverse-square), so they get a
 *      negative gain trim of 20·log10(d/dFar) dB. Applied as client volume.
 *   3. Spatialize — a role→channel matrix upmixes stereo into L/R/center/
 *      surround/sub (a passive matrix decode), so the room images a soundstage.
 *
 * Speed of sound is temperature-corrected: c = 331.3·√(1 + T/273.15) m/s.
 *
 * Profiles persist per room to <data>/room-calibration.json. The numbers are
 * real and get pushed to Snapcast; the audible result needs the Snapcast server
 * + clients running on the hub (see /docs/run-hub).
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";

const DATA_DIR = new URL("../.data/", import.meta.url);
const FILE = new URL("../.data/room-calibration.json", import.meta.url);

export type SpatialMode = "stereo" | "surround" | "spatial";
export type Role = "stereo" | "left" | "right" | "center" | "surround-l" | "surround-r" | "sub" | "height-l" | "height-r";

export interface CalSpeaker { id: string; name?: string; role: Role; distanceM: number; delayMs: number; trimDb: number; }
export interface RoomProfile { room: string; mode: SpatialMode; tempC: number; speedMs: number; at: number; speakers: CalSpeaker[]; }

type Store = Record<string, RoomProfile>;
function load(): Store { try { return JSON.parse(readFileSync(FILE, "utf8")); } catch { return {}; } }
function save(s: Store) { try { mkdirSync(DATA_DIR, { recursive: true }); writeFileSync(FILE, JSON.stringify(s)); } catch (e) { console.log("[cal] save:", (e as Error).message); } }

export function speedOfSound(tempC = 20): number { return 331.3 * Math.sqrt(1 + tempC / 273.15); }

/** Auto-suggest a role layout from speaker count (stereo → 5.1-ish). */
export function suggestRoles(n: number): Role[] {
  if (n <= 1) return ["stereo"];
  if (n === 2) return ["left", "right"];
  if (n === 3) return ["left", "right", "center"];
  if (n === 4) return ["left", "right", "surround-l", "surround-r"];
  if (n === 5) return ["left", "right", "center", "surround-l", "surround-r"];
  return ["left", "right", "center", "surround-l", "surround-r", "sub", ...Array(Math.max(0, n - 6)).fill("stereo" as Role)];
}

/** Stereo(L,R) → per-role output coefficients (a passive matrix decode). */
export function channelMatrix(role: Role): { l: number; r: number; filter?: string } {
  switch (role) {
    case "left": return { l: 1, r: 0 };
    case "right": return { l: 0, r: 1 };
    case "center": return { l: 0.5, r: 0.5 };            // phantom center → real center
    case "surround-l": return { l: 0.5, r: -0.5, filter: "bandpass 200-7kHz, +12ms haas" };  // matrix surround (L−R)
    case "surround-r": return { l: -0.5, r: 0.5, filter: "bandpass 200-7kHz, +12ms haas" };
    case "height-l": return { l: 0.35, r: -0.35, filter: "highpass 1kHz (virtual height)" };
    case "height-r": return { l: -0.35, r: 0.35, filter: "highpass 1kHz (virtual height)" };
    case "sub": return { l: 0.5, r: 0.5, filter: "lowpass 80Hz" };
    default: return { l: 1, r: 1 };                       // stereo/mono: full range
  }
}

export interface CalInput { id: string; name?: string; role?: Role; distanceM?: number; }

/** Compute delay + trim for each speaker to align at the listening position. */
export function computeProfile(room: string, inputs: CalInput[], opts: { mode?: SpatialMode; tempC?: number } = {}): RoomProfile {
  const tempC = opts.tempC ?? 20;
  const c = speedOfSound(tempC);
  const roles = suggestRoles(inputs.length);
  const dists = inputs.map((i) => Math.max(0.3, i.distanceM ?? 3));
  const dFar = Math.max(...dists, 0.3);
  const speakers: CalSpeaker[] = inputs.map((i, idx) => {
    const d = Math.max(0.3, i.distanceM ?? 3);
    const delayMs = Math.round(((dFar - d) / c) * 1000 * 10) / 10;            // closer → more delay
    let trimDb = Math.round(20 * Math.log10(d / dFar) * 10) / 10;             // closer → attenuate
    trimDb = Math.max(-9, Math.min(0, trimDb));
    const role = i.role ?? roles[idx] ?? "stereo";
    return { id: i.id, name: i.name, role, distanceM: d, delayMs, trimDb: role === "sub" ? Math.max(-6, trimDb + 2) : trimDb };
  });
  return { room, mode: opts.mode ?? (inputs.length >= 4 ? "spatial" : inputs.length >= 2 ? "surround" : "stereo"), tempC, speedMs: Math.round(c * 10) / 10, at: Date.now(), speakers };
}

export function saveProfile(p: RoomProfile): RoomProfile { const s = load(); s[p.room] = p; save(s); return p; }
export function getProfile(room: string): RoomProfile | null { return load()[room] || null; }
export function clearProfile(room: string): void { const s = load(); delete s[room]; save(s); }
/** Calibration fields for a single speaker id (for merging into state). */
export function forSpeaker(room: string, id: string): { delayMs: number; trimDb: number; role: Role } | null {
  const p = load()[room]; if (!p) return null;
  const sp = p.speakers.find((x) => x.id === id); if (!sp) return null;
  return { delayMs: sp.delayMs, trimDb: sp.trimDb, role: sp.role };
}
export function calibratedRooms(): string[] { return Object.keys(load()); }

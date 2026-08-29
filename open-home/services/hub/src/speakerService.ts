/**
 * Speaker service — bridges live Spotify Connect devices (your Mac, iPhone, a
 * Sonos, etc.) into the openhome speaker/room model so they show up as real
 * speakers you can place in rooms, set volume on, and play to.
 *
 * Room assignments persist to <data>/speaker-rooms.json so a device keeps its
 * room across restarts. Playback routing and volume go through the real Spotify
 * Connect API; this is the live counterpart to the mock speakers in audio.ts.
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import * as spotify from "./spotify.ts";

const DATA_DIR = new URL("../.data/", import.meta.url);
const ROOMS_FILE = new URL("../.data/speaker-rooms.json", import.meta.url);

type RoomEntry = { room: string; name?: string };
type RoomMap = Record<string, RoomEntry>;

function loadRooms(): RoomMap { try { return JSON.parse(readFileSync(ROOMS_FILE, "utf8")); } catch { return {}; } }
function saveRooms(m: RoomMap) { try { mkdirSync(DATA_DIR, { recursive: true }); writeFileSync(ROOMS_FILE, JSON.stringify(m)); } catch (e) { console.log("[speakers] save:", (e as Error).message); } }

/** First-seen default room — keeps the Mac and the phone in separate rooms. */
function defaultRoom(type = "", name = ""): string {
  const t = type.toLowerCase(), n = name.toLowerCase();
  if (t === "smartphone" || n.includes("iphone") || n.includes("phone")) return "Bedroom";
  if (t === "computer" || n.includes("mac") || n.includes("book") || n.includes("web player")) return "Office";
  if (t === "speaker" || t === "avr" || t === "tv") return "Living Room";
  return "Living Room";
}

function kindOf(type = ""): string {
  const t = type.toLowerCase();
  if (t === "smartphone") return "airplay";
  if (t === "computer") return "wifi";
  if (t === "speaker" || t === "avr") return "wifi";
  return "wifi";
}

export interface LiveSpeaker {
  id: string; deviceId: string; name: string; room: string; kind: string;
  online: boolean; volume: number; muted: boolean; zone: null; role: string;
  latencyMs: number; calibrated: boolean; real: true; active: boolean; type: string;
}

let cache: LiveSpeaker[] = [];
export function cached(): LiveSpeaker[] { return cache.map((x) => ({ ...x })); }
export function deviceForSpeaker(id: string): LiveSpeaker | undefined { return cache.find((x) => x.id === id); }

/** Pull the live Connect devices and fold in persisted room/name assignments. */
export async function refresh(): Promise<void> {
  if (!spotify.connected()) { cache = []; return; }
  let ds: any[] = [];
  try { ds = await spotify.devices(); } catch { return; }
  const rooms = loadRooms();
  let changed = false;
  cache = ds.map((d: any) => {
    let e = rooms[d.id];
    if (!e) { e = { room: defaultRoom(d.type, d.name), name: d.name }; rooms[d.id] = e; changed = true; }
    return {
      id: "dev_" + d.id, deviceId: d.id, name: e.name || d.name, room: e.room || "—",
      kind: kindOf(d.type), online: true, volume: typeof d.volume === "number" ? d.volume : 50,
      muted: false, zone: null, role: "mono", latencyMs: 0, calibrated: false,
      real: true as const, active: !!d.active, type: d.type || "",
    };
  });
  // collapse duplicates that share a name (e.g. a device reconnecting), keeping
  // the active one so the list stays clean
  const byName = new Map<string, LiveSpeaker>();
  for (const s of cache) {
    const cur = byName.get(s.name);
    if (!cur || (s.active && !cur.active)) byName.set(s.name, s);
  }
  cache = [...byName.values()];
  if (changed) saveRooms(rooms);
}

export function setRoom(deviceId: string, room: string): void {
  const m = loadRooms(); const e = m[deviceId] || { room: "—" }; e.room = room || "—"; m[deviceId] = e; saveRooms(m);
  const c = cache.find((x) => x.deviceId === deviceId); if (c) c.room = e.room;
}

export function rename(deviceId: string, name: string): void {
  const m = loadRooms(); const e = m[deviceId] || { room: "Living Room" }; e.name = name; m[deviceId] = e; saveRooms(m);
  const c = cache.find((x) => x.deviceId === deviceId); if (c) c.name = name;
}

export async function setVolume(deviceId: string, v: number): Promise<boolean> {
  try { await spotify.setDeviceVolume(deviceId, v); const c = cache.find((x) => x.deviceId === deviceId); if (c) c.volume = Math.round(v); return true; }
  catch (e) { console.log("[speakers] volume:", (e as Error).message); return false; }
}

/** Transfer playback to whatever live speaker is assigned to `room`. */
export async function playRoom(room: string): Promise<string | null> {
  const sp = cache.find((x) => x.room === room);
  if (!sp) return null;
  try { await spotify.transfer(sp.deviceId, true); return sp.name; } catch { return null; }
}

/** Distinct rooms that currently have at least one live speaker. */
export function rooms(): string[] { return [...new Set(cache.map((x) => x.room))]; }

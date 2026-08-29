/**
 * openhome speaker service — the audio brain.
 *
 * Models speakers (WiFi / Bluetooth / AirPlay / Chromecast / Snapcast / openhome Pod),
 * groups them into zones, supports stereo-pair + surround roles with per-speaker latency
 * calibration, and drives a source (Spotify to start). Mock-but-real-shaped, like home.ts:
 * pure state + logic now, swapped for Snapcast + Music Assistant + librespot in Phase 1.
 *
 * Real backends this maps onto (see /docs/sound):
 *   - multi-room sync  → Snapcast (one client per speaker)
 *   - source bridging  → Music Assistant (Spotify / AirPlay / Cast / DLNA)
 *   - Spotify playback → librespot / Spotify Connect
 *   - Bluetooth        → BlueZ A2DP sink (convenience, single-room)
 */

import * as spotify from "./spotify.ts";
import * as speakerService from "./speakerService.ts";
import * as localAudio from "./localAudio.ts";
import * as calibration from "./calibration.ts";
import * as snapcast from "./snapcast.ts";

export type SpeakerKind = "wifi" | "bluetooth" | "airplay" | "chromecast" | "snapcast" | "pod";
export type Role = "mono" | "stereo" | "left" | "right" | "center" | "surround-l" | "surround-r" | "sub";

export interface Speaker {
  id: string;
  name: string;
  room: string;
  kind: SpeakerKind;
  online: boolean;
  volume: number;       // 0-100
  muted: boolean;
  zone: string | null;  // zone id, or null if standalone
  role: Role;           // position within a surround zone
  latencyMs: number;    // calibration delay to align this speaker in a zone
  calibrated: boolean;
}

export interface Zone {
  id: string;
  name: string;
  speakerIds: string[];
  surround: boolean;    // true once roles are assigned (2.0 / 3.1 / 5.1)
  volume: number;       // zone master 0-100
}

export interface NowPlaying {
  source: "spotify" | "bluetooth" | "airplay" | "radio" | "none";
  title: string; artist: string; album: string; art: string;
  playing: boolean;
  positionMs: number; durationMs: number;
  zoneId: string | null;
  device?: string;
}

const KIND_LABEL: Record<SpeakerKind, string> = {
  wifi: "Wi-Fi", bluetooth: "Bluetooth", airplay: "AirPlay",
  chromecast: "Chromecast", snapcast: "Snapcast", pod: "openhome Pod",
};

let seq = 100;
const nid = (p: string) => `${p}_${++seq}`;

function s(id: string, name: string, room: string, kind: SpeakerKind, volume: number, online = true): Speaker {
  return { id, name, room, kind, online, volume, muted: false, zone: null, role: "mono", latencyMs: 0, calibrated: false };
}

const speakers: Speaker[] = [
  s("spk_living", "Living Room", "Living Room", "wifi", 35),
  s("spk_living_r", "Living Room (Right)", "Living Room", "wifi", 35),
  s("spk_kitchen", "Kitchen", "Kitchen", "wifi", 28),
  s("spk_bedroom", "Bedroom Pod", "Bedroom", "pod", 20),
  s("spk_office", "Office", "Office", "airplay", 30),
  s("spk_portable", "Portable Speaker", "—", "bluetooth", 50, false),
];

const zones: Zone[] = [
  { id: "zone_living", name: "Living Room", speakerIds: ["spk_living", "spk_living_r"], surround: false, volume: 35 },
];
// reflect membership on the seeded speakers
for (const z of zones) for (const id of z.speakerIds) { const sp = speakers.find((x) => x.id === id); if (sp) sp.zone = z.id; }

let nowPlaying: NowPlaying = {
  source: "spotify",
  title: "Weightless", artist: "Marconi Union", album: "Ambient Works", art: "",
  playing: false, positionMs: 0, durationMs: 8 * 60_000,
  zoneId: "zone_living",
};

// ---- discovery (mock; real = mDNS/Snapcast for WiFi, BlueZ scan for BT) ----
const DISCOVERABLE: Record<"wifi" | "bluetooth", Array<{ name: string; room: string; kind: SpeakerKind }>> = {
  wifi: [
    { name: "Patio Speaker", room: "Backyard", kind: "wifi" },
    { name: "Bathroom Pod", room: "Bathroom", kind: "pod" },
    { name: "Sonos One", room: "Dining", kind: "airplay" },
  ],
  bluetooth: [
    { name: "JBL Flip 6", room: "—", kind: "bluetooth" },
    { name: "Bose SoundLink", room: "—", kind: "bluetooth" },
  ],
};

// ---------- reads ----------
export function kindLabel(k: SpeakerKind): string { return KIND_LABEL[k]; }
export function listSpeakers(): Speaker[] { return speakers.map((x) => ({ ...x })); }
export function listZones(): Zone[] { return zones.map((z) => ({ ...z, speakerIds: [...z.speakerIds] })); }

export function state() {
  const np = { ...nowPlaying };
  if (np.playing) np.positionMs = Math.min(np.durationMs, np.positionMs); // advanced by tick()
  // live Spotify Connect devices (your Mac, iPhone, …) show up as real speakers,
  // each in its assigned room, ahead of the mock demo speakers.
  const live = speakerService.cached();
  const local = localAudio.list().map((s) => ({
    id: s.id, name: s.name, room: s.room, kind: s.kind, online: s.status === "connected",
    volume: 40, muted: false, zone: null, role: "mono" as const, latencyMs: 0, calibrated: false,
    local: true as const, status: s.status, address: s.address, mac: s.mac,
  }));
  const merged = [...live, ...local, ...listSpeakers()];
  // annotate each speaker with its room calibration (delay/trim/role) if any
  const allSpeakers = merged.map((s: any) => {
    const cal = calibration.forSpeaker(s.room, s.id);
    return cal ? { ...s, cal, calibrated: true } : s;
  });
  const calRooms = calibration.calibratedRooms();
  return {
    nowPlaying: np,
    zones: listZones(),
    speakers: allSpeakers,
    calibratedRooms: calRooms,
    snapcast: snapcast.cached(),
    spotify: spotifyStatus(),
    counts: { speakers: allSpeakers.length, online: allSpeakers.filter((x) => x.online).length, zones: zones.length },
  };
}

export function discover(kind: "wifi" | "bluetooth") {
  const known = new Set(speakers.map((x) => x.name));
  return DISCOVERABLE[kind].filter((d) => !known.has(d.name));
}

// ---------- mutations ----------
export function addSpeaker(name: string, room: string, kind: SpeakerKind): Speaker {
  const sp = s(nid("spk"), name || "New Speaker", room || "—", kind, kind === "bluetooth" ? 50 : 30, true);
  speakers.push(sp);
  return { ...sp };
}
export function removeSpeaker(id: string): boolean {
  const i = speakers.findIndex((x) => x.id === id);
  if (i < 0) return false;
  const [sp] = speakers.splice(i, 1);
  if (sp.zone) { const z = zones.find((z) => z.id === sp.zone); if (z) z.speakerIds = z.speakerIds.filter((x) => x !== id); }
  return true;
}
export function setVolume(id: string, v: number): Speaker | Zone | null {
  const vol = Math.max(0, Math.min(100, Math.round(v)));
  const z = zones.find((z) => z.id === id);
  if (z) { z.volume = vol; for (const sid of z.speakerIds) { const sp = speakers.find((x) => x.id === sid); if (sp) sp.volume = vol; } return { ...z }; }
  const sp = speakers.find((x) => x.id === id);
  if (sp) { sp.volume = vol; return { ...sp }; }
  return null;
}
export function setMuted(id: string, muted: boolean): Speaker | null {
  const sp = speakers.find((x) => x.id === id);
  if (!sp) return null; sp.muted = muted; return { ...sp };
}

export function createZone(name: string, speakerIds: string[]): Zone {
  const z: Zone = { id: nid("zone"), name: name || "New Zone", speakerIds: [], surround: false, volume: 30 };
  zones.push(z);
  for (const id of speakerIds) addToZone(z.id, id);
  return { ...z };
}
export function addToZone(zoneId: string, speakerId: string): boolean {
  const z = zones.find((z) => z.id === zoneId); const sp = speakers.find((x) => x.id === speakerId);
  if (!z || !sp) return false;
  if (sp.zone && sp.zone !== zoneId) removeFromZone(sp.zone, speakerId);
  if (!z.speakerIds.includes(speakerId)) z.speakerIds.push(speakerId);
  sp.zone = zoneId; return true;
}
export function removeFromZone(zoneId: string, speakerId: string): boolean {
  const z = zones.find((z) => z.id === zoneId); if (!z) return false;
  z.speakerIds = z.speakerIds.filter((x) => x !== speakerId);
  const sp = speakers.find((x) => x.id === speakerId); if (sp && sp.zone === zoneId) { sp.zone = null; sp.role = "mono"; }
  if (z.speakerIds.length === 0) dissolveZone(zoneId);
  return true;
}
export function dissolveZone(zoneId: string): boolean {
  const i = zones.findIndex((z) => z.id === zoneId); if (i < 0) return false;
  for (const sid of zones[i].speakerIds) { const sp = speakers.find((x) => x.id === sid); if (sp) { sp.zone = null; sp.role = "mono"; } }
  zones.splice(i, 1);
  if (nowPlaying.zoneId === zoneId) nowPlaying.zoneId = null;
  return true;
}
export function setRole(speakerId: string, role: Role): Speaker | null {
  const sp = speakers.find((x) => x.id === speakerId); if (!sp) return null;
  sp.role = role;
  if (sp.zone) { const z = zones.find((z) => z.id === sp.zone); if (z) z.surround = z.speakerIds.some((id) => { const q = speakers.find((x) => x.id === id); return q && q.role !== "mono" && q.role !== "stereo"; }); }
  return { ...sp };
}

/** "Calibrate" a zone: measure + set per-speaker delay/level so the room is time-aligned. */
export function calibrate(zoneId: string): Zone | null {
  const z = zones.find((z) => z.id === zoneId); if (!z) return null;
  z.speakerIds.forEach((id, i) => {
    const sp = speakers.find((x) => x.id === id);
    if (sp) { sp.latencyMs = 4 + i * 3; sp.calibrated = true; } // stand-in for a real sweep/RTT alignment
  });
  return { ...z };
}

export function transport(action: "play" | "pause" | "next" | "prev" | "seek", ms?: number): NowPlaying {
  if (action === "play") nowPlaying.playing = true;
  else if (action === "pause") nowPlaying.playing = false;
  else if (action === "next" || action === "prev") { nowPlaying.positionMs = 0; nowPlaying.playing = true; }
  else if (action === "seek" && typeof ms === "number") nowPlaying.positionMs = Math.max(0, Math.min(nowPlaying.durationMs, ms));
  return { ...nowPlaying };
}
export function playInZone(zoneId: string): NowPlaying { nowPlaying.zoneId = zoneId; nowPlaying.playing = true; return { ...nowPlaying }; }

let liveFrom = 0; // timestamp of last real Spotify update

/** Mirror what Spotify is actually playing into Now Playing (called by the hub poll). */
export function applySpotifyPlayback(np: { title: string; artist: string; album: string; art: string; playing: boolean; positionMs: number; durationMs: number; device?: string }): void {
  nowPlaying = { source: "spotify", title: np.title, artist: np.artist, album: np.album, art: np.art, playing: np.playing, positionMs: np.positionMs, durationMs: np.durationMs, zoneId: nowPlaying.zoneId, device: np.device };
  liveFrom = Date.now();
}

/** advance the playhead so the UI feels live; skipped while a real Spotify feed is driving it. */
export function tick(dtMs: number): void {
  if (Date.now() - liveFrom < 8000) return; // Spotify is the source of truth
  if (nowPlaying.playing) {
    nowPlaying.positionMs += dtMs;
    if (nowPlaying.positionMs >= nowPlaying.durationMs) nowPlaying.positionMs = 0;
  }
}

// ---------- Spotify ----------
// Real integration lives in spotify.ts (OAuth + Web API). status() reflects it; the mock
// CATALOG below is only a fallback for when Spotify isn't connected yet.
export function spotifyStatus() { return spotify.status(); }

/** Set now-playing from a real track object {title,artist,album,image,durationMs}. */
export function setTrack(t: { title: string; artist?: string; album?: string; image?: string; durationMs?: number }, zoneId?: string): NowPlaying {
  nowPlaying = {
    source: "spotify", title: t.title, artist: t.artist ?? "", album: t.album ?? "", art: t.image ?? "",
    playing: true, positionMs: 0, durationMs: t.durationMs ?? 210_000, zoneId: zoneId ?? nowPlaying.zoneId,
  };
  return { ...nowPlaying };
}

const CATALOG = [
  { id: "t1", title: "Weightless", artist: "Marconi Union", album: "Ambient Works", durationMs: 8 * 60_000 },
  { id: "t2", title: "Nightcall", artist: "Kavinsky", album: "OutRun", durationMs: 258_000 },
  { id: "t3", title: "Redbone", artist: "Childish Gambino", album: "Awaken, My Love!", durationMs: 327_000 },
  { id: "t4", title: "Teardrop", artist: "Massive Attack", album: "Mezzanine", durationMs: 330_000 },
  { id: "t5", title: "Intro", artist: "The xx", album: "xx", durationMs: 128_000 },
  { id: "t6", title: "Sunset Lover", artist: "Petit Biscuit", album: "Petit Biscuit", durationMs: 235_000 },
];
export function spotifySearch(q: string) {
  const s = (q || "").toLowerCase().trim();
  const hits = s ? CATALOG.filter((t) => (t.title + " " + t.artist + " " + t.album).toLowerCase().includes(s)) : CATALOG;
  return hits.slice(0, 12);
}
export function spotifyPlay(trackId: string, zoneId?: string): NowPlaying | null {
  const t = CATALOG.find((x) => x.id === trackId); if (!t) return null;
  nowPlaying = { source: "spotify", title: t.title, artist: t.artist, album: t.album, art: "", playing: true, positionMs: 0, durationMs: t.durationMs, zoneId: zoneId ?? nowPlaying.zoneId };
  return { ...nowPlaying };
}

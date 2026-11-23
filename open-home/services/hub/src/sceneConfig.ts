/**
 * User-configurable scene actions — what a named scene ("good_morning") does on REAL
 * devices (lights + a pinned Spotify playlist), vs the mock scene in home.ts.
 * Persisted crash-safe to <data>/scene-config.json; seeded on first run.
 */
import { durableStore } from "./durableStore.ts";

const DATA_DIR = new URL("../.data/", import.meta.url);

export interface RGB { r: number; g: number; b: number }
export interface SceneLight { room?: string; id?: string; on: boolean; brightness?: number; rgb?: RGB }
// contextUri is any Spotify context: a playlist (spotify:playlist:…) or an artist
// (spotify:artist:…). shuffle plays it in a random order.
// `query` is the alternative to a pinned contextUri: the scene searches Spotify for
// it at run time. The stored config on the Pi used {source, query} while the runner
// only understood contextUri, so "good morning" silently played nothing for weeks.
// Both shapes are supported now; whichever is present wins, contextUri first.
export interface SceneMusic { contextUri?: string; query?: string; source?: string; name?: string; shuffle?: boolean }
export interface SceneActions { lights?: SceneLight[]; music?: SceneMusic | null }

// Time-of-day scenes. Morning also turns on the warm-orange Living Room light + reads
// the NYC daily report (the report is wired to the "good morning" trigger, not here).
const DEFAULTS: Record<string, SceneActions> = {
  good_morning: {
    lights: [{ room: "Living Room", on: true, brightness: 100, rgb: { r: 255, g: 130, b: 30 } }],
    music: { contextUri: "spotify:playlist:6SzaqnY0tHF6TY6EUtp0EQ", name: "Upbeat Morning Jazz", shuffle: true },
  },
  afternoon: {
    music: { contextUri: "spotify:artist:2M3sfEXSEDYBurdjeExx6G", name: "Palm Monkey", shuffle: true },
  },
  evening: {
    music: { contextUri: "spotify:playlist:37talafIK8enbbryNV5ZCg", name: "Morning Café Jazz", shuffle: true },
  },
};

const store = durableStore<Record<string, SceneActions>>(DATA_DIR, "scene-config.json", "scenes");
let cfg: Record<string, SceneActions> = store.load({});
{
  let changed = false;
  for (const [k, v] of Object.entries(DEFAULTS)) { if (!cfg[k]) { cfg[k] = v; changed = true; } }
  if (changed) store.save(cfg);
}

export function getScene(id: string): SceneActions | undefined { return cfg[id]; }
export function setScene(id: string, actions: SceneActions): void { cfg[id] = actions; store.save(cfg); }
export function allScenes(): Record<string, SceneActions> { return cfg; }

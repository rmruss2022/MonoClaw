/**
 * User-configurable scene actions — what a named scene ("good_morning") does on REAL
 * devices (lights + a pinned Spotify playlist), vs the mock scene in home.ts.
 * Persisted crash-safe to <data>/scene-config.json; seeded on first run.
 */
import { durableStore } from "./durableStore.ts";

const DATA_DIR = new URL("../.data/", import.meta.url);

export interface RGB { r: number; g: number; b: number }
export interface SceneLight { room?: string; id?: string; on: boolean; brightness?: number; rgb?: RGB }
export interface SceneMusic { playlistUri?: string; name?: string }
export interface SceneActions { lights?: SceneLight[]; music?: SceneMusic | null }

// good_morning: Living Room light ON, warm white at 100%, + the Morning Café Jazz playlist.
const DEFAULTS: Record<string, SceneActions> = {
  good_morning: {
    lights: [{ room: "Living Room", on: true, brightness: 100, rgb: { r: 255, g: 180, b: 107 } }],
    music: { playlistUri: "spotify:playlist:37talafIK8enbbryNV5ZCg", name: "Morning Café Jazz" },
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

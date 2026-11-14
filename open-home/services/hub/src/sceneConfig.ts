/**
 * User-configurable scene actions — what a named scene ("good_morning", …) should
 * actually DO on real devices (turn on specific lights, play specific music), as
 * opposed to the mock/demo scene in home.ts.
 *
 * Persisted (crash-safe) to <data>/scene-config.json so a user's configured scene
 * survives restarts. Seeded with sensible defaults on first run; editable via
 * setScene() (e.g. an endpoint or a future "set my morning scene to …" voice flow).
 */
import { durableStore } from "./durableStore.ts";

const DATA_DIR = new URL("../.data/", import.meta.url);

export interface RGB { r: number; g: number; b: number }
export interface SceneLight { room?: string; id?: string; on: boolean; brightness?: number; rgb?: RGB }
export interface SceneMusic { source: "spotify" | "soundcloud"; query: string }
export interface SceneActions { lights?: SceneLight[]; music?: SceneMusic | null }

// First-run defaults. good_morning: turn on the Living Room light + play 2026 jazz.
const DEFAULTS: Record<string, SceneActions> = {
  good_morning: {
    lights: [{ room: "Living Room", on: true }],
    music: { source: "spotify", query: "2026 jazz" },
  },
};

const store = durableStore<Record<string, SceneActions>>(DATA_DIR, "scene-config.json", "scenes");
let cfg: Record<string, SceneActions> = store.load({});

// Seed any missing defaults and persist, so the configured scene is a real saved
// record (not just an in-memory code default).
{
  let changed = false;
  for (const [k, v] of Object.entries(DEFAULTS)) {
    if (!cfg[k]) { cfg[k] = v; changed = true; }
  }
  if (changed) store.save(cfg);
}

export function getScene(id: string): SceneActions | undefined { return cfg[id]; }
export function setScene(id: string, actions: SceneActions): void { cfg[id] = actions; store.save(cfg); }
export function allScenes(): Record<string, SceneActions> { return cfg; }

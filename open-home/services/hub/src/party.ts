/**
 * Party mode — flash the REAL color lights through vivid colors to the music.
 *
 * Without real-time audio DSP (and with Spotify's audio-features endpoint 403ing for
 * new apps) we drive a lively, rhythmic color cycle. If we can read the current track's
 * tempo we sync the flash to the beat; otherwise we fall back to a fixed upbeat interval.
 * Each light gets a different color offset so the room looks alive, not uniform.
 */
import * as lights from "./lights.ts";
import * as spotify from "./spotify.ts";

const PARTY_COLORS = [
  { r: 255, g: 0, b: 0 },     // red
  { r: 255, g: 110, b: 0 },   // orange
  { r: 255, g: 230, b: 0 },   // yellow
  { r: 0, g: 255, b: 0 },     // green
  { r: 0, g: 255, b: 255 },   // cyan
  { r: 0, g: 90, b: 255 },    // blue
  { r: 160, g: 0, b: 255 },   // violet
  { r: 255, g: 0, b: 190 },   // magenta
];

let timer: ReturnType<typeof setInterval> | null = null;
let tick = 0;

export function isOn(): boolean {
  return timer !== null;
}

function colorLights() {
  // Real, color-capable, online lights only.
  return lights.listLights().filter((l: any) => l.real && l.color && l.online !== false);
}

async function step() {
  try {
    const ls = colorLights();
    for (let i = 0; i < ls.length; i++) {
      const c = PARTY_COLORS[(tick + i) % PARTY_COLORS.length];
      lights.control(ls[i].id, { on: true, rgb: c, brightness: 100 }).catch(() => {});
    }
    tick++;
  } catch { /* keep the party going */ }
}

/** Start the party. Tries to beat-match the current track's tempo, else ~130 BPM feel. */
export async function start(): Promise<{ ok: boolean; lights: number; intervalMs: number }> {
  stop();
  tick = 0;
  let intervalMs = 460;   // ~130 BPM default
  try {
    const bpm = await spotify.trackTempo();
    if (bpm && bpm > 40 && bpm < 220) {
      // flash on the beat (halve very fast tempos so it isn't a seizure)
      intervalMs = Math.round(60000 / (bpm > 150 ? bpm / 2 : bpm));
    }
  } catch { /* no tempo — use default */ }
  await step();
  timer = setInterval(step, intervalMs);
  return { ok: true, lights: colorLights().length, intervalMs };
}

/** Stop the party. By default settles the lights to warm white; pass restore=false when
 * another light command is about to set its own color (so we don't fight it). */
export function stop(restore = true): void {
  if (timer) { clearInterval(timer); timer = null; }
  if (!restore) return;
  try {
    for (const l of colorLights()) {
      lights.control(l.id, { on: true, rgb: { r: 255, g: 180, b: 107 }, brightness: 100 }).catch(() => {});
    }
  } catch { /* ignore */ }
}

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
// Which room the party is in, if it was asked for by room. Held for the life of
// the party so every tick drives the same set of bulbs.
let room: string | null = null;

export function isOn(): boolean {
  return timer !== null;
}

function colorLights() {
  // Real, color-capable, online lights only.
  const all = lights.listLights().filter((l: any) => l.real && l.color && l.online !== false);
  if (!room) return all;
  const inRoom = all.filter((l: any) => String(l.room || "").toLowerCase().includes(room!));
  // "Party mode in the living room" should not mean "no party" just because
  // the room name did not match how the bulb is labelled.
  return inRoom.length ? inRoom : all;
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
export async function start(inRoom?: string): Promise<{ ok: boolean; lights: number; intervalMs: number; bpm: number | null }> {
  stop(false, "restarting");
  tick = 0;
  room = inRoom ? inRoom.toLowerCase().replace(" room", "") : null;
  let intervalMs = 460;   // ~130 BPM default
  let bpm: number | null = null;
  try {
    bpm = await spotify.trackTempo();
    if (bpm && bpm > 40 && bpm < 220) {
      // flash on the beat (halve very fast tempos so it isn't a seizure)
      intervalMs = Math.round(60000 / (bpm > 150 ? bpm / 2 : bpm));
    }
  } catch { /* no tempo — use default */ }
  const n = colorLights().length;
  // Say so rather than reporting a party that is flashing nothing. There is
  // exactly one colour-capable bulb on this house right now, so "0" is a real
  // outcome worth hearing about, not an edge case.
  console.log(`[party] ${n} colour light${n === 1 ? "" : "s"}${room ? ` in ${room}` : ""}, ` +
    (bpm ? `beat-matched to ${Math.round(bpm)} BPM` : "no tempo from Spotify — using a 130 BPM feel") +
    ` (${intervalMs}ms)`);
  await step();
  timer = setInterval(step, intervalMs);
  return { ok: true, lights: n, intervalMs, bpm };
}

/** Stop the party. By default settles the lights to warm white; pass restore=false when
 * another light command is about to set its own color (so we don't fight it). */
/**
 * Stop the party. `why` is not decoration.
 *
 * The party gets stopped as a SIDE EFFECT from several places — any direct
 * light command, any other scene — and none of them said so. When a running
 * party went dark unexpectedly the only evidence left was the bulb's final
 * colour, which had to be matched against PARTY_COLORS by hand to work out
 * that an unrelated light command had killed it. One log line would have
 * answered it instantly.
 */
export function stop(restore = true, why = "asked"): void {
  if (timer) { clearInterval(timer); timer = null; console.log(`[party] stopped (${why})`); }
  if (!restore) { room = null; return; }
  try {
    for (const l of colorLights()) {
      lights.control(l.id, { on: true, rgb: { r: 255, g: 180, b: 107 }, brightness: 100 }).catch(() => {});
    }
  } catch { /* ignore */ }
  room = null;
}

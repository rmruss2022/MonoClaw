/**
 * The Python test suite, ported alongside the engine.
 *
 * The point is not coverage for its own sake: the phone and the Pi must agree
 * about what a double tap is, so the port needs to be demonstrably faithful.
 * These are the same nine cases as test_gestures.py, plus the same sample-rate
 * sweep, so a disagreement between the two implementations shows up here
 * rather than in Matthew's living room.
 *
 * No test framework — the app has none, and adding one to prove a port is the
 * wrong trade. Run it directly:
 *
 *   npx tsx src/ring/gestures.test.ts
 *   # or: node --experimental-strip-types src/ring/gestures.test.ts
 */
// Values and types split: node's type-stripping cannot import a type as a
// value, and these three are types.
import { COUNTS_PER_G, DEFAULT_CONFIG, Engine } from "./gestures.ts";
import type { Config, Gesture, Sample } from "./gestures.ts";

const G = COUNTS_PER_G;

function trace(opts: {
  duration: number;
  hz: number;
  taps?: number[];
  spike?: number;
  spikeWidth?: number;
  rollRamp?: [number, number, number];
}): Sample[] {
  const { duration, hz, taps = [], spike = 4000, spikeWidth = 0.03, rollRamp } = opts;
  const out: Sample[] = [];
  const n = Math.floor(duration * hz);
  for (let i = 0; i < n; i++) {
    const t = i / hz;
    let ang = 0;
    if (rollRamp) {
      const [s0, s1, deg] = rollRamp;
      if (t >= s1) ang = deg;
      else if (t > s0) ang = (deg * (t - s0)) / (s1 - s0);
    }
    const rad = (ang * Math.PI) / 180;
    let z = G * Math.cos(rad);
    const y = G * Math.sin(rad);
    for (const tp of taps) {
      if (Math.abs(t - tp) <= spikeWidth / 2) z += spike;
    }
    out.push({ x: 0, y, z, t });
  }
  return out;
}

function run(samples: Sample[], cfg?: Partial<Config>): Gesture[] {
  const got: Gesture[] = [];
  const e = new Engine((g) => got.push(g), cfg);
  for (const s of samples) e.feed(s);
  e.tick(samples[samples.length - 1].t + 1);
  return got;
}

const kinds = (gs: Gesture[]) => gs.map((g) => g.kind);

// ------------------------------------------------------------------ tests ---
const tests: Array<[string, () => string]> = [
  ["still hand -> nothing", () => {
    const gs = run(trace({ duration: 5, hz: 250 }));
    if (gs.length) throw new Error(`a still hand produced ${kinds(gs)}`);
    return "still hand -> nothing";
  }],
  ["one tap -> tap", () => {
    const gs = run(trace({ duration: 4, hz: 250, taps: [2.0] }));
    if (kinds(gs).join() !== "tap") throw new Error(kinds(gs).join());
    return "one tap -> tap";
  }],
  ["double tap @250Hz", () => {
    const gs = run(trace({ duration: 4, hz: 250, taps: [2.0, 2.2] }));
    if (!kinds(gs).includes("double_tap")) throw new Error(kinds(gs).join());
    if (!kinds(gs).includes("music_enter")) throw new Error("double tap should open music mode");
    return "double tap @250Hz -> double_tap + music_enter";
  }],
  ["triple tap", () => {
    const gs = run(trace({ duration: 4, hz: 250, taps: [2.0, 2.18, 2.36] }));
    if (!kinds(gs).includes("triple_tap")) throw new Error(kinds(gs).join());
    if (kinds(gs).includes("music_enter")) throw new Error("triple must NOT open music mode");
    return "triple tap -> triple_tap, no music mode";
  }],
  ["wide spike is still one tap", () => {
    // Hysteresis. A 40 ms spike at 250 Hz spans ~10 samples; without the
    // release band that reads as ten taps.
    const gs = run(trace({ duration: 4, hz: 250, taps: [2.0], spikeWidth: 0.04 }));
    if (kinds(gs).join() !== "tap") throw new Error(`hysteresis failed: ${kinds(gs)}`);
    return "wide single spike -> still one tap";
  }],
  ["sustained press -> hold", () => {
    const samples: Sample[] = [];
    for (let i = 0; i < 4 * 250; i++) {
      const t = i / 250;
      const extra = t >= 1.0 && t <= 2.5 ? 4000 : 0;
      samples.push({ x: 0, y: 0, z: G + extra, t });
    }
    const gs = run(samples);
    if (!kinds(gs).includes("hold")) throw new Error(kinds(gs).join());
    return "sustained press -> hold";
  }],
  ["roll in music mode moves volume", () => {
    const gs = run(trace({ duration: 6, hz: 250, taps: [1.0, 1.2], rollRamp: [1.8, 2.8, 40] }));
    if (!kinds(gs).includes("music_enter")) throw new Error(kinds(gs).join());
    const vols = gs.filter((g) => g.kind === "music_volume");
    if (!vols.length) throw new Error(`no volume events: ${kinds(gs)}`);
    const last = vols[vols.length - 1].value ?? 0;
    if (last <= 25) throw new Error(`expected a large roll delta, got ${last}`);
    return `roll 40deg -> ${vols.length} volume events, last ${last}deg`;
  }],
  ["music mode times out", () => {
    const gs = run(trace({ duration: 9, hz: 250, taps: [1.0, 1.2] }));
    if (!kinds(gs).includes("music_exit")) throw new Error(kinds(gs).join());
    return "music mode exits on idle";
  }],
  ["roll with no wake gesture -> nothing", () => {
    // The whole reason the mode is modal: a hand rotates all day.
    const gs = run(trace({ duration: 6, hz: 250, rollRamp: [1.0, 3.0, 70] }));
    if (gs.length) throw new Error(`roll without a wake gesture emitted ${kinds(gs)}`);
    return "roll with no wake gesture -> nothing";
  }],
];

function rateSweep(): void {
  const rates = [12, 25, 50, 125, 250];
  const gaps = [0.1, 0.15, 0.2, 0.25, 0.3];
  if (Math.max(...gaps) >= DEFAULT_CONFIG.burstEnd) throw new Error("gaps must be inside the burst window");
  console.log("\n  double-tap detection, by sample rate and inter-tap gap");
  console.log(`  (tap = 30 ms transient; burst window = ${DEFAULT_CONFIG.burstEnd * 1000} ms;`);
  console.log("   8 phase offsets per cell, since whether a transient lands on a");
  console.log("   sample is luck at low rates)\n");
  console.log("        gap:" + gaps.map((g) => `${Math.round(g * 1000)}ms`.padStart(7)).join(""));
  for (const hz of rates) {
    let row = `  ${String(hz).padStart(5)} Hz:  `;
    for (const gap of gaps) {
      let detected = 0;
      const trials = 8;
      for (let p = 0; p < trials; p++) {
        const offset = p / trials / hz;
        const gs = run(trace({ duration: 4, hz, taps: [2 + offset, 2 + offset + gap] }));
        if (kinds(gs).includes("double_tap")) detected++;
      }
      const ok = detected >= trials / 2;
      row += `${(ok ? "D" : ".") + `(${detected}/${trials})`}`.padStart(9);
    }
    console.log(row);
  }
  console.log();
}

let failed = 0;
console.log("gesture engine tests (TypeScript port)\n");
for (const [name, fn] of tests) {
  try {
    console.log(`   ok   ${fn()}`);
  } catch (e) {
    failed++;
    console.log(`  FAIL  ${name}: ${(e as Error).message}`);
  }
}
rateSweep();
console.log(`  ${tests.length - failed}/${tests.length} tests passed`);
if (failed) process.exit(1);

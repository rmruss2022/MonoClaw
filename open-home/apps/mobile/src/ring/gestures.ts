/**
 * Ring gestures — a direct port of services/ring-bridge/gestures.py.
 *
 * WHY A PORT AND NOT A SECOND DESIGN
 * The phone and the Pi must agree about what a double tap is, or the same
 * knock does different things depending on which radio heard it. So this is
 * deliberately a line-by-line port rather than an idiomatic rewrite: same
 * constants, same state machine, same ordering. The Python tests were ported
 * alongside it (gestures.test.ts) so "the port is faithful" is a checked claim
 * rather than an intention.
 *
 * No Bluetooth in this file. It is a function of (x, y, z, t), which is what
 * makes it testable without a ring — see the test file.
 */

/** Counts per g. Logging only; the rest level is calibrated, not assumed. */
export const COUNTS_PER_G = 8192;

export type GestureKind =
  | "tap" | "double_tap" | "triple_tap" | "hold"
  | "music_enter" | "music_volume" | "music_exit";

export interface Sample {
  x: number;
  y: number;
  z: number;
  /** seconds, monotonic */
  t: number;
}

export interface Gesture {
  kind: GestureKind;
  at: number;
  /** music_volume: signed degrees since mode entry */
  value?: number;
  /** hand orientation from BEFORE the gesture, when obtainable */
  orientation?: [number, number, number];
}

export interface Config {
  jolt: number;
  release: number;
  still: number;
  minGap: number;
  burstEnd: number;
  maxGap: number;
  refractory: number;
  holdTime: number;
  calibrateN: number;
  restAlpha: number;
  orientationLead: number;
  orientationMaxAge: number;
  musicTimeout: number;
  musicDeadzoneDeg: number;
  musicStepDeg: number;
  /** Which axis pair gives roll. Depends on how the ring sits on the finger. */
  rollAxes: ["x" | "y" | "z", "x" | "y" | "z"];
}

/** Identical to the Python defaults. Change both or neither. */
export const DEFAULT_CONFIG: Config = {
  jolt: 1200,
  release: 700,
  still: 500,
  minGap: 0.05,
  burstEnd: 0.35,
  maxGap: 0.6,
  refractory: 0.4,
  holdTime: 0.9,
  calibrateN: 15,
  restAlpha: 0.02,
  orientationLead: 0.3,
  orientationMaxAge: 4.0,
  musicTimeout: 5.0,
  musicDeadzoneDeg: 8,
  musicStepDeg: 5,
  rollAxes: ["y", "z"],
};

export function magnitude(s: Sample): number {
  return Math.sqrt(s.x * s.x + s.y * s.y + s.z * s.z);
}

/**
 * Wrist roll from the gravity vector. A 3-axis accelerometer at rest measures
 * gravity, so the angle between two axes IS the orientation — no gyro. Only
 * valid while the hand is not accelerating, which the caller gates on.
 */
export function rollDegrees(s: Sample, axes: Config["rollAxes"]): number {
  return (Math.atan2(s[axes[0]], s[axes[1]]) * 180) / Math.PI;
}

function median(xs: number[]): number {
  const a = [...xs].sort((p, q) => p - q);
  return a[Math.floor(a.length / 2)];
}

export class Engine {
  readonly cfg: Config;
  private emit: (g: Gesture) => void;
  rest: number | null = null;
  private calib: number[] = [];
  private armed = true;
  private burst: number[] = [];
  private lastReport = -1e9;
  private stillHist: Array<{ t: number; v: [number, number, number] }> = [];
  private aboveSince: number | null = null;
  private holdFired = false;
  musicUntil: number | null = null;
  private musicRef: number | null = null;
  private musicLast = 0;

  constructor(onGesture: (g: Gesture) => void, cfg?: Partial<Config>) {
    this.emit = onGesture;
    this.cfg = { ...DEFAULT_CONFIG, ...(cfg ?? {}) };
  }

  /**
   * The pose from just before `when`, or undefined.
   *
   * Two exclusions carried over from the prior art, both learned the hard way:
   * readings AFTER the gesture began are a lie (mid-swing looks like pure
   * gravity while the wrist has already turned), and stale readings are worse
   * than none because they match confidently and wrongly.
   */
  private orientationBefore(when: number): [number, number, number] | undefined {
    const cutoff = when - this.cfg.orientationLead;
    const usable = this.stillHist.filter((h) => h.t <= cutoff);
    if (usable.length === 0) return undefined;
    if (when - usable[usable.length - 1].t > this.cfg.orientationMaxAge) return undefined;
    const recent = usable.slice(-8).map((h) => h.v);
    const n = recent.length;
    return [
      recent.reduce((a, v) => a + v[0], 0) / n,
      recent.reduce((a, v) => a + v[1], 0) / n,
      recent.reduce((a, v) => a + v[2], 0) / n,
    ];
  }

  feed(s: Sample): void {
    const mag = magnitude(s);

    if (this.rest === null) {
      this.calib.push(mag);
      if (this.calib.length >= this.cfg.calibrateN) this.rest = median(this.calib);
      return;
    }

    const dev = Math.abs(mag - this.rest);
    const quiet = dev < this.cfg.release;

    if (quiet) {
      // Track drift, but only while nothing is happening — otherwise a gesture
      // moves the reference it is being measured against.
      this.rest += this.cfg.restAlpha * (mag - this.rest);
      this.armed = true;
      this.aboveSince = null;
      this.holdFired = false;
    }

    if (dev < this.cfg.still) {
      this.stillHist.push({ t: s.t, v: [s.x, s.y, s.z] });
      while (this.stillHist.length && s.t - this.stillHist[0].t > 15) this.stillHist.shift();
    }

    if (this.musicUntil !== null) {
      if (this.musicTick(s, dev)) return;
    }

    if (dev >= this.cfg.jolt) {
      if (this.aboveSince === null) {
        this.aboveSince = s.t;
      } else if (
        !this.holdFired &&
        s.t - this.aboveSince >= this.cfg.holdTime &&
        this.burst.length <= 1
      ) {
        this.holdFired = true;
        this.report("hold", s.t, this.aboveSince);
        return;
      }
    }

    if (this.burst.length) {
      const gap = s.t - this.burst[this.burst.length - 1];
      if (gap > this.cfg.burstEnd || gap > this.cfg.maxGap) this.closeBurst(s.t);
    }

    if (s.t - this.lastReport < this.cfg.refractory) return;
    if (dev < this.cfg.jolt || !this.armed) return;

    // Hysteresis: nothing counts again until it settles back inside `release`.
    this.armed = false;
    if (this.burst.length && s.t - this.burst[this.burst.length - 1] < this.cfg.minGap) {
      return; // same tap, seen twice
    }
    this.burst.push(s.t);
  }

  private closeBurst(now: number): void {
    const n = this.burst.length;
    const start = this.burst.length ? this.burst[0] : now;
    this.burst = [];
    if (n === 0 || this.holdFired) return;
    const kind: GestureKind = n === 1 ? "tap" : n === 2 ? "double_tap" : "triple_tap";
    this.report(kind, now, start);
    if (kind === "double_tap") this.musicOpen(now);
  }

  private report(kind: GestureKind, now: number, eventStart: number): void {
    this.lastReport = now;
    this.emit({ kind, at: now, orientation: this.orientationBefore(eventStart) });
  }

  private musicOpen(now: number): void {
    this.musicUntil = now + this.cfg.musicTimeout;
    this.musicRef = null;
    this.musicLast = 0;
    this.emit({ kind: "music_enter", at: now });
  }

  /** True if music mode consumed this sample. */
  private musicTick(s: Sample, dev: number): boolean {
    if (this.musicUntil === null) return false;
    if (s.t > this.musicUntil) {
      this.musicUntil = null;
      this.emit({ kind: "music_exit", at: s.t });
      return false;
    }
    // Roll is only meaningful while the hand is not accelerating — atan2 on a
    // moving hand measures the movement, not the pose.
    if (dev >= this.cfg.still) return false;

    const roll = rollDegrees(s, this.cfg.rollAxes);
    if (this.musicRef === null) {
      this.musicRef = roll;
      return true;
    }
    let delta = roll - this.musicRef;
    while (delta > 180) delta -= 360;
    while (delta < -180) delta += 360;

    if (Math.abs(delta) < this.cfg.musicDeadzoneDeg) return true;
    if (Math.abs(delta - this.musicLast) < this.cfg.musicStepDeg) return true;

    this.musicLast = delta;
    this.musicUntil = s.t + this.cfg.musicTimeout; // real input keeps it open
    this.emit({ kind: "music_volume", at: s.t, value: Math.round(delta * 10) / 10 });
    return true;
  }

  /** Call when samples stop arriving, so a trailing burst still closes. */
  tick(now: number): void {
    if (this.burst.length && now - this.burst[this.burst.length - 1] > this.cfg.burstEnd) {
      this.closeBurst(now);
    }
    if (this.musicUntil !== null && now > this.musicUntil) {
      this.musicUntil = null;
      this.emit({ kind: "music_exit", at: now });
    }
  }
}

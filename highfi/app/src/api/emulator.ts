// Full in-browser fake HighFi device. Speaks the exact same protocol as the
// firmware: emits a snapshot on connect, then streams deltas from a live model
// (playback clock, battery drain, vape coil physics + safety interlocks).
//
// This is the "build the emulator first, wire real hardware to the same seam"
// pattern the product owner loves. Nothing here talks to a network — the whole
// app is usable and testable with zero hardware.

import type { DeviceConnection } from "./connection.ts";
import {
  applyDelta,
  setLibrary,
  setSnapshot,
  setStatus,
} from "../state.ts";
import {
  VAPE_LIMITS,
  clampVolts,
  clampVolume,
  clampWatts,
  type DeviceState,
  type RepeatMode,
  type StateDeltaMsg,
  type Track,
  type VapeFault,
  type VapeSetPayload,
} from "../protocol.ts";

const TICK_MS = 250;
const AMBIENT_C = 22;

const LIBRARY: Track[] = [
  { id: "01", title: "Golden Hour", artist: "Velvet Ember", durationS: 198 },
  { id: "02", title: "Slow Burn", artist: "The Low Watts", durationS: 241 },
  { id: "03", title: "Amber Room", artist: "Kishi Bloom", durationS: 176 },
  { id: "04", title: "Purple Static", artist: "Nyx & Sol", durationS: 223 },
  { id: "05", title: "Cloudchaser", artist: "Meridian", durationS: 205 },
  { id: "06", title: "Ohm", artist: "Coil & Cadence", durationS: 312 },
  { id: "07", title: "Elevated", artist: "Highfidelity", durationS: 214 },
  { id: "08", title: "Draw Sensor", artist: "MEMS", durationS: 188 },
  { id: "09", title: "Terpene Dream", artist: "Rosin Radio", durationS: 260 },
  { id: "10", title: "Cutoff (10s)", artist: "Safety First", durationS: 143 },
];

function initialState(): DeviceState {
  return {
    audio: {
      playing: false,
      track: LIBRARY[6], // "Elevated" — matches SPEC example track "07"
      positionS: 42,
      volume: 60,
      repeat: "off",
      shuffle: false,
    },
    vape: {
      locked: true, // ships locked — SPEC §5.5
      firing: false,
      mode: "voltage",
      setVolts: 3.2,
      setWatts: 9,
      coilOhms: 1.2,
      coilTempC: AMBIENT_C,
      sessionS: 0,
      cartPresent: true,
      fault: "locked",
    },
    power: { battPct: 76, charging: false, voltage: 3.86 },
    device: {
      name: "HighFi (emulator)",
      fw: "0.1.0-sim",
      wifi: "ap",
      ip: "192.168.4.1",
    },
  };
}

export class Emulator implements DeviceConnection {
  private s: DeviceState = initialState();
  private timer: number | null = null;
  private fireHeld = false;
  private battAccumS = 0;

  connect(): void {
    this.s = initialState();
    setStatus("connecting");
    // Emulate the tiny handshake latency of a real socket.
    window.setTimeout(() => {
      setSnapshot(structuredClone(this.s));
      setLibrary(LIBRARY);
      setStatus("connected");
      this.timer = window.setInterval(() => this.tick(), TICK_MS);
    }, 180);
  }

  disconnect(): void {
    if (this.timer !== null) {
      clearInterval(this.timer);
      this.timer = null;
    }
    this.fireHeld = false;
    setStatus("offline");
  }

  // --- the model clock ----------------------------------------------------

  private tick(): void {
    const dt = TICK_MS / 1000;
    const delta: StateDeltaMsg = { t: "delta" };

    // audio playback clock
    if (this.s.audio.playing && this.s.audio.track) {
      let pos = this.s.audio.positionS + dt;
      const dur = this.s.audio.track.durationS;
      if (pos >= dur) {
        this.advanceTrack(true, delta);
        pos = this.s.audio.positionS;
      } else {
        this.s.audio.positionS = pos;
      }
      delta.audio = { ...delta.audio, positionS: this.s.audio.positionS };
    }

    // vape coil physics + safety interlocks
    this.tickVape(dt, delta);

    // battery drain / charge
    this.tickPower(dt, delta);

    this.emit(delta);
  }

  private tickVape(dt: number, delta: StateDeltaMsg): void {
    const v = this.s.vape;
    const fault = this.computeFault();

    const wantFire = this.fireHeld && fault === null;

    if (wantFire) {
      v.firing = true;
      v.sessionS += dt;
      // Warm the coil toward a target set by delivered power.
      const power =
        v.mode === "watts"
          ? v.setWatts
          : (v.setVolts * v.setVolts) / Math.max(v.coilOhms, 0.3);
      const target = AMBIENT_C + power * 22; // rough W→°C mapping
      v.coilTempC += (target - v.coilTempC) * Math.min(1, dt * 1.4);

      // Hard 10 s cutoff — SPEC §5.1.
      if (v.sessionS >= VAPE_LIMITS.maxSessionS) {
        v.firing = false;
        this.fireHeld = false;
        v.fault = "cooling";
      } else if (v.coilTempC >= VAPE_LIMITS.overTempC) {
        // Over-temp cutoff — SPEC §5.3.
        v.firing = false;
        this.fireHeld = false;
        v.fault = "over-temp";
      } else {
        v.fault = null;
      }
    } else {
      if (v.firing) v.firing = false;
      // cool down toward ambient
      v.coilTempC += (AMBIENT_C - v.coilTempC) * Math.min(1, dt * 0.35);
      if (v.sessionS > 0) v.sessionS = 0;
      // Clear a transient cooling fault once the coil is near ambient again.
      if (v.fault === "cooling" && v.coilTempC < AMBIENT_C + 8) {
        v.fault = fault; // may be null or a persistent fault (locked/no-cart)
      } else {
        v.fault = fault ?? (v.fault === "cooling" ? "cooling" : null);
      }
    }

    delta.vape = {
      firing: v.firing,
      sessionS: Math.round(v.sessionS * 10) / 10,
      coilTempC: Math.round(v.coilTempC),
      fault: v.fault ?? null,
    };
  }

  /** Persistent (non-timer) safety faults; null = clear to fire. */
  private computeFault(): VapeFault | null {
    const v = this.s.vape;
    if (v.locked) return "locked";
    if (!v.cartPresent || v.coilOhms > VAPE_LIMITS.openOhms) return "no-cart";
    if (v.coilOhms < VAPE_LIMITS.shortOhms) return "short";
    if (v.coilTempC >= VAPE_LIMITS.overTempC) return "over-temp";
    return null;
  }

  private tickPower(dt: number, delta: StateDeltaMsg): void {
    const p = this.s.power;
    this.battAccumS += dt;
    // Drain faster while firing or playing; trickle otherwise. Slow enough to
    // demo, fast enough to see movement in a session.
    let drainPerMin = 0.05;
    if (this.s.audio.playing) drainPerMin += 0.15;
    if (this.s.vape.firing) drainPerMin += 3.0;

    if (this.battAccumS >= 2) {
      const step = (drainPerMin / 60) * this.battAccumS;
      this.battAccumS = 0;
      if (p.charging) {
        p.battPct = Math.min(100, p.battPct + 0.4);
      } else {
        p.battPct = Math.max(0, p.battPct - step);
      }
      p.voltage = 3.4 + (p.battPct / 100) * 0.75;
      delta.power = {
        battPct: Math.round(p.battPct),
        voltage: Math.round(p.voltage * 100) / 100,
        charging: p.charging,
      };
      // Auto-lock the coil if the pack runs critically low.
      if (p.battPct <= 3 && !this.s.vape.locked) {
        this.s.vape.locked = true;
        this.fireHeld = false;
        delta.vape = { ...delta.vape, locked: true, fault: "locked" };
      }
    }
  }

  private advanceTrack(auto: boolean, delta: StateDeltaMsg): void {
    const a = this.s.audio;
    if (a.repeat === "one" && auto) {
      a.positionS = 0;
    } else {
      const idx = LIBRARY.findIndex((t) => t.id === a.track?.id);
      let nextIdx: number;
      if (a.shuffle) {
        nextIdx = Math.floor(Math.random() * LIBRARY.length);
      } else {
        nextIdx = idx + 1;
        if (nextIdx >= LIBRARY.length) {
          if (a.repeat === "all" || !auto) nextIdx = 0;
          else {
            // reached the end with repeat off — stop.
            a.playing = false;
            a.positionS = 0;
            delta.audio = { ...delta.audio, playing: false, positionS: 0 };
            return;
          }
        }
      }
      a.track = LIBRARY[nextIdx];
      a.positionS = 0;
    }
    delta.audio = {
      ...delta.audio,
      track: a.track,
      positionS: a.positionS,
      playing: a.playing,
    };
  }

  private emit(delta: StateDeltaMsg): void {
    // Route through the exact same store path the real client uses.
    applyDelta(delta);
  }

  private pushVape(patch: Partial<DeviceState["vape"]>): void {
    applyDelta({ t: "delta", vape: patch });
  }

  private pushAudio(patch: Partial<DeviceState["audio"]>): void {
    applyDelta({ t: "delta", audio: patch });
  }

  // --- command handlers (mirror firmware validation) ---------------------

  play(): void {
    if (!this.s.audio.track) this.s.audio.track = LIBRARY[0];
    this.s.audio.playing = true;
    this.pushAudio({ playing: true, track: this.s.audio.track });
  }
  pause(): void {
    this.s.audio.playing = false;
    this.pushAudio({ playing: false });
  }
  next(): void {
    const delta: StateDeltaMsg = { t: "delta" };
    this.advanceTrack(false, delta);
    if (delta.audio) applyDelta(delta);
  }
  prev(): void {
    const a = this.s.audio;
    if (a.positionS > 3) {
      a.positionS = 0;
      this.pushAudio({ positionS: 0 });
      return;
    }
    const idx = LIBRARY.findIndex((t) => t.id === a.track?.id);
    const prevIdx = (idx - 1 + LIBRARY.length) % LIBRARY.length;
    a.track = LIBRARY[prevIdx];
    a.positionS = 0;
    this.pushAudio({ track: a.track, positionS: 0 });
  }
  stop(): void {
    this.s.audio.playing = false;
    this.s.audio.positionS = 0;
    this.pushAudio({ playing: false, positionS: 0 });
  }
  seek(positionS: number): void {
    const dur = this.s.audio.track?.durationS ?? 0;
    this.s.audio.positionS = Math.max(0, Math.min(dur, positionS));
    this.pushAudio({ positionS: this.s.audio.positionS });
  }
  setVolume(volume: number): void {
    this.s.audio.volume = clampVolume(volume);
    this.pushAudio({ volume: this.s.audio.volume });
  }
  playTrack(id: string): void {
    const track = LIBRARY.find((t) => t.id === id);
    if (!track) return;
    this.s.audio.track = track;
    this.s.audio.positionS = 0;
    this.s.audio.playing = true;
    this.pushAudio({ track, positionS: 0, playing: true });
  }
  setShuffle(on: boolean): void {
    this.s.audio.shuffle = on;
    this.pushAudio({ shuffle: on });
  }
  setRepeat(mode: RepeatMode): void {
    this.s.audio.repeat = mode;
    this.pushAudio({ repeat: mode });
  }

  vapeFire(on: boolean): void {
    // Firmware only *requests* fire; interlocks decide. Mirror that: record the
    // held intent and let the tick loop enforce faults + the 10 s cutoff.
    this.fireHeld = on;
    if (!on) {
      this.s.vape.firing = false;
      this.pushVape({ firing: false });
    }
  }
  vapeSet(payload: VapeSetPayload): void {
    const v = this.s.vape;
    v.mode = payload.mode;
    if (payload.watts !== undefined) v.setWatts = clampWatts(payload.watts);
    if (payload.volts !== undefined) v.setVolts = clampVolts(payload.volts);
    this.pushVape({
      mode: v.mode,
      setWatts: v.setWatts,
      setVolts: v.setVolts,
    });
  }
  vapeLock(locked: boolean): void {
    this.s.vape.locked = locked;
    if (locked) {
      this.fireHeld = false;
      this.s.vape.firing = false;
    }
    this.pushVape({
      locked,
      firing: this.s.vape.firing,
      fault: this.computeFault(),
    });
  }

  led(_preset: string): void {
    void _preset; // no visible model beyond the preset selection itself
  }
  eq(_preset: string): void {
    void _preset;
  }

  requestLibrary(): void {
    setLibrary(LIBRARY);
  }

  // --- emulator-only test affordances (used by the Device screen) --------

  /** Toggle a cart in/out of the 510 connector to exercise no-atomizer lockout. */
  toggleCart(): void {
    const v = this.s.vape;
    v.cartPresent = !v.cartPresent;
    v.coilOhms = v.cartPresent ? 1.2 : 99;
    this.pushVape({
      cartPresent: v.cartPresent,
      coilOhms: v.coilOhms,
      fault: this.computeFault(),
    });
  }

  /** Toggle charging so the Device/Vape screens show a moving battery. */
  toggleCharging(): void {
    this.s.power.charging = !this.s.power.charging;
    applyDelta({ t: "delta", power: { charging: this.s.power.charging } });
  }
}

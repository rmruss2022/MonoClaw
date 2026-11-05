// HighFi control protocol — SPEC.md §4.
// Single shared source of truth for both the real device client and the
// in-browser emulator. Firmware speaks the exact same JSON shapes.

// ---------------------------------------------------------------------------
// Domain constants (mirrors firmware clamps — SPEC §3.3 / §5)
// ---------------------------------------------------------------------------

export const VAPE_LIMITS = {
  watts: { min: 5, max: 15 },
  volts: { min: 2.5, max: 3.6 },
  /** Hard fire cutoff — SPEC §5.1. */
  maxSessionS: 10,
  /** Short-circuit cutoff threshold (SPEC §5.2). */
  shortOhms: 0.15,
  /** No-atomizer / open-coil threshold (SPEC §5.2). */
  openOhms: 3.0,
  /** Over-temp cutoff (SPEC §5.3). */
  overTempC: 240,
} as const;

export const VOLUME_LIMITS = { min: 0, max: 100 } as const;

// ---------------------------------------------------------------------------
// State snapshot (device → app)
// ---------------------------------------------------------------------------

export type RepeatMode = "off" | "one" | "all";
export type VapeMode = "voltage" | "watts";
export type WifiStatus = "connected" | "connecting" | "ap" | "offline";

export interface Track {
  id: string;
  title: string;
  artist: string;
  durationS: number;
}

export interface AudioState {
  playing: boolean;
  track: Track | null;
  positionS: number;
  volume: number;
  repeat: RepeatMode;
  shuffle: boolean;
}

export interface VapeState {
  locked: boolean;
  firing: boolean;
  mode: VapeMode;
  setVolts: number;
  setWatts: number;
  coilOhms: number;
  coilTempC: number;
  sessionS: number;
  cartPresent: boolean;
  /** Present when a safety interlock is blocking fire. */
  fault?: VapeFault | null;
}

export type VapeFault =
  | "locked"
  | "no-cart"
  | "short"
  | "over-temp"
  | "cooling";

export interface PowerState {
  battPct: number;
  charging: boolean;
  voltage: number;
}

export interface DeviceInfo {
  name: string;
  fw: string;
  wifi: WifiStatus;
  ip: string;
}

export interface DeviceState {
  audio: AudioState;
  vape: VapeState;
  power: PowerState;
  device: DeviceInfo;
}

// ---------------------------------------------------------------------------
// Wire messages (device → app)
// ---------------------------------------------------------------------------

/** Full snapshot sent on connect. */
export interface StateSnapshotMsg extends DeviceState {
  t: "state";
}

/** Partial delta — any subset of the state subtrees. */
export interface StateDeltaMsg {
  t: "delta";
  audio?: Partial<AudioState>;
  vape?: Partial<VapeState>;
  power?: Partial<PowerState>;
  device?: Partial<DeviceInfo>;
}

/** Device-emitted library listing (response to a library request / HTTP mirror). */
export interface LibraryMsg {
  t: "library";
  tracks: Track[];
}

export type DeviceToApp = StateSnapshotMsg | StateDeltaMsg | LibraryMsg;

// ---------------------------------------------------------------------------
// Commands (app → device). Firmware clamps/validates everything.
// ---------------------------------------------------------------------------

export type AudioCommand = "play" | "pause" | "next" | "prev" | "stop";

export interface LedPreset {
  preset: string;
}

export interface EqPreset {
  preset: string;
}

export interface VapeSetPayload {
  mode: VapeMode;
  watts?: number;
  volts?: number;
}

/**
 * A command message. Exactly one intent field is set per message, matching the
 * SPEC §4 examples ({ t:"cmd", audio:"play" }, { t:"cmd", seekS:90 }, ...).
 */
export interface CommandMsg {
  t: "cmd";
  audio?: AudioCommand;
  seekS?: number;
  volume?: number;
  playTrack?: string;
  shuffle?: boolean;
  repeat?: RepeatMode;
  vape?: "fire";
  on?: boolean;
  vapeSet?: VapeSetPayload;
  vapeLock?: boolean;
  led?: LedPreset;
  eq?: EqPreset;
  /** Client asks the device to (re)send its library listing. */
  library?: true;
}

export type AppToDevice = CommandMsg;

// ---------------------------------------------------------------------------
// Helpers shared by client + emulator
// ---------------------------------------------------------------------------

export function clamp(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, n));
}

export function clampWatts(w: number): number {
  return clamp(w, VAPE_LIMITS.watts.min, VAPE_LIMITS.watts.max);
}

export function clampVolts(v: number): number {
  return clamp(v, VAPE_LIMITS.volts.min, VAPE_LIMITS.volts.max);
}

export function clampVolume(v: number): number {
  return Math.round(clamp(v, VOLUME_LIMITS.min, VOLUME_LIMITS.max));
}

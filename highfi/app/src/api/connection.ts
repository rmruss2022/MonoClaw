// The seam every screen talks to. The real WebSocket client and the in-browser
// emulator both implement DeviceConnection, so the UI never knows (or cares)
// which one is live. Swapping transports is just: old.disconnect(); new.connect().

import type {
  AudioCommand,
  RepeatMode,
  VapeSetPayload,
} from "../protocol.ts";

export interface DeviceConnection {
  /** Open the transport, push a snapshot into the store, begin streaming. */
  connect(): void;
  /** Tear down. Idempotent. */
  disconnect(): void;

  // --- audio ---
  play(): void;
  pause(): void;
  next(): void;
  prev(): void;
  stop(): void;
  seek(positionS: number): void;
  setVolume(volume: number): void;
  playTrack(id: string): void;
  setShuffle(on: boolean): void;
  setRepeat(mode: RepeatMode): void;

  // --- vape ---
  vapeFire(on: boolean): void;
  vapeSet(payload: VapeSetPayload): void;
  vapeLock(locked: boolean): void;

  // --- vibe ---
  led(preset: string): void;
  eq(preset: string): void;

  // --- misc ---
  requestLibrary(): void;
}

export type { AudioCommand };

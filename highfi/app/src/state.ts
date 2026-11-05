// Single app store. The UI is a pure render of this state; device deltas and
// connection-status changes are the only things that mutate it.

import type {
  DeviceState,
  StateDeltaMsg,
  Track,
} from "./protocol.ts";

export type ConnectionStatus =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "offline";

export type TransportKind = "emulator" | "device";

export interface AppState {
  /** Null until the first snapshot arrives. */
  device: DeviceState | null;
  library: Track[];
  status: ConnectionStatus;
  transport: TransportKind;
  /** Host used for the real WebSocket client (device mode). */
  host: string;
  /** Last error string, if any (surfaced on the Device screen). */
  lastError: string | null;
}

type Listener = (s: AppState) => void;

const state: AppState = {
  device: null,
  library: [],
  status: "connecting",
  transport: "emulator",
  host: "",
  lastError: null,
};

const listeners = new Set<Listener>();

export function getState(): AppState {
  return state;
}

export function subscribe(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function notify(): void {
  for (const fn of listeners) fn(state);
}

// --- mutations ------------------------------------------------------------

export function setSnapshot(snapshot: DeviceState): void {
  state.device = snapshot;
  notify();
}

/** Deep-ish merge of a delta into the current device state. */
export function applyDelta(delta: StateDeltaMsg): void {
  if (!state.device) return; // deltas are meaningless before a snapshot
  const d = state.device;
  if (delta.audio) d.audio = { ...d.audio, ...delta.audio };
  if (delta.vape) d.vape = { ...d.vape, ...delta.vape };
  if (delta.power) d.power = { ...d.power, ...delta.power };
  if (delta.device) d.device = { ...d.device, ...delta.device };
  notify();
}

export function setLibrary(tracks: Track[]): void {
  state.library = tracks;
  notify();
}

export function setStatus(status: ConnectionStatus): void {
  if (state.status === status) return;
  state.status = status;
  notify();
}

export function setTransport(transport: TransportKind): void {
  state.transport = transport;
  notify();
}

export function setHost(host: string): void {
  state.host = host;
  notify();
}

export function setError(err: string | null): void {
  state.lastError = err;
  notify();
}

/** Clear device state when a transport disconnects/swaps. */
export function clearDevice(): void {
  state.device = null;
  state.library = [];
  notify();
}

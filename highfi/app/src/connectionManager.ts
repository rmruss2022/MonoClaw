// Owns the single active transport and swaps between the emulator and a real
// device behind the DeviceConnection seam. Screens ask this module for the live
// connection; they never construct one themselves.

import type { DeviceConnection } from "./api/connection.ts";
import { DeviceClient } from "./api/deviceClient.ts";
import { Emulator } from "./api/emulator.ts";
import {
  clearDevice,
  setError,
  setHost,
  setTransport,
  type TransportKind,
} from "./state.ts";

const HOST_KEY = "highfi.host";
const TRANSPORT_KEY = "highfi.transport";

const DEFAULT_HOST = (import.meta as { env?: Record<string, string> }).env
  ?.VITE_DEVICE_HOST ?? "highfi.local";

let active: DeviceConnection | null = null;

export function getConnection(): DeviceConnection {
  if (!active) throw new Error("No active connection — call boot() first.");
  return active;
}

/** The live emulator instance, if the emulator transport is active. */
export function getEmulator(): Emulator | null {
  return active instanceof Emulator ? active : null;
}

export function getSavedHost(): string {
  return localStorage.getItem(HOST_KEY) ?? DEFAULT_HOST;
}

function savedTransport(): TransportKind {
  const raw = localStorage.getItem(TRANSPORT_KEY);
  // Default to the emulator so the app is instantly usable with no hardware.
  return raw === "device" ? "device" : "emulator";
}

function stop(): void {
  if (active) {
    active.disconnect();
    active = null;
  }
  clearDevice();
}

export function useEmulator(): void {
  stop();
  localStorage.setItem(TRANSPORT_KEY, "emulator");
  setTransport("emulator");
  setError(null);
  active = new Emulator();
  active.connect();
}

export function useDevice(host: string): void {
  const cleaned = host.trim() || DEFAULT_HOST;
  stop();
  localStorage.setItem(TRANSPORT_KEY, "device");
  localStorage.setItem(HOST_KEY, cleaned);
  setTransport("device");
  setHost(cleaned);
  setError(null);
  active = new DeviceClient(cleaned);
  active.connect();
}

/** Boot the transport chosen last time (emulator by default). */
export function boot(): void {
  setHost(getSavedHost());
  if (savedTransport() === "device") {
    useDevice(getSavedHost());
  } else {
    useEmulator();
  }
}

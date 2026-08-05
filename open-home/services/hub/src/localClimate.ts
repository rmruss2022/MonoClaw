/**
 * Local climate integration — discover, onboard, control and maintain real
 * thermostats on the hub's network. Same capability-aware pattern as lights:
 *
 *   - ESPHome  → mDNS discovery (reuses the lights scan) + control over the
 *                device's web_server REST climate API (mode + target temp).
 *                Our own-firmware path: an ESP32/Sonoff running ESPHome's
 *                on-device `climate` controller. Zero cloud.
 *   - Matter   → thermostat cluster via a local chip-tool controller when one
 *                is present (system-mode + occupied setpoints).
 *
 * UI + API work in °F (US); the ESPHome boundary converts to/from °C.
 * Onboarded thermostats persist to <data>/local-climate.json; a maintenance
 * loop tracks reachability (connected / reconnecting / offline).
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { execFile } from "node:child_process";
import net from "node:net";
import http from "node:http";
import * as localLights from "./localLights.ts";

const DATA_DIR = new URL("../.data/", import.meta.url);
const STORE = new URL("../.data/local-climate.json", import.meta.url);

export type ClimateBackend = "esphome" | "matter";
export type ConnStatus = "connected" | "reconnecting" | "offline";
export type Mode = "off" | "heat" | "cool" | "auto" | "fan";
export type Action = "heating" | "cooling" | "fan" | "idle";

export interface Thermostat {
  id: string; name: string; room: string; backend: ClimateBackend;
  address?: string; port?: number; entity?: string; node?: string; endpoint?: number;
  mode: Mode; action: Action;
  currentF: number; targetF: number; humidity?: number;
  minF: number; maxF: number;
  status: ConnStatus; lastSeen: number; attempts: number;
}

function load(): Thermostat[] { try { return JSON.parse(readFileSync(STORE, "utf8")); } catch { return []; } }
function save(list: Thermostat[]) { try { mkdirSync(DATA_DIR, { recursive: true }); writeFileSync(STORE, JSON.stringify(list)); } catch (e) { console.log("[climate] save:", (e as Error).message); } }
let stats: Thermostat[] = load();
export function list(): Thermostat[] { return stats.map((s) => ({ ...s })); }

const f2c = (f: number) => Math.round(((f - 32) * 5 / 9) * 10) / 10;

function sh(cmd: string, args: string[], timeoutMs = 8000): Promise<{ ok: boolean; out: string }> {
  return new Promise((resolve) => execFile(cmd, args, { timeout: timeoutMs }, (err, stdout) => resolve({ ok: !err, out: String(stdout || "") })));
}

/** Discovery reuses the ESPHome mDNS scan; Matter uses the lights node scan. */
export async function scan(backend: ClimateBackend) {
  return backend === "matter" ? await localLights.scanMatter() : await localLights.scanEsphome();
}
export async function capabilities() { const c = await localLights.capabilities(); return { esphome: true, matter: c.matter }; }

export function onboard(dev: { name: string; backend: ClimateBackend; address?: string; port?: number; entity?: string; node?: string; endpoint?: number }, room: string): Thermostat {
  const seed = dev.node || (dev.address || "") + dev.name;
  const id = "th_" + dev.backend + "_" + Buffer.from(seed).toString("hex").slice(0, 12);
  let t = stats.find((x) => x.id === id);
  if (!t) {
    t = {
      id, name: dev.name, room: room || "Hallway", backend: dev.backend,
      address: dev.address, port: dev.port || (dev.backend === "esphome" ? 80 : undefined),
      entity: dev.entity, node: dev.node, endpoint: dev.endpoint ?? 1,
      mode: "auto", action: "idle", currentF: 70, targetF: 70, humidity: undefined,
      minF: 50, maxF: 90, status: "reconnecting", lastSeen: 0, attempts: 0,
    };
    stats.push(t);
  } else t.room = room || t.room;
  save(stats); checkOne(t).catch(() => {});
  return { ...t };
}
export function remove(id: string): boolean { const n = stats.length; stats = stats.filter((s) => s.id !== id); if (stats.length !== n) { save(stats); return true; } return false; }
export function setRoom(id: string, room: string) { const t = stats.find((x) => x.id === id); if (t) { t.room = room || "—"; save(stats); } }
export function rename(id: string, name: string) { const t = stats.find((x) => x.id === id); if (t && name) { t.name = String(name).slice(0, 60); save(stats); } }

function httpPost(host: string, port: number, path: string, timeoutMs = 3000): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.request({ host, port, path, method: "POST", timeout: timeoutMs }, (res) => { res.resume(); resolve((res.statusCode || 500) < 400); });
    req.on("timeout", () => { req.destroy(); resolve(false); });
    req.on("error", () => resolve(false));
    req.end();
  });
}
async function applyEsphome(t: Thermostat, patch: { mode?: Mode; targetF?: number }): Promise<boolean> {
  if (!t.address) return false;
  const entity = t.entity || t.name.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
  const q: string[] = [];
  if (patch.mode) q.push("mode=" + (patch.mode === "fan" ? "fan_only" : patch.mode));
  if (patch.targetF != null) q.push("target_temperature=" + f2c(patch.targetF));
  return await httpPost(t.address, t.port || 80, `/climate/${entity}/set?` + q.join("&"));
}
async function applyMatter(t: Thermostat, patch: { mode?: Mode; targetF?: number }): Promise<boolean> {
  const caps = await localLights.capabilities();
  if (!caps.matter || !t.node) return false;
  const ep = String(t.endpoint ?? 1);
  if (patch.mode) { const m = { off: "0", auto: "1", cool: "3", heat: "4", fan: "7" }[patch.mode] ?? "1"; await sh("chip-tool", ["thermostat", "write", "system-mode", m, t.node, ep]); }
  if (patch.targetF != null) await sh("chip-tool", ["thermostat", "write", "occupied-heating-setpoint", String(Math.round(f2c(patch.targetF) * 100)), t.node, ep]);
  return true;
}

export async function control(id: string, patch: { mode?: Mode; targetF?: number }): Promise<{ ok: boolean; reason?: string; thermostat?: Thermostat }> {
  const t = stats.find((x) => x.id === id);
  if (!t) return { ok: false, reason: "not found" };
  const ok = t.backend === "esphome" ? await applyEsphome(t, patch) : await applyMatter(t, patch);
  if (ok) {
    if (patch.mode) t.mode = patch.mode;
    if (patch.targetF != null) t.targetF = Math.max(t.minF, Math.min(t.maxF, Math.round(patch.targetF)));
    // reflect a plausible action until the device reports back (respect mode)
    t.action = t.mode === "off" ? "idle" : t.mode === "fan" ? "fan"
      : t.mode === "heat" ? (t.targetF > t.currentF ? "heating" : "idle")
      : t.mode === "cool" ? (t.targetF < t.currentF ? "cooling" : "idle")
      : (t.targetF > t.currentF ? "heating" : t.targetF < t.currentF ? "cooling" : "idle");
    t.lastSeen = Date.now(); save(stats);
    return { ok: true, thermostat: { ...t } };
  }
  return { ok: false, reason: t.backend === "matter" ? "Matter thermostat needs a chip-tool controller on the hub (see Setup)." : "Thermostat didn't respond on the LAN (is the hub on the same network?)." };
}

function tcpReachable(host: string, port: number, timeoutMs = 2500): Promise<boolean> {
  return new Promise((resolve) => {
    const sock = new net.Socket(); let settled = false;
    const finish = (v: boolean) => { if (!settled) { settled = true; try { sock.destroy(); } catch {} resolve(v); } };
    sock.setTimeout(timeoutMs);
    sock.once("connect", () => finish(true)); sock.once("timeout", () => finish(false)); sock.once("error", () => finish(false));
    try { sock.connect(port, host); } catch { finish(false); }
  });
}
async function checkOne(t: Thermostat): Promise<void> {
  if (t.backend === "esphome" && t.address) {
    const up = await tcpReachable(t.address, t.port || 80);
    if (up) { t.status = "connected"; t.lastSeen = Date.now(); t.attempts = 0; }
    else { t.attempts++; t.status = t.attempts > 3 ? "offline" : "reconnecting"; }
  } else if (t.backend === "matter") {
    const caps = await localLights.capabilities();
    t.status = caps.matter ? "connected" : "offline"; if (caps.matter) { t.lastSeen = Date.now(); t.attempts = 0; }
  } else t.status = "offline";
}
export async function reconnect(id: string): Promise<Thermostat | null> { const t = stats.find((x) => x.id === id); if (!t) return null; t.attempts = 0; await checkOne(t); save(stats); return { ...t }; }
let maintaining = false;
export async function maintain(): Promise<void> {
  if (maintaining || !stats.length) return; maintaining = true;
  try { for (const t of stats) await checkOne(t); save(stats); } finally { maintaining = false; }
}

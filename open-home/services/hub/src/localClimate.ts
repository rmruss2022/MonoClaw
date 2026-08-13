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
import { createHash } from "node:crypto";
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
const c2f = (c: number) => Math.round((c * 9 / 5 + 32) * 10) / 10;

// App mode → ESPHome climate mode string (web_server /set?mode=…). ESPHome uses
// `heat_cool` (two-setpoint) for the both-heat-and-cool mode — NOT `auto` — and
// `fan_only` for fan. Sending `auto` is rejected by devices that only expose heat_cool.
const TO_ESPHOME_MODE: Record<Mode, string> = { off: "off", heat: "heat", cool: "cool", auto: "heat_cool", fan: "fan_only" };
// ESPHome climate mode string → app mode (read-back). Accept both heat_cool and the
// legacy `auto` as our "auto"; `dry` has no app equivalent so we surface it as cool.
const FROM_ESPHOME_MODE: Record<string, Mode> = { off: "off", heat: "heat", cool: "cool", heat_cool: "auto", auto: "auto", fan_only: "fan", dry: "cool" };
// heat_cool needs a low/high band; our model is single-setpoint, so bracket the
// target with a symmetric deadband (°F).
const DEADBAND_F = 2;

function entityOf(t: Thermostat): string {
  return t.entity || t.name.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
}
function clampF(t: Thermostat, f: number): number {
  return Math.max(t.minF, Math.min(t.maxF, Math.round(f)));
}
function deriveAction(t: Thermostat): Action {
  if (t.mode === "off") return "idle";
  if (t.mode === "fan") return "fan";
  if (t.mode === "heat") return t.targetF > t.currentF ? "heating" : "idle";
  if (t.mode === "cool") return t.targetF < t.currentF ? "cooling" : "idle";
  return t.targetF > t.currentF ? "heating" : t.targetF < t.currentF ? "cooling" : "idle";
}

function sh(cmd: string, args: string[], timeoutMs = 8000): Promise<{ ok: boolean; out: string }> {
  return new Promise((resolve) => execFile(cmd, args, { timeout: timeoutMs }, (err, stdout) => resolve({ ok: !err, out: String(stdout || "") })));
}

/** Discovery reuses the ESPHome mDNS scan; Matter uses the lights node scan. */
export async function scan(backend: ClimateBackend) {
  return backend === "matter" ? await localLights.scanMatter() : await localLights.scanEsphome();
}
export async function capabilities() { const c = await localLights.capabilities(); return { esphome: true, matter: c.matter }; }

export function onboard(dev: { name: string; backend: ClimateBackend; address?: string; port?: number; entity?: string; node?: string; endpoint?: number }, room: string): Thermostat {
  // Identity must include address+port+entity (+node/name) — hashing just the first
  // bytes of the address collided every device sharing an IP prefix (e.g. two units
  // at 192.168.1.x), silently overwriting one with the other.
  const seed = dev.node || `${dev.address || ""}:${dev.port ?? ""}/${dev.entity || dev.name}`;
  const id = "th_" + dev.backend + "_" + createHash("sha1").update(seed).digest("hex").slice(0, 12);
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
function httpGetJson(host: string, port: number, path: string, timeoutMs = 3000): Promise<any | null> {
  return new Promise((resolve) => {
    const req = http.request({ host, port, path, method: "GET", timeout: timeoutMs }, (res) => {
      if ((res.statusCode || 500) >= 400) { res.resume(); return resolve(null); }
      let body = ""; res.setEncoding("utf8");
      res.on("data", (c) => { body += c; if (body.length > 100_000) req.destroy(); });
      res.on("end", () => { try { resolve(JSON.parse(body)); } catch { resolve(null); } });
    });
    req.on("timeout", () => { req.destroy(); resolve(null); });
    req.on("error", () => resolve(null));
    req.end();
  });
}

async function applyEsphome(t: Thermostat, patch: { mode?: Mode; targetF?: number }): Promise<boolean> {
  if (!t.address) return false;
  const entity = entityOf(t);
  // Effective mode decides which setpoint fields the device expects: heat_cool
  // wants target_temperature_low/high, single modes want target_temperature.
  const effMode: Mode = patch.mode ?? t.mode;
  const q: string[] = [];
  if (patch.mode) q.push("mode=" + TO_ESPHOME_MODE[patch.mode]);
  if (patch.targetF != null) {
    if (effMode === "auto") {
      q.push("target_temperature_low=" + f2c(patch.targetF - DEADBAND_F));
      q.push("target_temperature_high=" + f2c(patch.targetF + DEADBAND_F));
    } else {
      q.push("target_temperature=" + f2c(patch.targetF));
    }
  }
  if (!q.length) return true;
  return await httpPost(t.address, t.port || 80, `/climate/${entity}/set?` + q.join("&"));
}

/**
 * Read the device's real state back over the web_server REST API and reconcile it
 * onto our model — so the dial shows the room's actual temperature and mode, not
 * our optimistic guess. Returns false if the device didn't answer (used as the
 * reachability signal for ESPHome, since it's a real API round-trip).
 */
async function readEsphome(t: Thermostat): Promise<boolean> {
  if (!t.address) return false;
  const j = await httpGetJson(t.address, t.port || 80, `/climate/${entityOf(t)}`);
  if (!j || typeof j !== "object") return false;
  if (typeof j.current_temperature === "number") t.currentF = Math.round(c2f(j.current_temperature));
  if (typeof j.target_temperature === "number") t.targetF = clampF(t, c2f(j.target_temperature));
  else if (typeof j.target_temperature_low === "number" && typeof j.target_temperature_high === "number")
    t.targetF = clampF(t, c2f((j.target_temperature_low + j.target_temperature_high) / 2));
  if (typeof j.mode === "string") { const m = FROM_ESPHOME_MODE[j.mode.toLowerCase()]; if (m) t.mode = m; }
  t.action = deriveAction(t);
  return true;
}
async function applyMatter(t: Thermostat, patch: { mode?: Mode; targetF?: number }): Promise<boolean> {
  const caps = await localLights.capabilities();
  if (!caps.matter || !t.node) return false;
  const ep = String(t.endpoint ?? 1);
  if (patch.mode) { const m = { off: "0", auto: "1", cool: "3", heat: "4", fan: "7" }[patch.mode] ?? "1"; await sh("chip-tool", ["thermostat", "write", "system-mode", m, t.node, ep]); }
  if (patch.targetF != null) await sh("chip-tool", ["thermostat", "write", "occupied-heating-setpoint", String(Math.round(f2c(patch.targetF) * 100)), t.node, ep]);
  return true;
}

const VALID_MODES: Mode[] = ["off", "heat", "cool", "auto", "fan"];
export async function control(id: string, patch: { mode?: Mode; targetF?: number }): Promise<{ ok: boolean; reason?: string; thermostat?: Thermostat }> {
  const t = stats.find((x) => x.id === id);
  if (!t) return { ok: false, reason: "not found" };
  if (patch.mode !== undefined && !VALID_MODES.includes(patch.mode)) return { ok: false, reason: "invalid mode" };
  if (patch.targetF !== undefined && !Number.isFinite(patch.targetF)) return { ok: false, reason: "invalid temperature" };
  // Clamp to the device's range *before* sending it on the wire — never push an
  // out-of-range setpoint to real hardware.
  const eff: { mode?: Mode; targetF?: number } = { mode: patch.mode };
  if (patch.targetF != null) eff.targetF = clampF(t, patch.targetF);
  const ok = t.backend === "esphome" ? await applyEsphome(t, eff) : await applyMatter(t, eff);
  if (ok) {
    if (eff.mode) t.mode = eff.mode;
    if (eff.targetF != null) t.targetF = eff.targetF;
    t.action = deriveAction(t); // optimistic until the device reports back
    // Reconcile against the device's real state so the model matches hardware
    // (e.g. heat_cool band midpoint, clamped setpoints, actual room temp).
    if (t.backend === "esphome") await readEsphome(t).catch(() => false);
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
    // A real climate GET is both the reachability probe and the state read-back;
    // fall back to a TCP check if the device is up but the entity path 404s.
    const read = await readEsphome(t).catch(() => false);
    const up = read || await tcpReachable(t.address, t.port || 80);
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

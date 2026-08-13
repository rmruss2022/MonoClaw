/**
 * Climate domain — the single view the /climate UI talks to. Merges the mock
 * thermostat(s) in home.ts with real onboarded thermostats (ESPHome / Matter)
 * and routes control to the right place. Works in °F. Mirrors lights.ts.
 */
import * as home from "./home.ts";
import * as localClimate from "./localClimate.ts";

export interface ThermostatView {
  id: string; name: string; room: string;
  mode: localClimate.Mode; action: localClimate.Action;
  currentF: number; targetF: number; humidity?: number; minF: number; maxF: number;
  real: boolean; backend?: localClimate.ClimateBackend; status?: localClimate.ConnStatus; online: boolean;
}

function deriveAction(mode: string, cur: number, tgt: number): localClimate.Action {
  if (mode === "off") return "idle"; if (mode === "fan") return "fan";
  if (mode === "heat") return tgt > cur + 0.4 ? "heating" : "idle";
  if (mode === "cool") return tgt < cur - 0.4 ? "cooling" : "idle";
  if (tgt > cur + 0.4) return "heating"; if (tgt < cur - 0.4) return "cooling"; return "idle";
}
function fromReal(t: localClimate.Thermostat): ThermostatView {
  return { id: t.id, name: t.name, room: t.room, mode: t.mode, action: t.action, currentF: t.currentF, targetF: t.targetF, humidity: t.humidity, minF: t.minF, maxF: t.maxF, real: true, backend: t.backend, status: t.status, online: t.status === "connected" };
}
function fromMock(d: home.Device): ThermostatView {
  const mode = (d.state.mode || "auto") as localClimate.Mode;
  const cur = Number(d.state.temp ?? 70), tgt = Number(d.state.target ?? 70);
  return { id: d.id, name: d.name, room: d.room, mode, action: deriveAction(mode, cur, tgt), currentF: cur, targetF: tgt, humidity: d.state.humidity, minF: 50, maxF: 90, real: false, online: true };
}

export function listThermostats(): ThermostatView[] {
  const real = localClimate.list().map(fromReal);
  const ids = new Set(real.map((r) => r.id));
  const mock = home.allDevices().filter((d) => d.type === "thermostat" && !ids.has(d.id)).map(fromMock);
  return [...real, ...mock];
}
export async function capabilities() { return await localClimate.capabilities(); }

export function state() {
  const all = listThermostats();
  const order: string[] = [], groups: Record<string, ThermostatView[]> = {};
  for (const t of all) { const r = t.room || "—"; if (!groups[r]) { groups[r] = []; order.push(r); } groups[r].push(t); }
  return { thermostats: all, rooms: order.map((room) => ({ room, thermostats: groups[room] })), counts: { total: all.length, real: all.filter((t) => t.real).length, active: all.filter((t) => t.action !== "idle").length } };
}

export const MODES: localClimate.Mode[] = ["off", "heat", "cool", "auto", "fan"];
export function normalizeMode(m: any): localClimate.Mode {
  const s = String(m || "").toLowerCase();
  if (s === "fan_only" || s === "fan") return "fan";
  return (MODES.includes(s as localClimate.Mode) ? s : "auto") as localClimate.Mode;
}

/** Validate + sanitize a control patch. Returns null with a reason on bad input. */
function clean(patch: { mode?: any; targetF?: any }): { ok: true; patch: { mode?: localClimate.Mode; targetF?: number } } | { ok: false; reason: string } {
  const out: { mode?: localClimate.Mode; targetF?: number } = {};
  if (patch.mode !== undefined) {
    const s = String(patch.mode).toLowerCase();
    const m = s === "fan_only" ? "fan" : s;
    if (!MODES.includes(m as localClimate.Mode)) return { ok: false, reason: `Invalid mode "${patch.mode}"` };
    out.mode = m as localClimate.Mode;
  }
  if (patch.targetF !== undefined) {
    const n = Number(patch.targetF);
    if (!Number.isFinite(n)) return { ok: false, reason: "Invalid temperature" };
    out.targetF = n;
  }
  return { ok: true, patch: out };
}

export async function control(id: string, patch: { mode?: any; targetF?: any }): Promise<{ ok: boolean; reason?: string }> {
  const c = clean(patch);
  if (!c.ok) return { ok: false, reason: c.reason };
  const real = localClimate.list().find((t) => t.id === id);
  if (real) { const r = await localClimate.control(id, c.patch); return { ok: r.ok, reason: r.reason }; }
  const dev = home.getDevice(id);
  if (!dev || dev.type !== "thermostat") return { ok: false, reason: "not found" };
  const p: Record<string, any> = {};
  if (c.patch.mode) p.mode = c.patch.mode;
  if (c.patch.targetF != null) p.target = Math.max(50, Math.min(90, Math.round(c.patch.targetF)));
  home.setDevice(id, p);
  return { ok: true };
}

/** The primary real thermostat the agent/scenes act on (first onboarded), or null. */
export function primary(): localClimate.Thermostat | null { return localClimate.list()[0] || null; }

/** Real thermostats normalized to the mock device shape for the /devices view. */
export function deviceRows() {
  return localClimate.list().map((t) => ({
    id: t.id, name: t.name, type: "thermostat", room: t.room, icon: "🌡️",
    state: { temp: Math.round(t.currentF), target: Math.round(t.targetF), mode: t.mode, real: true },
  }));
}

/**
 * Mirror the mock thermostat onto the real primary (voice/scenes → hardware).
 * Change-tracked: it only pushes when the mock's target/mode actually changes, and
 * adopts the current state on first observe / when the primary changes — so a direct
 * dial change on the real device is never clobbered by an unrelated reconcile.
 */
let lastSyncKey = "";
export async function syncMockToPrimary(): Promise<void> {
  const p = primary();
  if (!p) { lastSyncKey = ""; return; }
  const dev = home.getDevice("thermostat_main"); if (!dev) return;
  const targetF = Number(dev.state.target);
  const mode = normalizeMode(dev.state.mode);
  const key = `${p.id}|${mode}|${Number.isFinite(targetF) ? Math.round(targetF) : "?"}`;
  if (lastSyncKey === "" || !lastSyncKey.startsWith(p.id + "|")) { lastSyncKey = key; return; } // adopt, don't push
  if (key === lastSyncKey) return;
  lastSyncKey = key;
  await localClimate.control(p.id, { mode, targetF: Number.isFinite(targetF) ? targetF : undefined });
}
export function setRoom(id: string, room: string) {
  const real = localClimate.list().find((t) => t.id === id);
  if (real) localClimate.setRoom(id, room); else { const d = home.getDevice(id); if (d) d.room = room || "—"; }
}
export function rename(id: string, name: string) {
  const real = localClimate.list().find((t) => t.id === id);
  if (real) localClimate.rename(id, name); else { const d = home.getDevice(id); if (d && name) d.name = String(name).slice(0, 60); }
}

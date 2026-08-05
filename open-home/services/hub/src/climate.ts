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

export async function control(id: string, patch: { mode?: localClimate.Mode; targetF?: number }): Promise<{ ok: boolean; reason?: string }> {
  const real = localClimate.list().find((t) => t.id === id);
  if (real) { const r = await localClimate.control(id, patch); return { ok: r.ok, reason: r.reason }; }
  const dev = home.getDevice(id);
  if (!dev || dev.type !== "thermostat") return { ok: false, reason: "not found" };
  const p: Record<string, any> = {};
  if (patch.mode) p.mode = patch.mode;
  if (patch.targetF != null) p.target = Math.max(50, Math.min(90, Math.round(patch.targetF)));
  home.setDevice(id, p);
  return { ok: true };
}
export function setRoom(id: string, room: string) {
  const real = localClimate.list().find((t) => t.id === id);
  if (real) localClimate.setRoom(id, room); else { const d = home.getDevice(id); if (d) d.room = room || "—"; }
}
export function rename(id: string, name: string) {
  const real = localClimate.list().find((t) => t.id === id);
  if (real) localClimate.rename(id, name); else { const d = home.getDevice(id); if (d && name) d.name = String(name).slice(0, 60); }
}

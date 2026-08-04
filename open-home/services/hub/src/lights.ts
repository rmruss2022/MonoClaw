/**
 * Lighting domain — the single view the /lights UI talks to.
 *
 * Merges two sources into one room-grouped model (mirrors audio.ts for speakers):
 *   - real onboarded lights from localLights.ts (ESPHome / Matter), and
 *   - the mock demo lights in home.ts, so the room stays populated before any
 *     real hardware is added.
 *
 * Control routes to the real backend when the light is real, else to the mock
 * home model. Scenes fan a patch across a room (or the whole home).
 */
import * as home from "./home.ts";
import * as localLights from "./localLights.ts";

export interface LightView {
  id: string; name: string; room: string; on: boolean; brightness: number;
  rgb?: localLights.RGB; colorTempK?: number;
  real: boolean; backend?: localLights.LightBackend;
  dimmable: boolean; color: boolean; tunable: boolean;
  status?: localLights.ConnStatus; online: boolean;
}

function fromReal(l: localLights.LocalLight): LightView {
  return {
    id: l.id, name: l.name, room: l.room, on: l.on, brightness: l.brightness,
    rgb: l.rgb, colorTempK: l.colorTempK, real: true, backend: l.backend,
    dimmable: l.dimmable, color: l.color, tunable: l.tunable,
    status: l.status, online: l.status === "connected",
  };
}
function fromMock(d: home.Device): LightView {
  return {
    id: d.id, name: d.name, room: d.room, on: !!d.state.on,
    brightness: typeof d.state.brightness === "number" ? d.state.brightness : 100,
    rgb: d.state.rgb, colorTempK: d.state.colorTempK,
    real: false, dimmable: true, color: !!d.state.rgb || d.id.includes("living") || d.id.includes("bedroom"),
    tunable: true, online: true,
  };
}

export function listLights(): LightView[] {
  const real = localLights.list().map(fromReal);
  const realIds = new Set(real.map((r) => r.id));
  const mock = home.allDevices().filter((d) => d.type === "light" && !realIds.has(d.id)).map(fromMock);
  return [...real, ...mock];
}

export async function capabilities() { return await localLights.capabilities(); }

export function state() {
  const all = listLights();
  const order: string[] = [], groups: Record<string, LightView[]> = {};
  for (const l of all) { const r = l.room || "—"; if (!groups[r]) { groups[r] = []; order.push(r); } groups[r].push(l); }
  return {
    lights: all,
    rooms: order.map((room) => ({ room, lights: groups[room] })),
    scenes: home.getScenes(),
    counts: { total: all.length, on: all.filter((l) => l.on).length, real: all.filter((l) => l.real).length },
  };
}

/** Route a control patch to the real backend or the mock model. */
export async function control(id: string, patch: { on?: boolean; brightness?: number; rgb?: localLights.RGB; colorTempK?: number }): Promise<{ ok: boolean; reason?: string }> {
  const real = localLights.list().find((l) => l.id === id);
  if (real) { const r = await localLights.control(id, patch); return { ok: r.ok, reason: r.reason }; }
  // mock
  const dev = home.getDevice(id);
  if (!dev || dev.type !== "light") return { ok: false, reason: "not found" };
  const p: Record<string, any> = {};
  if (patch.on != null) p.on = patch.on;
  if (patch.brightness != null) { p.brightness = Math.round(patch.brightness); if (patch.brightness > 0) p.on = true; }
  if (patch.rgb) { p.rgb = patch.rgb; p.on = true; }
  if (patch.colorTempK != null) p.colorTempK = patch.colorTempK;
  home.setDevice(id, p);
  return { ok: true };
}

/** Move a light into a room (real lights persist; mock lights update in memory). */
export function setRoom(id: string, room: string) {
  const real = localLights.list().find((l) => l.id === id);
  if (real) localLights.setRoom(id, room);
  else { const dev = home.getDevice(id); if (dev) dev.room = room || "—"; }
}

/** Turn every light in a room on/off (or the whole home when room is empty). */
export async function setRoomPower(room: string, on: boolean): Promise<number> {
  const targets = listLights().filter((l) => !room || l.room === room);
  let n = 0;
  for (const l of targets) { const r = await control(l.id, { on }); if (r.ok) n++; }
  return n;
}

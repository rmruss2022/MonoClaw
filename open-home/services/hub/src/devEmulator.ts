/**
 * In-process ESPHome climate emulator — the same faithful web_server contract as
 * test/esphome-thermostat.py, but embedded in the hub so a dev-only UI button can
 * spin up a fake thermostat with zero external processes or hardware.
 *
 * GATED: only started via the dev-flagged /climate/command `add-demo-thermostat`
 * (OPEN_HOME_DEV=1). It binds to 127.0.0.1 only.
 *
 * Contract (mirrors the standalone emulator):
 *   GET  /climate/<entity>          → JSON state (mode, current_temperature,
 *                                     target_temperature | low/high)
 *   POST /climate/<entity>/set?…    → mode ∈ {off,heat,cool,heat_cool,fan_only,dry}
 *                                     (unsupported → 400); setpoints per effective
 *                                     mode (a lone target_temperature in heat_cool
 *                                     is ignored, like a real device).
 * Temperatures on the wire are °C, exactly as ESPHome emits.
 */
import http from "node:http";
import { URL } from "node:url";

const SUPPORTED = new Set(["off", "heat", "cool", "heat_cool", "fan_only", "dry"]);

interface EntityState { mode: string; current: number; target: number; low: number; high: number; }
const entities = new Map<string, EntityState>();

let server: http.Server | null = null;
let boundPort = 0;
const HOST = "127.0.0.1";

function stateJson(entity: string, s: EntityState) {
  const out: Record<string, unknown> = { id: `climate-${entity}`, mode: s.mode, current_temperature: s.current };
  if (s.mode === "heat_cool") { out.target_temperature_low = s.low; out.target_temperature_high = s.high; }
  else out.target_temperature = s.target;
  return out;
}

function handle(req: http.IncomingMessage, res: http.ServerResponse) {
  const send = (code: number, body: unknown) => {
    const b = Buffer.from(JSON.stringify(body));
    res.writeHead(code, { "Content-Type": "application/json", "Content-Length": b.length });
    res.end(b);
  };
  const u = new URL(req.url || "/", `http://${HOST}`);
  const m = u.pathname.match(/^\/climate\/([^/]+)(\/set)?$/);
  if (!m) return send(404, { error: "not found" });
  const entity = decodeURIComponent(m[1]);
  const s = entities.get(entity);
  if (!s) return send(404, { error: "unknown entity" });

  if (req.method === "GET" && !m[2]) return send(200, stateJson(entity, s));
  if (req.method === "POST" && m[2]) {
    const q = u.searchParams;
    const numOf = (k: string) => { const v = q.get(k); return v == null || v === "" ? null : Number(v); };
    const nm = (q.get("mode") || "").toLowerCase() || null;
    if (nm) { if (!SUPPORTED.has(nm)) return send(400, { error: `unsupported mode ${nm}` }); s.mode = nm; }
    if (s.mode === "heat_cool") {
      const lo = numOf("target_temperature_low"), hi = numOf("target_temperature_high");
      if (lo != null && Number.isFinite(lo)) s.low = lo;
      if (hi != null && Number.isFinite(hi)) s.high = hi; // lone target_temperature ignored
    } else {
      const t = numOf("target_temperature");
      if (t != null && Number.isFinite(t)) s.target = t;
    }
    return send(200, stateJson(entity, s));
  }
  return send(404, { error: "not found" });
}

/** Start the emulator server (idempotent). Returns the bound {host, port}. */
export function ensure(): Promise<{ host: string; port: number }> {
  if (server && boundPort) return Promise.resolve({ host: HOST, port: boundPort });
  return new Promise((resolve, reject) => {
    const srv = http.createServer(handle);
    let port = 47010;
    const tryBind = () => {
      srv.once("error", (e: NodeJS.ErrnoException) => {
        if (e.code === "EADDRINUSE" && port < 47060) { port++; setTimeout(tryBind, 0); }
        else reject(e);
      });
      srv.listen(port, HOST, () => { server = srv; boundPort = port; resolve({ host: HOST, port }); });
    };
    tryBind();
  });
}

/** Register a fake device entity with a plausible starting state (°C). */
export function addEntity(entity: string, seedIndex = 0): void {
  if (entities.has(entity)) return;
  // vary each demo a little so the UI looks alive (deterministic, no RNG)
  const current = 20 + (seedIndex % 3);          // 20/21/22 °C  (≈68/70/72 °F)
  const target = 21 + (seedIndex % 2);           // 21/22 °C
  entities.set(entity, { mode: "heat", current, target, low: target - 2, high: target + 2 });
}

export function removeEntity(entity: string): void { entities.delete(entity); }
export function running(): boolean { return !!server && !!boundPort; }

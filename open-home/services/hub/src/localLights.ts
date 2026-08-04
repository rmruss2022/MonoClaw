/**
 * Local lighting integration — discover, onboard, control and maintain real
 * lights on the hub's own network. Two capability-aware backends, no cloud:
 *
 *   - ESPHome  → mDNS discovery (`_esphomelib._tcp`), control over the device's
 *                local web_server REST API (on/off, brightness, RGB, color-temp).
 *                This is our own-firmware path — zero cloud, fully local.
 *   - Matter   → mDNS discovery of commissionable/operational nodes
 *                (`_matterc._udp` / `_matter._tcp`). Control runs through a local
 *                Matter controller (`chip-tool`, or python-matter-server on
 *                127.0.0.1:5580) when one is present on the hub.
 *
 * Onboarded lights persist to <data>/local-lights.json and a maintenance loop
 * keeps them reachable (TCP probe for ESPHome, controller ping for Matter),
 * tracking connected / reconnecting / offline so the UI can show status and
 * offer a manual retry — exactly like the speaker service.
 *
 * NOTE: discovery only sees devices on the SAME LAN. Run the hub on the network
 * with your lights (a Pi/Mac); a cloud host correctly reports an empty scan.
 * Matter *control* additionally needs a controller installed on the hub.
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { execFile } from "node:child_process";
import dgram from "node:dgram";
import net from "node:net";
import http from "node:http";

const DATA_DIR = new URL("../.data/", import.meta.url);
const STORE = new URL("../.data/local-lights.json", import.meta.url);

export type LightBackend = "esphome" | "matter";
export type ConnStatus = "connected" | "reconnecting" | "offline";
export interface RGB { r: number; g: number; b: number }

export interface LocalLight {
  id: string; name: string; room: string; backend: LightBackend;
  address?: string; port?: number;      // esphome
  entity?: string;                      // esphome web_server entity (light/<entity>)
  node?: string; endpoint?: number;     // matter node id + endpoint
  // capabilities
  dimmable: boolean; color: boolean; tunable: boolean;
  // live-ish state (optimistic; refreshed from device when reachable)
  on: boolean; brightness: number; rgb?: RGB; colorTempK?: number;
  status: ConnStatus; lastSeen: number; attempts: number;
}

// ---- persistence ----
function load(): LocalLight[] { try { return JSON.parse(readFileSync(STORE, "utf8")); } catch { return []; } }
function save(list: LocalLight[]) { try { mkdirSync(DATA_DIR, { recursive: true }); writeFileSync(STORE, JSON.stringify(list)); } catch (e) { console.log("[lights] save:", (e as Error).message); } }
let lights: LocalLight[] = load();
export function list(): LocalLight[] { return lights.map((l) => ({ ...l })); }

// ---- capability detection ----
function sh(cmd: string, args: string[], timeoutMs = 6000): Promise<{ ok: boolean; out: string }> {
  return new Promise((resolve) => {
    execFile(cmd, args, { timeout: timeoutMs }, (err, stdout) => resolve({ ok: !err, out: String(stdout || "") }));
  });
}
let matterChecked = false, matterCtl: null | "chip-tool" | "matter-server" = null;
async function matterController(): Promise<null | "chip-tool" | "matter-server"> {
  if (matterChecked) return matterCtl;
  matterChecked = true;
  const bin = await sh("chip-tool", ["--version"], 3000);
  if (bin.ok || /chip-?tool/i.test(bin.out)) { matterCtl = "chip-tool"; return matterCtl; }
  if (await tcpReachable("127.0.0.1", 5580, 800)) { matterCtl = "matter-server"; return matterCtl; }
  matterCtl = null; return matterCtl;
}
export async function capabilities() {
  return { esphome: true, matter: (await matterController()) !== null };
}

// ---- minimal mDNS multicast query (self-contained; same proven codec as audio) ----
const MDNS_ADDR = "224.0.0.251", MDNS_PORT = 5353;
const SERVICES: Record<string, LightBackend | "matter-commissionable"> = {
  "_esphomelib._tcp.local": "esphome",
  "_matter._tcp.local": "matter",              // operational (commissioned) nodes
  "_matterc._udp.local": "matter-commissionable", // commissionable (setup-ready)
};
function encodeName(name: string): Buffer {
  const parts = name.split(".").filter(Boolean);
  const bufs = parts.map((p) => { const b = Buffer.from(p); return Buffer.concat([Buffer.from([b.length]), b]); });
  return Buffer.concat([...bufs, Buffer.from([0])]);
}
function buildQuery(names: string[]): Buffer {
  const header = Buffer.alloc(12);
  header.writeUInt16BE(names.length, 4);
  const qs = names.map((n) => Buffer.concat([encodeName(n), Buffer.from([0x00, 0x0c, 0x00, 0x01])]));
  return Buffer.concat([header, ...qs]);
}
function readName(buf: Buffer, off: number): [string, number] {
  const labels: string[] = []; let jumped = false, next = off, safety = 0;
  while (safety++ < 128) {
    if (off >= buf.length) break;
    const len = buf[off];
    if (len === 0) { off++; if (!jumped) next = off; break; }
    if ((len & 0xc0) === 0xc0) { const ptr = ((len & 0x3f) << 8) | buf[off + 1]; if (!jumped) next = off + 2; jumped = true; off = ptr; continue; }
    labels.push(buf.slice(off + 1, off + 1 + len).toString("utf8")); off += 1 + len;
  }
  return [labels.join("."), next];
}
interface Ans { name: string; type: number; rdata: Buffer; roff: number }
function parseAnswers(buf: Buffer): Ans[] {
  const answers: Ans[] = [];
  try {
    const qd = buf.readUInt16BE(4), an = buf.readUInt16BE(6), ns = buf.readUInt16BE(8), ar = buf.readUInt16BE(10);
    let off = 12;
    for (let i = 0; i < qd; i++) { const [, n] = readName(buf, off); off = n + 4; }
    for (let i = 0; i < an + ns + ar && off < buf.length; i++) {
      const [name, n] = readName(buf, off); off = n;
      const type = buf.readUInt16BE(off); off += 8;
      const rdlen = buf.readUInt16BE(off); off += 2;
      answers.push({ name, type, rdata: buf.slice(off, off + rdlen), roff: off });
      off += rdlen;
    }
  } catch {}
  return answers;
}

export interface Discovered { id: string; name: string; backend: LightBackend; address?: string; port?: number; node?: string; commissionable?: boolean }

/** Discover ESPHome lights on the LAN via mDNS. */
export function scanEsphome(timeoutMs = 4000): Promise<Discovered[]> {
  return mdnsScan(["_esphomelib._tcp.local"], timeoutMs);
}
/** Discover Matter nodes on the LAN (operational + commissionable). */
export function scanMatter(timeoutMs = 4000): Promise<Discovered[]> {
  return mdnsScan(["_matter._tcp.local", "_matterc._udp.local"], timeoutMs);
}
function mdnsScan(services: string[], timeoutMs: number): Promise<Discovered[]> {
  return new Promise((resolve) => {
    const found = new Map<string, Discovered>();
    let sock: dgram.Socket;
    try { sock = dgram.createSocket({ type: "udp4", reuseAddr: true }); } catch { resolve([]); return; }
    const done = () => { try { sock.close(); } catch {} resolve([...found.values()]); };
    sock.on("error", () => done());
    sock.on("message", (msg, rinfo) => {
      const answers = parseAnswers(msg);
      let instance = "", port: number | undefined, backend: LightBackend | null = null, commissionable = false;
      for (const a of answers) {
        for (const svc of services) {
          const tag = svc.split(".")[0];
          if (a.name.includes(tag)) {
            backend = svc.startsWith("_esphome") ? "esphome" : "matter";
            if (svc.startsWith("_matterc")) commissionable = true;
          }
        }
        if (a.type === 12) { const [target] = readName(msg, a.roff); instance = target.split("._")[0] || instance; }
        else if (a.type === 33) { try { port = a.rdata.readUInt16BE(4); } catch {} if (!instance) instance = a.name.split("._")[0]; }
      }
      if (!backend) return;
      const address = rinfo.address;
      const name = decodeURIComponent(instance || `${backend} ${address}`);
      const id = backend + "_" + Buffer.from(address + name).toString("hex").slice(0, 12);
      if (!found.has(id)) found.set(id, { id, name, backend, address, port, node: backend === "matter" ? instance : undefined, commissionable });
    });
    try {
      sock.bind(0, () => {
        try { sock.setMulticastTTL(255); } catch {}
        const q = buildQuery(services);
        sock.send(q, MDNS_PORT, MDNS_ADDR);
        setTimeout(() => { try { sock.send(q, MDNS_PORT, MDNS_ADDR); } catch {} }, 400);
      });
    } catch { done(); return; }
    setTimeout(done, timeoutMs);
  });
}

// ---- onboarding ----
export function onboard(dev: Partial<LocalLight> & { name: string; backend: LightBackend }, room: string): LocalLight {
  const seed = dev.node || (dev.address || "") + dev.name;
  const id = dev.id || dev.backend + "_" + Buffer.from(seed).toString("hex").slice(0, 12);
  let l = lights.find((x) => x.id === id);
  if (!l) {
    l = {
      id, name: dev.name, room: room || "Living Room", backend: dev.backend,
      address: dev.address, port: dev.port || (dev.backend === "esphome" ? 80 : undefined),
      entity: dev.entity, node: dev.node, endpoint: dev.endpoint ?? 1,
      dimmable: dev.dimmable ?? true, color: dev.color ?? true, tunable: dev.tunable ?? true,
      on: false, brightness: 100, rgb: dev.rgb, colorTempK: dev.colorTempK,
      status: "reconnecting", lastSeen: 0, attempts: 0,
    };
    lights.push(l);
  } else { l.room = room || l.room; }
  save(lights);
  checkOne(l).catch(() => {});
  return { ...l };
}
export function remove(id: string): boolean {
  const n = lights.length; lights = lights.filter((l) => l.id !== id);
  if (lights.length !== n) { save(lights); return true; } return false;
}
export function setRoom(id: string, room: string) { const l = lights.find((x) => x.id === id); if (l) { l.room = room || "—"; save(lights); } }
export function rename(id: string, name: string) { const l = lights.find((x) => x.id === id); if (l && name) { l.name = String(name).slice(0, 60); save(lights); } }

/** Commission a brand-new Matter light from its setup code / QR payload. */
export async function commission(payload: { code: string; name?: string; room?: string }): Promise<{ ok: boolean; reason?: string; light?: LocalLight }> {
  const ctl = await matterController();
  if (ctl !== "chip-tool") return { ok: false, reason: "Matter commissioning needs chip-tool on the hub (see Setup). Discovery works on the LAN, but pairing a new bulb needs the controller." };
  const code = String(payload.code || "").replace(/[^0-9A-Z:.-]/gi, "");
  if (!code) return { ok: false, reason: "Enter the 11-digit setup code or QR payload from the bulb." };
  // Assign a fresh node id and pair over IP (BLE-Thread variants use pairing code-thread).
  const node = String(1000 + Math.floor(process.hrtime()[1] % 9000));
  const r = await sh("chip-tool", ["pairing", "code", node, code], 60000);
  if (!r.ok || /error|fail/i.test(r.out)) return { ok: false, reason: "Pairing failed — check the code and that the bulb is in pairing mode." };
  const l = onboard({ name: payload.name || "Matter light", backend: "matter", node, endpoint: 1 }, payload.room || "Living Room");
  return { ok: true, light: l };
}

/** Flash a light so you can tell which one you're setting up. */
export async function identify(id: string): Promise<{ ok: boolean; reason?: string }> {
  const l = lights.find((x) => x.id === id);
  if (!l) return { ok: false, reason: "not found" };
  if (l.backend === "matter") {
    const ctl = await matterController();
    if (ctl !== "chip-tool" || !l.node) return { ok: false, reason: "Blink needs a Matter controller." };
    await sh("chip-tool", ["identify", "identify", "3", l.node, String(l.endpoint ?? 1)], 8000);
    return { ok: true };
  }
  if (l.backend === "esphome" && l.address) {
    // three quick on/off pulses via the web_server API
    const wasOn = l.on;
    for (let i = 0; i < 3; i++) {
      await applyEsphome(l, { on: true, brightness: 100 });
      await new Promise((r) => setTimeout(r, 350));
      await applyEsphome(l, { on: false });
      await new Promise((r) => setTimeout(r, 350));
    }
    await applyEsphome(l, { on: wasOn });
    return { ok: true };
  }
  return { ok: false, reason: "Can't blink this light." };
}

// ---- control ----
function httpPost(host: string, port: number, path: string, timeoutMs = 3000): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.request({ host, port, path, method: "POST", timeout: timeoutMs }, (res) => {
      res.resume(); resolve((res.statusCode || 500) < 400);
    });
    req.on("timeout", () => { req.destroy(); resolve(false); });
    req.on("error", () => resolve(false));
    req.end();
  });
}
function esphomePath(l: LocalLight, patch: Partial<LocalLight>): string {
  const entity = l.entity || l.name.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
  if (patch.on === false) return `/light/${entity}/turn_off`;
  const q: string[] = [];
  if (patch.brightness != null) q.push("brightness=" + Math.round(Math.max(0, Math.min(100, patch.brightness)) / 100 * 255));
  const rgb = patch.rgb;
  if (rgb) { q.push("r=" + (rgb.r | 0), "g=" + (rgb.g | 0), "b=" + (rgb.b | 0)); }
  if (patch.colorTempK != null) q.push("color_temp=" + Math.round(1e6 / patch.colorTempK)); // mireds
  return `/light/${entity}/turn_on` + (q.length ? "?" + q.join("&") : "");
}
async function applyEsphome(l: LocalLight, patch: Partial<LocalLight>): Promise<{ ok: boolean; reason?: string }> {
  if (!l.address) return { ok: false, reason: "No address for this light." };
  const ok = await httpPost(l.address, l.port || 80, esphomePath(l, patch));
  return ok ? { ok: true } : { ok: false, reason: "Light didn't respond on the LAN (is the hub on the same network?)." };
}
async function applyMatter(l: LocalLight, patch: Partial<LocalLight>): Promise<{ ok: boolean; reason?: string }> {
  const ctl = await matterController();
  if (!ctl) return { ok: false, reason: "No Matter controller on the hub — install chip-tool or matter-server (see Setup)." };
  if (ctl !== "chip-tool" || !l.node) return { ok: false, reason: "Matter control needs chip-tool with a commissioned node." };
  const ep = String(l.endpoint ?? 1);
  if (patch.on != null) await sh("chip-tool", ["onoff", patch.on ? "on" : "off", l.node, ep], 8000);
  if (patch.brightness != null) await sh("chip-tool", ["levelcontrol", "move-to-level", String(Math.round(patch.brightness / 100 * 254)), "0", "0", "0", l.node, ep], 8000);
  return { ok: true };
}

/** Apply a control patch to a real light; updates optimistic state on success. */
export async function control(id: string, patch: Partial<LocalLight>): Promise<{ ok: boolean; reason?: string; light?: LocalLight }> {
  const l = lights.find((x) => x.id === id);
  if (!l) return { ok: false, reason: "not found" };
  const res = l.backend === "esphome" ? await applyEsphome(l, patch) : await applyMatter(l, patch);
  if (res.ok) {
    if (patch.on != null) l.on = patch.on;
    if (patch.brightness != null) { l.brightness = Math.round(patch.brightness); if (patch.brightness > 0) l.on = true; }
    if (patch.rgb) { l.rgb = patch.rgb; l.on = true; }
    if (patch.colorTempK != null) l.colorTempK = patch.colorTempK;
    l.lastSeen = Date.now(); save(lights);
  }
  return { ...res, light: { ...l } };
}

// ---- maintenance / reconnection ----
function tcpReachable(host: string, port: number, timeoutMs = 2500): Promise<boolean> {
  return new Promise((resolve) => {
    const sock = new net.Socket(); let settled = false;
    const finish = (v: boolean) => { if (!settled) { settled = true; try { sock.destroy(); } catch {} resolve(v); } };
    sock.setTimeout(timeoutMs);
    sock.once("connect", () => finish(true));
    sock.once("timeout", () => finish(false));
    sock.once("error", () => finish(false));
    try { sock.connect(port, host); } catch { finish(false); }
  });
}
async function checkOne(l: LocalLight): Promise<void> {
  if (l.backend === "esphome" && l.address) {
    const up = await tcpReachable(l.address, l.port || 80);
    if (up) { l.status = "connected"; l.lastSeen = Date.now(); l.attempts = 0; }
    else { l.attempts++; l.status = l.attempts > 3 ? "offline" : "reconnecting"; }
  } else if (l.backend === "matter") {
    const ctl = await matterController();
    if (!ctl) { l.status = "offline"; return; }
    l.status = "connected"; l.lastSeen = Date.now(); l.attempts = 0; // controller present; node liveness is best-effort
  } else { l.status = "offline"; }
}
export async function reconnect(id: string): Promise<LocalLight | null> {
  const l = lights.find((x) => x.id === id); if (!l) return null;
  l.attempts = 0; await checkOne(l); save(lights); return { ...l };
}
let maintaining = false;
export async function maintain(): Promise<void> {
  if (maintaining || !lights.length) return;
  maintaining = true;
  try { for (const l of lights) await checkOne(l); save(lights); } finally { maintaining = false; }
}

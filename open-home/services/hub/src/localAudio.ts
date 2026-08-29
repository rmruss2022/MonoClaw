/**
 * Local speaker integration — discover, onboard and maintain real Wi-Fi (mDNS)
 * and Bluetooth (BlueZ) speakers on the hub's own network.
 *
 * Discovery backends are capability-aware and dependency-free:
 *   - Wi-Fi      → pure-Node mDNS multicast query (AirPlay/Chromecast/Sonos/Snapcast)
 *   - Bluetooth  → bluetoothctl (BlueZ) when a local adapter is present
 *
 * Onboarded speakers persist to <data>/local-speakers.json and a maintenance
 * loop keeps them connected — TCP reachability for Wi-Fi, `bluetoothctl connect`
 * for Bluetooth — tracking status so the UI can show connected / reconnecting /
 * offline and offer a manual retry.
 *
 * NOTE: discovery only sees devices on the SAME network / a real BT radio. Run
 * the hub on the LAN with your speakers (a Pi/Mac) for it to find them; a
 * cloud host will correctly report an empty scan.
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { execFile } from "node:child_process";
import dgram from "node:dgram";
import net from "node:net";

const DATA_DIR = new URL("../.data/", import.meta.url);
const STORE = new URL("../.data/local-speakers.json", import.meta.url);

export type LocalKind = "wifi" | "bluetooth";
export type ConnStatus = "connected" | "reconnecting" | "offline";

export interface LocalSpeaker {
  id: string; name: string; room: string; kind: LocalKind;
  address?: string; port?: number; mac?: string; service?: string;
  status: ConnStatus; lastSeen: number; attempts: number;
}

// ---- persistence ----
function load(): LocalSpeaker[] { try { return JSON.parse(readFileSync(STORE, "utf8")); } catch { return []; } }
function save(list: LocalSpeaker[]) { try { mkdirSync(DATA_DIR, { recursive: true }); writeFileSync(STORE, JSON.stringify(list)); } catch (e) { console.log("[local] save:", (e as Error).message); } }
let speakers: LocalSpeaker[] = load();

export function list(): LocalSpeaker[] { return speakers.map((s) => ({ ...s })); }

// ---- capability detection ----
function sh(cmd: string, args: string[], timeoutMs = 6000): Promise<{ ok: boolean; out: string }> {
  return new Promise((resolve) => {
    execFile(cmd, args, { timeout: timeoutMs }, (err, stdout) => resolve({ ok: !err, out: String(stdout || "") }));
  });
}
let btChecked = false, btAvailable = false;
async function bluetoothAvailable(): Promise<boolean> {
  if (btChecked) return btAvailable;
  const r = await sh("bluetoothctl", ["list"], 4000);
  btAvailable = r.ok && /Controller/i.test(r.out);
  btChecked = true;
  return btAvailable;
}
export async function capabilities() {
  return { wifi: true, bluetooth: await bluetoothAvailable() };
}

// ---- Wi-Fi discovery: minimal mDNS multicast query ----
const MDNS_ADDR = "224.0.0.251", MDNS_PORT = 5353;
const SERVICES: Record<string, string> = {
  "_raop._tcp.local": "airplay",       // AirPlay (HomePod, AirPort, many speakers)
  "_airplay._tcp.local": "airplay",
  "_googlecast._tcp.local": "chromecast", // Chromecast / Nest / Google
  "_sonos._tcp.local": "wifi",         // Sonos
  "_snapcast._tcp.local": "snapcast",  // Snapcast clients (our own)
  "_spotify-connect._tcp.local": "wifi",
};

function encodeName(name: string): Buffer {
  const parts = name.split(".").filter(Boolean);
  const bufs = parts.map((p) => { const b = Buffer.from(p); return Buffer.concat([Buffer.from([b.length]), b]); });
  return Buffer.concat([...bufs, Buffer.from([0])]);
}
function buildQuery(names: string[]): Buffer {
  const header = Buffer.alloc(12);
  header.writeUInt16BE(0, 0); header.writeUInt16BE(0, 2);       // id, flags (query)
  header.writeUInt16BE(names.length, 4);                        // qdcount
  const qs = names.map((n) => Buffer.concat([encodeName(n), Buffer.from([0x00, 0x0c, 0x00, 0x01])])); // PTR, IN
  return Buffer.concat([header, ...qs]);
}
// read a (possibly compressed) DNS name; returns [name, nextOffset]
function readName(buf: Buffer, off: number): [string, number] {
  const labels: string[] = []; let jumped = false, next = off, safety = 0;
  while (safety++ < 128) {
    if (off >= buf.length) break;
    const len = buf[off];
    if (len === 0) { off++; if (!jumped) next = off; break; }
    if ((len & 0xc0) === 0xc0) { // pointer
      const ptr = ((len & 0x3f) << 8) | buf[off + 1];
      if (!jumped) next = off + 2; jumped = true; off = ptr; continue;
    }
    labels.push(buf.slice(off + 1, off + 1 + len).toString("utf8")); off += 1 + len;
  }
  return [labels.join("."), next];
}

interface Wanswer { name: string; type: number; rdata: Buffer; roff: number; }
function parseAnswers(buf: Buffer): { answers: Wanswer[] } {
  const answers: Wanswer[] = [];
  try {
    const qd = buf.readUInt16BE(4), an = buf.readUInt16BE(6), ns = buf.readUInt16BE(8), ar = buf.readUInt16BE(10);
    let off = 12;
    for (let i = 0; i < qd; i++) { const [, n] = readName(buf, off); off = n + 4; }
    const total = an + ns + ar;
    for (let i = 0; i < total && off < buf.length; i++) {
      const [name, n] = readName(buf, off); off = n;
      const type = buf.readUInt16BE(off); off += 8; // type(2) class(2) ttl(4)
      const rdlen = buf.readUInt16BE(off); off += 2;
      answers.push({ name, type, rdata: buf.slice(off, off + rdlen), roff: off });
      off += rdlen;
    }
  } catch {}
  return { answers };
}

export function scanWifi(timeoutMs = 4000): Promise<Array<{ id: string; name: string; kind: string; address: string; port?: number; service: string }>> {
  return new Promise((resolve) => {
    const found = new Map<string, any>();
    let sock: dgram.Socket;
    try { sock = dgram.createSocket({ type: "udp4", reuseAddr: true }); } catch { resolve([]); return; }
    const done = () => { try { sock.close(); } catch {} resolve([...found.values()]); };
    sock.on("error", () => done());
    sock.on("message", (msg, rinfo) => {
      const { answers } = parseAnswers(msg);
      let instance = "", port: number | undefined, service = "";
      for (const a of answers) {
        if (a.type === 12) { // PTR → service instance
          const [target] = readName(msg, a.roff);
          for (const svc of Object.keys(SERVICES)) if (a.name.includes(svc.split(".")[0])) service = SERVICES[svc];
          instance = target.split("._")[0] || instance;
        } else if (a.type === 33) { // SRV → port
          try { port = a.rdata.readUInt16BE(4); } catch {}
          if (!instance) instance = a.name.split("._")[0];
          for (const svc of Object.keys(SERVICES)) if (a.name.includes(svc.split(".")[0])) service = SERVICES[svc];
        }
      }
      if (!service) return; // not an audio service we care about
      const address = rinfo.address;
      const name = decodeURIComponent(instance || `Speaker ${address}`);
      const id = "lan_" + Buffer.from(address + name).toString("hex").slice(0, 12);
      if (!found.has(id)) found.set(id, { id, name, kind: service === "chromecast" ? "chromecast" : service === "snapcast" ? "snapcast" : "wifi", address, port, service });
    });
    try {
      sock.bind(0, () => {
        try { sock.setMulticastTTL(255); } catch {}
        const q = buildQuery(Object.keys(SERVICES));
        sock.send(q, MDNS_PORT, MDNS_ADDR);
        setTimeout(() => sock.send(q, MDNS_PORT, MDNS_ADDR), 400); // second burst
      });
    } catch { done(); return; }
    setTimeout(done, timeoutMs);
  });
}

// ---- Bluetooth discovery via bluetoothctl ----
export async function scanBluetooth(timeoutMs = 8000): Promise<{ available: boolean; reason?: string; devices: Array<{ id: string; name: string; mac: string; kind: string }> }> {
  if (!(await bluetoothAvailable())) return { available: false, reason: "No Bluetooth adapter on this host.", devices: [] };
  await sh("bluetoothctl", ["--timeout", String(Math.ceil(timeoutMs / 1000)), "scan", "on"], timeoutMs + 2000);
  const r = await sh("bluetoothctl", ["devices"], 4000);
  const devices: any[] = [];
  for (const line of r.out.split("\n")) {
    const m = line.match(/Device\s+([0-9A-F:]{17})\s+(.+)/i);
    if (m) { const mac = m[1], name = m[2].trim(); devices.push({ id: "bt_" + mac.replace(/:/g, ""), name, mac, kind: "bluetooth" }); }
  }
  return { available: true, devices };
}

// ---- onboarding ----
export function onboard(dev: { name: string; kind: LocalKind; address?: string; port?: number; mac?: string; service?: string }, room: string): LocalSpeaker {
  const id = dev.mac ? "bt_" + dev.mac.replace(/:/g, "") : "lan_" + Buffer.from((dev.address || "") + dev.name).toString("hex").slice(0, 12);
  let sp = speakers.find((s) => s.id === id);
  if (!sp) { sp = { id, name: dev.name, room: room || "Living Room", kind: dev.kind, address: dev.address, port: dev.port, mac: dev.mac, service: dev.service, status: "reconnecting", lastSeen: 0, attempts: 0 }; speakers.push(sp); }
  else { sp.room = room || sp.room; }
  save(speakers);
  checkOne(sp).catch(() => {}); // connect immediately
  return { ...sp };
}
export function remove(id: string): boolean {
  const n = speakers.length; speakers = speakers.filter((s) => s.id !== id); if (speakers.length !== n) { save(speakers); return true; } return false;
}
export function setRoom(id: string, room: string) { const s = speakers.find((x) => x.id === id); if (s) { s.room = room || "—"; save(speakers); } }

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
async function btConnected(mac: string): Promise<boolean> {
  const r = await sh("bluetoothctl", ["info", mac], 4000);
  return /Connected:\s*yes/i.test(r.out);
}
async function checkOne(sp: LocalSpeaker): Promise<void> {
  if (sp.kind === "bluetooth" && sp.mac) {
    if (!(await bluetoothAvailable())) { sp.status = "offline"; return; }
    if (await btConnected(sp.mac)) { sp.status = "connected"; sp.lastSeen = Date.now(); sp.attempts = 0; return; }
    sp.status = "reconnecting"; sp.attempts++;
    const r = await sh("bluetoothctl", ["connect", sp.mac], 8000);
    if (r.ok && /Connection successful/i.test(r.out)) { sp.status = "connected"; sp.lastSeen = Date.now(); sp.attempts = 0; }
    else if (sp.attempts > 3) sp.status = "offline";
  } else if (sp.address) {
    const port = sp.port || (sp.service === "chromecast" ? 8009 : sp.service === "airplay" ? 7000 : sp.service === "snapcast" ? 1704 : 80);
    const up = await tcpReachable(sp.address, port);
    if (up) { sp.status = "connected"; sp.lastSeen = Date.now(); sp.attempts = 0; }
    else { sp.attempts++; sp.status = sp.attempts > 3 ? "offline" : "reconnecting"; }
  } else { sp.status = "offline"; }
}
export async function reconnect(id: string): Promise<LocalSpeaker | null> {
  const sp = speakers.find((s) => s.id === id); if (!sp) return null;
  sp.attempts = 0; await checkOne(sp); save(speakers); return { ...sp };
}
let maintaining = false;
export async function maintain(): Promise<void> {
  if (maintaining || !speakers.length) return;
  maintaining = true;
  try { for (const sp of speakers) await checkOne(sp); save(speakers); } finally { maintaining = false; }
}

/**
 * Hub reachability — how a phone finds this hub from anywhere.
 *
 * See CONNECTIVITY.md. In short: the hub knows its own addresses better than
 * anything else does, so it publishes them rather than waiting to be found.
 *
 * Addresses are ranked, lowest priority first:
 *
 *   custom  (5)  an owner's own DNS — they configured it, they meant it
 *   lan    (10)  fastest, private, never leaves the house
 *   tailnet(20)  works off-LAN with no public exposure
 *   tunnel (30)  works everywhere, costs a hop through someone else's network
 *
 * Nothing here is a secret, but addresses are location-revealing, which is why
 * publishing to the cloud is opt-out (see cacheDirectory).
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { networkInterfaces } from "node:os";
import { execFile } from "node:child_process";
import { createHash, createHmac, randomInt } from "node:crypto";

const FILE = new URL("../.data/connectivity.json", import.meta.url);
const DATA_DIR = new URL("../.data/", import.meta.url);

const PORT = Number(process.env.OPEN_HOME_PORT || 4700);
const CLOUD_URL = (process.env.OPEN_HOME_CLOUD_URL || "https://openhome-cloud-production.up.railway.app").replace(/\/$/, "");
const PUBLIC_URL = (process.env.OPEN_HOME_PUBLIC_URL || "").replace(/\/$/, "");
const HOME_ID = process.env.OPEN_HOME_HOME_ID || "";
const HOME_TOKEN_SECRET = process.env.HOME_TOKEN_SECRET || "";
/** Owners who want nothing of theirs in our DB set this to 0. */
const PUBLISH = process.env.OPEN_HOME_PUBLISH_ADDRESSES !== "0";

export type AddressKind = "custom" | "lan" | "tailnet" | "tunnel";
export interface HubAddress { kind: AddressKind; url: string; priority: number }

interface Store {
  hubId?: string;
  tunnelUrl?: string;
  pair?: { code: string; expires: number };
  lastRegister?: { at: number; ok: boolean; detail?: string };
}

function load(): Store {
  try { return JSON.parse(readFileSync(FILE, "utf8")); } catch { return {}; }
}
function save(s: Store) {
  try { mkdirSync(DATA_DIR, { recursive: true }); } catch {}
  writeFileSync(FILE, JSON.stringify(s, null, 2));
}

/**
 * Stable per-machine id. Derived from machine-id rather than stored, so it
 * survives losing .data but changes if the OS is reinstalled — which is the
 * behaviour you want: a reflashed box is a new hub.
 */
export function hubId(): string {
  const s = load();
  if (s.hubId) return s.hubId;
  let seed = "";
  for (const p of ["/etc/machine-id", "/var/lib/dbus/machine-id"]) {
    try { seed = readFileSync(p, "utf8").trim(); if (seed) break; } catch {}
  }
  if (!seed) seed = String(Date.now()) + Math.random();
  const id = "hub_" + createHash("sha256").update(seed).digest("hex").slice(0, 16);
  s.hubId = id; save(s);
  return id;
}

function ipv4s(): { lan: string[]; tailnet: string[] } {
  const lan: string[] = [], tailnet: string[] = [];
  for (const [name, addrs] of Object.entries(networkInterfaces())) {
    for (const a of addrs ?? []) {
      if (a.family !== "IPv4" || a.internal) continue;
      // Tailscale hands out 100.64.0.0/10 (CGNAT). Treat that as its own kind:
      // it reaches off-LAN without exposing anything publicly.
      const first = Number(a.address.split(".")[0]);
      const second = Number(a.address.split(".")[1]);
      if (first === 100 && second >= 64 && second <= 127) tailnet.push(a.address);
      else if (name.startsWith("tailscale")) tailnet.push(a.address);
      else lan.push(a.address);
    }
  }
  return { lan, tailnet };
}

/** Every way this hub can currently be reached, best first. */
export function addresses(): HubAddress[] {
  const out: HubAddress[] = [];
  if (PUBLIC_URL) out.push({ kind: "custom", url: PUBLIC_URL, priority: 5 });
  const { lan, tailnet } = ipv4s();
  for (const ip of lan) out.push({ kind: "lan", url: `http://${ip}:${PORT}`, priority: 10 });
  for (const ip of tailnet) out.push({ kind: "tailnet", url: `http://${ip}:${PORT}`, priority: 20 });
  const t = load().tunnelUrl;
  if (t) out.push({ kind: "tunnel", url: t, priority: 30 });
  return out.sort((a, b) => a.priority - b.priority);
}

export function setTunnelUrl(url: string) {
  const s = load();
  s.tunnelUrl = url.replace(/\/$/, "");
  save(s);
}

/**
 * A short code the owner types into the app to claim this hub.
 *
 * Deliberately NOT an access token — it only authorises *linking* a hub to an
 * account. Single use, 10 minutes, and unambiguous characters only so it can be
 * read aloud or off a TV across a room.
 */
const ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"; // no I/O/0/1
export function pairingCode(): { code: string; expiresIn: number } {
  const s = load();
  const now = Date.now();
  if (s.pair && s.pair.expires > now) {
    return { code: s.pair.code, expiresIn: Math.round((s.pair.expires - now) / 1000) };
  }
  let code = "";
  for (let i = 0; i < 6; i++) code += ALPHABET[randomInt(ALPHABET.length)];
  s.pair = { code, expires: now + 10 * 60_000 };
  save(s);
  return { code, expiresIn: 600 };
}

export function consumePairingCode(code: string): boolean {
  const s = load();
  const ok = !!s.pair && s.pair.expires > Date.now() &&
             s.pair.code.toUpperCase() === String(code || "").toUpperCase();
  if (ok) { delete s.pair; save(s); }
  return ok;
}

/**
 * Tell the cloud where we are. Signed with HOME_TOKEN_SECRET so nobody else can
 * re-point someone's home at a hub they control.
 *
 * Failure is never fatal — a hub with no internet must still work perfectly on
 * the LAN. We record the outcome so /hub/connectivity can show it honestly
 * rather than implying success.
 */
export async function register(): Promise<{ ok: boolean; detail: string }> {
  const s = load();
  if (!PUBLISH) {
    const detail = "publishing disabled (OPEN_HOME_PUBLISH_ADDRESSES=0)";
    s.lastRegister = { at: Date.now(), ok: false, detail }; save(s);
    return { ok: false, detail };
  }
  if (!HOME_ID || !HOME_TOKEN_SECRET) {
    const detail = "not paired yet (OPEN_HOME_HOME_ID / HOME_TOKEN_SECRET unset)";
    s.lastRegister = { at: Date.now(), ok: false, detail }; save(s);
    return { ok: false, detail };
  }
  const body = {
    homeId: HOME_ID,
    hubId: hubId(),
    addresses: addresses(),
    at: Date.now(),
  };
  // HMAC, not sha256(secret||body): the latter is length-extendable, so a
  // captured signature could be extended into a valid one for a longer body.
  const payload = JSON.stringify(body);
  const sig = createHmac("sha256", HOME_TOKEN_SECRET).update(payload).digest("base64url");
  try {
    const r = await fetch(`${CLOUD_URL}/api/hub/register`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-openhome-signature": sig },
      body: payload,
      signal: AbortSignal.timeout(10_000),
    });
    const detail = `HTTP ${r.status}`;
    const ok = r.ok;
    s.lastRegister = { at: Date.now(), ok, detail }; save(s);
    return { ok, detail };
  } catch (e: any) {
    const detail = String(e?.message || e).slice(0, 120);
    s.lastRegister = { at: Date.now(), ok: false, detail }; save(s);
    return { ok: false, detail };
  }
}

/** Everything the app or a human needs to understand reachability right now. */
export function status() {
  const s = load();
  return {
    hubId: hubId(),
    paired: !!HOME_ID,
    homeId: HOME_ID || null,
    publishing: PUBLISH,
    cloudUrl: CLOUD_URL,
    customUrl: PUBLIC_URL || null,
    addresses: addresses(),
    lastRegister: s.lastRegister ?? null,
  };
}

let timer: NodeJS.Timeout | null = null;
/** Register on boot, then every 5 minutes so a DHCP change is picked up. */
export function startHeartbeat(): void {
  if (timer) return;
  void register();
  timer = setInterval(() => { void register(); }, 5 * 60_000);
  if (typeof timer.unref === "function") timer.unref();
}

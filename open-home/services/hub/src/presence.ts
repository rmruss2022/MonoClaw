/**
 * Who is home — over Wi-Fi, with no extra hardware.
 *
 * This is NOT room detection. One hub is one vantage point, so the honest
 * ceiling here is "home or away" plus "how long". Per-room needs a radio per
 * room; see proximity.ts, which is built and waiting for one.
 *
 * Finding phones is harder than it looks, for two reasons:
 *
 *  - Apple randomises Wi-Fi MACs, but the random MAC is STABLE per network, so
 *    tracking it works fine once learned. Hostnames are even better: an iPhone
 *    answers to <name>.local over mDNS whatever its MAC.
 *  - A sleeping iPhone ignores ICMP. Pinging it reports "away" while it sits
 *    on the nightstand. iOS keeps TCP 62078 (lockdownd) open and answers it
 *    even when asleep, so that is the probe that actually works. ARP is the
 *    backstop, since a device on the network must answer ARP to use it.
 *
 * Absence is therefore only believed after several consecutive misses.
 */
import { spawn } from "node:child_process";
import { createConnection } from "node:net";
import { durableStore } from "./durableStore.ts";

const DATA_DIR = new URL("../.data/", import.meta.url);

export interface Person {
  id: string;
  name: string;
  /** mDNS name (preferred — survives MAC rotation) e.g. "Matthews-iPhone-2.local" */
  host?: string;
  /** Last known IP; a hint only, re-resolved from `host` when it goes stale. */
  ip?: string;
  /** Wi-Fi MAC, used for the ARP backstop. */
  mac?: string;
  /** Ports worth probing. iOS: 62078. macOS: 7000/5000 (AirPlay). */
  ports?: number[];
}

export interface PresenceState {
  home: boolean;
  since: number;       // when the current state began
  lastSeen: number;    // last successful probe
  misses: number;
}

// A phone that has been quiet this many rounds is treated as gone. At a 30s
// interval that is five minutes — long enough to ride out deep sleep, short
// enough to be useful for "did he just get home".
const MISSES_BEFORE_AWAY = Number(process.env.OPEN_HOME_PRESENCE_MISSES ?? 10);
const INTERVAL_MS = Number(process.env.OPEN_HOME_PRESENCE_INTERVAL_MS ?? 30_000);

const peopleStore = durableStore<Person[]>(DATA_DIR, "people.json", "people");
let people: Person[] = peopleStore.load([]);
const state = new Map<string, PresenceState>();

export function list(): Array<Person & PresenceState> {
  return people.map((p) => ({
    ...p,
    ...(state.get(p.id) ?? { home: false, since: 0, lastSeen: 0, misses: 0 }),
  }));
}

export function add(p: Person): Person[] {
  if (!people.some((x) => x.id === p.id)) people.push(p);
  else people = people.map((x) => (x.id === p.id ? { ...x, ...p } : x));
  peopleStore.save(people);
  return people;
}

export function remove(id: string): void {
  people = people.filter((p) => p.id !== id);
  state.delete(id);
  peopleStore.save(people);
}

/** True if anyone is home. */
export interface Arrival { at: number; id: string; name: string; event: "home" | "left" }
const HISTORY_MAX = 200;
const historyStore = durableStore<Arrival[]>(DATA_DIR, "presence-log.json", "presence");
let history: Arrival[] = historyStore.load([]);

/** Arrivals and departures, newest last. Survives restarts. */
export function log(limit = 50): Arrival[] { return history.slice(-limit); }

function record(p: Person, event: "home" | "left"): void {
  history.push({ at: Date.now(), id: p.id, name: p.name, event });
  if (history.length > HISTORY_MAX) history = history.slice(-HISTORY_MAX);
  historyStore.save(history);
}

export function anyoneHome(): boolean {
  return [...state.values()].some((s) => s.home);
}

function sh(cmd: string, args: string[], timeoutMs = 4000): Promise<string> {
  return new Promise((resolve) => {
    const p = spawn(cmd, args);
    let out = "";
    const timer = setTimeout(() => { try { p.kill(); } catch {} resolve(out); }, timeoutMs);
    p.stdout?.on("data", (d) => { out += d; });
    p.on("exit", () => { clearTimeout(timer); resolve(out); });
    p.on("error", () => { clearTimeout(timer); resolve(""); });
  });
}

/** Resolve a .local name to an IP. Survives the device changing address. */
async function resolveHost(host: string): Promise<string | null> {
  const out = await sh("avahi-resolve", ["-n", host], 4000);
  const m = out.trim().split(/\s+/)[1];
  return m && /^\d+\.\d+\.\d+\.\d+$/.test(m) ? m : null;
}

function tcpOpen(ip: string, port: number, timeoutMs = 1500): Promise<boolean> {
  return new Promise((resolve) => {
    const sock = createConnection({ host: ip, port });
    let done = false;
    const finish = (v: boolean) => { if (!done) { done = true; try { sock.destroy(); } catch {} resolve(v); } };
    sock.setTimeout(timeoutMs);
    sock.once("connect", () => finish(true));
    // A refused connection still proves the host is awake and on the network.
    sock.once("error", (e: any) => finish(e?.code === "ECONNREFUSED"));
    sock.once("timeout", () => finish(false));
  });
}

async function inArpTable(ip: string): Promise<boolean> {
  const out = await sh("ip", ["neigh", "show", ip], 2500);
  // ONLY REACHABLE. A STALE entry just means the kernel has not re-verified
  // the address recently — it lingers long after a device has left, so
  // accepting it reported Matthew home continuously from 13:59 to 17:49 while
  // he was actually out. STALE is "unknown", not "present".
  return /REACHABLE/.test(out);
}

async function probe(p: Person): Promise<boolean> {
  let ip = p.ip ?? null;
  if (p.host) {
    const fresh = await resolveHost(p.host);
    if (fresh) {
      if (fresh !== p.ip) { p.ip = fresh; peopleStore.save(people); }
      ip = fresh;
    }
  }
  if (!ip) return false;

  for (const port of p.ports ?? [62078, 7000, 5000, 22]) {
    if (await tcpOpen(ip, port)) return true;
  }
  // Nudge the ARP cache, then read it. A sleeping phone answers ARP even when
  // it ignores everything else — but only a REACHABLE entry proves that just
  // happened. The ping is what forces the re-verification.
  await sh("ping", ["-c", "2", "-W", "1", ip], 3000);
  return inArpTable(ip);
}

async function tick(opts: { silent?: boolean } = {}): Promise<void> {
  for (const p of people) {
    const now = Date.now();
    const prev = state.get(p.id) ?? { home: false, since: now, lastSeen: 0, misses: 0 };
    const seen = await probe(p).catch(() => false);

    if (seen) {
      if (!prev.home && !opts.silent) { console.log(`[presence] ${p.name} is home`); record(p, "home"); onArrive.forEach((f) => { try { f(p); } catch {} }); }
      state.set(p.id, { home: true, since: prev.home ? prev.since : now, lastSeen: now, misses: 0 });
      continue;
    }
    const misses = prev.misses + 1;
    const stillHome = prev.home && misses < MISSES_BEFORE_AWAY;
    if (prev.home && !stillHome) {
      console.log(`[presence] ${p.name} left (${misses} misses over ${Math.round(misses * INTERVAL_MS / 60000)} min)`);
      record(p, "left");
    }
    state.set(p.id, {
      home: stillHome,
      since: stillHome ? prev.since : (prev.home ? now : prev.since),
      lastSeen: prev.lastSeen,
      misses,
    });
  }
}

type Hook = (p: Person) => void;
const onArrive: Hook[] = [];
/** Called when someone arrives — used for the welcome-home greeting. */
export function onArrival(fn: Hook): void { onArrive.push(fn); }

let timer: ReturnType<typeof setInterval> | null = null;
export function start(): void {
  if (timer) return;
  // Seed Matthew's phone on first run so this works out of the box; the mDNS
  // name is what the hub actually saw on the network.
  if (!people.length) {
    add({ id: "matthew", name: "Matthew", host: "Matthews-iPhone-2.local", ports: [62078, 49152] });
  }
  // Seed state silently first: the first poll after a hub restart is not an
  // arrival, and announcing "welcome home" on every deploy would be absurd.
  tick({ silent: true }).catch(() => {});
  timer = setInterval(() => { tick().catch(() => {}); }, INTERVAL_MS);
}

/**
 * openhome hub client — cloud-routed.
 *
 * The app signs in to the openhome-cloud control-plane (email + password), which
 * hands back a short-lived, home-scoped grant and the hub's endpoint. From then on
 * the app talks *directly* to the hub, carrying the grant as the `oh_auth` cookie —
 * the cloud is never in the data path. This mirrors the web /sso hand-off.
 *
 *   app ──(email+pw)──► control-plane ──► {endpoint, homeToken}
 *   app ──(oh_auth=homeToken)──────────► hub (your house)
 *
 * The control-plane session (30 days) is kept so we can silently refresh the
 * 12-hour home token when it lapses.
 */
import AsyncStorage from "@react-native-async-storage/async-storage";

const CP_URL_KEY = "oh_cp_url";
const CP_SESSION_KEY = "oh_cp_session";
const HUB_URL_KEY = "oh_hub_url";
const HOME_TOKEN_KEY = "oh_home_token";
const EMAIL_KEY = "oh_email";
const LAST_GOOD_KEY = "oh_last_good";

// Default control-plane. Can be overridden in Settings (e.g. app.bedrock.casa later).
export const DEFAULT_CONTROL_PLANE = "https://openhome-cloud-production.up.railway.app";

let controlPlane = DEFAULT_CONTROL_PLANE;
let cpSession: string | null = null;
let hubUrl: string | null = null;
let homeToken: string | null = null;
let email: string | null = null;

export async function loadSession(): Promise<void> {
  controlPlane = (await AsyncStorage.getItem(CP_URL_KEY)) || DEFAULT_CONTROL_PLANE;
  cpSession = await AsyncStorage.getItem(CP_SESSION_KEY);
  hubUrl = await AsyncStorage.getItem(HUB_URL_KEY);
  homeToken = await AsyncStorage.getItem(HOME_TOKEN_KEY);
  email = await AsyncStorage.getItem(EMAIL_KEY);
}

export function getControlPlane(): string {
  return controlPlane;
}
export function getEmail(): string | null {
  return email;
}
export function getHubUrl(): string | null {
  return hubUrl;
}
export function hasSession(): boolean {
  return !!cpSession;
}

/** The home grant, reused by the TV content-router client (same Bearer token). */
export function getHomeToken(): string | null {
  return homeToken;
}

export async function setControlPlane(url: string): Promise<void> {
  controlPlane = url.replace(/\/+$/, "");
  await AsyncStorage.setItem(CP_URL_KEY, controlPlane);
}

async function persist(): Promise<void> {
  await AsyncStorage.multiSet([
    [CP_SESSION_KEY, cpSession ?? ""],
    [HUB_URL_KEY, hubUrl ?? ""],
    [HOME_TOKEN_KEY, homeToken ?? ""],
    [EMAIL_KEY, email ?? ""],
  ]);
}

export class AuthError extends Error {}
export class HubError extends Error {}

/** Resolve (or refresh) the home endpoint + grant from the control-plane. */
export interface HubAddress { kind: string; url: string; priority: number }

function normalise(u: string): string {
  const s = String(u).trim().replace(/\/+$/, "");
  return /^https?:\/\//.test(s) ? s : `https://${s}`;
}

/** Is this URL a live hub? Short timeout — we are racing, not waiting. */
async function probe(url: string, timeoutMs = 1500): Promise<boolean> {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), timeoutMs);
    const r = await fetch(`${url}/health`, { signal: ctrl.signal });
    clearTimeout(t);
    if (!r.ok) return false;
    const j = await r.json().catch(() => null);
    return !!j && (j.status === "ok" || j.service === "open-home-hub");
  } catch {
    return false;
  }
}

/**
 * Probe every candidate simultaneously and resolve with the first that answers.
 *
 * Promise.any would reject only when ALL reject, which is what we want, but we
 * also want a hard ceiling so a hung network cannot stall sign-in. Hence the
 * timeout racer alongside.
 */
async function raceAddresses(urls: string[], timeoutMs = 2500): Promise<string | null> {
  const unique = [...new Set(urls.map(normalise))].filter(Boolean);
  if (!unique.length) return null;
  const attempts = unique.map(
    (u) => new Promise<string>((resolve, reject) => {
      probe(u, timeoutMs).then((ok) => (ok ? resolve(u) : reject(new Error("dead"))), reject);
    }),
  );
  const ceiling = new Promise<null>((resolve) => setTimeout(() => resolve(null), timeoutMs + 400));
  try {
    const winner = await Promise.race([Promise.any(attempts), ceiling]);
    return (winner as string) || null;
  } catch {
    return null;
  }
}

/** Addresses the control-plane knows about, best first. */
let knownAddresses: HubAddress[] = [];
export function getKnownAddresses(): HubAddress[] { return knownAddresses; }

async function resolveHome(): Promise<boolean> {
  if (!cpSession) return false;
  let body: any = null;
  try {
    const res = await fetch(`${controlPlane}/api/home`, {
      headers: { Accept: "application/json", Authorization: `Bearer ${cpSession}` },
    });
    if (!res.ok) return false;
    body = await res.json();
  } catch { return false; }
  if (!body?.ok || !body.homeToken) return false;

  homeToken = String(body.homeToken);
  knownAddresses = Array.isArray(body.addresses) ? body.addresses : [];

  // Build the candidate list: what worked last time, then the ranked list,
  // then the legacy single endpoint so older control-planes still work.
  const lastGood = await AsyncStorage.getItem(LAST_GOOD_KEY);
  const ranked = [...knownAddresses]
    .sort((a, b) => (a.priority ?? 50) - (b.priority ?? 50))
    .map((a) => a.url);
  const legacy = body.endpoint ? [String(body.endpoint)] : [];

  // The last known-good address gets its own quick shot first: the usual case
  // is nothing has changed, and that should resolve in milliseconds.
  if (lastGood && (await probe(normalise(lastGood), 1200))) {
    hubUrl = normalise(lastGood);
    await persist();
    return true;
  }

  const winner = await raceAddresses([...ranked, ...legacy]);
  if (!winner) {
    // Keep the best guess so the UI can show it and offer a manual override,
    // rather than leaving the user with nothing to act on.
    hubUrl = ranked[0] ? normalise(ranked[0]) : legacy[0] ? normalise(legacy[0]) : null;
    await persist();
    return false;
  }
  hubUrl = winner;
  await AsyncStorage.setItem(LAST_GOOD_KEY, winner);
  await persist();
  return true;
}

/** Point the app at a hub by hand (Settings → Advanced, or onboarding). */
export async function setHubUrlManual(url: string): Promise<boolean> {
  const u = normalise(url);
  if (!(await probe(u, 4000))) return false;
  hubUrl = u;
  await AsyncStorage.setItem(LAST_GOOD_KEY, u);
  await persist();
  return true;
}

/**
 * Claim a hub with the 6-character code it displays.
 * Tried against each candidate because a brand-new app may only be able to
 * reach the hub on the LAN.
 */
export async function claimWithCode(code: string, candidates: string[]): Promise<string | null> {
  for (const c of [...new Set(candidates.map(normalise))]) {
    try {
      const r = await fetch(`${c}/hub/pair/claim`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: code.trim().toUpperCase() }),
      });
      if (!r.ok) continue;
      const j = await r.json();
      if (j?.ok) {
        hubUrl = c;
        await AsyncStorage.setItem(LAST_GOOD_KEY, c);
        await persist();
        return c;
      }
    } catch { /* try the next candidate */ }
  }
  return null;
}

/**
 * Sign in to the control-plane, then fetch the routing grant.
 *   "ok"       signed in and routed to a home
 *   "no_home"  signed in but no hub paired to the account yet
 *   "bad"      wrong email/password
 *   "error"    couldn't reach the control-plane
 */
export async function login(mail: string, password: string): Promise<"ok" | "no_home" | "bad" | "error"> {
  try {
    const res = await fetch(`${controlPlane}/api/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ email: mail, password }),
    });
    if (res.status === 401) return "bad";
    if (!res.ok) return "error";
    const body = await res.json();
    if (!body?.ok || !body.token) return "bad";
    cpSession = String(body.token);
    email = mail;
    await persist();
    return (await resolveHome()) ? "ok" : "no_home";
  } catch {
    return "error";
  }
}

/** True if we have a usable grant (or can refresh one) for the hub. */
export async function ensureHome(): Promise<boolean> {
  if (hubUrl && homeToken) return true;
  return resolveHome();
}

/**
 * Call a hub endpoint with the home grant. Transparently refreshes the grant
 * once on 401 (home tokens live 12h; the control-plane session lives 30 days).
 */
export async function api<T = any>(
  path: string,
  opts: { method?: string; body?: unknown; timeoutMs?: number; _retried?: boolean } = {}
): Promise<T> {
  if (!hubUrl || !homeToken) {
    if (!(await resolveHome())) throw new AuthError("no_home");
  }
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), opts.timeoutMs ?? 12000);
  try {
    const res = await fetch(`${hubUrl}${path}`, {
      method: opts.method ?? "GET",
      headers: {
        Accept: "application/json",
        // Bearer is the reliable path on native (cookie jars can drop a manual
        // Cookie header); the cookie is kept for parity with the web client.
        Authorization: `Bearer ${homeToken}`,
        Cookie: `oh_auth=${homeToken}`,
        ...(opts.body ? { "Content-Type": "application/json" } : {}),
      },
      body: opts.body ? JSON.stringify(opts.body) : undefined,
      signal: ctrl.signal,
    });
    if (res.status === 401) {
      // Grant may have lapsed — refresh once and retry.
      if (!opts._retried && (await resolveHome())) {
        return api<T>(path, { ...opts, _retried: true });
      }
      throw new AuthError("unauthorized");
    }
    if (!res.ok) throw new HubError(`${res.status} ${path}`);
    const text = await res.text();
    return (text ? JSON.parse(text) : {}) as T;
  } finally {
    clearTimeout(timer);
  }
}

export async function logout(): Promise<void> {
  // Best-effort revoke the control-plane session.
  try {
    if (cpSession) {
      await fetch(`${controlPlane}/api/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${cpSession}` },
      });
    }
  } catch {
    /* ignore */
  }
  cpSession = null;
  hubUrl = null;
  homeToken = null;
  email = null;
  await AsyncStorage.multiRemove([CP_SESSION_KEY, HUB_URL_KEY, HOME_TOKEN_KEY, EMAIL_KEY]);
}

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
async function resolveHome(): Promise<boolean> {
  if (!cpSession) return false;
  const res = await fetch(`${controlPlane}/api/home`, {
    headers: { Accept: "application/json", Authorization: `Bearer ${cpSession}` },
  });
  if (!res.ok) return false;
  const body = await res.json();
  if (!body?.ok || !body.endpoint || !body.homeToken) return false;
  hubUrl = `https://${String(body.endpoint).replace(/^https?:\/\//, "").replace(/\/+$/, "")}`;
  homeToken = String(body.homeToken);
  await persist();
  return true;
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

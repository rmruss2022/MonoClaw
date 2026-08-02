/**
 * Real Spotify integration — OAuth 2.0 Authorization Code + Web API.
 *
 * Setup (one time):
 *   1. Create an app at https://developer.spotify.com/dashboard
 *   2. Add a Redirect URI that matches SPOTIFY_REDIRECT_URI below
 *      (e.g. https://<your-tunnel>/audio/spotify/callback)
 *   3. Set env: SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI
 *
 * Tokens persist to <data>/spotify-tokens.json so sign-in survives restarts.
 */
import { readFile, writeFile, mkdir } from "node:fs/promises";

const CLIENT_ID = process.env.SPOTIFY_CLIENT_ID || "";
const CLIENT_SECRET = process.env.SPOTIFY_CLIENT_SECRET || "";
const REDIRECT_URI = process.env.SPOTIFY_REDIRECT_URI || "http://127.0.0.1:4700/audio/spotify/callback";
const SCOPES = [
  "user-read-private", "user-read-email",
  "playlist-read-private", "playlist-read-collaborative",
  "user-library-read", "user-top-read",
  "user-read-playback-state", "user-modify-playback-state", "streaming",
].join(" ");

const DATA_DIR = new URL("../.data/", import.meta.url);
const TOKEN_FILE = new URL("../.data/spotify-tokens.json", import.meta.url);

interface Tokens { access_token: string; refresh_token: string; expires_at: number; }
let tokens: Tokens | null = null;
let profile: { name: string; email?: string; image?: string; product?: string } | null = null;

export function configured(): boolean { return !!(CLIENT_ID && CLIENT_SECRET); }
export function connected(): boolean { return !!tokens?.refresh_token; }
export function redirectUri(): string { return REDIRECT_URI; }

export function status() {
  return { configured: configured(), connected: connected(), profile, redirectUri: REDIRECT_URI };
}

export async function load(): Promise<void> {
  try {
    tokens = JSON.parse(await readFile(TOKEN_FILE, "utf8"));
    await me().catch(() => {}); // warm the profile
  } catch { tokens = null; }
}

async function persist(): Promise<void> {
  await mkdir(DATA_DIR, { recursive: true });
  await writeFile(TOKEN_FILE, JSON.stringify(tokens), { mode: 0o600 });
}

export function authUrl(state: string): string {
  const p = new URLSearchParams({
    response_type: "code", client_id: CLIENT_ID, scope: SCOPES,
    redirect_uri: REDIRECT_URI, state, show_dialog: "false",
  });
  return `https://accounts.spotify.com/authorize?${p.toString()}`;
}

function basicAuth(): string { return "Basic " + Buffer.from(`${CLIENT_ID}:${CLIENT_SECRET}`).toString("base64"); }

export async function exchangeCode(code: string): Promise<boolean> {
  const body = new URLSearchParams({ grant_type: "authorization_code", code, redirect_uri: REDIRECT_URI });
  const r = await fetch("https://accounts.spotify.com/api/token", {
    method: "POST", headers: { Authorization: basicAuth(), "Content-Type": "application/x-www-form-urlencoded" }, body,
  });
  if (!r.ok) { console.log("[spotify] token exchange failed", r.status, await r.text()); return false; }
  const j: any = await r.json();
  tokens = { access_token: j.access_token, refresh_token: j.refresh_token, expires_at: Date.now() + (j.expires_in - 60) * 1000 };
  await persist(); await me().catch(() => {});
  return true;
}

export function disconnect(): void { tokens = null; profile = null; persist().catch(() => {}); }

async function accessToken(): Promise<string | null> {
  if (!tokens) return null;
  if (Date.now() < tokens.expires_at) return tokens.access_token;
  const body = new URLSearchParams({ grant_type: "refresh_token", refresh_token: tokens.refresh_token });
  const r = await fetch("https://accounts.spotify.com/api/token", {
    method: "POST", headers: { Authorization: basicAuth(), "Content-Type": "application/x-www-form-urlencoded" }, body,
  });
  if (!r.ok) { console.log("[spotify] refresh failed", r.status); return null; }
  const j: any = await r.json();
  tokens.access_token = j.access_token;
  tokens.expires_at = Date.now() + (j.expires_in - 60) * 1000;
  if (j.refresh_token) tokens.refresh_token = j.refresh_token;
  await persist();
  return tokens.access_token;
}

async function api(path: string, init?: RequestInit): Promise<any> {
  const tok = await accessToken();
  if (!tok) throw new Error("not_connected");
  const r = await fetch(`https://api.spotify.com/v1${path}`, {
    ...init, headers: { ...(init?.headers || {}), Authorization: `Bearer ${tok}` },
  });
  if (r.status === 204) return {};
  const txt = await r.text();
  if (!r.ok) throw new Error(`spotify_${r.status}: ${txt.slice(0, 200)}`);
  return txt ? JSON.parse(txt) : {};
}

export async function me() {
  const j = await api("/me");
  profile = { name: j.display_name || j.id, email: j.email, image: j.images?.[0]?.url, product: j.product };
  return profile;
}

export async function playlists(limit = 50) {
  const j = await api(`/me/playlists?limit=${limit}`);
  return (j.items || []).map((p: any) => ({
    id: p.id, uri: p.uri, name: p.name, tracks: p.tracks?.total ?? 0,
    image: p.images?.[0]?.url, owner: p.owner?.display_name, ownerId: p.owner?.id,
  }));
}

export async function liked(limit = 50) {
  const j = await api(`/me/tracks?limit=${limit}`);
  return (j.items || []).map((it: any) => trackOf(it.track));
}

export async function topTracks(limit = 20) {
  const j = await api(`/me/top/tracks?limit=${limit}&time_range=medium_term`);
  return (j.items || []).map(trackOf);
}

export async function playlistTracks(id: string, limit = 100) {
  const j = await api(`/playlists/${id}/tracks?limit=${limit}`);
  return (j.items || []).map((it: any) => trackOf(it.track)).filter((t: any) => t.id);
}

export async function search(q: string) {
  const j = await api(`/search?type=track&limit=12&q=${encodeURIComponent(q)}`);
  return (j.tracks?.items || []).map(trackOf);
}

export async function devices() {
  const j = await api("/me/player/devices");
  return (j.devices || []).map((d: any) => ({ id: d.id, name: d.name, type: d.type, active: d.is_active, volume: d.volume_percent }));
}

/** Pick a Connect device — prefer the MacBook, then any computer, then whatever's active. */
export async function pickDeviceId(prefer = "mac"): Promise<{ id: string; name: string } | null> {
  const ds = await devices();
  if (!ds.length) return null;
  const p = prefer.toLowerCase();
  const d = ds.find((x: any) => (x.name || "").toLowerCase().includes(p) || (x.name || "").toLowerCase().includes("book"))
    || ds.find((x: any) => x.type === "Computer")
    || ds.find((x: any) => x.active)
    || ds[0];
  return { id: d.id, name: d.name };
}

/** Play a context (playlist uri) or track uris. Defaults output to the MacBook. */
export async function play(opts: { contextUri?: string; uris?: string[]; deviceId?: string; prefer?: string }) {
  let deviceId = opts.deviceId, deviceName = "";
  if (!deviceId) { const d = await pickDeviceId(opts.prefer ?? "mac"); if (!d) throw new Error("no_device"); deviceId = d.id; deviceName = d.name; }
  const body: any = {};
  if (opts.contextUri) body.context_uri = opts.contextUri;
  if (opts.uris) body.uris = opts.uris;
  await api(`/me/player/play?device_id=${deviceId}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  return { ok: true, device: deviceName };
}

export async function transportRemote(action: "play" | "pause" | "next" | "previous") {
  const m = action === "play" ? "PUT" : action === "pause" ? "PUT" : "POST";
  const path = action === "play" ? "/me/player/play" : action === "pause" ? "/me/player/pause" : `/me/player/${action}`;
  await api(path, { method: m });
  return { ok: true };
}

/** What Spotify is actually playing right now (drives the Now Playing bar). */
export async function currentlyPlaying() {
  const j = await api("/me/player/currently-playing");
  if (!j || !j.item) return null;
  const t = j.item;
  return {
    source: "spotify" as const,
    title: t.name, artist: (t.artists || []).map((a: any) => a.name).join(", "),
    album: t.album?.name ?? "", art: t.album?.images?.[0]?.url ?? "",
    playing: !!j.is_playing, positionMs: j.progress_ms ?? 0, durationMs: t.duration_ms ?? 0,
    device: j.device?.name ?? "",
  };
}

function trackOf(t: any) {
  if (!t) return { id: "" };
  return {
    id: t.id, uri: t.uri, title: t.name,
    artist: (t.artists || []).map((a: any) => a.name).join(", "),
    album: t.album?.name, image: t.album?.images?.[0]?.url,
    durationMs: t.duration_ms,
  };
}

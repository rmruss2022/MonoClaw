/**
 * Content-router client for the phone's TV tab. Reuses the openhome account grant
 * (same Bearer home token as the hub) so search + cast work with no extra login.
 */
import { getHomeToken } from "@/api/client";

// Point at the deployed content-router (configurable later in Settings).
export const DEFAULT_ROUTER = "https://openhome-tv-production.up.railway.app";

export interface TvSource { service: string; serviceName: string; offer: string; price?: number; quality?: string }
export interface TvTitle {
  id: string; type: "movie" | "show" | "music"; name: string; year?: number;
  overview?: string; poster?: string; rating?: number; genres?: string[]; sources: TvSource[];
}
export interface TvStick { id: string; name: string; region: string; online: boolean; installed: string[]; owned: string[] }

let routerUrl = DEFAULT_ROUTER;
export function setRouterUrl(u: string) { routerUrl = u.replace(/\/+$/, ""); }

function headers(json = false): Record<string, string> {
  const h: Record<string, string> = { Accept: "application/json" };
  if (json) h["Content-Type"] = "application/json";
  const t = getHomeToken();
  if (t) h["Authorization"] = `Bearer ${t}`;
  return h;
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${routerUrl}${path}`, { headers: headers() });
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}
async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${routerUrl}${path}`, { method: "POST", headers: headers(true), body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}

export const tv = {
  search: (q: string, type?: string) =>
    get<{ results: TvTitle[] }>(`/search?q=${encodeURIComponent(q)}${type ? `&type=${type}` : ""}`).then((r) => r.results),
  trending: (type?: string) =>
    get<{ results: TvTitle[] }>(`/trending${type ? `?type=${type}` : ""}`).then((r) => r.results),
  sticks: () => get<{ sticks: TvStick[] }>(`/sticks`).then((r) => r.sticks),
  pair: (code: string) => post<{ ok: boolean; stick?: TvStick; error?: string }>(`/sticks/pair/claim`, { code }),
  cast: (titleId: string, stickId: string) =>
    post<{ ok: boolean; route?: any; castTo?: string; reason?: string }>(`/route`, { titleId, stickId }),
  command: (stickId: string, cmd: string) => post(`/stick/${stickId}/command`, { cmd }),
};

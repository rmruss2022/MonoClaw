/**
 * openhome content-router client for the stick (and reusable by the phone).
 * Framework-agnostic: fetch for the REST API, a pluggable SSE for the control
 * channel. The stick listens for `launch`/`command` events and opens deep links.
 */
export interface Source { service: string; serviceName: string; offer: string; price?: number; quality?: string; contentId?: string }
export interface Title {
  id: string; type: "movie" | "show" | "music"; name: string; year?: number;
  overview?: string; poster?: string; backdrop?: string; rating?: number;
  genres?: string[]; runtimeMin?: number; cast?: string[]; sources: Source[];
}
export interface LaunchCommand {
  title: { id: string; name: string; poster?: string };
  service: string; deepLink: string; androidPackage: string; level: "title" | "search";
}

export class RouterClient {
  constructor(private baseUrl: string, private token?: string) {}
  setToken(t: string) { this.token = t; }

  private headers(json = false): Record<string, string> {
    const h: Record<string, string> = { Accept: "application/json" };
    if (json) h["Content-Type"] = "application/json";
    if (this.token) h["Authorization"] = `Bearer ${this.token}`;
    return h;
  }
  private async get<T>(path: string): Promise<T> {
    const r = await fetch(`${this.baseUrl}${path}`, { headers: this.headers() });
    if (!r.ok) throw new Error(`${r.status} ${path}`);
    return r.json();
  }
  private async post<T>(path: string, body: unknown): Promise<T> {
    const r = await fetch(`${this.baseUrl}${path}`, { method: "POST", headers: this.headers(true), body: JSON.stringify(body) });
    if (!r.ok) throw new Error(`${r.status} ${path}`);
    return r.json();
  }

  search(q: string, type?: string) {
    const p = new URLSearchParams({ q }); if (type) p.set("type", type);
    return this.get<{ results: Title[] }>(`/search?${p}`).then((r) => r.results);
  }
  trending(type?: string) {
    return this.get<{ results: Title[] }>(`/trending${type ? `?type=${type}` : ""}`).then((r) => r.results);
  }
  detail(id: string) {
    return this.get<{ title: Title }>(`/title/${encodeURIComponent(id)}`).then((r) => r.title);
  }
  beginPairing(stickId: string, name: string) {
    return this.post<{ code: string; expiresAt: number }>("/sticks/pair/begin", { stickId, name });
  }
  reportApps(stickId: string, installed: string[], owned: string[]) {
    return this.post(`/stick/${stickId}/apps`, { installed, owned });
  }
  route(titleId: string, stickId: string, prefer?: string[]) {
    return this.post<{ ok: boolean; route?: any; reason?: string; castTo?: string }>("/route", { titleId, stickId, prefer });
  }
  reportNowPlaying(stickId: string, np: unknown) {
    return this.post(`/stick/${stickId}/event`, np);
  }
  streamUrl(stickId: string) { return `${this.baseUrl}/stick/${stickId}/stream`; }
}

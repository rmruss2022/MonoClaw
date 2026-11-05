/**
 * Watchmode availability provider — "where can I watch this, and (on paid plans)
 * the exact deep link to open it."
 *
 * Two-step lookup: resolve our TMDB id → a Watchmode title id (cached), then fetch
 * that title's sources. `android_url` carries the title-level Android deep link —
 * but ONLY on Watchmode's paid plans; the free tier returns a placeholder string
 * there, which we detect and ignore (falling back to the per-service template).
 *
 * Because the free tier is ~1k calls/month and this is 2 calls per title, the
 * engine only calls Watchmode for a *selected* title (detail/route), not for every
 * search result. Activates with WATCHMODE_API_KEY.
 */
import type { AvailabilityProvider, Title, Source, OfferType } from "../types.ts";
import { serviceName, type ServiceId } from "../deeplinks.ts";

const KEY = process.env.WATCHMODE_API_KEY ?? "";
const BASE = "https://api.watchmode.com/v1";

const NAME_MAP: Record<string, ServiceId> = {
  "Netflix": "netflix", "Amazon Prime Video": "prime", "Amazon Video": "prime",
  "Disney+": "disney", "Max": "hbomax", "MAX": "hbomax", "HBO Max": "hbomax", "Hulu": "hulu",
  "Apple TV": "appletv", "Apple TV+": "appletv", "YouTube": "youtube",
  "Peacock": "peacock", "Peacock Premium": "peacock", "Paramount+": "paramount",
  "Tubi TV": "tubi", "Tubi": "tubi", "Spotify": "spotify", "Plex": "plex",
};
const OFFER_MAP: Record<string, OfferType> = { sub: "sub", free: "free", rent: "rent", buy: "buy", tve: "sub" };

// tmdb id → watchmode id (and null = not found) so we don't re-search.
const idCache = new Map<string, number | null>();

function usableDeepLink(u: unknown): string | undefined {
  if (typeof u !== "string") return undefined;
  // Free-tier placeholder: "Deeplinks available for paid plans only."
  if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(u) && !u.startsWith("intent:")) return undefined;
  return u;
}

async function watchmodeId(tmdbType: "movie" | "tv", tmdbId: string): Promise<number | null> {
  const key = `${tmdbType}:${tmdbId}`;
  if (idCache.has(key)) return idCache.get(key)!;
  const field = tmdbType === "movie" ? "tmdb_movie_id" : "tmdb_tv_id";
  try {
    const r = await fetch(`${BASE}/search/?apiKey=${KEY}&search_field=${field}&search_value=${tmdbId}`);
    if (!r.ok) { idCache.set(key, null); return null; }
    const j = await r.json();
    const id = j?.title_results?.[0]?.id ?? null;
    idCache.set(key, id);
    return id;
  } catch { idCache.set(key, null); return null; }
}

export const watchmodeAvailability: AvailabilityProvider = {
  id: "watchmode",
  ready: () => KEY.length > 0,
  async sourcesFor(title: Title, region: string): Promise<Source[]> {
    const [provider, type, providerId] = title.id.split(":");
    if (provider !== "tmdb" || type === "music") return [];
    const wid = await watchmodeId(type === "movie" ? "movie" : "tv", providerId);
    if (!wid) return [];
    let rows: any[];
    try {
      const r = await fetch(`${BASE}/title/${wid}/sources/?apiKey=${KEY}&regions=${(region || "US").toUpperCase()}`);
      if (!r.ok) return [];
      rows = await r.json();
    } catch { return []; }
    if (!Array.isArray(rows)) return [];

    const out: Source[] = [];
    for (const s of rows) {
      const svc = NAME_MAP[s.name];
      if (!svc) continue;
      const offer = OFFER_MAP[s.type] ?? "sub";
      const deepLink = usableDeepLink(s.android_url) ?? usableDeepLink(s.web_url);
      const quality = s.format === "4K" ? "4K" : s.format === "HD" ? "HD" : s.format === "SD" ? "SD" : undefined;
      const existing = out.find((x) => x.service === svc && x.offer === offer);
      if (existing) { if (!existing.deepLink && deepLink) existing.deepLink = deepLink; continue; }
      out.push({
        service: svc, serviceName: serviceName(svc), offer,
        price: typeof s.price === "number" ? s.price : undefined, quality, deepLink,
      });
    }
    return out;
  },
};

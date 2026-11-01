/**
 * Watchmode availability provider — the real "where can I watch this, and the
 * exact deep link to open it" integration. This is the piece that makes openhome
 * TV's universal search behave like a Fire TV's: for a given title it returns
 * every service that carries it (sub/free/rent/buy), the price, and — crucially —
 * the **android_url** deep link to open that app directly to the title.
 *
 * Activates when WATCHMODE_API_KEY is set. Resolves TMDB-based titles via
 * Watchmode's external-id lookup (tmdb_movie_/tmdb_tv_).
 */
import type { AvailabilityProvider, Title, Source, OfferType } from "../types.ts";
import { serviceName, type ServiceId } from "../deeplinks.ts";

const KEY = process.env.WATCHMODE_API_KEY ?? "";
const BASE = "https://api.watchmode.com/v1";

// Watchmode source display name → our ServiceId.
const NAME_MAP: Record<string, ServiceId> = {
  "Netflix": "netflix", "Amazon Prime Video": "prime", "Amazon Video": "prime",
  "Disney+": "disney", "Max": "hbomax", "HBO Max": "hbomax", "Hulu": "hulu",
  "Apple TV": "appletv", "Apple TV+": "appletv", "YouTube": "youtube",
  "Peacock": "peacock", "Peacock Premium": "peacock", "Paramount+": "paramount",
  "Tubi TV": "tubi", "Tubi": "tubi", "Spotify": "spotify", "Plex": "plex",
};

const OFFER_MAP: Record<string, OfferType> = { sub: "sub", free: "free", rent: "rent", buy: "buy", tve: "sub" };

export const watchmodeAvailability: AvailabilityProvider = {
  id: "watchmode",
  ready: () => KEY.length > 0,
  async sourcesFor(title: Title, region: string): Promise<Source[]> {
    const [provider, type, providerId] = title.id.split(":");
    if (provider !== "tmdb" || type === "music") return [];
    const wmId = type === "movie" ? `tmdb_movie_${providerId}` : `tmdb_tv_${providerId}`;
    const url = `${BASE}/title/${wmId}/sources/?apiKey=${KEY}&regions=${(region || "US").toUpperCase()}`;
    let rows: any[];
    try {
      const r = await fetch(url, { headers: { Accept: "application/json" } });
      if (!r.ok) return [];
      rows = await r.json();
    } catch { return []; }
    if (!Array.isArray(rows)) return [];

    const out: Source[] = [];
    for (const s of rows) {
      const svc = NAME_MAP[s.name];
      if (!svc) continue;
      const offer = OFFER_MAP[s.type] ?? "sub";
      const deepLink = s.android_url || s.web_url || undefined;
      const existing = out.find((x) => x.service === svc && x.offer === offer);
      const quality = s.format === "4K" ? "4K" : s.format === "HD" ? "HD" : s.format === "SD" ? "SD" : undefined;
      if (existing) {
        if (!existing.deepLink && deepLink) existing.deepLink = deepLink;
        continue;
      }
      out.push({
        service: svc, serviceName: serviceName(svc), offer,
        price: typeof s.price === "number" ? s.price : undefined,
        quality, deepLink,
      });
    }
    return out;
  },
};

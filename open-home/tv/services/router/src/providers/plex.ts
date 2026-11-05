/**
 * Plex — a real full integration for *your own* media. Searches your Plex server
 * and returns matches with a plex source + deep link. Because it's your server,
 * this is true search + play (no walled garden). Activates with PLEX_URL +
 * PLEX_TOKEN. (Per-account server config is P2; env config is single-tenant dev.)
 */
import type { SearchContributor, Title, SearchQuery, MediaType } from "../types.ts";
import { serviceName, SERVICES } from "../deeplinks.ts";

const URL_ = (process.env.PLEX_URL ?? "").replace(/\/+$/, "");
const TOKEN = process.env.PLEX_TOKEN ?? "";

function mapType(plexType: string): MediaType {
  return plexType === "show" ? "show" : "movie";
}

export const plex: SearchContributor = {
  id: "plex",
  ready: () => URL_.length > 0 && TOKEN.length > 0,
  async search(q: SearchQuery): Promise<Title[]> {
    if (q.type === "music") return [];
    const u = `${URL_}/hubs/search?query=${encodeURIComponent(q.q)}&limit=12`;
    let data: any;
    try {
      const r = await fetch(u, { headers: { Accept: "application/json", "X-Plex-Token": TOKEN } });
      if (!r.ok) return [];
      data = await r.json();
    } catch { return []; }
    const hubs = data?.MediaContainer?.Hub ?? [];
    const out: Title[] = [];
    for (const hub of hubs) {
      for (const m of hub.Metadata ?? []) {
        if (m.type !== "movie" && m.type !== "show") continue;
        const type = mapType(m.type);
        out.push({
          id: `plex:${type}:${m.ratingKey}`,
          type,
          name: m.title,
          year: m.year,
          overview: m.summary,
          poster: m.thumb ? `${URL_}${m.thumb}?X-Plex-Token=${TOKEN}` : undefined,
          rating: typeof m.rating === "number" ? m.rating : undefined,
          sources: [{
            service: "plex", serviceName: serviceName("plex"), offer: "free",
            contentId: m.ratingKey, deepLink: SERVICES.plex.title!(m.ratingKey),
          }],
        });
      }
    }
    return out;
  },
};

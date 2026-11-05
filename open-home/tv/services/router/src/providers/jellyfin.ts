/**
 * Jellyfin — real full integration for your own open-source media server. Activates
 * with JELLYFIN_URL + JELLYFIN_TOKEN (+ JELLYFIN_USER). Like Plex, it's your media,
 * so it's true search + play. (Per-account config is P2.)
 */
import type { SearchContributor, Title, SearchQuery } from "../types.ts";
import { serviceName, SERVICES } from "../deeplinks.ts";

const URL_ = (process.env.JELLYFIN_URL ?? "").replace(/\/+$/, "");
const TOKEN = process.env.JELLYFIN_TOKEN ?? "";
const USER = process.env.JELLYFIN_USER ?? "";

export const jellyfin: SearchContributor = {
  id: "jellyfin",
  ready: () => URL_.length > 0 && TOKEN.length > 0 && USER.length > 0,
  async search(q: SearchQuery): Promise<Title[]> {
    if (q.type === "music") return [];
    const u = new URL(`${URL_}/Users/${USER}/Items`);
    u.searchParams.set("searchTerm", q.q);
    u.searchParams.set("IncludeItemTypes", "Movie,Series");
    u.searchParams.set("Recursive", "true");
    u.searchParams.set("Limit", "12");
    u.searchParams.set("Fields", "Overview,ProductionYear");
    let data: any;
    try {
      const r = await fetch(u, { headers: { Accept: "application/json", "X-Emby-Token": TOKEN } });
      if (!r.ok) return [];
      data = await r.json();
    } catch { return []; }
    return (data.Items ?? []).map((it: any): Title => {
      const type = it.Type === "Series" ? "show" : "movie";
      const img = it.ImageTags?.Primary ? `${URL_}/Items/${it.Id}/Images/Primary?tag=${it.ImageTags.Primary}` : undefined;
      return {
        id: `jellyfin:${type}:${it.Id}`,
        type,
        name: it.Name,
        year: it.ProductionYear,
        overview: it.Overview,
        poster: img,
        sources: [{
          service: "jellyfin", serviceName: serviceName("jellyfin"), offer: "free",
          contentId: it.Id, deepLink: SERVICES.jellyfin.search(it.Name),
        }],
      };
    });
  },
};

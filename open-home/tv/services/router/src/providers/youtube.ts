/**
 * YouTube — a real full-API integration. Searches via the YouTube Data API and
 * returns videos as titles with a youtube source + exact deep link (the stick
 * opens the YouTube app to the video). Activates with YOUTUBE_API_KEY.
 */
import type { SearchContributor, Title, SearchQuery } from "../types.ts";
import { serviceName, SERVICES } from "../deeplinks.ts";

const KEY = process.env.YOUTUBE_API_KEY ?? "";
const BASE = "https://www.googleapis.com/youtube/v3";

export const youtube: SearchContributor = {
  id: "youtube",
  ready: () => KEY.length > 0,
  async search(q: SearchQuery): Promise<Title[]> {
    if (q.type && q.type !== "show" && q.type !== "music") return [];
    const u = new URL(`${BASE}/search`);
    u.searchParams.set("key", KEY);
    u.searchParams.set("part", "snippet");
    u.searchParams.set("type", "video");
    u.searchParams.set("maxResults", "8");
    u.searchParams.set("q", q.q);
    let data: any;
    try {
      const r = await fetch(u, { headers: { Accept: "application/json" } });
      if (!r.ok) return [];
      data = await r.json();
    } catch { return []; }
    return (data.items ?? []).map((it: any): Title => {
      const vid = it.id.videoId;
      return {
        id: `youtube:show:${vid}`,
        type: "show",
        name: it.snippet.title,
        overview: it.snippet.description,
        poster: it.snippet.thumbnails?.high?.url || it.snippet.thumbnails?.default?.url,
        year: it.snippet.publishedAt ? Number(it.snippet.publishedAt.slice(0, 4)) : undefined,
        sources: [{
          service: "youtube", serviceName: serviceName("youtube"), offer: "free",
          contentId: vid, deepLink: SERVICES.youtube.title!(vid),
        }],
      };
    });
  },
};

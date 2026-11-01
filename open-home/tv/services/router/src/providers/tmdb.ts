/**
 * TMDB metadata + availability provider. Activates when TMDB_API_KEY is set.
 *
 * Metadata (titles, posters, cast, ratings) is TMDB's core. For availability we
 * use TMDB's /watch/providers (powered by JustWatch), which tells us *which*
 * services carry a title per region — but not title-level deep links, so these
 * resolve to app-search deep links. A Watchmode provider (P2) adds title-level
 * links on top.
 */
import type { MetadataProvider, AvailabilityProvider, Title, SearchQuery, MediaType, Source } from "../types.ts";
import { serviceName, type ServiceId } from "../deeplinks.ts";

const KEY = process.env.TMDB_API_KEY ?? "";
const BASE = "https://api.themoviedb.org/3";
const IMG = "https://image.tmdb.org/t/p/w500";

// TMDB provider display name → our ServiceId.
const PROVIDER_MAP: Record<string, ServiceId> = {
  "Netflix": "netflix", "Amazon Prime Video": "prime", "Amazon Video": "prime",
  "Disney Plus": "disney", "Max": "hbomax", "HBO Max": "hbomax", "Hulu": "hulu",
  "Apple TV": "appletv", "Apple TV Plus": "appletv", "YouTube": "youtube",
  "Peacock": "peacock", "Peacock Premium": "peacock", "Paramount Plus": "paramount",
  "Tubi": "tubi", "Spotify": "spotify",
};

async function tmdb(path: string, params: Record<string, string> = {}): Promise<any> {
  const u = new URL(BASE + path);
  u.searchParams.set("api_key", KEY);
  for (const [k, v] of Object.entries(params)) u.searchParams.set(k, v);
  const r = await fetch(u, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error(`tmdb ${r.status} ${path}`);
  return r.json();
}

function toType(mediaType: string): MediaType | null {
  if (mediaType === "movie") return "movie";
  if (mediaType === "tv") return "show";
  return null;
}

function mapTitle(row: any, type: MediaType): Title {
  const date = row.release_date || row.first_air_date || "";
  return {
    id: `tmdb:${type}:${row.id}`,
    type,
    name: row.title || row.name,
    year: date ? Number(date.slice(0, 4)) : undefined,
    overview: row.overview || undefined,
    poster: row.poster_path ? IMG + row.poster_path : undefined,
    backdrop: row.backdrop_path ? IMG + row.backdrop_path : undefined,
    rating: typeof row.vote_average === "number" ? Math.round(row.vote_average * 10) / 10 : undefined,
    genres: Array.isArray(row.genres) ? row.genres.map((g: any) => g.name) : undefined,
    runtimeMin: row.runtime || (Array.isArray(row.episode_run_time) ? row.episode_run_time[0] : undefined),
    cast: row.credits?.cast ? row.credits.cast.slice(0, 6).map((c: any) => c.name) : undefined,
    sources: [],
  };
}

export const tmdbMetadata: MetadataProvider = {
  id: "tmdb",
  ready: () => KEY.length > 0,
  async search(q: SearchQuery) {
    const data = await tmdb("/search/multi", { query: q.q, include_adult: "false" });
    const out: Title[] = [];
    for (const row of data.results ?? []) {
      const type = toType(row.media_type);
      if (!type) continue;
      if (q.type && type !== q.type) continue;
      out.push(mapTitle(row, type));
    }
    return out;
  },
  async detail(providerId: string, type: MediaType) {
    const path = type === "movie" ? `/movie/${providerId}` : `/tv/${providerId}`;
    const row = await tmdb(path, { append_to_response: "credits" });
    return mapTitle(row, type);
  },
  async trending(type?: MediaType) {
    const scope = type === "movie" ? "movie" : type === "show" ? "tv" : "all";
    const data = await tmdb(`/trending/${scope}/week`);
    const out: Title[] = [];
    for (const row of data.results ?? []) {
      const t = toType(row.media_type) ?? (type ?? null);
      if (!t) continue;
      out.push(mapTitle(row, t));
    }
    return out;
  },
};

export const tmdbAvailability: AvailabilityProvider = {
  id: "tmdb",
  ready: () => KEY.length > 0,
  async sourcesFor(title: Title, region: string) {
    const [, type, providerId] = title.id.split(":");
    if (type === "music") return [];
    const path = type === "movie" ? `/movie/${providerId}/watch/providers` : `/tv/${providerId}/watch/providers`;
    let data: any;
    try { data = await tmdb(path); } catch { return []; }
    const r = data.results?.[region.toUpperCase()] ?? data.results?.US;
    if (!r) return [];
    const out: Source[] = [];
    const add = (list: any[], offer: Source["offer"]) => {
      for (const p of list ?? []) {
        const svc = PROVIDER_MAP[p.provider_name];
        if (svc && !out.find((s) => s.service === svc)) {
          out.push({ service: svc, serviceName: serviceName(svc), offer });
        }
      }
    };
    add(r.flatrate, "sub");
    add(r.free, "free");
    add(r.rent, "rent");
    add(r.buy, "buy");
    return out;
  },
};

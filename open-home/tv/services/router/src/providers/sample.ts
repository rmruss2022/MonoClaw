/**
 * Zero-key sample provider — a small real dataset so the router runs, demos, and
 * is testable with no API keys. Swapped for TMDB + Watchmode in production (they
 * take over automatically when their keys are set).
 */
import type { MetadataProvider, AvailabilityProvider, Title, SearchQuery, MediaType, Source } from "../types.ts";
import { serviceName } from "../deeplinks.ts";

function src(service: any, offer: any, extra: Partial<Source> = {}): Source {
  return { service, serviceName: serviceName(service), offer, quality: "4K", ...extra };
}

const CATALOG: Title[] = [
  {
    id: "sample:movie:dune2", type: "movie", name: "Dune: Part Two", year: 2024,
    overview: "Paul Atreides unites with the Fremen to wage war against House Harkonnen.",
    rating: 8.2, genres: ["Sci-Fi", "Adventure"], runtimeMin: 166, cast: ["Timothée Chalamet", "Zendaya"],
    poster: "https://image.tmdb.org/t/p/w500/8b8R8l88Qje9dn9OE8PY05Nxl1X.jpg",
    sources: [src("hbomax", "sub"), src("prime", "rent", { price: 5.99, contentId: "dune-part-two" }), src("appletv", "buy", { price: 19.99 })],
  },
  {
    id: "sample:show:thebear", type: "show", name: "The Bear", year: 2022,
    overview: "A young chef returns to Chicago to run his family's sandwich shop.",
    rating: 8.6, genres: ["Drama", "Comedy"], cast: ["Jeremy Allen White"],
    poster: "https://image.tmdb.org/t/p/w500/zPyNaOi5JTl4Sr8Dd8iJURWsGLj.jpg",
    sources: [src("hulu", "sub", { contentId: "the-bear" }), src("disney", "sub")],
  },
  {
    id: "sample:movie:oppenheimer", type: "movie", name: "Oppenheimer", year: 2023,
    overview: "The story of J. Robert Oppenheimer and the creation of the atomic bomb.",
    rating: 8.1, genres: ["Drama", "History"], runtimeMin: 180, cast: ["Cillian Murphy"],
    poster: "https://image.tmdb.org/t/p/w500/8Gxv8gSFCU0XGDykEGv7zR1n2ua.jpg",
    sources: [src("peacock", "sub"), src("prime", "rent", { price: 4.99 }), src("appletv", "buy", { price: 14.99 })],
  },
  {
    id: "sample:show:severance", type: "show", name: "Severance", year: 2022,
    overview: "Employees surgically divide their work and personal memories.",
    rating: 8.7, genres: ["Sci-Fi", "Thriller"], cast: ["Adam Scott"],
    poster: "https://image.tmdb.org/t/p/w500/lFf6LLrQjYldcZItzOkGmMMigP7.jpg",
    sources: [src("appletv", "sub", { contentId: "severance" })],
  },
  {
    id: "sample:movie:spiderverse", type: "movie", name: "Spider-Man: Across the Spider-Verse", year: 2023,
    overview: "Miles Morales traverses the multiverse with a team of Spider-People.",
    rating: 8.3, genres: ["Animation", "Action"], runtimeMin: 140,
    poster: "https://image.tmdb.org/t/p/w500/8Vt6mWEReuy4Of61Lnj5Xj704m8.jpg",
    sources: [src("netflix", "sub", { contentId: "81674364" }), src("prime", "rent", { price: 3.99 })],
  },
  {
    id: "sample:music:blondshell", type: "music", name: "Blondshell — If You Asked for a Picture", year: 2025,
    overview: "Sophomore album from the LA alt-rock songwriter.",
    rating: 7.9, genres: ["Alt-Rock"],
    poster: "https://image.tmdb.org/t/p/w500/placeholder.jpg",
    sources: [src("spotify", "sub", { contentId: "album:5xyz", quality: undefined })],
  },
];

function matches(t: Title, q: SearchQuery): boolean {
  if (q.type && t.type !== q.type) return false;
  const hay = `${t.name} ${t.overview ?? ""} ${(t.genres ?? []).join(" ")} ${(t.cast ?? []).join(" ")}`.toLowerCase();
  return q.q.trim().length === 0 || hay.includes(q.q.toLowerCase());
}

export const sampleMetadata: MetadataProvider = {
  id: "sample",
  ready: () => true,
  async search(q) {
    return CATALOG.filter((t) => matches(t, q));
  },
  async detail(providerId, type) {
    return CATALOG.find((t) => t.id === `sample:${type}:${providerId}` || t.id.endsWith(`:${providerId}`)) ?? null;
  },
  async trending(type?: MediaType) {
    return CATALOG.filter((t) => !type || t.type === type);
  },
};

/** The sample dataset already carries sources, so availability is a pass-through. */
export const sampleAvailability: AvailabilityProvider = {
  id: "sample",
  ready: () => true,
  async sourcesFor(title) {
    return title.sources ?? [];
  },
};

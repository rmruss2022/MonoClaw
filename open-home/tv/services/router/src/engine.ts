/**
 * The engine: pick active providers, run unified search, enrich with availability,
 * rank results, and run the routing algorithm that chooses ONE source + deep link
 * to launch on a stick.
 */
import type { MetadataProvider, AvailabilityProvider, Title, SearchQuery, MediaType, Source } from "./types.ts";
import { sampleMetadata, sampleAvailability } from "./providers/sample.ts";
import { tmdbMetadata, tmdbAvailability } from "./providers/tmdb.ts";
import { watchmodeAvailability } from "./providers/watchmode.ts";
import { youtube } from "./providers/youtube.ts";
import { plex } from "./providers/plex.ts";
import { jellyfin } from "./providers/jellyfin.ts";
import type { SearchContributor } from "./types.ts";
import { resolveDeepLink, SERVICES, type ServiceId } from "./deeplinks.ts";

// Full-API services that contribute their own titles (real search + play).
const CONTRIBUTORS: SearchContributor[] = [plex, jellyfin, youtube];
function activeContributors(): SearchContributor[] {
  return CONTRIBUTORS.filter((c) => c.ready());
}

function metadataProvider(): MetadataProvider {
  return tmdbMetadata.ready() ? tmdbMetadata : sampleMetadata;
}
// Cheap availability for search-result lists (TMDB is generous; Watchmode's free
// tier is ~1k/mo so we don't hit it 20× per search).
function searchAvailability(): AvailabilityProvider {
  return tmdbAvailability.ready() ? tmdbAvailability : sampleAvailability;
}
// Richest availability for a *selected* title (detail/route) — Watchmode first.
function detailAvailability(): AvailabilityProvider {
  if (watchmodeAvailability.ready()) return watchmodeAvailability;
  if (tmdbAvailability.ready()) return tmdbAvailability;
  return sampleAvailability;
}

export function providerStatus() {
  return {
    metadata: metadataProvider().id,
    searchAvailability: searchAvailability().id,
    detailAvailability: detailAvailability().id,
    deepLinks: watchmodeAvailability.ready() ? "title-level when offered (watchmode)" : "service-level",
    contributors: activeContributors().map((c) => c.id),
    live: tmdbMetadata.ready(),
  };
}

function mergeSources(a: Source[], b: Source[]): Source[] {
  const out = [...a];
  for (const s of b) {
    const existing = out.find((x) => x.service === s.service);
    if (!existing) out.push(s);
    else {
      if (!existing.contentId && s.contentId) existing.contentId = s.contentId;
      if (!existing.deepLink && s.deepLink) existing.deepLink = s.deepLink; // prefer exact links
    }
  }
  return out;
}

async function enrich(title: Title, region: string, deep = false): Promise<Title> {
  try {
    const provider = deep ? detailAvailability() : searchAvailability();
    const extra = await provider.sourcesFor(title, region);
    return { ...title, sources: mergeSources(title.sources ?? [], extra) };
  } catch {
    return title;
  }
}

function rank(titles: Title[], q: string): Title[] {
  const ql = q.toLowerCase();
  return titles
    .map((t) => {
      const name = t.name.toLowerCase();
      let score = (t.rating ?? 0) * 2;
      if (name === ql) score += 100;
      else if (name.startsWith(ql)) score += 50;
      else if (name.includes(ql)) score += 20;
      score += (t.sources?.length ?? 0); // more ways to watch = more useful
      return { t, score };
    })
    .sort((a, b) => b.score - a.score)
    .map((x) => x.t);
}

// Bounded cache of titles we've shown, so /route can resolve any title id —
// including contributor titles (YouTube/Plex/Jellyfin) that have no detail fetch.
const titleCache = new Map<string, Title>();
function remember(titles: Title[]) {
  for (const t of titles) {
    titleCache.set(t.id, t);
    if (titleCache.size > 2000) titleCache.delete(titleCache.keys().next().value);
  }
}

export async function search(q: SearchQuery): Promise<Title[]> {
  const region = q.region || "US";
  // Primary metadata (TMDB/sample) enriched with availability, plus every active
  // full-API contributor (Plex/Jellyfin/YouTube) that carries its own sources.
  const [base, ...contribLists] = await Promise.all([
    metadataProvider().search(q),
    ...activeContributors().map((c) => c.search(q).catch(() => [])),
  ]);
  const enriched = await Promise.all(base.slice(0, 20).map((t) => enrich(t, region)));
  const all = rank([...enriched, ...contribLists.flat()], q.q);
  remember(all);
  return all;
}

export async function detail(id: string, region = "US"): Promise<Title | null> {
  const cached = titleCache.get(id);
  const [provider, type, providerId] = id.split(":") as [string, MediaType, string];
  // Contributor titles (YouTube/Plex/Jellyfin) carry their own sources; cache-only.
  if (provider !== "tmdb" && provider !== "sample") return cached ?? null;
  const base = cached ?? (await metadataProvider().detail(providerId, type));
  if (!base) return null;
  // Deep enrichment (Watchmode) only now, for the one selected title.
  return enrich(base, region, true);
}

export async function trending(type?: MediaType, region = "US"): Promise<Title[]> {
  const base = await metadataProvider().trending(type);
  const all = await Promise.all(base.slice(0, 20).map((t) => enrich(t, region)));
  remember(all);
  return all;
}

// ----- Routing algorithm --------------------------------------------------
export interface RouteContext {
  ownedServices?: ServiceId[];   // subscriptions the user pays for
  installedApps?: ServiceId[];   // apps actually installed on the stick
  prefer?: ServiceId[];          // user preference order (e.g. personal media first)
}
export interface RouteResult {
  ok: boolean;
  reason?: string;
  service?: ServiceId;
  offer?: Source["offer"];
  deepLink?: string;
  level?: "title" | "search";
  androidPackage?: string;
}

const OFFER_RANK: Record<Source["offer"], number> = { sub: 0, free: 1, rent: 2, buy: 3 };

export function chooseSource(title: Title, ctx: RouteContext = {}): RouteResult {
  const installed = ctx.installedApps;
  const owned = new Set(ctx.ownedServices ?? []);
  let candidates = (title.sources ?? []).slice();
  if (installed && installed.length) candidates = candidates.filter((s) => installed.includes(s.service));
  if (!candidates.length) {
    return { ok: false, reason: installed?.length ? "No installed app carries this title." : "No source found." };
  }
  const prefIndex = (s: ServiceId) => {
    const i = (ctx.prefer ?? []).indexOf(s);
    return i === -1 ? 999 : i;
  };
  candidates.sort((a, b) => {
    // 1) something you already pay for (sub you own) wins
    const aOwned = a.offer === "sub" && owned.has(a.service) ? 0 : 1;
    const bOwned = b.offer === "sub" && owned.has(b.service) ? 0 : 1;
    if (aOwned !== bOwned) return aOwned - bOwned;
    // 2) cheaper offer type (sub < free < rent < buy)
    if (OFFER_RANK[a.offer] !== OFFER_RANK[b.offer]) return OFFER_RANK[a.offer] - OFFER_RANK[b.offer];
    // 3) cheaper price
    if ((a.price ?? 0) !== (b.price ?? 0)) return (a.price ?? 0) - (b.price ?? 0);
    // 4) title-level deep link beats search
    const aTitle = a.contentId ? 0 : 1, bTitle = b.contentId ? 0 : 1;
    if (aTitle !== bTitle) return aTitle - bTitle;
    // 5) user preference order
    return prefIndex(a.service) - prefIndex(b.service);
  });
  const best = candidates[0];
  // Prefer an exact provider-supplied deep link (Watchmode/Plex/Jellyfin); else
  // fall back to our per-service template (title-level if we have a contentId).
  if (best.deepLink) {
    return {
      ok: true, service: best.service, offer: best.offer,
      deepLink: best.deepLink, level: "title", androidPackage: SERVICES[best.service].androidPackage,
    };
  }
  const link = resolveDeepLink(best.service, { contentId: best.contentId, query: title.name });
  return {
    ok: true,
    service: best.service,
    offer: best.offer,
    deepLink: link.uri,
    level: link.level,
    androidPackage: link.androidPackage,
  };
}

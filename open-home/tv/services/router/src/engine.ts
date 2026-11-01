/**
 * The engine: pick active providers, run unified search, enrich with availability,
 * rank results, and run the routing algorithm that chooses ONE source + deep link
 * to launch on a stick.
 */
import type { MetadataProvider, AvailabilityProvider, Title, SearchQuery, MediaType, Source } from "./types.ts";
import { sampleMetadata, sampleAvailability } from "./providers/sample.ts";
import { tmdbMetadata, tmdbAvailability } from "./providers/tmdb.ts";
import { resolveDeepLink, type ServiceId } from "./deeplinks.ts";

function metadataProvider(): MetadataProvider {
  return tmdbMetadata.ready() ? tmdbMetadata : sampleMetadata;
}
function availabilityProvider(): AvailabilityProvider {
  return tmdbAvailability.ready() ? tmdbAvailability : sampleAvailability;
}

export function providerStatus() {
  return {
    metadata: metadataProvider().id,
    availability: availabilityProvider().id,
    live: tmdbMetadata.ready(),
  };
}

function mergeSources(a: Source[], b: Source[]): Source[] {
  const out = [...a];
  for (const s of b) {
    const existing = out.find((x) => x.service === s.service);
    if (!existing) out.push(s);
    else if (!existing.contentId && s.contentId) existing.contentId = s.contentId;
  }
  return out;
}

async function enrich(title: Title, region: string): Promise<Title> {
  try {
    const extra = await availabilityProvider().sourcesFor(title, region);
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

export async function search(q: SearchQuery): Promise<Title[]> {
  const region = q.region || "US";
  const base = await metadataProvider().search(q);
  const enriched = await Promise.all(base.slice(0, 20).map((t) => enrich(t, region)));
  return rank(enriched, q.q);
}

export async function detail(id: string, region = "US"): Promise<Title | null> {
  const [, type, providerId] = id.split(":") as [string, MediaType, string];
  const t = await metadataProvider().detail(providerId, type);
  if (!t) return null;
  return enrich(t, region);
}

export async function trending(type?: MediaType, region = "US"): Promise<Title[]> {
  const base = await metadataProvider().trending(type);
  return Promise.all(base.slice(0, 20).map((t) => enrich(t, region)));
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

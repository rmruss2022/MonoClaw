import type { ServiceId } from "./deeplinks.ts";

export type MediaType = "movie" | "show" | "music";
export type OfferType = "sub" | "free" | "rent" | "buy";

/** A place you can watch/listen to a title, resolved to a launchable deep link. */
export interface Source {
  service: ServiceId;
  serviceName: string;
  offer: OfferType;
  price?: number; // for rent/buy, in USD
  quality?: "SD" | "HD" | "4K";
  contentId?: string; // the service's own id, enables a title-level deep link
  deepLink?: string;  // an exact, provider-supplied launch URL (Watchmode android_url, Plex, …)
                      // — overrides the templated deep link when present.
}

/** A unified, provider-agnostic title. */
export interface Title {
  id: string; // our id: `${provider}:${type}:${providerId}`
  type: MediaType;
  name: string;
  year?: number;
  overview?: string;
  poster?: string;
  backdrop?: string;
  rating?: number; // 0–10
  genres?: string[];
  runtimeMin?: number;
  cast?: string[];
  sources: Source[];
}

export interface SearchQuery {
  q: string;
  type?: MediaType;
  region?: string;
}

export interface MetadataProvider {
  id: string;
  ready(): boolean;
  search(q: SearchQuery): Promise<Title[]>;
  detail(providerId: string, type: MediaType): Promise<Title | null>;
  trending(type?: MediaType): Promise<Title[]>;
}

export interface AvailabilityProvider {
  id: string;
  ready(): boolean;
  /** Return where a title can be watched, given a provider title + region. */
  sourcesFor(title: Title, region: string): Promise<Source[]>;
}

/**
 * A full-API service that contributes its OWN titles (already carrying a source
 * + deep link), e.g. YouTube, Plex, Jellyfin — the services that expose real
 * search/play APIs. Merged into unified search alongside the metadata provider.
 */
export interface SearchContributor {
  id: string;
  ready(): boolean;
  search(q: SearchQuery): Promise<Title[]>;
  trending?(type?: MediaType): Promise<Title[]>;
}

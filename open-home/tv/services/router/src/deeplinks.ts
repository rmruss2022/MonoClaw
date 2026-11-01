/**
 * Streaming-app registry — the part that makes "launch to the exact title" real.
 *
 * Each service has:
 *  - androidPackage: the Android TV package id (for intent launch + install check)
 *  - title(id): a deep link that opens the app to a specific title, when the
 *    service supports it (id is that service's own content id)
 *  - search(q):  a fallback deep link that opens the app's search for a query
 *
 * The content-router never streams anything; it resolves intent → a URI the
 * stick fires as an Android deep-link intent.
 */
export type ServiceId =
  | "netflix" | "prime" | "disney" | "hbomax" | "hulu" | "appletv"
  | "youtube" | "peacock" | "paramount" | "tubi" | "plex" | "jellyfin" | "spotify";

export interface ServiceDef {
  id: ServiceId;
  name: string;
  androidPackage: string;
  color: string;
  title?: (contentId: string) => string;
  search: (query: string) => string;
  kind: "video" | "music" | "personal";
}

const enc = encodeURIComponent;

export const SERVICES: Record<ServiceId, ServiceDef> = {
  netflix: {
    id: "netflix", name: "Netflix", androidPackage: "com.netflix.ninja", color: "#E50914", kind: "video",
    title: (id) => `nflx://www.netflix.com/title/${id}`,
    search: (q) => `nflx://www.netflix.com/search?q=${enc(q)}`,
  },
  prime: {
    id: "prime", name: "Prime Video", androidPackage: "com.amazon.avod.thirdpartyclient", color: "#00A8E1", kind: "video",
    title: (id) => `https://app.primevideo.com/detail?gti=${id}`,
    search: (q) => `https://app.primevideo.com/search?phrase=${enc(q)}`,
  },
  disney: {
    id: "disney", name: "Disney+", androidPackage: "com.disney.disneyplus", color: "#113CCF", kind: "video",
    title: (id) => `https://www.disneyplus.com/video/${id}`,
    search: (q) => `https://www.disneyplus.com/search?q=${enc(q)}`,
  },
  hbomax: {
    id: "hbomax", name: "Max", androidPackage: "com.wbd.stream", color: "#0046FF", kind: "video",
    title: (id) => `https://play.max.com/video/watch/${id}`,
    search: (q) => `https://play.max.com/search?q=${enc(q)}`,
  },
  hulu: {
    id: "hulu", name: "Hulu", androidPackage: "com.hulu.plus", color: "#1CE783", kind: "video",
    title: (id) => `hulu://watch/${id}`,
    search: (q) => `hulu://search?q=${enc(q)}`,
  },
  appletv: {
    id: "appletv", name: "Apple TV", androidPackage: "com.apple.atve.androidtv.appletv", color: "#FFFFFF", kind: "video",
    title: (id) => `https://tv.apple.com/show/${id}`,
    search: (q) => `https://tv.apple.com/search?term=${enc(q)}`,
  },
  youtube: {
    id: "youtube", name: "YouTube", androidPackage: "com.google.android.youtube.tv", color: "#FF0000", kind: "video",
    title: (id) => `https://www.youtube.com/watch?v=${id}`,
    search: (q) => `https://www.youtube.com/results?search_query=${enc(q)}`,
  },
  peacock: {
    id: "peacock", name: "Peacock", androidPackage: "com.peacocktv.peacockandroid", color: "#000000", kind: "video",
    search: (q) => `https://www.peacocktv.com/search?q=${enc(q)}`,
  },
  paramount: {
    id: "paramount", name: "Paramount+", androidPackage: "com.cbs.ott", color: "#0064FF", kind: "video",
    search: (q) => `https://www.paramountplus.com/search/?query=${enc(q)}`,
  },
  tubi: {
    id: "tubi", name: "Tubi", androidPackage: "com.tubitv", color: "#FA382F", kind: "video",
    title: (id) => `tubitv://media/${id}`,
    search: (q) => `tubitv://search/${enc(q)}`,
  },
  plex: {
    id: "plex", name: "Plex", androidPackage: "com.plexapp.android", color: "#E5A00D", kind: "personal",
    title: (id) => `plex://preplay/?key=${enc(id)}`,
    search: (q) => `plex://search?query=${enc(q)}`,
  },
  jellyfin: {
    id: "jellyfin", name: "Jellyfin", androidPackage: "org.jellyfin.androidtv", color: "#00A4DC", kind: "personal",
    search: (q) => `jellyfin://search?q=${enc(q)}`,
  },
  spotify: {
    id: "spotify", name: "Spotify", androidPackage: "com.spotify.tv.android", color: "#1DB954", kind: "music",
    title: (id) => `spotify:${id}`,
    search: (q) => `spotify:search:${enc(q)}`,
  },
};

/** Build the best deep link for a service: title-level if we have an id, else search. */
export function resolveDeepLink(service: ServiceId, opts: { contentId?: string; query: string }): {
  uri: string;
  level: "title" | "search";
  androidPackage: string;
} {
  const def = SERVICES[service];
  if (opts.contentId && def.title) {
    return { uri: def.title(opts.contentId), level: "title", androidPackage: def.androidPackage };
  }
  return { uri: def.search(opts.query), level: "search", androidPackage: def.androidPackage };
}

export function serviceName(id: ServiceId): string {
  return SERVICES[id]?.name ?? id;
}

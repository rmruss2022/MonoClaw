/**
 * Music curator agent — generates a handful of "what to play right now" picks.
 *
 * Uses Gemini to propose 4 varied listening options (seeded by the user's Spotify
 * top tracks + optional mood), then resolves each to real, playable tracks via
 * Spotify search (playlist-track reads are restricted, but search is not). Each pick
 * comes back with track URIs you can fire straight into playback — ideal for a
 * 4-option remote gesture.
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import * as spotify from "./spotify.ts";

const MODEL = "gemini-flash-latest";
function key(): string {
  try { return process.env.GEMINI_API_KEY || readFileSync(`${homedir()}/.gemini/imagekey`, "utf8").trim(); } catch { return ""; }
}
export function enabled(): boolean { return !!key(); }

// ---- Persistent cache: keep generated mixes and only refresh every few hours ----
const DATA_DIR = new URL("../.data/", import.meta.url);
const CACHE_FILE = new URL("../.data/curator-cache.json", import.meta.url);
const TTL_MS = 6 * 60 * 60 * 1000; // regenerate at most every 6 hours
type CacheEntry = { at: number; picks: any[] };
function loadCache(): Record<string, CacheEntry> {
  try { return JSON.parse(readFileSync(CACHE_FILE, "utf8")); } catch { return {}; }
}
function saveCache(c: Record<string, CacheEntry>) {
  try { mkdirSync(DATA_DIR, { recursive: true }); writeFileSync(CACHE_FILE, JSON.stringify(c)); } catch (e) { console.log("[curator] cache save:", (e as Error).message); }
}

interface Pick { label: string; vibe: string; query: string; }

function fallback(): Pick[] {
  return [
    { label: "Focus Flow", vibe: "calm instrumentals to lock in", query: "focus instrumental beats" },
    { label: "Golden Hour", vibe: "warm mellow indie", query: "chill sunset indie" },
    { label: "Kitchen Dance", vibe: "upbeat feel-good", query: "feel good pop dance hits" },
    { label: "Late Night", vibe: "moody after-hours", query: "late night r&b lofi" },
  ];
}

async function propose(mood: string): Promise<Pick[]> {
  const k = key();
  let seed = "";
  try { if (spotify.connected()) { const top = await spotify.topTracks(); seed = top.slice(0, 12).map((t: any) => `${t.title} — ${t.artist}`).join("; "); } } catch {}
  if (!k) return fallback();
  const prompt = `You are openhome's music curator. Suggest exactly 4 distinct listening options ${mood ? `for this vibe: "${mood}"` : "for right now"}.
${seed ? `The listener's recent favourites: ${seed}` : ""}
Make the 4 genuinely varied (different energy/genre). Return ONLY JSON:
{"picks":[{"label":"<3-5 word name>","vibe":"<one short line why>","query":"<a Spotify search query that finds this vibe>"}]}`;
  try {
    const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent`, {
      method: "POST", headers: { "x-goog-api-key": k, "Content-Type": "application/json" },
      body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }], generationConfig: { responseMimeType: "application/json", temperature: 1.0 } }),
    });
    const j: any = await r.json();
    const txt = j?.candidates?.[0]?.content?.parts?.map((p: any) => p.text).join("") || "{}";
    const picks = (JSON.parse(txt).picks || []).filter((p: any) => p.label && p.query).slice(0, 4);
    return picks.length ? picks : fallback();
  } catch (e) { console.log("[curator]", (e as Error).message); return fallback(); }
}

async function generate(mood: string) {
  const picks = await propose(mood);
  const out = [];
  for (const p of picks) {
    let tracks: any[] = [];
    try { if (spotify.connected()) tracks = (await spotify.search(p.query, 25)).slice(0, 25); } catch {}
    out.push({
      label: p.label, vibe: p.vibe, query: p.query,
      image: tracks[0]?.image || "", count: tracks.length,
      uris: tracks.map((t) => t.uri).filter(Boolean),
      sample: tracks.slice(0, 3).map((t) => `${t.title} — ${t.artist}`),
    });
  }
  return out;
}

/** Return curated mixes. Cached on disk per mood; regenerated only every ~6h
 *  (or immediately when `force` is set, e.g. the user hits Refresh). */
export async function curate(mood = "", force = false) {
  const cacheKey = mood.trim().toLowerCase() || "__default";
  const cache = loadCache();
  const hit = cache[cacheKey];
  if (!force && hit && (Date.now() - hit.at) < TTL_MS && hit.picks?.length) {
    return hit.picks;
  }
  const out = await generate(mood);
  // only overwrite the cache when we actually produced playable mixes
  if (out.some((p) => p.uris?.length)) {
    cache[cacheKey] = { at: Date.now(), picks: out };
    saveCache(cache);
    return out;
  }
  // generation came back empty (e.g. transient) — fall back to any prior cache
  return hit?.picks?.length ? hit.picks : out;
}

/** When the cache for a mood was last generated (ms epoch), or 0 if never. */
export function cachedAt(mood = ""): number {
  const c = loadCache();
  return c[(mood.trim().toLowerCase() || "__default")]?.at || 0;
}

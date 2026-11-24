/**
 * OpenHome voice agent — a real conversational assistant (not keyword matching).
 *
 * Brain: Claude via the ccut gateway (the signed-in `claude` CLI behind a bearer
 * token) — no Google/Anthropic API key needed. Tools: home control, music, and
 * web search (weather + free search, no key). One or two LLM round-trips per turn.
 *
 * Contract: run(text) -> { reply, actions } so the hub's /agent route and the Pi
 * voice client can use it directly. `reply` is short + spoken aloud.
 */
import { execFile } from "node:child_process";
// (voiceagent) — home/lights/spotify tool execution
import * as home from "./home.ts";
import * as lights from "./lights.ts";
import * as spotify from "./spotify.ts";
import * as sceneConfig from "./sceneConfig.ts";
import * as personal from "./personal.ts";
import * as presence from "./presence.ts";
import * as speech from "./speech.ts";
import * as party from "./party.ts";

const CCUT_URL = (process.env.CCUT_CLAUDE_URL || "").replace(/\/$/, "");
const CCUT_TOKEN = process.env.CCUT_CLAUDE_TOKEN || "";
// Direct Anthropic is the primary path; the ccut gateway stays as a fallback
// for deployments that have it. Either one satisfies enabled().
const ANTHROPIC_KEY = process.env.ANTHROPIC_API_KEY || "";
const VOICE_MODEL_ID = process.env.VOICE_MODEL_ID || "claude-haiku-4-5-20251001";
const FIRECRAWL_KEY = process.env.FIRECRAWL_API_KEY || "";
const BRAVE_KEY = process.env.BRAVE_API_KEY || process.env.BRAVE_SEARCH_API_KEY || "";
// Where the house is. Used for "near me" searches and for the default weather
// lookup, both of which are nonsense without it.
//
// Two settings, not one, because they are read by different things. The PLACE
// string goes into search queries, where a neighbourhood name is what makes a
// result local ("in New York, NY" centres on Midtown, four miles away). The
// coordinates go to the weather API, which cannot geocode a neighbourhood --
// open-meteo returns nothing for "Bushwick, Brooklyn, NY" and the right answer
// for bare "Bushwick".
const HOME_PLACE = process.env.OPEN_HOME_PLACE || "New York, NY";
const HOME_LAT = Number(process.env.OPEN_HOME_LAT ?? 40.7128);
const HOME_LON = Number(process.env.OPEN_HOME_LON ?? -74.006);
const UID = process.getuid ? process.getuid() : 1000;
const EXEC_ENV = { ...process.env, XDG_RUNTIME_DIR: process.env.XDG_RUNTIME_DIR || `/run/user/${UID}` };

export function enabled(): boolean { return !!ANTHROPIC_KEY || !!(CCUT_URL && CCUT_TOKEN); }

// Same contract as ccut(): prompt in, model's text out. Keeping the signature
// identical means the two call sites and all the JSON parsing stay untouched.
async function anthropic(prompt: string, timeoutMs = 45000): Promise<string> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": ANTHROPIC_KEY,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: VOICE_MODEL_ID,
        max_tokens: 1024,
        messages: [{ role: "user", content: prompt }],
      }),
      signal: ctrl.signal,
    });
    if (!r.ok) throw new Error(`anthropic HTTP ${r.status}`);
    const j: any = await r.json();
    const out = String(j?.content?.[0]?.text || "").trim();
    if (!out) throw new Error("anthropic: empty result");
    return out;
  } finally {
    clearTimeout(t);
  }
}

async function ccut(
prompt: string, timeoutMs = 45000): Promise<string> {
  if (ANTHROPIC_KEY) return anthropic(prompt, timeoutMs);
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(`${CCUT_URL}/v1/claude`, {
      method: "POST",
      headers: { "content-type": "application/json", authorization: `Bearer ${CCUT_TOKEN}` },
      body: JSON.stringify({ prompt, model: process.env.VOICE_MODEL || "haiku" }),
      signal: ctrl.signal,
    });
    if (!r.ok) throw new Error(`ccut HTTP ${r.status}`);
    const outer: any = await r.json();
    const env = JSON.parse(outer.stdout || "{}");
    const out = String(env.result || "").trim();
    if (!out) throw new Error("ccut: empty result");
    return out;
  } finally {
    clearTimeout(t);
  }
}

function parseJson(txt: string): any {
  let s = txt.trim();
  if (s.startsWith("```")) s = s.replace(/^```[a-zA-Z]*\n?/, "").replace(/\n?```$/, "").trim();
  try { return JSON.parse(s); } catch {}
  const m = s.match(/\{[\s\S]*\}/);
  if (m) { try { return JSON.parse(m[0]); } catch {} }
  return null;
}

const SYSTEM = `You are Matthew's assistant at home. You happen to control the house, but you are HIS assistant, not the building's. Your replies are spoken aloud. Keep "say" to ONE short, natural sentence (~15 words) unless he explicitly asks for detail. No markdown, no emoji, no lists in "say".

Who you are talking to: Matthew. Use his name sparingly, the way a person would.

Respond with ONLY a JSON object, nothing else:
{"say": "<spoken reply, or empty string if you need a web search first>",
 "actions": [ <zero or more actions> ],
 "web_search": "<optional: a query if you need live/current info you don't know>",
 "listen": <true if you asked him something and expect an answer, false otherwise>}

Actions you can take (include any that apply):
- {"type":"scene","id":"good_morning|good_night|movie|away|home|dinner"}
- {"type":"lights","room":"living|kitchen|bedroom|office|bathroom|all","on":true|false}
- {"type":"party","on":true|false,"room":"<optional room>"}
  Party mode: flashes the colour bulbs through vivid colours in time with the music.
  Use it for "party mode", "party time", "disco", "make the lights dance".
  NOT for "play a party playlist" — that is a music action.
- {"type":"lock","locked":true|false}
- {"type":"thermostat","target":<fahrenheit int>}
- {"type":"music","op":"<see list>","source":"spotify|soundcloud","query":"<see below>"}
  music ops: play (needs query), pause, resume, next, previous, stop, shuffle_on, shuffle_off,
  repeat_on, repeat_one, repeat_off, now_playing, like, volume.
  query: for play → a song, artist, genre like "jazz", a playlist name, or "my liked songs";
         for volume → "up", "down", or a number 0-100; otherwise empty.
  Default source is spotify; use soundcloud only if the user says SoundCloud.
  Examples: "next song"→next, "go back"→previous, "turn it up"→volume "up", "shuffle"→shuffle_on,
  "what's playing"→now_playing, "like this song"→like, "play my discover weekly"→play query "discover weekly".

Rules:
- For anything needing current/live info (weather, news, sports, prices, movie times, opening hours, "today", facts you're unsure of), set "web_search" to a focused query and set "say" to "" — the home will search and ask you again with results.
- You CAN search the live web. Never say you are unable to look something up: if you do not know it, set "web_search" instead. If results come back empty, say what you do know and that the search found nothing — not that you have no access.
- For anything local ("near me", "around here"), search with the actual place name, not "near me".
- Otherwise put your spoken answer in "say" and any device actions in "actions".
- Be decisive: if he says "turn on the lights", do it. If he just chats, chat back briefly.

When to keep listening:
- Set "listen": true ONLY when you have asked a question you actually want
  answered, so the house keeps the mic open and he can just reply.
- Set it false for anything you have simply done ("lights off"), or for a
  remark that does not invite a reply. Leaving the mic open after an action is
  how an assistant ends up transcribing the room.

How to talk to him:
- "What's going on?", "what's up?", "how's it going?" are questions about HIS day,
  not the house. Answer about him: what's on his list, what's coming up, what he
  might want to get done. Ask him something back.
- NEVER recite device or system status unless he actually asks for it. The house
  being 71 degrees with music on is not news. Assume the system is healthy and
  say nothing about it; only speak up if something is genuinely broken AND it
  affects him.
- Device state below is background so your answers make sense in context. It is
  not a report to read out.
- Be a person about it: warm, direct, brief. Curious about how he is and what he
  is trying to get done. No status-report voice, no pleasantries for their own
  sake.`;

// ---- tools -----------------------------------------------------------------
function run(cmd: string, args: string[], timeout = 8000): Promise<string> {
  return new Promise((resolve) => {
    execFile(cmd, args, { timeout, env: EXEC_ENV }, (err, stdout) => resolve(err ? "" : String(stdout || "")));
  });
}

// Questions whose answer lives on the page, not in the snippet about the page.
//
// Deliberately narrow, and movie showtimes are deliberately NOT in it. They
// look like the obvious case and they are the one that does not work: measured
// against Fandango, Moviefone and CinemaClock, the listings are loaded by
// JavaScript from an API after a location prompt, so a scrape returns the
// filter sidebar and the promo fine print — CinemaClock literally renders
// "0 cinemas, 0 movies". Reading one costs six seconds to learn nothing, so
// showtimes need a real showtimes API, not a scraper.
const NEEDS_PAGE = /open (today|now|until|till)|opening hours|what time does .* (open|close)|hours of operation|\bmenu\b|final score|standings|box score|times for/i;

/**
 * Read one page through Firecrawl.
 *
 * Only called for the queries that need it — it costs several seconds, which
 * is a long time to stand in a room waiting for an answer.
 */
/**
 * The part of a page that answers the question.
 *
 * Taking the first N characters is the obvious thing and it is wrong: on any
 * real page those are the nav bar, the cookie notice and the filter sidebar.
 * Measured on a cinema listings page, 3500 characters from the top got as far
 * as the list of languages. So: strip the markdown chrome, then keep the
 * window where the query's own words are densest.
 */
function relevantPart(md: string, query: string, budget = 3500): string {
  const lines = md
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")       // images
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")    // links -> their text
    .split("\n")
    .map((l) => l.replace(/^[\s\-*|>]+/, "").trimEnd())
    .filter((l) => l.length >= 3);
  const joined = lines.join("\n");
  if (joined.length <= budget) return joined;

  const words = (query.toLowerCase().match(/[a-z]{4,}/g) || []).filter((w) => w !== "what");
  const score = (l: string) => {
    const s = l.toLowerCase();
    // Times and prices are what these questions are usually after.
    return (l.match(/\b\d{1,2}:\d{2}\s*[ap]?\.?m?\.?/gi) || []).length * 3
      + words.filter((w) => s.includes(w)).length;
  };
  const scores = lines.map(score);
  const win = 80;
  let run = scores.slice(0, win).reduce((a, b) => a + b, 0);
  let best = run, at = 0;
  for (let i = 1; i + win <= scores.length; i++) {
    run += scores[i + win - 1] - scores[i - 1];
    if (run > best) { best = run; at = i; }
  }
  // Nothing scored: the answer is probably not on the page at all, and the top
  // is at least where the page says what it is.
  const slice = lines.slice(best > 0 ? at : 0, (best > 0 ? at : 0) + 400).join("\n");
  return slice.slice(0, budget);
}

async function readPage(url: string | undefined, query: string): Promise<string> {
  if (!url || !FIRECRAWL_KEY) return "";
  try {
    const ctrl = new AbortController();
    // Shorter than it wants to be: this is on the critical path of someone
    // standing in a room waiting for an answer.
    const t = setTimeout(() => ctrl.abort(), 12000);
    const r = await fetch("https://api.firecrawl.dev/v2/scrape", {
      method: "POST",
      headers: { Authorization: `Bearer ${FIRECRAWL_KEY}`, "Content-Type": "application/json" },
      body: JSON.stringify({ url, formats: ["markdown"], onlyMainContent: true }),
      signal: ctrl.signal,
    });
    clearTimeout(t);
    const j: any = await r.json();
    const md = String(j?.data?.markdown || j?.markdown || "").trim();
    if (!md) { console.log(`[search] firecrawl read ${url} -> empty`); return ""; }
    const kept = relevantPart(md, query);
    console.log(`[search] firecrawl read ${url} -> ${md.length} chars, kept ${kept.length}`);
    return `\n\nContents of ${url} (read live, trust this over the snippets above):\n${kept}`;
  } catch (e) {
    console.log("[search] firecrawl read failed:", (e as Error)?.message);
    return "";
  }
}

/** WMO weather code -> plain English, so the model never has to guess. */
function sky(code: number): string {
  const m: Record<number, string> = {
    0: "clear", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "freezing fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    56: "freezing drizzle", 57: "heavy freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain",
    66: "freezing rain", 67: "heavy freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "light rain showers", 81: "rain showers", 82: "violent rain showers",
    85: "snow showers", 86: "heavy snow showers",
    95: "thunderstorms", 96: "thunderstorms with hail", 99: "severe thunderstorms with hail",
  };
  return m[code] ?? "unclear";
}

async function webSearch(query: string): Promise<string> {
  const q = query.toLowerCase();
  // Weather: geocode (open-meteo, no key) + current conditions.
  if (/weather|temperature|forecast|rain|snow|cold|hot|degrees/.test(q)) {
    // A place counts as named ONLY if he said "in/for/at <somewhere>".
    //
    // This used to strip known words and treat whatever survived as a place
    // name, which is fragile in a way that fails silently: "whats the weather
    // right now" left the word "whats" behind, because the pattern matched
    // "what's" and "what is" but not "whats". We then geocoded "whats", got
    // nothing, skipped the weather lookup entirely, and fell through to a
    // general web search — and the model answered from the only temperature in
    // its prompt, which was the THERMOSTAT. It reported 70°F indoors as the
    // weather outside on a 54°F evening.
    // "in/for/at <Place>" anywhere, or a capitalised word that is not the
    // first one. The model forms its own follow-up queries and writes them
    // however it likes — "Chicago weather tomorrow" puts the place FIRST, and
    // a pattern anchored to "weather in" silently fell back to home
    // coordinates and answered about Brooklyn.
    const m = query.match(/\b(?:in|for|at)\s+([A-Z][A-Za-z.'-]*(?:[\s,]+[A-Z][A-Za-z.'-]*)*)/)
      || query.slice(1).match(/\b([A-Z][A-Za-z.'-]{2,}(?:\s+[A-Z][A-Za-z.'-]+)*)\b/);
    const named = (m ? m[1] : "").replace(/\s*,\s*$/, "").trim();
    try {
      // No place named: use the house's own coordinates. Geocoding the home
      // place by name does not work for a neighbourhood -- open-meteo returns
      // nothing at all for "Bushwick, Brooklyn, NY", which is the string that
      // makes Brave searches local. Coordinates sidestep that, and skip a
      // network round trip on the single most common question asked here.
      const home = { latitude: HOME_LAT, longitude: HOME_LON, name: HOME_PLACE, admin1: "" };
      const geocode = async (name: string) =>
        (await (await fetch(`https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(name)}&count=1`)).json())?.results?.[0];
      let loc = named ? await geocode(named) : home;
      if (named && !loc) {
        // Multi-word neighbourhoods do not geocode: open-meteo has nothing for
        // "Bushwick Brooklyn NY" and the right answer for bare "Bushwick". The
        // model writes queries like that about our own home place, so without
        // this retry the most ordinary follow-up — "how about tomorrow" — fell
        // through to a general web search.
        const first = named.split(/[\s,]+/)[0];
        loc = await geocode(first);
        // Still nothing, and it was our own place echoed back: use what we know.
        if (!loc && HOME_PLACE.toLowerCase().includes(first.toLowerCase())) loc = home;
        if (loc) console.log(`[search] weather: "${named}" did not geocode, used "${first}"`);
      }
      if (loc) {
        // Three days, not one. "How about tomorrow?" is the most obvious
        // follow-up there is and the data stopped at midnight tonight, so the
        // only way to answer it was from the model's own head.
        const w: any = await (await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${loc.latitude}&longitude=${loc.longitude}&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=auto&forecast_days=3&daily=temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max`)).json();
        const c = w?.current || {};
        const d = w?.daily || {};
        // The weather path returns data without going near Brave, so without
        // this there was no way to tell a real lookup from a confabulation.
        console.log(`[search] weather ${loc.name ?? "home"} (${loc.latitude},${loc.longitude}) -> now ${Math.round(c.temperature_2m)}F, ${sky(c.weather_code)}`);
        // Spell it out. The old format put "now 54°F" and "Today high 70°F" in
        // one sentence and the model answered "It's 70 degrees and
        // surprisingly warm" — reading the day's high as the temperature
        // outside, on the question this house gets asked more than any other.
        // Also translate the WMO code: left as "weather_code 3" the model
        // guessed at it, and guessing is how "overcast" became "almost no rain
        // expected tonight".
        return [
          `Weather at ${loc.name}${loc.admin1 ? `, ${loc.admin1}` : ""}.`,
          `RIGHT NOW, THIS IS THE TEMPERATURE OUTSIDE: ${Math.round(c.temperature_2m)}°F.`,
          `It feels like ${Math.round(c.apparent_temperature)}°F with ${Math.round(c.wind_speed_10m)} mph wind.`,
          `Sky right now: ${sky(c.weather_code)}.`,
          `For reference only, do NOT report these as the current temperature:`,
          `today's high was ${Math.round(d.temperature_2m_max?.[0])}°F and tonight's low will be ${Math.round(d.temperature_2m_min?.[0])}°F.`,
          d.temperature_2m_max?.[1] != null
            ? `TOMORROW: high ${Math.round(d.temperature_2m_max[1])}°F, low ${Math.round(d.temperature_2m_min[1])}°F, ${sky(d.weather_code?.[1])}, ${d.precipitation_probability_max?.[1] ?? "?"}% chance of precipitation.`
            : "",
          d.temperature_2m_max?.[2] != null
            ? `THE DAY AFTER: high ${Math.round(d.temperature_2m_max[2])}°F, low ${Math.round(d.temperature_2m_min[2])}°F, ${sky(d.weather_code?.[2])}.`
            : "",
        ].filter(Boolean).join(" ");
      }
    } catch {}
  }
  // General: Brave first. It is an actual search index — it answers "movie
  // times near me" and "is this place open" with the thing you asked for,
  // which the DuckDuckGo instant-answer endpoint simply does not do. That was
  // the whole of "I couldn't search the web for movie times": no key was
  // installed on this Pi, so every general query fell through to DDG, which
  // returns an empty abstract for anything local or time-sensitive.
  if (BRAVE_KEY) {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 9000);
      const r = await fetch(
        `https://api.search.brave.com/res/v1/web/search?q=${encodeURIComponent(query)}&count=5&country=us`,
        { headers: { Accept: "application/json", "X-Subscription-Token": BRAVE_KEY }, signal: ctrl.signal },
      );
      clearTimeout(t);
      if (r.ok) {
        const j: any = await r.json();
        const bits: string[] = [];
        const top: string[] = [];
        // Brave's own extracted answer, when it has one, is usually the whole
        // answer — put it first so the model does not have to infer it from
        // five snippets.
        const fx = j?.faq?.results?.[0];
        if (fx?.answer) bits.push(String(fx.answer));
        for (const w of (j?.web?.results || []).slice(0, 5)) {
          const line = `${w.title || ""}: ${(w.description || "").replace(/<\/?[^>]+>/g, "")}`.trim();
          if (line.length > 2) bits.push(line);
          if (w.url) top.push(String(w.url));
        }
        if (bits.length) {
          console.log(`[search] brave "${query}" -> ${bits.length} results`);
          // Some questions cannot be answered from snippets. Movie times are
          // the clear case: Brave's cached description for a listings page is
          // days old, so the answer looked live and was not. For those, read
          // the top page itself.
          const page = NEEDS_PAGE.test(query) ? await readPage(top[0], query) : "";
          return `Web results for "${query}":\n- ${bits.join("\n- ")}${page}`;
        }
      } else {
        console.log(`[search] brave HTTP ${r.status}`);
      }
    } catch (e) { console.log("[search] brave failed:", (e as Error)?.message); }
  }
  // Firecrawl next: slower, but it reads pages rather than snippets, so it
  // still wins on anything that needs the detail behind a link.
  if (FIRECRAWL_KEY) {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 18000);
      const r = await fetch("https://api.firecrawl.dev/v2/search", {
        method: "POST",
        headers: { Authorization: `Bearer ${FIRECRAWL_KEY}`, "Content-Type": "application/json" },
        body: JSON.stringify({ query, limit: 4 }),
        signal: ctrl.signal,
      });
      clearTimeout(t);
      const j: any = await r.json();
      const items = j.data?.web || j.web || j.data || [];
      const bits = (Array.isArray(items) ? items : []).slice(0, 4)
        .map((x: any) => `${x.title || ""}: ${x.description || x.snippet || ""}`.trim()).filter(Boolean);
      if (bits.length) return `Web results for "${query}":\n- ${bits.join("\n- ")}`;
    } catch {}
  }
  // Fallback: DuckDuckGo instant answer (free, no key).
  try {
    const j: any = await (await fetch(`https://api.duckduckgo.com/?q=${encodeURIComponent(query)}&format=json&no_html=1&skip_disambig=1`)).json();
    const bits = [j.AbstractText, j.Answer, j.Definition, ...(j.RelatedTopics || []).slice(0, 3).map((x: any) => x.Text)].filter(Boolean);
    if (bits.length) return `Search results for "${query}": ${bits.join(" | ")}`;
  } catch {}
  return `No clear search result for "${query}". Answer from your own knowledge, and say you couldn't look it up live.`;
}

async function setRoomVolume(q: string): Promise<string> {
  const s = String(q || "").toLowerCase();
  let arg = "", label = "";
  if (/up|louder|raise|increase|higher|more/.test(s)) { arg = "0.12+"; label = "up"; }
  else if (/down|lower|quiet|decrease|soft|less/.test(s)) { arg = "0.12-"; label = "down"; }
  else { const m = s.match(/(\d{1,3})/); if (m) { arg = (Math.max(0, Math.min(100, +m[1])) / 100).toFixed(2); label = `to ${m[1]}%`; } }
  if (!arg) return "tell me up, down, or a number";
  await run("wpctl", ["set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", arg]);
  return `volume ${label}`;
}

// Genre/mood/collection queries should play a PLAYLIST; specific artists/songs play tracks.
const GENRES = ["pop", "rock", "jazz", "classical", "hip hop", "hip-hop", "rap", "country",
  "indie", "lofi", "lo-fi", "edm", "dance", "house", "techno", "trap", "r&b", "rnb", "soul",
  "funk", "blues", "metal", "punk", "reggae", "reggaeton", "latin", "afrobeats", "k-pop",
  "kpop", "gospel", "ambient", "acoustic", "folk", "disco", "grunge"];
const PLAYLIST_MARKERS = ["hit", "top ", "mix", "playlist", "radio", "station", "vibe", "chill",
  "workout", "party", "focus", "sleep", "throwback", "essentials", "this is", "discover",
  "release radar", "daily mix", "charts", "trending", "best of", "roadtrip", "road trip",
  "dinner", "study", "classics", "anthems", "bangers", "hype", "relax", "jams"];
function wantsPlaylist(q: string): boolean {
  const s = q.toLowerCase().trim();
  if (GENRES.includes(s)) return true;
  return PLAYLIST_MARKERS.some((m) => s.includes(m));
}

// Tidy a playlist title for speaking: drop SEO spam after | / • / - separators,
// strip a leading "the" (so we don't say "the The ..."), and cap the length.
// Pick the most relevant playlist from search results — Spotify personalizes search and
// often ranks junk/short-named playlists first, so score by query-word overlap in the name
// (and prefer Spotify's own editorial) instead of blindly taking result #0.
function pickBestPlaylist(query: string, found: any[]): any {
  const qwords = query.toLowerCase().split(/\s+/).filter((w) => w.length > 2);
  let best = found[0];
  let bestScore = -1;
  for (const p of found) {
    const n = String(p?.name || "").toLowerCase();
    let score = qwords.filter((w) => n.includes(w)).length;
    if (String(p?.owner || "").toLowerCase() === "spotify") score += 2;
    if (score > bestScore) { bestScore = score; best = p; }
  }
  return best;
}

function speakName(n: string): string {
  let s = String(n || "").split(/[|•·]/)[0].trim();
  s = s.replace(/^the\s+/i, "").trim();
  if (s.length > 44) s = s.slice(0, 44).replace(/\s+\S*$/, "").trim();
  return s || String(n || "").trim();
}

async function doMusic(a: any): Promise<string> {
  const op = String(a.op || "play").toLowerCase();
  const src = String(a.source || "spotify").toLowerCase();
  const query = String(a.query || "").trim();
  if (op === "volume") return await setRoomVolume(query);  // room (X10) volume, any source
  if (src === "soundcloud") {
    if (op === "stop") { await run("sc-ctl", ["stop"]); return "stopped SoundCloud"; }
    if (["pause", "resume", "next"].includes(op)) { await run("sc-ctl", [op]); return op + " SoundCloud"; }
    await run("sc-play", query ? query.split(" ") : ["lofi"]); return `playing ${query || "music"} on SoundCloud`;
  }
  // --- Spotify control ---
  // Transport that Soloist does locally (reliable, instant); Web API for the rest.
  const connected = spotify.connected();
  const safe = async (fn: () => Promise<any>) => { try { await fn(); return true; } catch (e) { console.log("[music]", (e as Error)?.message); return false; } };
  switch (op) {
    case "pause": await run("soloist", ["ctl", "pause"]); return "paused";
    case "stop": await run("soloist", ["ctl", "pause"]); return "stopped";
    case "next": case "skip": await run("soloist", ["ctl", "next"]); return "skipped";
    case "previous": case "back": case "last": await safe(() => spotify.transportRemote("previous")); return "going back a track";
    case "shuffle_on": case "shuffle": await safe(() => spotify.shuffle(true)); return "shuffle on";
    case "shuffle_off": await safe(() => spotify.shuffle(false)); return "shuffle off";
    case "repeat_on": case "repeat": await safe(() => spotify.repeat("context")); return "repeat on";
    case "repeat_one": await safe(() => spotify.repeat("track")); return "repeating this track";
    case "repeat_off": await safe(() => spotify.repeat("off")); return "repeat off";
    case "now_playing": case "whats_playing": { try { const c = await spotify.currentlyPlaying(); return c ? `${c.title} by ${c.artist}` : "nothing is playing"; } catch { return "I couldn't check what's playing"; } }
    case "like": case "save": { try { const c = await spotify.saveCurrent(); return c ? `saved ${c.title} to your liked songs` : "nothing is playing to save"; } catch { return "I couldn't save that"; } }
  }
  // op play/resume (optionally with a query to start something)
  if (!query) { await run("soloist", ["ctl", "play"]); return "playing"; }
  if (!connected) { await run("soloist", ["ctl", "play"]); return "playing Spotify"; }
  try {
    const dev = await spotify.deviceForRoom("Living Room");
    const deviceId = dev?.id;
    const q = query.toLowerCase();
    if (/\bliked\b|liked songs|my songs|my music|my library|saved songs/.test(q)) {
      const uris = (await spotify.liked(50)).map((t: any) => t.uri).filter(Boolean);
      if (uris.length) { await spotify.play({ uris, deviceId }); return "NOWPLAYING::your liked songs"; }
    }
    // the user's OWN playlist, if the name matches
    const mine = await spotify.playlists(50);
    const pl = mine.find((p: any) => { const n = String(p.name || "").toLowerCase(); return n && (q.includes(n) || n.includes(q)); });
    if (pl) { await spotify.play({ contextUri: pl.uri, deviceId }); return `NOWPLAYING::the ${speakName(pl.name)} playlist`; }
    // Genre / mood / "top hits" / "mix" / "playlist" → play the best PUBLIC playlist
    // (Spotify's editorial catalog), not a literal track search.
    if (wantsPlaylist(q)) {
      try {
        const found = await spotify.searchPlaylists(query, 10);
        if (found.length) { const pl2 = pickBestPlaylist(query, found); await spotify.play({ contextUri: pl2.uri, deviceId }); return `NOWPLAYING::the ${speakName(pl2.name)} playlist`; }
      } catch (e) { console.log("[agent] playlist search failed:", (e as Error)?.message); }
    }
    // Specific song / artist → track search
    const tracks = await spotify.search(query, 25);
    const uris = tracks.map((t: any) => t.uri).filter(Boolean).slice(0, 30);
    if (uris.length) {
      await spotify.play({ uris, deviceId });
      const first = tracks[0];
      return first ? `NOWPLAYING::${first.title} by ${first.artist}` : `NOWPLAYING::${query}`;
    }
    // Last resort: any public playlist that matches
    try {
      const found = await spotify.searchPlaylists(query, 10);
      if (found.length) { const pl2 = pickBestPlaylist(query, found); await spotify.play({ contextUri: pl2.uri, deviceId }); return `NOWPLAYING::the ${speakName(pl2.name)} playlist`; }
    } catch {}
    return `I couldn't find ${query} on Spotify`;
  } catch {
    await run("soloist", ["ctl", "play"]); return "playing Spotify";
  }
}

// Run a scene's REAL configured actions (lights + a pinned Spotify playlist) on actual
// devices, so "good morning" turns on the real bulb and plays real music — not the mock.
async function runSceneReal(id: string): Promise<string | null> {
  const cfg = sceneConfig.getScene(id);
  if (!cfg) return null;
  const parts: string[] = [];
  for (const la of cfg.lights || []) {
    try {
      const all = lights.listLights().filter((x: any) => x.real);
      const targets = la.room
        ? all.filter((x: any) => String(x.room || "").toLowerCase().includes(la.room!.toLowerCase()))
        : all;
      let hit = 0;
      for (const l of targets) {
        const patch: any = { on: la.on };
        if (la.brightness != null) patch.brightness = la.brightness;
        if (la.rgb) patch.rgb = la.rgb;
        try { const r = await lights.control(l.id, patch); if (r.ok) hit++; } catch { /* light offline */ }
      }
      if (hit) parts.push(`${la.room || "lights"} on`);
    } catch { /* ignore light group errors */ }
  }
  // A scene can pin a context (playlist/artist URI) OR give a search query. The
  // config stored on the Pi used {source:"spotify", query:"2026 jazz"} while this
  // only ever read contextUri, so "good morning" turned on a light and then played
  // silence — with no error, because the branch simply never ran.
  if (cfg.music && !cfg.music.contextUri && cfg.music.query) {
    try {
      const picked = await doMusic({ op: "play", source: cfg.music.source || "spotify", query: cfg.music.query });
      if (picked) parts.push(picked.replace(/^NOWPLAYING::/, "playing "));
    } catch (e) { console.log("[scene] music query failed:", (e as Error)?.message); }
  } else if (cfg.music && cfg.music.contextUri) {
    try {
      const dev = await spotify.deviceForRoom("Living Room");
      // Spotify throws transient 502/503/429s (esp. when another stream is already
      // playing) — retry a few times so the scene's music isn't dropped on a hiccup.
      let played = false;
      for (let attempt = 0; attempt < 4 && !played; attempt++) {
        try {
          await spotify.play({ contextUri: cfg.music.contextUri, deviceId: dev?.id });
          played = true;
        } catch (e) {
          const msg = (e as Error)?.message || "";
          if (attempt < 3 && /50[0-9]|429|rate|timeout/i.test(msg)) {
            await new Promise((r) => setTimeout(r, 700));
            continue;
          }
          throw e;
        }
      }
      if (played) {
        if (cfg.music.shuffle) {
          // Let the device actually start the context before toggling shuffle, else the
          // shuffle command races the device warm-up and silently no-ops.
          await new Promise((r) => setTimeout(r, 900));
          try { await spotify.shuffle(true); } catch { /* best effort */ }
        }
        parts.push(`playing ${cfg.music.name || "music"}`);
      }
    } catch (e) { console.log("[scene] music failed:", (e as Error)?.message); }
  }
  return parts.length ? parts.join(", ") : null;
}

async function execActions(actions: any[]): Promise<string[]> {
  const done: string[] = [];
  for (const a of actions || []) {
    try {
      switch (a.type) {
        case "scene": {
          // Every scene except the party itself ends the party: a scene sets
          // its own light colours and would be overwritten on the next flash.
          if (party.isOn() && String(a.id) !== "party") party.stop(false, `scene "${a.id}"`);
          const real = await runSceneReal(String(a.id));   // real devices (lights + playlist)
          home.activateScene(String(a.id));                // keep mock/UI model in sync
          done.push(real || `scene ${a.id}`);
          break;
        }
        case "party": {
          if (a.on === false) { party.stop(); done.push("party over"); break; }
          const r = await party.start(a.room ? String(a.room) : undefined);
          done.push(r.lights
            ? `party on, ${r.lights} light${r.lights === 1 ? "" : "s"}${r.bpm ? ` at ${Math.round(r.bpm)} BPM` : ""}`
            : "no colour lights are online to party with");
          break;
        }
        case "lights": {
          const on = !!a.on;
          const room = String(a.room || "all").toLowerCase();
          // A direct light command takes over from the party, or the two fight
          // over the same bulb every half second.
          if (party.isOn()) party.stop(false, `lights ${on ? "on" : "off"} command`);
          // Control REAL onboarded lights (ESPHome/Matter).
          let hit = 0;
          try {
            const all = lights.listLights().filter((x: any) => x.real);
            const targets = room === "all" ? all : all.filter((x: any) => String(x.room || "").toLowerCase().includes(room));
            for (const l of targets) { try { const r = await lights.control(l.id, { on }); if (r.ok) hit++; } catch {} }
          } catch {}
          // keep the mock/UI state in sync too
          if (a.room && a.room !== "all") home.setDevice(`light_${a.room}`, { on }); else home.setByType("light", { on });
          done.push(`lights ${on ? "on" : "off"}${hit ? ` (${hit} real)` : ""}`); break;
        }
        case "lock": home.setByType("lock", { locked: !!a.locked }); done.push(a.locked ? "locked" : "unlocked"); break;
        case "thermostat": home.setDevice("thermostat_main", { target: Number(a.target) }); done.push(`thermostat ${a.target}`); break;
        case "music": done.push(await doMusic(a)); break;
      }
    } catch (e) { console.log("[agent] action failed:", JSON.stringify(a), "->", (e as Error)?.message); }
  }
  return done;
}

const DASH_REPORT_URL = process.env.DASH_REPORT_URL || "https://dash.bedrock.casa/api/report-latest";

/**
 * The NYC daily digest that the morning scene reads out.
 *
 * Best effort on purpose: a slow or down dashboard must not hold up the lights
 * and the music, which are the part of "good morning" you actually notice.
 */
async function dailyReport(): Promise<string | null> {
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 8000);
    try {
      const r = await fetch(DASH_REPORT_URL, { signal: ctrl.signal });
      if (!r.ok) return null;
      const j: any = await r.json();
      // Prefer the SPOKEN version. The generator writes both: a long written
      // briefing with bulleted sections, and a ~30s spoken summary. Reading
      // the written one aloud meant grinding through every transit bullet.
      const spoken = String(j?.report?.spoken ?? "").trim();
      const text = String(j?.report?.text ?? "").trim();
      return spoken || text || null;
    } finally { clearTimeout(timer); }
  } catch (e) {
    console.log("[scene] daily report failed:", (e as Error)?.message);
    return null;
  }
}

/**
 * The radial remote's action keys, run against REAL devices.
 *
 * `/control` previously went straight to home.control(), which only moves the
 * mock house — so the dial animated, reported success, and changed nothing in
 * the room. Scene keys now go through the same execActions path as voice, and
 * the caller falls back to the mock for the keys with no hardware behind them
 * (cameras, doorbell).
 */
const CONTROL_SCENES: Record<string, string> = {
  morning: "good_morning", good_morning: "good_morning",
  goodnight: "good_night", nighttime: "good_night", good_night: "good_night",
  movie: "movie", away: "away", home: "home",
  // NB: "party" is handled before this table in runControl — it is a running
  // light show, not a one-shot scene.
  reading: "reading", dinner: "dinner", evening: "evening",
};

export async function runControl(action: string): Promise<{ label: string; scene?: string; actions: string[]; say?: string } | null> {
  // The dial's party key was in CONTROL_SCENES, so it looked wired — but it
  // went to runSceneReal, there is no "party" entry in the scene config, and
  // the fallback only moved the mock house. The dial animated and the room did
  // nothing. It is a toggle, not a scene.
  if (action === "party") {
    if (party.isOn()) { party.stop(); return { label: "party over", actions: ["party over"] }; }
    const r = await party.start();
    return {
      label: r.lights ? `party on · ${r.lights} light${r.lights === 1 ? "" : "s"}` : "no colour lights online",
      actions: [r.lights ? `party on (${r.lights})` : "no colour lights online"],
    };
  }
  const scene = CONTROL_SCENES[action];
  if (scene) {
    const done = await execActions([{ type: "scene", id: scene }]);
    const clean = done.map((d) => d.replace(/^NOWPLAYING::/, "now playing "));
    // The morning gesture should sound exactly like saying "good morning" out
    // loud — same scene, same report. Reaching it by a different route should
    // not get you a quieter version of it.
    let say: string | undefined;
    if (scene === "good_morning") {
      const report = await dailyReport();
      say = report ? `Good morning! Starting your morning scene.\n\n${report}` : "Good morning! Starting your morning scene.";
    }
    return { label: clean.join(", ") || scene.replace(/_/g, " "), scene, actions: clean, say };
  }
  if (action === "lights") {
    // Toggle on the real bulbs' current state, not the mock's, or the dial and
    // the room disagree about what "on" means.
    const real = lights.listLights().filter((x: any) => x.real);
    const anyOn = real.some((l: any) => l.on);
    const done = await execActions([{ type: "lights", on: !anyOn, room: "all" }]);
    return { label: done.join(", ") || (anyOn ? "lights off" : "lights on"), actions: done };
  }
  if (action === "music") {
    const done = await execActions([{ type: "music", op: "play" }]);
    return { label: done.join(", ") || "music", actions: done };
  }
  if (action === "matthews_room") {
    const done = await execActions([{ type: "lights", on: true, room: "bedroom" }]);
    return { label: done.join(", ") || "Matthew's room", actions: done };
  }
  return null; // no real hardware for this key — caller uses the mock
}

/**
 * Fast path — answer without the LLM.
 *
 * Measured on this Pi: speech-to-text 1563 ms, the agent 1426 ms, first TTS
 * byte 914 ms. Nearly four seconds for "turn on the lights", of which the
 * model contributed nothing a regex could not. The previous client did the
 * same thing and the droplet's notes clock it at ~42 ms.
 *
 * Deliberately narrow. It only fires on an unambiguous command — a verb cue
 * plus a target — so "is the kitchen light on?" and anything conversational
 * still goes to the model, where it belongs. A fast path that guesses is worse
 * than no fast path.
 */
const ROOMS = ["living room", "living", "kitchen", "bedroom", "office", "bathroom", "hallway", "dining"];

function detectRoom(t: string): string {
  for (const r of ROOMS) if (t.includes(r)) return r.replace(" room", "");
  return "all";
}

export async function fastPath(text: string): Promise<{ reply: string; actions: string[]; listen: boolean } | null> {
  const t = text.toLowerCase().trim().replace(/[.!?]+$/, "");

  // "Stop." — and it has to be instant, because the thing you are trying to
  // stop is talking over you while you say it. Nothing goes to the model here.
  //
  // Bare "stop" is ambiguous on purpose and resolved by what is actually
  // happening: if the house is mid-sentence you meant the house, otherwise you
  // meant the music. "Stop the music" is unambiguous and handled below.
  // Closing a conversation. "No, that's alright" went to the model, which
  // sensibly had nothing to say or do — and the house answered "Sorry, I
  // didn't get that", turning a polite decline into a failure. These end the
  // turn in silence, which is what a person would do.
  // Note what is NOT in here: "good night", which is the night scene's
  // trigger phrase and must keep reaching it.
  // "that's" / "thats" / "that is" — the transcriber is not consistent about
  // contractions, and matching only one spelling is how this reads as a
  // failure instead of a decline.
  const THATS = "that(?:'?s| is)";
  // A decline wants silence. Saying anything back to "no, that's alright" is
  // one more thing to listen to.
  const DECLINE = new RegExp(
    `^(?:no,? ?(?:thanks|thank you|${THATS} (?:alright|all ?right|ok|okay|fine)|i'?m good|we'?re good)` +
    `|${THATS} (?:all|it|fine|ok|okay|alright|all ?right)` +
    `|i'?m good|we'?re good|all good|nothing|nope|no)$`,
  );
  if (DECLINE.test(t)) {
    if (speech.speaking()) speech.stop();
    return { reply: "", actions: [], listen: false };
  }
  // A goodbye is not a decline. It got "See you in a bit" from the model and
  // that was better than silence — so keep the warmth, skip the round trip.
  if (/^(bye|goodbye|bye bye|see ?ya|see you|later|good ?bye now)$/.test(t)) {
    return { reply: "See you in a bit.", actions: [], listen: false };
  }
  if (/^(thanks|thank you|thanks a lot|cheers|appreciate it|nice one)$/.test(t)) {
    return { reply: "Any time.", actions: [], listen: false };
  }

  if (/^(stop|stop it|stop talking|shut up|be quiet|quiet|silence|enough|that'?s enough|never ?mind|cancel|forget it|skip it)$/.test(t)) {
    if (speech.speaking()) {
      speech.stop();
      // No reply. Answering "okay" to "shut up" is its own small insult, and
      // it would also be the next thing playing out of the speaker.
      return { reply: "", actions: ["stopped talking"], listen: false };
    }
    if (/^(stop|stop it|quiet|silence|enough|that'?s enough)$/.test(t)) {
      const done = await execActions([{ type: "music", op: "pause" }]);
      return { reply: "", actions: done, listen: false };
    }
    return { reply: "", actions: [], listen: false };
  }

  // Party mode. It lived in party.ts behind POST /lights/command and nothing
  // voice-facing could reach it, so asking out loud got "I don't have a party
  // mode set up yet" from a model that had never been told it exists.
  //
  // Guarded against the music sense of the word: "play a party playlist" is a
  // Spotify search, not a light show.
  if (/\bparty\b|\bdisco\b/.test(t) && !/\b(play|playlist|song|album|spotify|soundcloud)\b/.test(t)) {
    const off = /\b(off|stop|end|over|kill|quit|enough|no more)\b/.test(t);
    if (off) {
      party.stop();
      return { reply: "Party over.", actions: ["party over"], listen: false };
    }
    const r = await party.start(detectRoom(t) === "all" ? undefined : detectRoom(t));
    if (!r.lights) {
      return { reply: "No colour lights are online, so there's nothing to flash.", actions: [], listen: false };
    }
    return {
      reply: r.bpm ? `Party mode, on the beat.` : `Party mode on.`,
      actions: [`party on (${r.lights} light${r.lights === 1 ? "" : "s"})`],
      listen: false,
    };
  }

  // Lights. Require a command cue, so questions fall through to the model.
  const lightCue = /\b(turn|switch|put|shut|kill|cut)\b/.test(t) || /^lights? (on|off)\b/.test(t);
  if (lightCue && /\blights?\b/.test(t)) {
    const on = /\bon\b/.test(t) && !/\boff\b/.test(t);
    const room = detectRoom(t);
    const done = await execActions([{ type: "lights", on, room }]);
    const hit = done.join(", ");
    return { reply: on ? "Lights on." : "Lights off.", actions: [hit || `lights ${on ? "on" : "off"}`], listen: false };
  }

  // Volume. Measured failing live: "Lower the volume." went to the model,
  // which came back with an empty say and no actions, so the house answered
  // "Okay." and did nothing — which is worse than refusing. There is nothing
  // here to reason about.
  const vol = /\b(volume|turn it|turn the (music|sound)|make it)\b/.test(t) || /^(louder|quieter|softer)$/.test(t);
  if (vol) {
    const down = /\b(down|lower|quiet|quieter|softer|soft|less|reduce)\b/.test(t);
    const up = /\b(up|louder|higher|raise|more|increase)\b/.test(t);
    // A number only means an absolute level if he actually said "to 40" or
    // "40 percent". Caught live: "Lower the volume by 3 notches" would have
    // matched the bare 3 and set the room to 3% — the opposite of a small
    // nudge down. "By N <anything>" is relative, so just step it.
    const num = /\b(to|at)\s+\d{1,3}\b|\b\d{1,3}\s*(percent|%)/.test(t)
      ? t.match(/\b(\d{1,3})\b/)
      : null;
    if (down || up || num) {
      const q = num ? num[1] : down ? "down" : "up";
      const done = await execActions([{ type: "music", op: "volume", query: q }]);
      return { reply: "", actions: done, listen: false };
    }
  }

  // Music transport. "next"/"skip"/"pause" need no reasoning.
  const music: Record<string, string> = {
    "next": "next", "skip": "next", "next song": "next", "skip this": "next",
    "pause": "pause", "pause the music": "pause", "stop the music": "pause",
    "resume": "resume", "play": "resume", "unpause": "resume", "keep playing": "resume",
  };
  if (music[t]) {
    const done = await execActions([{ type: "music", op: music[t] }]);
    return { reply: done[0] ? String(done[0]) : music[t], actions: done, listen: false };
  }

  // Time and date: a clock read is not a job for a language model.
  if (/^(what('s| is)? the )?time( is it)?$/.test(t) || t === "what time is it") {
    const now = new Date();
    return { reply: `It's ${now.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}.`, actions: [], listen: false };
  }
  if (/^what('s| is)? (the )?(date|day)( is it)?$/.test(t) || t === "what day is it") {
    const now = new Date();
    return { reply: `It's ${now.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}.`, actions: [], listen: false };
  }

  return null;
}

// ---- conversation memory ---------------------------------------------------
/**
 * What was said before now.
 *
 * There was none of this. Every utterance built a fresh prompt — SYSTEM, the
 * house state, and `Matthew said: "<text>"` — with no trace of the turn before
 * it. The `listen` flag held the microphone open, which made it LOOK like a
 * conversation, but the model was answering each sentence cold.
 *
 * The failure, from the log:
 *     19:44:25  "theater times for the new Hunger Games tonight"
 *               -> "7 PM at AMC 19th St. East, or 10:35 PM"
 *     19:45:00  "Where is the theater located?"
 *               -> searched Brave for the literal string
 *                  "Where is the theater located?"
 *               -> "I'm not sure which one you mean"
 *
 * It had named the theater forty seconds earlier and had no idea.
 *
 * Deliberately a time window and not a session id: the exchange above spanned
 * two separate wake words ("Bye." ended the first), and a follow-up five
 * seconds after a goodbye is obviously the same conversation. Tying memory to
 * the mic being open would have failed this exact case.
 *
 * In process, not on disk. This is short-term memory — what a person would
 * still have in their head — not a record of everything ever said in the
 * house. It evaporates on restart, which is the right default for a thing that
 * listens all day.
 */
interface Turn { at: number; said: string; replied: string; context?: string }
const MEMORY_WINDOW_MS = Number(process.env.OPEN_HOME_MEMORY_MINUTES ?? 10) * 60_000;
const MEMORY_TURNS = Number(process.env.OPEN_HOME_MEMORY_TURNS ?? 8);
let turns: Turn[] = [];

function recent(): Turn[] {
  const cut = Date.now() - MEMORY_WINDOW_MS;
  turns = turns.filter((t) => t.at >= cut);
  return turns.slice(-MEMORY_TURNS);
}

function remember(said: string, replied: string, context?: string): void {
  turns.push({ at: Date.now(), said, replied, context });
  if (turns.length > MEMORY_TURNS * 2) turns = turns.slice(-MEMORY_TURNS);
}

export function forget(): void { turns = []; }

/** The conversation so far, oldest first, as the model should read it. */
function transcript(hist: Turn[]): string {
  if (!hist.length) return "";
  const lines = hist.map((t) => `Matthew: ${t.said}\nYou: ${t.replied}`);
  // Carry the most recent search results forward verbatim. Without them a
  // follow-up about something we just looked up has to be searched again from
  // scratch, which is exactly what could not be done without the context.
  const ctx = hist.filter((t) => t.context).slice(-1)[0]?.context;
  return `\nEarlier in this conversation (oldest first — "the theater", "it", "there" refer to things in here):\n${lines.join("\n")}\n` +
    (ctx ? `\nWhat you looked up a moment ago, still valid:\n${ctx.slice(0, 1500)}\n` : "");
}

/**
 * Is this a follow-up that cannot be searched on its own?
 *
 * "Where is the theater located?" matched the live-info regex and got searched
 * verbatim, which is meaningless. When the question leans on something said
 * earlier, the model has to see the history and form the query itself — so skip
 * the pre-search and let it ask.
 */
function isFollowUp(text: string): boolean {
  if (!turns.length) return false;
  // Names its own subject, so it stands alone no matter how short it is.
  // "whats the weather in Chicago" is five words and was being treated as a
  // follow-up, which skipped the weather lookup and sent it to a general web
  // search instead — a worse answer than the one it had asked for.
  if (/\b(?:in|at|for|to)\s+[A-Z][a-z]/.test(text)) return false;
  const t = text.toLowerCase();
  const refers = /\b(it|its|it's|that|those|them|they|there|the one|this)\b/.test(t)
    || /\bthe (theater|theatre|place|movie|film|show|game|restaurant|store|team|song|artist|album)\b/.test(t);
  // Three words or fewer genuinely cannot carry a question on their own
  // ("how about tomorrow", "and the low"). Six was too greedy.
  return refers || t.split(/\s+/).length <= 3;
}

// ---- main entry ------------------------------------------------------------
export async function runAgent(text: string): Promise<{ reply: string; actions: string[]; understood: boolean; listen?: boolean }> {
  // Filler is not a question. "Oh" and "you" both reached the model, cost a
  // round trip each, and were answered out loud with "Sorry, I didn't get
  // that" — which is worse than the silence they deserved. The client's frame
  // count now catches most of these before they are even sent; this is the
  // backstop for the ones that transcribe into a real word.
  const bare = text.toLowerCase().trim().replace(/[.!?,]+$/, "");
  if (bare.length < 2 || /^(oh|uh|um|erm|hmm|mm+|ah|eh|huh|you|a|the|and|so|well|yeah|ok|okay|mhm)$/.test(bare)) {
    console.log(`[agent] ignoring filler: ${JSON.stringify(text)}`);
    return { reply: "", actions: [], understood: false, listen: false };
  }

  // Deterministic scene trigger: the core "good morning" scene must not depend on the
  // (occasionally empty/slow) LLM. Match the phrase and run the configured scene directly.
  if (/\bgood morning\b|\bwake up\b/i.test(text)) {
    const done = await execActions([{ type: "scene", id: "good_morning" }]);
    const cleanDone = done.map((d) => d.replace(/^NOWPLAYING::/, "now playing "));
    // The NYC daily digest used to reach Matthew only through the Pi's own voice
    // client, which speaks it over the jazz. Any other surface — the phone, the
    // web app — got the scene without the report. Fetching it here means every
    // client gets it, and it no longer depends on that one process being alive.
    const report = await dailyReport();
    const reply = report
      ? `Good morning! Starting your morning scene.\n\n${report}`
      : "Good morning! Starting your morning scene.";
    // The report is the one thing worth keeping as context rather than as a
    // reply: "what did it say about the trains?" is a reasonable follow-up.
    remember(text, "Good morning! Starting your morning scene.", report || undefined);
    return { reply, actions: cleanDone, understood: true, listen: false };
  }
  if (/\bgood afternoon\b|\bafternoon\b/i.test(text)) {
    const done = await execActions([{ type: "scene", id: "afternoon" }]);
    const cleanDone = done.map((d) => d.replace(/^NOWPLAYING::/, "now playing "));
    return { reply: "Good afternoon! Putting on Palm Monkey.", actions: cleanDone, understood: true, listen: false };
  }
  if (/\bgood evening\b|\bevening\b/i.test(text)) {
    const done = await execActions([{ type: "scene", id: "evening" }]);
    const cleanDone = done.map((d) => d.replace(/^NOWPLAYING::/, "now playing "));
    return { reply: "Good evening! Starting your evening playlist.", actions: cleanDone, understood: true, listen: false };
  }
  // Try to answer without the model first — see fastPath().
  try {
    const fast = await fastPath(text);
    if (fast) {
      console.log(`[agent] fast path: ${JSON.stringify(text)} -> ${JSON.stringify(fast.actions)}`);
      // Still remembered, so "turn them off again" has something to refer to.
      remember(text, fast.reply || fast.actions.join(", "));
      return { ...fast, understood: true };
    }
  } catch (e) { console.log("[agent] fast path failed, using the model:", (e as Error)?.message); }

  // Label it. Handed the raw summary, the model answered "what's the weather?"
  // with the thermostat reading — which is a perfectly reasonable mistake when
  // the only number in the prompt called "temp" is 71.
  const state = `${JSON.stringify(home.summary())} — note: "temp" and "target" are the INDOOR thermostat in Fahrenheit, never the weather outside.`;
  // Who he is and what he has on, fetched in the background and cached so it
  // costs nothing on a "turn off the lights".
  let about = await personal.brief().catch(() => "");
  // Whether he is actually home, and for how long — context a person would
  // have. Cheap: presence polls on its own schedule, this just reads it.
  try {
    const me = presence.list().find((x) => x.id === "matthew");
    if (me) {
      const mins = me.since ? Math.round((Date.now() - me.since) / 60000) : 0;
      about += me.home
        ? `\nMatthew is home (${mins} min).`
        : `\nMatthew is out (left ${mins} min ago).`;
    }
  } catch { /* presence is optional context */ }
  // Pre-search obvious live-info questions so they're a single LLM round-trip (faster).
  // Pre-searching costs a round trip, but asking the model first and THEN
  // searching costs two — so anything that smells like it needs the live web
  // gets searched up front. "Movie times" belongs here; it was missing, so the
  // model answered from training data and then admitted it couldn't look it up.
  const needsLive = /weather|forecast|temperatur|rain|snow|news|headline|today|tonight|tomorrow|latest|score|who won|standings|game|price|stock|how much|right now|currently|open now|hours|what time|near me|movie|showtime|show time|times for|playing at|theater|theatre|restaurant|reservation|menu|address|directions|traffic|subway|train|flight|when does|when is|who is|what is the|concert|tickets|is .* open/i.test(text);
  // "Movie times near me" is unanswerable without a "me". The house knows
  // where it is; the search engine does not.
  // "to me" and "closest" were missing, so "where is the closest movie theater
  // to me" went to Brave verbatim and came back about theatres in general.
  const LOCAL = /near(est)? me|near by|nearby|around here|near here|close by|closest|nearest|around me|by me|in my area|walking distance|local/i;
  const localise = (q: string) =>
    LOCAL.test(q)
      ? `${q.replace(/near(est)? me|nearby|near by|around here|near here|close by|around me|by me|to me|in my area/gi, "").replace(/\s{2,}/g, " ").trim()} in ${HOME_PLACE}`
      : q;
  const hist = recent();
  const past = transcript(hist);
  // A follow-up must NOT be pre-searched. Searching "Where is the theater
  // located?" verbatim is how that question got answered with "I'm not sure
  // which one you mean" about a theater we had just named. Let the model read
  // the history and form a query that stands on its own.
  const followUp = isFollowUp(text);
  let pre = "";
  let searched = "";
  if (needsLive && !followUp) {
    searched = localise(text);
    const results = await webSearch(searched);
    pre = `\nWeb results (use these, don't ask to search again):\n${results}\n`;
  } else if (needsLive) {
    console.log(`[agent] follow-up — not pre-searching ${JSON.stringify(text)}`);
  }
  // Giving it the history was necessary but not sufficient. With context and
  // no pre-search it stopped asking to search and started answering from its
  // own head: "Where is the theater located?" came back "AMC 19th Street is at
  // 28 Liberty Street", confidently, with web_search empty. It is 890
  // Broadway. A wrong address delivered in a calm voice is worse than "let me
  // look that up", so on a factual follow-up the search is mandatory.
  const mustSearch = followUp && needsLive
    ? `\nIMPORTANT: this is a follow-up to the conversation above and it refers to something already mentioned. You do NOT know the answer. Set "say" to "" and set "web_search" to a SELF-CONTAINED query that resolves the reference using the history — name the thing explicitly instead of saying "the theater" or "it". Addresses, times, runtimes and prices must come from a search, never from memory; those are exactly what you get wrong.\n`
    : "";
  if (past) console.log(`[agent] ${hist.length} turn(s) of context${followUp ? " (follow-up)" : ""}`);
  const p1 = `${SYSTEM}\n\nThe house is in ${HOME_PLACE}; "near me" means there.\n\n${about}\n\nHouse (background only, do not recite): ${state}${past}${pre}${mustSearch}\nMatthew said: "${text}"`;
  let out = parseJson(await ccut(p1)) || {};
  // fallback: one web-search round-trip if the model still asks for one
  // One search per turn, hard. When we pre-searched and the model asks again
  // anyway — which it does when the results are thin — a second round trip
  // takes the answer from 5 seconds to 16 and comes back saying the same
  // thing. Better a frank "I couldn't find it" quickly.
  if (pre && out.web_search) {
    console.log("[agent] ignoring a second search request; already pre-searched");
    out.web_search = "";
    if (!String(out.say || "").trim()) out.say = "I looked, but I couldn't find that. Want me to try it a different way?";
  }
  let results = "";
  // It was told to ask and answered anyway. Search on the resolved question
  // rather than trusting it, since the whole point is that it does not know.
  if (mustSearch && !out.web_search) {
    const topic = hist.slice(-1)[0];
    out.web_search = `${text} ${topic ? topic.said : ""}`.trim();
    out.say = "";
    console.log(`[agent] follow-up answered without searching; forcing a search for ${JSON.stringify(out.web_search)}`);
  }
  if (out.web_search && !String(out.say || "").trim()) {
    searched = localise(String(out.web_search));
    results = await webSearch(searched);
    const p2 = `${SYSTEM}\n\nThe house is in ${HOME_PLACE}.\n\n${about}\n\nHouse (background only, do not recite): ${state}${past}\nMatthew said: "${text}"\n\nYou asked to search for "${searched}"; here are results:\n${results}\n\nNow answer. Respond with the JSON object (put the answer in "say").`;
    out = parseJson(await ccut(p2)) || out;
  }
  console.log("[agent] llm out:", JSON.stringify({ say: out.say, actions: out.actions, web_search: out.web_search }));
  const done = await execActions(out.actions || []);
  // Music plays tag their result as "NOWPLAYING::<name>" so we can announce the
  // real thing that started, not the model's generic "sure, playing that".
  const np = done.map((d) => /^NOWPLAYING::(.+)/.exec(d)?.[1]).find(Boolean);
  const cleanDone = done.map((d) => d.replace(/^NOWPLAYING::/, "now playing "));
  let reply = String(out.say || "").trim();
  if (np) reply = `Now playing ${np}.`;
  // "Okay." for a model that returned nothing and did nothing is a lie, and it
  // happened live on "Lower the volume." Say so instead.
  if (!reply) reply = cleanDone.length ? "Done." : "Sorry, I didn't get that.";
  // Should the house keep the mic open? Trust the model when it says so, but
  // only when it did NOT also do something: "lights off. Anything else?" is a
  // completed action, and holding the mic after an action is how an assistant
  // ends up transcribing the room. Falling back to a question mark covers the
  // model forgetting the flag, which it will.
  // A question ANYWHERE in the reply counts. "My day's been quiet — how was
  // yours? I see you've got a few things on your list." ends in a full stop
  // but is plainly waiting for an answer; only matching a trailing "?" missed
  // exactly that case.
  const asked = reply.includes("?");
  const listen = cleanDone.length === 0 && (out.listen === true || asked);
  // Remember this exchange, including whatever we looked up, so the next
  // question can refer to it the way a person would.
  remember(text, reply, results || pre.replace(/^\nWeb results[^\n]*\n/, "") || undefined);
  return { reply, actions: cleanDone, understood: cleanDone.length > 0 || !!out.say, listen };
}

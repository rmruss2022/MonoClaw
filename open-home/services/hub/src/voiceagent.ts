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
import { AsyncLocalStorage } from "node:async_hooks";
// (voiceagent) — home/lights/spotify tool execution
import * as home from "./home.ts";
import * as lights from "./lights.ts";
import * as spotify from "./spotify.ts";

const CCUT_URL = (process.env.CCUT_CLAUDE_URL || "").replace(/\/$/, "");
const CCUT_TOKEN = process.env.CCUT_CLAUDE_TOKEN || "";
const FIRECRAWL_KEY = process.env.FIRECRAWL_API_KEY || "";
const UID = process.getuid ? process.getuid() : 1000;
const EXEC_ENV = { ...process.env, XDG_RUNTIME_DIR: process.env.XDG_RUNTIME_DIR || `/run/user/${UID}` };
const turnBudget = new AsyncLocalStorage<{ deadline: number; signal: AbortSignal }>();

function remainingMs(): number {
  const budget = turnBudget.getStore();
  const remaining = budget ? budget.deadline - Date.now() : 10500;
  if (remaining <= 0 || budget?.signal.aborted) throw new Error("Voice request timed out");
  return remaining;
}

function requestSignal(timeoutMs: number): AbortSignal {
  const timeout = AbortSignal.timeout(Math.max(1, Math.min(timeoutMs, remainingMs())));
  const signal = turnBudget.getStore()?.signal;
  return signal ? AbortSignal.any([signal, timeout]) : timeout;
}

export function enabled(): boolean { return !!(CCUT_URL && CCUT_TOKEN); }

async function ccut(prompt: string, timeoutMs = 7500): Promise<string> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(`${CCUT_URL}/v1/claude`, {
      method: "POST",
      headers: { "content-type": "application/json", authorization: `Bearer ${CCUT_TOKEN}` },
      body: JSON.stringify({ prompt, model: process.env.VOICE_MODEL || "haiku" }),
      signal: AbortSignal.any([ctrl.signal, requestSignal(timeoutMs)]),
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

async function llmJson(prompt: string): Promise<any> {
  for (let attempt = 0; attempt < 2; attempt++) {
    const out = parseJson(await ccut(attempt ? `${prompt}\nReturn ONLY valid JSON: {"say":"...","actions":[]}. No prose or code fences.` : prompt));
    if (out && typeof out === "object" && !Array.isArray(out)
        && typeof out.say === "string" && Array.isArray(out.actions)
        && out.actions.every((action: any) => action && typeof action === "object" && typeof action.type === "string")) return out;
    // A malformed response gets exactly one strict retry, only within this turn's budget.
    if (remainingMs() < 1000) break;
  }
  throw new Error("Invalid assistant JSON response");
}

const SYSTEM = `You are the OpenHome voice assistant in a smart home. Your replies are spoken aloud. Keep "say" to ONE short, natural sentence (~15 words) unless the user explicitly asks for detail. No markdown, no emoji, no lists in "say".

Respond with ONLY a JSON object, nothing else:
{"say": "<spoken reply, or empty string if you need a web search first>",
 "actions": [ <zero or more actions> ],
 "web_search": "<optional: a query if you need live/current info you don't know>"}

Actions you can take (include any that apply):
- {"type":"scene","id":"good_morning|good_night|movie|away|home|dinner"}
- {"type":"lights","room":"living|kitchen|bedroom|office|bathroom|all","on":true|false}
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
- For anything needing current/live info (weather, news, sports, prices, "today", facts you're unsure of), set "web_search" to a focused query and set "say" to "" — the home will search and ask you again with results.
- Otherwise put your spoken answer in "say" and any device actions in "actions".
- Be decisive: if they say "turn on the lights", do it. If they just chat, chat back briefly.`;

// ---- tools -----------------------------------------------------------------
type CommandResult = { ok: boolean; code: number | string | null; stdout: string; stderr: string };
async function run(cmd: string, args: string[], timeout = 8000, retry = true): Promise<CommandResult> {
  const result = await new Promise<CommandResult>((resolve) => {
    execFile(cmd, args, { timeout: Math.max(1, Math.min(timeout, remainingMs())), signal: turnBudget.getStore()?.signal, env: EXEC_ENV }, (err, stdout, stderr) => {
      resolve({ ok: !err, code: err ? err.code ?? null : 0, stdout: String(stdout || ""), stderr: String(stderr || "") });
    });
  });
  if (!result.ok && cmd === "soloist" && retry && remainingMs() > 1500) {
    const restarted = await run("systemctl", ["--user", "restart", "soloist"], 1500, false);
    if (restarted.ok) return run(cmd, args, timeout, false);
  }
  if (!result.ok) console.log("[agent] command failed:", cmd, result.code, result.stderr.slice(0, 160));
  return result;
}

async function commandReply(cmd: string, args: string[], success: string): Promise<string> {
  return (await run(cmd, args)).ok ? success : "I couldn't control the music right now";
}

async function webSearch(query: string): Promise<string> {
  const q = query.toLowerCase();
  // Weather: geocode (open-meteo, no key) + current conditions.
  if (/weather|temperature|forecast|rain|snow|cold|hot|degrees/.test(q)) {
    const place = query.replace(/.*weather (in|for|at)\s*/i, "").replace(/weather|what('s| is)|the|like|right now|today|\?/gi, "").trim() || "New York";
    try {
      const g: any = await (await fetch(`https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(place)}&count=1`, { signal: requestSignal(1200) })).json();
      const loc = g?.results?.[0];
      if (loc) {
        const w: any = await (await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${loc.latitude}&longitude=${loc.longitude}&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=auto&forecast_days=1&daily=temperature_2m_max,temperature_2m_min`, { signal: requestSignal(1200) })).json();
        const c = w?.current || {};
        const d = w?.daily || {};
        return `Weather for ${loc.name}, ${loc.admin1 || loc.country || ""}: now ${Math.round(c.temperature_2m)}°F (feels ${Math.round(c.apparent_temperature)}°F), wind ${Math.round(c.wind_speed_10m)} mph, weather_code ${c.weather_code}. Today high ${Math.round(d.temperature_2m_max?.[0])}°F / low ${Math.round(d.temperature_2m_min?.[0])}°F.`;
      }
    } catch {}
  }
  // General: Firecrawl search (real web results).
  if (FIRECRAWL_KEY) {
    try {
      const r = await fetch("https://api.firecrawl.dev/v2/search", {
        method: "POST",
        headers: { Authorization: `Bearer ${FIRECRAWL_KEY}`, "Content-Type": "application/json" },
        body: JSON.stringify({ query, limit: 4 }),
        signal: requestSignal(1800),
      });
      if (!r.ok) throw new Error(`search HTTP ${r.status}`);
      const j: any = await r.json();
      const items = j.data?.web || j.web || j.data || [];
      const bits = (Array.isArray(items) ? items : []).slice(0, 4)
        .map((x: any) => `${x.title || ""}: ${x.description || x.snippet || ""}`.trim()).filter(Boolean);
      if (bits.length) return `Web results for "${query}":\n- ${bits.join("\n- ")}`;
    } catch {}
  }
  // Fallback: DuckDuckGo instant answer (free, no key).
  try {
    const j: any = await (await fetch(`https://api.duckduckgo.com/?q=${encodeURIComponent(query)}&format=json&no_html=1&skip_disambig=1`, { signal: requestSignal(1200) })).json();
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
  const result = await run("wpctl", ["set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", arg]);
  return result.ok ? `volume ${label}` : "I couldn't change the volume";
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
    if (op === "stop") return commandReply("sc-ctl", ["stop"], "stopped SoundCloud");
    if (["pause", "resume", "next"].includes(op)) return commandReply("sc-ctl", [op], op + " SoundCloud");
    return commandReply("sc-play", query ? query.split(" ") : ["lofi"], `playing ${query || "music"} on SoundCloud`);
  }
  // --- Spotify control ---
  // Transport that Soloist does locally (reliable, instant); Web API for the rest.
  const connected = spotify.connected();
  const safe = async (fn: () => Promise<any>) => { try { await fn(); return true; } catch (e) { console.log("[music]", (e as Error)?.message); return false; } };
  switch (op) {
    case "pause": return commandReply("soloist", ["ctl", "pause"], "paused");
    case "stop": return commandReply("soloist", ["ctl", "pause"], "stopped");
    case "next": case "skip": return commandReply("soloist", ["ctl", "next"], "skipped");
    case "previous": case "back": case "last": return await safe(() => spotify.transportRemote("previous")) ? "going back a track" : "I couldn't go back a track";
    case "shuffle_on": case "shuffle": return await safe(() => spotify.shuffle(true)) ? "shuffle on" : "I couldn't change shuffle";
    case "shuffle_off": return await safe(() => spotify.shuffle(false)) ? "shuffle off" : "I couldn't change shuffle";
    case "repeat_on": case "repeat": return await safe(() => spotify.repeat("context")) ? "repeat on" : "I couldn't change repeat";
    case "repeat_one": return await safe(() => spotify.repeat("track")) ? "repeating this track" : "I couldn't change repeat";
    case "repeat_off": return await safe(() => spotify.repeat("off")) ? "repeat off" : "I couldn't change repeat";
    case "now_playing": case "whats_playing": { try { const c = await spotify.currentlyPlaying(); return c ? `${c.title} by ${c.artist}` : "nothing is playing"; } catch { return "I couldn't check what's playing"; } }
    case "like": case "save": { try { const c = await spotify.saveCurrent(); return c ? `saved ${c.title} to your liked songs` : "nothing is playing to save"; } catch { return "I couldn't save that"; } }
  }
  // op play/resume (optionally with a query to start something)
  if (!query) return commandReply("soloist", ["ctl", "play"], "playing");
  if (!connected) return commandReply("soloist", ["ctl", "play"], "playing Spotify");
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
    return commandReply("soloist", ["ctl", "play"], "playing Spotify");
  }
}

async function execActions(actions: any[]): Promise<string[]> {
  const done: string[] = [];
  for (const a of actions || []) {
    remainingMs();   // Never start another action after the caller's deadline.
    try {
      switch (a.type) {
        case "scene": home.activateScene(String(a.id)); done.push(`scene ${a.id}`); break;
        case "lights": {
          const on = !!a.on;
          const room = String(a.room || "all").toLowerCase();
          // Control REAL onboarded lights (ESPHome/Matter).
          let hit = 0;
          try {
            const all = lights.listLights().filter((x: any) => x.real);
            const targets = room === "all" ? all : all.filter((x: any) => String(x.room || "").toLowerCase().includes(room));
            for (const l of targets) { remainingMs(); try { const r = await lights.control(l.id, { on }, turnBudget.getStore()?.signal); if (r.ok) hit++; } catch {} }
            if (targets.length && hit < targets.length) {
              done.push("I couldn't control all of those lights");
              break;
            }
          } catch {}
          remainingMs();
          // keep the mock/UI state in sync too
          if (a.room && a.room !== "all") home.setDevice(`light_${a.room}`, { on }); else home.setByType("light", { on });
          done.push(`lights ${on ? "on" : "off"}${hit ? ` (${hit} real)` : ""}`); break;
        }
        case "lock": home.setByType("lock", { locked: !!a.locked }); done.push(a.locked ? "locked" : "unlocked"); break;
        case "thermostat": home.setDevice("thermostat_main", { target: Number(a.target) }); done.push(`thermostat ${a.target}`); break;
        case "music": done.push(await doMusic(a)); break;
      }
    } catch (e) {
      console.log("[agent] action failed:", JSON.stringify(a), "->", (e as Error)?.message);
      done.push("I couldn't complete that action");
    }
  }
  return done;
}

// ---- main entry ------------------------------------------------------------
export async function runAgent(text: string): Promise<{ reply: string; actions: string[]; understood: boolean }> {
  const ctrl = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  const expired = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      ctrl.abort();
      reject(new Error("Voice request timed out"));
    }, 10500);
  });
  try {
    return await Promise.race([expired, turnBudget.run({ deadline: Date.now() + 10500, signal: ctrl.signal },
      () => spotify.withRequestSignal(ctrl.signal, () => runAgentWithinBudget(text)))]);
  } catch (e) {
    console.log("[agent] failed:", (e as Error).message);
    return { reply: "Sorry, I couldn't complete that request in time. Please try again.", actions: [], understood: false };
  } finally {
    clearTimeout(timer);
  }
}

async function runAgentWithinBudget(text: string): Promise<{ reply: string; actions: string[]; understood: boolean }> {
  const state = JSON.stringify(home.summary());
  // Pre-search obvious live-info questions so they're a single LLM round-trip (faster).
  const needsLive = /weather|forecast|temperatur|rain|snow|news|headline|today|tonight|latest|score|who won|standings|game|price|stock|how much|right now|currently|open now|hours|what time|near me/i.test(text);
  let pre = "";
  if (needsLive) {
    const results = await webSearch(text);
    pre = `\nWeb results (use these, don't ask to search again):\n${results}\n`;
  }
  const p1 = `${SYSTEM}\n\nHome state: ${state}${pre}\nUser said: "${text}"`;
  let out = await llmJson(p1);
  // fallback: one web-search round-trip if the model still asks for one
  if (out.web_search && !String(out.say || "").trim()) {
    if (remainingMs() < 2000) throw new Error("Insufficient time for another search");
    const results = await webSearch(String(out.web_search));
    const p2 = `${SYSTEM}\n\nHome state: ${state}\nUser said: "${text}"\n\nYou asked to search; here are results:\n${results}\n\nNow answer. Respond with the JSON object (put the answer in "say").`;
    if (remainingMs() < 1000) throw new Error("Insufficient time for another LLM call");
    out = await llmJson(p2);
  }
  console.log("[agent] llm out:", JSON.stringify({ say: out.say, actions: out.actions, web_search: out.web_search }));
  const done = await execActions(out.actions || []);
  remainingMs();
  // Music plays tag their result as "NOWPLAYING::<name>" so we can announce the
  // real thing that started, not the model's generic "sure, playing that".
  const np = done.map((d) => /^NOWPLAYING::(.+)/.exec(d)?.[1]).find(Boolean);
  const cleanDone = done.map((d) => d.replace(/^NOWPLAYING::/, "now playing "));
  let reply = String(out.say || "").trim();
  const failure = cleanDone.find((result) => /^I couldn't/i.test(result));
  if (failure) reply = failure;
  if (np && !failure) reply = `Now playing ${np}.`;
  if (!reply) reply = cleanDone.length ? "Done." : "Okay.";
  return { reply, actions: cleanDone, understood: cleanDone.length > 0 || !!out.say };
}

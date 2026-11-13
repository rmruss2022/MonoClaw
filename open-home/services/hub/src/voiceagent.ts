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

const CCUT_URL = (process.env.CCUT_CLAUDE_URL || "").replace(/\/$/, "");
const CCUT_TOKEN = process.env.CCUT_CLAUDE_TOKEN || "";
const FIRECRAWL_KEY = process.env.FIRECRAWL_API_KEY || "";
const UID = process.getuid ? process.getuid() : 1000;
const EXEC_ENV = { ...process.env, XDG_RUNTIME_DIR: process.env.XDG_RUNTIME_DIR || `/run/user/${UID}` };

export function enabled(): boolean { return !!(CCUT_URL && CCUT_TOKEN); }

async function ccut(prompt: string, timeoutMs = 45000): Promise<string> {
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
function run(cmd: string, args: string[], timeout = 8000): Promise<string> {
  return new Promise((resolve) => {
    execFile(cmd, args, { timeout, env: EXEC_ENV }, (err, stdout) => resolve(err ? "" : String(stdout || "")));
  });
}

async function webSearch(query: string): Promise<string> {
  const q = query.toLowerCase();
  // Weather: geocode (open-meteo, no key) + current conditions.
  if (/weather|temperature|forecast|rain|snow|cold|hot|degrees/.test(q)) {
    const place = query.replace(/.*weather (in|for|at)\s*/i, "").replace(/weather|what('s| is)|the|like|right now|today|\?/gi, "").trim() || "New York";
    try {
      const g: any = await (await fetch(`https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(place)}&count=1`)).json();
      const loc = g?.results?.[0];
      if (loc) {
        const w: any = await (await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${loc.latitude}&longitude=${loc.longitude}&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=auto&forecast_days=1&daily=temperature_2m_max,temperature_2m_min`)).json();
        const c = w?.current || {};
        const d = w?.daily || {};
        return `Weather for ${loc.name}, ${loc.admin1 || loc.country || ""}: now ${Math.round(c.temperature_2m)}°F (feels ${Math.round(c.apparent_temperature)}°F), wind ${Math.round(c.wind_speed_10m)} mph, weather_code ${c.weather_code}. Today high ${Math.round(d.temperature_2m_max?.[0])}°F / low ${Math.round(d.temperature_2m_min?.[0])}°F.`;
      }
    } catch {}
  }
  // General: Firecrawl search (real web results).
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
      if (uris.length) { await spotify.play({ uris, deviceId }); return "playing your liked songs"; }
    }
    // named playlist
    const pls = await spotify.playlists(50);
    const pl = pls.find((p: any) => { const n = String(p.name || "").toLowerCase(); return n && (q.includes(n) || n.includes(q)); });
    if (pl) { await spotify.play({ contextUri: pl.uri, deviceId }); return `playing the ${pl.name} playlist`; }
    // search (song / artist / genre like "jazz")
    const uris = (await spotify.search(query, 25)).map((t: any) => t.uri).filter(Boolean).slice(0, 30);
    if (uris.length) { await spotify.play({ uris, deviceId }); return `playing ${query} on Spotify`; }
    return `I couldn't find ${query} on Spotify`;
  } catch {
    await run("soloist", ["ctl", "play"]); return "playing Spotify";
  }
}

async function execActions(actions: any[]): Promise<string[]> {
  const done: string[] = [];
  for (const a of actions || []) {
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

// ---- main entry ------------------------------------------------------------
export async function runAgent(text: string): Promise<{ reply: string; actions: string[]; understood: boolean }> {
  const state = JSON.stringify(home.summary());
  // Pre-search obvious live-info questions so they're a single LLM round-trip (faster).
  const needsLive = /weather|forecast|temperatur|rain|snow|news|headline|today|tonight|latest|score|who won|standings|game|price|stock|how much|right now|currently|open now|hours|what time|near me/i.test(text);
  let pre = "";
  if (needsLive) {
    const results = await webSearch(text);
    pre = `\nWeb results (use these, don't ask to search again):\n${results}\n`;
  }
  const p1 = `${SYSTEM}\n\nHome state: ${state}${pre}\nUser said: "${text}"`;
  let out = parseJson(await ccut(p1)) || {};
  // fallback: one web-search round-trip if the model still asks for one
  if (out.web_search && !String(out.say || "").trim()) {
    const results = await webSearch(String(out.web_search));
    const p2 = `${SYSTEM}\n\nHome state: ${state}\nUser said: "${text}"\n\nYou asked to search; here are results:\n${results}\n\nNow answer. Respond with the JSON object (put the answer in "say").`;
    out = parseJson(await ccut(p2)) || out;
  }
  console.log("[agent] llm out:", JSON.stringify({ say: out.say, actions: out.actions, web_search: out.web_search }));
  const done = await execActions(out.actions || []);
  let reply = String(out.say || "").trim();
  if (!reply) reply = done.length ? "Done." : "Okay.";
  return { reply, actions: done, understood: done.length > 0 || !!out.say };
}

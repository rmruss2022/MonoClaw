/**
 * open-home hub — entry point.
 *
 * Zero-dependency skeleton so the repo runs on a fresh checkout with just Node 20+.
 * As the project grows this gets swapped for Fastify + a real MQTT bus (see ARCHITECTURE.md),
 * but the shape — HTTP API + realtime + agent loop + device bus — stays the same.
 *
 * Serves both the JSON API and the dashboard (apps/app) from the same origin, so the
 * UI needs no CORS and there is a single URL to hit.
 */
import { createServer } from "node:http";
import { createServer as createHttpsServer } from "node:https";
import { readFile } from "node:fs/promises";
import { readFileSync } from "node:fs";
import { EventBus } from "./bus.ts";
import { Agent } from "./agent.ts";
import { docsIndexHtml, docPageHtml } from "./docs.ts";
import * as home from "./home.ts";
import * as ai from "./ai.ts";
import * as voiceagent from "./voiceagent.ts";
import * as audio from "./audio.ts";
import * as spotify from "./spotify.ts";
import * as curator from "./curator.ts";
import * as speakerService from "./speakerService.ts";
import * as localAudio from "./localAudio.ts";
import * as calibration from "./calibration.ts";
import * as snapcast from "./snapcast.ts";
import * as pwRouter from "./pwRouter.ts";
import * as lights from "./lights.ts";
import * as party from "./party.ts";
import * as localLights from "./localLights.ts";
import * as hub from "./hub.ts";
import * as climate from "./climate.ts";
import * as localClimate from "./localClimate.ts";
import * as devEmulator from "./devEmulator.ts";
import * as auth from "./auth.ts";

const PORT = Number(process.env.OPEN_HOME_PORT ?? 4700);
// The account/identity service. The hub proxies email+password sign-in to it so
// home.bedrock.casa is the ONE site — the cloud stays an invisible backend.
const CLOUD_URL = process.env.OPEN_HOME_CLOUD_URL || "https://openhome-cloud-production.up.railway.app";
// The TV content-router. The hub proxies the web TV tab to it with the user's
// existing session (oh_auth), so the TV tab needs no second login.
const TV_ROUTER_URL = process.env.OPEN_HOME_TV_URL || "https://openhome-tv-production.up.railway.app";
const HTTPS_PORT = Number(process.env.OPEN_HOME_HTTPS_PORT ?? 4443);
// Dev mode gates in-app test tooling (e.g. the emulated "test thermostat" button).
// Off by default; enable with OPEN_HOME_DEV=1.
const DEV = process.env.OPEN_HOME_DEV === "1";
const DASHBOARD = new URL("../../../apps/app/index.html", import.meta.url);
const CONTROL = new URL("../../../apps/app/control.html", import.meta.url);
const MUSIC = new URL("../../../apps/app/music.html", import.meta.url);
const SPEAKERS = new URL("../../../apps/app/speakers.html", import.meta.url);
const LIGHTS = new URL("../../../apps/app/lights.html", import.meta.url);
const SETUP = new URL("../../../apps/app/setup.html", import.meta.url);
const CLIMATE = new URL("../../../apps/app/climate.html", import.meta.url);
const TV = new URL("../../../apps/app/tv.html", import.meta.url);

function readBody(req: import("node:http").IncomingMessage): Promise<string> {
  return new Promise((resolve) => {
    let data = "";
    req.on("data", (c) => { data += c; if (data.length > 8e6) req.destroy(); });
    req.on("end", () => resolve(data));
    req.on("error", () => resolve(""));
  });
}

const bus = new EventBus();
const agent = new Agent(bus);
void spotify.load(); // restore Spotify sign-in from disk if present

// Heartbeat so the event feed isn't empty on first run.
setInterval(() => {
  bus.publish({ type: "hub.heartbeat", ts: Date.now(), payload: { ok: true } });
}, 15_000);

// Ambient simulator — the mock house nudges itself so the feed feels like a real home.
setInterval(() => {
  const ev = home.simulateTick(Date.now());
  if (ev) bus.publish({ type: ev.type, ts: Date.now(), payload: ev.payload });
}, 12_000);

// Advance the music playhead so the now-playing UI feels live.
setInterval(() => audio.tick(2_000), 2_000);

// Mirror Spotify's real playback into Now Playing when signed in. (Skipped while
// rate-limited so we don't pile onto a 429.)
setInterval(async () => {
  if (!spotify.connected() || spotify.rateLimited()) return;
  try { const np = await spotify.currentlyPlaying(); if (np) audio.applySpotifyPlayback(np); } catch {}
}, 12_000);

// Keep the live Connect devices (Mac/iPhone/…) synced into the speaker model.
speakerService.refresh().catch(() => {});
setInterval(() => { if (!spotify.rateLimited()) speakerService.refresh().catch(() => {}); }, 15_000);

// Maintain onboarded local Wi-Fi/Bluetooth speakers — reconnect on drop.
setInterval(() => { localAudio.maintain().catch(() => {}); }, 15_000);

// Maintain onboarded local lights (ESPHome/Matter) — reconnect on drop.
setInterval(() => { localLights.maintain().catch(() => {}); }, 15_000);

// Maintain onboarded thermostats (ESPHome/Matter) — reconnect on drop.
setInterval(() => { localClimate.maintain().catch(() => {}); }, 15_000);

// Mirror agent/scene thermostat changes onto the real primary thermostat.
setInterval(() => { climate.syncMockToPrimary().catch(() => {}); }, 4_000);

// Poll the Snapcast server (synchronized multi-room), if one is running.
snapcast.refresh().catch(() => {});
setInterval(() => { snapcast.refresh().catch(() => {}); }, 20_000);

function spotifyHint(m: string): string {
  if (m.includes("rate_limited")) return "Spotify is rate-limiting us — pausing a moment, try again shortly.";
  if (m.includes("no_device") || m.includes("404")) return "no_device";
  if (m.includes("403")) return "Spotify needs Premium for remote playback.";
  return "Couldn't reach Spotify — try again.";
}
function json(res: import("node:http").ServerResponse, body: unknown, code = 200): void {
  res.statusCode = code;
  res.setHeader("Content-Type", "application/json");
  res.end(JSON.stringify(body));
}

const handler = async (req: import("node:http").IncomingMessage, res: import("node:http").ServerResponse) => {
  const url = (req.url ?? "/").split("?")[0];

  // --- Access gate ---------------------------------------------------------
  // When a passphrase is configured the hub is private: every route except the
  // login flow and /health requires a valid signed session cookie. Disabled
  // automatically when OPEN_HOME_PASSWORD is unset (fresh local dev).
  if (auth.enabled()) {
    // Optional network allowlist (CF-Connecting-IP) — a belt-and-suspenders
    // layer on top of the passphrase. No-op unless OPEN_HOME_ALLOW_IPS is set.
    if (auth.ipBlocked(req)) {
      res.statusCode = 403;
      res.setHeader("Content-Type", "text/plain; charset=utf-8");
      res.end("Forbidden — this home only accepts connections from approved networks.");
      return;
    }
    if (url === "/login") {
      if (req.method === "POST") {
        const body = await readBody(req);
        const pw = new URLSearchParams(body).get("password") ?? "";
        // Native/API clients ask for JSON and get the session token in the body
        // (they replay it as the oh_auth cookie); browsers get the usual redirect.
        const wantsJson = (req.headers.accept ?? "").includes("application/json");
        const ok = auth.checkPassword(pw);
        if (ok) {
          const token = auth.makeToken();
          res.setHeader("Set-Cookie", auth.setCookieHeader(token));
          if (wantsJson) {
            json(res, { ok: true, token });
          } else {
            res.statusCode = 302;
            res.setHeader("Location", "/");
            res.end();
          }
        } else if (wantsJson) {
          json(res, { ok: false, error: "bad_password" }, 401);
        } else {
          res.statusCode = 401;
          res.setHeader("Content-Type", "text/html; charset=utf-8");
          res.setHeader("Cache-Control", "no-store");
          res.end(auth.loginPage("Wrong passphrase. Try again."));
        }
        return;
      }
      res.statusCode = 200;
      res.setHeader("Content-Type", "text/html; charset=utf-8");
      res.setHeader("Cache-Control", "no-store");
      res.end(auth.loginPage());
      return;
    }
    if (url === "/logout") {
      res.statusCode = 302;
      res.setHeader("Set-Cookie", auth.clearCookieHeader());
      res.setHeader("Location", "/login");
      res.end();
      return;
    }
    // Account sign-in (email+password) — proxied to the cloud identity service so
    // this one site handles it. On success we store the home grant as oh_auth.
    if (url === "/account-login" && req.method === "POST") {
      let email = "", password = "";
      try { const p = JSON.parse((await readBody(req)) || "{}"); email = String(p.email ?? ""); password = String(p.password ?? ""); } catch {}
      try {
        const lr = await fetch(`${CLOUD_URL}/api/login`, {
          method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ email, password }),
        });
        const lj: any = await lr.json().catch(() => ({}));
        if (!lj.ok || !lj.token) { json(res, { ok: false, error: "bad_login" }, 401); return; }
        const hr = await fetch(`${CLOUD_URL}/api/home`, { headers: { Authorization: `Bearer ${lj.token}` } });
        const hj: any = await hr.json().catch(() => ({}));
        if (!hj.ok || !hj.homeToken) { json(res, { ok: false, error: "no_home" }, 400); return; }
        res.setHeader("Set-Cookie", auth.setCookieHeader(hj.homeToken));
        json(res, { ok: true });
      } catch {
        json(res, { ok: false, error: "cloud_unreachable" }, 502);
      }
      return;
    }
    // Single sign-on hand-off from the openhome-cloud control-plane. The cloud
    // app signs the user in, then hands them here with a valid home token; we
    // store it as the session cookie and drop them into the house — no passphrase.
    if (url === "/sso") {
      let token = "";
      if (req.method === "POST") {
        token = new URLSearchParams(await readBody(req)).get("token") ?? "";
      } else {
        token = new URL(req.url ?? "/", "http://x").searchParams.get("token") ?? "";
      }
      res.statusCode = 302;
      if (auth.validHomeToken(token)) {
        res.setHeader("Set-Cookie", auth.setCookieHeader(token));
        res.setHeader("Location", "/");
      } else {
        res.setHeader("Location", "/login");
      }
      res.end();
      return;
    }
    if (url !== "/health" && !auth.cookieAuthed(req)) {
      const accept = req.headers.accept ?? "";
      if (accept.includes("text/html")) {
        res.statusCode = 302;
        res.setHeader("Location", "/login");
        res.end();
      } else {
        json(res, { error: "unauthorized", login: "/login" }, 401);
      }
      return;
    }
  }

  // Home = the control surface (same-origin UI)
  if (url === "/") {
    try {
      const html = await readFile(CONTROL, "utf8");
      res.statusCode = 200;
      res.setHeader("Content-Type", "text/html; charset=utf-8");
      res.setHeader("Cache-Control", "no-store");
      res.end(html);
      return;
    } catch {
      json(res, { error: "control_not_found" }, 500);
      return;
    }
  }

  // Legacy hub dashboard (status / devices / event stream)
  if (url === "/dashboard" || url === "/index.html") {
    try {
      const html = await readFile(DASHBOARD, "utf8");
      res.statusCode = 200;
      res.setHeader("Content-Type", "text/html; charset=utf-8");
      res.setHeader("Cache-Control", "no-store");
      res.end(html);
      return;
    } catch {
      json(res, { error: "dashboard_not_found" }, 500);
      return;
    }
  }

  // Voice/text agent — the AI brain drives the house; keyword NLU is the fallback.
  if (url === "/agent" && req.method === "POST") {
    const body = await readBody(req);
    let text = "";
    try { text = String(JSON.parse(body || "{}").text ?? ""); } catch {}
    // Real conversational agent (Claude via ccut gateway) — home control + web search.
    if (voiceagent.enabled() && text.trim()) {
      try {
        const r = await voiceagent.runAgent(text);
        console.log(`[agent] (ccut) in=${JSON.stringify(text)} actions=${JSON.stringify(r.actions)} reply=${JSON.stringify(r.reply)}`);
        json(res, { ok: true, heard: text, reply: r.reply, understood: r.understood, actions: r.actions, source: "agent", summary: home.summary() });
        return;
      } catch (e) { console.log("[agent] ccut error:", (e as Error)?.message); }
    }
    if (ai.aiEnabled()) {
      try {
        const r = await ai.aiText(text);
        const done = await ai.execute(r.actions);
        console.log(`[agent] in=${JSON.stringify(text)} model=${JSON.stringify(r.actions)} executed=${JSON.stringify(done)} reply=${JSON.stringify(r.reply)}`);
        done.forEach((a) => bus.publish({ type: `agent.${a.label}`, ts: Date.now(), payload: { via: "voice", text } }));
        json(res, { ok: true, heard: text, reply: r.reply, understood: done.length > 0, actions: done, source: "ai", summary: home.summary() });
        return;
      } catch (e) { console.log("[agent] AI error:", (e as Error)?.message); }
    }
    const r = home.respond(text);
    bus.publish({ type: r.action ? `agent.${r.action}` : "agent.unrecognized", ts: Date.now(), payload: { via: "voice", text } });
    json(res, { ok: true, heard: text, ...r, source: "keyword", summary: home.summary() });
    return;
  }

  // Voice agent — real speech: browser sends captured audio, Gemini transcribes + acts.
  if (url === "/agent/audio" && req.method === "POST") {
    if (!ai.aiEnabled()) { console.log("[agent/audio] rejected: ai_disabled"); json(res, { ok: false, error: "ai_disabled" }, 503); return; }
    const body = await readBody(req);
    let audio = "", mime = "audio/webm";
    try { const p = JSON.parse(body || "{}"); audio = String(p.audio ?? ""); mime = String(p.mime ?? mime); } catch {}
    console.log(`[agent/audio] received b64bytes=${audio.length} mime=${mime}`);
    if (!audio) { json(res, { ok: false, error: "empty_audio", reply: "I didn't catch any audio — hold a moment longer." }, 200); return; }
    try {
      const r = await ai.aiAudio(audio, mime);
      const done = await ai.execute(r.actions);
      console.log(`[agent/audio] transcript=${JSON.stringify(r.transcript)} model=${JSON.stringify(r.actions)} executed=${JSON.stringify(done)}`);
      done.forEach((a) => bus.publish({ type: `agent.${a.label}`, ts: Date.now(), payload: { via: "audio" } }));
      json(res, { ok: true, transcript: r.transcript ?? "", reply: r.reply, actions: done, source: "ai-audio", summary: home.summary() });
    } catch (e) { console.log("[agent/audio] AI error:", (e as Error)?.message); json(res, { ok: false, error: "ai_error" }, 502); }
    return;
  }

  // Client-side voice diagnostics (so we can see where iOS mic capture fails).
  if (url === "/debug/voice" && req.method === "POST") {
    const body = await readBody(req);
    console.log("[voice-debug]", body.slice(0, 400));
    json(res, { ok: true });
    return;
  }

  // Radial gesture control surface
  if (url === "/control") {
    if (req.method === "POST") {
      const body = await readBody(req);
      let action = "unknown", angle: number | undefined;
      try { const p = JSON.parse(body || "{}"); action = String(p.action ?? "unknown"); angle = p.angle; } catch {}
      const result = home.control(action);
      bus.publish({ type: `control.${action}`, ts: Date.now(), payload: { via: "radial", angle, ...result } });
      json(res, { ok: true, action, ...result, summary: home.summary() });
      return;
    }
    try {
      const html = await readFile(CONTROL, "utf8");
      res.statusCode = 200;
      res.setHeader("Content-Type", "text/html; charset=utf-8");
      res.setHeader("Cache-Control", "no-store");
      res.end(html);
    } catch {
      json(res, { error: "control_not_found" }, 500);
    }
    return;
  }

  // Music app (same-origin UI)
  if (url === "/music" || url === "/music.html") {
    try {
      const html = await readFile(MUSIC, "utf8");
      res.statusCode = 200;
      res.setHeader("Content-Type", "text/html; charset=utf-8");
      res.setHeader("Cache-Control", "no-store");
      res.end(html);
    } catch {
      json(res, { error: "music_not_found" }, 500);
    }
    return;
  }
  if (url === "/speakers" || url === "/speakers.html") {
    try {
      const html = await readFile(SPEAKERS, "utf8");
      res.statusCode = 200;
      res.setHeader("Content-Type", "text/html; charset=utf-8");
      res.setHeader("Cache-Control", "no-store");
      res.end(html);
    } catch {
      json(res, { error: "speakers_not_found" }, 500);
    }
    return;
  }
  if (url === "/lights" || url === "/lights.html") {
    try {
      const html = await readFile(LIGHTS, "utf8");
      res.statusCode = 200;
      res.setHeader("Content-Type", "text/html; charset=utf-8");
      res.setHeader("Cache-Control", "no-store");
      res.end(html);
    } catch {
      json(res, { error: "lights_not_found" }, 500);
    }
    return;
  }
  if (url === "/climate" || url === "/climate.html") {
    try {
      const html = await readFile(CLIMATE, "utf8");
      res.statusCode = 200;
      res.setHeader("Content-Type", "text/html; charset=utf-8");
      res.setHeader("Cache-Control", "no-store");
      res.end(html);
    } catch {
      json(res, { error: "climate_not_found" }, 500);
    }
    return;
  }
  // TV content-router, served under this one front door. The browser "TV"
  // (/mock), the standalone remote (/remote) and every router API they call use
  // location.origin, so proxying these paths lets the whole TV stack live on
  // home.bedrock.casa instead of the raw Railway URL. The pages carry their own
  // router tokens in Authorization (passed through), and the SSE stream is piped
  // rather than buffered so the mock TV updates live.
  {
    const isTvRouter =
      url === "/mock" || url === "/remote" || url === "/remote/login" ||
      url === "/sticks" || url === "/trending" || url === "/route" || url === "/search" ||
      url.startsWith("/stick/") || url.startsWith("/sticks/") || url.startsWith("/title/");
    if (isTvRouter) {
      const fullPath = req.url ?? "/"; // keep the query string
      const method = req.method ?? "GET";
      const body = method === "POST" ? await readBody(req) : undefined;
      const isStream = url.startsWith("/stick/") && url.endsWith("/stream");
      const authz = req.headers["authorization"];
      try {
        const r = await fetch(`${TV_ROUTER_URL}${fullPath}`, {
          method,
          headers: {
            Accept: isStream ? "text/event-stream" : "*/*",
            ...(method === "POST" ? { "Content-Type": "application/json" } : {}),
            ...(authz ? { Authorization: String(authz) } : {}),
          },
          body,
        });
        if (isStream && r.body) {
          res.statusCode = r.status;
          res.setHeader("Content-Type", "text/event-stream");
          res.setHeader("Cache-Control", "no-store");
          res.setHeader("Connection", "keep-alive");
          const { Readable } = await import("node:stream");
          Readable.fromWeb(r.body as any).pipe(res);
          return;
        }
        const text = await r.text();
        res.statusCode = r.status;
        res.setHeader("Content-Type", r.headers.get("content-type") || "application/json");
        res.setHeader("Cache-Control", "no-store");
        res.end(text);
      } catch {
        json(res, { error: "tv_router_unreachable" }, 502);
      }
      return;
    }
  }
  // TV tab proxy: forward /tv/api/* to the content-router with the user's session
  // grant (oh_auth) as the Bearer token — no second login on the TV tab.
  if (url.startsWith("/tv/api/")) {
    const fullPath = (req.url ?? "/").slice("/tv/api".length); // keeps the query string
    const token = auth.parseCookies(req.headers.cookie)[auth.cookieName()] ?? "";
    const method = req.method ?? "GET";
    const body = method === "POST" ? await readBody(req) : undefined;
    try {
      const r = await fetch(`${TV_ROUTER_URL}${fullPath}`, {
        method,
        headers: { Accept: "application/json", "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body,
      });
      const text = await r.text();
      res.statusCode = r.status;
      res.setHeader("Content-Type", "application/json");
      res.setHeader("Cache-Control", "no-store");
      res.end(text);
    } catch {
      json(res, { error: "tv_router_unreachable" }, 502);
    }
    return;
  }
  if (url === "/tv" || url === "/tv.html") {
    try {
      const html = await readFile(TV, "utf8");
      res.statusCode = 200;
      res.setHeader("Content-Type", "text/html; charset=utf-8");
      res.setHeader("Cache-Control", "no-store");
      res.end(html);
    } catch {
      json(res, { error: "tv_not_found" }, 500);
    }
    return;
  }
  if (url === "/setup" || url === "/setup.html" || url === "/welcome") {
    try {
      const html = await readFile(SETUP, "utf8");
      res.statusCode = 200;
      res.setHeader("Content-Type", "text/html; charset=utf-8");
      res.setHeader("Cache-Control", "no-store");
      res.end(html);
    } catch {
      json(res, { error: "setup_not_found" }, 500);
    }
    return;
  }

  // Static assets (images for docs/dashboard)
  if (url.startsWith("/assets/")) {
    const name = url.slice("/assets/".length);
    // allow one level of subfolder (e.g. brand/logo.svg); block traversal
    if (!/^[a-zA-Z0-9._-]+(\/[a-zA-Z0-9._-]+)?$/.test(name) || name.includes("..")) {
      json(res, { error: "bad_asset" }, 400); return;
    }
    const types: Record<string, string> = {
      ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
      ".webp": "image/webp", ".svg": "image/svg+xml",
      ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
    };
    const ext = name.slice(name.lastIndexOf("."));
    try {
      const buf = await readFile(new URL(`../../../apps/app/assets/${name}`, import.meta.url));
      res.statusCode = 200;
      res.setHeader("Content-Type", types[ext] ?? "application/octet-stream");
      res.setHeader("Cache-Control", "no-store");
      res.end(buf);
    } catch {
      json(res, { error: "asset_not_found", name }, 404);
    }
    return;
  }

  // Docs pages (rendered from the real .md files)
  if (url === "/docs" || url === "/docs/") {
    res.statusCode = 200;
    res.setHeader("Content-Type", "text/html; charset=utf-8");
    res.end(docsIndexHtml());
    return;
  }
  if (url.startsWith("/docs/")) {
    const slug = url.slice("/docs/".length).replace(/\/+$/, "");
    const html = await docPageHtml(slug);
    if (html) {
      res.statusCode = 200;
      res.setHeader("Content-Type", "text/html; charset=utf-8");
      res.setHeader("Cache-Control", "no-store");
      res.end(html);
    } else {
      json(res, { error: "doc_not_found", slug }, 404);
    }
    return;
  }

  // JSON API
  if (url === "/health") {
    json(res, { status: "ok", service: "open-home-hub", uptime: process.uptime(), model: agent.modelLabel, devices: home.summary().devices });
    return;
  }
  if (url === "/devices") {
    // Merge real onboarded thermostats; hide the mock thermostat when a real one exists.
    const rows = climate.deviceRows();
    let devices = home.flat();
    const sum = home.summary();
    if (rows.length) {
      devices = devices.filter((d: any) => d.id !== "thermostat_main").concat(rows as any);
      sum.devices = devices.length;
    }
    json(res, { devices, summary: sum });
    return;
  }
  if (url === "/home") {
    json(res, home.snapshot());
    return;
  }
  if (url === "/scenes") {
    if (req.method === "POST") {
      const body = await readBody(req);
      let id = "";
      try { id = String(JSON.parse(body || "{}").id ?? ""); } catch {}
      const scene = home.activateScene(id);
      bus.publish({ type: `scene.${id}`, ts: Date.now(), payload: { via: "api" } });
      json(res, { ok: true, scene, summary: home.summary() });
      return;
    }
    json(res, { scenes: home.getScenes() });
    return;
  }
  // Set an individual device: POST /device { id, patch }
  if (url === "/device" && req.method === "POST") {
    const body = await readBody(req);
    let id = "", patch: Record<string, unknown> = {};
    try { const p = JSON.parse(body || "{}"); id = String(p.id ?? ""); patch = p.patch ?? {}; } catch {}
    const dev = home.setDevice(id, patch);
    if (!dev) { json(res, { error: "device_not_found", id }, 404); return; }
    bus.publish({ type: `device.${id}`, ts: Date.now(), payload: patch });
    json(res, { ok: true, device: dev });
    return;
  }
  if (url === "/events/recent") {
    json(res, { events: bus.recent() });
    return;
  }

  // ---- Speaker service / music ----
  if (url === "/speakers") { json(res, { speakers: audio.listSpeakers(), zones: audio.listZones() }); return; }
  if (url === "/audio/state") { json(res, audio.state()); return; }
  // PipeWire output router — openhome's own audio routing (no Spotify device-picker).
  if (url === "/audio/outputs") { json(res, await pwRouter.status()); return; }
  if (url === "/audio/spotify/search") {
    const q = new URL(req.url ?? "/", "http://x").searchParams.get("q") ?? "";
    if (spotify.connected()) { try { json(res, { tracks: await spotify.search(q, 20) }); return; } catch (e) { console.log("[spotify] search error:", (e as Error).message); } }
    json(res, { tracks: audio.spotifySearch(q) }); return;
  }
  // --- Spotify OAuth + account ---
  if (url === "/audio/spotify/login") {
    if (!spotify.configured()) { json(res, { error: "not_configured", need: ["SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "SPOTIFY_REDIRECT_URI"], redirectUri: spotify.redirectUri() }, 503); return; }
    res.statusCode = 302; res.setHeader("Location", spotify.authUrl("openhome")); res.end(); return;
  }
  if (url === "/audio/spotify/callback") {
    const code = new URL(req.url ?? "/", "http://x").searchParams.get("code") ?? "";
    const ok = code ? await spotify.exchangeCode(code).catch(() => false) : false;
    bus.publish({ type: "audio.spotify-signin", ts: Date.now(), payload: { ok } });
    res.statusCode = 302; res.setHeader("Location", ok ? "/music?spotify=ok" : "/music?spotify=fail"); res.end(); return;
  }
  if (url === "/audio/spotify/me") { try { json(res, { profile: await spotify.me() }); } catch { json(res, { profile: null }, 401); } return; }
  if (url === "/audio/spotify/playlists") { try { json(res, { playlists: await spotify.playlists() }); } catch { json(res, { playlists: [] }, 401); } return; }
  if (url === "/audio/spotify/liked") { try { json(res, { tracks: await spotify.liked() }); } catch { json(res, { tracks: [] }, 401); } return; }
  if (url === "/audio/spotify/top") { try { json(res, { tracks: await spotify.topTracks() }); } catch { json(res, { tracks: [] }, 401); } return; }
  if (url === "/audio/spotify/playlist") {
    const id = new URL(req.url ?? "/", "http://x").searchParams.get("id") ?? "";
    try { json(res, { tracks: await spotify.playlistTracks(id) }); } catch { json(res, { tracks: [] }, 401); } return;
  }
  if (url === "/audio/spotify/devices") { try { json(res, { devices: await spotify.devices() }); } catch { json(res, { devices: [] }, 401); } return; }
  if (url === "/audio/spotify/token") { try { json(res, await spotify.webToken()); } catch { json(res, { error: "not_connected" }, 401); } return; }
  if (url === "/audio/curator") {
    const qs = new URL(req.url ?? "/", "http://x").searchParams;
    const mood = qs.get("mood") ?? "";
    const force = qs.get("force") === "1" || qs.get("refresh") === "1";
    try { json(res, { picks: await curator.curate(mood, force), ai: curator.enabled(), cachedAt: curator.cachedAt(mood) }); } catch { json(res, { picks: [] }, 500); }
    return;
  }
  if (url === "/audio/spotify/home") {
    try {
      const [pl, liked, top] = await Promise.all([spotify.playlists(), spotify.liked(), spotify.topTracks()]);
      const isSpotify = (p: any) => String(p.ownerId || p.owner || "").toLowerCase() === "spotify";
      json(res, { mixes: pl.filter(isSpotify), playlists: pl.filter((p: any) => !isSpotify(p)), liked, top });
    } catch { json(res, { mixes: [], playlists: [], liked: [], top: [] }, 401); }
    return;
  }
  if (url === "/audio/spotify/disconnect" && req.method === "POST") { spotify.disconnect(); json(res, { ok: true }); return; }
  if (url === "/audio/discover") {
    const kind = (new URL(req.url ?? "/", "http://x").searchParams.get("kind") ?? "wifi") as "wifi" | "bluetooth";
    if (kind === "bluetooth") {
      const r = await localAudio.scanBluetooth();
      json(res, { found: r.devices, available: r.available, note: r.available ? undefined : r.reason }); return;
    }
    const found = await localAudio.scanWifi();
    json(res, { found, note: found.length ? undefined : "No speakers answered on this network. Run the hub on the same LAN as your speakers to find them." }); return;
  }

  // ---- Hub onboarding / status ----
  if (url === "/hub/status") { json(res, await hub.status(agent.modelLabel)); return; }
  if (url === "/hub/command" && req.method === "POST") {
    const body = await readBody(req);
    let p: any = {}; try { p = JSON.parse(body || "{}"); } catch {}
    const cmd = String(p.cmd ?? "");
    let hint: string | undefined, cfg = hub.config();
    switch (cmd) {
      case "name-home": { cfg = hub.setHomeName(String(p.name ?? "")); hint = `Home named “${cfg.homeName}”`; break; }
      case "complete-setup": { cfg = hub.completeSetup(); hint = "Setup complete"; break; }
      case "reset-setup": { cfg = hub.resetSetup(); hint = "Setup reset"; break; }
      default: hint = "Unknown command";
    }
    json(res, { ok: true, hint, config: cfg }); return;
  }

  // ---- Climate / thermostat service ----
  if (url === "/climate/state") { json(res, { ...climate.state(), capabilities: await climate.capabilities(), dev: DEV }); return; }
  if (url.startsWith("/climate/discover")) {
    const backend = (new URL(req.url ?? "/", "http://x").searchParams.get("backend") ?? "esphome") as "esphome" | "matter";
    const found = await localClimate.scan(backend);
    const caps = await climate.capabilities();
    const available = backend === "matter" ? caps.matter : true;
    json(res, { found, available, note: found.length ? undefined : (backend === "matter" && !caps.matter ? "No Matter controller on the hub yet — pairing needs chip-tool/matter-server (see Setup). Run the hub on your Pi." : "No thermostats answered on this network. Run the hub on the same LAN as your thermostat.") }); return;
  }
  if (url === "/climate/command" && req.method === "POST") {
    const body = await readBody(req);
    let p: any = {}; try { p = JSON.parse(body || "{}"); } catch {}
    const cmd = String(p.cmd ?? "");
    let hint: string | undefined;
    switch (cmd) {
      case "set-temp": { const r = await climate.control(String(p.id), { targetF: Number(p.targetF) }); if (!r.ok) hint = r.reason; break; }
      case "set-mode": { const r = await climate.control(String(p.id), { mode: p.mode }); if (!r.ok) hint = r.reason; break; }
      case "climate-room": { climate.setRoom(String(p.id), String(p.room ?? "—")); break; }
      case "rename-thermostat": { climate.rename(String(p.id), String(p.name ?? "")); hint = "Renamed"; break; }
      case "onboard-thermostat": { const t = localClimate.onboard(p.device || {}, String(p.room ?? "Hallway")); hint = `Added ${t.name} to ${t.room}`; break; }
      case "reconnect-thermostat": { const t = await localClimate.reconnect(String(p.id)); hint = t ? `${t.name}: ${t.status}` : "not found"; break; }
      case "remove-thermostat": { localClimate.remove(String(p.id)); break; }
      case "add-demo-thermostat": {
        if (!DEV) { hint = "Dev mode is off (set OPEN_HOME_DEV=1)"; break; }
        const em = await devEmulator.ensure();
        const n = localClimate.list().filter((t) => (t.entity || "").startsWith("demo")).length + 1;
        const entity = "demo" + n;
        devEmulator.addEntity(entity, n - 1);
        const rooms = ["Living Room", "Bedroom", "Kitchen", "Office"];
        const room = rooms[(n - 1) % rooms.length];
        const t = localClimate.onboard({ name: "Test Thermostat " + n, backend: "esphome", address: em.host, port: em.port, entity }, room);
        hint = `Added ${t.name} (emulated) to ${room}`;
        break;
      }
      case "clear-demo-thermostats": {
        if (!DEV) { hint = "Dev mode is off"; break; }
        let k = 0;
        for (const t of localClimate.list()) if ((t.entity || "").startsWith("demo")) { localClimate.remove(t.id); devEmulator.removeEntity(t.entity!); k++; }
        hint = `Removed ${k} test thermostat${k === 1 ? "" : "s"}`;
        break;
      }
      default: hint = "Unknown command";
    }
    json(res, { ok: true, hint, state: climate.state() }); return;
  }

  // ---- Lights service ----
  if (url === "/lights/state") { json(res, { ...lights.state(), capabilities: await lights.capabilities() }); return; }
  if (url.startsWith("/lights/discover")) {
    const backend = (new URL(req.url ?? "/", "http://x").searchParams.get("backend") ?? "esphome") as "esphome" | "matter";
    if (backend === "matter") {
      const cap = await lights.capabilities();
      const found = await localLights.scanMatter();
      json(res, { found, available: cap.matter, note: found.length ? undefined : (cap.matter ? "No Matter nodes answered. Commission a device first, or check it's on this LAN." : "No Matter controller on the hub yet — discovery works on the LAN, but control needs chip-tool/matter-server (see Setup). Run the hub on your Pi.") }); return;
    }
    const found = await localLights.scanEsphome();
    json(res, { found, available: true, note: found.length ? undefined : "No ESPHome lights answered on this network. Run the hub on the same LAN as your lights to find them." }); return;
  }
  if (url === "/lights/command" && req.method === "POST") {
    const body = await readBody(req);
    let p: any = {}; try { p = JSON.parse(body || "{}"); } catch {}
    const cmd = String(p.cmd ?? "");
    let hint: string | undefined;
    // Any real light change ends the party first (so "set the lights green" takes over),
    // except brightness (which can ride along) and the party command itself.
    if (party.isOn() && cmd !== "party" && cmd !== "brightness") party.stop(false);
    switch (cmd) {
      case "toggle": { const r = await lights.control(String(p.id), { on: !!p.on }); if (!r.ok) hint = r.reason; break; }
      case "brightness": { const r = await lights.control(String(p.id), { brightness: Number(p.brightness) }); if (!r.ok) hint = r.reason; break; }
      case "color": { const r = await lights.control(String(p.id), { rgb: p.rgb }); if (!r.ok) hint = r.reason; break; }
      case "temp": { const r = await lights.control(String(p.id), { colorTempK: Number(p.colorTempK) }); if (!r.ok) hint = r.reason; break; }
      case "light-room": { lights.setRoom(String(p.id), String(p.room ?? "—")); break; }
      case "room-power": { const n = await lights.setRoomPower(String(p.room ?? ""), !!p.on); hint = `${p.on ? "On" : "Off"} · ${n} light${n === 1 ? "" : "s"}`; break; }
      case "party": {
        if (p.on === false) { party.stop(); hint = "Party over"; }
        else { const r = await party.start(); hint = `Party on · ${r.lights} light${r.lights === 1 ? "" : "s"} @ ${Math.round(60000 / r.intervalMs)} fpm`; }
        break;
      }
      case "scene": { const s = home.activateScene(String(p.id)); hint = (s as any).name ? `${(s as any).name} scene` : undefined; break; }
      case "onboard-light": { const l = localLights.onboard(p.device || {}, String(p.room ?? "Living Room")); hint = `Added ${l.name} to ${l.room}`; break; }
      case "reconnect-light": { const l = await localLights.reconnect(String(p.id)); hint = l ? `${l.name}: ${l.status}` : "not found"; break; }
      case "remove-light": { localLights.remove(String(p.id)); break; }
      case "rename-light": { lights.rename(String(p.id), String(p.name ?? "")); hint = "Renamed"; break; }
      case "identify-light": { const r = await lights.identify(String(p.id)); hint = r.ok ? "Blinking…" : r.reason; break; }
      case "commission-light": { const r = await localLights.commission({ code: String(p.code ?? ""), name: p.name, room: p.room }); hint = r.ok ? `Paired ${r.light?.name}` : r.reason; break; }
      default: hint = "Unknown command";
    }
    json(res, { ok: true, hint, state: lights.state() }); return;
  }
  if (url === "/audio/command" && req.method === "POST") {
    const body = await readBody(req);
    let p: any = {};
    try { p = JSON.parse(body || "{}"); } catch {}
    const cmd = String(p.cmd ?? "");
    let result: unknown = null;
    let hint: string | undefined;
    switch (cmd) {
      case "transport": {
        if (spotify.connected()) {
          try {
            if (p.action === "seek") await spotify.seek(Number(p.ms) || 0);
            else await spotify.transportRemote(p.action === "prev" ? "previous" : p.action);
          } catch (e) { const m = (e as Error).message || ""; if (m.includes("no_device") || m.includes("404")) hint = "no_device"; else if (m.includes("rate_limited")) hint = "Spotify is busy — give it a moment."; }
        }
        result = audio.transport(p.action, p.ms); break;
      }
      case "volume": {
        const id = String(p.id);
        const live = speakerService.deviceForSpeaker(id);
        if (live) { const ok = await speakerService.setVolume(live.deviceId, Number(p.volume)); if (!ok) hint = "This device doesn't allow remote volume."; result = audio.state().nowPlaying; }
        else result = audio.setVolume(id, Number(p.volume));
        break;
      }
      case "speaker-room": { speakerService.setRoom(String(p.deviceId), String(p.room ?? "—")); result = audio.state(); break; }
      case "play-room": {
        const name = await speakerService.playRoom(String(p.room));
        hint = name ? `Playing in ${p.room} (${name})` : `No live speaker in ${p.room} yet`;
        result = audio.state().nowPlaying; break;
      }
      case "onboard-speaker": {
        const sp = localAudio.onboard(p.device || {}, String(p.room ?? "Living Room"));
        hint = `Added ${sp.name} to ${sp.room}`; result = audio.state(); break;
      }
      case "reconnect-speaker": { const sp = await localAudio.reconnect(String(p.id)); hint = sp ? `${sp.name}: ${sp.status}` : "not found"; result = audio.state(); break; }
      case "remove-local": { localAudio.remove(String(p.id)); result = audio.state(); break; }
      case "local-room": { localAudio.setRoom(String(p.id), String(p.room ?? "—")); result = audio.state(); break; }
      case "calibrate-room": {
        const room = String(p.room || "");
        const inputs = Array.isArray(p.speakers) ? p.speakers.map((x: any) => ({ id: String(x.id), name: x.name, role: x.role, distanceM: Number(x.distanceM) })) : [];
        const profile = calibration.saveProfile(calibration.computeProfile(room, inputs, { mode: p.mode, tempC: Number(p.tempC) }));
        hint = `Calibrated ${room} — spatial audio active`;
        // push the delays/trims to Snapcast clients if a server is running
        const ap = await snapcast.applyCalibration(profile).catch(() => null);
        if (ap && ap.applied) hint += ` · Snapcast ${ap.applied}/${ap.total}`;
        result = { profile, state: audio.state() }; break;
      }
      case "clear-calibration": { calibration.clearProfile(String(p.room || "")); result = audio.state(); break; }
      case "sync-room": {
        const room = String(p.room || "");
        const names = (audio.state().speakers as any[]).filter((s) => s.room === room).map((s) => s.name);
        const r = await snapcast.syncRoom(names);
        hint = r.ok ? `Synced ${r.grouped} speakers in ${room}` : (r.reason || "Snapcast not available");
        result = audio.state(); break;
      }
      case "mute": result = audio.setMuted(String(p.id), !!p.muted); break;
      case "add-speaker": result = audio.addSpeaker(String(p.name ?? ""), String(p.room ?? "—"), p.kind); break;
      case "remove-speaker": result = audio.removeSpeaker(String(p.id)); break;
      case "create-zone": result = audio.createZone(String(p.name ?? ""), Array.isArray(p.speakerIds) ? p.speakerIds : []); break;
      case "add-to-zone": result = audio.addToZone(String(p.zoneId), String(p.speakerId)); break;
      case "remove-from-zone": result = audio.removeFromZone(String(p.zoneId), String(p.speakerId)); break;
      case "dissolve-zone": result = audio.dissolveZone(String(p.zoneId)); break;
      case "set-role": result = audio.setRole(String(p.id), p.role); break;
      case "calibrate": result = audio.calibrate(String(p.zoneId)); break;
      case "spotify-play": {
        const uris = Array.isArray(p.uris) ? p.uris.map(String) : (p.uri ? [String(p.uri)] : undefined);
        if (spotify.connected() && (uris || p.contextUri)) {
          // route to the selected room's server-side endpoint (librespot) when given a room
          let deviceId = p.deviceId;
          if (!deviceId && p.room) { const d = await spotify.deviceForRoom(String(p.room)); if (d) deviceId = d.id; }
          try { const r = await spotify.play({ uris, contextUri: p.contextUri, offset: p.offset, deviceId }); hint = r.device ? `Playing in ${p.room || r.device}` : undefined; }
          catch (e) { const m = (e as Error).message || ""; hint = spotifyHint(m); console.log("[spotify] play:", m); }
          result = p.meta ? audio.setTrack(p.meta, p.zoneId) : audio.state().nowPlaying;
        } else {
          result = audio.spotifyPlay(String(p.trackId), p.zoneId);
        }
        break;
      }
      case "spotify-transfer": {
        if (spotify.connected() && p.deviceId) {
          try { await spotify.transfer(String(p.deviceId), p.play !== false); hint = "Moved playback"; }
          catch (e) { const m = (e as Error).message || ""; hint = m.includes("404") ? "no_device" : m; }
        }
        result = audio.state().nowPlaying; break;
      }
      // Pick a room → move Spotify playback to that room's server endpoint (librespot → room speaker).
      case "play-in-room": {
        const room = String(p.room || "");
        if (!spotify.connected()) { hint = "Connect Spotify first."; result = audio.state().nowPlaying; break; }
        const d = await spotify.deviceForRoom(room);
        if (!d) { hint = `No endpoint for ${room} yet — open Spotify → Connect → "openhome · ${room}" → play once (only needed one time).`; result = audio.state().nowPlaying; break; }
        try { await spotify.transfer(d.id, true); hint = `Playing in ${room}`; }
        catch (e) { const m = (e as Error).message || ""; hint = m.includes("404") ? "no_device" : m; }
        result = audio.state().nowPlaying; break;
      }
      case "play-in-zone": result = audio.playInZone(String(p.zoneId)); break;
      // ---- PipeWire output router (internal audio routing) ----
      case "route-output": {
        // Route audio to a sink by node name or id. openhome owns the output —
        // no "go pick a device in Spotify" needed.
        let ok = false;
        if (p.nodeName) ok = await pwRouter.routeByNode(String(p.nodeName));
        else if (p.sinkId != null) ok = await pwRouter.route(Number(p.sinkId));
        hint = ok ? `Output → ${p.label || p.nodeName || p.sinkId}` : "Couldn't switch output (PipeWire unavailable?)";
        result = await pwRouter.status(); break;
      }
      case "test-output": {
        const node = String(p.nodeName || "");
        const ok = node ? await pwRouter.testTone(node) : false;
        hint = ok ? "Playing test tone 🔊" : "Couldn't play test tone";
        result = await pwRouter.status(); break;
      }
      case "output-volume": {
        const ok = await pwRouter.setVolume(Number(p.sinkId), Number(p.volume));
        hint = ok ? undefined : "Volume change failed"; result = await pwRouter.status(); break;
      }
      default: json(res, { ok: false, error: "unknown_cmd", cmd }, 400); return;
    }
    bus.publish({ type: `audio.${cmd}`, ts: Date.now(), payload: { via: "music-app" } });
    json(res, { ok: true, cmd, result, hint, state: audio.state() });
    return;
  }

  json(res, { error: "not_found", tryThese: ["/", "/health", "/devices", "/events/recent"] }, 404);
};

createServer(handler).listen(PORT, () => {
  console.log(`🏠 open-home hub listening on http://localhost:${PORT}`);
  console.log(`   agent     → ${ai.aiEnabled() ? ai.provider() + " (cloud opt-in)" : agent.modelLabel}`);
});

// HTTPS with a self-signed cert so browsers grant microphone access for real voice.
try {
  const key = readFileSync(new URL("../../../certs/key.pem", import.meta.url));
  const cert = readFileSync(new URL("../../../certs/cert.pem", import.meta.url));
  createHttpsServer({ key, cert }, handler).listen(HTTPS_PORT, () => {
    console.log(`   https     → https://localhost:${HTTPS_PORT}/ (voice-enabled)`);
  });
} catch {
  console.log("   https     → disabled (no certs/)");
}

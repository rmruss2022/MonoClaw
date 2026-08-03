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
import * as audio from "./audio.ts";
import * as spotify from "./spotify.ts";
import * as curator from "./curator.ts";
import * as speakerService from "./speakerService.ts";
import * as localAudio from "./localAudio.ts";
import * as calibration from "./calibration.ts";
import * as snapcast from "./snapcast.ts";

const PORT = Number(process.env.OPEN_HOME_PORT ?? 4700);
const HTTPS_PORT = Number(process.env.OPEN_HOME_HTTPS_PORT ?? 4443);
const DASHBOARD = new URL("../../../apps/app/index.html", import.meta.url);
const CONTROL = new URL("../../../apps/app/control.html", import.meta.url);
const MUSIC = new URL("../../../apps/app/music.html", import.meta.url);
const SPEAKERS = new URL("../../../apps/app/speakers.html", import.meta.url);

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
}, 5_000);

// Keep the live Connect devices (Mac/iPhone/…) synced into the speaker model.
speakerService.refresh().catch(() => {});
setInterval(() => { if (!spotify.rateLimited()) speakerService.refresh().catch(() => {}); }, 15_000);

// Maintain onboarded local Wi-Fi/Bluetooth speakers — reconnect on drop.
setInterval(() => { localAudio.maintain().catch(() => {}); }, 15_000);

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

  // Dashboard (same-origin UI)
  if (url === "/" || url === "/index.html") {
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
    if (ai.aiEnabled()) {
      try {
        const r = await ai.aiText(text);
        const done = ai.execute(r.actions);
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
    if (!ai.aiEnabled()) { json(res, { ok: false, error: "ai_disabled" }, 503); return; }
    const body = await readBody(req);
    let audio = "", mime = "audio/webm";
    try { const p = JSON.parse(body || "{}"); audio = String(p.audio ?? ""); mime = String(p.mime ?? mime); } catch {}
    try {
      const r = await ai.aiAudio(audio, mime);
      const done = ai.execute(r.actions);
      console.log(`[agent/audio] transcript=${JSON.stringify(r.transcript)} model=${JSON.stringify(r.actions)} executed=${JSON.stringify(done)}`);
      done.forEach((a) => bus.publish({ type: `agent.${a.label}`, ts: Date.now(), payload: { via: "audio" } }));
      json(res, { ok: true, transcript: r.transcript ?? "", reply: r.reply, actions: done, source: "ai-audio", summary: home.summary() });
    } catch { json(res, { ok: false, error: "ai_error" }, 502); }
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
    };
    const ext = name.slice(name.lastIndexOf("."));
    try {
      const buf = await readFile(new URL(`../../../apps/app/assets/${name}`, import.meta.url));
      res.statusCode = 200;
      res.setHeader("Content-Type", types[ext] ?? "application/octet-stream");
      res.setHeader("Cache-Control", "public, max-age=3600");
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
    json(res, { devices: home.flat(), summary: home.summary() });
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
          try { const r = await spotify.play({ uris, contextUri: p.contextUri, offset: p.offset, deviceId: p.deviceId }); hint = r.device ? `Playing on ${r.device}` : undefined; }
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
      case "play-in-zone": result = audio.playInZone(String(p.zoneId)); break;
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

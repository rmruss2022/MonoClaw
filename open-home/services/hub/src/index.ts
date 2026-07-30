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

const PORT = Number(process.env.OPEN_HOME_PORT ?? 4700);
const HTTPS_PORT = Number(process.env.OPEN_HOME_HTTPS_PORT ?? 4443);
const DASHBOARD = new URL("../../../apps/app/index.html", import.meta.url);
const CONTROL = new URL("../../../apps/app/control.html", import.meta.url);

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

// Heartbeat so the event feed isn't empty on first run.
setInterval(() => {
  bus.publish({ type: "hub.heartbeat", ts: Date.now(), payload: { ok: true } });
}, 15_000);

// Ambient simulator — the mock house nudges itself so the feed feels like a real home.
setInterval(() => {
  const ev = home.simulateTick(Date.now());
  if (ev) bus.publish({ type: ev.type, ts: Date.now(), payload: ev.payload });
}, 12_000);

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

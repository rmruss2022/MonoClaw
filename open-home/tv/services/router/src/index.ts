/**
 * openhome content-router — entry point.
 *
 * Universal search + availability + routing engine for openhome TV. Serves a
 * JSON API (search/details/trending), a stick registry + pairing, the routing
 * endpoint that casts a title to a stick, and a per-stick SSE control channel
 * (server→stick push for launch/keys; stick→server POST for now-playing).
 *
 * Zero-dependency Node 22 + node:sqlite. Deploys next to openhome-cloud on Railway.
 */
import { createServer, IncomingMessage, ServerResponse } from "node:http";
import * as engine from "./engine.ts";
import { accountFromToken, stickFromToken, issueStickToken, authConfigured, sticks, pairing } from "./sessions.ts";
import type { MediaType } from "./types.ts";
import type { ServiceId } from "./deeplinks.ts";
import { mockStickPage } from "./mockStick.ts";
import { remotePage } from "./remoteCtrl.ts";

const CLOUD_URL = process.env.CLOUD_URL || "https://openhome-cloud-production.up.railway.app";

const PORT = Number(process.env.PORT ?? 8090);

// Live SSE connections per stick, and last now-playing snapshot.
const channels = new Map<string, Set<ServerResponse>>();
const nowPlaying = new Map<string, unknown>();

function send(res: ServerResponse, body: unknown, code = 200) {
  const s = JSON.stringify(body);
  res.statusCode = code;
  res.setHeader("Content-Type", "application/json");
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.end(s);
}
function readBody(req: IncomingMessage): Promise<string> {
  return new Promise((r) => { let d = ""; req.on("data", (c) => (d += c)); req.on("end", () => r(d)); req.on("error", () => r("")); });
}
function bearer(req: IncomingMessage): string | undefined {
  const a = req.headers.authorization;
  if (a?.startsWith("Bearer ")) return a.slice(7).trim();
  return undefined;
}
function pushToStick(stickId: string, event: string, data: unknown) {
  const conns = channels.get(stickId);
  if (!conns) return 0;
  const payload = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
  for (const res of conns) res.write(payload);
  return conns.size;
}

const handler = async (req: IncomingMessage, res: ServerResponse) => {
  const u = new URL(req.url ?? "/", "http://x");
  const path = u.pathname;
  const method = req.method ?? "GET";
  if (method === "OPTIONS") {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Headers", "authorization,content-type");
    res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
    res.statusCode = 204; res.end(); return;
  }

  if (path === "/health") {
    return send(res, { status: "ok", service: "openhome-content-router", providers: engine.providerStatus(), auth: authConfigured() });
  }

  // Browser mock stick — open in a tab, pairs with code 000000.
  if (path === "/mock" || path === "/mock/") {
    res.statusCode = 200;
    res.setHeader("Content-Type", "text/html; charset=utf-8");
    res.setHeader("Cache-Control", "no-store");
    return res.end(mockStickPage());
  }
  // Browser remote — sign in + search + cast (no native app needed).
  if (path === "/remote" || path === "/remote/") {
    res.statusCode = 200;
    res.setHeader("Content-Type", "text/html; charset=utf-8");
    res.setHeader("Cache-Control", "no-store");
    return res.end(remotePage());
  }
  // Proxy the control-plane login server-side (avoids browser CORS); returns the
  // account's home grant so the remote page can cast.
  if (path === "/remote/login" && method === "POST") {
    let p: any = {};
    try { p = JSON.parse((await readBody(req)) || "{}"); } catch {}
    try {
      const lr = await fetch(`${CLOUD_URL}/api/login`, {
        method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ email: p.email, password: p.password }),
      });
      const lj: any = await lr.json().catch(() => ({}));
      if (!lj.ok || !lj.token) return send(res, { ok: false, error: "bad_login" }, 401);
      const hr = await fetch(`${CLOUD_URL}/api/home`, { headers: { Authorization: `Bearer ${lj.token}` } });
      const hj: any = await hr.json().catch(() => ({}));
      if (!hj.ok || !hj.homeToken) return send(res, { ok: false, error: "no_home" }, 400);
      return send(res, { ok: true, homeToken: hj.homeToken, email: lj.account?.email });
    } catch {
      return send(res, { ok: false, error: "cloud_unreachable" }, 502);
    }
  }

  // ---- Public content API ----
  if (path === "/search") {
    const q = u.searchParams.get("q") ?? "";
    const type = (u.searchParams.get("type") as MediaType) || undefined;
    const region = u.searchParams.get("region") || "US";
    return send(res, { results: await engine.search({ q, type, region }) });
  }
  if (path.startsWith("/title/")) {
    const id = decodeURIComponent(path.slice("/title/".length));
    const t = await engine.detail(id, u.searchParams.get("region") || "US");
    return t ? send(res, { title: t }) : send(res, { error: "not_found" }, 404);
  }
  if (path === "/trending") {
    const type = (u.searchParams.get("type") as MediaType) || undefined;
    return send(res, { results: await engine.trending(type, u.searchParams.get("region") || "US") });
  }

  // ---- Stick pairing: the stick identifies itself (no account yet) ----
  if (path === "/sticks/pair/begin" && method === "POST") {
    const p = JSON.parse((await readBody(req)) || "{}");
    const stickId = String(p.stickId || "");
    const name = String(p.name || "openhome TV");
    if (!stickId) return send(res, { error: "stickId_required" }, 400);
    // The browser mock stick (id "stick-mock") may request a fixed code (000000).
    const fixed = stickId === "stick-mock" && typeof p.code === "string" && p.code ? String(p.code) : undefined;
    return send(res, { ...pairing.begin(stickId, name, fixed), stickToken: issueStickToken(stickId) });
  }

  // ---- Everything below needs an account grant or a stick token ----
  const aid = accountFromToken(bearer(req));
  const stickTok = stickFromToken(bearer(req));
  // Authorized to act on a stick = its account owner, or the stick itself.
  const ownsStick = (stickId: string) => {
    const st = sticks.get(stickId);
    if (!st) return false;
    return (aid && st.account_id === aid) || stickTok === stickId;
  };

  // Stick SSE control channel. The stick connects with its own stick token.
  if (path.startsWith("/stick/") && path.endsWith("/stream")) {
    const stickId = path.slice("/stick/".length, -"/stream".length);
    const st = sticks.get(stickId);
    // Browser EventSource can't set an Authorization header, so for the stream we
    // also accept the stick token via ?token= query (used by the /mock browser stick).
    const qTokStick = stickFromToken(u.searchParams.get("token") || "");
    if (!st || !(ownsStick(stickId) || qTokStick === stickId)) { res.statusCode = 401; return res.end(); }
    res.statusCode = 200;
    res.setHeader("Content-Type", "text/event-stream");
    res.setHeader("Cache-Control", "no-store");
    res.setHeader("Connection", "keep-alive");
    res.write(`event: ready\ndata: ${JSON.stringify({ stickId })}\n\n`);
    if (!channels.has(stickId)) channels.set(stickId, new Set());
    channels.get(stickId)!.add(res);
    sticks.markOnline(stickId, true); sticks.touch(stickId);
    const ping = setInterval(() => res.write(`event: ping\ndata: {}\n\n`), 25000);
    req.on("close", () => {
      clearInterval(ping);
      const set = channels.get(stickId); set?.delete(res);
      if (!set || set.size === 0) sticks.markOnline(stickId, false);
    });
    return;
  }

  // ---- Stick-self endpoints: the stick (stick token) or its account owner ----
  if (path.startsWith("/stick/") && path.endsWith("/apps") && method === "POST") {
    const stickId = path.slice("/stick/".length, -"/apps".length);
    if (!ownsStick(stickId)) return send(res, { error: "unauthorized" }, 401);
    const p = JSON.parse((await readBody(req)) || "{}");
    if (Array.isArray(p.installed)) sticks.setInstalled(stickId, p.installed as ServiceId[]);
    if (Array.isArray(p.owned)) sticks.setOwned(stickId, p.owned as ServiceId[]);
    return send(res, { ok: true, stick: sticks.get(stickId) });
  }
  if (path.startsWith("/stick/") && path.endsWith("/event") && method === "POST") {
    const stickId = path.slice("/stick/".length, -"/event".length);
    if (!ownsStick(stickId)) return send(res, { error: "unauthorized" }, 401);
    nowPlaying.set(stickId, JSON.parse((await readBody(req)) || "{}"));
    sticks.touch(stickId);
    return send(res, { ok: true });
  }
  if (path.startsWith("/stick/") && path.endsWith("/nowplaying")) {
    const stickId = path.slice("/stick/".length, -"/nowplaying".length);
    if (!ownsStick(stickId)) return send(res, { error: "unauthorized" }, 401);
    return send(res, { nowPlaying: nowPlaying.get(stickId) ?? null, online: !!channels.get(stickId)?.size });
  }

  // ---- Account-only below ----
  if (!aid) return send(res, { error: "unauthorized" }, 401);
  if (path === "/sticks" && method === "GET") {
    return send(res, { sticks: sticks.forAccount(aid) });
  }
  if (path === "/sticks/pair/claim" && method === "POST") {
    const p = JSON.parse((await readBody(req)) || "{}");
    const st = pairing.claim(String(p.code || ""), aid);
    return st ? send(res, { ok: true, stick: st }) : send(res, { ok: false, error: "bad_or_expired_code" }, 400);
  }

  // Remote keys / transport → pushed to the stick.
  if (path.startsWith("/stick/") && path.endsWith("/command") && method === "POST") {
    const stickId = path.slice("/stick/".length, -"/command".length);
    const st = sticks.get(stickId);
    if (!st || st.account_id !== aid) return send(res, { error: "not_found" }, 404);
    const p = JSON.parse((await readBody(req)) || "{}");
    const delivered = pushToStick(stickId, "command", { cmd: String(p.cmd || ""), ...p });
    return send(res, { ok: delivered > 0, delivered });
  }

  // The cast: choose a source and push a launch to the stick.
  if (path === "/route" && method === "POST") {
    const p = JSON.parse((await readBody(req)) || "{}");
    const stickId = String(p.stickId || "");
    const st = sticks.get(stickId);
    if (!st || st.account_id !== aid) return send(res, { error: "stick_not_found" }, 404);
    const title = await engine.detail(String(p.titleId || ""), st.region);
    if (!title) return send(res, { error: "title_not_found" }, 404);
    const route = engine.chooseSource(title, { installedApps: st.installed, ownedServices: st.owned, prefer: p.prefer });
    if (!route.ok) return send(res, { ok: false, reason: route.reason, title }, 409);
    const delivered = pushToStick(stickId, "launch", {
      title: { id: title.id, name: title.name, poster: title.poster },
      service: route.service, deepLink: route.deepLink, androidPackage: route.androidPackage, level: route.level,
    });
    return send(res, { ok: true, route, castTo: st.name, delivered });
  }

  return send(res, { error: "not_found" }, 404);
};

createServer(handler).listen(PORT, () => {
  const p = engine.providerStatus();
  console.log(`openhome content-router on :${PORT}`);
  console.log(`  metadata=${p.metadata} availability=${p.availability} live=${p.live} auth=${authConfigured()}`);
});

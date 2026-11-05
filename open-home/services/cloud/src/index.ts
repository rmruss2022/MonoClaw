/**
 * openhome cloud — control-plane entry point.
 *
 * public app ──► [ this service ] ──► routes you to your hub
 *                 identity + directory
 *
 * Responsibilities (and nothing more):
 *   1. Accounts — signup / login / sessions.
 *   2. Directory — which home(s) an account owns and how to reach each hub.
 *   3. Routing grant — issue a short-lived, home-scoped token the app carries
 *      straight to its hub. The hub verifies it locally; house data never flows
 *      through here.
 *
 * Zero-dependency Node http + node:sqlite, so it deploys clean on Railway.
 */
import { createServer, IncomingMessage, ServerResponse } from "node:http";
import { randomUUID } from "node:crypto";
import { accounts, homes, sessions, type Account } from "./db.ts";
import * as auth from "./auth.ts";
import { signinPage } from "./pages.ts";
import { seedFromEnv } from "./seed.ts";

const PORT = Number(process.env.PORT ?? 8080);
const SESSION_TTL = 60 * 60 * 24 * 30; // 30 days
const COOKIE = "oh_cloud_sess";

function readBody(req: IncomingMessage): Promise<string> {
  return new Promise((resolve) => {
    let d = "";
    req.on("data", (c) => {
      d += c;
      if (d.length > 1e6) req.destroy();
    });
    req.on("end", () => resolve(d));
    req.on("error", () => resolve(""));
  });
}

function json(res: ServerResponse, body: unknown, code = 200): void {
  const s = JSON.stringify(body);
  res.statusCode = code;
  res.setHeader("Content-Type", "application/json");
  res.setHeader("Cache-Control", "no-store");
  res.end(s);
}

function parseCookies(header?: string): Record<string, string> {
  const out: Record<string, string> = {};
  if (!header) return out;
  for (const part of header.split(";")) {
    const i = part.indexOf("=");
    if (i > 0) out[part.slice(0, i).trim()] = part.slice(i + 1).trim();
  }
  return out;
}

/** Session may arrive as a cookie (web) or `Authorization: Bearer` (native app). */
function sessionToken(req: IncomingMessage): string | undefined {
  const authz = req.headers.authorization;
  if (authz?.startsWith("Bearer ")) return authz.slice(7).trim();
  return parseCookies(req.headers.cookie)[COOKIE];
}

function currentAccount(req: IncomingMessage): Account | undefined {
  const tok = sessionToken(req);
  if (!tok) return undefined;
  const s = sessions.get(tok);
  if (!s || s.expires_at < Math.floor(Date.now() / 1000)) return undefined;
  return accounts.byId(s.account_id);
}

function clientIp(req: IncomingMessage): string {
  const cf = req.headers["cf-connecting-ip"];
  if (typeof cf === "string" && cf) return cf;
  const xff = req.headers["x-forwarded-for"];
  if (typeof xff === "string" && xff) return xff.split(",")[0].trim();
  return req.socket.remoteAddress ?? "";
}

function homeView(h: { id: string; name: string; endpoint: string; status: string }) {
  return { id: h.id, name: h.name, endpoint: h.endpoint, status: h.status };
}

async function handleAuth(
  req: IncomingMessage,
  res: ServerResponse,
  mode: "signup" | "login"
): Promise<void> {
  const ip = clientIp(req);
  const wait = auth.throttled(ip);
  if (wait > 0) {
    json(res, { ok: false, error: `Too many attempts. Try again in ${wait}s.` }, 429);
    return;
  }
  let email = "",
    password = "";
  try {
    const p = JSON.parse((await readBody(req)) || "{}");
    email = String(p.email ?? "").trim().toLowerCase();
    password = String(p.password ?? "");
  } catch {
    /* ignore */
  }
  if (!email || !password || !email.includes("@")) {
    json(res, { ok: false, error: "Enter a valid email and password." }, 400);
    return;
  }

  let account: Account | undefined;
  if (mode === "signup") {
    if (accounts.byEmail(email)) {
      json(res, { ok: false, error: "An account with that email already exists." }, 409);
      return;
    }
    if (password.length < 8) {
      json(res, { ok: false, error: "Password must be at least 8 characters." }, 400);
      return;
    }
    account = { id: randomUUID(), email, pw_hash: auth.hashPassword(password), created_at: Date.now() };
    accounts.create(account);
  } else {
    account = accounts.byEmail(email);
    if (!account || !auth.verifyPassword(password, account.pw_hash)) {
      auth.noteFailure(ip);
      json(res, { ok: false, error: "Wrong email or password." }, 401);
      return;
    }
  }
  auth.noteSuccess(ip);

  const token = auth.newSessionToken();
  sessions.create(token, account.id, SESSION_TTL);
  res.setHeader(
    "Set-Cookie",
    `${COOKIE}=${token}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=${SESSION_TTL}`
  );
  json(res, {
    ok: true,
    token, // native clients store this and send it as Bearer
    account: { email: account.email },
    homes: homes.forAccount(account.id).map(homeView),
  });
}

const handler = async (req: IncomingMessage, res: ServerResponse) => {
  const url = (req.url ?? "/").split("?")[0];
  const method = req.method ?? "GET";

  if (url === "/health") {
    json(res, { status: "ok", service: "openhome-cloud", homeTokens: auth.homeTokenConfigured() });
    return;
  }

  if (url === "/api/signup" && method === "POST") return handleAuth(req, res, "signup");
  if (url === "/api/login" && method === "POST") return handleAuth(req, res, "login");

  if (url === "/api/logout" && method === "POST") {
    const tok = sessionToken(req);
    if (tok) sessions.destroy(tok);
    res.setHeader("Set-Cookie", `${COOKIE}=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0`);
    json(res, { ok: true });
    return;
  }

  if (url === "/api/me") {
    const acct = currentAccount(req);
    if (!acct) {
      json(res, { ok: false, error: "unauthorized" }, 401);
      return;
    }
    json(res, { ok: true, account: { email: acct.email }, homes: homes.forAccount(acct.id).map(homeView) });
    return;
  }

  // The routing resolution: given a signed-in account, hand back where its home
  // is and a short-lived token to authenticate directly to that hub.
  if (url === "/api/home") {
    const acct = currentAccount(req);
    if (!acct) {
      json(res, { ok: false, error: "unauthorized" }, 401);
      return;
    }
    const mine = homes.forAccount(acct.id);
    const id = new URL(req.url ?? "/", "http://x").searchParams.get("id");
    const home = id ? mine.find((h) => h.id === id) : mine[0];
    if (!home) {
      json(res, { ok: false, error: "no_home", hint: "Pair a hub to this account first." }, 404);
      return;
    }
    if (!auth.homeTokenConfigured()) {
      json(res, { ok: false, error: "home_tokens_unconfigured" }, 503);
      return;
    }
    json(res, {
      ok: true,
      home: homeView(home),
      endpoint: home.endpoint,
      homeToken: auth.issueHomeToken(acct.id, home.id),
    });
    return;
  }

  if (url === "/" || url === "/login") {
    res.statusCode = 200;
    res.setHeader("Content-Type", "text/html; charset=utf-8");
    res.setHeader("Cache-Control", "no-store");
    res.end(signinPage());
    return;
  }

  json(res, { error: "not_found" }, 404);
};

// Optional first-boot seed (idempotent). Handy on hosts without a shell; remove
// SEED_PASSWORD from the env once the account exists.
try { seedFromEnv(); } catch (e) { console.log("[seed] skipped:", (e as Error).message); }

// Prune expired sessions hourly.
setInterval(() => sessions.prune(), 60 * 60 * 1000);

createServer(handler).listen(PORT, () => {
  console.log(`openhome-cloud listening on :${PORT}`);
  console.log(`  home tokens: ${auth.homeTokenConfigured() ? "configured" : "NOT configured (set HOME_TOKEN_SECRET)"}`);
});

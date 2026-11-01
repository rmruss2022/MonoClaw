/**
 * open-home hub — access gate.
 *
 * Zero-dependency password gate so the hub isn't wide-open when exposed over a
 * public tunnel. Disabled automatically when no password is configured, so a
 * fresh local checkout still runs with no friction.
 *
 * Config (via env / systemd EnvironmentFile):
 *   OPEN_HOME_PASSWORD      required to enable the gate
 *   OPEN_HOME_AUTH_SECRET   HMAC key for signing the session cookie (keep stable
 *                           across restarts so sign-ins survive a reboot)
 *   OPEN_HOME_ALLOW_IPS     optional comma-separated allowlist of client IPs
 *                           (matched against Cloudflare's CF-Connecting-IP);
 *                           empty = allow any IP that knows the password
 */
import { createHmac, timingSafeEqual, randomBytes } from "node:crypto";
import type { IncomingMessage } from "node:http";

const PASSWORD = process.env.OPEN_HOME_PASSWORD ?? "";
// Fall back to an ephemeral secret if none is set — the gate still works, but
// cookies won't survive a restart (everyone re-logs in). Set the env for stability.
const SECRET = process.env.OPEN_HOME_AUTH_SECRET || randomBytes(32).toString("hex");
const ALLOW_IPS = (process.env.OPEN_HOME_ALLOW_IPS ?? "")
  .split(",").map((s) => s.trim()).filter(Boolean);
// Shared with the openhome-cloud control-plane. When set, this hub also accepts
// cloud-issued "home tokens" — so a user who signed in to the cloud app is routed
// here and authenticated without ever typing this hub's local passphrase. The
// cloud signs {aid,hid,exp}; we verify the signature locally (cloud stays out of
// the data path). Optionally pin OPEN_HOME_HOME_ID so only *this* home's grants pass.
const HOME_TOKEN_SECRET = process.env.HOME_TOKEN_SECRET ?? "";
const HOME_ID = process.env.OPEN_HOME_HOME_ID ?? "";

const COOKIE = "oh_auth";
const MAX_AGE = 30 * 24 * 3600; // 30 days

export function enabled(): boolean { return PASSWORD.length > 0; }

/**
 * Validate a control-plane home token: base64url(JSON{aid,hid,exp}) + "." + HMAC.
 * Mirrors openhome-cloud/src/auth.ts so the two stay in lockstep.
 */
export function validHomeToken(tok?: string): boolean {
  if (!tok || !HOME_TOKEN_SECRET) return false;
  const dot = tok.lastIndexOf(".");
  if (dot < 0) return false;
  const payload = tok.slice(0, dot);
  const mac = tok.slice(dot + 1);
  const expected = createHmac("sha256", HOME_TOKEN_SECRET).update(payload).digest("base64url");
  const a = Buffer.from(mac), b = Buffer.from(expected);
  if (a.length !== b.length || !timingSafeEqual(a, b)) return false;
  try {
    const body = JSON.parse(Buffer.from(payload, "base64url").toString());
    if (typeof body.exp !== "number" || body.exp < Math.floor(Date.now() / 1000)) return false;
    if (HOME_ID && body.hid !== HOME_ID) return false;
    return true;
  } catch { return false; }
}

function sign(payload: string): string {
  return createHmac("sha256", SECRET).update(payload).digest("base64url");
}

export function makeToken(): string {
  const exp = Math.floor(Date.now() / 1000) + MAX_AGE;
  const payload = `v1.${exp}`;
  return `${payload}.${sign(payload)}`;
}

export function validToken(tok?: string): boolean {
  if (!tok) return false;
  const parts = tok.split(".");
  if (parts.length !== 3) return false;
  const payload = `${parts[0]}.${parts[1]}`;
  const expected = sign(payload);
  const got = Buffer.from(parts[2]);
  const exp = Buffer.from(expected);
  if (got.length !== exp.length) return false;
  if (!timingSafeEqual(got, exp)) return false;
  return Number(parts[1]) > Math.floor(Date.now() / 1000);
}

export function checkPassword(given: string): boolean {
  if (!PASSWORD) return false;
  const a = Buffer.from(given);
  const b = Buffer.from(PASSWORD);
  if (a.length !== b.length) return false;
  return timingSafeEqual(a, b);
}

export function parseCookies(header?: string): Record<string, string> {
  const out: Record<string, string> = {};
  if (!header) return out;
  for (const part of header.split(";")) {
    const i = part.indexOf("=");
    if (i < 0) continue;
    out[part.slice(0, i).trim()] = decodeURIComponent(part.slice(i + 1).trim());
  }
  return out;
}

export function cookieName(): string { return COOKIE; }

export function setCookieHeader(token: string): string {
  return `${COOKIE}=${token}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=${MAX_AGE}`;
}

export function clearCookieHeader(): string {
  return `${COOKIE}=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0`;
}

/** Real client IP as seen through the Cloudflare tunnel, else the socket peer. */
export function clientIp(req: IncomingMessage): string {
  const cf = req.headers["cf-connecting-ip"];
  if (typeof cf === "string" && cf) return cf;
  const xff = req.headers["x-forwarded-for"];
  if (typeof xff === "string" && xff) return xff.split(",")[0].trim();
  return req.socket.remoteAddress ?? "";
}

/** True when an optional IP allowlist is set and this request isn't on it. */
export function ipBlocked(req: IncomingMessage): boolean {
  if (ALLOW_IPS.length === 0) return false;
  return !ALLOW_IPS.includes(clientIp(req));
}

export function cookieAuthed(req: IncomingMessage): boolean {
  // Accept either a locally-issued session token or a valid cloud home token,
  // presented as the oh_auth cookie (browsers, /sso) or an Authorization: Bearer
  // header (native apps, whose cookie jars can mangle a manual Cookie header).
  const cookie = parseCookies(req.headers.cookie)[COOKIE];
  if (validToken(cookie) || validHomeToken(cookie)) return true;
  const authz = req.headers.authorization;
  if (typeof authz === "string" && authz.startsWith("Bearer ")) {
    const t = authz.slice(7).trim();
    if (validToken(t) || validHomeToken(t)) return true;
  }
  return false;
}

export function loginPage(msg = ""): string {
  const err = msg
    ? `<p class="err">${msg.replace(/</g, "&lt;")}</p>`
    : "";
  return `<!doctype html><html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
<title>Sign in · openhome</title>
<link rel="icon" type="image/svg+xml" href="/assets/brand/favicon.svg"/>
<meta name="theme-color" content="#0b0a12"/>
<style>
  :root{--bg:#0b0a12;--panel:#181527;--line:#2a2540;--text:#ece9f5;--muted:#9a93b8;--accent:#f5c977;--purple:#a855f7;
    --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif}
  *{box-sizing:border-box}
  html,body{height:100%}
  body{margin:0;background:radial-gradient(1200px 900px at 50% -5%,#140f22,var(--bg));color:var(--text);
    font:15px/1.5 ui-rounded,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,system-ui,sans-serif;
    display:flex;align-items:center;justify-content:center;padding:24px}
  .stars{position:fixed;inset:0;z-index:-1;pointer-events:none}
  .card{width:100%;max-width:360px;background:rgba(24,21,39,.78);backdrop-filter:blur(8px);border:1px solid var(--line);
    border-radius:20px;padding:28px 24px;box-shadow:0 24px 70px rgba(0,0,0,.5),0 0 0 1px rgba(168,85,247,.08)}
  .brand{display:flex;align-items:center;gap:10px;margin-bottom:6px;font-weight:600;font-size:22px;font-family:var(--serif);letter-spacing:.2px}
  .dot{width:11px;height:11px;border-radius:50%;background:var(--accent);box-shadow:0 0 14px var(--accent)}
  p.sub{margin:0 0 20px;color:var(--muted);font-size:13px}
  label{display:block;font-size:12px;color:var(--muted);margin:0 0 6px}
  input{width:100%;padding:13px 14px;border-radius:12px;border:1px solid var(--line);
    background:#0b0a12;color:var(--text);font-size:16px;outline:none}
  input:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(245,201,119,.15)}
  button{margin-top:16px;width:100%;padding:13px;border:0;border-radius:12px;
    background:linear-gradient(180deg,#f7d58c,var(--accent));color:#2a1e05;font-weight:800;font-size:15px;cursor:pointer;
    box-shadow:0 10px 30px rgba(245,201,119,.22)}
  .err{color:#ff6b6b;font-size:13px;margin:12px 0 0}
  .foot{margin-top:18px;color:var(--muted);font-size:11px;text-align:center;letter-spacing:.3px}
</style></head>
<body>
  <canvas class="stars"></canvas>
  <form class="card" method="POST" action="/login">
    <div class="brand"><span class="dot"></span>openhome</div>
    <p class="sub">This home is private. Enter the passphrase to continue.</p>
    <label for="password">Passphrase</label>
    <input id="password" name="password" type="password" autocomplete="current-password" autofocus required/>
    <button type="submit">Unlock</button>
    ${err}
    <div class="foot">Your home. Your keys.</div>
  </form>
  <script>(function(){var c=document.querySelector('.stars');if(!c)return;var x=c.getContext('2d');
  function rs(){c.width=innerWidth;c.height=innerHeight;}rs();addEventListener('resize',rs);
  var st=Array.from({length:60},function(){return{x:Math.random()*c.width,y:Math.random()*c.height,r:Math.random()*1.2+.2,a:Math.random()*6};});
  (function loop(){x.clearRect(0,0,c.width,c.height);for(var i=0;i<st.length;i++){var s=st[i];s.a+=0.015;var o=.22+.33*Math.sin(s.a);x.fillStyle='rgba(220,210,255,'+o+')';x.beginPath();x.arc(s.x,s.y,s.r,0,7);x.fill();}requestAnimationFrame(loop);})();})();</script>
</body></html>`;
}

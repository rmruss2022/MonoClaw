/**
 * openhome cloud — auth primitives.
 *
 *  - Passwords: scrypt (built-in crypto), stored as `scrypt$N$salt$hash`.
 *  - Sessions: opaque random token → row in `sessions` (control-plane cookie).
 *  - Home token: an HMAC-signed grant the app carries to its hub. The hub shares
 *    HOME_TOKEN_SECRET and verifies it locally, so the cloud is never in the
 *    data path. Shape: base64url(JSON{aid,hid,exp}) + "." + HMAC.
 */
import { randomBytes, scryptSync, timingSafeEqual, createHmac } from "node:crypto";

const SCRYPT_N = 16384;

export function hashPassword(pw: string): string {
  const salt = randomBytes(16);
  const hash = scryptSync(pw, salt, 32, { N: SCRYPT_N });
  return `scrypt$${SCRYPT_N}$${salt.toString("base64url")}$${hash.toString("base64url")}`;
}

export function verifyPassword(pw: string, stored: string): boolean {
  const parts = stored.split("$");
  if (parts.length !== 4 || parts[0] !== "scrypt") return false;
  const N = Number(parts[1]);
  const salt = Buffer.from(parts[2], "base64url");
  const expected = Buffer.from(parts[3], "base64url");
  const got = scryptSync(pw, salt, expected.length, { N });
  return got.length === expected.length && timingSafeEqual(got, expected);
}

export function newSessionToken(): string {
  return randomBytes(32).toString("base64url");
}

// --- Home token (shared with the hub) -------------------------------------
const HOME_TOKEN_SECRET =
  process.env.HOME_TOKEN_SECRET || process.env.OPEN_HOME_AUTH_SECRET || "";
const HOME_TOKEN_TTL = 60 * 60 * 12; // 12h — short-lived; app refreshes via /api/home

export function homeTokenConfigured(): boolean {
  return HOME_TOKEN_SECRET.length > 0;
}

function sign(payload: string): string {
  return createHmac("sha256", HOME_TOKEN_SECRET).update(payload).digest("base64url");
}

export function issueHomeToken(accountId: string, homeId: string): string {
  const body = {
    aid: accountId,
    hid: homeId,
    exp: Math.floor(Date.now() / 1000) + HOME_TOKEN_TTL,
  };
  const payload = Buffer.from(JSON.stringify(body)).toString("base64url");
  return `${payload}.${sign(payload)}`;
}

/** Verify a home token (same logic the hub runs). Returns the claims or null. */
export function verifyHomeToken(
  tok?: string
): { aid: string; hid: string; exp: number } | null {
  if (!tok) return null;
  const dot = tok.lastIndexOf(".");
  if (dot < 0) return null;
  const payload = tok.slice(0, dot);
  const mac = tok.slice(dot + 1);
  const expected = sign(payload);
  const a = Buffer.from(mac);
  const b = Buffer.from(expected);
  if (a.length !== b.length || !timingSafeEqual(a, b)) return null;
  try {
    const body = JSON.parse(Buffer.from(payload, "base64url").toString());
    if (typeof body.exp !== "number" || body.exp < Math.floor(Date.now() / 1000)) return null;
    return body;
  } catch {
    return null;
  }
}

// --- Simple per-key login throttle (brute-force dampener) ------------------
const attempts = new Map<string, { n: number; until: number }>();

export function throttled(key: string): number {
  const rec = attempts.get(key);
  if (!rec) return 0;
  const now = Date.now();
  if (rec.until > now) return Math.ceil((rec.until - now) / 1000);
  return 0;
}

export function noteFailure(key: string): void {
  const rec = attempts.get(key) ?? { n: 0, until: 0 };
  rec.n += 1;
  // back off after 5 bad tries: 2^(n-5) seconds, capped at 5 min
  if (rec.n >= 5) rec.until = Date.now() + Math.min(300, 2 ** (rec.n - 5)) * 1000;
  attempts.set(key, rec);
}

export function noteSuccess(key: string): void {
  attempts.delete(key);
}

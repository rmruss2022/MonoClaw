/**
 * Identity + stick registry for the content-router.
 *
 * Auth reuses the openhome account grant: the phone/stick present the same
 * HMAC home token the control-plane issues ({aid,hid,exp}); we verify it locally
 * with the shared HOME_TOKEN_SECRET and authorize "this account may control these
 * sticks." Sticks are the account's living-room devices.
 */
import { DatabaseSync } from "node:sqlite";
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { createHmac, timingSafeEqual, randomBytes } from "node:crypto";
import type { ServiceId } from "./deeplinks.ts";

const DATA_DIR = process.env.DATA_DIR || join(process.cwd(), "data");
mkdirSync(DATA_DIR, { recursive: true });
export const db = new DatabaseSync(join(DATA_DIR, "tv-router.db"));

db.exec(`
  PRAGMA journal_mode = WAL;
  CREATE TABLE IF NOT EXISTS sticks (
    id            TEXT PRIMARY KEY,
    account_id    TEXT NOT NULL,
    name          TEXT NOT NULL,
    region        TEXT NOT NULL DEFAULT 'US',
    installed     TEXT NOT NULL DEFAULT '[]',
    owned         TEXT NOT NULL DEFAULT '[]',
    paired_at     INTEGER NOT NULL,
    last_seen     INTEGER
  );
  CREATE TABLE IF NOT EXISTS pairings (
    code          TEXT PRIMARY KEY,
    stick_id      TEXT NOT NULL,
    name          TEXT NOT NULL,
    expires_at    INTEGER NOT NULL,
    account_id    TEXT
  );
`);

const HOME_TOKEN_SECRET = process.env.HOME_TOKEN_SECRET ?? "";
export function authConfigured(): boolean { return HOME_TOKEN_SECRET.length > 0; }

/** Issue a long-lived stick-scoped token (stick authenticates its own channel). */
export function issueStickToken(stickId: string): string {
  const payload = Buffer.from(JSON.stringify({ sid: stickId })).toString("base64url");
  return `stk.${payload}.${createHmac("sha256", HOME_TOKEN_SECRET).update(payload).digest("base64url")}`;
}
/** Verify a stick token → the stick id, or null. */
export function stickFromToken(tok?: string): string | null {
  if (!tok || !HOME_TOKEN_SECRET || !tok.startsWith("stk.")) return null;
  const rest = tok.slice(4);
  const dot = rest.lastIndexOf(".");
  if (dot < 0) return null;
  const payload = rest.slice(0, dot), mac = rest.slice(dot + 1);
  const expected = createHmac("sha256", HOME_TOKEN_SECRET).update(payload).digest("base64url");
  const a = Buffer.from(mac), b = Buffer.from(expected);
  if (a.length !== b.length || !timingSafeEqual(a, b)) return null;
  try { return JSON.parse(Buffer.from(payload, "base64url").toString()).sid ?? null; } catch { return null; }
}

/** Verify a cloud home token → the account id (aid), or null. */
export function accountFromToken(tok?: string): string | null {
  if (!tok || !HOME_TOKEN_SECRET) return null;
  const dot = tok.lastIndexOf(".");
  if (dot < 0) return null;
  const payload = tok.slice(0, dot), mac = tok.slice(dot + 1);
  const expected = createHmac("sha256", HOME_TOKEN_SECRET).update(payload).digest("base64url");
  const a = Buffer.from(mac), b = Buffer.from(expected);
  if (a.length !== b.length || !timingSafeEqual(a, b)) return null;
  try {
    const body = JSON.parse(Buffer.from(payload, "base64url").toString());
    if (typeof body.exp !== "number" || body.exp < Math.floor(Date.now() / 1000)) return null;
    return typeof body.aid === "string" ? body.aid : null;
  } catch { return null; }
}

export interface Stick {
  id: string; account_id: string; name: string; region: string;
  installed: ServiceId[]; owned: ServiceId[]; paired_at: number; last_seen: number | null; online: boolean;
}

const online = new Set<string>(); // stick ids with a live WS

function rowToStick(r: any): Stick {
  return {
    id: r.id, account_id: r.account_id, name: r.name, region: r.region,
    installed: JSON.parse(r.installed || "[]"), owned: JSON.parse(r.owned || "[]"),
    paired_at: r.paired_at, last_seen: r.last_seen, online: online.has(r.id),
  };
}

export const sticks = {
  forAccount(aid: string): Stick[] {
    return (db.prepare("SELECT * FROM sticks WHERE account_id = ? ORDER BY paired_at").all(aid) as any[]).map(rowToStick);
  },
  get(id: string): Stick | null {
    const r = db.prepare("SELECT * FROM sticks WHERE id = ?").get(id);
    return r ? rowToStick(r) : null;
  },
  setInstalled(id: string, installed: ServiceId[]) {
    db.prepare("UPDATE sticks SET installed = ? WHERE id = ?").run(JSON.stringify(installed), id);
  },
  setOwned(id: string, owned: ServiceId[]) {
    db.prepare("UPDATE sticks SET owned = ? WHERE id = ?").run(JSON.stringify(owned), id);
  },
  touch(id: string) {
    db.prepare("UPDATE sticks SET last_seen = ? WHERE id = ?").run(Date.now(), id);
  },
  markOnline(id: string, is: boolean) { is ? online.add(id) : online.delete(id); },
};

/** A stick with no account yet generates a pairing code; the phone claims it. */
export const pairing = {
  begin(stickId: string, name: string, fixedCode?: string): { code: string; expiresAt: number } {
    const code = fixedCode ?? String(randomBytes(3).readUIntBE(0, 3) % 1000000).padStart(6, "0");
    const expiresAt = Date.now() + 10 * 60 * 1000;
    db.prepare("INSERT OR REPLACE INTO pairings (code, stick_id, name, expires_at) VALUES (?, ?, ?, ?)")
      .run(code, stickId, name, expiresAt);
    return { code, expiresAt };
  },
  /** Phone claims the code for its account → creates the stick. */
  claim(code: string, accountId: string): Stick | null {
    const p = db.prepare("SELECT * FROM pairings WHERE code = ?").get(code) as any;
    if (!p || p.expires_at < Date.now()) return null;
    const existing = sticks.get(p.stick_id);
    if (!existing) {
      db.prepare("INSERT INTO sticks (id, account_id, name, region, paired_at) VALUES (?, ?, ?, 'US', ?)")
        .run(p.stick_id, accountId, p.name, Date.now());
    } else {
      db.prepare("UPDATE sticks SET account_id = ? WHERE id = ?").run(accountId, p.stick_id);
    }
    db.prepare("DELETE FROM pairings WHERE code = ?").run(code);
    return sticks.get(p.stick_id);
  },
};

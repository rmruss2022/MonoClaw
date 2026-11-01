/**
 * openhome cloud — data layer.
 *
 * The control-plane is deliberately tiny: it holds *identity* (accounts) and a
 * *directory* (which home each account owns + how to reach its hub). It never
 * sees house data — after sign-in the app talks straight to the hub. So this DB
 * is small and low-churn: accounts, homes, sessions.
 *
 * Storage is SQLite via Node's built-in `node:sqlite` (zero native deps, so it
 * builds anywhere — Railway included). Point DATA_DIR at a persistent volume in
 * production so accounts survive redeploys.
 */
import { DatabaseSync } from "node:sqlite";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

const DATA_DIR = process.env.DATA_DIR || join(process.cwd(), "data");
mkdirSync(DATA_DIR, { recursive: true });

export const db = new DatabaseSync(join(DATA_DIR, "cloud.db"));

db.exec(`
  PRAGMA journal_mode = WAL;

  CREATE TABLE IF NOT EXISTS accounts (
    id         TEXT PRIMARY KEY,
    email      TEXT UNIQUE NOT NULL,
    pw_hash    TEXT NOT NULL,
    created_at INTEGER NOT NULL
  );

  CREATE TABLE IF NOT EXISTS homes (
    id         TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    name       TEXT NOT NULL,
    endpoint   TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'unknown',
    paired_at  INTEGER NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
  );

  CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
  );
`);

export interface Account {
  id: string;
  email: string;
  pw_hash: string;
  created_at: number;
}
export interface Home {
  id: string;
  account_id: string;
  name: string;
  endpoint: string;
  status: string;
  paired_at: number;
}

export const accounts = {
  byEmail(email: string): Account | undefined {
    return db.prepare("SELECT * FROM accounts WHERE email = ?").get(email.toLowerCase()) as
      | Account
      | undefined;
  },
  byId(id: string): Account | undefined {
    return db.prepare("SELECT * FROM accounts WHERE id = ?").get(id) as Account | undefined;
  },
  create(a: Account): void {
    db.prepare(
      "INSERT INTO accounts (id, email, pw_hash, created_at) VALUES (?, ?, ?, ?)"
    ).run(a.id, a.email.toLowerCase(), a.pw_hash, a.created_at);
  },
};

export const homes = {
  forAccount(accountId: string): Home[] {
    return db.prepare("SELECT * FROM homes WHERE account_id = ? ORDER BY paired_at").all(accountId) as Home[];
  },
  create(h: Home): void {
    db.prepare(
      "INSERT INTO homes (id, account_id, name, endpoint, status, paired_at) VALUES (?, ?, ?, ?, ?, ?)"
    ).run(h.id, h.account_id, h.name, h.endpoint, h.status, h.paired_at);
  },
  setStatus(id: string, status: string): void {
    db.prepare("UPDATE homes SET status = ? WHERE id = ?").run(status, id);
  },
};

export const sessions = {
  create(token: string, accountId: string, ttlSec: number): void {
    const now = Math.floor(Date.now() / 1000);
    db.prepare(
      "INSERT INTO sessions (token, account_id, created_at, expires_at) VALUES (?, ?, ?, ?)"
    ).run(token, accountId, now, now + ttlSec);
  },
  get(token: string): { account_id: string; expires_at: number } | undefined {
    return db.prepare("SELECT account_id, expires_at FROM sessions WHERE token = ?").get(token) as
      | { account_id: string; expires_at: number }
      | undefined;
  },
  destroy(token: string): void {
    db.prepare("DELETE FROM sessions WHERE token = ?").run(token);
  },
  prune(): void {
    db.prepare("DELETE FROM sessions WHERE expires_at < ?").run(Math.floor(Date.now() / 1000));
  },
};

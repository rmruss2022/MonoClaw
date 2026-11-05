/**
 * Idempotent account/home seeding from env vars — so credentials never land in
 * source. Used two ways:
 *   • CLI:  `node --experimental-strip-types src/seed.ts`
 *   • Boot: index.ts calls seedFromEnv() when SEED_EMAIL is set (handy on
 *           Railway, where there's no shell to run a one-off against the volume).
 *
 *   SEED_EMAIL, SEED_PASSWORD, SEED_HOME_NAME, SEED_HOME_ENDPOINT
 */
import { randomUUID } from "node:crypto";
import { accounts, homes, type Account } from "./db.ts";
import { hashPassword } from "./auth.ts";

export function seedFromEnv(): void {
  const email = (process.env.SEED_EMAIL ?? "").trim().toLowerCase();
  const password = process.env.SEED_PASSWORD ?? "";
  const homeName = process.env.SEED_HOME_NAME ?? "My home";
  const homeEndpoint = (process.env.SEED_HOME_ENDPOINT ?? "")
    .replace(/^https?:\/\//, "")
    .replace(/\/+$/, "");

  if (!email) return; // nothing to seed
  let account: Account | undefined = accounts.byEmail(email);
  if (account) {
    console.log(`[seed] account exists: ${email}`);
  } else {
    if (!password) {
      console.log(`[seed] ${email} not found but SEED_PASSWORD unset — skipping create`);
      return;
    }
    account = { id: randomUUID(), email, pw_hash: hashPassword(password), created_at: Date.now() };
    accounts.create(account);
    console.log(`[seed] created account: ${email}`);
  }

  if (homeEndpoint) {
    const existing = homes.forAccount(account.id).find((h) => h.endpoint === homeEndpoint);
    if (existing) {
      console.log(`[seed] home exists: ${homeEndpoint}`);
    } else {
      homes.create({
        id: randomUUID(),
        account_id: account.id,
        name: homeName,
        endpoint: homeEndpoint,
        status: "unknown",
        paired_at: Date.now(),
      });
      console.log(`[seed] paired home: ${homeName} → ${homeEndpoint}`);
    }
  }
}

// Run directly as a CLI.
if (import.meta.url === `file://${process.argv[1]}`) {
  if (!process.env.SEED_EMAIL || !process.env.SEED_PASSWORD) {
    console.error("Set SEED_EMAIL and SEED_PASSWORD.");
    process.exit(1);
  }
  seedFromEnv();
  console.log("[seed] complete.");
}

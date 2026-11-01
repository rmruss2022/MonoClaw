# openhome · cloud (control-plane)

The thin identity + routing layer that turns openhome from a single appliance
into a product:

```
public app ──► openhome-cloud ──► routes you to YOUR hub
               (accounts + directory)   (direct, token-authed, local-first)
```

It does **three things and nothing more**:

1. **Accounts** — email/password signup, login, 30-day sessions.
2. **Directory** — which home(s) an account owns and each hub's public endpoint.
3. **Routing grant** — on `/api/home` it issues a short-lived, home-scoped
   **home token** (HMAC-signed `{aid,hid,exp}`). The app carries it straight to
   the hub, which verifies it locally. **House data never flows through here.**

Zero runtime dependencies: Node 22 `http` + built-in `node:sqlite`.

## API

| Route | Method | Auth | Purpose |
|-------|--------|------|---------|
| `/health` | GET | — | Liveness + whether home tokens are configured |
| `/api/signup` | POST | — | `{email,password}` → create account + session |
| `/api/login` | POST | — | `{email,password}` → session (`token` in body + cookie) |
| `/api/logout` | POST | session | Destroy session |
| `/api/me` | GET | session | `{account, homes[]}` |
| `/api/home` | GET | session | `{endpoint, homeToken}` — the routing resolution |
| `/` | GET | — | Themed web sign-in page |

Session travels as the `oh_cloud_sess` cookie (web) or `Authorization: Bearer`
(native app).

## The hub side

Each hub shares `HOME_TOKEN_SECRET` with this service and accepts the home token
as its `oh_auth` cookie (see `services/hub/src/auth.ts` → `validHomeToken`). Pin
`OPEN_HOME_HOME_ID` on a hub so only *that* home's grants are accepted.

## Env

See `.env.example`. The critical one is **`HOME_TOKEN_SECRET`** — it must be
identical here and on every hub, or grants won't verify.

```bash
HOME_TOKEN_SECRET=$(node -e "console.log(require('crypto').randomBytes(32).toString('hex'))")
```

## Run locally

```bash
cd open-home/services/cloud
HOME_TOKEN_SECRET=dev-secret npm start           # :8080
# seed an account (credentials via env, never committed):
SEED_EMAIL=you@example.com SEED_PASSWORD=secret12 \
  SEED_HOME_NAME="My home" SEED_HOME_ENDPOINT=home.bedrock.casa npm run seed
```

## Deploy to Railway

1. **New project → Deploy from repo** (or `railway up` from this folder). Set the
   service **Root Directory** to `open-home/services/cloud`. Nixpacks + Node 22
   are pinned (`nixpacks.toml`, `railway.json`).
2. **Add a Volume**, mount at `/data`, and set `DATA_DIR=/data` so accounts
   survive redeploys.
3. **Variables:** set `HOME_TOKEN_SECRET` (same value goes on the Pi hub).
   `PORT` is injected by Railway.
4. **Seed the first account** once (Railway shell or a one-off):
   `SEED_EMAIL=… SEED_PASSWORD=… SEED_HOME_ENDPOINT=home.bedrock.casa npm run seed`
5. (Optional) Add a custom domain, e.g. `app.bedrock.casa`, in Railway settings.

Then point the mobile app's control-plane base at the Railway URL (or custom
domain) and wire login → `/api/home` → hub.

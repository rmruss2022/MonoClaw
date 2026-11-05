# Long-Term Memory

## 🎬 Creator Cut — hosted + Claude gateway (Nov 1, 2026)

**creator-cut** = Matthew's private GitHub repo `rmruss2022/creator-cut` (TS monorepo: `server` Express + `web` React/Vite + `shared`), an AI editor that **cuts footage to the downbeat of a song** — two modes: music-video (beat-cut) and ad (Claude writes copy + vision-scores clips, Pillow sets text, ElevenLabs voiceover, ffmpeg renders). Local-first. Cloned to `/tmp/creator-cut` using the **`gh` OAuth token still in `/root/.config/gh/hosts.yml`** (the `gh` binary is gone but the token works for git/API; user `rmruss2022`). NOT React Native — it's React+Vite; the macOS path is Electron/Tauri, not RN.
- **ccut-gateway** (`/root/MonoClaw/ccut-gateway/server.mjs`, Node stdlib, systemd `ccut-gateway.service`, loopback :18850) wraps the droplet's **signed-in `claude` CLI** as an HTTP endpoint so the app runs vision+copy **with NO Anthropic API key** (rides the Claude Code sub). Public at **`https://ccut-llm.bedrock.casa`** (bedrock tunnel ingress + CNAME). Hardened: bearer token (in `ccut-gateway.env`, chmod 600, gitignored), Read-only tools forced server-side, isolated temp cwd/call, model allowlist (default **sonnet**), concurrency cap 3, per-call timeout, body cap 28MB, daily budget 2000. POST `/v1/claude {prompt,model,tools,files:[{name,b64}]}` → `{stdout}` (the CLI JSON envelope). `GET /health` open.
- **App wiring:** `server/src/lib/vision/cli.ts` `runClaude()` now POSTs to the gateway when `CREATORCUT_CLAUDE_URL`+`CREATORCUT_CLAUDE_TOKEN` are set (ships cwd frames as files); `cliAvailable()`/`resolveProvider()` treat a configured gateway as available. Local CLI + API-key paths untouched. Fixed the broken `./run` (pointed at old `bin/downbeat.mjs`→`creatorcut.mjs`). Added Linux font fallback to `draw.py`. All 195 `npm -w server run check` pass. Pushed to **main** (f087127).
- **Hosted on Railway** (project `creator-cut`, acct russellm22@vt.edu): **`https://creator-cut-production.up.railway.app`** — Dockerfile (node20+ffmpeg+python3-pil+fonts), binds 0.0.0.0 behind `CREATORCUT_TOKEN` (token in `ccut-gateway/creatorcut-web.env`; current = `08cbd1ffff5bf14efaae94c12a55eaae9443d15e4e11a472`; open with `/?token=<that>`). Verified `/api/health` → `vision:true, provider:cli`. Redeploy: `cd /tmp/creator-cut && railway up --service creator-cut`. ⚠️ Railway storage ephemeral (no volume yet → renders/projects reset on redeploy); heavy 4K renders slow on shared CPU; Photos import is macOS-only (off on host).
- **macOS app:** `desktop/` Electron shell scaffolded (boots local server, native window). `.dmg` must build on a Mac (`cd desktop && npm i && npm run dist:mac`). ffmpeg-bundle/Pillow-vendor/data-dir still TODO for a shipped app (noted in desktop/README).
- ⚠️ A **background auto-committer runs on MonoClaw** (sweeps staged files into commits/amends; folded ccut-gateway into HEAD `bbcb97f`). Harmless but don't fight it; explicit `git commit` may report "no changes" if it already swept.

## 🌙 Night Sweep agent — nightly autonomous review+implement (Nov 1, 2026)

`/root/MonoClaw/nightsweep/nightsweep.sh` — gated nightly pipeline (cron **3 AM ET**, DST-safe UTC-guard `0 7,8 * * *` + `TZ=America/New_York ...=="03"`; uses the **`claude` CLI headless**, NOT gateway in-cron LLM which is broken). 8 gates each verified by a "doctor"; critical gate fail halts + pings. **FULL AUTONOMY (Matthew opted in Nov 1): it commits, deploys to prod, AND pushes to origin+main.** Flow: doctor(env) → gather (24h git log/status/diff + today's memory) → **plan** (claude read-only → `reports/<date>.md` with `## Changes`, `## Suggestions for tomorrow`, ```json `safe_changes` 0-3 items) → **implement** (claude edits + stages its files on the current branch) → **doctor** (`tsc` on changed TS + `ast.parse` on changed .py; auto-revert staged + abort on fail) → commit → **deploy** (`deploy_dir`: restart droplet systemd svc / `railway up` / re-export recilia web; **health-check each; on fail → `git revert` the commit + redeploy**) → **push** (origin current branch + `HEAD:main` if FF) → compose → deliver (Telegram summary-of-summary to 5574760589). Report has a **"How to revert"** section with the exact `git revert <sha> && git push` command (Matthew's escape hatch). `DRY=1` = plan+report only, no edits/deploy/push. Reports in `nightsweep/reports/`, logs in `nightsweep/logs/`. Doctor+health-check is the hard safety: nothing broken deploys/ships. Tested DRY Nov 1 — 8/8 gates pass. To dial autonomy: edit the `plan` prompt's policy / the `deploy_dir` map / cron guard.


## 🌿 Nightbloom (tinnitus app, repo dir `recilia`) — consumer rebuild (Nov 1, 2026)

**User-facing name is now "Nightbloom"** (renamed from Recilia Nov 1). Repo dir stays `/root/MonoClaw/recilia`, bundle id `health.recilia.app`, Railway project `recilia-api`, host `recilia.bedrock.casa`, Expo slug `recilia` — all internal, UNCHANGED (don't rename). Only display strings/logo/app.json `name` are Nightbloom. Garden metaphor is the whole brand: tend a night-garden; tool icons are garden motifs (dewdrop/leaf-stem/vine/bloom/sprout). Shared copy in `src/content.ts`.
- **Visual-QA system (Nov 1):** no browser on the droplet, so installed **Playwright + headless Chromium** at `/root/shots/` — `node /root/shots/capture.js` screenshots the live web build (mobile viewport, can seed a grown garden via localStorage key `recilia-profile-v1`). Use it to audit/verify any recilia UI change. Grove screen rebuilt Lumen-style: **Light currency (=growth), Level, progress bar, daily-goal card, streak flame, stats, achievements**, and a rich layered night-garden SVG (moon, stars, fireflies, hills, varied glowing flora: flowers/mushrooms/buds/stalks). **Font gotcha:** Orbitron's heavy `0` renders as a tofu box — use Space Grotesk (`SpaceGrotesk_700Bold`) for numerals that can be 0.

`/root/MonoClaw/recilia` — React Native/Expo/TS tinnitus app (EAS project `tigertroll14/lumen`? no — its own; bundle TBD). Matthew repositioned it from clinical→**consumer/gamified** ("keep the research, remove the restrictions"). Changes made (all type-check clean, `npx tsc --noEmit` = 0 errors; native app, shows on next Expo/EAS build — NOT a live deploy):
- **Removed clinical gates:** forced Triage red-flag screen (nav now opens to Grove), startup "not a medical device" modal (App.tsx), Home's mandatory ~10-min "measurement first" assessment gate (`assessmentDone`) — all 6 tools now open from launch. RI/"Quiet" no longer hard-blocks on Match (defaults to 6 kHz) and dropped the "this is NOT relief" framing.
- **KEPT on purpose (do not remove without explicit ok):** engine hearing-safety volume cap `MAX_GAIN 0.55` / `HYPERACUSIS_MAX_GAIN 0.25` in `src/audio/engine.ts` — removing risks hearing damage + App Store rejection. Triage/TFI/PTM screens still exist but are now optional/unlinked.
- **Nightbloom** gamification (the brand/principle: practice "tends the quiet" and grows a bioluminescent night-garden = visible habituation): new `src/screens/GardenScreen.tsx` (SVG, landing route `Grove`), growth model in `src/state/store.ts` (`growth/streak/bestStreak/tendDays/sessions/toolsUsed`, `tend(points,tool)`, stages Seed→Luminous, `bloomCount`, `ACHIEVEMENTS` + unlock modal). All 5 tools call `tend()`: quiet, blend, sweep, match, checkin. Home has a Nightbloom banner.
- **Web-hosted at `https://recilia.bedrock.casa`** (Nov 1): Expo **web export** (`npx expo export -p web` → `dist/`), served by **`recilia-web.service`** (`python3 -m http.server 18845 --directory .../recilia/dist`) behind the bedrock tunnel (ingress :18845 + proxied CNAME). The native-only audio lib **`react-native-audio-api`** is aliased on web to `src/shims/audioApiWeb.ts` via `metro.config.js` (maps to the browser's Web Audio API; AudioManager stubbed). **To update the web preview:** re-run `npx expo export -p web` in `/root/MonoClaw/recilia` then `systemctl restart recilia-web`. Dash card now links here (public). Real distribution is still EAS→TestFlight/App Store.
- **Accounts + grove sync (production, Nov 1):** backend `/root/MonoClaw/recilia-api/` (Python stdlib + SQLite, pbkdf2 + bearer tokens, CORS-open; endpoints `/health /auth/signup /auth/login /me /me/profile`). **Deployed to Railway** project `recilia-api` (own project, volume at `/data`) → **`https://recilia-api-production.up.railway.app`** (verified signup/sync/read end-to-end). App side: `src/api.ts` (API_BASE = that URL), store auth slice (`authToken/authEmail`, `signIn/signOut/syncPush`, `syncableProfile`), `src/screens/AuthScreen.tsx`, debounced push in App.tsx, guest-first sign-in link on the Grove screen. **Login is OPTIONAL/guest-first** (don't make it a gate). Redeploy API: `cd recilia-api && railway up -y` (project already linked).
- Still TODO/optional: Match "octave challenge" friction; deeper polish; verify web audio actually plays in-browser (autoplay/gesture); building/submitting to App Store.
- **App Store Connect (Nov 1):** Bundle ID **`health.recilia.app`** REGISTERED in ASC (name "Nightbloom", UNIVERSAL, ASC id `GBM4MS53W7`, team seed `5RDPA99DY5`) via the **shared Lumen ASC API key** (`/root/.lumen-asc-api-key.p8`, issuer `182c0a6f-d589-4013-a89b-ec1c62ab8097`, kid `4M5SWS426L` — same Apple team as Lumen/openhome). Matthew creates the App record himself. **ASO package built** in `/root/MonoClaw/recilia/store/`: `LISTING.md` (name/subtitle/keywords/description/promo/what's-new/review-notes — all honest-framing: distress/attention/sleep, NEVER "quieter"), and **6 App Store screenshots** at 1320×2868 (6.9") in `store/screenshots/` (01-home…06-evidence). Screenshots are DESIGNED marketing frames (device frame + caption + sample data), rendered from `store/shots.html` via headless Chromium (`/root/.cache/ms-playwright/chromium-1248/.../chrome --headless=new --no-sandbox --screenshot`, served over a temp `http.server` since file:// is blocked). To regenerate: serve `store/` and screenshot `shots.html?s=0..5`. Upload-to-ASC tooling exists: `/root/asc-tools/upload_screens.py` (reserves+uploads appScreenshots once the app record + version exist). Alt: `/root/shots/capture.js` captures REAL live web-build UI if authentic screenshots preferred. Privacy Policy URL still MUST exist before submit.


## 🌐 bedrock.casa — permanent public URLs for all apps (Oct 31, 2026)

Bought Cloudflare domain **`bedrock.casa`** (Cloudflare Registrar, zone id `5a8af03d0dbbd451010212cab36a0b2e`, account `2810a857921c6dadee1d28a2ffb08456`). It now fronts all the droplet apps with permanent HTTPS URLs via a single Cloudflare **named tunnel**.
- **Droplet tunnel:** name `bedrock`, id **`587e53e4-0521-4fea-9717-a1fcd9b81144`**, remotely-managed (`config_src=cloudflare`, ingress set via API, NOT a local config.yml). Runs as systemd **`bedrock-tunnel.service`** (enabled, 4 QUIC conns) → `cloudflared --no-autoupdate tunnel run --token-file /etc/cloudflared/bedrock-token`. Token also at `/root/.openclaw/credentials/bedrock-tunnel.token` (600).
- **Hostname → local port (ingress + proxied CNAME → `<tid>.cfargotunnel.com`):** `bedrock.casa` & `www` & `dash` → **:18824 (the "Dash" portfolio landing — `portfolio/server.py`, this is what Matthew means by "dash portfolio")**, `apps` → :18823 (My Apps catalog), `reports` → :18820 (daily digest portal), `portfolio` → :18824, `travelog` → :18825, `inkling` → :18826, `croppa` → :18842, `slipstream` → :18843, `rolodex` → :18831, `waypoint` → :18822. Catch-all → 404. All verified HTTP 200 externally.
- **Dash portfolio** (`portfolio/server.py`, :18824) is the apex landing: app cards now link to the permanent `*.bedrock.casa` URLs (was dead Tailscale `bushwick.tail9d821f.ts.net` HUB links); has an **"Apps"** section + a **"Claw Apps"** section (Daily Reports & News → reports.bedrock.casa). The old rotating-tunnel `public_url.txt` lookups in render() were removed. The separate `appcatalog` "My Apps" page (:18823, now at apps.bedrock.casa) also got a Claw Apps category earlier.
- **`home.bedrock.casa` is a SEPARATE tunnel** (openhome, id `3202b8c7-…`, runs on the **Pi** via `/etc/cloudflared/token`). Returns 401 = hub login gate (pw `velvet-harbor-cedar-81`). Don't touch it when editing the droplet tunnel. (A leftover droplet quick-tunnel to :4700 still runs — orphaned, harmless.)
- **Retired:** the old rotating `trycloudflare.com` quick-tunnel services (`reports/portfolio/travelog/inkling/croppa/chase/rolodex-tunnel`) are **disabled** — replaced by bedrock. App servers (python) still run on their ports independently. `portal/data/public_url.txt` pinned to `https://reports.bedrock.casa` (stops the rotating-URL texts).
- **To add an app:** add an ingress rule (PUT `/accounts/<acct>/cfd_tunnel/<tid>/configurations`) + a proxied CNAME (`<sub>` → `<tid>.cfargotunnel.com`) via the CF API token. Cloudflare auto-issues the HTTPS cert in seconds; no cert files.
- **Marquee** (NYC events calendar, repo `/root/MonoClaw/nyc-events/server.py`, single-file stdlib http.server, `nyc-events.service` on **:18852**, public at **`https://marquee.bedrock.casa`**, added Nov 3). Keyless live data: **Gemini with Google Search grounding** (`tools:[{google_search:{}}]`, needs GEMINI_API_KEY) returns real current NYC events w/ real links → cached `data/events.json`, background-refresh when stale (12h). Month calendar + upcoming list + category filters. **Location-aware**: home base **Bushwick, Brooklyn** (`MARQUEE_HOME`); fetch biases toward Brooklyn/near-Bushwick events; each event tagged `borough` + `near_home`; UI has a 📍 header pill + `[All NYC | ★ Near me | Brooklyn]` filter + "near you" badges; dash widget bubbles near-you first. **Category icons** (11 cats incl. Wellness 🧘) on chips/badges. **Personal events**: "+ Add event" modal → `data/personal.json` (gitignored), recurring (weekly weekday toggles, JS Sun=0) or one-off; expand+merge at request time; MINE badge + delete ×; API `POST /api/personal/add|delete`. Default view is **This week** + **★ Mine** filter (opens on Matthew's own events for the week; All NYC/Near me/Brooklyn/Upcoming/Calendar still available). Seeded **Matthew's Baby Cobra Yoga** (47 Thames St #206, Bushwick) — runs **DAILY** evening classes (he goes ~7pm; ClassPass `classpass.com/studios/baby-cobra---bushwick-brooklyn` is the real daily schedule, Tickettailor only lists special workshops). Recurrence = daily 7pm; scan **augments** (doesn't replace) with Tickettailor specials. Also seeded **Williamsburg Run: Founders, Creatives & Coffee** (Founders House, `luma.com/hhndqkur`) — weekly **Wed 7:30am** 5K from Padel Haus Williamsburg (near-home, Wellness). **Luma pages are Firecrawl-scannable** via the generic `fc_scrape`. De-dup normalizes to start time so scanned occurrences don't double the recurrence. **Content cache**: `fc_scrape` is cache-first — scrapes cached to `data/cache/<sha1>.json` (TTL `MARQUEE_CACHE_H`=12h), serves cache instantly, falls back to stale cache if a live crawl fails. **Background crawl agent** (`crawler_loop`, every `MARQUEE_CRAWL_EVERY_H`=6h) refreshes regulars' source pages + re-extracts. `/health` reports `cached_pages`. **Admin panel** at `/admin` (linked from app footer): hand-built SVG architecture diagram (Client → Server+stores → 3 agents [Discovery=Gemini grounding, Crawl=Firecrawl 6h, Extract=Gemini] → External), live agent status, content-cache table, regulars table w/ per-row Scan, controls (refresh/re-crawl/clear-cache). Endpoints `/api/admin`, `/api/admin/clear-cache`. **Multi-source events** (`SOURCES`, `build_all_events()` runs in parallel): our internet search (Gemini grounding, source="Search") + platform listings Firecrawl-scraped + Gemini-extracted, each event tagged `source` + "via X" badge. ON: DICE, Shotgun, Eventbrite (verified NYC-correct). OFF by default: Resident Advisor (ra.co scrape returns mixed/DC — no geo without the app; needs RA API), Bandsintown, Songkick, Fever, Posh. Luma city pages JS-blocked → Luma only for specific regular events. Admin has an Event sources table. Now **Firecrawl-scanned**: `scan_url`=tickettailor.com/events/babycobrayoga, `location_match`=Bushwick. **Firecrawl agent**: `fc_scrape()` → Firecrawl API v2 (`FIRECRAWL_API_KEY`, key `fc-…` lives in `/root/.openclaw/openclaw.json` + the nyc-events.service env) → Gemini extracts real sessions → stored in record `sessions[]` (takes priority over weekday recurrence). `POST /api/personal/scan {id}`; auto-scans stale (>24h) regulars on boot. **My-events view**: `★ Mine` filter + "Scan for real times" button. **Add to calendar**: every card has 📅 (client-side .ics download → opens iOS/Google Calendar) + ＋ to save a discovered event into My events. Category icons are real **inline SVG** (not emoji). Events now require a **deep-link listing URL** (anti-hallucination), temp 0.1, LLM timeout 240s. Dash integration: Claw App card (icon key `marquee`) + a "What's on in NYC" widget fed by portfolio's same-origin `/api/events-widget` proxy → `127.0.0.1:18852/api/widget` (avoids CORS). Grounded fetch is slow (~60-120s); urllib timeout 150s. Dash **to-do widget already exists** (top of dash, `dash_todos_v1` localStorage).
- **Vantage** (consumer name for the **Content Engine**, repo `/root/MonoClaw/contentforge`, its own nested git repo) — content-intelligence engine: Prong 1 competitor search via **xpoz** (mcporter, `getTwitterPostsByKeywords` etc) + Gemini LLM breakdown (LIVE); Prong 2 editor/EditSpec → Creator Cut (scaffolded, needs CC `/api/render-from-spec`); Prong 3 distribution (scaffolded). Python stdlib `server.py`, `contentforge.service` on **:18851** (env GEMINI_API_KEY + GEMINI_MODEL=gemini-flash-latest). Public at **`https://vantage.bedrock.casa`** (bedrock tunnel ingress + CNAME, added Nov 3). Needs mcporter on PATH at runtime for prong-1 (fine on droplet; a plain Railway image won't have it). Dash card key `vantage` (radar icon); Foreman roster slug `contentforge`.
- **Foreman board avatars** (`portfolio/server.py`): each job lane shows its app icon — PNG from `portfolio/avatars/<slug>.png` (generated by `foreman/make_avatars.py` from app icons) → else the dash's branded SVG tile (`_FOREMAN_ICON_KEYS` maps foreman slug → `ICONS` key) → else coloured initial. Job titles are concise Gemini-generated descriptions cached in `foreman/titles.json` (gitignored); needs `GEMINI_API_KEY` in portfolio.service env (systemd drop-in `/etc/systemd/system/portfolio.service.d/gemini.conf`).
- **Foreman heartbeat + acceptance gates** (built Nov 3, `foreman/doctor.py` now a heartbeat+verification engine). A finished job clears 3 gates: (1) pipeline test (`doctorCmd`), (2) **photo evidence** — `evidence_shot.js` screenshots the project's live `url` (new field in `projects.json`) → `data/evidence/<run_id>.png`, served by dash at `/evidence/<id>.png`; uses `/root/shots/node_modules/playwright` + `--no-sandbox`, (3) **acceptance criteria** — set at intake via `job.py --accept "…"` (repeatable) or inline `accept: a; b; c`, stored in `data/jobs.json` keyed by label, embedded in the subagent brief, verified per-criterion by **Gemini vision** against the evidence screenshot. Overall ok = tests AND all criteria. `verdicts.json` is now rich `{ok,tests,evidence,acceptance[],acceptance_ok}`. Doctor writes `data/heartbeat.json` each poll (running/verifying/healthy/failing + stuck>`FOREMAN_STUCK_MIN` 30m). `foreman-doctor.service` needs `GEMINI_API_KEY` (drop-in `env.conf`) + node on PATH. Dash shows a pulsing heartbeat bar + per-card test/criteria pills + evidence thumb; modal shows full checklist + test PASS/FAIL + full evidence photo. Runtime stores (jobs.json, heartbeat.json, evidence/) gitignored. **To send a job with criteria:** `python3 foreman/job.py "<slug>: <task>" --accept "<criterion>" --accept "<criterion>"` then spawn with the printed brief.
- ⚠️ **CF API token:** `CF_API_TOKEN` in `/root/.openclaw/credentials/cloudflare.env` is now **FULL-ACCESS** (Matthew widened it Oct 31). It fails `/user/tokens/verify` ("Invalid API Token") but DNS/zone/tunnel API calls succeed — the verify quirk is harmless. **Should be narrowed to DNS:Edit + Tunnel:Edit (or rolled)** when convenient; it's broad and was pasted in chat. The earlier R2 keys in that file are also exposed → roll.
- TODO (not yet done): Cloudflare Access (per-user login) in front of the dashboard/apps — they're currently open to the internet (same as before, when they were on quick tunnels). Needs a one-time "Enable Access" click in Zero Trust.

## 🏠 openhome Pi — access + deploy (Oct 31, 2026)

**The openhome hub runs on a Raspberry Pi at Matthew's home** (NOT on the droplet — speaker mDNS + Bluetooth discovery only work on the home LAN).
- **Reach it via Tailscale.** Tailscale is now installed on the droplet (`bushwick-v16`, tailnet IP `100.81.110.49`, acct `mattrussellc@`). The Pi is tailnet node **`pi` = `100.98.117.57`** (MagicDNS `pi.tail9d821f.ts.net`), Debian 13 trixie, Node v26.7.0, offers exit node.
- **SSH:** `ssh pi@100.98.117.57` — droplet's key (`/root/.ssh/id_ed25519.pub`, `openclaw-new-box@bushwick-v16`) is in the Pi's `~/.ssh/authorized_keys`. `~/.ssh/config` has an accept-new block for `*.tail9d821f.ts.net`. Pi's regular sshd (Tailscale SSH NOT enabled on the Pi). `pi` has **passwordless sudo**.
- **Hub location:** `/home/pi/open-home` (plain file copy, **NOT a git repo**). Systemd unit `open-home-hub.service` (enabled, auto-restart), ExecStart `/home/pi/open-home/start-hub-pi.sh` → `node --experimental-strip-types services/hub/src/index.ts`, **port 4700** (HTTP) + 4443 (HTTPS/voice), agent = Gemini (cloud opt-in). Creds in `/home/pi/.openhome/{spotify,google-genai}.env`.
- **To deploy latest code:** rsync from droplet `/root/MonoClaw/open-home/` → Pi `/home/pi/open-home/`, EXCLUDE `.git node_modules data/ .data/ start-hub-pi.sh certs/ *.env` (these are Pi-local), then `sudo systemctl restart open-home-hub.service`. The droplet is the source of truth for code. Done once Oct 31 (synced new `auth.ts` + updated `index.ts`; backup tarball left at `/home/pi/open-home-src-backup-*.tgz`). Verified HTTP 200 on 4700, clean restart.
- Known noise: a Bluetooth speaker "X10" (`F4:4E:FD:49:83:98`) is offline and retries pairing endlessly in logs — pre-existing, ignore.

## 🤖 Multi-agent Telegram bots — config pattern + builder added (Oct 31, 2026)

OpenClaw runs **multiple agents, one Telegram bot each**, all in `/root/.openclaw/openclaw.json`. To add an agent like Claw:
1. `agents.list[]` += `{id, name, workspace:/root/MonoClaw/agents/<id>, agentDir:/root/.openclaw/agents/<id>/agent, model:"anthropic/claude-opus-4-8", models:{...agentRuntime.id:"claude-cli"}}` (mirror the `ora` entry).
2. `channels.telegram.accounts.<id>` += `{name, botToken, enabled:true, dmPolicy:"allowlist", allowFrom:[5574760589], groupAllowFrom:["5574760589"]}`.
3. `bindings[]` += `{type:"route", agentId:"<id>", match:{channel:"telegram", accountId:"<id>"}}` — **routing is explicit via bindings**, not name convention.
4. Scaffold the workspace (copy SOUL/AGENTS/TOOLS/USER from `/root/.openclaw/workspace`, own IDENTITY, no MEMORY). Note the old agents' `USER.md` is a **broken symlink** to `/Users/matthew/...` (Mac path) — use a real file.
⚠️ **The gateway `config.patch` API REFUSES these paths** (botToken, agentDir, workspace, name, dmPolicy, allowFrom… are "protected"). Must edit `openclaw.json` directly + restart (back it up first). Paths hot-reload.
- **Current agents:** main (Claw, default bot), sage (career-coach), atlas (tech-lead), ora (Ora Health), **builder (@builder9999bot, id 9093986747 — added Oct 31, mirrors Claw, 🔨)**.
- ⚠️ **Known issue (Oct 31):** `ora`, `atlas`, `raveplanner` bots are in a Telegram getUpdates **conflict loop** (1500+ poller restarts) — another poller holds those tokens, almost certainly the **OLD box (Bushwick 159.223.150.134) gateway still running**. `default` + `builder` are clean. TODO: stop the old box's gateway (or those accounts) to fix.

## ⏰ CRON GOTCHA — this box ignores CRON_TZ (read before scheduling ANY cron job) (Oct 31, 2026)

**The new box (`Bushwick-V16`) runs Debian `cron` (`/usr/sbin/cron -f -P`), whose system clock is UTC and which IGNORES `CRON_TZ`.** Verified with live fire tests Oct 31: jobs scheduled in a `CRON_TZ=America/New_York` crontab fired at the UTC equivalent of the clock time, NOT Eastern. A `CRON_TZ=` line in the crontab is silently useless here.

**Rules for any future system cron job that needs a local (Eastern) time:**
1. Write the schedule fields in **UTC**, not Eastern.
2. Eastern is a moving target: **EDT = UTC-4** (summer), **EST = UTC-5** (winter); DST flips on the US schedule (ends first Sun of Nov, begins second Sun of Mar). A single fixed-UTC line will be an hour off for half the year.
3. **DST-safe pattern:** schedule BOTH candidate UTC hours and gate the command on the actual Eastern hour, so exactly one run happens per day:
   `0 H1,H2 * * * [ "$(TZ=America/New_York date +\%H)" = "HH" ] && /path/cmd`
   where HH = desired Eastern hour (2-digit), H1 = HH+4, H2 = HH+5 (mod 24). Example 8 AM ET → `0 12,13 * * * [ "$(TZ=America/New_York date +\%H)" = "08" ] && ...`
4. In crontab, **escape every `%` as `\%`** (cron treats bare `%` as newline-in-stdin).
5. Alternative for OpenClaw-managed cron: the `cron` tool DOES honor a `tz` field — but gateway in-cron LLM routing is broken on this box (see digest note), so the tool is only safe for non-LLM jobs.
6. Don't `TZ=`-set the whole box or `systemctl set-timezone` — the box is intentionally UTC (logs/services depend on it). Gate per-job instead.

**Verified facts:** root crontab DOES execute (self-test fired, confirmed in `/var/log/syslog` `CRON[...] CMD`); the TZ-guard pattern above fires correctly. Debug by: `crontab -l`, watch `grep 'CRON\[' /var/log/syslog`, compare `date -u` vs `TZ=America/New_York date`.

## 🖥️ Droplet Migration — NEW BOX (Oct 30, 2026)

**Migrated from old droplet to a bigger one.** Everything now runs on the NEW box.
- **New box:** `146.190.214.134` — hostname `Bushwick-V16`, region nyc1, **15 GiB RAM** (the upgrade)
- **Old box (keep until Matthew says destroy):** `159.223.150.134` — hostname `Bushwick`. OpenClaw gateway STOPPED there. SSH works from new box via `/root/.ssh/id_ed25519` (pubkey `openclaw-new-box@bushwick-v16`).
- **What migrated:** `/root/.openclaw`, `/root/MonoClaw`, Postgres `favorly` DB, all app services + cloudflared tunnels, ollama. Telegram live on new box.
- **Rsync gap caught:** original migration only copied `.openclaw` + `MonoClaw`. Recovered the rest of `/root` (lumen scripts + keys, go/node_modules/ora-health-26/groundfloor-nyc/migrate, dotfiles) + `/etc/iptables` + `portfolio-tunnel` systemd override from old box.
- **OpenVPN:** repointed to new IP. UDP `1194` + TCP `443` (`server-tcp443.conf` had old IP hardcoded in `local`). Firewall rules recreated in `/etc/iptables`, `ip_forward` on. New client profiles in `/root/vpn-clients/` (travel-mac, open). Client template repointed.
- **WireGuard:** was active on old box (`wg0`, peer "asus") but NOT migrated (Matthew uses OpenVPN). Config parked dormant at `/root/wireguard-backup-from-old/`.
- **Tailscale:** was disabled on old box — ignored.
- **TODO (Matthew):** confirm DO Cloud Firewall on new droplet allows inbound `443/tcp` + `1194/udp` (host firewall already open; doctl not installed so can't check cloud firewall from box).

## 🔧 NYC Daily Digest — moved off gateway cron (Oct 31, 2026)

The OpenClaw gateway's **in-cron LLM routing is broken** (both Google/Gemini and claude-cli fail fast with "LLM request failed" inside isolated cron agentTurns — 14 consecutive errors; a gateway restart did NOT fix it). The live session LLM works fine; only the spawned-cron path is dead.
- **Fix:** standalone script `/root/MonoClaw/portal/generate_digest.sh` that uses the **`claude` CLI directly** (`claude -p ... --allowedTools "WebSearch WebFetch"`, OAuth, headless web search confirmed working) to compose the briefing as JSON `{briefing, spoken}`, then edge-tts → voice note, `save_report.py` → portal, and `openclaw message send` → Telegram (text + mp3). Logs to `portal/digest.log`.
- **Scheduled via system crontab** (not OpenClaw cron). ⚠️ This box's Debian `cron` **ignores `CRON_TZ`** — all schedules are read as UTC (verified Oct 31 with live fire tests). DST-safe fix: `0 12,13 * * * [ "$(TZ=America/New_York date +\%H)" = "08" ] && .../generate_digest.sh`. Fires at both 12:00 & 13:00 UTC but the inner TZ guard only proceeds at 08:00 ET, so exactly one runs each season (12 UTC in EDT, 13 UTC in EST) → always 8 AM Eastern, never double-runs. cron-run log: `portal/digest-cron.log`. Root crontab execution + the TZ-guard pattern both confirmed firing via syslog.
- **OpenClaw cron `92f827d5-c51f-4d9a-8d1c-3e37381f08f9` DISABLED** (left as dormant backup). Don't re-enable until gateway in-cron LLM is actually fixed.
- Tested end-to-end Oct 31 — delivered text + voice note successfully.

## 📰 Daily Reports Web App (Oct 31, 2026)

Built a new single-page web app for Matthew's daily briefings (NYC Daily Digest + archive).
- **Frontend:** `/root/MonoClaw/portal/webapp/index.html` (zero-dep vanilla JS SPA — parses digest text into section cards, archive list, search, sticky audio player w/ waveform, light/dark, PWA installable). Legacy page still at `/legacy`.
- **Backend:** existing `portal/server.py` on `127.0.0.1:18820` serves the app at `/`, data at `/api/reports`, audio at `/audio/<file>`. Reports = `portal/reports/<date>.json`, voice notes = `media/tts/digest-<date>.mp3`.
- **Public URL:** via `reports-tunnel.service` (cloudflared quick tunnel → 18820). URL rotates on restart; live URL saved to `portal/data/public_url.txt` and Matthew auto-texted on change. (Replaces the dead Tailscale `bushwick.tail9d821f.ts.net` portal.)
- NYC Daily Digest cron feeds it daily at 8 AM ET.

## Agent Swarm Architecture (Feb 11, 2026)

**Vision**: Distributed workforce of specialized agents working in cascade to build production products overnight.

**Core Components**:
- **Orchestrator Agent**: Maintains kanban board, spawns specialists, receives results
- **Specialized Agents**: Product, Research, Architect, Dev, QA, PM
- **Workflow**: Spawn → Complete → Update Board → Spawn Next
- **Communication**: `sessions_spawn`, `sessions_send`, agent-to-agent messaging

**Kanban States**: todo → in-progress → ready → qa → complete

**Use Case**: "Build SaaS dashboard" spawns Product Agent → Dev Agents (parallel) → QA Agent → Deploy Agent, all while user sleeps.

## Model Configuration (Feb 11, 2026)

**Default Model**: nvidia/moonshotai/kimi-k2.5
- Context: 256K tokens
- Reasoning: Enabled
- Cost: Free via NVIDIA API
- **When to use**: Default for all agents, sub-agents, hooks

**Legacy Options**:
- `anthropic/claude-sonnet-4-5` (alias: sonnet) - previous default
- `anthropic/claude-opus-4-6` (alias: opus) - for complex analysis

## Job Search Pipeline

**Status**: Active job search, multiple opportunities in pipeline
**Location**: Jobs dashboard at http://localhost:3003
**Memory**: Check daily memory files for interview details and follow-ups

## Technical Preferences

**Voice Output**: Manual curl to voice server required for webchat (auto-hooks disabled due to chunking issues). Always post complete response text to http://127.0.0.1:18790/speak

**Cron Wake Mode**: Use "now" for time-critical jobs (not "next-heartbeat") to ensure reliable execution.

**Email Filtering**: Only announce urgent categories (jobs, appointments, financial). Silence marketing/promotional.

## System Architecture

**Environment Security** (Updated Feb 20, 2026):
- **API Keys**: Stored in `~/.openclaw/.env` (600 permissions)
- **Gateway Launch**: Via wrapper script `~/.openclaw/gateway-wrapper.sh` that sources .env
- **LaunchAgent**: `~/Library/LaunchAgents/ai.openclaw.gateway.plist` - no keys exposed
- **Why**: Removed hardcoded keys from openclaw.json and plist files for security

**Gmail Integration** (Updated Feb 12, 2026):
- **Polling-based** (not push) - Every 10 minutes via cron
- **Cron ID**: `3956a4f1-f07b-4ce6-869d-5d69664debb2`
- **Why**: Push hooks caused 38 parallel processes → session store lock contention
- **Solution**: Single isolated agent processes emails sequentially
- **Model**: nvidia/moonshotai/kimi-k2.5 (free)
- **Delivery**: Urgent emails only to Telegram (5574760589)
- **Trade-off**: 10-min delay acceptable for non-critical emails

## Active Services & Dashboards

**Core Infrastructure:**
- **Voice Server** (port 18790) - Edge TTS, manual posting for webchat
- **Activity Tracker V3** (LaunchAgent) - Polls session transcripts every 5s
- **Token Tracker** (port 18791) - Cost tracking, $558.63/month current
- **ActivityHub/ActivityClaw** (port 18796) - Activity monitoring & logging
- **ContextClaw** (port 18792) - Context management

**Command & Control:**
- **Mission Control** (port 18795) - Central hub, links to all dashboards
- **MonoClaw Dashboard** (port 18802) - System overview

**Project Dashboards:**
- **Agent Swarm Dashboard** (port 18798) - Kanban board for agent orchestration
- **Jobs Dashboard** (port 3003) - Job application tracking
- **Raves Dashboard** (port 3004) - Social/events tracking
- **Moltbook Dashboard** (port 18794) - [Purpose TBD]
- **Arbitrage Scanner** (port 3005) - Prediction market arbitrage detection
- **Vision Controller** (port 18799 + backend 9000) - Gesture detection via webcam + gesture window manager (headless mode via `run_headless.py`)

**Automation:**
- **Daily Blog Generator** - Cron job at 6:00 PM, auto-generates & deploys posts
- **Gmail Scanner** - Cron job every 10 minutes, alerts urgent emails via Telegram
- **LaunchAgents** - Activity tracker, token collector, voice server

## Projects Active

**Doctor Strange Hand Lab** (Feb 21-28, 2026)
- Status: Complete, both modes working
- Location: `/Users/matthew/.openclaw/workspace/doctor-strange-hand-lab/`
- Stack: Vanilla JS + Vite + Three.js + MediaPipe HandLandmarker
- Run: `cd doctor-strange-hand-lab && npm run dev`
- Features:
  - **Arcane Shield mode**: Hand-tracked mandala with petal rosettes, star polygons, seed-of-life, glyphs, shards, particle system, UnrealBloomPass bloom
  - **Astral Wireframe mode**: GPU-deformed icosahedron following index finger, second hand pinch controls spin speed, palm rotation controls morph, pinch-then-open-palm triggers fragment explosion with shockwaves/tendrils/particle trails
  - Two-hand resonance bridge (lightning arc between hands in shield mode)
  - CSS `mix-blend-mode: screen` composites effects over webcam feed
- Architecture: `main.js` (renderer + frame loop), `handTracking.js` (MediaPipe), `shieldScene.js` (mandala), `wireframeScene.js` (artifact + explosion)

**Gesture Window Manager** (Feb 28, 2026)
- Status: Backend complete, tested and working
- Location: `/Users/matthew/.openclaw/workspace/vision-controller/`
- Run: `cd vision-controller/backend && python3 -u run_headless.py` (from Terminal.app for camera access)
- Test: `python3 test_snap.py` (interactive snap testing, no camera needed)
- Stack: Python + FastAPI + MediaPipe + OpenCV + PyObjC (Quartz + Accessibility API)
- Features:
  - Headless mode captures webcam directly via OpenCV, no browser needed
  - Point (1 finger) = select frontmost window + full screen snap
  - Peace (2 fingers) = half screen snap (hand position = left/right)
  - Four fingers = quarter screen snap (hand position = quadrant)
  - Open palm = deselect window
  - Auto-detects all monitors via Quartz CGDisplayBounds
  - Moves/resizes windows via macOS Accessibility API (AXUIElement)
- Display layout: External 1920x1080 at (-1920,0) LEFT, MacBook 1512x982 at (0,0) RIGHT
- Permissions: Camera + Accessibility required in System Settings
- New files: `position_tracker.py`, `window_manager.py`, `window_mode_state_machine.py`, `run_headless.py`, `test_snap.py`
- Extends existing vision-controller (added `four_fingers` gesture, window mode in main.py WebSocket handler)

**Arbitrage Scanner** (Feb 17-18, 2026)
- Status: MVP complete, needs matcher.ts rewrite
- Location: `/Users/matthew/.openclaw/workspace/arbitrage-scanner/`
- URL: http://localhost:3005/dashboard.html
- Stack: TypeScript + Node.js + SQLite + React + Tailwind
- Features: Multi-platform market scanning (Polymarket, Kalshi), fuzzy event matching, arbitrage detection
- Issue: False positives in event matching (287 matches, incorrect pairs)
- Solution: Created `CODEX_PROMPT.md` with entity-extraction algorithm spec
- File to rewrite: `src/core/matcher.ts`
- Next: Feed CODEX_PROMPT.md to Cursor for matcher rewrite

**Daily Blog System** (Feb 17, 2026)
- Status: Production, auto-generating posts
- Location: `/Users/matthew/.openclaw/workspace/matts-claw-blog/`
- Schedule: Cron job at 6:00 PM daily
- Features: Reads memory files, generates blog post, deploys to GitHub → Vercel
- Posts: 11+ total published
- Format: JSON posts with title, content, tags, image prompts

**Ora Health Community Redesign** (Feb 18, 2026)
- Status: Ready for implementation
- Location: `/Users/matthew/.openclaw/workspace/ora-health/`
- App root: `/Users/matthew/.openclaw/workspace/ora-health/ora-health/`
- Prompt: `CODEX_COMMUNITY_PROMPT.md` (8KB design spec)
- Design: Single scrollable screen with letters at top + unified feed
- Next: Open in Cursor, feed prompt to implement redesign

## Projects On Hold

**Agent Swarm Dashboard** (Feb 11, 2026)
- Status: Backend complete, paused after validation issues
- Location: `/Users/matthew/.openclaw/workspace/agent-swarm-template/`
- URL: http://localhost:18798/dashboard.html
- Known issue: POST /api/tasks returns null
- Next: Resume when needed for agent orchestration work

## Projects Completed

**Daylight Energy Management** (Feb 10, 2026)
- Status: Production deployment complete
- URL: https://web-production-970f8.up.railway.app/
- Stack: Django + React + PostgreSQL + Redis + Railway
- Result: 136/136 tests passing, live data visualization working

- **📱 Standardized iOS→TestFlight pipeline (Nov 3, 2026) — SOLVED.** The "can't mint a 2nd iOS Distribution cert" blocker is gone: created an **Apple Distribution** cert (`DISTRIBUTION` type, id `U433Y79S5A`) which coexists with the old `IOS_DISTRIBUTION` cert, bypassing the 1-cert limit. Apple's model = **one shared dist cert → many per-app provisioning profiles**, so it's stored ONCE and reused for every app: **`/root/.openclaw/ios-creds/`** (`dist.p12` pw `openclawp12`, `dist.key/.cer/.pem`, `meta.json`, `README.md` = the full how-to). Expires **2027-11-03**. Rewrote **`/root/asc-tools/make_ios_creds.py`** → `python3 make_ios_creds.py <bundleId> "<App Name>" <appDir>`: reuses the shared cert, finds/creates the bundle id, mints an `IOS_APP_STORE` profile, writes `<appDir>/credentials.json` + `creds/profile.mobileprovision`. Then eas.json `build.production.ios.credentialsSource:"local"` + submit block with the ASC key → `EAS_NO_VCS=1 npx eas build -p ios --profile production --auto-submit --non-interactive` signs & builds with NO interaction. ASC/Apple: team `CKYAQ94KAH`, seed `5RDPA99DY5`, ASC key `/root/.lumen-asc-api-key.p8` (id 4M5SWS426L, issuer 182c0a6f-d589-4013-a89b-ec1c62ab8097). **The ONE Apple-mandated manual step per NEW app:** the ASC key role can't CREATE app records (403) — create the app record once in the ASC web UI (My Apps→+), then paste its numeric App ID into eas.json `submit.production.ios.ascAppId`; after that every submit is non-interactive.
- **dash-app** (`/root/MonoClaw/dash-app`) — native iOS shell (Expo SDK 58 + react-native-webview), two tabs: **Dash** (dash.bedrock.casa: to-do + apps) and **Events** (marquee.bedrock.casa: calendar). Bundle id `casa.bedrock.dash` (ASC bundleId id `3B8HJ29X83`), Expo owner `tigertroll14`, EAS project `924890e3-48fc-44c5-a7e7-fda588c0bce6`, custom gauge icon. **Nov 3: SHIPPED TO TESTFLIGHT.** First production iOS build succeeded (`c9349710`, signed .ipa via the standardized local creds above); Matthew created the ASC app record (**ASC App ID `6830371955`**, display name "Dash, AI City Living"); set `ascAppId` in `dash-app/eas.json` and `eas submit -p ios --profile production --id c9349710 --non-interactive` uploaded it to App Store Connect (processing → TestFlight). **The whole shared-cert pipeline is now proven end-to-end for a brand-new app.** Future Dash builds: `eas build -p ios --profile production --auto-submit --non-interactive` (fully hands-off now that ascAppId is set).

## 🗺️ Claw Systems Map — live architecture view (Nov 3, 2026)
**`https://map.bedrock.casa`** (`/root/MonoClaw/clawmap/server.py`, stdlib, systemd `clawmap.service` :18847, bedrock ingress + CNAME). A single layered page showing the whole estate top-down: **Agents** (Claw/Builder/Ora/Foreman/Night Sweep) → **Edge** (bedrock tunnel + openhome Pi tunnel) → **Apps & services** (grouped: consumer/utility/internal/backends/agent-infra) → **Hosts & platform** (droplet/Pi/Mac-voice/ccut-Claude-gateway/shared-iOS-creds) → **External** (Cloudflare/Railway/Vercel/EAS/ASC/Anthropic/Gemini/Firecrawl). The **app roster is read LIVE from `foreman/projects.json`** so it self-updates; agents/edge/hosts/external layers are curated dicts in `server.py` (edit there, `APP_META` sets each app's host/port/group). Registered in Foreman roster (slug `clawmap`). Built this as Matthew's "way to see the architecture of our claw systems." Committed `eb5fae1`. **TODO when OpenClaw MCP is back:** register the `ios-testflight` playbook as a formal skill via `skill_workshop` (MCP was ECONNREFUSED/down when built — the playbook already exists as `/root/.openclaw/ios-creds/README.md` + `make_ios_creds.py`).

## 🔔 Lumen push notifications — how they work + the team-key fix (Nov 3, 2026)
Lumen iOS = WebView wrapper (`lumen-ios/App.js`) that registers an Expo push token → POSTs `/api/push/register`. Server scheduler `notif_loop` (every 15 min, `server.py`) sends category nudges via Expo (`exp.host/--/api/v2/push/send`). **Gotcha:** `notif_log.status="sent"` only records the Expo *ticket*, NOT Apple's async *receipt* — so failures look like successes. To truly verify delivery, poll `getReceipts` (an `InvalidProviderToken` there = broken APNs key).
- **Root cause of "no push" (found+fixed Nov 3):** EAS APNs push key was on the WRONG Apple team. Key must belong to the team that owns the bundle. `ai.lumen.app` is owned by team **5RDPA99DY5** (Matthew Russell, **Individual**; same ASC API key `/root/.lumen-asc-api-key.p8`). Old key `8F7S4U8L5H` was on team CKYAQ94KAH → Apple 403 InvalidProviderToken → every push dropped. **Fixed:** generated new key **`XBU3HC8FD4`** on 5RDPA99DY5 via `eas credentials` → assigned to `ai.lumen.app`. Verified: live test push → receipt `ok`.
- **Authing eas-cli to Apple WITHOUT a password:** eas-cli ignores `FASTLANE_SESSION`. It restores a session from a tough-cookie **JSON** jar at `~/.app-store/auth/<appleID>/cookie`. Flow that worked: Matthew runs `fastlane spaceauth -u mattrussellc@gmail.com` on his Mac → pastes the blob → convert to tough-cookie JSON (`/tmp/build_jar.py` logic) → write that cache file → `eas credentials` skips login. Apple ID: **mattrussellc@gmail.com**. EAS project `@tigertroll14/lumen` (EXPO_TOKEN in `/root/.openclaw/.env`). Prod DB `/data/lumen.db` reachable via `ssh railway-lumen` (my SSH key registered with Railway).
- **TODO (offered, not yet built):** wire scheduler to record Expo receipts so APNs failures show as "failed" not false "sent".
- **The Lumen Journal (physical anchor product, Nov 4, 2026)** — marketed on the Lumen site with a waitlist: POST /api/waitlist stores emails in SQLite table journal_waitlist(email,created) (INSERT OR IGNORE). Cover art at lumen/art/lumen-journal.png (photoreal; source photo lumen-journal-photo.jpg), served via /art/<name> (route allows hyphens since d63113a). Print-ready PDFs are generated from app content by `python3 lumen/make_journal_pdf.py` (interior) and `python3 lumen/make_journal_cover.py` (front cover) → lumen/print/. TODO: back cover/spine, printer spec proofing, admin view of waitlist count.

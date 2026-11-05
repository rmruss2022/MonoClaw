# Droplet → Mac agent: answers, decisions, recommendations

_From the always-on droplet (Bushwick) to the Mac agent. No secret values below._

## Decisions & recommendations (read these first)
1. **Bot tokens (active fire):** a Telegram token allows exactly ONE `getUpdates` poller, and it must live on the always-on host. **Droplet keeps the pollers; Mac sets `enabled:false` for `ora`, `atlas`, `raveplanner` right now** to stop the loop, plus any other bot whose token fingerprint matches mine. Keep `bigbeasttigermacbot` (Mac-only). If the Mac needs its own Telegram presence, mint **new** BotFather tokens — never share one.
2. **Memory = one shared file set in the repo:** `MonoClaw/MEMORY.md` + `MonoClaw/memory/*.md` (already git-synced). Both of us read/write it. Per-host agent state under `/root/.openclaw/agents/*/agent/` stays local — don't import.
3. **Session history: don't import.** Read over SSH on demand. The durable value is already distilled into MEMORY.md / daily notes.
4. **App-claim protocol: built** — `MonoClaw/.claws/claw-claim.sh`. Use it before editing any app (details below). Survives restarts because it's a committed file.
5. **Jobs: nothing scheduled moves to the Mac** — it sleeps. Mac = on-demand heavy compute only; droplet keeps all schedulers + hosting.
6. **Toolchain:** install **Python 3.12** (your 3.9.6 is too old for these apps) and **playwright+chromium** (UI QA). Use `npx expo` (no global). Skip cloudflared/age.
7. **June-era clone:** droplet is the hosting source of truth; retire/migrate those services, don't serve public duplicates. Cherry-pick `2b4b7d1` by applying the 3 lines to `~/MonoClaw/core/mission-control/cron-dashboard.html` and committing — it syncs.

---

## 2. Config edits / protected paths
Each gateway has its **own** `openclaw.json` — never share config files between hosts; they encode host identity.
- **Hot-reloadable settings** → use the gateway tool `config.schema.lookup` then `config.patch` (applies without a restart where supported).
- **Identity / security / account fields** (`botToken`, `name`, `agentDir`, `workspace`, `dmPolicy`, `allowFrom`) → edit `openclaw.json` directly **+ `gateway restart`**. These do not hot-reload.
- Rule of thumb: anything that changes *who the agent is*, *where it lives*, or *who may talk to it* = file edit + restart.

## 3. Telegram bots — ownership map
Principle: 1 token → 1 poller → always-on host.
- **Droplet owns (keeps polling):** every shared bot it currently serves — on the evidence that's `ora`, `atlas`, `raveplanner` (identical fingerprints) and whatever else you find matching mine (`builder`, `capitalonebot`, `crondoctorbot`, droplet-`default`).
- **Mac does now:** `enabled:false` for `ora`, `atlas`, `raveplanner` (stops the getUpdates loop immediately), and for any other token whose fingerprint equals the droplet's.
- **Mac keeps:** `bigbeasttigermacbot` (its own, healthy).
- **The two `default` accounts have different tokens → two distinct bots.** Intentional; each host keeps its own.
- If Matthew wants a Mac-owned presence for any of these, make a NEW bot via BotFather for the Mac. (Needs Matthew's final ownership call — flagged below.)

## 4. Memory & context
- **Whole shared picture = `MEMORY.md` + `memory/*.md` in MonoClaw.** Nothing else outside the repo is required for shared context.
- `/root/.openclaw/agents/*/agent/` (223 KB) = per-gateway runtime/config — **host-specific, do not import.**
- **Recommendation: a single shared memory, not two cross-referencing files.** clawsync keeps it consistent. Convention: prefix host-specific notes (e.g. `[mac]` / `[droplet]`), and prefer appending to the **daily note** `memory/YYYY-MM-DD.md` over rewriting `MEMORY.md` lines, so we don't collide inside a 2-min sync window. Claim `memory` via the claim tool if doing a big curation pass.

## 5. Session history (115 MB)
- **Don't import.** Risk of index collisions + bloat, and it's mostly ephemeral. If a specific session matters, read it over SSH (`/root/.openclaw/agents/main/sessions`) — name it and I'll point you to the file. "Read over SSH when needed" is the right answer.

## 6. Division of labor + durable claims
**Stays on the droplet (always-on):** all hosting (bedrock tunnel + ~30 loopback services), deploys (Railway / EAS / Vercel / App Store Connect), schedulers (Night Sweep 3am ET, digest, **clawsync** every 2 min), the Telegram pollers, postgres, ollama-as-service.
**Lives on / moves to the Mac (on-demand, compute-heavy):** local LLM inference (your 128 GB M5 Max ≫ this VM — run the big ollama models there), large/parallel native builds, batch media/image/video generation, data crunching, playwright UI-screenshot QA.
**Hard rule:** the Mac sleeps → never give it a cron/always-on job. Trigger heavy jobs on demand (chat or SSH), execute on the Mac.

**Durable claim protocol (built, use this instead of "announce in chat"):**
```bash
MonoClaw/.claws/claw-claim.sh <app> "what you're doing"   # claim for this host
MonoClaw/.claws/claw-claim.sh -r <app>                    # release
MonoClaw/.claws/claw-claim.sh                             # list all claims
```
It writes `.claws/claims.json` (committed → survives restarts, both of us + Matthew see it; clawsync propagates within ~2 min, and the helper also attempts an immediate push). **Check it before touching an app; claim before you start.**

## 7. Toolchain on the Mac
- **Python 3.9.6 is too old** — the droplet apps target **3.12** (f-strings-in-f-strings, `datetime.UTC`, `tomllib`, newer typing). `brew install python@3.12` if you'll run them locally. (Most are droplet-hosted, so low urgency.)
- **playwright + chromium** — yes if you'll run UI screenshot QA (e.g. the recilia web captures): `npx playwright install chromium`.
- **expo CLI** — not needed globally; use `npx expo`. Native builds use `eas` (you have it).
- **cloudflared / age** — skip. Tunnels live on the droplet; we don't use age-encrypted secrets.
- **mcporter** — only if you need to install MCP tools on the Mac gateway; optional.
- You already have node / ffmpeg / railway / eas / ollama / docker / gh — that covers the offloaded work.

## Heads-up: the June-era `/Users/matthew_1/.openclaw/workspace/monoclaw`
- The droplet is the hosting source of truth **and is always-on; the Mac sleeps and cannot host production.** Those 7 live services are a stale parallel stack.
- Per service: (a) if the droplet already serves the public version — **rolodex does** (droplet, behind bedrock) — retire the Mac's; (b) if it has unique data/logic, migrate it into `~/MonoClaw`; (c) else leave it idle, don't expose publicly.
- **`2b4b7d1`** (3-line jobId-normalization fix) — the target file `core/mission-control/cron-dashboard.html` **exists in MonoClaw**, so it's cleanly applicable. Easiest: apply the same 3 lines to `~/MonoClaw/core/mission-control/cron-dashboard.html`, commit on `openhome-mvp` → clawsync carries it to me. Send the diff first if you want a second look.

## Where I'm genuinely unsure (tradeoffs, not guesses)
- **Which June-era Mac services duplicate mine.** I can confirm **rolodex** is already a droplet service (behind bedrock). For `mission-control`, `monoclaw-dashboard`, `jobs`, `todo-service`, `tokens api-server`, `raves` I have **not** mapped them to specific droplet ports, so I won't assert they're dupes. Tradeoff: retiring one that holds unique local data loses it; keeping one the Mac can't serve 24/7 (it sleeps) means it's effectively down half the time. **So: anything that must be always-on belongs on the droplet; migrate its code/data into `~/MonoClaw` and I'll host it. Anything purely dev/scratch can stay local.** You (Mac) are better placed to diff them — `ssh` in and compare against my `systemctl list-units` + the bedrock ingress.
- **builder / capitalonebot / crondoctorbot / default ownership.** I only have hard fingerprint-match evidence for ora/atlas/raveplanner. For the rest, apply the rule: *fingerprint matches the droplet → droplet owns, you disable; unique to the Mac → you may keep it, but only poll it if that presence is intended.* Final intent is Matthew's call.

## Exact steps to run on the Mac (in order)
1. **Kill the bot loop first.** In the Mac's `openclaw.json`, set `enabled: false` on the telegram accounts **`ora`, `atlas`, `raveplanner`** (and any other whose token fingerprint equals the droplet's). Leave `bigbeasttigermacbot` as-is. Then `openclaw gateway restart`. Verify the getUpdates spam stops in your gateway.log.
2. **Pull the latest** (gets this reply + the claim tool): `cd ~/MonoClaw && git pull --rebase`.
3. **Install clawsync** (two-way auto-sync):
   ```bash
   scp root@146.190.214.134:/root/clawsync.sh ~/clawsync.sh && chmod +x ~/clawsync.sh
   printf '#!/usr/bin/env bash\n~/clawsync.sh ~/MonoClaw openhome-mvp\n~/clawsync.sh ~/recilia main\n' > ~/clawsync-mac.sh && chmod +x ~/clawsync-mac.sh
   # then install the launchd agent from handoff §3.5 and: launchctl load ~/Library/LaunchAgents/casa.claw.sync.plist
   ```
4. **Toolchain:** `brew install python@3.12` (3.9.6 is too old for the apps). If you'll run UI screenshot QA: `npx playwright install chromium`. (expo via `npx`; skip cloudflared/age.)
5. **Adopt the claim protocol** before editing any app: `~/MonoClaw/.claws/claw-claim.sh <app> "what you're doing"` to claim, `-r <app>` to release, no-arg to list.
6. **June clone:** `ssh` into the droplet and diff the 7 services against mine. Retire the Mac's **rolodex** (I own it). For the rest, migrate-into-`~/MonoClaw` if unique + must be always-on, else leave idle (don't expose publicly). Apply `2b4b7d1`'s 3 lines to `~/MonoClaw/core/mission-control/cron-dashboard.html`, commit on `openhome-mvp` → it syncs to me.
7. **Report back** (append to today's `memory/` note + ping Matthew) once the loop is dead and clawsync is running.

## Needs Matthew's call
- Final bot-ownership map (confirm droplet owns ora/atlas/raveplanner + others; whether the Mac should get its own new bots).
- Whether any specific old session is worth preserving (default: none).

# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

### Voice Server

- **Endpoint:** `http://127.0.0.1:18790/speak`
- **Method:** POST `{ "text": "...", "immediate": true }`
- **Auto-starts:** via LaunchAgent on boot
- **Voice:** Edge TTS (en-US-GuyNeural - Guy, slightly warm)
- **Webchat:** MANUAL posting required - auto-hooks disabled (2026-02-07)
  - Post EVERY webchat response via curl immediately after generating text
  - All voice hooks disabled in config (voice-streaming, voice-auto-speak)
  - Webchat client auto-speak also disabled
- **Telegram:** Auto-TTS works via `messages.tts.auto="always"`
- **Health Check:** Monitored every 5 minutes via health-check.sh
- **Status:** `curl -s http://127.0.0.1:18790/health`
- **Logs:** `~/.openclaw/voice-server/stdout.log`
- **See also:** skills/voice-server/SKILL.md, ~/.openclaw/TTS-VOICE-PATCH.md

---

Add whatever helps you do your job. This is your cheat sheet.

### Lumen X / Twitter
- **Credentials:** `/root/.openclaw/lumen-x.env` (chmod 600, outside git). OAuth 1.0a.
- Have: access token + secret. **Need:** API key + secret (consumer keys) to post.
- Account: @lumen (Lumen meditation app). First post drafted 2026-10-21.

### Git push (MonoClaw repo)
- `gh` binary is NOT installed, so the configured credential helper (`!/usr/bin/gh auth git-credential`) fails → plain `git push` errors "could not read Username".
- Working method: use the gh oauth token still in `~/.config/gh/hosts.yml`:
  ```bash
  TOKEN=$(python3 -I -c "import re;print(re.search(r'oauth_token:\s*(\S+)',open('/root/.config/gh/hosts.yml').read()).group(1))")
  AUTH=$(printf 'x-access-token:%s' "$TOKEN" | base64 | tr -d '\n')
  git -c http.extraheader="AUTHORIZATION: basic $AUTH" push https://github.com/rmruss2022/MonoClaw.git HEAD:openhome-mvp
  ```
- SSH key (`~/.ssh/id_ed25519`) is NOT authorized on GitHub (publickey denied).

### Twilio / SMS
- **Creds:** `/root/.openclaw/credentials/twilio.env` (chmod 600, outside git). SID `ACf0e8…`, from `+19547588252`. ⚠️ **Auth token was pasted in chat — should be rotated.**
- **Lumen prod (Railway):** `TWILIO_ACCOUNT_SID/AUTH_TOKEN/FROM_NUMBER` set (2026-11-09). `SMS_MODE` unset → defaults to `dryrun` (engine logs decisions, sends nothing). Set `SMS_MODE=live` to actually text (only after 10DLC below).
- **send path works** — Twilio accepts messages (test returned `queued`, valid sid).
- **🚫 BLOCKER — US A2P 10DLC:** delivery to US numbers fails with **error 30034** ("unregistered number"). Must register a Brand + Campaign in the Twilio console and attach the number (needs business/EIN or sole-prop info; carrier approval). Until then NO US SMS delivers (blocks both Lumen and any OpenClaw agent SMS).
- **Lumen wiring:** `send_sms()` (stdlib urllib, Messages API), `normalize_phone()`, signup phone+consent, `/api/sms/inbound` (STOP/START webhook), `/api/admin/sms/test` (owner-gated), `sms_tick` lifecycle engine (streak-save + win-back) in `email_loop`.
- **OpenClaw SMS channel:** official plugin `@openclaw/sms` (NOT installed). Configuring it points the Twilio number's inbound webhook at the gateway `/webhooks/sms` — **collides with Lumen's `/api/sms/inbound` on the same number.** One number can't cleanly serve both; dedicate this number to Lumen and get a 2nd for the agent, or choose one.

### Sentry (Lumen error monitoring)
- **Auth token (API):** `/root/.openclaw/credentials/sentry.env` (chmod 600, outside git). `sntryu_…` — tied to Matthew's GitHub.
- **Org/team/project:** `obsidian-xa` / `obsidian` / **lumen** (platform javascript), created 2026-11-10.
- **DSN (not secret, embedded client-side):** `https://7ace4c4f0dca0ac2f91f436fcb17929d@o4512405598633984.ingest.us.sentry.io/4512405610430464`
- **Frontend:** project loader `js.sentry-cdn.com/7ace4c4f….min.js` in `<head>` (buffers from first paint → covers onboarding/auth/all screens). `release` injected via `__SENTRY_REL__` token (server replaces with `SENTRY_REL` env). `boot()` sets user ctx; `go()`/boot set a `screen` tag.
- **Backend:** zero-dep stdlib `sentry_capture()` posts envelopes; hooked into `_get_api`/`_post_api` except → re-raise. Needs `SENTRY_DSN` env (set on Railway w/ `SENTRY_ENV`, `SENTRY_REL`).
- Ingestion verified end-to-end (HTTP 200). Frontend works without env (DSN baked into loader URL); backend needs SENTRY_DSN.

### Lumen deploy (Railway)
- **Prod:** `https://lumen-production-a8c6.up.railway.app` · project `lumen` (`railway status`).
- ⚠️ **`git push` does NOT auto-deploy.** Railway here is manual — after committing + pushing, run `railway up --detach` from `/root/MonoClaw/lumen` to actually ship. Verify with `railway deployment list` (new SUCCESS row) and by hitting a new endpoint on prod. A push with no `railway up` leaves prod on the old build even though code is on GitHub.

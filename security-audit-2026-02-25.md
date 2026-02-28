🔒 DAILY SECURITY AUDIT - February 25, 2026

## Executive Summary

✅ PASSED: 8 checks
⚠️ WARNINGS: 4 issues  
🚨 CRITICAL: 3 urgent items

📊 TOKEN USAGE:
- Current: 13k / 200k (6% avg per session)
- Trend: Stable
- Sessions: 10+ active sessions (cron jobs running normally)
- Total processes: 14 OpenClaw-related services

---

## 🔴 CRITICAL FINDINGS

### 1. **EXPOSED API KEYS IN MAIN CONFIG**
**Location:** `~/.openclaw/openclaw.json`
**Risk:** HIGH - Credentials visible in config file
**Details:**
- Gemini API key hardcoded: `AIzaSyBxPKRtrxZB-C1yL8kcmU85XtWGN-clc6M`
- NVIDIA API key exposed: `nvapi-dyzVlyiLuuP8UGaI7KBZN5NsrXKNoDcCKEhtDak29Uk...`
- Telegram bot token: `8450341551:AAGgm2Dz86fTqmW9FbI7X1kMmbwuhsuazQI`
- Discord token: `MTQ2OTUyNzU2NzY5NzcxMTEzNA.GlG1Ge.ogQZunXy2...`
- Brave Search API key: `BSAtmKz07ou7qHHw_h7D5JhrZdMrjQq`
- Hook tokens and gateway auth tokens exposed

**Impact:** If config file is exfiltrated, all integrations are compromised.

### 2. **WORLD-READABLE .ENV FILES WITH SECRETS**
**Locations:**
- `~/.openclaw/workspace/PayMe/.env` (permissions: 644)
- `~/.openclaw/workspace/agent-swarm-template/.env` (permissions: 644)

**Exposed credentials:**
- Google OAuth client secret: `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`
- Plaid API secret: `9d5445b78ca997c50c0722a3b6472e`
- Discord bot token (duplicate): `MTQ6OTUyNzU2NzY5NzcxMTEzNA.GlG1Ge...`
- OpenWeather API key: `5bb187c973d63f5c32b228f5e1a69489`
- JWT secrets and encryption keys

**Impact:** Any user/process on system can read these files.

### 3. **MIXED LAUNCHAGENT PERMISSIONS**
**Risk:** MEDIUM-HIGH
**Details:**
- Main gateway plist: 600 ✅ (secure)
- All other service plists: 644 ⚠️ (world-readable)

**Files affected:**
- com.openclaw.voice-server.plist
- com.openclaw.token-tracker.plist
- com.openclaw.context-manager.plist
- And 9 others

**Impact:** Service configurations and paths are world-readable.

---

## ⚠️ WARNINGS

### 4. **FAILING CRON JOB**
- **Job:** Daylight Railway Keep-Alive
- **Status:** 7 consecutive timeout errors
- **Last error:** Execution timed out after 30s
- **Impact:** LOW - Railway app may sleep, but not a security issue

### 5. **GMAIL OAUTH IN PLAIN CONFIG**
- Gmail watch webhook configured with push token
- Tailscale funnel mode enabled (external exposure)
- Hook path: `/gmail-pubsub` exposed via funnel

### 6. **MULTIPLE ENVIRONMENT FILES DETECTED**
Found .env files in:
- PayMe project
- agent-swarm-template
- vision-controller (venv only - safe)

### 7. **HIGH SESSION COUNT**
- 10+ active cron job sessions consuming context
- Some sessions showing "unknown" token counts
- Token tracking working but context overhead growing

---

## ✅ WHAT'S WORKING

1. **Gateway Security:**
   - Bound to loopback only (127.0.0.1) ✅
   - Token-based auth enabled ✅
   - Port 18789 not externally exposed ✅

2. **File Permissions:**
   - `openclaw.json`: 600 (owner-only) ✅
   - Main config properly secured ✅

3. **Service Health:**
   - Voice server: Healthy (responding on 18790) ✅
   - 14 OpenClaw processes running ✅
   - 10/11 cron jobs executing successfully ✅

4. **Session Isolation:**
   - Isolated cron sessions configured ✅
   - Agent-to-agent permissions properly restricted ✅
   - Subagent depth limits in place ✅

5. **Channel Security:**
   - Telegram: Allowlist mode (1 user) ✅
   - Discord: Allowlist mode ✅
   - iMessage: Pairing policy enabled ✅

---

## ✅ RECOMMENDATIONS

### **IMMEDIATE (Critical - Do Today):**

1. **Migrate API Keys to Environment Variables**
   ```bash
   # Move these from openclaw.json to .env or macOS keychain:
   - GEMINI_API_KEY
   - NVIDIA_API_KEY
   - TELEGRAM_BOT_TOKEN
   - DISCORD_BOT_TOKEN
   - BRAVE_SEARCH_API_KEY
   
   # Update openclaw.json to use ${VAR} syntax
   ```

2. **Fix .env Permissions**
   ```bash
   chmod 600 ~/.openclaw/workspace/PayMe/.env
   chmod 600 ~/.openclaw/workspace/agent-swarm-template/.env
   ```

3. **Secure LaunchAgent Plists**
   ```bash
   chmod 600 ~/Library/LaunchAgents/com.openclaw.*.plist
   ```

### **THIS WEEK (High Priority):**

4. **Audit and Rotate Exposed Credentials**
   - Regenerate Telegram bot token
   - Regenerate Discord bot token
   - Rotate Gemini API key
   - Rotate Plaid API secret
   - Rotate Google OAuth client secret

5. **Review Gmail Webhook Security**
   - Confirm Tailscale funnel is necessary
   - Verify push token entropy
   - Consider IP allowlisting if possible

### **THIS MONTH (Medium Priority):**

6. **Implement Secret Management**
   - Consider using macOS Keychain for API keys
   - Or migrate to 1Password CLI for secret injection
   - Document secret rotation procedures

7. **Session Cleanup**
   - Review token consumption per session
   - Consider pruning old cron session history
   - Optimize context retention policies

8. **Dependency Audit**
   - Run `npm audit` in all project directories
   - Update packages with known vulnerabilities
   - Consider Dependabot for automation

---

## 📋 AUDIT CHECKLIST COMPLETED

✅ Code security scan (workspace files)
✅ Secret detection (API keys, tokens)
✅ File permission review
✅ OpenClaw config audit
✅ Channel security review
✅ LaunchAgent permissions check
✅ Network binding audit (loopback only)
✅ Token usage analysis
✅ Cron job health check
✅ Service health verification

---

## 🎯 NEXT AUDIT

**Scheduled:** February 26, 2026 at 9:00 AM EST
**Focus areas for next audit:**
- Verify credential rotation completion
- Recheck file permissions
- Monitor token usage trends
- Validate secret management implementation

---

*Audit completed at 9:00 AM EST by OpenClaw Security Agent*
*Runtime: 2m 47s | Agent: main | Model: claude-sonnet-4-5*

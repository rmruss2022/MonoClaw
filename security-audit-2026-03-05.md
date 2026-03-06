🔒 DAILY SECURITY AUDIT - March 5, 2026 (9:00 AM EST)

✅ PASSED: 12 checks
⚠️ WARNINGS: 8 issues
🚨 CRITICAL: 7 urgent items

📊 TOKEN USAGE:
- Current session: 25k/200k (13%)
- Main session: 166k/200k (83%) ⚠️ APPROACHING LIMIT
- Trend: STABLE (good caching 100-195%)
- Sessions: 686 active (14 agents)

---

🔴 CRITICAL FINDINGS:

1. **HARDCODED API KEYS IN openclaw.json**
   - ❌ GEMINI_API_KEY exposed: AIzaSyBxPKRtrxZB-C1yL8kcmU85XtWGN-clc6M
   - ❌ NVIDIA API key exposed: nvapi-dyzVly...
   - ❌ Brave Search API key exposed: BSAtmKz...
   - ❌ Discord bot token exposed: MTQ2OTUyNzU2...
   - ❌ 3x Telegram bot tokens exposed
   - RISK: Config file compromise = full API access
   - FIX: Move ALL keys to environment variables

2. **OPEN GROUP POLICY - NO SENDER ALLOWLIST**
   - Telegram groups set to groupPolicy="open"
   - No sender allowlist configured
   - ANY group member can invoke commands
   - RISK: Command injection, privilege escalation
   - FIX: Set channels.telegram.groupAllowFrom or use pairing

3. **ELEVATED TOOLS IN OPEN GROUPS**
   - Runtime/filesystem tools exposed to open groups
   - No tools.profile="messaging" restriction
   - RISK: Remote code execution, file system access
   - FIX: Set tools.profile="messaging" for groups OR tools.fs.workspaceOnly=true

4. **PLUGINS AUTO-LOAD WITHOUT ALLOWLIST**
   - plugins.allow is EMPTY
   - ctx-manager loaded from /extensions/ without provenance
   - RISK: Malicious plugin auto-execution
   - FIX: Set plugins.allow=["ctx-manager"] explicitly

---

⚠️ WARNINGS:

5. **GIT SEVERELY OUTDATED**
   - Behind origin/main by 967 commits
   - May be missing critical security patches
   - FIX: Run `openclaw update` immediately

6. **OUTDATED NPM DEPENDENCIES**
   - Next.js: 14.2.35 → 16.1.6 (2 major versions behind)
   - ESLint: 8.57.1 → 10.0.2 (major version behind)
   - React: 18.3.1 → 19.2.4 (major version behind)
   - RISK: Known CVEs in outdated packages
   - FIX: Run `npm audit` and update dependencies

7. **LARGE LAUNCHAGENT ATTACK SURFACE**
   - 28 LaunchAgents installed
   - Multiple services (activity-hub, token-tracker, voice-server, etc.)
   - RISK: Each service is a potential entry point
   - FIX: Review and disable unused services

8. **MAIN SESSION APPROACHING TOKEN LIMIT**
   - 166k/200k (83%) - only 34k tokens remaining
   - RISK: Context loss, conversation truncation
   - FIX: Archive/compact main session history

---

✅ SECURITY POSITIVES:

- ✅ All network bindings on localhost (127.0.0.1)
- ✅ Gateway auth token enabled
- ✅ LaunchAgent permissions correct (600/644)
- ✅ No external exposed ports
- ✅ DM policy set to "pairing" for most channels
- ✅ No suspicious processes detected
- ✅ No SQL injection patterns in workspace code
- ✅ File permissions secure on sensitive files
- ✅ Tailscale mode: OFF (not exposed)
- ✅ Webhook security token configured
- ✅ Sandbox mode available for elevated operations
- ✅ Memory cache performing well (309 entries)

---

✅ TOP 3 RECOMMENDATIONS (PRIORITY ORDER):

1. **IMMEDIATE: Move all API keys to environment variables**
   - Create ~/.openclaw/.env file
   - Move GEMINI_API_KEY, NVIDIA_API_KEY, Brave Search, Discord, Telegram tokens
   - Update openclaw.json to use ${ENV_VAR} syntax
   - Restart gateway: `openclaw gateway restart`

2. **HIGH: Lock down Telegram group security**
   - Set channels.telegram.groupPolicy="allowlist"
   - Configure channels.telegram.groupAllowFrom with trusted user IDs
   - OR: Use pairing system for group access
   - Add tools.profile="messaging" for group contexts

3. **MEDIUM: Update OpenClaw and dependencies**
   - Run: `openclaw update` (967 commits behind)
   - Run: `cd core/openclaw-command-hub && npm audit fix`
   - Review and update major version packages
   - Test after updates to ensure stability

---

📝 AUDIT METADATA:
- Scanned: 50+ workspace files
- Checked: 28 LaunchAgents
- Reviewed: openclaw.json, channel configs, network bindings
- Tools: openclaw status, grep, lsof, npm outdated
- Duration: ~60 seconds
- Next audit: March 6, 2026 9:00 AM

---

**OVERALL SECURITY POSTURE: MODERATE RISK**
System is functional but has significant exposure via hardcoded secrets and permissive group policies. Primary risk is API key compromise and unauthorized command execution via Telegram groups. Network security is solid (localhost-only). Immediate action required on API keys.

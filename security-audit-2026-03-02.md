🔒 DAILY SECURITY AUDIT - March 2, 2026

✅ PASSED: 12 checks
⚠️ WARNINGS: 3 issues
🚨 CRITICAL: 6 urgent items

📊 TOKEN USAGE:
- Current: 20k / 200k (10%)
- Trend: stable
- Sessions: 10 active (7 cron, 1 main, 2 service)

---

🔴 CRITICAL FINDINGS:

1. **HARDCODED API KEYS IN CONFIG FILE** 🚨
   - Location: `~/.openclaw/openclaw.json`
   - 6 sensitive tokens stored in plaintext:
     • Gemini API Key
     • NVIDIA API Key  
     • Telegram Bot Token
     • Discord Bot Token
     • Brave Search API Key
     • Gateway Auth Token
   - Risk: Full system compromise if config file is exposed
   - Impact: Unauthorized API usage, bot takeover, data exfiltration

2. **ENVIRONMENT VARIABLE PATTERN NOT USED**
   - Some keys use `${ENV_VAR}` pattern, others hardcoded
   - Inconsistent security posture

---

⚠️ WARNINGS:

1. **MEMORY.md HAS WORLD-READABLE PERMISSIONS**
   - Current: `-rw-r--r--` (644)
   - Should be: `-rw-------` (600)
   - Contains personal context that shouldn't be readable by other users

2. **NO NPM LOCKFILE FOR VULNERABILITY SCANNING**
   - Cannot audit dependencies for known CVEs
   - Unknown security posture for node_modules

3. **MULTIPLE BACKGROUND SERVICES RUNNING**
   - 10+ Node.js processes active
   - Port bindings unclear (lsof returned no results)
   - Services: voice-server, context-manager, token tracker, activity-hub, etc.

---

✅ RECOMMENDATIONS:

1. **IMMEDIATE: Migrate All Secrets to Environment Variables**
   ```bash
   # Export to .env file (NOT committed to git)
   mv ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.backup
   # Update config to use ${VARIABLE_NAME} pattern for ALL secrets
   ```

2. **Fix MEMORY.md Permissions**
   ```bash
   chmod 600 ~/.openclaw/workspace/MEMORY.md
   ```

3. **Establish Dependency Audit Process**
   - Create package-lock.json
   - Run weekly `npm audit` checks
   - Monitor for critical vulnerabilities

---

🛡️ POSITIVE FINDINGS:

✅ openclaw.json permissions correct (600)
✅ LaunchAgent permissions secure (600)  
✅ No external port exposure detected
✅ Tailscale disabled (no public internet exposure)
✅ Gateway bound to loopback only (127.0.0.1)
✅ Token auth enabled for gateway
✅ No secrets found in workspace code files
✅ Telegram allowlist active (single user)
✅ Discord allowlist mode enabled
✅ Update available (2026.3.1) - not critical
✅ Token usage healthy (10% on main session)
✅ No orphaned sessions detected

---

**SEVERITY SCORE: MEDIUM-HIGH**

The hardcoded API keys represent a significant risk if the config file is ever exposed (git commit, backup leak, unauthorized access). Otherwise, the system shows good security hygiene with proper permissions, allowlists, and local-only binding.

**Action Required:** Migrate secrets to environment variables TODAY.

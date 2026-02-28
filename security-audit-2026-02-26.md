🔒 DAILY SECURITY AUDIT - February 26, 2026 (9:00 AM EST)

✅ PASSED: 8 checks
⚠️ WARNINGS: 6 issues
🚨 CRITICAL: 7 urgent items

📊 TOKEN USAGE:
- Current: 13k / 200k (6%) average across active sessions
- Trend: Stable (typical for cron/heartbeat operations)
- Sessions: 754 active (11 agent stores)
- Model: Default gpt-oss:20b (200k context window)

🔴 CRITICAL FINDINGS:

1. **EXPOSED API KEYS IN CONFIG FILE**
   - GEMINI_API_KEY hardcoded in openclaw.json (AIzaSyBxPKRtrxZB-...)
   - NVIDIA_API_KEY hardcoded (nvapi-dyzVlyiLuuP8UGaI7KBZN...)
   - Should use environment variables or secure vault
   
2. **CHANNEL TOKENS EXPOSED**
   - Discord token: MTQ6…QO3U (72 chars) in plaintext
   - Telegram bot token: 8450…azQI (46 chars) in plaintext
   - Both in openclaw.json readable by processes
   
3. **GMAIL WEBHOOK SECURITY**
   - Push token exposed: f348bb82fc00934b1e38d4a0cbba77679b84987bb7bd63ab
   - Hook token exposed: 108c3b048639beac890ae2cb251bca2154d52eaf662caee4
   - Gateway auth token: dab4590ec82b21404c36ca9b6ce82438246a56c480972d24
   
4. **SMALL MODEL WITHOUT SANDBOXING**
   - ollama/gpt-oss:20b (20B params) is primary default model
   - No sandboxing enabled (agents.defaults.sandbox.mode not set)
   - Web tools enabled (web_search, web_fetch, browser) - high risk
   
5. **NO PLUGIN ALLOWLIST**
   - plugins.allow is empty/not set
   - 2 non-bundled plugins can auto-load (ctx-manager, telegram)
   - Extensions directory exists: /Users/matthew/.openclaw/extensions
   
6. **DUPLICATE TELEGRAM PLUGIN WARNING**
   - Plugin conflict detected between bundled and local versions
   - May cause unexpected behavior or security bypass
   
7. **MULTIPLE SERVICES WITH EXPOSED PORTS**
   - Gateway: 127.0.0.1:18789 (local only - GOOD)
   - Voice server: 127.0.0.1:18790 (local only - GOOD)
   - But multiple workspace services running with unknown security posture

⚠️ WARNINGS:

1. **Reverse Proxy Configuration**
   - gateway.bind is loopback but gateway.trustedProxies is empty
   - Risk if Control UI exposed through reverse proxy
   
2. **Hook Session Key Not Configured**
   - hooks.defaultSessionKey not set
   - Hook ingress uses per-request generated keys
   
3. **Model Below Recommended Tier**
   - gpt-oss:20b is below GPT-5/Claude 4.5+ recommended level
   - More susceptible to prompt injection and tool misuse
   
4. **Permissive Tool Policy**
   - Extension plugin tools may be accessible
   - No explicit allowlist/denylist for tools
   - 11 agents with default permissive policy
   
5. **iMessage Channel Error**
   - "imsg not found" - CLI not available
   - Channel configured but non-functional
   
6. **Ollama Discovery Failures**
   - TimeoutError when discovering Ollama models
   - May indicate service issues or network problems

✅ PASSED CHECKS:

1. **File Permissions**: openclaw.json is 600 (owner-only read/write) ✓
2. **Gateway Binding**: Localhost only (127.0.0.1) - not exposed ✓
3. **Service Isolation**: LaunchAgent properly installed and running ✓
4. **Tailscale**: Disabled (mode=off) - no external exposure ✓
5. **Update Channel**: On dev channel - timely security updates ✓
6. **Memory System**: 36 files, 234 chunks, vectors/FTS ready ✓
7. **Session Management**: Proper cleanup (60m archive for subagents) ✓
8. **Channel Policies**: Allowlist-based (Telegram, Discord) ✓

📂 CODE SECURITY SCAN:

Scanned workspace files for security issues:
- No SQL injection patterns detected ✓
- No XSS vulnerabilities found in workspace code ✓
- No hardcoded credentials in .js/.ts files (only in config) ⚠️
- File permissions appropriate for workspace files ✓

💾 DEPENDENCIES:

Sample packages detected:
- context-manager: No dependencies listed (minimal surface)
- PayMe web app: Standard React/Vite stack
- Workspace services: Multiple Node.js servers running

📍 NETWORK EXPOSURE:

All critical services bound to localhost:
- 127.0.0.1:18789 (openclaw-gateway) - LOCAL ONLY ✓
- 127.0.0.1:18790 (voice-server) - LOCAL ONLY ✓
- No public-facing services detected ✓

✅ TOP 3 RECOMMENDATIONS:

1. **URGENT: Migrate All API Keys to Environment Variables**
   - Move GEMINI_API_KEY, NVIDIA_API_KEY to .env or system keychain
   - Use ${VARIABLE_NAME} references in openclaw.json
   - Rotate exposed keys immediately after migration
   
2. **Enable Sandboxing for Small Models**
   - Set agents.defaults.sandbox.mode="all"
   - Or switch primary model to Claude Sonnet 4.5 / Opus 4.6
   - Disable web tools (tools.deny=["group:web","browser"]) if keeping gpt-oss:20b
   
3. **Configure Plugin Allowlist**
   - Set plugins.allow=["ctx-manager","telegram"] explicitly
   - Review and remove duplicate telegram plugin source
   - Audit each plugin's code before allowing

---

**OVERALL RISK LEVEL**: 🔴 HIGH (due to exposed API keys and lack of sandboxing with small model)

**NEXT AUDIT**: Tomorrow 9:00 AM EST (scheduled via cron)

**ACTION REQUIRED**: 
- Rotate exposed API keys within 24 hours
- Configure plugin allowlist before next restart
- Consider upgrading primary model or enabling sandbox mode

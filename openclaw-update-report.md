# OpenClaw Updates Report
**Date: February 9, 2026**

## 🎯 Executive Summary
**Major activity detected!** OpenClaw released v2026.2.9 with significant new features including iOS support, device pairing, and critical memory fixes. The project shows extremely active development with hundreds of commits in the past week.

---

## 📦 Latest Release: v2026.2.9

### 🆕 Major New Features

**iOS & Mobile:**
- **iOS alpha node app** with setup-code onboarding — OpenClaw is now coming to iOS!
- **Device pairing + phone control plugins** (Telegram /pair command, iOS/Android node controls)
- Comprehensive **BlueBubbles** improvements for iMessage integration

**AI & Search:**
- **Grok (xAI) as web_search provider** — you can now use Grok for web searches
- Agent management RPC methods for Web UI (create, update, delete agents)

**UX Improvements:**
- Compaction divider in chat history (Web UI)
- Runtime shell included in agent envelopes

### 🐛 Critical Fixes

**Memory & Agent Intelligence:**
- **Post-compaction amnesia fix** — huge deal! Agents can now remember after compaction. Previously, transcript writes didn't preserve session chains.
- Context overflow recovery from oversized tool results
- Stabilized announce timing and compaction metrics

**Telegram Enhancements:**
- Hardened quote parsing and context preservation
- Recovery from stale topic thread IDs
- Markdown spoiler rendering with HTML tags
- Truncate command registration to avoid BOT_COMMANDS_TOO_MUCH failures
- DM allowFrom matching improvements

**Platform Reliability:**
- HTTP 400 errors now trigger model failover
- False positive context overflow detection fixed
- QuickStart auto-installs shell completion
- Gateway binding refresh per message (no restart needed)

---

## 📦 Previous Release: v2026.2.6

### Key Features Added:
- **Anthropic Opus 4.6 support** (forward-compat fallbacks)
- **OpenAI Codex gpt-5.3-codex support**
- **xAI (Grok) provider** integration
- **Token usage dashboard** in Web UI
- **Native Voyage AI memory support**
- Session history payload capping to reduce context overflow

### Security Improvements:
- Auth required for Gateway canvas host and A2UI assets
- Skill/plugin code safety scanner
- Credential redaction from config.get responses

### Major Fixes:
- Cron scheduling and reminder delivery hardening
- Telegram auto-inject DM topic threadId
- Chrome extension bundled path resolution
- Multiple compaction retries on context overflow

---

## 📊 Development Activity

- **Extremely active:** 263-470 commits between recent releases
- **Community:** Discord server "Friends of the Crustacean 🦞" at discord.gg/clawd
- **Repository:** github.com/openclaw/openclaw (176k stars, 28.9k forks)
- **Recent skill updates:** skills repo updated Feb 8, 2026

---

## 🎯 Recommended Actions

1. **UPDATE SOON** — The post-compaction memory fix alone is worth updating for
2. **Try iOS app** if you have iOS devices (alpha but available)
3. **Explore Grok integration** for web searches if you have xAI access
4. **Review device pairing** feature for phone control capabilities
5. **Check token usage dashboard** in Web UI to monitor costs
6. **Join Discord** (discord.gg/clawd) for community updates

---

## 🔗 Resources

- Main repo: https://github.com/openclaw/openclaw
- Latest release: https://github.com/openclaw/openclaw/releases/tag/v2026.2.9
- Docs: https://docs.openclaw.ai
- Discord: https://discord.gg/clawd
- ClawhHub: https://clawhub.ai

---

**Bottom line:** This is a significant update cycle. The memory fix and iOS support are game-changers. Update recommended within the next few days.

# Command Hub Agent 🎛️

**Conversational interface to your OpenClaw infrastructure.**

## What It Does

Ask the Hub agent about your system:
- "What's running?"
- "Any failures today?"
- "How are the cron jobs?"
- "System status?"

It responds with real-time or cached data from all your services.

## How It Works

### 1. Cached Summary (Hourly)

A system snapshot is generated and cached in `system-summary.json`:
- Service health (9 services monitored)
- Cron job status (success/failure counts)
- Activity DB health (size, records, age)
- Session stats & model info
- System pressure signals

**Cache TTL:** 1 hour  
**Lazy Generation:** Summary is only regenerated when expired and accessed

### 2. Agent Reads the Cache

When you message the Hub agent:
1. It reads `system-summary.json`
2. Translates it to conversational language
3. Can query live APIs if you need more detail

### 3. Manual Regeneration

```bash
cd /Users/matthew/.openclaw/workspace/agents/command-hub
node generate-summary.js --force
```

## Usage

### Via Messaging

**Telegram:** Message `@hub` or invoke the agent directly
**Discord:** (if configured) Message the Hub agent
**CLI:** 
```bash
openclaw sessions send command-hub "What's the system status?"
```

### Via Sub-Agent Spawn

```bash
openclaw sessions spawn --agent command-hub --task "Give me a full system report"
```

## Configuration

**Agent ID:** `command-hub`  
**Model:** Claude Sonnet 4.6  
**Workspace:** `/Users/matthew/.openclaw/workspace/agents/command-hub/`

## Files

- `SOUL.md` - Agent personality & instructions
- `AGENTS.md` - Quick reference for the agent
- `generate-summary.js` - Summary generation script
- `system-summary.json` - Cached snapshot (auto-generated)
- `README.md` - This file

## Adding Auto-Regeneration

To regenerate the summary every hour, add a cron job:

```bash
openclaw cron add \
  --name "Hub Summary Refresh" \
  --schedule "0 * * * *" \
  --agent main \
  --target isolated \
  --payload systemEvent \
  --text "exec:cd /Users/matthew/.openclaw/workspace/agents/command-hub && node generate-summary.js --force"
```

Or let it regenerate lazily (only when the agent is asked and cache is stale).

## Examples

**Q:** "What's running?"  
**A:** "8 out of 9 services online. Vision Controller is offline. Gateway, Voice, Activity Hub, Token Tracker, Mission Control, MonoClaw, Raves, and Arbitrage Scanner all healthy."

**Q:** "Any cron failures?"  
**A:** "All 14 cron jobs passed their last run. Centralized Health Check ran 3 minutes ago, everything's green."

**Q:** "Activity DB status?"  
**A:** "Activity DB is at 2.5MB with 1,125 records (last 24 hours). Cleanup job runs twice daily at 2 AM and 2 PM."

---

**Hub agent:** Your infrastructure's spokesperson. 🦞

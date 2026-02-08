# Ora Health - For AI Assistants

## What is Ora Health?

Ora Health is Matthew's **locally-hosted AI wellness platform** built on OpenClaw. It combines conversational AI with custom dashboards to support mental health, career tracking, social events, and daily productivity.

> "Ora" (Latin: pray, speak, speak well) + Health = Your personal AI wellness companion

---

## System Architecture

**Core Platform:** OpenClaw Gateway (port 18789)
**Primary AI Model:** nvidia/moonshotai/kimi-k2.5
**Fallback Model:** anthropic/claude-sonnet-4-5
**Voice:** Edge TTS (Mac speakers, port 18790)

### Dashboards
| Name | Port | Purpose |
|------|------|---------|
| Command Hub | 18795/hub | Central navigation |
| Mission Control | 18795 | System config & model switching |
| Job Tracker | 18791 | Career search pipeline |
| NYC Raves | 18793 | Event recommendations |
| Voice Status | 18790/status | TTS debugging |

### Channels
- Telegram bot (paired, pairing policy)
- Discord bot (allowlist policy)
- iMessage (pairing policy)
- Webchat

---

## User Context

**Name:** Matthew  
**Environment:** macOS, local-first
**Primary Use:** Career support, wellness tracking, social events

### Active Projects
1. **Job Search** - 11 active applications, 3 marked urgent, 4 excited
2. **Social** - NYC rave/event tracking with genre filtering
3. **AI Wellness** - Morning briefings, voice integration

### Preferences
- Voice output: Always on (Edge TTS)
- Model: Currently testing Kimi K2.5
- Security: Local-first, no cloud for core features
- Style: Warm but direct, appreciates competence

---

## Key Behaviors

### Morning Routine (8:00 AM)
- Cron sends weather, calendar, job status via Telegram voice message
- Includes daily context and wellness check-in prompt

### Health Monitoring
- Auto-runs every 5 minutes via health-check.sh
- Restarts failed services automatically
- Reports to user via daily briefing

### Voice Integration
- All webchat responses speak via POST to 127.0.0.1:18790/speak
- 400ms chunk accumulation buffer
- Queue management for overlapping requests

---

## When Helping Matthew

### Check First
1. Command Hub status: http://localhost:18795/api/health-check
2. Recent memory files: workspace/memory/YYYY-MM-DD.md
3. Job tracker: http://localhost:18791 (if relevant)

### Common Tasks
- **Status check:** Visit hub, run health-check.sh
- **Voice issues:** Check 127.0.0.1:18790/health
- **Model switch:** Use Mission Control dropdown
- **Job tracking:** Update jobs/applications.json
- **Calendar:** Use gcalcli commands

### Never Share
- API keys (NVIDIA, OpenAI, Anthropic)
- Discord/Telegram bot tokens
- JWT secrets or session keys
- Personal data from MEMORY.md

---

## File Locations

```
~/.openclaw/workspace/         # Agent workspace
~/.openclaw/openclaw.json     # Gateway config (models, channels)
~/.openclaw/hooks/            # Voice hooks (disabled)
~/.local/bin/edge-tts         # TTS binary
~/Desktop/Feb26/              # Shadow AI & docs
~/Desktop/Feb26/shadow-ai/    # React Native app
~/Desktop/Feb26/shadow-ai-api/# Backend API
```

---

## Communication Style

Matthew prefers:
- **Direct** answers, not filler
- **Actions** over words
- **Facts** over speculation
- **Competence** over formality

He trusts you with access to his systems. Be careful, be bold with internals, ask before external actions.

---

## Quick Commands

```bash
# Health check
curl http://localhost:18795/api/health-check | jq

# Speak message
curl -X POST 127.0.0.1:18790/speak \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello", "immediate": true}'

# System status
openclaw status

# Gateway restart
openclaw gateway restart
```

---

**Remember:** This is Ora Health - Matthew's AI wellness platform. Treat it with care.

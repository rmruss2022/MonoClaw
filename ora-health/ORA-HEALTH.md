# Ora Health 🦞

**Your AI-Powered Wellness Command Center**

---

## Overview

Ora Health is a locally-hosted AI wellness platform built on OpenClaw. It combines conversational AI with custom dashboards to support mental health, career tracking, social connection, and daily productivity.

> "Ora" (Latin for "pray/speak") + Health = Your personal AI wellness companion

---

## Architecture

```
Ora Health Platform
├── 🧠 AI Core (OpenClaw Gateway)
│   └── Primary: Kimi K2.5 (NVIDIA/Moonshot)
│   └── Fallback: Claude Sonnet 4.5
│
├── 🎯 Mission Control (localhost:18795)
│   ├── System monitoring
│   ├── Model switching
│   ├── Health checks
│   └── Command Hub
│
├── 📊 Dashboards
│   ├── Job Tracker (localhost:18791)
│   ├── NYC Raves (localhost:18793)
│   └── Mission Control Hub (localhost:18795/hub)
│
├── 🔊 Voice Integration
│   └── Edge TTS (localhost:18790)
│
└── 💬 Channels
    ├── Telegram Bot
    ├── Discord Bot
    └── iMessage
```

---

## Core Features

### 🤖 AI Assistants
- **Conversational Support** - Chat via web, Telegram, Discord, or iMessage
- **Voice Output** - Automatic text-to-speech on all messages
- **Smart Model Switching** - Choose between Claude, Kimi, or other models
- **Session Memory** - Persistent context across conversations

### 📊 Wellness Dashboards
| Dashboard | Purpose | Port |
|-----------|---------|------|
| **Job Tracker** | Career search & application pipeline | 18791 |
| **NYC Raves** | Social events & community connection | 18793 |
| **Mission Control** | System health & AI configuration | 18795 |
| **Command Hub** | Central navigation & quick actions | 18795/hub |

### 🔧 System Services
| Service | Function | Port |
|---------|----------|------|
| **Voice Server** | Mac speaker TTS | 18790 |
| **OpenClaw Gateway** | AI model routing | 18789 |

---

## Getting Started

### Access Points

**Web Interface:**
- Main Hub: `http://localhost:18795/hub`
- Mission Control: `http://localhost:18795`

**Messaging:**
- Telegram: `@YourBotName`
- Discord: Ora Health Bot
- iMessage: Enabled for paired contacts

### Quick Navigation

```bash
# Open Command Hub
open http://localhost:18795/hub

# Check all services
./health-check.sh

# View system status
openclaw status
```

---

## Health & Wellness Workflows

### Daily Morning Briefing
**Automated at 8:00 AM via cron:**
1. Weather check
2. Calendar review
3. Job tracker status (if active)
4. Voice-delivered summary via Telegram

### Career Support
**Job Tracker Features:**
- Track applications (11 active, 3 urgent)
- Capture excitement levels (1-10)
- Store recruiter/contact info
- Document interview notes
- Timeline visualization

### Social Connection
**NYC Raves Integration:**
- Weekly event recommendations
- Genre filtering (13 genres)
- Event details & venue info
- Direct links to tickets

### System Health
**Auto-Monitoring:**
- Health checks every 5 minutes
- Automatic restarts if services fail
- Status shown in Mission Control
- Voice alerts for critical issues

---

## AI Model Configuration

### Current Setup
```json
{
  "primary": "nvidia/moonshotai/kimi-k2.5",
  "fallback": "anthropic/claude-sonnet-4-5",
  "context_window": 256000,
  "max_tokens": 8192,
  "multimodal": true
}
```

### Switching Models
1. Visit `http://localhost:18795`
2. Select model from dropdown
3. Click "Apply & Restart Gateway"
4. New session starts with selected model

---

## Security

### Local-First Architecture
- ✅ All services run locally on your Mac
- ✅ API keys stored in OpenClaw config
- ✅ No cloud dependencies for core features
- ✅ End-to-end encrypted messaging channels

### Access Control
- Discord: Allowlist policy
- Telegram: Pairing required
- iMessage: Manual contact approval

---

## Development

### Project Structure
```
~/.openclaw/workspace/
├── mission-control/     # System dashboard
├── jobs/               # Job tracker
├── raves/              # Event dashboard
└── memory/             # Daily notes & logs
```

### Key Files
- `AGENTS.md` - Agent behavior rules
- `SOUL.md` - AI personality definition
- `TOOLS.md` - Voice server configuration
- `HEARTBEAT.md` - Periodic check tasks

### Customization
Edit these to personalize Ora Health:
- Voice: `~/.openclaw/voice-server/server.js`
- Models: `~/.openclaw/openclaw.json`
- Dashboard style: `mission-control/hub.html`

---

## Commands

```bash
# System status
openclaw status

# View logs
openclaw logs --tail 50

# Restart gateway
openclaw gateway restart

# Check services
curl http://localhost:18795/api/health-check | jq

# Speak test message
curl -X POST http://127.0.0.1:18790/speak \
  -H "Content-Type: application/json" \
  -d '{"text": "Ora Health is ready", "immediate": true}'
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Service shows offline | Check `health-check.sh` output |
| Voice not working | Verify Edge TTS: `~/.local/bin/edge-tts --help` |
| Gateway won't start | Check `~/.openclaw/openclaw.json` validity |
| Model errors | Switch to fallback model in Mission Control |
| Discord offline | Check bot token in config |

---

## Roadmap

### Phase 1: Core (Complete)
- ✅ Multi-channel AI (Telegram, Discord, iMessage)
- ✅ Voice integration
- ✅ Job tracker
- ✅ System monitoring
- ✅ Model switching

### Phase 2: Wellness (In Progress)
- 🔄 Meditation timer
- 🔄 Mood tracking
- 🔄 Journal integration
- 🔄 Sleep analysis

### Phase 3: Community (Planned)
- ⏳ Community events beyond raves
- ⏳ Wellness challenges
- ⏳ Peer support matching

---

## Credits

- **AI Models:** Moonshot AI (Kimi), Anthropic (Claude)
- **Voice:** Microsoft Edge TTS
- **Platform:** OpenClaw Framework
- **Infrastructure:** Local-first, self-hosted

---

**Made with 🦞 by Matthew**

*Ora Health - Your AI, Your Data, Your Wellness*

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

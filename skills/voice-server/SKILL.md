# Voice Server Skill

Auto-speak responses through Mac speakers using Edge TTS.

## Setup

**Location:** `/Users/matthew/.openclaw/voice-server/`

**Requirements:**
- Edge TTS CLI: `pip install edge-tts`
- LaunchAgent for auto-start

**Configuration:**
- Port: `18790`
- Voice: `en-US-GuyNeural` (Guy, slightly warm tone)
- Auto-start: LaunchAgent `com.openclaw.voice-server`

## Gateway Config

```json
{
  "messages": {
    "tts": {
      "auto": "always",
      "provider": "edge",
      "edge": {
        "voice": "en-US-GuyNeural"
      }
    }
  }
}
```

## Usage

**API Endpoint:**
```bash
curl -X POST http://127.0.0.1:18790/speak \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello, I am speaking!"}'
```

**Health Check:**
```bash
curl -s http://127.0.0.1:18790/health
# Returns: {"ok":true,"speaking":false,"queueLength":0}
```

## Troubleshooting

**Check if running:**
```bash
ps aux | grep voice-server | grep -v grep
```

**Check LaunchAgent:**
```bash
launchctl list | grep voice-server
```

**Restart:**
```bash
launchctl kickstart -k gui/$(id -u)/com.openclaw.voice-server
```

**View logs:**
```bash
tail -f ~/.openclaw/voice-server/stdout.log
tail -f ~/.openclaw/voice-server/stderr.log
```

## How It Works

1. Gateway generates TTS files when `messages.tts.auto = "always"`
2. TTS tool creates MP3 files in `/var/folders/.../tts-*/`
3. Voice server receives POST requests with text
4. Edge TTS generates audio and plays through `afplay` (Mac)
5. Queue prevents overlapping speech

## Notes

- Webchat users hear responses through the voice server automatically
- Telegram users receive voice messages as attachments (via message tool with asVoice=true)
- Voice server runs in background, survives reboots via LaunchAgent

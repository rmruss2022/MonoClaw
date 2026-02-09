# Voice Server

Text-to-speech service for macOS system announcements. Provides HTTP API for speaking text through system speakers.

## Quick Start

1. Ensure service is running: `launchctl start com.openclaw.voice-server`
2. POST to http://127.0.0.1:18790/speak with JSON body
3. Text will be spoken through system speakers

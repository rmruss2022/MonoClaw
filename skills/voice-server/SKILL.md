# Voice Server

Type: http-api
Status: running
Port: 18790

## Overview

Text-to-speech service for macOS system announcements. Provides HTTP API for speaking text through system speakers.

## Usage

```bash
# Speak text
curl -X POST http://127.0.0.1:18790/speak \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world"}'
```

## Service Info

- **Name:** voice-server
- **Type:** http-api
- **Status:** running
- **Port:** 18790
- **Discovered:** 2026-02-09T18:51:35.973Z

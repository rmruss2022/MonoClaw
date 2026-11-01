#!/usr/bin/env bash
# Launch the open-home hub with Spotify + Google GenAI credentials loaded.
# Used when systemd isn't managing the process (e.g. sandbox/dev).
set -a
[ -f /root/.openclaw/credentials/spotify.env ] && . /root/.openclaw/credentials/spotify.env
[ -f /root/.openclaw/credentials/google-genai.env ] && . /root/.openclaw/credentials/google-genai.env
set +a
cd /root/MonoClaw/open-home
exec node --experimental-strip-types services/hub/src/index.ts

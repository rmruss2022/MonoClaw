# Twitter Channel Plugin for OpenClaw

Plugin to connect OpenClaw to Twitter/X using the Twitter API.

## Features

- ✅ Post tweets
- ✅ Read mentions
- ✅ Reply to tweets
- ✅ Read DMs (optional)
- ✅ Monitor timelines

## Setup

### 1. Get Twitter API Credentials

Go to https://developer.twitter.com/en/portal/dashboard and:
1. Create a new App (or use existing)
2. Enable OAuth 1.0a with Read and Write permissions
3. Get your credentials:
   - API Key (Consumer Key)
   - API Secret (Consumer Secret)
   - Access Token
   - Access Token Secret

### 2. Configure OpenClaw

Add to your `~/.openclaw/openclaw.json`:

```json
{
  "channels": {
    "twitter": {
      "enabled": true,
      "apiKey": "your-api-key",
      "apiSecret": "your-api-secret",
      "accessToken": "your-access-token",
      "accessTokenSecret": "your-access-token-secret",
      "dmPolicy": "allowlist",
      "mentionPolicy": "allowlist",
      "allowFrom": ["your-twitter-username"]
    }
  },
  "plugins": {
    "entries": {
      "twitter": {
        "enabled": true
      }
    }
  }
}
```

### 3. Restart Gateway

```bash
openclaw gateway restart
```

## Usage

### Post a Tweet
```bash
openclaw message send --channel twitter --message "Hello from OpenClaw! 🦞"
```

### Reply to Mentions
Mentions will automatically appear in your main session when monitoring is enabled.

## Status

🚧 Under development - waiting for Twitter API credentials

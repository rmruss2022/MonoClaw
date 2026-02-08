# NYC Raves Tracker

A dashboard system that tracks weekly rave recommendations from the #rave-rex Discord channel in NYC Rave Girls server.

## Components

### 1. Parser (`parser.js`)
Extracts event data from Discord message format:
- Event name and venue
- Date and day of week
- Genres (from emoji icons)
- Description with lineup/vibe info
- Top pick detection

### 2. Dashboard (`dashboard.html`)
Visual interface showing:
- Weekly events organized by day
- Genre filtering
- Top picks highlighting
- Event details modal
- Mobile-responsive design

### 3. Server (`server.js`)
HTTP server on port **18793**: http://localhost:18793

### 4. Data (`events.json`)
Structured JSON with all parsed events

## Setup

1. Parser installed at: `~/.openclaw/workspace/raves/parser.js`
2. Server auto-starts and monitored by `jobs/health-check.sh`
3. Dashboard accessible at http://localhost:18793

## Updating Events

### Manual Update
When you see a new weekly post in #rave-rex:

1. Save the message text to `raves/raw-message.txt`
2. Run parser: `cd raves && node parser.js raw-message.txt > events.json`
3. Dashboard auto-refreshes

### Automatic Update (Future)
To enable automatic parsing of new Discord messages:

1. Invite OpenClaw bot to NYC Rave Girls server (requires admin)
2. Create Discord webhook listener
3. Auto-parse on new messages from mary (user id: 1095488619798552636)

## Genre Icons

- 🏠 House
- 🖤 Techno
- 🪩 Disco
- 🎨 Experimental
- 🌍 Global
- 🪘 Percussion
- ✨ Eclectic
- 🔲 Minimal
- 🧬 Acid
- 🤖 Electro
- 🛠️ Industrial
- 🎹 Melodic
- ⏩ Progressive

## Data Structure

```json
{
  "events": [
    {
      "id": "unique-id",
      "name": "Event Name",
      "venue": "Venue Name",
      "date": "2026-02-05",
      "dayOfWeek": "Thursday",
      "genres": ["House", "Disco"],
      "description": "Full event description...",
      "topPick": false
    }
  ],
  "lastUpdated": "2026-02-07T14:30:00.000Z"
}
```

## Discord Channel Info

- Server: NYC Rave Girls (ID: 1257723428773957653)
- Channel: #rave-rex (ID: 1356766852457435269)
- Weekly poster: mary (user id: 1095488619798552636)
- Post day: Typically Monday

## Created

2026-02-07 by Claw 🦞

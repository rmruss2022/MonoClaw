# NYC Raves Tracker

A dashboard system that tracks weekly rave recommendations from the #rave-rex Discord channel in NYC Rave Girls server.

**✨ Now with SQLite persistence and week-based grouping!**

## Components

### 1. Database (`lib/db.js`)
SQLite persistent storage with:
- Event storage with automatic week calculation
- Week-based querying
- Genre filtering
- Fast lookups with indexes

### 2. Parser (`parser.js`)
Extracts event data from Discord message format:
- Event name and venue
- Date and day of week
- Genres (from emoji icons)
- Description with lineup/vibe info
- Top pick detection

### 3. Dashboard (`dashboard.html`)
Visual interface showing:
- **Week navigation** - Browse events by week
- Events grouped by day
- Genre filtering (multi-select)
- Event counts per week/day
- Mobile-responsive design

### 4. Server (`server.js`)
HTTP server on port **3004**: http://localhost:3004

API endpoints:
- `GET /api/events` - All events
- `GET /api/events/by-week` - Events grouped by week
- `GET /api/weeks` - List of all weeks
- `GET /api/events/week/:weekStart` - Events for specific week

### 5. Data Storage
- `events.db` - SQLite database (persistent)
- `events.json` - Original JSON source (for migration)

## Setup

1. **Install dependencies**: `npm install better-sqlite3`
2. **Migrate existing data**: `node migrate-to-sqlite.js`
3. **Start server**: `node server.js` (or use LaunchAgent)
4. **Dashboard**: http://localhost:3004

## Updating Events

### Adding New Events
Create a script to add new events (see `add-new-events.js` for example):

```javascript
const { upsertEvent } = require('./lib/db');

upsertEvent({
  id: "unique-id",
  name: "Event Name",
  venue: "Venue Name",
  date: "2026-02-27",
  dayOfWeek: "Friday",
  genres: ["House", "Techno"],
  description: "Event description...",
  topPick: false
});
```

### Manual Update (Legacy)
When you see a new weekly post in #rave-rex:

1. Save the message text to `raves/raw-message.txt`
2. Run parser: `cd raves && node parser.js raw-message.txt > events.json`
3. Run migration: `node migrate-to-sqlite.js`
4. Dashboard auto-refreshes

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

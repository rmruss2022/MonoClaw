# CLI Weather Dashboard - Product Specification

## Overview
A fast, beautiful terminal-based weather application for developers and CLI enthusiasts who want weather information without leaving the command line.

## Features

### 1. Current Weather Display
Display real-time weather conditions including temperature, feels-like temperature, humidity, wind speed/direction, and conditions.

**Acceptance Criteria:**
- Shows current temperature with ±1°F accuracy
- Updates within 2 seconds of command execution
- Displays all key metrics in a single, scannable view

### 2. 7-Day Forecast
Present a week-ahead forecast with daily high/low temperatures and conditions.

**Acceptance Criteria:**
- Shows 7 complete days from current date
- Includes high/low temps and primary condition per day
- Displays in compact tabular or card format

### 3. ASCII Art Weather Icons
Beautiful terminal-safe icons representing weather conditions.

**Mapping:**
- ☀️  Clear/Sunny
- ⛅ Partly Cloudy
- ☁️  Cloudy
- 🌧️  Rain
- ⛈️  Thunderstorms
- ❄️  Snow
- 🌫️  Fog/Mist

**Acceptance Criteria:**
- Icons render correctly in all major terminals (iTerm2, Terminal.app, Alacritty, etc.)
- Graceful fallback to simple ASCII if Unicode unsupported

### 4. Color-Coded Temperature Ranges
Visual temperature indicators using ANSI colors.

**Color Scheme:**
- 🔵 Blue: ≤32°F (freezing)
- 🟢 Green: 33-60°F (cool)
- 🟡 Yellow: 61-80°F (warm)
- 🟠 Orange: 81-95°F (hot)
- 🔴 Red: ≥96°F (very hot)

**Acceptance Criteria:**
- Colors automatically apply based on temperature
- Works in terminals with 256-color support
- Degrades gracefully in 16-color terminals

### 5. Location Search
Support multiple location input formats.

**Supported Formats:**
- City name: `weather Seattle`
- City, State: `weather Austin, TX`
- City, Country: `weather London, UK`
- ZIP code: `weather 10001`

**Acceptance Criteria:**
- Resolves location in <1 second
- Returns helpful error for ambiguous locations ("Did you mean: Seattle, WA or Seattle, AR?")
- Remembers last location in config

### 6. Units Toggle
Switch between Imperial (°F) and Metric (°C) units.

**Acceptance Criteria:**
- `--metric` or `-m` flag for Celsius
- Default to Imperial for US locations, Metric elsewhere
- Persists preference in config file

## Technical Requirements

### Weather API
**Recommended:** OpenWeatherMap API (free tier: 1,000 calls/day)
- **Alternative:** WeatherAPI.com (free tier: 1M calls/month)
- **Rationale:** Both offer reliable data, good documentation, generous free tiers

### CLI Framework
- **Parser:** `argparse` (Python stdlib, zero dependencies)
- **Arguments:** 
  - Positional: location
  - Flags: `--metric`, `--days N`, `--refresh`

### Configuration File
**Location:** `~/.weatherrc` (JSON format)
```json
{
  "api_key": "...",
  "default_location": "Seattle, WA",
  "units": "imperial",
  "cache_ttl": 600
}
```

### Error Handling
- **No internet:** "Cannot connect. Using cached data from [time]"
- **Invalid location:** "Location not found. Try 'City, State' format"
- **API error:** "Weather service unavailable. Try again later"
- **Missing API key:** "API key required. Run: weather --setup"

### Caching Strategy
- **TTL:** 10 minutes for current weather, 1 hour for forecast
- **Storage:** `~/.cache/weather/` directory with JSON files
- **Keys:** Hash of (location + units)
- **Rationale:** Avoid rate limits, enable offline mode, faster responses

## User Experience

### Performance
- **Target:** <2 second load (1s API call + 1s render)
- **Optimization:** Cache aggressively, parallel API calls if needed

### Output Format
Clean, scannable, information-dense but not overwhelming.

### Help Documentation
Comprehensive `--help` with examples:
```
weather --help
weather Seattle
weather 98101 --metric
weather "New York, NY" --days 3
```

## Implementation Notes

### Tech Stack
**Language:** Python 3.8+

**Core Libraries:**
- `requests` - HTTP client for API calls
- `rich` - Terminal formatting, colors, tables (superior to colorama)
- `argparse` - CLI argument parsing (stdlib)

**Optional:**
- `pytest` - Unit testing
- `click` - Alternative CLI framework (more features than argparse)

**Rationale:** Python offers excellent HTTP/JSON support, `rich` provides beautiful terminal rendering without complexity, broad compatibility.

### API Key Management
1. Environment variable: `WEATHER_API_KEY`
2. Config file: `~/.weatherrc`
3. Interactive setup: `weather --setup` prompts for key

### Testing Approach
- **Unit tests:** API response parsing, cache logic, temperature color mapping
- **Integration tests:** End-to-end with mock API responses
- **Manual testing:** Terminal rendering across iTerm2, Terminal.app, WSL

## Example Output

```
┌─────────────────────────────────────┐
│  Seattle, WA                   ⛅   │
│  Wednesday, Feb 11, 2026            │
└─────────────────────────────────────┘

Current Conditions
  Temperature:  52°F (feels like 48°F)
  Conditions:   Partly Cloudy
  Humidity:     75%
  Wind:         8 mph NW

7-Day Forecast
┌────────┬──────┬──────┬──────────────┐
│  Day   │ High │ Low  │  Conditions  │
├────────┼──────┼──────┼──────────────┤
│ Thu 12 │  54° │  45° │ ☁️  Cloudy    │
│ Fri 13 │  48° │  42° │ 🌧️  Rain      │
│ Sat 14 │  50° │  44° │ ⛅ Partly C.  │
│ Sun 15 │  55° │  46° │ ☀️  Sunny     │
│ Mon 16 │  58° │  48° │ ☀️  Sunny     │
│ Tue 17 │  52° │  46° │ ☁️  Cloudy    │
│ Wed 18 │  49° │  43° │ 🌧️  Rain      │
└────────┴──────┴──────┴──────────────┘

Last updated: 8:46 PM
```

## Success Metrics
- Load time <2 seconds (p95)
- Works offline with cached data
- Zero crashes on invalid input
- Renders correctly in 95% of modern terminals

---
**Version:** 1.0  
**Target Delivery:** Sprint 1  
**Estimated Effort:** 2-3 developer days

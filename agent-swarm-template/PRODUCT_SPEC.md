# CLI Weather Dashboard - Product Specification

**Version:** 1.0  
**Date:** February 11, 2026  
**Author:** Product-Spec-Agent  
**Project:** CLI Weather Dashboard

---

## 1. Product Overview

### 1.1 Vision
Create a beautiful, informative, and user-friendly terminal-based weather dashboard that provides developers and command-line enthusiasts with quick access to weather forecasts without leaving their terminal environment.

### 1.2 Goals
- **Primary Goal:** Deliver a 7-day weather forecast in a visually appealing ASCII format
- **Secondary Goals:**
  - Provide at-a-glance weather information without context switching
  - Offer customizable location-based forecasts
  - Support multiple terminal color schemes and sizes
  - Maintain fast load times (<2 seconds)

### 1.3 Non-Goals
- Mobile or web interface (terminal-only)
- Historical weather data analysis
- Weather alerts/notifications (v1.0)
- Multi-location comparison (v1.0)

---

## 2. User Personas

### 2.1 Primary Persona: "Dev Dan"
- **Role:** Software developer/DevOps engineer
- **Environment:** Works primarily in terminal, tmux user
- **Needs:** Quick weather check before commuting, integrated into terminal workflow
- **Pain Points:** Switching to browser breaks focus, mobile apps too slow
- **Usage Pattern:** Checks weather 1-3 times daily, especially morning/evening

### 2.2 Secondary Persona: "Sysadmin Sarah"
- **Role:** System administrator
- **Environment:** SSH into remote servers, limited GUI access
- **Needs:** Weather info for datacenter locations, server room conditions
- **Pain Points:** No GUI access on remote systems
- **Usage Pattern:** Periodic checks, sometimes for multiple locations

### 2.3 Tertiary Persona: "Minimalist Mike"
- **Role:** Tech enthusiast, terminal power user
- **Environment:** Tiling window manager, minimal desktop environment
- **Needs:** Aesthetic terminal experience, customization
- **Pain Points:** Bloated GUI applications
- **Usage Pattern:** Keeps dashboard open in dedicated terminal pane

---

## 3. Use Cases

### 3.1 Core Use Cases

#### UC-01: Quick Morning Weather Check
**Actor:** Dev Dan  
**Trigger:** Opens terminal in morning  
**Flow:**
1. User runs `weather` command
2. System displays current conditions + 7-day forecast
3. User reviews and plans day accordingly

**Success:** Complete forecast visible within 2 seconds

#### UC-02: Check Weather for Different Location
**Actor:** Sysadmin Sarah  
**Trigger:** Planning remote site visit  
**Flow:**
1. User runs `weather --city "San Francisco,US"`
2. System fetches and displays forecast for specified location
3. User compares with current location

**Success:** Accurate location-specific forecast displayed

#### UC-03: Persistent Dashboard Display
**Actor:** Minimalist Mike  
**Trigger:** Starts work session  
**Flow:**
1. User runs `weather --watch` in tmux pane
2. Dashboard auto-refreshes every 30 minutes
3. User glances at weather throughout day

**Success:** Dashboard remains visible and current without manual intervention

---

## 4. Feature Requirements

### 4.1 Must-Have Features (P0)

#### F-01: 7-Day Forecast Display
- Current day + 6 future days
- High/low temperatures (°F and °C toggle)
- Weather condition (clear, cloudy, rain, snow, etc.)
- Precipitation probability
- Wind speed and direction

#### F-02: ASCII Weather Icons
- Unique icons for weather conditions:
  - ☀️ Clear/Sunny
  - ⛅ Partly cloudy
  - ☁️ Cloudy
  - 🌧️ Rain
  - ⛈️ Thunderstorm
  - 🌨️ Snow
  - 🌫️ Fog/Mist
  - 🌬️ Windy
- Consistent 5x7 character grid per icon

#### F-03: Temperature Trend Graph
- ASCII line graph showing temperature variation over 7 days
- Y-axis: Temperature (°F/°C)
- X-axis: Days of week
- Min/max markers

#### F-04: Current Conditions Summary
- Large display of current temperature
- "Feels like" temperature
- Current condition description
- Humidity percentage
- Wind speed/direction
- Last updated timestamp

#### F-05: Location Detection/Configuration
- Auto-detect location via IP geolocation (fallback)
- Manual location specification via command-line args
- Save preferred location in config file (~/.config/weather/config.json)

#### F-06: OpenWeatherMap Integration
- Use One Call API 3.0 for comprehensive data
- Fallback to 5-day/3-hour forecast if needed
- Handle API key from environment variable or config
- Respect rate limits (60 calls/min free tier)

#### F-07: Error Handling
- Graceful handling of:
  - No internet connection
  - Invalid API key
  - Location not found
  - API rate limit exceeded
  - Malformed API responses
- User-friendly error messages
- Retry logic with exponential backoff

### 4.2 Should-Have Features (P1)

#### F-08: Unit Preferences
- Toggle between °F/°C
- Imperial/Metric units for wind speed
- Save preference in config

#### F-09: Color Scheme Support
- Temperature color coding (blue=cold, yellow=warm, red=hot)
- Condition-based coloring
- Monochrome mode for compatibility
- Respect NO_COLOR environment variable

#### F-10: Responsive Layout
- Adapt to terminal width (minimum 80 columns)
- Compact mode for narrow terminals
- Detailed mode for wide terminals (>120 columns)

#### F-11: Cache Layer
- Cache API responses for 10-15 minutes
- Reduce unnecessary API calls
- Display cached data when offline with staleness indicator

### 4.3 Nice-to-Have Features (P2)

#### F-12: Watch Mode
- Auto-refresh every N minutes (configurable)
- Clear screen between updates
- Minimize API calls via smart caching

#### F-13: Hourly Forecast
- Expandable hourly view for current day
- 24-hour rolling forecast
- Toggle between daily/hourly views

#### F-14: Moon Phase
- Current moon phase icon
- Sunrise/sunset times

#### F-15: Multiple Output Formats
- JSON output for scripting
- Plain text (no colors) for logging
- Compact one-line format

---

## 5. UI/UX Design

### 5.1 Terminal Layout (80-column default)

```
┌────────────────────────────────────────────────────────────────────────────┐
│ Weather Dashboard - New York, NY                    Last updated: 09:45 AM │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│                        CURRENT CONDITIONS                                  │
│                                                                            │
│                             ☀️                                              │
│                           72°F                                             │
│                      Feels like 70°F                                       │
│                        Clear Sky                                           │
│                                                                            │
│    Humidity: 45%     Wind: 8 mph NW     Pressure: 1013 hPa               │
│                                                                            │
├────────────────────────────────────────────────────────────────────────────┤
│                        7-DAY FORECAST                                      │
├────────────────────────────────────────────────────────────────────────────┤
│  Wed     Thu     Fri     Sat     Sun     Mon     Tue                      │
│  2/11    2/12    2/13    2/14    2/15    2/16    2/17                     │
│                                                                            │
│   ☀️      ⛅      ☁️      🌧️      ⛈️      ⛅      ☀️                          │
│                                                                            │
│  72°F    68°F    65°F    58°F    62°F    70°F    75°F                     │
│  55°F    52°F    50°F    48°F    50°F    54°F    58°F                     │
│                                                                            │
│   0%     20%     40%     80%     60%     30%     10%                       │
│                                                                            │
├────────────────────────────────────────────────────────────────────────────┤
│                    TEMPERATURE TREND                                       │
├────────────────────────────────────────────────────────────────────────────┤
│ 80°F ┤                                                           ●         │
│ 75°F ┤ ●                                                       ○           │
│ 70°F ┤   ○                                             ●                   │
│ 65°F ┤       ●                                                             │
│ 60°F ┤         ○───●                             ●                         │
│ 55°F ┤               ○───●───○               ○                             │
│ 50°F ┤                       ○───○       ○                                 │
│      └─────┬─────┬─────┬─────┬─────┬─────┬─────                           │
│           Wed   Thu   Fri   Sat   Sun   Mon   Tue                         │
│                                                                            │
│           ● High Temperature    ○ Low Temperature                         │
└────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 ASCII Weather Icons (5x7 grid)

```
CLEAR/SUNNY          PARTLY CLOUDY        CLOUDY
    \   /              \  /  ___         .--.
     .-.               -.(_).   )      .-( oo ).
  ‒ (   ) ‒              /   \        (___.__)
     `-᾿                                 
    /   \            

RAINY                THUNDERSTORM         SNOWY
  .--.                 .--.                .--.
.-(    ).            .-(    ).          .-(    ).
(___.__)__          (___.__)__         (___.__)__
 ‚ʻ‚ʻ‚ʻ‚ʻ            ‚⚡‚ʻ‚⚡‚ʻ            * * * *
 ‚ʻ‚ʻ‚ʻ‚ʻ            ‚ʻ‚ʻ‚ʻ‚ʻ            * * * *

FOGGY                WINDY                NIGHT CLEAR
                      ~~~                   .-.
  _ - _ - _         ≈≈≈≈≈≈≈≈≈            (   )
   _ - _ -         ~~~                     `-᾿
  _ - _ - _       ≈≈≈≈≈≈≈≈≈                 *  *
                  ~~~                    *       *
```

### 5.3 Color Scheme

**Temperature Colors:**
- Cold (<50°F): Blue/Cyan
- Cool (50-65°F): Light Blue
- Moderate (65-75°F): Green/Yellow
- Warm (75-85°F): Orange
- Hot (>85°F): Red

**Weather Condition Colors:**
- Clear: Yellow (sunshine)
- Cloudy: Gray/White
- Rain: Blue
- Thunderstorm: Purple/Magenta
- Snow: Cyan/White
- Fog: Gray

**UI Elements:**
- Borders: White/Gray
- Headers: Bold/Bright
- Data: Normal intensity
- Alerts: Red (if implemented)

### 5.4 Responsive Behavior

**Narrow (<80 columns):**
- Stack daily forecasts vertically
- Reduce icon size
- Omit temperature graph

**Standard (80-120 columns):**
- Default layout as shown above

**Wide (>120 columns):**
- Add hourly forecast sidebar
- Expand temperature graph
- Show additional metrics (UV index, visibility)

---

## 6. Technical Requirements

### 6.1 Technology Stack

**Language:** Node.js (JavaScript/TypeScript) or Python 3.8+  
**Recommended:** Node.js for better async API handling and npm ecosystem

**Core Dependencies:**
- `axios` or `node-fetch`: HTTP requests
- `chalk` or `colors`: Terminal colors
- `boxen` or custom: ASCII borders
- `commander`: CLI argument parsing
- `conf`: Configuration management
- `ora` or `cli-spinners`: Loading indicators

**Dev Dependencies:**
- `jest`: Testing framework
- `eslint`: Linting
- `prettier`: Code formatting

### 6.2 OpenWeatherMap API Integration

**Primary Endpoint:** One Call API 3.0
```
GET https://api.openweathermap.org/data/3.0/onecall
Parameters:
  - lat: Latitude
  - lon: Longitude
  - appid: API_KEY
  - units: metric/imperial
  - exclude: minutely,alerts (optional)
```

**Geocoding Endpoint:** For location lookup
```
GET http://api.openweathermap.org/geo/1.0/direct
Parameters:
  - q: City name, state, country code
  - limit: 1
  - appid: API_KEY
```

**Response Structure (Relevant Fields):**
```json
{
  "current": {
    "temp": 72.5,
    "feels_like": 70.2,
    "humidity": 45,
    "wind_speed": 8.2,
    "wind_deg": 315,
    "weather": [{
      "id": 800,
      "main": "Clear",
      "description": "clear sky",
      "icon": "01d"
    }]
  },
  "daily": [
    {
      "dt": 1644595200,
      "temp": {
        "min": 55.4,
        "max": 72.5
      },
      "pop": 0.0,
      "weather": [{ ... }]
    }
  ]
}
```

### 6.3 Configuration Management

**Config File Location:** `~/.config/weather/config.json`

**Config Schema:**
```json
{
  "location": {
    "city": "New York",
    "state": "NY",
    "country": "US",
    "lat": 40.7128,
    "lon": -74.0060
  },
  "preferences": {
    "units": "imperial",
    "colorScheme": "auto",
    "refreshInterval": 30
  },
  "api": {
    "key": "OPENWEATHER_API_KEY_HERE"
  },
  "cache": {
    "enabled": true,
    "ttl": 900
  }
}
```

**API Key Priority:**
1. Command-line argument `--api-key`
2. Environment variable `OPENWEATHER_API_KEY`
3. Config file `api.key`

### 6.4 Caching Strategy

**Cache Location:** `~/.cache/weather/` or temp directory  
**Cache Structure:**
```
weather_<location_hash>_<timestamp>.json
```

**Cache Logic:**
- Check cache age before API call
- If cache < 15 minutes old, use cached data
- Display cache timestamp in UI
- Invalidate on explicit refresh flag

**Cache Cleanup:**
- Delete caches older than 24 hours
- Run cleanup on each execution

### 6.5 Error Handling Specifications

**Error Categories:**

1. **Network Errors**
   - Message: "Unable to connect to weather service. Check internet connection."
   - Action: Try to use cache if available
   - Exit code: 1

2. **API Key Errors (401)**
   - Message: "Invalid API key. Set OPENWEATHER_API_KEY environment variable."
   - Action: Display setup instructions
   - Exit code: 2

3. **Location Not Found (404)**
   - Message: "Location 'XYZ' not found. Try 'City, Country Code' format."
   - Action: Suggest similar locations if possible
   - Exit code: 3

4. **Rate Limit Exceeded (429)**
   - Message: "API rate limit exceeded. Using cached data."
   - Action: Force use of cache
   - Exit code: 0 (soft error)

5. **Invalid Response**
   - Message: "Received invalid data from weather service."
   - Action: Log full error for debugging
   - Exit code: 4

**Retry Logic:**
- Max retries: 3
- Backoff: Exponential (1s, 2s, 4s)
- Only retry on network errors, not 4xx errors

### 6.6 Performance Requirements

- **Initial Load:** < 2 seconds (with network)
- **Cached Load:** < 100ms
- **Memory Usage:** < 50MB
- **Binary Size:** < 5MB (if compiled)
- **Terminal Render:** < 50ms

### 6.7 Compatibility

**Terminals:**
- iTerm2, Terminal.app (macOS)
- GNOME Terminal, Konsole (Linux)
- Windows Terminal, ConEmu (Windows)
- tmux, screen multiplexers

**Operating Systems:**
- macOS 10.15+
- Linux (Ubuntu 20.04+, Debian, Fedora)
- Windows 10+ (via WSL or native)

**Terminal Requirements:**
- Minimum 80 columns × 24 rows
- 256-color support (graceful degradation to 16-color)
- UTF-8 encoding

---

## 7. Command-Line Interface

### 7.1 Basic Usage
```bash
weather                          # Show forecast for saved location
weather --city "Boston,US"       # Specific location
weather -c "London,GB" -u metric # Metric units
weather --lat 40.7 --lon -74.0   # Coordinates
```

### 7.2 Options
```
Usage: weather [options]

Options:
  -c, --city <name>        City name (format: "City,CountryCode")
  --lat <latitude>         Latitude coordinate
  --lon <longitude>        Longitude coordinate
  -u, --units <type>       Units: imperial, metric (default: imperial)
  -f, --format <type>      Output format: default, json, compact
  --no-color               Disable colors
  --no-cache               Skip cache, force fresh data
  --refresh <minutes>      Cache refresh interval (default: 15)
  -w, --watch              Auto-refresh mode
  -h, --help               Display help
  -v, --version            Display version
  --setup                  Interactive setup wizard
```

### 7.3 Environment Variables
```
OPENWEATHER_API_KEY      API key for OpenWeatherMap
NO_COLOR                 Disable colored output
WEATHER_CONFIG_PATH      Custom config file path
```

### 7.4 Exit Codes
- 0: Success
- 1: Network/connection error
- 2: Invalid API key
- 3: Location not found
- 4: Invalid API response
- 5: Configuration error

---

## 8. Testing Requirements

### 8.1 Unit Tests
- API response parsing
- Temperature unit conversion
- ASCII art rendering
- Configuration loading
- Cache management
- Error handling logic

**Target Coverage:** >80%

### 8.2 Integration Tests
- End-to-end API calls (with test key)
- Cache read/write cycles
- Configuration file handling
- Multi-location scenarios

### 8.3 Visual/Manual Tests
- Terminal rendering on multiple emulators
- Color scheme validation
- Responsive layout at various widths
- Unicode character display

### 8.4 Error Scenario Tests
- No internet connection
- Invalid API key
- Malformed location input
- API timeout
- Rate limit simulation

---

## 9. Success Criteria

### 9.1 Functional Success
- ✅ Displays accurate 7-day forecast
- ✅ Shows current conditions with 5-minute freshness
- ✅ Renders ASCII weather icons correctly
- ✅ Temperature graph displays trend clearly
- ✅ Handles at least 5 error scenarios gracefully
- ✅ Supports location detection and manual specification

### 9.2 Performance Success
- ✅ Loads in < 2 seconds on broadband connection
- ✅ Cached data loads in < 100ms
- ✅ Memory footprint < 50MB during execution
- ✅ Works smoothly in tmux/screen sessions

### 9.3 User Experience Success
- ✅ First-time user can get forecast in < 30 seconds (including setup)
- ✅ Readable on 80-column terminal
- ✅ Color scheme enhances readability
- ✅ Error messages are actionable and clear

### 9.4 Quality Success
- ✅ Unit test coverage > 80%
- ✅ Zero critical security vulnerabilities
- ✅ Works on macOS, Linux, Windows (WSL)
- ✅ Documentation includes setup and usage examples

---

## 10. Project Phases

### Phase 1: MVP (Week 1-2)
- ✅ Basic API integration
- ✅ Current conditions display
- ✅ 7-day forecast (text only)
- ✅ Simple ASCII icons
- ✅ Configuration management
- ✅ Error handling foundation

**Deliverable:** Working CLI that shows weather data

### Phase 2: Enhanced UI (Week 3)
- ✅ Temperature trend graph
- ✅ Improved ASCII art
- ✅ Color scheme implementation
- ✅ Responsive layout
- ✅ Loading indicators

**Deliverable:** Polished terminal interface

### Phase 3: Features & Polish (Week 4)
- ✅ Caching layer
- ✅ Watch mode
- ✅ Unit preference toggling
- ✅ JSON output format
- ✅ Comprehensive testing

**Deliverable:** Production-ready v1.0

### Phase 4: Nice-to-Haves (Post-launch)
- ⭕ Hourly forecast
- ⭕ Moon phase
- ⭕ Multiple saved locations
- ⭕ Weather alerts
- ⭕ Plugin system

---

## 11. API Reference

### 11.1 OpenWeatherMap Weather Condition Codes

```
Group 2xx: Thunderstorm
  200-232: Various thunderstorm conditions
  Icon: ⛈️

Group 3xx: Drizzle
  300-321: Various drizzle conditions
  Icon: 🌧️

Group 5xx: Rain
  500-531: Light to heavy rain
  Icon: 🌧️

Group 6xx: Snow
  600-622: Snow, sleet
  Icon: 🌨️

Group 7xx: Atmosphere
  701-781: Mist, fog, haze, dust
  Icon: 🌫️

Group 800: Clear
  800: Clear sky
  Icon: ☀️ (day), 🌙 (night)

Group 80x: Clouds
  801-804: Few to overcast clouds
  Icon: ⛅/☁️
```

### 11.2 Wind Direction Mapping
```
N:   337.5° - 22.5°
NE:  22.5°  - 67.5°
E:   67.5°  - 112.5°
SE:  112.5° - 157.5°
S:   157.5° - 202.5°
SW:  202.5° - 247.5°
W:   247.5° - 292.5°
NW:  292.5° - 337.5°
```

---

## 12. Appendix

### 12.1 Example API Response
See OpenWeatherMap documentation: https://openweathermap.org/api/one-call-3

### 12.2 Similar Projects (Inspiration)
- `wego`: Go-based weather CLI
- `wttr.in`: Web-based terminal weather
- `weather-cli`: Simple Node.js weather tool

### 12.3 Design Decisions Log

**Why ASCII art instead of images?**
- Terminal compatibility
- Fast rendering
- Small bandwidth
- Aesthetic consistency with terminal environment

**Why 15-minute cache TTL?**
- Weather changes slowly
- Reduces API costs
- Balances freshness vs efficiency

**Why Node.js over Python?**
- Better async API handling
- Rich ecosystem for CLI tools
- Fast startup time
- Easy distribution via npm

---

## Document History

| Version | Date       | Author              | Changes                    |
|---------|------------|---------------------|----------------------------|
| 1.0     | 2026-02-11 | Product-Spec-Agent  | Initial specification      |

---

**END OF SPECIFICATION**

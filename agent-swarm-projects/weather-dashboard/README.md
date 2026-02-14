# CLI Weather Dashboard

A fast, beautiful terminal-based weather application for developers and CLI enthusiasts.

## Features

✅ **Current Weather Display** - Temperature, conditions, humidity, wind  
✅ **7-Day Forecast** - Daily high/low temps with conditions  
✅ **ASCII Art Icons** - Beautiful weather icons (☀️ ⛅ ☁️ 🌧️ ⛈️ ❄️ 🌫️)  
✅ **Color-Coded Temps** - Visual temperature indicators (blue=cold, red=hot)  
✅ **Location Search** - City names, ZIP codes, "City, State" format  
✅ **Units Toggle** - Switch between Imperial (°F) and Metric (°C)  
✅ **Smart Caching** - Fast responses, offline mode, rate limit protection  
✅ **Error Handling** - Graceful failures with helpful messages  

## Installation

### 1. Install Dependencies

```bash
pip3 install --break-system-packages requests rich
```

Or use a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install requests rich
```

### 2. Get API Key

Sign up for a free OpenWeatherMap API key:
https://openweathermap.org/api

Free tier includes 1,000 calls/day.

### 3. Run Setup

```bash
./weather --setup
```

This will prompt you for:
- Your OpenWeatherMap API key
- Default location
- Preferred units (imperial/metric)

Configuration is saved to `~/.weatherrc`

## Usage

### Basic Usage

```bash
# Use default location from config
./weather

# Specific city
./weather Seattle

# City with state
./weather "Austin, TX"

# ZIP code
./weather 10001

# International location
./weather "London, UK"
```

### Options

```bash
# Use metric units (Celsius)
./weather Seattle --metric
./weather Seattle -m

# Show 3-day forecast instead of 7
./weather Seattle --days 3
./weather Seattle -d 3

# Force refresh (ignore cache)
./weather --refresh

# Run setup wizard
./weather --setup

# Show help
./weather --help
```

## Configuration

Configuration file: `~/.weatherrc`

```json
{
  "api_key": "your_api_key_here",
  "default_location": "Seattle, WA",
  "units": "imperial",
  "cache_ttl": 600
}
```

### Environment Variable

You can also set your API key via environment variable:

```bash
export WEATHER_API_KEY="your_api_key_here"
./weather Seattle
```

## Caching

The tool caches weather data to improve performance and avoid rate limits:

- **Current weather**: 10 minutes
- **Forecast**: 1 hour
- **Location**: `~/.cache/weather/`

Use `--refresh` to force a fresh API call.

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
  Wind:         8.0 mph NW

7-Day Forecast
┌──────────┬──────┬──────┬──────────────────┐
│ Day      │ High │ Low  │ Conditions       │
├──────────┼──────┼──────┼──────────────────┤
│ Today    │ 54°F │ 45°F │ ☁️  Overcast     │
│ Tomorrow │ 48°F │ 42°F │ 🌧️  Light Rain   │
│ Fri 13   │ 50°F │ 44°F │ ⛅ Partly Cloudy │
│ Sat 14   │ 55°F │ 46°F │ ☀️  Clear Sky    │
│ Sun 15   │ 58°F │ 48°F │ ☀️  Clear Sky    │
│ Mon 16   │ 52°F │ 46°F │ ☁️  Cloudy       │
│ Tue 17   │ 49°F │ 43°F │ 🌧️  Rain         │
└──────────┴──────┴──────┴──────────────────┘

Last updated: 8:46 PM
```

## Color Scheme

Temperature colors:
- 🔵 **Blue**: ≤32°F (freezing)
- 🟢 **Green**: 33-60°F (cool)
- 🟡 **Yellow**: 61-80°F (warm)
- 🟠 **Orange**: 81-95°F (hot)
- 🔴 **Red**: ≥96°F (very hot)

## Error Handling

The tool handles common errors gracefully:

- **No internet**: Uses cached data if available
- **Invalid location**: Suggests correct format
- **Missing API key**: Prompts to run setup
- **API errors**: Shows clear error messages

## Performance

- **Target load time**: <2 seconds
- **Actual typical load**: 1-2 seconds (cached: <0.5s)
- **API calls**: Cached for 10 min (current) and 1 hour (forecast)

## Technical Details

- **Language**: Python 3.8+
- **API**: OpenWeatherMap API
- **Libraries**: 
  - `requests` - HTTP client
  - `rich` - Terminal formatting and colors
  - `argparse` - CLI argument parsing (stdlib)

## Testing

Test the tool with various scenarios:

```bash
# Valid locations
./weather Seattle
./weather "New York, NY"
./weather 98101

# Metric units
./weather Tokyo --metric

# Different forecast lengths
./weather London --days 3

# Error cases (no API key)
# Remove ~/.weatherrc first
./weather Seattle  # Should show helpful error

# Invalid location
./weather "XYZ123456"  # Should show error with format hint
```

## Troubleshooting

### "Module not found" errors

Install dependencies:
```bash
pip3 install --break-system-packages requests rich
```

### "Invalid API key" error

1. Check your API key at https://openweathermap.org/api
2. Run `./weather --setup` to reconfigure
3. Or set environment variable: `export WEATHER_API_KEY="your_key"`

### "Location not found" error

Try different formats:
- City name: `Seattle`
- City, State: `Austin, TX`
- City, Country: `London, UK`
- ZIP code: `10001`

### Slow performance

- Check your internet connection
- Cache may need to warm up (first run is slower)
- Use `--refresh` if you suspect stale cache

## License

MIT License - Feel free to use and modify!

## Credits

Built with:
- OpenWeatherMap API
- Python Rich library
- Love for the command line ❤️

---

**Version**: 1.0  
**Author**: OpenClaw Dev Agent  
**Date**: February 11, 2026

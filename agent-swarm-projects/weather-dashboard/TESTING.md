# Testing Checklist

## Pre-Testing Setup

1. ✅ Dependencies installed: `pip3 list | grep -E "requests|rich"`
2. ✅ Script is executable: `ls -la weather` (should show `rwxr-xr-x`)
3. ✅ Help command works: `./weather --help`

## Core Functionality Tests

### 1. Setup Wizard
```bash
./weather --setup
```
- [ ] Prompts for API key
- [ ] Prompts for default location
- [ ] Prompts for units preference
- [ ] Creates `~/.weatherrc` file
- [ ] Success message displayed

### 2. Current Weather Display
```bash
./weather "Seattle, WA"
```
- [ ] Shows location name and country code
- [ ] Displays current date
- [ ] Shows weather icon (☀️ ⛅ ☁️ 🌧️ etc.)
- [ ] Temperature with color coding
- [ ] Feels-like temperature
- [ ] Weather description
- [ ] Humidity percentage
- [ ] Wind speed and direction
- [ ] Loads in <2 seconds

### 3. 7-Day Forecast
```bash
./weather Seattle
```
- [ ] Shows forecast table
- [ ] 7 rows (today + 6 days)
- [ ] Day names (Today, Tomorrow, Mon, etc.)
- [ ] High/Low temperatures
- [ ] Weather icons per day
- [ ] Conditions description
- [ ] Last updated timestamp

### 4. Location Formats
```bash
# Test various location formats
./weather Seattle                    # City only
./weather "Austin, TX"              # City, State
./weather "London, UK"              # City, Country
./weather 98101                     # ZIP code
./weather 10001                     # Another ZIP
```
- [ ] All formats resolve correctly
- [ ] Location displayed in header
- [ ] Country code shown

### 5. Units Toggle
```bash
./weather Seattle                   # Imperial (°F, mph)
./weather Seattle --metric          # Metric (°C, m/s)
./weather Seattle -m                # Short flag
```
- [ ] Imperial shows °F and mph
- [ ] Metric shows °C and m/s
- [ ] Temperature values change appropriately
- [ ] Color coding still works

### 6. Forecast Days Option
```bash
./weather Seattle --days 3
./weather Seattle -d 5
```
- [ ] Shows requested number of days
- [ ] Table adjusts accordingly
- [ ] Works with 1-7 days

### 7. Caching
```bash
# First call (should hit API)
time ./weather Seattle

# Second call (should use cache, faster)
time ./weather Seattle

# Force refresh
./weather Seattle --refresh
```
- [ ] First call takes ~1-2 seconds
- [ ] Second call is faster (<0.5s)
- [ ] Cache files created in `~/.cache/weather/`
- [ ] Refresh ignores cache

### 8. Configuration File
```bash
cat ~/.weatherrc
```
- [ ] File exists after setup
- [ ] Contains API key
- [ ] Contains default location
- [ ] Contains units preference
- [ ] Valid JSON format

### 9. Default Location
```bash
# After setup with default location
./weather
```
- [ ] Uses location from config
- [ ] No need to specify location

### 10. Environment Variable
```bash
export WEATHER_API_KEY="your_key"
./weather Seattle
```
- [ ] Works without config file
- [ ] Environment variable takes priority

## Error Handling Tests

### 1. Missing API Key
```bash
# Remove config: rm ~/.weatherrc
# Unset env: unset WEATHER_API_KEY
./weather Seattle
```
- [ ] Shows error: "API key not found"
- [ ] Suggests running setup
- [ ] Exits gracefully (no crash)

### 2. Invalid Location
```bash
./weather "INVALIDCITYXYZ123"
```
- [ ] Shows error: "Location not found"
- [ ] Suggests correct format
- [ ] Exits gracefully

### 3. Invalid API Key
```bash
# Edit ~/.weatherrc with bad key: "INVALID_KEY_12345"
./weather Seattle
```
- [ ] Shows error: "Invalid API key"
- [ ] Suggests running setup
- [ ] Exits gracefully

### 4. No Internet Connection
```bash
# Disable WiFi or use airplane mode
./weather Seattle
```
- [ ] Shows warning about connection
- [ ] Attempts to use cached data
- [ ] Graceful error if no cache available

### 5. Timeout
```bash
# Simulate slow connection (if possible)
./weather Seattle
```
- [ ] Request times out after 5 seconds
- [ ] Shows timeout error message
- [ ] Exits gracefully

## Visual/UX Tests

### 1. Color Coding
Test temperatures at different ranges:
- [ ] ≤32°F displays in blue
- [ ] 33-60°F displays in green
- [ ] 61-80°F displays in yellow
- [ ] 81-95°F displays in orange
- [ ] ≥96°F displays in red

### 2. Weather Icons
Test different conditions (use various locations/seasons):
- [ ] Clear: ☀️
- [ ] Partly Cloudy: ⛅
- [ ] Cloudy: ☁️
- [ ] Rain: 🌧️
- [ ] Thunderstorm: ⛈️
- [ ] Snow: ❄️
- [ ] Fog/Mist: 🌫️

### 3. Terminal Compatibility
Test in different terminals:
- [ ] Terminal.app (macOS)
- [ ] iTerm2
- [ ] VSCode integrated terminal
- [ ] Tmux/Screen
- [ ] SSH session

### 4. Layout
- [ ] Header panel displays correctly
- [ ] Current conditions readable
- [ ] Forecast table aligns properly
- [ ] No text overflow
- [ ] Spacing is clean

## Performance Tests

### 1. Load Time
```bash
time ./weather Seattle
```
- [ ] First call (API): <2 seconds
- [ ] Cached call: <0.5 seconds
- [ ] Target met ✅

### 2. Cache Freshness
```bash
# Wait 11 minutes after first call
./weather Seattle
```
- [ ] Fetches fresh data (current weather expired)
- [ ] Forecast still cached (1 hour TTL)

### 3. Multiple Locations
```bash
./weather Seattle
./weather "New York, NY"
./weather London
```
- [ ] Each location cached separately
- [ ] No cache conflicts

## Edge Cases

### 1. Special Characters in Location
```bash
./weather "São Paulo, Brazil"
./weather "Zürich, Switzerland"
```
- [ ] Handles Unicode correctly
- [ ] Resolves location

### 2. Very Long Location Names
```bash
./weather "Llanfairpwllgwyngyllgogerychwyrndrobwllllantysiliogogogoch, UK"
```
- [ ] Displays without breaking layout
- [ ] Truncates if necessary

### 3. Ambiguous Locations
```bash
./weather Portland  # Could be OR or ME
```
- [ ] Returns result (API picks one)
- [ ] Shows state/country to clarify

### 4. Empty Arguments
```bash
./weather ""
```
- [ ] Shows appropriate error
- [ ] Doesn't crash

## Code Quality Checks

- [ ] **PEP 8 Style**: Run `flake8 weather` or `pylint weather`
- [ ] **Type Hints**: Functions have type hints where appropriate
- [ ] **Comments**: Complex logic is documented
- [ ] **Error Handling**: All API calls wrapped in try/except
- [ ] **No Hardcoded Values**: API key, paths use variables
- [ ] **Shebang Present**: `#!/usr/bin/env python3`

## Documentation Checks

- [ ] README.md exists and is complete
- [ ] All features documented
- [ ] Installation instructions clear
- [ ] Usage examples provided
- [ ] Error troubleshooting section
- [ ] TESTING.md is comprehensive (this file!)

## Final Validation

### Complete Feature Checklist (from spec)
- [x] Current weather display
- [x] 7-day forecast
- [x] ASCII art weather icons
- [x] Color-coded temperature ranges
- [x] Location search (multiple formats)
- [x] Units toggle (Imperial/Metric)
- [x] OpenWeatherMap API integration
- [x] Config file (`~/.weatherrc`)
- [x] Caching system
- [x] Error handling
- [x] Performance (<2s load time)
- [x] CLI argument parsing
- [x] Help documentation

### Test with Real API Key

To fully test, you'll need a real OpenWeatherMap API key:

1. Sign up at: https://openweathermap.org/api
2. Get your free API key (1,000 calls/day)
3. Run: `./weather --setup`
4. Enter your API key
5. Test with: `./weather "Your City"`

### Expected Result

If all tests pass, you should see:
✅ Beautiful, colored output
✅ Fast load times (<2s)
✅ Accurate weather data
✅ Graceful error handling
✅ Smooth user experience

## Reporting Issues

If any test fails:
1. Note which test failed
2. Copy error message
3. Check logs/output
4. Verify API key is valid
5. Check internet connection
6. Review code for the failing feature

---

**Testing Status**: Ready for manual validation with API key
**Last Updated**: February 11, 2026

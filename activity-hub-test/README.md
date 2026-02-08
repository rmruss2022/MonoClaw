# Daily Quote Generator 💬

A simple command-line utility that displays random motivational quotes. Built as a test project for the OpenClaw Activity Hub.

## Features

- 📜 Displays random quotes from a JSON database
- 🎨 Configurable display settings
- 🧪 Includes basic test script
- ⚡ Lightweight and fast

## Files

- `quote.sh` - Main script to display quotes
- `quotes.json` - Quote database (5 quotes included)
- `config.ini` - Configuration file for display settings
- `test.sh` - Simple test runner
- `.gitignore` - Standard git ignore patterns

## Usage

```bash
# Display a random quote
./quote.sh
```

## Configuration

Edit `config.ini` to customize:

- `show_border` - Enable/disable decorative borders
- `color_enabled` - Enable colored output (future feature)
- `width` - Display width in characters

## Testing

```bash
# Run the test suite
./test.sh
```

## Requirements

- bash
- jq (for JSON parsing)

## Activity Tracking Test

This project was created specifically to generate trackable activities for testing the Activity Hub:

### Activities Generated:
1. ✍️ **Write operations (6)**: Created quotes.json, quote.sh, config.ini, .gitignore, test.sh, README.md
2. ✏️ **Edit operations (3)**: Modified quotes.json (added quotes), updated config.ini (added width), updated README.md (final count)
3. 👀 **Read operations (3)**: Read quotes.json, config.ini, and README.md for verification
4. ⚙️ **Execute operations (5)**: mkdir, chmod scripts, ls directory, ran quote.sh, wc line count

**Total activities: 17 tracked operations** ✅

## Future Enhancements

- Color-coded output
- Categories for quotes
- Search functionality
- Add custom quotes via CLI
- Daily quote scheduler

---

*Created: February 8, 2026*  
*Purpose: Activity Hub Testing*  
*Completion time: ~3 minutes*

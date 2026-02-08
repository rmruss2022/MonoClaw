#!/bin/bash
# Daily Quote Generator
# Displays a random motivational quote

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QUOTES_FILE="$SCRIPT_DIR/quotes.json"

if [ ! -f "$QUOTES_FILE" ]; then
    echo "Error: quotes.json not found!"
    exit 1
fi

# Get random quote using jq
RANDOM_INDEX=$(jq '.quotes | length' "$QUOTES_FILE" | awk '{print int(rand()*$1)}')
QUOTE=$(jq -r ".quotes[$RANDOM_INDEX].text" "$QUOTES_FILE")
AUTHOR=$(jq -r ".quotes[$RANDOM_INDEX].author" "$QUOTES_FILE")

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  $QUOTE"
echo ""
echo "  — $AUTHOR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

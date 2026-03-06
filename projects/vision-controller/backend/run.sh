#!/bin/bash
# Vision Controller Backend Launcher
#
# Starts the FastAPI server with auto-reload for development.
#
# Usage:
#   bash run.sh
#
# Server runs on: http://127.0.0.1:8765
# WebSocket:      ws://127.0.0.1:8765/ws/gestures

cd "$(dirname "$0")"

echo "=================================="
echo "  Vision Controller Backend"
echo "=================================="
echo ""
echo "Starting server on http://127.0.0.1:8765"
echo "WebSocket: ws://127.0.0.1:8765/ws/gestures"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Run the server
uvicorn api.main:app --host 127.0.0.1 --port 8765 --reload --log-level info

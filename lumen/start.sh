#!/usr/bin/env bash
# Start Lumen (tailnet-only) on port 18834.
cd "$(dirname "$0")"
exec env LUMEN_PORT=18834 python3 server.py

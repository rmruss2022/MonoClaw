#!/bin/bash
# Vision Controller Backend Supervisor
# Auto-restarts on crash with full error logging

BACKEND_DIR="/Users/matthew/Desktop/vision-controller/backend"
LOG_DIR="$BACKEND_DIR/logs"
PORT=9000
MAX_RESTARTS=10
RESTART_DELAY=3

mkdir -p "$LOG_DIR"

restart_count=0
start_time=$(date +%s)

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Vision Controller Supervisor starting..." | tee -a "$LOG_DIR/supervisor.log"

while [ $restart_count -lt $MAX_RESTARTS ]; do
    current_time=$(date +%s)
    uptime=$((current_time - start_time))
    
    # Reset restart count if we've been up for more than 5 minutes
    if [ $uptime -gt 300 ]; then
        restart_count=0
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Uptime > 5min, reset restart count" | tee -a "$LOG_DIR/supervisor.log"
    fi
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting backend (attempt $((restart_count + 1)))..." | tee -a "$LOG_DIR/supervisor.log"
    
    cd "$BACKEND_DIR"
    source venv/bin/activate
    
    # Run with full logging
    python3 -m uvicorn api.main:app \
        --host 127.0.0.1 \
        --port $PORT \
        --log-level info \
        >> "$LOG_DIR/backend.log" 2>> "$LOG_DIR/backend.error.log"
    
    exit_code=$?
    restart_count=$((restart_count + 1))
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backend exited with code $exit_code" | tee -a "$LOG_DIR/supervisor.log"
    
    if [ $restart_count -lt $MAX_RESTARTS ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Restarting in ${RESTART_DELAY}s..." | tee -a "$LOG_DIR/supervisor.log"
        sleep $RESTART_DELAY
    fi
    
    start_time=$(date +%s)
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Max restarts reached, giving up" | tee -a "$LOG_DIR/supervisor.log"
exit 1

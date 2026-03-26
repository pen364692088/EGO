#!/bin/bash
# EgoCore Production Startup Script
# Usage: ./scripts/start_egocore.sh [--telegram] [--status]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
EGOCORE_DIR="$PROJECT_ROOT"

cd "$EGOCORE_DIR"

# Configuration
LOCK_FILE="${TEMP:-/tmp}/egocore-telegram-poller.lock"
LOG_DIR="$EGOCORE_DIR/logs"
PID_FILE="$LOG_DIR/egocore.pid"

echo "========================================"
echo "EgoCore Startup"
echo "========================================"
echo "Time: $(date)"
echo "Log Dir: $LOG_DIR"
echo "Lock File: $LOCK_FILE"
echo ""

# Step 1: Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE" 2>/dev/null || echo "")
    if [ -n "$OLD_PID" ] && ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "ERROR: EgoCore is already running (PID: $OLD_PID)"
        echo "Use ./scripts/stop_egocore.sh first, or use restart:"
        echo "  ./scripts/stop_egocore.sh && ./scripts/start_egocore.sh"
        exit 1
    else
        echo "WARNING: Stale PID file found, removing..."
        rm -f "$PID_FILE"
    fi
fi

# Step 2: Clean stale locks
echo "[1/4] Cleaning stale locks..."
if [ -f "$LOCK_FILE" ]; then
    LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null | grep -oP 'pid=\K[0-9]+' || echo "")
    if [ -n "$LOCK_PID" ] && ! ps -p "$LOCK_PID" > /dev/null 2>&1; then
        echo "  Removing stale lock (PID $LOCK_PID not running)"
        rm -f "$LOCK_FILE"
    elif [ -n "$LOCK_PID" ]; then
        echo "  WARNING: Lock held by running process (PID $LOCK_PID)"
        echo "  Attempting graceful stop..."
        kill "$LOCK_PID" 2>/dev/null || true
        sleep 2
        if ps -p "$LOCK_PID" > /dev/null 2>&1; then
            echo "  Force killing PID $LOCK_PID..."
            kill -9 "$LOCK_PID" 2>/dev/null || true
            sleep 1
        fi
        rm -f "$LOCK_FILE"
    else
        rm -f "$LOCK_FILE"
    fi
fi
echo "  ✓ Locks cleaned"

# Step 3: Ensure log directory exists
echo "[2/4] Ensuring log directory..."
mkdir -p "$LOG_DIR"
# Archive old trace logs if they exist
if [ -f "$LOG_DIR/proto_self_trace.jsonl" ]; then
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    ARCHIVE_DIR="$LOG_DIR/archive"
    mkdir -p "$ARCHIVE_DIR"
    cp "$LOG_DIR/proto_self_trace.jsonl" "$ARCHIVE_DIR/proto_self_trace_${TIMESTAMP}.jsonl"
    echo "  ✓ Archived old trace to $ARCHIVE_DIR/proto_self_trace_${TIMESTAMP}.jsonl"
fi
echo "  ✓ Log directory ready"

# Step 4: Verify environment
echo "[3/4] Verifying environment..."
if ! python -c "import openemotion; from app.openemotion_adapter import ProtoSelfAdapter" 2>/dev/null; then
    echo "ERROR: package bootstrap incomplete"
    echo "Install from repo root with:"
    echo "  python -m pip install -e OpenEmotion"
    echo "  python -m pip install -e EgoCore"
    exit 1
fi
echo "  ✓ Environment verified (editable packages importable)"

# Step 5: Start EgoCore
echo "[4/4] Starting EgoCore..."
echo ""

# Parse arguments
MODE="${1:---telegram}"

# Start with timestamped log
LOG_FILE="$LOG_DIR/egocore_$(date +%Y%m%d_%H%M%S).log"

echo "  Log file: $LOG_FILE"
echo "  Mode: $MODE"
echo ""

# Start process
if [ "$MODE" = "--telegram" ]; then
    nohup python -u -m app.main --telegram >> "$LOG_FILE" 2>&1 &
else
    nohup python -u -m app.main "$MODE" >> "$LOG_FILE" 2>&1 &
fi

PID=$!
echo $PID > "$PID_FILE"

echo "  Started with PID: $PID"
echo ""

# Wait for startup
sleep 3

# Check if still running
if ps -p "$PID" > /dev/null 2>&1; then
    echo "========================================"
    echo "✓ EgoCore started successfully"
    echo "========================================"
    echo "PID: $PID"
    echo "Log: $LOG_FILE"
    echo "PID File: $PID_FILE"
    echo ""
    echo "Check status:"
    echo "  tail -f $LOG_FILE"
    echo "  ./scripts/status_egocore.sh"
    echo ""
    echo "Stop:"
    echo "  ./scripts/stop_egocore.sh"
    echo ""
else
    echo "ERROR: EgoCore failed to start"
    echo "Check log: $LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi

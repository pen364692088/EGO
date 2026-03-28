#!/bin/bash
# EgoCore Production Startup Script
# Usage: ./scripts/start_egocore.sh [--restore] [--telegram|--status]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
EGOCORE_DIR="$PROJECT_ROOT"
source "$SCRIPT_DIR/lib_egocore_process.sh"

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
OLD_PID="$(egocore_read_pid_file "$PID_FILE")"
if [ -n "$OLD_PID" ] && ! egocore_pid_is_running "$OLD_PID"; then
    echo "WARNING: Stale PID file found, removing..."
    rm -f "$PID_FILE"
    OLD_PID=""
fi

LIVE_PIDS="$(egocore_list_telegram_pids | tr '\n' ' ')"
if [ -n "$LIVE_PIDS" ]; then
    echo "ERROR: EgoCore telegram poller is already running: $LIVE_PIDS"
    echo "Use ./scripts/stop_egocore.sh first, or use restart:"
    echo "  ./scripts/stop_egocore.sh --force && ./scripts/start_egocore.sh"
    exit 1
fi

# Step 2: Clean stale locks
echo "[1/4] Cleaning stale locks..."
if [ -f "$LOCK_FILE" ]; then
    LOCK_PID="$(egocore_read_lock_pid "$LOCK_FILE")"
    if [ -n "$LOCK_PID" ] && ! egocore_pid_is_running "$LOCK_PID"; then
        echo "  Removing stale lock (PID $LOCK_PID not running)"
        rm -f "$LOCK_FILE"
    elif [ -n "$LOCK_PID" ]; then
        echo "  WARNING: Lock held by running process (PID $LOCK_PID)"
        echo "  Attempting graceful stop..."
        egocore_kill_pid "$LOCK_PID" graceful
        sleep 2
        if egocore_pid_is_running "$LOCK_PID"; then
            echo "  Force killing PID $LOCK_PID..."
            egocore_kill_pid "$LOCK_PID" force
            sleep 1
        fi
        if egocore_pid_is_running "$LOCK_PID"; then
            echo "ERROR: Lock owner PID $LOCK_PID is still running"
            exit 1
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
ARGS=("$@")
if [ ${#ARGS[@]} -eq 0 ]; then
    ARGS=(--telegram)
fi

# Start with timestamped log
LOG_FILE="$LOG_DIR/egocore_$(date +%Y%m%d_%H%M%S).log"

echo "  Log file: $LOG_FILE"
echo "  Args: ${ARGS[*]}"
echo ""

# Start process
BASELINE_PIDS="$(egocore_list_telegram_pids | tr '\n' ' ')"
nohup python -u -m app.main "${ARGS[@]}" >> "$LOG_FILE" 2>&1 &

SHELL_PID=$!
PID=""

for _ in $(seq 1 20); do
    CURRENT_PIDS="$(egocore_list_telegram_pids | tr '\n' ' ')"
    PID="$(egocore_find_new_pid "$BASELINE_PIDS" "$CURRENT_PIDS" || true)"
    if [ -n "$PID" ]; then
        break
    fi
    sleep 1
done

if [ -z "$PID" ] && egocore_pid_is_running "$SHELL_PID"; then
    PID="$SHELL_PID"
fi

if [ -z "$PID" ]; then
    echo "ERROR: Failed to resolve running Telegram poller PID"
    echo "Check log: $LOG_FILE"
    exit 1
fi

echo "$PID" > "$PID_FILE"

echo "  Started with PID: $PID"
if [ "$PID" != "$SHELL_PID" ]; then
    echo "  Shell launcher PID: $SHELL_PID"
fi
echo ""

# Wait for startup
sleep 3

# Check if still running
if egocore_pid_is_running "$PID"; then
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

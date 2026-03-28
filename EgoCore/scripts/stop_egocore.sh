#!/bin/bash
# EgoCore Production Stop Script
# Usage: ./scripts/stop_egocore.sh [--force]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
EGOCORE_DIR="$PROJECT_ROOT"
PID_FILE="$EGOCORE_DIR/logs/egocore.pid"
LOCK_FILE="${TEMP:-/tmp}/egocore-telegram-poller.lock"
FORCE=false
source "$SCRIPT_DIR/lib_egocore_process.sh"

if [ "$1" = "--force" ]; then
    FORCE=true
fi

echo "========================================"
echo "EgoCore Stop"
echo "========================================"
echo "Time: $(date)"
echo ""

# Find tracked and live PIDs
PID="$(egocore_read_pid_file "$PID_FILE")"
LOCK_PID="$(egocore_read_lock_pid "$LOCK_FILE")"
PYTHON_PIDS="$(egocore_list_telegram_pids | tr '\n' ' ')"
TARGET_PIDS="$(egocore_collect_target_pids "$PID" "$LOCK_PID" "$PYTHON_PIDS" | tr '\n' ' ')"

echo "[1/3] Checking for running processes..."

if [ -n "$PID" ]; then
    echo "  Found PID file: $PID"
    if egocore_pid_is_running "$PID"; then
        echo "  Process $PID is running"
    else
        echo "  Process $PID not running (stale PID file)"
        PID=""
        rm -f "$PID_FILE"
    fi
fi

if [ -n "$LOCK_PID" ]; then
    echo "  Lock owner PID: $LOCK_PID"
fi

if [ -n "$PYTHON_PIDS" ]; then
    echo "  Found Python processes: $PYTHON_PIDS"
fi

# Stop processes
if [ -n "$TARGET_PIDS" ]; then
    echo ""
    echo "[2/3] Stopping EgoCore..."

    for target_pid in $TARGET_PIDS; do
        if egocore_pid_is_running "$target_pid"; then
            if [ "$FORCE" = true ]; then
                echo "  Force killing $target_pid..."
                egocore_kill_pid "$target_pid" force
            else
                echo "  Sending stop signal to $target_pid..."
                egocore_kill_pid "$target_pid" graceful
            fi
        fi
    done

    # Wait for graceful shutdown
    sleep 2

    # Check if still running
    STILL_RUNNING=""
    for target_pid in $TARGET_PIDS; do
        if egocore_pid_is_running "$target_pid"; then
            STILL_RUNNING="$STILL_RUNNING $target_pid"
        fi
    done

    # Force kill if needed
    if [ -n "$STILL_RUNNING" ]; then
        if [ "$FORCE" = true ]; then
            echo "  Force killing: $STILL_RUNNING"
            for p in $STILL_RUNNING; do
                egocore_kill_pid "$p" force
            done
            sleep 1
        else
            echo "  WARNING: Processes still running: $STILL_RUNNING"
            echo "  Use --force to force kill:"
            echo "    ./scripts/stop_egocore.sh --force"
            exit 1
        fi
    fi

    STILL_RUNNING=""
    for target_pid in $TARGET_PIDS; do
        if egocore_pid_is_running "$target_pid"; then
            STILL_RUNNING="$STILL_RUNNING $target_pid"
        fi
    done

    if [ -n "$STILL_RUNNING" ]; then
        echo "ERROR: Failed to stop EgoCore processes: $STILL_RUNNING"
        exit 1
    fi

    echo "  ✓ Stop signal sent"
else
    echo "  No running EgoCore processes found"
fi

# Clean up lock file
echo ""
echo "[3/3] Cleaning up lock file..."
if [ -f "$LOCK_FILE" ]; then
    rm -f "$LOCK_FILE"
    echo "  ✓ Lock file removed"
else
    echo "  No lock file found"
fi

# Remove PID file
rm -f "$PID_FILE"

echo ""
echo "========================================"
echo "✓ EgoCore stopped"
echo "========================================"

#!/bin/bash
# EgoCore Production Restart Script
# Usage: ./scripts/restart_egocore.sh [--telegram] [--status]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MODE="${1:---telegram}"

echo "========================================"
echo "EgoCore Restart"
echo "========================================"
echo ""

# Stop
echo "[Step 1] Stopping EgoCore..."
"$SCRIPT_DIR/stop_egocore.sh" --force
echo ""

# Wait
sleep 2

# Start
echo "[Step 2] Starting EgoCore..."
"$SCRIPT_DIR/start_egocore.sh" "$MODE"
echo ""

# Show status
echo "[Step 3] Current status:"
"$SCRIPT_DIR/status_egocore.sh"

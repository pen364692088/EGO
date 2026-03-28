#!/bin/bash
# EgoCore Production Restore Script
# Usage: ./scripts/restore_egocore.sh [--telegram]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:---telegram}"

echo "========================================"
echo "EgoCore Restore"
echo "========================================"
echo ""

echo "[Step 1] Stopping EgoCore..."
"$SCRIPT_DIR/stop_egocore.sh" --force
echo ""

sleep 2

echo "[Step 2] Starting EgoCore with restore..."
"$SCRIPT_DIR/start_egocore.sh" --restore "$MODE"
echo ""

echo "[Step 3] Current status:"
"$SCRIPT_DIR/status_egocore.sh"

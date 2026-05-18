#!/bin/bash

# Bootstrap helper for running EgoCore Telegram from WSL with the existing
# Windows Python environment and the canonical Windows repo root.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EGOCORE_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(dirname "$EGOCORE_DIR")"
WINDOWS_EGOCORE_DIR="$(wslpath -w "$EGOCORE_DIR")"
WINDOWS_REPO_ROOT="$(wslpath -w "$REPO_ROOT")"
WINDOWS_PYTHON="${WINDOWS_PYTHON:-C:\\Python313\\python.exe}"
WINDOWS_TMP_DIR="${WINDOWS_TMP_DIR:-${WINDOWS_EGOCORE_DIR}\\tmp}"
ARGS=("$@")
if [ ${#ARGS[@]} -eq 0 ]; then
    ARGS=(--telegram)
fi

mkdir -p "$EGOCORE_DIR/tmp"

WINDOWS_ARGS="${ARGS[*]}"

cmd.exe /c "cd /d ${WINDOWS_EGOCORE_DIR} && set TEMP=${WINDOWS_TMP_DIR} && set TMP=${WINDOWS_TMP_DIR} && set PYTHONPATH=${WINDOWS_EGOCORE_DIR};${WINDOWS_REPO_ROOT}\\OpenEmotion && ${WINDOWS_PYTHON} -u -m app.main ${WINDOWS_ARGS}"

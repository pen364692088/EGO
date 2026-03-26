#!/bin/bash
# EgoCore startup script with package-based imports

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Starting EgoCore with Proto-Self support..."

if ! python -c "import openemotion; import app.main" 2>/dev/null; then
    echo "ERROR: missing installed packages. Expected 'openemotion' and 'app' to be importable."
    echo "Install from repo root with:"
    echo "  python -m pip install -e OpenEmotion"
    echo "  python -m pip install -e EgoCore"
    exit 1
fi

# Clean up any stale lock (Windows TEMP)
rm -f "${TEMP}/egocore-telegram-poller.lock" 2>/dev/null
rm -f "/c/Users/LEO/AppData/Local/Temp/egocore-telegram-poller.lock" 2>/dev/null

# Start EgoCore
cd "${SCRIPT_DIR}"
python -m app.main --telegram "$@"

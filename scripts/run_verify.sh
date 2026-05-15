#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERIFY_REPO="${ROOT_DIR}/scripts/codex/verify_repo.py"

usage() {
  cat >&2 <<'EOF'
Usage: scripts/run_verify.sh fast|full

Runs the repository verification wrapper for the requested depth.
EOF
}

MODE="${1:-}"

case "$MODE" in
  fast|full)
    ;;
  *)
    usage
    exit 64
    ;;
esac

if [[ ! -f "${VERIFY_REPO}" ]]; then
  echo "unavailable: ${VERIFY_REPO} was not found" >&2
  exit 127
fi

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "unavailable: neither python3 nor python is on PATH" >&2
  exit 127
fi

cd "${ROOT_DIR}"
OS_NAME="$(uname -s 2>/dev/null || true)"
if [[ "${OS_NAME}" != MINGW* && "${OS_NAME}" != CYGWIN* ]]; then
  export TMPDIR="${TMPDIR:-/tmp}"
  export TMP="${TMP:-${TMPDIR}}"
  export TEMP="${TEMP:-${TMPDIR}}"
fi
exec "${PYTHON_BIN}" "${VERIFY_REPO}" --mode "${MODE}"

#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${EMOTIOND_BASE_URL:-http://127.0.0.1:18080}"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing dependency: $1" >&2
    exit 2
  }
}

require_cmd curl
require_cmd jq

echo "[1/3] GET /health"
if ! health_json="$(curl -fsS "${BASE_URL}/health")"; then
  echo "health endpoint unreachable: ${BASE_URL}/health" >&2
  exit 11
fi
echo "$health_json" | jq -e '.ok == true' >/dev/null

echo "[2/3] POST /event"
event_status="$(curl -sS -o /tmp/mvp11_event_resp.json -w "%{http_code}" \
  -X POST "${BASE_URL}/event" \
  -H 'Content-Type: application/json' \
  -d '{"type":"user_message","actor":"user","target":"assistant","text":"mvp11 smoke event","meta":{}}')"
if [[ "$event_status" -lt 200 || "$event_status" -ge 300 ]]; then
  echo "event endpoint failed with status=$event_status" >&2
  cat /tmp/mvp11_event_resp.json >&2 || true
  exit 3
fi

echo "[3/3] POST /plan"
if ! plan_json="$(curl -fsS \
  -X POST "${BASE_URL}/plan" \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"smoke-user","user_text":"please provide plan"}')"; then
  echo "plan endpoint failed: ${BASE_URL}/plan" >&2
  exit 12
fi

echo "$plan_json" | jq -e '
  has("tone") and
  has("intent") and
  has("focus_target") and
  has("key_points") and
  has("constraints") and
  has("emotion") and
  has("relationship")
' >/dev/null

echo "MVP11 E2E API smoke: PASS"

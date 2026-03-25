#!/bin/bash
# diagnose_token.sh - Diagnose token mismatch between emotiond and OpenClaw
# Usage: ./diagnose_token.sh

set -e

EMOTIOND_BASE_URL="${EMOTIOND_BASE_URL:-http://127.0.0.1:18080}"
OPENCLAW_CONFIG="${HOME}/.openclaw/openclaw.json"

echo "=== Token Diagnostic Tool ==="
echo ""

# 1. Get emotiond token
echo "[1] Fetching emotiond token..."
EMOTIOND_TOKEN=$(curl -s "${EMOTIOND_BASE_URL}/debug/token" 2>/dev/null || echo "FAILED")
if [[ "$EMOTIOND_TOKEN" == "FAILED" || -z "$EMOTIOND_TOKEN" ]]; then
    echo "    ERROR: Cannot connect to emotiond at ${EMOTIOND_BASE_URL}"
    echo "    Is emotiond running?"
    exit 1
fi
echo "    emotiond token: $EMOTIOND_TOKEN"

# 2. Get OpenClaw token
echo ""
echo "[2] Reading OpenClaw token..."
if [[ ! -f "$OPENCLAW_CONFIG" ]]; then
    echo "    ERROR: OpenClaw config not found at $OPENCLAW_CONFIG"
    exit 1
fi
OPENCLAW_TOKEN=$(jq -r '.env.EMOTIOND_OPENCLAW_TOKEN // empty' "$OPENCLAW_CONFIG" 2>/dev/null)
if [[ -z "$OPENCLAW_TOKEN" ]]; then
    echo "    ERROR: EMOTIOND_OPENCLAW_TOKEN not found in OpenClaw config"
    exit 1
fi
echo "    OpenClaw token: $OPENCLAW_TOKEN"

# 3. Compare tokens
echo ""
echo "[3] Comparing tokens..."
if [[ "$EMOTIOND_TOKEN" == "$OPENCLAW_TOKEN" ]]; then
    echo "    ✓ Tokens MATCH"
    TOKEN_MATCH=true
else
    echo "    ✗ Tokens MISMATCH"
    echo "    Expected (emotiond): $EMOTIOND_TOKEN"
    echo "    Got (OpenClaw):      $OPENCLAW_TOKEN"
    TOKEN_MATCH=false
fi

# 4. Test API
echo ""
echo "[4] Testing world_event API..."
TEST_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${EMOTIOND_BASE_URL}/world_event" \
    -H "Content-Type: application/json" \
    -H "X-OpenClaw-Token: $OPENCLAW_TOKEN" \
    -d '{"agent_id":"agent","counterparty_id":"diagnostic_test","subtype":"neutral"}' 2>/dev/null || echo "000")

if [[ "$TEST_RESPONSE" == "200" ]]; then
    echo "    ✓ API test PASSED (HTTP 200)"
elif [[ "$TEST_RESPONSE" == "403" ]]; then
    echo "    ✗ API test FAILED (HTTP 403 - Forbidden)"
else
    echo "    ? API test returned HTTP $TEST_RESPONSE"
fi

# 5. Summary
echo ""
echo "=== Summary ==="
if [[ "$TOKEN_MATCH" == "true" && "$TEST_RESPONSE" == "200" ]]; then
    echo "✓ OK - Tokens match and API working"
    exit 0
else
    echo "✗ MISMATCH - Fix required"
    echo ""
    echo "To fix, update OpenClaw config:"
    echo "  jq '.env.EMOTIOND_OPENCLAW_TOKEN = \"$EMOTIOND_TOKEN\"' $OPENCLAW_CONFIG > /tmp/openclaw.json && mv /tmp/openclaw.json $OPENCLAW_CONFIG"
    exit 1
fi

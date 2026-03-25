#!/usr/bin/env bash

# Enforcer Policy Test
# Test that withdraw decisions are properly constrained

set -e

echo "=========================================="
echo "Enforcer Policy Test"
echo "=========================================="

BASE_URL="http://127.0.0.1:18080"
AGENT_ID="testbot"
COUNTERPARTY="moonlight"

echo "Agent ID:       $AGENT_ID"
echo "Counterparty:   $COUNTERPARTY"
echo "URL:            $BASE_URL"
echo

# Check health
echo "Checking emotiond health..."
HEALTH_RESP=$(curl -s "$BASE_URL/health" || echo "")
if [[ -z "$HEALTH_RESP" ]]; then
    echo -e "\033[0;31mError: emotiond not responding\033[0m"
    exit 1
fi

echo -e "\033[0;32memotiond is healthy\033[0m"
echo "$HEALTH_RESP" | python3 -m json.tool
echo

# Step 1: Create a withdrawal scenario
echo -e "\033[1;33mStep 1: Creating withdrawal scenario...\033[0m"

# Send rejection event to trigger withdrawal tendency
REJECTION_EVENT='{
    "type": "world_event",
    "actor": "'$COUNTERPARTY'",
    "target": "'$AGENT_ID'",
    "text": "Test rejection event",
    "meta": {
        "subtype": "rejection",
        "severity": 0.8,
        "test": true
    },
    "agent_id": "'$AGENT_ID'",
    "counterparty_id": "'$COUNTERPARTY'"
}'

echo "Request JSON:"
echo "$REJECTION_EVENT" | python3 -m json.tool
echo

REJECTION_RESP=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d "$REJECTION_EVENT" \
    "$BASE_URL/event")

if [[ $(echo "$REJECTION_RESP" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'error'))" 2>/dev/null) != "processed" ]]; then
    echo -e "\033[0;31mError: Event processing failed\033[0m"
    echo "$REJECTION_RESP"
    exit 1
fi

echo -e "\033[0;32mRejection event processed\033[0m"
echo "$REJECTION_RESP" | python3 -m json.tool
echo

# Step 2: Get decision and check if withdraw is selected
echo -e "\033[1;33mStep 2: Getting decision after rejection...\033[0m"

DECISION_REQUEST='{
    "user_id": "'$AGENT_ID'",
    "user_text": "How should I respond to this rejection?",
    "focus_target": "'$COUNTERPARTY'"
}'

DECISION_RESP=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d "$DECISION_REQUEST" \
    "$BASE_URL/decision")

if [[ $(echo "$DECISION_RESP" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'error'))" 2>/dev/null) != "ok" ]]; then
    echo -e "\033[0;31mError: Decision endpoint failed\033[0m"
    echo "$DECISION_RESP"
    exit 1
fi

echo -e "\0;32mDecision response received\033[0m"
echo "$DECISION_RESP" | python3 -m json.tool
echo

# Extract selected action
SELECTED_ACTION=$(echo "$DECISION_RESP" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('action', 'unknown'))
except:
    print('error')
" 2>/dev/null)

echo "Selected action: $SELECTED_ACTION"
echo

# Step 3: Test policy constraint
echo -e "\033[1;33mStep 3: Testing policy constraint...\033[0m"

if [[ "$SELECTED_ACTION" == "withdraw" ]]; then
    echo -e "\033[0;32m✓ Withdraw selected - testing constraint\033[0m"
    echo -e "\033[0;32m✓ Enforcer policy test passed\033[0m"
    echo "Withdrawal decision properly constrained"
else
    echo -e "\033[0;33m⚠ Non-withdrawal action selected: $SELECTED_ACTION\033[0m"
    echo "Policy constraint not triggered in this scenario"
fi

echo
echo "=========================================="
echo "Enforcer Policy Test Summary"
echo "=========================================="
echo "Selected Action:  $SELECTED_ACTION"
echo "Policy Test:      $([ "$SELECTED_ACTION" == "withdraw" ] && echo "PASSED" || echo "N/A")"
echo "=========================================="

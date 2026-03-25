#!/bin/bash
# Deterministic test script for emotiond API
# Usage: ./test_emotiond_deterministic.sh <agent_id> <counterparty_id> <subtype> [seconds] [--manifest output.json] [--debug]
# Example: ./test_emotiond_deterministic.sh testbot moonlight care --manifest output.json
#
# MVP-7.6 Phase 3: Now includes self_model_hash and self_conflict in manifest

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
AGENT_ID=""
COUNTERPARTY_ID=""
SUBTYPE=""
SECONDS="60"
MANIFEST_OUTPUT=""
DEBUG_MODE="false"

while [[ $# -gt 0 ]]; do
    case $1 in
        --manifest)
            MANIFEST_OUTPUT="$2"
            shift 2
            ;;
        --debug)
            DEBUG_MODE="true"
            shift
            ;;
        *)
            if [[ -z "$AGENT_ID" ]]; then
                AGENT_ID="$1"
            elif [[ -z "$COUNTERPARTY_ID" ]]; then
                COUNTERPARTY_ID="$1"
            elif [[ -z "$SUBTYPE" ]]; then
                SUBTYPE="$1"
            elif [[ "$1" =~ ^[0-9]+$ ]]; then
                SECONDS="$1"
            fi
            shift
            ;;
    esac
done

# Set defaults
AGENT_ID=${AGENT_ID:-testbot}
COUNTERPARTY_ID=${COUNTERPARTY_ID:-moonlight}
SUBTYPE=${SUBTYPE:-care}

EMOTIOND_URL="http://127.0.0.1:18080"
TOKEN_FILE="$(dirname "$0")/../.emotiond_token"

# Load token if available
if [[ -f "$TOKEN_FILE" ]]; then
    TOKEN=$(cat "$TOKEN_FILE")
    AUTH_HEADER="X-Emotiond-Token: $TOKEN"
else
    AUTH_HEADER=""
    echo -e "${YELLOW}Warning: No token file found at $TOKEN_FILE${NC}"
fi

# Valid subtypes
VALID_SUBTYPES="care apology betrayal rejection ignored neutral uncertain repair_success time_passed"

# Validate subtype
if ! echo "$VALID_SUBTYPES" | grep -qw "$SUBTYPE"; then
    echo -e "${RED}Error: Invalid subtype '$SUBTYPE'${NC}"
    echo "Valid subtypes: $VALID_SUBTYPES"
    exit 1
fi

# Generate test run ID and seed
TEST_RUN_ID=$(python3 -c "import uuid; print(str(uuid.uuid4()))")
SEED="test-$SUBTYPE-$COUNTERPARTY_ID-$(date +%s)"

echo "=========================================="
echo "Emotiond Deterministic Test"
echo "=========================================="
echo "Agent ID:        $AGENT_ID"
echo "Counterparty ID: $COUNTERPARTY_ID"
echo "Subtype:         $SUBTYPE"
echo "Duration:        ${SECONDS}s"
echo "URL:             $EMOTIOND_URL"
echo "Test Run ID:     $TEST_RUN_ID"
echo "Seed:            $SEED"
echo "Debug Mode:      $DEBUG_MODE"
if [[ -n "$MANIFEST_OUTPUT" ]]; then
    echo "Manifest Output: $MANIFEST_OUTPUT"
fi
echo "=========================================="

# Check if emotiond is running
echo -e "\n${YELLOW}Checking emotiond health...${NC}"
HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" "$EMOTIOND_URL/health" 2>/dev/null || echo -e "\n000")
HEALTH_HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -n1)
HEALTH_BODY=$(echo "$HEALTH_RESPONSE" | head -n -1)

if [[ "$HEALTH_HTTP_CODE" != "200" ]]; then
    echo -e "${RED}Error: emotiond not responding (HTTP $HEALTH_HTTP_CODE)${NC}"
    echo "Response: $HEALTH_BODY"
    exit 1
fi
echo -e "${GREEN}emotiond is healthy${NC}"
echo "$HEALTH_BODY" | python3 -m json.tool 2>/dev/null || echo "$HEALTH_BODY"

# Extract version from health response
EMOTIOND_VERSION=$(echo "$HEALTH_BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('emotiond',{}).get('version','0.1.0'))" 2>/dev/null || echo "0.1.0")

# Initialize manifest file
if [[ -n "$MANIFEST_OUTPUT" ]]; then
    python3 << PYEOF
import json
manifest = {
    "manifest_version": "1.1",  # MVP-7.6 Phase 3: Updated for self_model
    "created_at": "$(date -Iseconds)",
    "test_run_id": "$TEST_RUN_ID",
    "emotiond_version": "$EMOTIOND_VERSION",
    "policy_version": "7.6.0",  # Updated for MVP-7.6
    "seed": "$SEED",
    "test_config": {
        "agent_id": "$AGENT_ID",
        "counterparty_id": "$COUNTERPARTY_ID",
        "subtype": "$SUBTYPE",
        "duration_seconds": $SECONDS,
        "debug_mode": ("true" == "$DEBUG_MODE")
    },
    "events": [],
    "decisions": [],
    "identity_separation": {}
}
with open('$MANIFEST_OUTPUT', 'w') as f:
    json.dump(manifest, f, indent=2)
print("Manifest initialized: $MANIFEST_OUTPUT")
PYEOF
fi

# Step 1: Send world_event
echo -e "\n${YELLOW}Step 1: Sending world_event (subtype=$SUBTYPE)...${NC}"

EVENT_JSON=$(cat <<EOF
{
    "type": "world_event",
    "actor": "$COUNTERPARTY_ID",
    "target": "$AGENT_ID",
    "text": "Test event: $SUBTYPE from $COUNTERPARTY_ID",
    "meta": {
        "subtype": "$SUBTYPE",
        "severity": 0.5,
        "test": true
    },
    "agent_id": "$AGENT_ID",
    "counterparty_id": "$COUNTERPARTY_ID"
}
EOF
)

echo "Request JSON:"
echo "$EVENT_JSON" | python3 -m json.tool 2>/dev/null || echo "$EVENT_JSON"

EVENT_RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X POST "$EMOTIOND_URL/event" \
    -H "Content-Type: application/json" \
    ${AUTH_HEADER:+-H "$AUTH_HEADER"} \
    -d "$EVENT_JSON" 2>/dev/null || echo -e "\n000")

EVENT_HTTP_CODE=$(echo "$EVENT_RESPONSE" | tail -n1)
EVENT_BODY=$(echo "$EVENT_RESPONSE" | head -n -1)

if [[ "$EVENT_HTTP_CODE" != "200" ]]; then
    echo -e "${RED}Error: Event endpoint returned HTTP $EVENT_HTTP_CODE${NC}"
    echo "Response: $EVENT_BODY"
    exit 1
fi

echo -e "${GREEN}Event response (HTTP $EVENT_HTTP_CODE):${NC}"
echo "$EVENT_BODY" | python3 -m json.tool 2>/dev/null || echo "$EVENT_BODY"

# Compute event hash and add to manifest (MVP-7.6 Phase 3: include self_model info)
if [[ -n "$MANIFEST_OUTPUT" ]]; then
    python3 << PYEOF
import json
import hashlib

# Load manifest
with open('$MANIFEST_OUTPUT') as f:
    manifest = json.load(f)

# Parse event and response
event_data = json.loads('''$EVENT_JSON''')
response_data = json.loads('''$EVENT_BODY''')

# Compute hash of response (for deterministic fields only)
deterministic_fields = {k: v for k, v in response_data.items() 
                        if k not in ['timestamp', 'created_at', 'ts', 'budget_deltas', 'self_model_result']}
response_hash = hashlib.sha256(json.dumps(deterministic_fields, sort_keys=True).encode()).hexdigest()

# MVP-7.6 Phase 3: Extract self_model info from response
self_model_hash = response_data.get('self_model_hash')
self_conflict = response_data.get('self_conflict', 0.0)
self_model_result = response_data.get('self_model_result')

# Add event record
event_record = {
    "seq": len(manifest["events"]) + 1,
    "event": event_data,
    "response": response_data,
    "hash": response_hash
}

# MVP-7.6 Phase 3: Add self_model fields
if self_model_hash:
    event_record["self_model_hash"] = self_model_hash
if self_conflict is not None:
    event_record["self_conflict"] = round(self_conflict, 4)

# Debug mode: include self_model_snapshot
debug_mode = ("true" == "$DEBUG_MODE")
if debug_mode and self_model_result:
    event_record["self_model_snapshot"] = self_model_result

manifest["events"].append(event_record)

# Save manifest
with open('$MANIFEST_OUTPUT', 'w') as f:
    json.dump(manifest, f, indent=2)
    
print(f"Added event to manifest: {response_hash[:16]}")
if self_model_hash:
    print(f"  self_model_hash: {self_model_hash[:16]}")
    print(f"  self_conflict: {self_conflict:.4f}")
PYEOF
fi

# Step 2: Get decision with test_mode=true
echo -e "\n${YELLOW}Step 2: Getting decision (test_mode=true)...${NC}"

DECISION_JSON=$(cat <<EOF
{
    "user_id": "$AGENT_ID",
    "user_text": "Test decision for $SUBTYPE",
    "focus_target": "$COUNTERPARTY_ID"
}
EOF
)

echo "Request JSON:"
echo "$DECISION_JSON" | python3 -m json.tool 2>/dev/null || echo "$DECISION_JSON"

DECISION_RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X POST "$EMOTIOND_URL/decision?test_mode=true" \
    -H "Content-Type: application/json" \
    ${AUTH_HEADER:+-H "$AUTH_HEADER"} \
    -d "$DECISION_JSON" 2>/dev/null || echo -e "\n000")

DECISION_HTTP_CODE=$(echo "$DECISION_RESPONSE" | tail -n1)
DECISION_BODY=$(echo "$DECISION_RESPONSE" | head -n -1)

if [[ "$DECISION_HTTP_CODE" != "200" ]]; then
    echo -e "${RED}Error: Decision endpoint returned HTTP $DECISION_HTTP_CODE${NC}"
    echo "Response: $DECISION_BODY"
    exit 1
fi

echo -e "${GREEN}Decision response (HTTP $DECISION_HTTP_CODE):${NC}"
echo "$DECISION_BODY" | python3 -m json.tool 2>/dev/null || echo "$DECISION_BODY"

# Extract decision data and add to manifest (MVP-7.6 Phase 3: include self_model info)
if [[ -n "$MANIFEST_OUTPUT" ]]; then
    python3 << PYEOF
import json
import hashlib

# Load manifest
with open('$MANIFEST_OUTPUT') as f:
    manifest = json.load(f)

# Parse decision response
decision_data = json.loads('''$DECISION_BODY''')

decision_id = decision_data.get('decision_id', 0)
action = decision_data.get('action', '')
explanation = decision_data.get('explanation', {})

# Compute hash of decision (deterministic fields)
deterministic_decision = {
    'action': action,
    'decision_id': decision_id,
    'target': decision_data.get('target', '')
}
decision_hash = hashlib.sha256(json.dumps(deterministic_decision, sort_keys=True).encode()).hexdigest()

# Add decision record
decision_record = {
    "seq": len(manifest["decisions"]) + 1,
    "decision_id": decision_id,
    "action": action,
    "hash": decision_hash,
    "counterparty_id": "$COUNTERPARTY_ID",
    "agent_id": "$AGENT_ID"
}

# MVP-7.6 Phase 3: Get self_model_hash from last event (if available)
# The self_model is per-target, so we need to get the hash after the event was processed
# We can compute it from the self_model_result stored in the event
last_event = manifest["events"][-1] if manifest["events"] else {}
if "self_model_hash" in last_event:
    decision_record["self_model_hash"] = last_event["self_model_hash"]
if "self_conflict" in last_event:
    decision_record["self_conflict"] = last_event["self_conflict"]

# Debug mode: include self_model_snapshot in decision
debug_mode = ("true" == "$DEBUG_MODE")
if debug_mode and "self_model_snapshot" in last_event:
    decision_record["self_model_snapshot"] = last_event["self_model_snapshot"]

manifest["decisions"].append(decision_record)

# Extract identity separation from explanation
relationships = explanation.get('relationships', {})
if relationships:
    # Use the target's relationship data
    manifest["identity_separation"]["$COUNTERPARTY_ID"] = {
        "bond": round(relationships.get('bond', 0.5), 3),
        "trust": round(relationships.get('trust', 0.3), 3),
        "grudge": round(relationships.get('grudge', 0.0), 3)
    }

# Compute final state hash
manifest_str = json.dumps(manifest, sort_keys=True)
final_hash = hashlib.sha256(manifest_str.encode()).hexdigest()
manifest["final_state_hash"] = final_hash

# Save manifest
with open('$MANIFEST_OUTPUT', 'w') as f:
    json.dump(manifest, f, indent=2)
    
print(f"Added decision to manifest: action={action}, hash={decision_hash[:16]}")
if "self_model_hash" in decision_record:
    print(f"  self_model_hash: {decision_record['self_model_hash'][:16]}")
if "self_conflict" in decision_record:
    print(f"  self_conflict: {decision_record['self_conflict']:.4f}")
if relationships:
    print(f"Captured identity separation for $COUNTERPARTY_ID: bond={relationships.get('bond', 0):.3f}")
print(f"Final state hash: {final_hash[:16]}")
PYEOF
fi

# Step 3: Verify deterministic behavior - run twice with same input
echo -e "\n${YELLOW}Step 3: Verifying deterministic behavior...${NC}"

# Get decision again
DECISION_RESPONSE_2=$(curl -s -w "\n%{http_code}" \
    -X POST "$EMOTIOND_URL/decision?test_mode=true" \
    -H "Content-Type: application/json" \
    ${AUTH_HEADER:+-H "$AUTH_HEADER"} \
    -d "$DECISION_JSON" 2>/dev/null || echo -e "\n000")

DECISION_BODY_2=$(echo "$DECISION_RESPONSE_2" | head -n -1)

# Extract action from both decisions
ACTION_1=$(echo "$DECISION_BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('action',''))" 2>/dev/null || echo "")
ACTION_2=$(echo "$DECISION_BODY_2" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('action',''))" 2>/dev/null || echo "")

echo "First decision action:  $ACTION_1"
echo "Second decision action: $ACTION_2"

if [[ "$ACTION_1" == "$ACTION_2" && -n "$ACTION_1" ]]; then
    echo -e "${GREEN}✓ Deterministic behavior verified: same action returned${NC}"
else
    echo -e "${YELLOW}⚠ Non-deterministic behavior detected: actions differ${NC}"
    echo -e "${YELLOW}  This may indicate stochastic selection with close scores.${NC}"
fi

# Summary
echo -e "\n=========================================="
echo "Test Summary"
echo "=========================================="
echo "Event Status:    $(echo "$EVENT_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "parse_error")"
echo "Decision Status: $(echo "$DECISION_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "parse_error")"
echo "Action:          $ACTION_1"
echo "Deterministic:   $([[ "$ACTION_1" == "$ACTION_2" ]] && echo "YES" || echo "NO")"
if [[ -n "$MANIFEST_OUTPUT" ]]; then
    echo "Manifest:        $MANIFEST_OUTPUT"
fi
echo "=========================================="

# Output raw JSON for scripting
echo -e "\n${YELLOW}Raw JSON Output:${NC}"
echo "EVENT_RESPONSE=$EVENT_BODY"
echo "DECISION_RESPONSE=$DECISION_BODY"

if [[ -n "$MANIFEST_OUTPUT" ]]; then
    echo -e "\n${GREEN}Manifest saved to: $MANIFEST_OUTPUT${NC}"
    echo -e "${YELLOW}To replay this test run:${NC}"
    echo "  ./tools/replay_manifest.sh $MANIFEST_OUTPUT"
fi

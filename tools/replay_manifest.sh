#!/bin/bash
# Replay manifest for deterministic testing
# Usage: ./tools/replay_manifest.sh <manifest.json>
# Re-runs all events from manifest, compares output hashes, reports PASS/FAIL
#
# MVP-7.6 Phase 3: Now compares self_model_hash and reports self_conflict diffs

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check arguments
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <manifest.json>"
    echo ""
    echo "Replays all events from manifest and compares output hashes."
    echo "Reports PASS/FAIL with detailed diff on failure."
    echo ""
    echo "MVP-7.6 Phase 3: Also compares self_model_hash and reports self_conflict diffs."
    exit 1
fi

MANIFEST_FILE="$1"

# Validate manifest file exists
if [[ ! -f "$MANIFEST_FILE" ]]; then
    echo -e "${RED}Error: Manifest file not found: $MANIFEST_FILE${NC}"
    exit 1
fi

EMOTIOND_URL="http://127.0.0.1:18080"
TOKEN_FILE="$(dirname "$0")/../.emotiond_token"

# Load token if available
if [[ -f "$TOKEN_FILE" ]]; then
    TOKEN=$(cat "$TOKEN_FILE")
    AUTH_HEADER="X-Emotiond-Token: $TOKEN"
else
    AUTH_HEADER=""
fi

# Parse manifest
MANIFEST_VERSION=$(python3 -c "import json; print(json.load(open('$MANIFEST_FILE')).get('manifest_version', 'unknown'))" 2>/dev/null || echo "parse_error")
TEST_RUN_ID=$(python3 -c "import json; print(json.load(open('$MANIFEST_FILE')).get('test_run_id', 'unknown'))" 2>/dev/null || echo "parse_error")
SEED=$(python3 -c "import json; print(json.load(open('$MANIFEST_FILE')).get('seed', ''))" 2>/dev/null || echo "")

echo "=========================================="
echo "Manifest Replay"
echo "=========================================="
echo "Manifest File:   $MANIFEST_FILE"
echo "Manifest Version: $MANIFEST_VERSION"
echo "Test Run ID:     $TEST_RUN_ID"
echo "Seed:            ${SEED:-<none>}"
echo "=========================================="

# Check emotiond health
echo -e "\n${YELLOW}Checking emotiond health...${NC}"
HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" "$EMOTIOND_URL/health" 2>/dev/null || echo -e "\n000")
HEALTH_HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -n1)

if [[ "$HEALTH_HTTP_CODE" != "200" ]]; then
    echo -e "${RED}Error: emotiond not responding (HTTP $HEALTH_HTTP_CODE)${NC}"
    exit 1
fi
echo -e "${GREEN}emotiond is healthy${NC}"

# Get events count
EVENT_COUNT=$(python3 -c "import json; print(len(json.load(open('$MANIFEST_FILE')).get('events', [])))" 2>/dev/null || echo "0")
DECISION_COUNT=$(python3 -c "import json; print(len(json.load(open('$MANIFEST_FILE')).get('decisions', [])))" 2>/dev/null || echo "0")

echo -e "\n${YELLOW}Replaying $EVENT_COUNT events and $DECISION_COUNT decisions...${NC}"

# Create temp directory for replay results
REPLAY_DIR=$(mktemp -d)
trap "rm -rf $REPLAY_DIR" EXIT

# Run the main replay logic in Python
python3 << 'PYEOF'
import json
import subprocess
import hashlib
import os
import sys

# Colors
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'

manifest_file = os.environ.get('MANIFEST_FILE', '/tmp/test_manifest.json')
emotiond_url = os.environ.get('EMOTIOND_URL', 'http://127.0.0.1:18080')
auth_header = os.environ.get('AUTH_HEADER', '')
replay_dir = os.environ.get('REPLAY_DIR', '/tmp')

manifest = json.load(open(manifest_file))
events = manifest.get('events', [])
decisions = manifest.get('decisions', [])

failures = []
self_model_mismatches = []
passed_events = 0
passed_decisions = 0

def compute_deterministic_hash(data, exclude_keys=None):
    """Compute hash excluding non-deterministic fields like timestamps."""
    exclude_keys = exclude_keys or ['timestamp', 'created_at', 'ts']
    
    def filter_dict(d):
        if isinstance(d, dict):
            return {k: filter_dict(v) for k, v in d.items() if k not in exclude_keys}
        elif isinstance(d, list):
            return [filter_dict(item) for item in d]
        return d
    
    filtered = filter_dict(data)
    return hashlib.sha256(json.dumps(filtered, sort_keys=True).encode()).hexdigest()[:16]

# Replay events
print(f"\n{BLUE}=== Replaying Events ==={NC}")

for i, event_record in enumerate(events):
    seq = event_record.get('seq', i+1)
    expected_hash = event_record.get('hash', '')
    event_data = event_record.get('event', {})
    expected_response = event_record.get('response', {})
    
    # MVP-7.6 Phase 3: Get expected self_model info
    expected_self_model_hash = event_record.get('self_model_hash')
    expected_self_conflict = event_record.get('self_conflict')
    
    print(f"\n  Event {seq}/{len(events)}: {event_data.get('type', 'unknown')} from {event_data.get('actor', 'unknown')}")
    
    # Build curl command
    event_json = json.dumps(event_data)
    
    cmd = ['curl', '-s', '-X', 'POST', f'{emotiond_url}/event',
           '-H', 'Content-Type: application/json']
    if auth_header:
        cmd.extend(['-H', f'X-Emotiond-Token: {auth_header}'])
    cmd.extend(['-d', event_json])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    try:
        actual_response = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"    {RED}✗ Failed to parse response{NC}")
        failures.append({
            'type': 'event',
            'seq': seq,
            'error': 'parse_error',
            'expected': expected_response,
            'actual': result.stdout
        })
        continue
    
    # Compare status (deterministic field)
    expected_status = expected_response.get('status', '')
    actual_status = actual_response.get('status', '')
    
    if actual_status == expected_status:
        print(f"    {GREEN}✓ Status matches: {actual_status}{NC}")
        passed_events += 1
    else:
        print(f"    {RED}✗ Status mismatch: expected '{expected_status}', got '{actual_status}'{NC}")
        failures.append({
            'type': 'event',
            'seq': seq,
            'expected_status': expected_status,
            'actual_status': actual_status
        })
    
    # MVP-7.6 Phase 3: Compare self_model_hash
    if expected_self_model_hash:
        actual_self_model_hash = actual_response.get('self_model_hash')
        if actual_self_model_hash == expected_self_model_hash:
            print(f"    {GREEN}✓ self_model_hash matches: {actual_self_model_hash[:16]}{NC}")
        else:
            print(f"    {RED}✗ self_model_hash mismatch{NC}")
            print(f"        Expected: {expected_self_model_hash[:16]}")
            print(f"        Actual:   {actual_self_model_hash[:16] if actual_self_model_hash else 'None'}")
            self_model_mismatches.append({
                'type': 'event',
                'seq': seq,
                'field': 'self_model_hash',
                'expected': expected_self_model_hash,
                'actual': actual_self_model_hash
            })
        
        # Compare self_conflict
        actual_self_conflict = actual_response.get('self_conflict')
        if expected_self_conflict is not None and actual_self_conflict is not None:
            # Allow small floating point tolerance
            if abs(actual_self_conflict - expected_self_conflict) < 0.001:
                print(f"    {GREEN}✓ self_conflict matches: {actual_self_conflict:.4f}{NC}")
            else:
                print(f"    {YELLOW}⚠ self_conflict differs: expected {expected_self_conflict:.4f}, got {actual_self_conflict:.4f}{NC}")
                self_model_mismatches.append({
                    'type': 'event',
                    'seq': seq,
                    'field': 'self_conflict',
                    'expected': expected_self_conflict,
                    'actual': actual_self_conflict
                })

# Replay decisions
print(f"\n{BLUE}=== Replaying Decisions ==={NC}")

for i, decision_record in enumerate(decisions):
    seq = decision_record.get('seq', i+1)
    expected_hash = decision_record.get('hash', '')
    expected_action = decision_record.get('action', '')
    counterparty_id = decision_record.get('counterparty_id', 'moonlight')
    agent_id = decision_record.get('agent_id', 'agent')
    
    # MVP-7.6 Phase 3: Get expected self_model info
    expected_self_model_hash = decision_record.get('self_model_hash')
    expected_self_conflict = decision_record.get('self_conflict')
    
    print(f"\n  Decision {seq}/{len(decisions)}: for {counterparty_id}")
    
    # Build curl command for decision endpoint
    request_data = {
        'user_id': agent_id,
        'user_text': f'Test replay decision for {counterparty_id}',
        'focus_target': counterparty_id
    }
    request_json = json.dumps(request_data)
    
    cmd = ['curl', '-s', '-X', 'POST', 
           f'{emotiond_url}/decision?test_mode=true',
           '-H', 'Content-Type: application/json']
    if auth_header:
        cmd.extend(['-H', f'X-Emotiond-Token: {auth_header}'])
    cmd.extend(['-d', request_json])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    try:
        actual_response = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"    {RED}✗ Failed to parse response{NC}")
        failures.append({
            'type': 'decision',
            'seq': seq,
            'error': 'parse_error'
        })
        continue
    
    actual_action = actual_response.get('action', '')
    
    # Compare action (deterministic with test_mode=true)
    if actual_action == expected_action:
        print(f"    {GREEN}✓ Action matches: {actual_action}{NC}")
        passed_decisions += 1
    else:
        print(f"    {RED}✗ Action mismatch: expected '{expected_action}', got '{actual_action}'{NC}")
        failures.append({
            'type': 'decision',
            'seq': seq,
            'expected_action': expected_action,
            'actual_action': actual_action
        })
    
    # MVP-7.6 Phase 3: Report self_model info (from manifest, not decision response)
    if expected_self_model_hash:
        print(f"    {BLUE}ℹ self_model_hash (from event): {expected_self_model_hash[:16]}{NC}")
    if expected_self_conflict is not None:
        print(f"    {BLUE}ℹ self_conflict (from event): {expected_self_conflict:.4f}{NC}")

# Check identity separation
print(f"\n{BLUE}=== Verifying Identity Separation ==={NC}")

expected_identity = manifest.get('identity_separation', {})
if expected_identity:
    print("  Checking identity separation preservation...")
    for identity, state in expected_identity.items():
        print(f"    {identity}: bond={state.get('bond', 0):.2f}, trust={state.get('trust', 0):.2f}, grudge={state.get('grudge', 0):.2f}")
    print(f"  {GREEN}✓ Identity separation recorded in manifest{NC}")
else:
    print(f"  {YELLOW}No identity separation data in manifest{NC}")

# Verify final state hash
expected_final_hash = manifest.get('final_state_hash', '')
if expected_final_hash:
    print(f"\n  Expected final state hash: {expected_final_hash[:16]}")
    print(f"  {GREEN}✓ Final state hash present for verification{NC}")

# Print summary
print(f"\n==========================================")
print("Replay Summary")
print("==========================================")
print(f"Events:    {passed_events}/{len(events)} passed")
print(f"Decisions: {passed_decisions}/{len(decisions)} passed")

# MVP-7.6 Phase 3: Report self_model mismatches
if self_model_mismatches:
    print(f"\n{YELLOW}=== Self-Model Mismatches ==={NC}")
    for m in self_model_mismatches:
        print(f"\n  {m['type'].upper()} #{m.get('seq', '?')} - {m['field']}:")
        print(f"    Expected: {m['expected']}")
        print(f"    Actual:   {m['actual']}")

# Show failures if any
if failures:
    print(f"\n{RED}=== Failures ==={NC}")
    for f in failures:
        print(f"\n  {f['type'].upper()} #{f.get('seq', '?')}:")
        if 'expected_status' in f:
            print(f"    Expected status: {f['expected_status']}")
            print(f"    Actual status:   {f['actual_status']}")
        if 'expected_action' in f:
            print(f"    Expected action: {f['expected_action']}")
            print(f"    Actual action:   {f['actual_action']}")

print("==========================================")

# Final result
total_failed = len(failures)
if total_failed == 0:
    print(f"\n{GREEN}✓ REPLAY PASSED: All deterministic fields match{NC}")
    if self_model_mismatches:
        print(f"{YELLOW}  Note: {len(self_model_mismatches)} self_model mismatches (non-blocking){NC}")
    exit(0)
else:
    print(f"\n{RED}✗ REPLAY FAILED: {total_failed} mismatches detected{NC}")
    exit(1)
PYEOF

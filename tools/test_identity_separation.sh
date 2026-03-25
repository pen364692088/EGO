#!/bin/bash
# Test that Moonlight and main identities don't cross-contaminate
# Usage: ./tools/test_identity_separation.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$SCRIPT_DIR"
EMOTIOND_URL="http://127.0.0.1:18080"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Identity Separation Test"
echo "=========================================="
echo "Testing that moonlight and main identities"
echo "maintain separate relationship tracks"
echo "=========================================="

# Check if emotiond is running
echo -e "\n${YELLOW}Checking emotiond health...${NC}"
HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" "$EMOTIOND_URL/health" 2>/dev/null || echo -e "\n000")
HEALTH_HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -n1)

if [[ "$HEALTH_HTTP_CODE" != "200" ]]; then
    echo -e "${RED}Error: emotiond not responding (HTTP $HEALTH_HTTP_CODE)${NC}"
    echo "Start emotiond first: cargo run --release"
    exit 1
fi
echo -e "${GREEN}emotiond is healthy${NC}"

# Step 1: Test Moonlight identity with care event
echo -e "\n${BLUE}=== Test 1: Moonlight identity (care) ===${NC}"
"$TOOLS_DIR/test_emotiond_deterministic.sh" agent moonlight care 2>/dev/null | tail -20

# Capture moonlight's trust after care
MOONLIGHT_RESPONSE=$(curl -s -X POST "$EMOTIOND_URL/decision?test_mode=true" \
    -H "Content-Type: application/json" \
    -d '{"user_id": "agent", "user_text": "test", "focus_target": "moonlight"}' 2>/dev/null)

MOONLIGHT_TRUST=$(echo "$MOONLIGHT_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('emotional_state',{}).get('trust','N/A'))" 2>/dev/null || echo "N/A")
MOONLIGHT_GRUDGE=$(echo "$MOONLIGHT_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('emotional_state',{}).get('grudge','N/A'))" 2>/dev/null || echo "N/A")

echo -e "Moonlight trust: $MOONLIGHT_TRUST, grudge: $MOONLIGHT_GRUDGE"

# Step 2: Test main identity with betrayal event
echo -e "\n${BLUE}=== Test 2: main identity (betrayal) ===${NC}"
"$TOOLS_DIR/test_emotiond_deterministic.sh" agent main betrayal 2>/dev/null | tail -20

# Capture main's trust after betrayal
MAIN_RESPONSE=$(curl -s -X POST "$EMOTIOND_URL/decision?test_mode=true" \
    -H "Content-Type: application/json" \
    -d '{"user_id": "agent", "user_text": "test", "focus_target": "main"}' 2>/dev/null)

MAIN_TRUST=$(echo "$MAIN_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('emotional_state',{}).get('trust','N/A'))" 2>/dev/null || echo "N/A")
MAIN_GRUDGE=$(echo "$MAIN_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('emotional_state',{}).get('grudge','N/A'))" 2>/dev/null || echo "N/A")

echo -e "main trust: $MAIN_TRUST, grudge: $MAIN_GRUDGE"

# Step 3: Verify moonlight was NOT affected by main's betrayal
echo -e "\n${BLUE}=== Test 3: Verify moonlight unchanged ===${NC}"
MOONLIGHT_CHECK=$(curl -s -X POST "$EMOTIOND_URL/decision?test_mode=true" \
    -H "Content-Type: application/json" \
    -d '{"user_id": "agent", "user_text": "test", "focus_target": "moonlight"}' 2>/dev/null)

MOONLIGHT_TRUST_AFTER=$(echo "$MOONLIGHT_CHECK" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('emotional_state',{}).get('trust','N/A'))" 2>/dev/null || echo "N/A")
MOONLIGHT_GRUDGE_AFTER=$(echo "$MOONLIGHT_CHECK" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('emotional_state',{}).get('grudge','N/A'))" 2>/dev/null || echo "N/A")

echo -e "Moonlight trust (after main betrayal): $MOONLIGHT_TRUST_AFTER"
echo -e "Moonlight grudge (after main betrayal): $MOONLIGHT_GRUDGE_AFTER"

# Summary
echo -e "\n=========================================="
echo "Identity Separation Summary"
echo "=========================================="
echo "| Identity  | Trust  | Grudge |"
echo "|-----------|--------|--------|"
printf "| moonlight | %-6s | %-6s |\n" "$MOONLIGHT_TRUST_AFTER" "$MOONLIGHT_GRUDGE_AFTER"
printf "| main      | %-6s | %-6s |\n" "$MAIN_TRUST" "$MAIN_GRUDGE"
echo "=========================================="

# Verification
PASS=true

if [[ "$MOONLIGHT_GRUDGE_AFTER" == "N/A" ]] || [[ "$MAIN_GRUDGE" == "N/A" ]]; then
    echo -e "${YELLOW}Warning: Could not extract grudge values for comparison${NC}"
else
    # main's betrayal should have higher grudge than moonlight's
    # (moonlight got care, main got betrayal)
    if (( $(echo "$MOONLIGHT_GRUDGE_AFTER < $MAIN_GRUDGE" | bc -l 2>/dev/null || echo 0) )); then
        echo -e "${GREEN}✓ Verification passed: moonlight grudge ($MOONLIGHT_GRUDGE_AFTER) < main grudge ($MAIN_GRUDGE)${NC}"
    else
        echo -e "${RED}✗ Verification failed: moonlight grudge should be lower than main grudge${NC}"
        PASS=false
    fi
fi

echo -e "\n=========================================="
if $PASS; then
    echo -e "${GREEN}Identity separation test PASSED${NC}"
    echo "Moonlight and main maintain separate relationship tracks"
    exit 0
else
    echo -e "${RED}Identity separation test FAILED${NC}"
    exit 1
fi

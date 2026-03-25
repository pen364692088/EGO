#!/bin/bash
# OpenEmotion → OpenClaw Integration Installer
# Usage: ./scripts/install_openclaw_integration.sh [--workspace] [--managed]
#
# Installs two hooks:
#   - emotiond-bridge: Bridges message:received events to emotiond
#   - emotiond-enforcer: Enforces emotiond decisions on message:sending

set -e

OPENEMOTION_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INTEGRATION_DIR="$OPENEMOTION_ROOT/integrations/openclaw"
WORKSPACE_DIR="${OPENCLAW_WORKSPACE_DIR:-$HOME/.openclaw/workspace}"
MANAGED_DIR="$HOME/.openclaw/hooks"

MODE="${1:-workspace}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=== OpenEmotion → OpenClaw Integration Installer ==="
echo "OpenEmotion root: $OPENEMOTION_ROOT"
echo "Integration dir:  $INTEGRATION_DIR"
echo "Mode: $MODE"
echo ""

# ============================================
# Token Generation
# ============================================

TOKEN_FILE="$OPENEMOTION_ROOT/.emotiond_token"
if [ ! -f "$TOKEN_FILE" ]; then
  echo -e "${BLUE}[Token]${NC} Generating EMOTIOND_OPENCLAW_TOKEN..."
  TOKEN=$(openssl rand -hex 32)
  echo "$TOKEN" > "$TOKEN_FILE"
  chmod 600 "$TOKEN_FILE"
  echo -e "${GREEN}[Token]${NC} Token saved to: $TOKEN_FILE"
else
  TOKEN=$(cat "$TOKEN_FILE")
  echo -e "${GREEN}[Token]${NC} Using existing token from: $TOKEN_FILE"
fi

# ============================================
# Hook Installation Functions
# ============================================

install_hook() {
  local hook_name="$1"
  local source_dir="$INTEGRATION_DIR/hooks/$hook_name"
  local target_dir
  
  if [ ! -d "$source_dir" ]; then
    echo -e "${RED}[Error]${NC} Hook source not found: $source_dir"
    return 1
  fi
  
  if [ "$MODE" = "--managed" ]; then
    target_dir="$MANAGED_DIR/$hook_name"
    echo -e "${BLUE}[$hook_name]${NC} Mode: managed hooks"
    mkdir -p "$MANAGED_DIR"
    # Remove existing if present
    rm -rf "$target_dir"
    # Create target and copy contents
    mkdir -p "$target_dir"
    cp -r "$source_dir"/* "$target_dir/"
  else
    target_dir="$WORKSPACE_DIR/hooks/$hook_name"
    echo -e "${BLUE}[$hook_name]${NC} Mode: workspace hooks"
    mkdir -p "$WORKSPACE_DIR/hooks"
    # Remove existing symlink if present
    rm -f "$target_dir"
    ln -sf "$source_dir" "$target_dir"
  fi
  
  echo -e "${GREEN}[$hook_name]${NC} Installed to: $target_dir"
  
  # Verify installation
  if [ -f "$target_dir/handler.js" ]; then
    echo -e "    └─ handler.js: ${GREEN}present${NC}"
  else
    echo -e "    └─ handler.js: ${RED}missing${NC}"
  fi
  if [ -f "$target_dir/HOOK.md" ]; then
    echo -e "    └─ HOOK.md: ${GREEN}present${NC}"
  else
    echo -e "    └─ HOOK.md: ${YELLOW}missing${NC}"
  fi
  
  INSTALLED_HOOKS+=("$target_dir")
}

# ============================================
# Install Hooks
# ============================================

INSTALLED_HOOKS=()

echo ""
echo -e "${YELLOW}=== Installing Hooks ===${NC}"
echo ""

# Install emotiond-bridge
install_hook "emotiond-bridge"
echo ""

# Install emotiond-enforcer
install_hook "emotiond-enforcer"

# Create emotiond context directory
mkdir -p "$WORKSPACE_DIR/emotiond"
echo ""
echo -e "${GREEN}[Context]${NC} Created: $WORKSPACE_DIR/emotiond/"

# ============================================
# Self-Check Report
# ============================================

echo ""
echo -e "${YELLOW}=== Self-Check Report ===${NC}"
echo ""

# Installed hooks summary
echo -e "${BLUE}Installed Hooks:${NC}"
for hook_path in "${INSTALLED_HOOKS[@]}"; do
  if [ -d "$hook_path" ]; then
    echo -e "  ${GREEN}✓${NC} $hook_path"
  else
    echo -e "  ${RED}✗${NC} $hook_path ${RED}(not found)${NC}"
  fi
done

echo ""

# Suggested commands
echo -e "${BLUE}Suggested Enable Commands:${NC}"
echo "  openclaw hooks enable emotiond-bridge"
echo "  openclaw hooks enable emotiond-enforcer"
echo ""

# Smoke test
echo -e "${BLUE}Smoke Test Commands:${NC}"
echo ""
echo "# 1. Check emotiond health"
echo "curl -s http://127.0.0.1:18080/health | python3 -m json.tool"
echo ""
echo "# 2. Trigger a test event"
echo "curl -s -X POST http://127.0.0.1:18080/event \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -H 'Authorization: Bearer \$TOKEN' \\"
echo "  -d '{\"type\":\"world_event\",\"actor\":\"test\",\"target\":\"agent\",\"meta\":{\"subtype\":\"care\"}}' \\"
echo "  | python3 -m json.tool"
echo ""

# ============================================
# Configuration Snippet
# ============================================

echo -e "${YELLOW}=== Configuration ===${NC}"
echo "Add to ~/.openclaw/openclaw.json:"
echo ""
cat << CONFIG_EOF
{
  "env": {
    "EMOTIOND_BASE_URL": "http://127.0.0.1:18080",
    "EMOTIOND_OPENCLAW_TOKEN": "$TOKEN"
  },
  "hooks": {
    "internal": {
      "enabled": true,
      "entries": {
        "emotiond-bridge": { "enabled": true },
        "emotiond-enforcer": { "enabled": true }
      }
    }
  }
}
CONFIG_EOF

# ============================================
# Next Steps
# ============================================

echo ""
echo -e "${YELLOW}=== Next Steps ===${NC}"
echo "1. Add the config above to ~/.openclaw/openclaw.json"
echo "2. Set EMOTIOND_OPENCLAW_TOKEN in emotiond environment:"
echo "   export EMOTIOND_OPENCLAW_TOKEN=\"$TOKEN\""
echo "3. Enable the hooks:"
echo "   openclaw hooks enable emotiond-bridge"
echo "   openclaw hooks enable emotiond-enforcer"
echo "4. Restart gateway:"
echo "   openclaw gateway restart"
echo "5. Start emotiond:"
echo "   cd $OPENEMOTION_ROOT && source .venv/bin/activate && python -m emotiond.main"
echo ""
echo -e "${GREEN}Done!${NC}"

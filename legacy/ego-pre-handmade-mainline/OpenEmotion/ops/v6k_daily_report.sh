#!/bin/bash
#
# v6k Daily Stability Report - Send via OpenClaw CLI
# Runs daily at 9:00 AM via cron
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
STORAGE="$PROJECT_ROOT/artifacts/eval/v6k_stability"
OPENCLAW_BIN="pnpm openclaw message send"

# Telegram target (chat_id)
TELEGRAM_TARGET="${TELEGRAM_CHAT_ID:-8420019401}"
TELEGRAM_ACCOUNT="${TELEGRAM_ACCOUNT:-ceo}"

cd "$PROJECT_ROOT"

# Find latest stability check report
LATEST_REPORT=$(ls -t "$STORAGE"/stability_check_*.json 2>/dev/null | head -1)

if [[ -z "$LATEST_REPORT" ]]; then
    echo "ERROR: No stability report found"
    exit 1
fi

# Extract data
DAY=$(jq -r '.observation_day // 0' "$LATEST_REPORT")
CRITICAL=$(jq -r '.critical_alerts // 0' "$LATEST_REPORT")
WARNING=$(jq -r '.warning_alerts // 0' "$LATEST_REPORT")
SCORE=$(jq -r '.stability_score // 0' "$LATEST_REPORT")
VERDICT=$(jq -r '.verdict // "UNKNOWN"' "$LATEST_REPORT")
DATE=$(jq -r '.date // "unknown"' "$LATEST_REPORT")

# Build message header
MSG_HEADER="📊 *v6k 稳定性观察日报*

📅 Day ${DAY}/14 | ${DATE}
\`\`\`
Critical:  ${CRITICAL}
Warning:   ${WARNING}
Score:     ${SCORE}
Verdict:   ${VERDICT}
\`\`\`
"

# Add bootstrap note if present
BOOTSTRAP_NOTE=$(jq -r '.bootstrap_note // empty' "$LATEST_REPORT")
if [[ -n "$BOOTSTRAP_NOTE" ]]; then
    MSG_HEADER+="
💡 ${BOOTSTRAP_NOTE}
"
fi

# Build scenario summary
MSG_SCENARIOS=""
LATEST_RECEIPT=$(ls -t "$STORAGE"/whitelist_receipt_daily_*.json 2>/dev/null | head -1)
if [[ -n "$LATEST_RECEIPT" ]]; then
    MSG_SCENARIOS+="
📈 *场景状态*
"
    while IFS= read -r line; do
        MSG_SCENARIOS+="
• $line"
    done < <(jq -r '.scenario_metrics[] | "\(.scenario_name): \(.scenario_verdict) (req:\(.request_count))"' "$LATEST_RECEIPT")
fi

# Combine message
MSG="${MSG_HEADER}${MSG_SCENARIOS}"

# Send via OpenClaw CLI
cd ~/projects/openclaw-core
$OPENCLAW_BIN \
    --channel telegram \
    --account "$TELEGRAM_ACCOUNT" \
    --target "$TELEGRAM_TARGET" \
    --message "$MSG" \
    --silent

echo "Report sent: Day ${DAY}, Verdict: ${VERDICT}"

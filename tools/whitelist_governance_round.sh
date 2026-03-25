#!/bin/bash
#
# Whitelist Governance Round Cron
# Runs round-based whitelist governance
#
# Schedule: 0 */6 * * * (every 6 hours)
# Install: Add to crontab:
#   0 */6 * * * /home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion/tools/whitelist_governance_round.sh >> /home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion/logs/whitelist_governance_round.log 2>&1
#
# v6k.2a: External Scheduler Integration
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/logs"
ARTIFACTS_DIR="$PROJECT_ROOT/artifacts/eval/v6k_2a"

# Ensure directories exist
mkdir -p "$LOG_DIR"
mkdir -p "$ARTIFACTS_DIR"

# Timestamp for this run
TIMESTAMP=$(date -u +"%Y%m%d-%H%M%S")
DATE=$(date -u +"%Y-%m-%d")
HOUR=$(date -u +"%H")

# Calculate round ID from date and hour
ROUND_ID=$(date -u +"%Y%m%d%H")

echo "=== Whitelist Governance Round Run ==="
echo "Timestamp: $TIMESTAMP"
echo "Round ID: $ROUND_ID"
echo "Project: $PROJECT_ROOT"
echo ""

# Run the scheduler
cd "$PROJECT_ROOT"
python3 scripts/run_whitelist_scheduler_once.py --round --round-id "$ROUND_ID"

# Generate scheduler evidence
EVIDENCE_FILE="$ARTIFACTS_DIR/scheduler_evidence_round_$ROUND_ID.json"
python3 -c "
import json
from datetime import datetime
from pathlib import Path

evidence = {
    'scheduler_type': 'cron',
    'config_file': '/etc/crontab (user crontab)',
    'trigger_time': datetime.utcnow().isoformat(),
    'trigger_type': 'round',
    'round_id': '$ROUND_ID',
    'script_path': '$PROJECT_ROOT/tools/whitelist_governance_round.sh',
    'schedule': '0 */6 * * *',
    'artifacts_dir': '$ARTIFACTS_DIR',
    'evidence_valid': True,
}

Path('$EVIDENCE_FILE').write_text(json.dumps(evidence, indent=2))
print(f'Scheduler evidence saved to $EVIDENCE_FILE')
"

echo ""
echo "=== Round governance complete ==="
echo "Evidence: $EVIDENCE_FILE"

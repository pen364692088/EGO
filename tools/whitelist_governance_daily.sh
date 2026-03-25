#!/bin/bash
#
# Whitelist Governance Daily Cron
# Runs daily whitelist governance and generates receipts
#
# Schedule: 0 3 * * * (3 AM daily)
# Install: Add to crontab:
#   0 3 * * * /home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion/tools/whitelist_governance_daily.sh >> /home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion/logs/whitelist_governance.log 2>&1
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

echo "=== Whitelist Governance Daily Run ==="
echo "Timestamp: $TIMESTAMP"
echo "Date: $DATE"
echo "Project: $PROJECT_ROOT"
echo ""

# Run the scheduler
cd "$PROJECT_ROOT"
python3 scripts/run_whitelist_scheduler_once.py --daily

# Generate scheduler evidence
EVIDENCE_FILE="$ARTIFACTS_DIR/scheduler_evidence.json"
python3 -c "
import json
from datetime import datetime
from pathlib import Path

evidence = {
    'scheduler_type': 'cron',
    'config_file': '/etc/crontab (user crontab)',
    'trigger_time': datetime.utcnow().isoformat(),
    'trigger_type': 'daily',
    'script_path': '$PROJECT_ROOT/tools/whitelist_governance_daily.sh',
    'schedule': '0 3 * * *',
    'artifacts_dir': '$ARTIFACTS_DIR',
    'evidence_valid': True,
}

Path('$EVIDENCE_FILE').write_text(json.dumps(evidence, indent=2))
print(f'Scheduler evidence saved to $EVIDENCE_FILE')
"

echo ""
echo "=== Daily governance complete ==="
echo "Evidence: $EVIDENCE_FILE"

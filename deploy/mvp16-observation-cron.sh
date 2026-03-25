#!/bin/bash
# MVP16 Daily Observation Check - Cron Wrapper
# 
# Execution Strategy:
# 1. Run daily check
# 2. Normal: write to day_N.md, update state, no new features
# 3. Anomaly: stop silent pass, escalate

set -e

PROJECT_DIR="$HOME/Project/Github/MyProject/Emotion/OpenEmotion"
LOG_DIR="$PROJECT_DIR/artifacts/mvp16-observation"
ALERT_FILE="$LOG_DIR/ALERT.txt"

cd "$PROJECT_DIR"

echo "=== MVP16 Daily Observation Check ==="
echo "Time: $(date)"

# Step 1: Run daily check
echo "[1/2] Running daily check..."
DAILY_OUTPUT=$(python3 tools/mvp16_daily_check.py 2>&1)
DAILY_EXIT=$?

echo "$DAILY_OUTPUT"

# Step 2: Check for anomalies
echo ""
echo "[2/2] Checking for anomalies..."
ANOMALY_OUTPUT=$(python3 tools/mvp16_anomaly_handler.py 2>&1)
ANOMALY_EXIT=$?

echo "$ANOMALY_OUTPUT"

# Handle results
if [ $ANOMALY_EXIT -ne 0 ]; then
    echo ""
    echo "⚠️ ANOMALY DETECTED - Escalation required"
    
    # Update ROADMAP_STATE.json with blocker
    python3 -c "
import json
from pathlib import Path
state_path = Path('$PROJECT_DIR/roadmap/ROADMAP_STATE.json')
state = json.loads(state_path.read_text())
state['active_blockers'] = ['anomaly_detected']
state['last_update'] = '$(date -Iseconds)'
state_path.write_text(json.dumps(state, indent=2))
"
    
    exit 1
fi

echo ""
echo "✅ Daily check complete - All systems nominal"
exit 0

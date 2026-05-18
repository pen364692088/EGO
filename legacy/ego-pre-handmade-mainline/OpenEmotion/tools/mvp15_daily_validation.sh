#!/bin/bash
# MVP15 Daily Validation Cron Script
# Historical archive/reference-only wrapper for funnel tracking and integrity check

set -e

PROJECT_DIR="/home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion"
LOG_DIR="$PROJECT_DIR/artifacts/mvp15/logs"
DATE=$(date +%Y-%m-%d)
DAY_FILE="$PROJECT_DIR/artifacts/mvp15/tracker/current_day.txt"

# Ensure directories exist
mkdir -p "$LOG_DIR"
mkdir -p "$PROJECT_DIR/artifacts/mvp15/tracker"

# Get current day number (increment daily)
if [ -f "$DAY_FILE" ]; then
    CURRENT_DAY=$(cat "$DAY_FILE")
else
    CURRENT_DAY=1
fi

echo "=== MVP15 Daily Validation - Day $CURRENT_DAY ===" >> "$LOG_DIR/validation_$DATE.log"
echo "Timestamp: $(date)" >> "$LOG_DIR/validation_$DATE.log"

cd "$PROJECT_DIR"

# 1. Record funnel metrics
echo "--- Recording funnel metrics ---" >> "$LOG_DIR/validation_$DATE.log"
python tools/mvp15_funnel_tracker.py --day $CURRENT_DAY --record --notes "Automated daily check" >> "$LOG_DIR/validation_$DATE.log" 2>&1

# 2. Run integrity check
echo "--- Running integrity check ---" >> "$LOG_DIR/validation_$DATE.log"
python tools/mvp15_artifact_integrity_check.py --save >> "$LOG_DIR/validation_$DATE.log" 2>&1

# 3. Generate report on Day 3
if [ "$CURRENT_DAY" -ge 3 ]; then
    echo "--- Generating trend report ---" >> "$LOG_DIR/validation_$DATE.log"
    python tools/mvp15_funnel_tracker.py --report >> "$LOG_DIR/validation_$DATE.log" 2>&1
fi

# Increment day counter for next run
NEXT_DAY=$((CURRENT_DAY + 1))
if [ "$NEXT_DAY" -le 3 ]; then
    echo $NEXT_DAY > "$DAY_FILE"
fi

echo "Validation complete for Day $CURRENT_DAY" >> "$LOG_DIR/validation_$DATE.log"
echo "" >> "$LOG_DIR/validation_$DATE.log"

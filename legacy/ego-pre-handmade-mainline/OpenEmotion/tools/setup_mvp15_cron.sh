#!/bin/bash
# Setup MVP15 Validation Cron Job
# Historical archive/reference-only cron wrapper, runs daily at 00:05 local time

CRON_JOB="5 0 * * * /home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion/tools/mvp15_daily_validation.sh"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "mvp15_daily_validation.sh"; then
    echo "Cron job already exists."
    echo "Current MVP15 cron jobs:"
    crontab -l 2>/dev/null | grep "mvp15"
    exit 0
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "✅ Cron job added successfully."
echo ""
echo "Schedule: Daily at 00:05"
echo "Script: /home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion/tools/mvp15_daily_validation.sh"
echo ""
echo "To view: crontab -l"
echo "To remove: crontab -e (delete the line)"
echo ""
echo "Logs will be at:"
echo "  /home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion/artifacts/mvp15/logs/"

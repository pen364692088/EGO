#!/bin/bash
#
# v6k Daily Stability Check
# Runs daily during observation period to verify whitelist governance stability
#
# Observation Period: 2026-03-16 ~ 2026-03-30 (14 days)
# Install: Add to crontab
#   5 4 * * * /path/to/tools/v6k_daily_stability_check.sh >> logs/v6k_stability.log 2>&1
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/logs"
ARTIFACTS_DIR="$PROJECT_ROOT/artifacts/eval/v6k_stability"
DATE=$(date -u +"%Y-%m-%d")
DATE_COMPACT=$(date -u +"%Y%m%d")
TIMESTAMP=$(date -u +"%Y%m%d-%H%M%S")

mkdir -p "$LOG_DIR"
mkdir -p "$ARTIFACTS_DIR"

echo "=== v6k Daily Stability Check ==="
echo "Date: $DATE"
echo "Timestamp: $TIMESTAMP"
echo ""

cd "$PROJECT_ROOT"

# Run daily governance
python3 scripts/run_whitelist_scheduler_once.py --daily --storage artifacts/eval/v6k_stability

# Generate stability report
python3 -c "
import json
from datetime import datetime, date
from pathlib import Path

storage = Path('artifacts/eval/v6k_stability')
date_str = '$DATE'
timestamp_str = '$TIMESTAMP'

# Load latest artifacts
alerts_file = storage / 'whitelist_alerts.json'
runs_file = storage / 'scheduler_runs.json'

# Find latest receipt file (handle timezone differences between local and UTC)
receipt_files = sorted(storage.glob('whitelist_receipt_daily_*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
receipt_file = receipt_files[0] if receipt_files else None

alerts_data = json.loads(alerts_file.read_text()) if alerts_file.exists() else {'alerts': []}
runs_data = json.loads(runs_file.read_text()) if runs_file.exists() else {'runs': []}

alerts = alerts_data.get('alerts', [])
runs = runs_data.get('runs', [])

# Check governance verdict from receipt
receipt_data = {}
if receipt_file and receipt_file.exists():
    receipt_data = json.loads(receipt_file.read_text())

governance_verdict = receipt_data.get('whitelist_verdict', 'unknown')

# Get latest run alerts
if alerts:
    latest_time = max(a.get('triggered_at', '')[:19] for a in alerts)  # Truncate to seconds
    latest_alerts = [a for a in alerts if a.get('triggered_at', '')[:19] == latest_time]
else:
    latest_alerts = []

critical = sum(1 for a in latest_alerts if a.get('severity') == 'critical')
warning = sum(1 for a in latest_alerts if a.get('severity') == 'warning')

# BOOTSTRAP detection: no real observation data yet
is_bootstrap = governance_verdict == 'observe' and critical == 0 and len(latest_alerts) == 0

# Also check if all scenarios are in bootstrap state
receipt_scenarios = receipt_data.get('scenario_metrics', [])
all_bootstrap = all(s.get('scenario_verdict') == 'bootstrap' for s in receipt_scenarios) if receipt_scenarios else False

if is_bootstrap or all_bootstrap:
    verdict = 'BOOTSTRAP'
    stability_score = 1.0  # Bootstrap is expected, not a failure
    bootstrap_note = 'No observation data yet - expected during initial period (does not count toward exit criteria)'
elif critical == 0:
    verdict = 'STABLE'
    stability_score = 1.0
    bootstrap_note = None
elif critical < 3:
    verdict = 'OBSERVE'
    stability_score = 0.5
    bootstrap_note = None
else:
    verdict = 'ACTION_REQUIRED'
    stability_score = 0.0
    bootstrap_note = None

report = {
    'date': date_str,
    'timestamp': datetime.utcnow().isoformat(),
    'observation_day': None,  # Will be calculated
    'scheduler_runs': len(runs),
    'latest_alerts': len(latest_alerts),
    'critical_alerts': critical,
    'warning_alerts': warning,
    'stability_score': stability_score,
    'verdict': verdict,
    'governance_verdict': governance_verdict,
}

if bootstrap_note:
    report['bootstrap_note'] = bootstrap_note

# Calculate observation day
start_date = date(2026, 3, 16)
current_date = date.today()
report['observation_day'] = (current_date - start_date).days + 1

# Save report
report_file = storage / f'stability_check_{timestamp_str}.json'
report_file.write_text(json.dumps(report, indent=2))

print(f'Stability Report:')
print(f'  Observation Day: {report[\"observation_day\"]}/14')
print(f'  Critical Alerts: {critical}')
print(f'  Warning Alerts: {warning}')
print(f'  Stability Score: {report[\"stability_score\"]}')
print(f'  Verdict: {report[\"verdict\"]}')
if bootstrap_note:
    print(f'  Note: {bootstrap_note}')
print(f'  Report: {report_file}')
"

echo ""
echo "=== v6k Daily Stability Check Complete ==="

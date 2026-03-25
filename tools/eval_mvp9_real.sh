#!/bin/bash
# MVP-9 Real Evaluation Script
#
# Uses real emotiond.core.process_event() instead of mock.
#
# Usage:
#   ./tools/eval_mvp9_real.sh [--scenarios-dir DIR] [--output FILE]
#
# Outputs:
#   reports/mvp9_eval_real.json    - Full evaluation report
#   reports/mvp9_failures_real.md  - Human-readable failure analysis

set -e

# Default paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SCENARIOS_DIR="${PROJECT_ROOT}/tests/scenarios/mvp9"
OUTPUT_DIR="${PROJECT_ROOT}/reports"
OUTPUT_JSON="${OUTPUT_DIR}/mvp9_eval_real.json"
OUTPUT_MD="${OUTPUT_DIR}/mvp9_failures_real.md"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --scenarios-dir)
            SCENARIOS_DIR="$2"
            shift 2
            ;;
        --output)
            OUTPUT_JSON="$2"
            OUTPUT_MD="${OUTPUT_JSON%.json}_failures.md"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [--scenarios-dir DIR] [--output FILE]"
            echo ""
            echo "Options:"
            echo "  --scenarios-dir DIR  Directory containing scenario JSON files (default: tests/scenarios/mvp9)"
            echo "  --output FILE        Output JSON file (default: reports/mvp9_eval_real.json)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Ensure output directory exists
mkdir -p "$(dirname "$OUTPUT_JSON")"

# Run evaluation
cd "$PROJECT_ROOT"

echo "MVP-9 Real Evaluation (using process_event)"
echo "============================================"
echo "Scenarios: $SCENARIOS_DIR"
echo "Output:    $OUTPUT_JSON"
echo ""

# Run Python evaluation with real process_event
python3 -c "
import json
import sys
import asyncio
import os
import tempfile
import hashlib
from concurrent.futures import ThreadPoolExecutor

# Set test environment - use temp DB for clean state
os.environ['EMOTIOND_TEST_MODE'] = '1'

sys.path.insert(0, '${PROJECT_ROOT}')

from emotiond.eval_mvp9 import load_scenarios, evaluate_all, generate_failures_markdown
from emotiond.core import process_event, emotion_state
from emotiond.models import Event
from emotiond.self_model import reset_self_model_v0
from emotiond.db import init_db

# Initialize test database
temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
temp_db.close()
os.environ['EMOTIOND_DB_PATH'] = temp_db.name

# Load scenarios
scenarios = load_scenarios('${SCENARIOS_DIR}')
print(f'Loaded {len(scenarios)} scenarios')

if not scenarios:
    print('No scenarios found!')
    os.unlink(temp_db.name)
    sys.exit(1)


def run_async_in_thread(coro):
    '''Run async coroutine in a new thread with its own event loop.'''
    def run_in_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_in_loop)
        return future.result()


def real_process_event(event_dict):
    '''Wrapper to call real async process_event in isolated thread.'''
    # Reset state
    reset_self_model_v0()

    # Create Event object
    event = Event(
        type=event_dict.get('type', 'user_message'),
        actor=event_dict.get('actor', 'user'),
        target=event_dict.get('target', 'agent'),
        text=event_dict.get('text'),
        meta=event_dict.get('meta', {})
    )

    # Run in isolated thread
    return run_async_in_thread(process_event(event))


# Run evaluation
report = evaluate_all(scenarios, real_process_event)

# Add git commit
import subprocess
try:
    report['git_commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd='${PROJECT_ROOT}').decode().strip()[:8]
except:
    report['git_commit'] = 'unknown'

# Mark as real evaluation
report['evaluation_mode'] = 'real_process_event'

# Add params_hash from policy_params_mvp9.json
try:
    with open('${PROJECT_ROOT}/emotiond/policy_params_mvp9.json') as f:
        params = json.load(f)
    canonical = json.dumps(params, sort_keys=True, separators=(',', ':'))
    report['params_hash'] = hashlib.sha256(canonical.encode()).hexdigest()[:16]
except Exception as e:
    report['params_hash'] = 'unknown'
    report['params_hash_error'] = str(e)

# Write JSON report
with open('${OUTPUT_JSON}', 'w') as f:
    json.dump(report, f, indent=2)
print(f'Wrote: ${OUTPUT_JSON}')

# Write markdown report
md = generate_failures_markdown(report)
with open('${OUTPUT_MD}', 'w') as f:
    f.write(md)
print(f'Wrote: ${OUTPUT_MD}')

# Print summary
print('')
print('Results:')
print(f'  Overall score:  {report[\"overall_score\"]:.4f}')
print(f'  Threshold:      {report[\"threshold\"]}')
print(f'  Status:         {\"PASS\" if report[\"passed\"] else \"FAIL\"}')
print(f'  Scenarios:      {report[\"scenarios_passed\"]}/{report[\"total_scenarios\"]} passed')
print(f'  Params hash:    {report.get(\"params_hash\", \"unknown\")}')

# Cleanup
os.unlink(temp_db.name)

# Exit with appropriate code
sys.exit(0 if report['passed'] else 1)
"

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ MVP-9 real evaluation PASSED"
else
    echo "❌ MVP-9 real evaluation FAILED (exit code $EXIT_CODE)"
fi

exit $EXIT_CODE

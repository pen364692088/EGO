#!/bin/bash
# CI Fresh Run - Clean Environment Reproducibility Check
# Simulates CI environment: fresh clone, clean venv, full verification
# Usage: ./scripts/ci_fresh_run.sh [--quick]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
WORKDIR="/tmp/emotiond_fresh_run_$(date +%Y%m%d_%H%M%S)"
QUICK_MODE="${1:-}"  # --quick for faster verification

echo "=== CI Fresh Run ==="
echo "Project: $PROJECT_ROOT"
echo "Workdir: $WORKDIR"
echo "Mode: ${QUICK_MODE:-full}"
echo ""

# 1. Clone fresh copy
echo "[1/5] Cloning fresh copy..."
rm -rf "$WORKDIR"
git clone "$PROJECT_ROOT" "$WORKDIR"
cd "$WORKDIR"

# 2. Create clean venv
echo "[2/5] Creating clean virtual environment..."
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
echo "[3/5] Installing dependencies..."
if command -v uv &> /dev/null; then
    uv pip install -e . --quiet
else
    pip install -e . --quiet
fi

# 4. Run verification
echo "[4/5] Running verification..."
if [ "$QUICK_MODE" == "--quick" ]; then
    echo "Quick mode: Running smoke tests only..."
    PYTHONPATH=. pytest tests/ -q -m "not slow" --tb=short 2>&1 | tee "$WORKDIR/test_output.log"
else
    echo "Full mode: Running all tests..."
    PYTHONPATH=. pytest tests/ -q --tb=short 2>&1 | tee "$WORKDIR/test_output.log"
fi

# 5. Generate report
echo "[5/5] Generating report..."
PASSED=$(grep -oP '\d+(?= passed)' "$WORKDIR/test_output.log" | tail -1)
SKIPPED=$(grep -oP '\d+(?= skipped)' "$WORKDIR/test_output.log" | tail -1)
FAILED=$(grep -oP '\d+(?= failed)' "$WORKDIR/test_output.log" | tail -1 || echo "0")
WARNINGS=$(grep -oP '\d+(?= warnings)' "$WORKDIR/test_output.log" | tail -1 || echo "0")

REPORT_FILE="$PROJECT_ROOT/reports/ci_fresh_run_$(date +%Y%m%d_%H%M%S).json"
cat > "$REPORT_FILE" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "git_commit": "$(git rev-parse HEAD)",
  "mode": "${QUICK_MODE:-full}",
  "results": {
    "passed": $PASSED,
    "skipped": $SKIPPED,
    "failed": $FAILED,
    "warnings": $WARNINGS
  },
  "workdir": "$WORKDIR",
  "status": "$([ "$FAILED" == "0" ] && echo "PASS" || echo "FAIL")"
}
EOF

echo ""
echo "=== Results ==="
echo "Passed:  $PASSED"
echo "Skipped: $SKIPPED"
echo "Failed:  $FAILED"
echo "Warnings: $WARNINGS"
echo "Report:  $REPORT_FILE"

# Cleanup
echo ""
echo "Cleaning up workdir..."
rm -rf "$WORKDIR"

if [ "$FAILED" == "0" ]; then
    echo "✅ Fresh environment verification PASSED"
    exit 0
else
    echo "❌ Fresh environment verification FAILED"
    exit 1
fi

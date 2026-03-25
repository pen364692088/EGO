#!/bin/bash
# MVP-5.1 Audit Check Script
# Usage: bash docs/mvp5.1/run_audit_checks.sh

set -e

echo "=========================================="
echo "MVP-5.1 Audit Check Script"
echo "=========================================="
echo ""

cd /home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion
source .venv/bin/activate

REPORTS_DIR="reports/audit_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$REPORTS_DIR"

echo "[1/8] Running test suite..."
make test 2>&1 | tee "$REPORTS_DIR/test_output.txt" | tail -30
echo ""

echo "[2/8] Checking for token leaks..."
echo "--- Hardcoded tokens check ---" > "$REPORTS_DIR/security_check.txt"
grep -rn "token.*=.*['\"]" emotiond/*.py scripts/*.py 2>/dev/null | grep -v "token_hex\|token_urlsafe\|getenv\|__pycache__" >> "$REPORTS_DIR/security_check.txt" || echo "No obvious hardcoded tokens found" >> "$REPORTS_DIR/security_check.txt"
echo "" >> "$REPORTS_DIR/security_check.txt"
echo "--- Token file permissions ---" >> "$REPORTS_DIR/security_check.txt"
ls -la ~/.config/openemotion/emotiond_token 2>/dev/null >> "$REPORTS_DIR/security_check.txt" || ls -la .emotiond_token 2>/dev/null >> "$REPORTS_DIR/security_check.txt" || echo "No token file found" >> "$REPORTS_DIR/security_check.txt"
cat "$REPORTS_DIR/security_check.txt"
echo ""

echo "[3/8] Checking 3KB injection cap..."
echo "--- max_chars in precision.py ---" > "$REPORTS_DIR/injection_cap_check.txt"
grep -n "max_chars" emotiond/precision.py >> "$REPORTS_DIR/injection_cap_check.txt" || echo "max_chars not found" >> "$REPORTS_DIR/injection_cap_check.txt"
cat "$REPORTS_DIR/injection_cap_check.txt"
echo ""

echo "[4/8] Checking trace rotation..."
echo "--- cleanup_old_budget_trace ---" > "$REPORTS_DIR/trace_rotation_check.txt"
grep -n "cleanup_old_budget_trace\|max_age_days" emotiond/db.py >> "$REPORTS_DIR/trace_rotation_check.txt" || echo "cleanup function not found" >> "$REPORTS_DIR/trace_rotation_check.txt"
echo "" >> "$REPORTS_DIR/trace_rotation_check.txt"
echo "--- Other trace cleanup ---" >> "$REPORTS_DIR/trace_rotation_check.txt"
grep -rn "cleanup_old\|trace.*rotat" emotiond/*.py >> "$REPORTS_DIR/trace_rotation_check.txt" || echo "No rotation triggers found" >> "$REPORTS_DIR/trace_rotation_check.txt"
cat "$REPORTS_DIR/trace_rotation_check.txt"
echo ""

echo "[5/8] Checking eval suite v2 capabilities..."
echo "--- Current eval_suite structure ---" > "$REPORTS_DIR/eval_check.txt"
grep -n "failure_reason\|telemetry\|attribution" scripts/eval_suite_v2.py | head -20 >> "$REPORTS_DIR/eval_check.txt" || echo "No attribution/telemetry found" >> "$REPORTS_DIR/eval_check.txt"
echo "" >> "$REPORTS_DIR/eval_check.txt"
echo "--- Running eval suite ---" >> "$REPORTS_DIR/eval_check.txt"
python scripts/eval_suite_v2.py --output json --output-file "$REPORTS_DIR/eval_output.json" 2>&1 | tail -20 >> "$REPORTS_DIR/eval_check.txt" || echo "Eval suite failed" >> "$REPORTS_DIR/eval_check.txt"
cat "$REPORTS_DIR/eval_check.txt"
echo ""

echo "[6/8] Checking auto_tune capabilities..."
echo "--- Search strategy ---" > "$REPORTS_DIR/autotune_check.txt"
grep -n "stage\|Stage\|latin\|sobol\|coordinate" scripts/auto_tune_v0.py | head -20 >> "$REPORTS_DIR/autotune_check.txt" || echo "No two-stage search found" >> "$REPORTS_DIR/autotune_check.txt"
echo "" >> "$REPORTS_DIR/autotune_check.txt"
echo "--- Fitness function ---" >> "$REPORTS_DIR/autotune_check.txt"
grep -n "fitness\|objective\|pass_count\|false_positive\|interference" scripts/auto_tune_v0.py | head -20 >> "$REPORTS_DIR/autotune_check.txt" || echo "No fitness function details found" >> "$REPORTS_DIR/autotune_check.txt"
cat "$REPORTS_DIR/autotune_check.txt"
echo ""

echo "[7/8] Checking cross-target isolation..."
echo "--- Isolation scenarios ---" > "$REPORTS_DIR/isolation_check.txt"
ls -la scenarios/*isolation*.yaml scenarios/*cross_target*.yaml 2>/dev/null >> "$REPORTS_DIR/isolation_check.txt" || echo "No isolation scenarios found" >> "$REPORTS_DIR/isolation_check.txt"
echo "" >> "$REPORTS_DIR/isolation_check.txt"
echo "--- Interference metrics ---" >> "$REPORTS_DIR/isolation_check.txt"
grep -rn "state_leak_global\|target_state_leak\|shared_self_model" scripts/eval_suite_v2.py emotiond/ 2>/dev/null | head -20 >> "$REPORTS_DIR/isolation_check.txt" || echo "No interference sub-metrics found" >> "$REPORTS_DIR/isolation_check.txt"
cat "$REPORTS_DIR/isolation_check.txt"
echo ""

echo "[8/8] Checking live integration tests..."
echo "--- Live test behavior ---" > "$REPORTS_DIR/live_test_check.txt"
grep -n "skip\|fixture\|live" tests/test_openclaw_integration2.py | head -20 >> "$REPORTS_DIR/live_test_check.txt" || echo "No live test patterns found" >> "$REPORTS_DIR/live_test_check.txt"
echo "" >> "$REPORTS_DIR/live_test_check.txt"
echo "--- conftest fixtures ---" >> "$REPORTS_DIR/live_test_check.txt"
grep -n "def.*fixture\|@pytest.fixture\|emotiond.*start\|port" tests/conftest.py 2>/dev/null | head -20 >> "$REPORTS_DIR/live_test_check.txt" || echo "No fixtures found" >> "$REPORTS_DIR/live_test_check.txt"
cat "$REPORTS_DIR/live_test_check.txt"
echo ""

echo "=========================================="
echo "Audit checks complete!"
echo "Reports saved to: $REPORTS_DIR"
echo "=========================================="
echo ""
echo "Summary:"
echo "--------"
echo "Test output:     $REPORTS_DIR/test_output.txt"
echo "Security check:  $REPORTS_DIR/security_check.txt"
echo "Injection cap:   $REPORTS_DIR/injection_cap_check.txt"
echo "Trace rotation:  $REPORTS_DIR/trace_rotation_check.txt"
echo "Eval check:      $REPORTS_DIR/eval_check.txt"
echo "AutoTune check:  $REPORTS_DIR/autotune_check.txt"
echo "Isolation check: $REPORTS_DIR/isolation_check.txt"
echo "Live test check: $REPORTS_DIR/live_test_check.txt"

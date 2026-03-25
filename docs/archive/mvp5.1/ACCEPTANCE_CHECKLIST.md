# MVP-5.1 Acceptance Checklist

> **Project**: OpenEmotion MVP-5.1 Evolution Loop  
> **Branch**: `feature-emotiond-mvp`  
> **Audit Date**: 2026-02-28  
> **Auditor**: QA SubAgent

---

## Overview

This checklist verifies the MVP-5.1 deliverables (D1-D4) plus security requirements.  
**DO NOT IMPLEMENT** - this is for verification only.

---

## D1: Eval Suite v2.1 (Attribution + Telemetry)

### Requirements
- [ ] Per-scenario structured output (pass/fail + failure_reasons)
- [ ] Failure attribution categories implemented:
  - [ ] `false_high_impact` - 误触发高影响事件
  - [ ] `missed_clarify` - 应澄清却未澄清
  - [ ] `over_clarify` - 过度澄清/反思
  - [ ] `ledger_misfire` - 承诺证据未生效/误判
  - [ ] `state_leak` - 跨 target 状态污染
  - [ ] `precision_saturation` - 权重被阈值夹死几乎不变
  - [ ] `budget_collapse` - 能量预算过快坍塌/恢复过慢
  - [ ] `intrinsic_dead` - expected_info_gain 变化不影响策略
- [ ] Telemetry fields per scenario:
  - [ ] `precision`: w_external/w_internal/w_memory/w_action/w_explore
  - [ ] `allostasis`: energy_budget 曲线
  - [ ] `intrinsic`: expected_info_gain, boredom/curiosity/confusion 强度
  - [ ] `self_model`: 更新次数, values 变化量, identity_stability
  - [ ] `ledger`: 证据强度分布 (promise_confidence, violation_strength)
  - [ ] `decision`: action 分布, meta-cog intents 触发频次
- [ ] Sensitivity smoke test (parameter changes cause observable telemetry changes)
- [ ] >=25 new tests covering attribution, telemetry, sensitivity

### Verification Commands

```bash
# Run eval suite v2.1
cd /home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion
source .venv/bin/activate
python scripts/eval_suite_v2.py --output json --output-file reports/eval_baseline.json

# Check telemetry fields
jq '.scenarios[0].telemetry' reports/eval_baseline.json

# Run sensitivity smoke test
python -m pytest tests/test_eval_sensitivity.py -v 2>/dev/null || echo "Sensitivity tests not yet implemented"

# Count eval-related tests
python -m pytest tests/ -k "eval" --collect-only 2>/dev/null | grep "test session" || echo "Check test collection"
```

### Evidence Files
- `reports/eval_baseline.json` - Must contain per-scenario telemetry
- `reports/eval_baseline.md` - Human-readable summary
- Test output showing >=25 eval-related tests passing

---

## D2: AutoTune v0.1 (Real Search)

### Requirements
- [ ] Two-stage search implemented:
  - [ ] Stage A: Random search + stratified sampling (200-500 candidates)
  - [ ] Stage B: Coordinate descent / local random hill climbing (50-150 iterations on top-k)
- [ ] Multi-objective fitness function with weights:
  - [ ] Scenario pass count (highest weight)
  - [ ] High impact false positive rate (lower is better)
  - [ ] Cross-target interference (lower is better)
  - [ ] Over-clarification rate (upper bound control)
  - [ ] Avg tokens/turn (optional cost control)
- [ ] Reproducible with `--seed`
- [ ] Output files:
  - [ ] `reports/auto_tune_<timestamp>.json` - Top-N candidates with params + metrics
  - [ ] `reports/auto_tune_<timestamp>.md` - Human-readable summary
  - [ ] `best_params_<timestamp>.json` - Loadable parameter file
- [ ] Report includes: git commit hash, parameter space definition, scenario version
- [ ] >=10 tests: reproducibility, schema completeness, error handling
- [ ] At least 1 local run showing metric changes (baseline vs candidate)

### Verification Commands

```bash
# Check auto_tune script exists and has search functionality
grep -n "stage\|Stage\|latin\|sobol\|coordinate" scripts/auto_tune_v0.py | head -20

# List tunable parameters
python scripts/auto_tune_v0.py --list-params

# Run quick auto-tune (small candidate count for verification)
python scripts/auto_tune_v0.py --perturbations 5 --seed 42 --output reports/

# Verify output files exist
ls -la reports/auto_tune_*.json reports/auto_tune_*.md 2>/dev/null || echo "Reports not yet generated"

# Check best_params file
ls -la best_params_*.json 2>/dev/null || echo "Best params not yet generated"

# Run auto-tune tests
python -m pytest tests/test_auto_tune_v0.py -v
```

### Evidence Files
- `reports/auto_tune_*.json` - Must contain top-N candidates
- `reports/auto_tune_*.md` - Must explain why best candidate was selected
- `best_params_*.json` - Must be loadable by eval_suite

---

## D3: Cross-target Interference (Diagnose & Gate)

### Requirements
- [ ] Cross-target interference decomposed into sub-metrics:
  - [ ] `state_leak_global_to_target`
  - [ ] `target_state_leak_between_targets`
  - [ ] `shared_self_model_leak`
- [ ] Telemetry outputs contribution of each sub-metric
- [ ] New YAML scenario: A/B target interleaving (>=30 turns)
  - [ ] A's ledger promise must not affect B's betrayal判定
  - [ ] A's bond changes must not change B's bond
  - [ ] Global mood/energy changes are allowed and correctly distinguished from leaks
- [ ] If real leaks exist:
  - [ ] State fields correctly attributed (per-target vs global)
  - [ ] Regression tests added
  - [ ] Cross_target_interference metric drops >=20% OR documented explanation

### Verification Commands

```bash
# Check for cross-target isolation scenario
ls -la scenarios/*isolation*.yaml scenarios/*cross_target*.yaml 2>/dev/null || echo "Isolation scenario not yet created"

# Check multi_target_isolation.yaml exists
cat scenarios/multi_target_isolation.yaml | head -50

# Run cross-target scenario
python scripts/eval_suite_v2.py --scenarios multi_target_isolation.yaml --output json

# Check telemetry for interference metrics
jq '.scenarios[].metrics.cross_target_interference' reports/eval_*.json 2>/dev/null || echo "Check eval output"

# Run isolation tests
python -m pytest tests/ -k "isolation" -v 2>/dev/null || echo "Isolation tests not yet implemented"
```

### Evidence Files
- `scenarios/cross_target_isolation.yaml` (or similar name)
- Eval report showing interference sub-metrics
- Test output showing isolation scenario passes

---

## D4: Live Integration Tests (Stop Skipping)

### Requirements
- [ ] Integration tests no longer skip by default when emotiond is not running
- [ ] Either:
  - [ ] **Option A (Recommended)**: Test fixture auto-starts emotiond on random port
    - [ ] `--no-live` flag to disable
    - [ ] Waits for /health before running
    - [ ] Cleans up after tests
  - [ ] **Option B**: Separate CI job for live tests
    - [ ] Unit tests don't skip live tests
    - [ ] Live tests in dedicated job with stable emotiond instance
- [ ] >=8 tests covering: start/stop, port conflict, health timeout errors

### Verification Commands

```bash
# Check current test behavior (should NOT skip when emotiond is down)
python -m pytest tests/test_openclaw_integration2.py -v 2>&1 | grep -i "skip\|SKIPPED" | head -10

# Check for live test fixture
grep -rn "fixture\|live\|emotiond.*start\|port" tests/conftest.py | head -20

# Check Makefile for integration test target
cat Makefile | grep -A5 "integration"

# Run live integration tests
make test-integration2-live 2>&1 | tail -30
```

### Evidence Files
- Test output showing live tests run (not skipped)
- Fixture code in `tests/conftest.py` or similar

---

## Security Checks (Critical)

### S1: No Token Leaks
- [ ] No hardcoded tokens in source code
- [ ] Token files have 0600 permissions
- [ ] Tokens not logged in plain text

```bash
# Check for hardcoded tokens
grep -rn "token.*=.*['\"]" emotiond/*.py scripts/*.py | grep -v "token_hex\|token_urlsafe\|getenv\|__pycache__" | head -20

# Check token file permissions
ls -la ~/.config/openemotion/emotiond_token 2>/dev/null || ls -la .emotiond_token 2>/dev/null
```

### S2: 3KB Injection Cap Intact
- [ ] `max_chars` parameter in `format_precision_summary()` defaults to 200
- [ ] No injection vectors exceed 3KB

```bash
# Verify 3KB cap in precision.py
grep -n "max_chars\|3KB\|3000" emotiond/precision.py

# Check all format/summary functions have size limits
grep -rn "max_chars\|max_len\|max_size" emotiond/*.py | head -20
```

### S3: Trace Rotation Intact
- [ ] `cleanup_old_budget_trace()` exists and is callable
- [ ] Default retention: 7 days (`max_age_days=7`)
- [ ] Rotation triggered periodically

```bash
# Verify trace cleanup function
grep -n "cleanup_old_budget_trace\|max_age_days" emotiond/db.py

# Check for rotation trigger in tick loop or similar
grep -rn "cleanup_old\|trace.*rotat\|budget_trace" emotiond/*.py | head -20
```

---

## Final Verification Commands

### Complete Test Suite
```bash
cd /home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion
source .venv/bin/activate

# Run all tests
make test 2>&1 | tail -50

# Verify 0 failures
make test 2>&1 | grep -E "passed|failed|error" | tail -5
```

### Eval Suite v2.1 Baseline
```bash
# Run full eval suite
python scripts/eval_suite_v2.py --output json --output-file reports/eval_v2_1_final.json

# Verify telemetry exists
jq '.scenarios[0] | keys' reports/eval_v2_1_final.json
```

### AutoTune v0.1 Run (200 candidates)
```bash
# Full search run (may take time)
python scripts/auto_tune_v0.py --perturbations 200 --seed 42 --output reports/

# Verify output
ls -la reports/auto_tune_*.json best_params_*.json
```

---

## Sign-off

| Check | Status | Notes |
|-------|--------|-------|
| D1: Eval v2.1 | [ ] | Pending |
| D2: AutoTune v0.1 | [ ] | Pending |
| D3: Cross-target Isolation | [ ] | Pending |
| D4: Live Tests | [ ] | Pending |
| S1: No Token Leaks | [ ] | Pending |
| S2: 3KB Cap | [ ] | Pending |
| S3: Trace Rotation | [ ] | Pending |
| make test (0 fail) | [ ] | Pending |

**Final Status**: [ ] NOT READY FOR RELEASE

---

*Generated by MVP-5.1 QA Auditor*

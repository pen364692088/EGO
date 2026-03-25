# MVP-5.1 QA Documentation

This directory contains QA and audit documentation for the MVP-5.1 Evolution Loop deliverables.

## Files

| File | Purpose |
|------|---------|
| `ACCEPTANCE_CHECKLIST.md` | Complete acceptance criteria for D1-D4 + security |
| `AUDIT_TEMPLATE.md` | Template for final audit report |
| `QA_BASELINE_REPORT.md` | Baseline state BEFORE D1-D4 implementation |
| `run_audit_checks.sh` | Automated script to run all audit checks |
| `README.md` | This file |

## Quick Start

### Run All Audit Checks

```bash
cd /home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion
bash docs/mvp5.1/run_audit_checks.sh
```

### Manual Security Verification

```bash
# S1: Token leaks
grep -rn "token.*=.*['\"]" emotiond/*.py scripts/*.py | grep -v "token_hex\|getenv"

# S2: Token permissions
ls -la .emotiond_token

# S3: 3KB injection cap
grep -n "max_chars" emotiond/precision.py

# S4: Trace rotation
grep -n "cleanup_old_budget_trace" emotiond/db.py
```

### Verify D1-D4 Implementation

See `ACCEPTANCE_CHECKLIST.md` for detailed verification commands for each deliverable.

## Deliverables Overview

### D1: Eval Suite v2.1
- Failure attribution (8 categories)
- Telemetry fields (17 metrics)
- Sensitivity smoke test
- 25+ new tests

### D2: AutoTune v0.1
- Two-stage search (global + local)
- Multi-objective fitness
- Top-N candidate tracking
- Reproducible with `--seed`

### D3: Cross-target Isolation
- 3 interference sub-metrics
- Isolation scenario (30+ turns)
- Telemetry breakdown
- 20% reduction target

### D4: Live Integration Tests
- Auto-start fixture
- `--no-live` flag
- No skipping by default
- 8+ fixture tests

## Security Requirements

All security checks must pass:
- ✅ No token leaks
- ✅ 0600 token file permissions
- ✅ 3KB injection cap intact
- ✅ Trace rotation (7-day default)

## Final Verification

```bash
# Run all tests
make test  # Must be 0 failures

# Run eval suite v2.1
python scripts/eval_suite_v2.py --output json

# Run auto-tune v0.1 (200 candidates)
python scripts/auto_tune_v0.py --perturbations 200 --seed 42

# Run audit script
bash docs/mvp5.1/run_audit_checks.sh
```

## Commit Message

When ready to commit:

```bash
chore(mvp5.1): docs + final audit report
```

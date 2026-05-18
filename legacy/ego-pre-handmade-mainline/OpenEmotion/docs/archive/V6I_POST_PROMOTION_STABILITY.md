# V6I: Post-Promotion Stability + Guard Drill

> Status: Implemented
> Date: 2026-03-16
> Capability Owner: OpenEmotion

## Overview

v6i implements post-promotion observation and stability verification for `complex_semantic_reasoning`:

1. **Observation Window** - Accumulate real samples after promotion
2. **Stability Verdict** - Determine if scenario remains stable
3. **Guard Drills** - Test demotion/rollback mechanisms
4. **Observation Receipts** - Audit trail for each round

## Problem Statement

v6h answered:
> Can this scenario be promoted to production whitelist?

v6i answers:
> After promotion, can it remain stable in production whitelist?

## Solution

### Post-Promotion Stability Evaluator

`emotiond/memory/embedding/post_promotion_stability.py`

Evaluates stability and outputs one of four verdicts:
- `stable_keep_promoted` - All criteria met
- `keep_under_observation` - Data insufficient or thresholds borderline
- `demote_to_pilot` - Significant issues detected
- `rollback_to_tfidf_only` - Critical issues detected

### Guard Drill Runner

`emotiond/memory/embedding/guard_drill.py`

Runs controlled drills to verify guard mechanisms:
- `fallback_rate_overflow` - Tests demotion trigger
- `wrong_user_guard_trigger` - Tests rollback trigger
- `provider_health_degradation` - Tests health monitoring
- `latency_spike` - Tests latency alerts
- `quality_signal_negative` - Tests quality signal alerts

## Observation Requirements

### Minimum for Stable Verdict
- `request_count >= 50`
- `observation_rounds >= 3`

### Stability Thresholds
- `wrong_user_guard_trigger_count = 0`
- `fallback_rate <= 5%`
- `provider_health_rate >= 98%`
- `p95_latency_ms <= 100`
- `quality_gain_signal > 0`

### Demotion Thresholds
- `fallback_rate > 10%`
- `provider_health_rate < 95%`

### Rollback Thresholds
- `wrong_user_guard_trigger_count > 0`

## Usage

### Run Observation

```bash
python scripts/run_post_promotion_observation.py \
  --scenario complex_semantic_reasoning \
  --rounds 3 \
  --samples 50
```

### Run Guard Drill

```bash
python scripts/run_guard_drill.py \
  --scenario complex_semantic_reasoning
```

### Evaluate Stability

```python
from emotiond.memory.embedding.post_promotion_stability import (
    PostPromotionStabilityEvaluator,
    StabilityVerdict,
)

evaluator = PostPromotionStabilityEvaluator(registry, guard)

# Record observations
observations = [{"success": True, "latency_ms": 65, "quality_signal": 0.4}]
receipt = evaluator.record_observation_round("complex_semantic_reasoning", observations)

# Evaluate stability
evaluation = evaluator.evaluate_stability("complex_semantic_reasoning")

if evaluation.verdict == StabilityVerdict.STABLE_KEEP_PROMOTED:
    print("Scenario is stable!")
```

## Artifacts

- `artifacts/eval/v6i/post_promotion_stability_report.json` - Stability evaluation
- `artifacts/eval/v6i/round_receipts.json` - Observation round receipts
- `artifacts/eval/v6i/guard_drill_report.json` - Drill results

## Verdict Decision Tree

```
                  promoted
                     │
         ┌───────────┼───────────┐
         │           │           │
    wrong_user   fallback>10%  data
    guard>0       or health<95% insufficient
         │           │           │
         ↓           ↓           ↓
     ROLLBACK     DEMOTE      KEEP_UNDER
                                  │
                          ┌───────┼───────┐
                          │       │       │
                      stable  issues   issues
                      (all) (5-10%) (minor)
                          │       │       │
                          ↓       ↓       ↓
                       STABLE  KEEP   KEEP_UNDER
```

## Tests

```bash
# Unit tests
pytest tests/embedding/test_post_promotion_stability.py
pytest tests/embedding/test_guard_drill.py

# E2E tests
pytest tests/e2e/test_v6i_post_promotion_stability.py
```

## Current Status

`complex_semantic_reasoning`:
- Promotion date: 2026-03-16
- Observation window: 14 days / 10 rounds
- Current samples: 0 (observation starting)

## Relation to v6a~v6h

| Version | Capability |
|---------|------------|
| v6a | A/B evaluation framework |
| v6b | High-quality retrieval mode |
| v6c | Admission governance |
| v6d | Limited rollout whitelist |
| v6e | Scope expansion governance |
| v6f | Candidate scenario pilot |
| v6g | Quality signal provenance |
| v6h | Production whitelist promotion |
| **v6i** | **Post-promotion stability + guard drill** |

## Key Invariants

1. **Real Samples** - Observation must use real production data
2. **Minimum Thresholds** - 50 requests + 3 rounds for stable verdict
3. **Guard Verification** - Drills prove demotion/rollback work
4. **Audit Trail** - Every round generates receipt
5. **No Auto-Promote** - Human decides final stability verdict

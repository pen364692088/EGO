# V6H: Production Whitelist Promotion + Post-Promotion Observation

> Status: Implemented
> Date: 2026-03-16
> Capability Owner: OpenEmotion

## Overview

v6h implements the production whitelist promotion workflow for `complex_semantic_reasoning`, enabling:

1. **Formal Promotion** - Structured promotion from pilot to production whitelist
2. **Promotion Receipt** - Auditable record of promotion decision
3. **Post-Promotion Observation** - Continued monitoring after promotion
4. **Auto-Demotion/Rollback** - Automatic downgrade when thresholds violated

## Problem Statement

v6g answered:
> Does this candidate scenario deserve to be promoted?

v6h answers:
> After promotion, how do we ensure it remains stable and can be safely rolled back?

## Solution

### Production Whitelist Registry

`emotiond/memory/embedding/production_whitelist.py`

Manages three tiers of scenarios:
- `pilot_candidate` - Eligible for pilot testing
- `pilot_active` - Currently in pilot
- `promoted` - In production whitelist
- `demoted` - Removed from production whitelist
- `rolled_back` - Emergency rollback

### Post-Promotion Guard

`emotiond/memory/embedding/post_promotion_guard.py`

Monitors promoted scenarios and triggers actions:
- `NONE` - No action needed
- `ALERT` - Warning condition detected
- `DEMOTE` - Demote to pilot status
- `ROLLBACK` - Emergency removal from whitelist

## Promotion Flow

```
pilot_candidate
      ↓
pilot_active (v6f evaluation)
      ↓
promoted (v6h promotion)
      ↓
post-promotion observation (v6h guard)
      ↓
  ┌───┴───┐
stable   degrade
  │         │
  ↓         ↓
remain   demote/rollback
```

## Thresholds

### Must Maintain (demotion triggers if exceeded)
- `wrong_user_guard_trigger_count` ≤ 0
- `fallback_rate` ≤ 10%
- `provider_health_rate` ≥ 95%
- `p95_latency_ms` ≤ 300

### Warning (alert triggers)
- `fallback_rate` > 5%
- `p95_latency_ms` > 100ms
- `provider_health_rate` < 98%

### Rollback Triggers
- `wrong_user_guard_trigger_count` > 0 (immediate rollback)
- `fallback_rate` > 15% with `provider_health_rate` < 90%

## Usage

### Promote a Scenario

```bash
python scripts/promote_candidate_scenario.py \
  --scenario complex_semantic_reasoning \
  --commit <git-commit> \
  --observation-days 14 \
  --observation-rounds 10
```

### Evaluate Post-Promotion Stability

```bash
python scripts/eval_post_promotion_stability.py \
  --scenario complex_semantic_reasoning \
  --rounds 5 \
  --samples-per-round 20
```

## Artifacts

- `artifacts/eval/v6h/promotion_receipt.json` - Promotion record
- `artifacts/eval/v6h/post_promotion_report.json` - Observation report
- `artifacts/eval/v6h/whitelist_state.json` - Current whitelist state
- `artifacts/eval/v6h/guard_decisions.json` - Guard action history

## Promotion Receipt Schema

```json
{
  "promoted_scenario": "complex_semantic_reasoning",
  "previous_state": "pilot_active",
  "new_state": "promoted",
  "approval_basis": "Pilot evaluation: 40 requests, 0% fallback, verdict=promote",
  "promotion_commit": "abc123",
  "promotion_timestamp": 1234567890.0,
  "promotion_datetime": "2026-03-16T17:00:00",
  "observation_window_days": 14,
  "observation_window_rounds": 10,
  "rollback_thresholds": {
    "max_wrong_user_guard_trigger_count": 0,
    "max_fallback_rate": 0.10,
    "min_provider_health_rate": 0.95,
    "max_p95_latency_ms": 300,
    "min_avg_quality_signal": 0.0
  }
}
```

## Current Production Whitelist

After v6h promotion:

1. `memory_search_hard_query` (v6d)
2. `narrative_recall_ambiguous_query` (v6d)
3. `long_context_semantic_lookup` (v6d)
4. `complex_semantic_reasoning` (v6h)

## Tests

```bash
# Unit tests
pytest tests/embedding/test_production_whitelist.py
pytest tests/embedding/test_post_promotion_guard.py

# E2E tests
pytest tests/e2e/test_v6h_production_promotion.py
```

## Key Invariants

1. **Single Truth Chain** - Only one production whitelist at a time
2. **Explicit Approval** - Promotion requires explicit approval_basis
3. **Audit Trail** - All promotions generate receipts
4. **Observable** - Post-promotion metrics tracked
5. **Reversible** - Demotion and rollback always possible

## Relation to v6a~v6g

| Version | Capability |
|---------|------------|
| v6a | A/B evaluation framework |
| v6b | High-quality retrieval mode |
| v6c | Admission governance |
| v6d | Limited rollout whitelist |
| v6e | Scope expansion governance |
| v6f | Candidate scenario pilot |
| v6g | Quality signal provenance |
| **v6h** | **Production whitelist promotion** |

## Future Work

- v6i: Multiple scenario promotion
- v6j: Auto-promotion based on pilot metrics
- v6k: Cross-scenario correlation analysis

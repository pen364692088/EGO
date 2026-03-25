# V6F Candidate Scenario Pilot + Quality Signal Calibration

**Version**: v6f
**Date**: 2026-03-16
**Status**: COMPLETED

---

## Executive Summary

Implemented pilot system for candidate scenarios with quality signal calibration:
- **Pilot registry** - Separate tracking for pilot scenarios
- **Quality signal calculator** - Multiple signal sources (shadow compare, downstream proxy, offline replay)
- **Pilot evaluator** - Promotion/keep/rollback decisions based on real signals

**Key Fix**: Quality signal is now **interpretable** and must be positive for promotion.

---

## Pilot Scope

### Candidate Scenario
- `complex_semantic_reasoning` (only one in v6f)

### Production Whitelist (Unchanged)
- `memory_search_hard_query`
- `narrative_recall_ambiguous_query`
- `long_context_semantic_lookup`

---

## Quality Signal Sources

| Source | Method | Interpretable | Use Case |
|--------|--------|---------------|----------|
| `shadow_compare` | Compare Ollama vs TF-IDF top-k | ✅ Yes | Production runs |
| `downstream_proxy` | Acceptance/rerank consistency | ✅ Yes | When shadow not possible |
| `offline_replay` | Labeled sample evaluation | ✅ Yes | Ground truth |
| `placeholder` | Default value | ❌ No | Signal not computed |

---

## Promotion Thresholds

| Metric | Threshold |
|--------|-----------|
| pilot_sample_size | ≥ 30 |
| pilot_rounds | ≥ 2 |
| fallback_rate | ≤ 5% |
| wrong_user_guard_trigger | = 0 |
| provider_health_rate | ≥ 98% |
| p95_latency_ms | ≤ 100ms |
| quality_signal | > 0 (interpretable) |

---

## Rollback Triggers

| Metric | Threshold |
|--------|-----------|
| fallback_rate | > 10% |
| p95_latency_ms | > 300ms |
| provider_health_rate | < 95% |

---

## Pilot Results

```
Scenario: complex_semantic_reasoning
  Pilot sample size: 40
  Pilot rounds: 2
  Fallback rate: 0.0%
  P95 latency: 78.03ms
  Provider health: 100.0%
  Wrong user triggers: 0
  Avg quality signal: 0.4000

Verdict: PROMOTE

Quality Signal:
  Value: 0.4000
  Source: shadow_compare
  Interpretable: True
  Confidence: 70%
```

---

## Quality Signal Calibration Fix

**v6e Problem**: `quality_gain_signal = 0.0` in expansion report, but verdict was `expand_one_more_scenario`

**v6f Fix**:
1. Quality signal is now **required** to be interpretable for promotion
2. Placeholder signals (`0.0` with no computation) are explicitly **not interpretable**
3. Promotion blocked if signal not interpretable

**Code Impact**:
```python
# v6e: Placeholder signal allowed promotion
if signal_value > 0:  # 0.0 > 0 is False, but 0 >= 0 could pass

# v6f: Interpretable check added
if not quality_signal.interpretable:
    blockers.append("Quality signal not interpretable")
```

---

## Files Created

| File | Purpose |
|------|---------|
| `emotiond/memory/embedding/pilot_registry.py` | Pilot scenario management |
| `emotiond/memory/embedding/quality_signal.py` | Quality signal computation |
| `emotiond/memory/embedding/pilot_evaluator.py` | Pilot evaluation logic |
| `scripts/run_candidate_scenario_pilot.py` | Pilot runner |
| `tests/embedding/test_quality_signal.py` | Signal tests |
| `tests/embedding/test_pilot_registry.py` | Registry tests |
| `tests/e2e/test_v6f_candidate_scenario_pilot.py` | E2E tests |
| `docs/V6F_PILOT_PROMOTION_GOVERNANCE.md` | This document |

---

## Test Results

```
tests/embedding/test_quality_signal.py: 19 passed
tests/embedding/test_pilot_registry.py: 17 passed
tests/e2e/test_v6f_candidate_scenario_pilot.py: 15 passed

Total: 51 passed
```

---

## Capability Ownership

**Owner**: OpenEmotion

- Pilot registry: `emotiond/memory/embedding/pilot_registry.py`
- Quality signal: `emotiond/memory/embedding/quality_signal.py`
- Pilot evaluator: `emotiond/memory/embedding/pilot_evaluator.py`

**NOT in**:
- EgoCore
- Host/宿主层

---

## What Was NOT Done

Per task constraints:
- ❌ Did NOT add candidate to permanent whitelist
- ❌ Did NOT activate auto mode
- ❌ Did NOT change default provider
- ❌ Did NOT add second candidate scenario

---

## v6e → v6f Transition

| Issue | v6e | v6f |
|-------|-----|-----|
| quality_gain_signal | 0.0 (placeholder) | Computed, interpretable |
| Promotion decision | Based on sample size only | Requires interpretable signal |
| Whitelist expansion | Automatic after samples | Requires pilot evaluation |

---

## Next Steps

1. **Approve promotion**: If metrics remain stable, add `complex_semantic_reasoning` to whitelist
2. **Extended pilot**: Run longer if more data needed
3. **Second candidate**: Consider `multi_turn_context_recall` for next pilot
4. **Production integration**: Wire pilot system into retrieval pipeline

---

## Environment

- Host Ollama URL: `http://192.168.79.1:11434/v1`
- Model: `mxbai-embed-large`
- Vector dimensions: 1024
- Test date: 2026-03-16

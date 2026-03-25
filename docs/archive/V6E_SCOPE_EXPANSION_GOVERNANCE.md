# V6E Scope Expansion Governance

**Version**: v6e
**Date**: 2026-03-16
**Status**: COMPLETED

---

## Executive Summary

Established governance for scope expansion decisions:
- **Observation window** with multi-round data collection
- **Expansion thresholds** for sample size, quality, latency, health
- **Verdict logic** for keep_same_scope / expand / rollback
- **Fixed whitelist** - unchanged in v6e

---

## Observation Window

| Parameter | Value |
|-----------|-------|
| min_total_sample_size | 60 |
| min_sample_size_per_scenario | 15 |
| min_observation_rounds | 3 |
| max_fallback_rate | 5% |
| max_wrong_user_guard_trigger | 0 |
| max_p95_latency_ms | 100ms |
| min_provider_health_rate | 98% |
| min_quality_gain | 10% |

---

## Fixed Whitelist (Unchanged)

- `memory_search_hard_query`
- `narrative_recall_ambiguous_query`
- `long_context_semantic_lookup`

---

## Expansion Verdicts

| Verdict | Condition |
|---------|-----------|
| `keep_same_scope` | Expansion criteria not met |
| `expand_one_more_scenario` | All criteria met |
| `shrink_or_rollback` | Critical issues detected |

---

## Rollback Triggers

| Condition | Threshold |
|-----------|-----------|
| fallback_rate | > 10% |
| p95_latency | > 300ms |
| provider_health_rate | < 95% |

---

## Observation Results

```
Observation Window:
  Total sample size: 225
  Rounds observed: 3
  Scenarios covered: 3

Scenario Metrics:
  memory_search_hard_query:
    Requests: 114
    Fallback rate: 0.0%
    P95 latency: 28.21ms
  narrative_recall_ambiguous_query:
    Requests: 75
    Fallback rate: 0.0%
    P95 latency: 27.87ms
  long_context_semantic_lookup:
    Requests: 36
    Fallback rate: 0.0%
    P95 latency: 28.17ms

Expansion Verdict: EXPAND_ONE_MORE_SCENARIO
```

---

## Files Created

| File | Purpose |
|------|---------|
| `emotiond/memory/embedding/observation_window.py` | Multi-round observation |
| `emotiond/memory/embedding/expansion_governance.py` | Expansion decision logic |
| `scripts/run_scope_expansion_observation.py` | Observation runner |
| `tests/embedding/test_expansion_governance.py` | Governance tests |
| `tests/e2e/test_v6e_scope_expansion.py` | E2E tests |
| `docs/V6E_SCOPE_EXPANSION_GOVERNANCE.md` | This document |

---

## Test Results

```
tests/embedding/test_expansion_governance.py: 16 passed
tests/e2e/test_v6e_scope_expansion.py: 10 passed

Total: 26 passed
```

---

## Capability Ownership

**Owner**: OpenEmotion

- Observation window: `emotiond/memory/embedding/observation_window.py`
- Expansion governance: `emotiond/memory/embedding/expansion_governance.py`

**NOT in**:
- EgoCore
- Host/宿主层

---

## What Was NOT Done

Per task constraints:
- ❌ Did NOT add new scenarios to whitelist
- ❌ Did NOT enable auto mode
- ❌ Did NOT change default provider
- ❌ Did NOT modify existing rollout rules

---

## Next Steps

1. **Evaluate expansion**: If verdict allows, consider adding one candidate scenario
2. **Extended observation**: Continue monitoring for stability
3. **Candidate scenarios**: `complex_semantic_reasoning`, `multi_turn_context_recall`
4. **Integration**: Wire into production decision flow

---

## Environment

- Host Ollama URL: `http://192.168.79.1:11434/v1`
- Model: `mxbai-embed-large`
- Vector dimensions: 1024
- Test date: 2026-03-16

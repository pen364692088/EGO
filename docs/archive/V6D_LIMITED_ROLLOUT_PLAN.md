# V6D Limited Rollout Plan for High-Quality Retrieval Mode

**Version**: v6d
**Date**: 2026-03-16
**Status**: COMPLETED

---

## Executive Summary

Implemented limited rollout mechanism for high-quality retrieval mode with:
- **Scenario whitelist** - only specific scenarios can use Ollama
- **Non-whitelist enforcement** - all other scenarios must use TF-IDF
- **Per-scenario observation** - track metrics by scenario
- **Rollout decision** - expand_same_scope / expand_more_scenarios / shrink_or_rollback

---

## Scenario Definition

### Whitelist Scenarios (Eligible for Ollama)

| Scenario | Trigger | Rationale |
|----------|---------|-----------|
| `memory_search_hard_query` | "I remember", "I think", "looking for" | Keywords unstable, TF-IDF may miss |
| `narrative_recall_ambiguous_query` | "something like", "kind of" | Fuzzy description, needs semantic match |
| `long_context_semantic_lookup` | Query > 100 chars | Long text, semantic matching helps |

### Non-Rollout Scenarios (Always TF-IDF)

| Scenario | Trigger | Rationale |
|----------|---------|-----------|
| `keyword_exact_match` | Quoted search, "exact" keyword | Exact match preferred |
| `low_latency_path` | "real-time" action, low_latency flag | Latency critical |
| `multi_user_sensitive` | "shared" action, multi_user context | Isolation sensitive |
| `default` | No specific indicators | Safe default |

---

## Configuration

```json
{
  "high_quality_rollout": {
    "enabled": true,
    "default_mode": "tfidf",
    "allowed_scenarios": [
      "memory_search_hard_query",
      "narrative_recall_ambiguous_query",
      "long_context_semantic_lookup"
    ],
    "rollout_percentage": 100,
    "fallback_to_tfidf": true,
    "shadow_compare_enabled": false
  }
}
```

---

## Observation Results

```
Metrics:
  Whitelist requests: 12
  Non-whitelist requests: 12
  Ollama success: 12
  Fallback count: 0
  TF-IDF count: 12
  P95 latency: 26.98ms
  Fallback rate: 0.0%

Verdict: expand_same_scope
```

### Whitelist Verification

- **Whitelist → Ollama**: 12/12 (100%)
- **Non-whitelist → TF-IDF**: 12/12 (100%)

---

## Files Created

| File | Purpose |
|------|---------|
| `emotiond/memory/embedding/scenario_router.py` | Scenario identification and routing |
| `emotiond/memory/embedding/rollout.py` | Rollout policy and execution |
| `scripts/run_limited_rollout_observation.py` | Observation runner |
| `tests/embedding/test_rollout_policy.py` | Policy tests |
| `tests/embedding/test_scenario_router.py` | Router tests |
| `tests/e2e/test_v6d_limited_rollout.py` | E2E tests |
| `docs/V6D_LIMITED_ROLLOUT_PLAN.md` | This document |
| `artifacts/eval/v6d/rollout_report.json` | Rollout report |

---

## Test Results

```
tests/embedding/test_rollout_policy.py: 22 passed
tests/embedding/test_scenario_router.py: 17 passed
tests/e2e/test_v6d_limited_rollout.py: 12 passed

Total: 51 passed
```

---

## Verdict Logic

| Condition | Verdict |
|-----------|---------|
| wrong_user_guard_trigger > 0 | `shrink_or_rollback` |
| fallback_rate > 10% | `shrink_or_rollback` |
| p95_latency > 300ms | `shrink_or_rollback` |
| whitelist_requests < 20 | `expand_same_scope` |
| All stable | `expand_same_scope` |

---

## Capability Ownership

**Owner**: OpenEmotion

- Scenario router: `emotiond/memory/embedding/scenario_router.py`
- Rollout policy: `emotiond/memory/embedding/rollout.py`

**NOT in**:
- EgoCore
- Host/宿主层

---

## What Was NOT Done

Per task constraints:
- ❌ Did NOT change default to Ollama
- ❌ Did NOT enable auto mode
- ❌ Did NOT allow all scenarios to use Ollama
- ❌ Did NOT add new providers

---

## Next Steps

1. **Extend observation**: Run for longer periods with real traffic
2. **Expand scenarios**: If metrics stay stable, add more scenarios to whitelist
3. **Shadow comparison**: Enable shadow mode for quality comparison
4. **Integration**: Wire into production retrieval pipeline

---

## Environment

- Host Ollama URL: `http://192.168.79.1:11434/v1`
- Model: `mxbai-embed-large`
- Vector dimensions: 1024
- Test date: 2026-03-16

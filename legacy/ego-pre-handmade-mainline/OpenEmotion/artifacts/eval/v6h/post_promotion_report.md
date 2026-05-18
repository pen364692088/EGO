# v6h Post-Promotion Report

## Promotion Summary

**Scenario:** `complex_semantic_reasoning`

**Previous State:** `pilot_active`

**New State:** `promoted` (production whitelist)

**Approval Basis:**
- 40 pilot requests
- 0% fallback rate
- 78.8ms p95 latency
- 0 wrong_user_guard triggers
- 100% provider health
- 0.40 quality signal

**Observation Window:** 14 days / 10 rounds

## Current Production Whitelist

1. `memory_search_hard_query` (v6d)
2. `narrative_recall_ambiguous_query` (v6d)
3. `long_context_semantic_lookup` (v6d)
4. `complex_semantic_reasoning` (v6h) ← **NEW**

## Rollback Thresholds

| Metric | Threshold | Action |
|--------|-----------|--------|
| wrong_user_guard_trigger_count | > 0 | ROLLBACK |
| fallback_rate | > 10% | DEMOTE |
| provider_health_rate | < 95% | DEMOTE |
| p95_latency_ms | > 300ms | DEMOTE |

## Warning Thresholds (Alert Only)

| Metric | Threshold |
|--------|-----------|
| fallback_rate | > 5% |
| p95_latency_ms | > 100ms |
| provider_health_rate | < 98% |

## Files Delivered

### Code
- `emotiond/memory/embedding/production_whitelist.py`
- `emotiond/memory/embedding/post_promotion_guard.py`

### Scripts
- `scripts/promote_candidate_scenario.py`
- `scripts/eval_post_promotion_stability.py`

### Tests
- `tests/embedding/test_production_whitelist.py`
- `tests/embedding/test_post_promotion_guard.py`
- `tests/e2e/test_v6h_production_promotion.py`

### Documentation
- `docs/V6H_PRODUCTION_WHITELIST_PROMOTION.md`

### Artifacts
- `artifacts/eval/v6h/promotion_receipt.json`
- `artifacts/eval/v6h/whitelist_state.json`

## Next Steps

1. Run `eval_post_promotion_stability.py` periodically during observation window
2. Monitor `post_promotion_report.json` for anomalies
3. If stable after 14 days, consider promotion permanent
4. If unstable, trigger demotion via guard thresholds

---

**Generated:** 2026-03-16
**Commit:** v6h-3925372

# V6G Quality Signal Provenance + Promotion Review

**Version**: v6g
**Date**: 2026-03-16
**Status**: COMPLETED

---

## Executive Summary

Fixed v6f issue where quality signal had contradiction:
- `interpretable = True`
- `source = shadow_compare`
- `signal_value = 0.4`
- `explanation = "Computed from 0 samples"` ❌

Now quality signal provenance is **consistent and traceable**:
- `sample_count_used = 40`
- `explanation = "Computed from 40 shadow-compare samples"` ✅

---

## v6f Issue

### The Problem
v6f pilot report contained this contradiction:

```json
{
  "signal_value": 0.4,
  "source": "shadow_compare",
  "interpretable": true,
  "explanation": "Computed from 0 samples"  // ❌ WRONG
}
```

This meant:
- Signal claimed to be interpretable
- But no evidence of actual computation
- Promotion decision based on untraceable signal

### The Fix
v6g introduces `QualitySignalProvenance` with mandatory fields:

```json
{
  "signal_value": 0.4105,
  "source": "shadow_compare",
  "interpretable": true,
  "sample_count_used": 40,
  "computation_method": "topk_shadow_compare_win_rate",
  "sample_batch_ref": "pilot_complex_semantic_reasoning_rounds_1_2",
  "baseline_provider": "tfidf",
  "candidate_provider": "ollama",
  "explanation": "Computed from 40 shadow-compare samples (baseline=tfidf, candidate=ollama)"
}
```

---

## Provenance Fields

| Field | Description | Required |
|-------|-------------|----------|
| `signal_value` | Computed quality signal | ✅ |
| `source` | How signal was computed | ✅ |
| `interpretable` | Can be used for decisions | ✅ |
| `sample_count_used` | Number of samples | ✅ (if interpretable) |
| `computation_method` | Algorithm used | ✅ (if interpretable) |
| `sample_batch_ref` | Batch identifier | ✅ |
| `baseline_provider` | Baseline provider (e.g., tfidf) | ✅ (if shadow_compare) |
| `candidate_provider` | Candidate provider (e.g., ollama) | ✅ (if shadow_compare) |
| `explanation` | Human-readable explanation | ✅ |

---

## Validation Rules

Promotion is **blocked** if:

1. `interpretable = false`
2. `sample_count_used = 0`
3. Explanation doesn't mention sample count
4. `source = shadow_compare` but providers missing
5. `signal_value > 0` but no computation method
6. Provenance fields missing

---

## Promotion Review Flow

```
1. Check rollback conditions (highest priority)
   ├─ fallback_rate > 10% → ROLLBACK
   ├─ p95_latency > 300ms → ROLLBACK
   └─ provider_health < 95% → ROLLBACK

2. Validate quality signal provenance
   ├─ interpretable check
   ├─ sample_count_used check
   ├─ consistency check
   └─ explanation match check

3. Check promotion conditions
   ├─ sample_size >= 30
   ├─ fallback_rate <= 5%
   ├─ provider_health >= 98%
   └─ quality_signal > 0

4. Verdict
   ├─ All pass → PROMOTE
   ├─ Provenance invalid → KEEP_PILOT
   └─ Rollback condition → ROLLBACK
```

---

## Rebuilt Results

```
Quality Signal Provenance:
  signal_value: 0.4105
  source: shadow_compare
  interpretable: True
  sample_count_used: 40
  computation_method: topk_shadow_compare_win_rate
  sample_batch_ref: pilot_complex_semantic_reasoning_rounds_1_2
  explanation: Computed from 40 shadow-compare samples (baseline=tfidf, candidate=ollama)
  baseline_provider: tfidf
  candidate_provider: ollama

Promotion Review:
  verdict: PROMOTE
  rationale: All promotion criteria met with valid quality signal provenance
```

---

## Files Created

| File | Purpose |
|------|---------|
| `emotiond/memory/embedding/quality_signal_provenance.py` | Provenance with consistency validation |
| `emotiond/memory/embedding/promotion_review.py` | Promotion review with provenance check |
| `scripts/rebuild_quality_signal_report.py` | Rebuild report with correct provenance |
| `tests/embedding/test_quality_signal_provenance.py` | Provenance tests |
| `tests/embedding/test_promotion_review.py` | Review tests |
| `tests/e2e/test_v6g_promotion_review.py` | E2E tests |
| `docs/V6G_QUALITY_SIGNAL_PROVENANCE.md` | This document |

---

## Test Results

```
tests/embedding/test_quality_signal_provenance.py: 24 passed
tests/embedding/test_promotion_review.py: 14 passed
tests/e2e/test_v6g_promotion_review.py: 11 passed

Total: 49 passed
```

---

## Key Changes from v6f

| Aspect | v6f | v6g |
|--------|-----|-----|
| Quality signal | `QualitySignalResult` | `QualitySignalProvenance` |
| sample_count_used | Not tracked | Mandatory |
| Explanation | Could contradict | Must match sample_count |
| Validation | None | `validate_consistency()` |
| Promotion check | Sample-based only | Provenance-based |

---

## Capability Ownership

**Owner**: OpenEmotion

- Provenance: `emotiond/memory/embedding/quality_signal_provenance.py`
- Review: `emotiond/memory/embedding/promotion_review.py`

**NOT in**:
- EgoCore
- Host/宿主层

---

## What Was NOT Done

Per task constraints:
- ❌ Did NOT add candidate to production whitelist
- ❌ Did NOT activate auto mode
- ❌ Did NOT change default provider
- ❌ Did NOT approve promotion without valid provenance

---

## Next Steps

1. **Final approval**: Confirm promotion with valid provenance
2. **Whitelist update**: Add `complex_semantic_reasoning` to production whitelist
3. **Monitoring**: Track quality signal in production
4. **Documentation**: Update governance docs

---

## Environment

- Host Ollama URL: `http://192.168.79.1:11434/v1`
- Model: `mxbai-embed-large`
- Vector dimensions: 1024
- Test date: 2026-03-16

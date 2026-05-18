# V6C High-Quality Retrieval Mode Admission Governance

**Version**: v6c
**Date**: 2026-03-16
**Status**: COMPLETED

---

## Executive Summary

Established admission governance for high-quality retrieval mode expansion. The system now has:
- **Real-time observation** of provider usage
- **Admission gates** with clear thresholds
- **Decision logic** for mode expansion eligibility
- **Risk guardrails** for rollback triggers

---

## Admission States

| State | Meaning | When |
|-------|---------|------|
| `manual_only` | Only explicit requests | Insufficient data or gates failed |
| `limited_rollout_candidate` | May expand to specific scenarios | All gates pass |
| `auto_mode_candidate` | Auto mode eligible | Reserved for future (conservative) |
| `rollback_required` | Must restrict usage | Critical risk detected |

---

## Admission Gates

| Gate | Threshold | Comparison |
|------|-----------|------------|
| sample_size | ≥ 20 | Need sufficient data |
| wrong_user_recall_count | = 0 | Zero tolerance for wrong-user |
| fallback_rate | ≤ 10% | Provider must be stable |
| provider_health_rate | ≥ 95% | Health checks must pass |
| p95_latency_ms | ≤ 300ms | Latency acceptable |
| quality_gain | ≥ 10% | Worth the cost |

---

## Current Observation Results

After 20 real samples:

```
State: LIMITED_ROLLOUT_CANDIDATE

Gates:
  ✅ sample_size: 20 (threshold: 20)
  ✅ wrong_user_recall: 0 (threshold: 0)
  ✅ fallback_rate: 0.0% (threshold: 10%)
  ✅ provider_health_rate: 100% (threshold: 95%)
  ✅ p95_latency: 58.9ms (threshold: 300ms)
  ✅ quality_gain: 20% (threshold: 10%)
```

---

## Decision Rules

### ROLLBACK_REQUIRED
If **any** of these occur:
- `wrong_user_recall_count > 0` (critical risk)

### MANUAL_ONLY
If **any** of these occur:
- `sample_size < 20`
- `fallback_rate > 10%`
- `provider_health_rate < 95%`
- `p95_latency > 300ms`

### LIMITED_ROLLOUT_CANDIDATE
If **all** gates pass:
- Sufficient samples
- Zero wrong-user recall
- Low fallback rate
- High provider health
- Acceptable latency
- Quality gain demonstrated

---

## Metrics Tracked

| Metric | Description |
|--------|-------------|
| sample_size | Total samples collected |
| request_count | Total provider requests |
| success_count | Successful requests |
| fallback_count | Fallback events |
| fallback_rate | fallback_count / request_count |
| timeout_count | Request timeouts |
| wrong_user_recall_count | Wrong-user incidents |
| avg_latency_ms | Average latency |
| p95_latency_ms | 95th percentile latency |
| provider_health_rate | Health check success rate |
| quality_gain | Ollama hit@1 - TF-IDF hit@1 |

---

## Files Created

| File | Purpose |
|------|---------|
| `emotiond/memory/embedding/admission.py` | Admission governance logic |
| `scripts/run_admission_observation.py` | Observation runner |
| `tests/embedding/test_admission_governance.py` | Governance tests |
| `tests/e2e/test_v6c_admission_governance.py` | E2E tests |
| `docs/V6C_ADMISSION_GOVERNANCE.md` | This document |

---

## Test Results

```
tests/embedding/test_admission_governance.py: 20 passed
tests/e2e/test_v6c_admission_governance.py: 8 passed

Total: 28 passed
```

Observation: All gates passed, `LIMITED_ROLLOUT_CANDIDATE`

---

## Capability Ownership

**Owner**: OpenEmotion

- Admission logic: `emotiond/memory/embedding/admission.py`
- Observation: `scripts/run_admission_observation.py`

**NOT in**:
- EgoCore
- Host/宿主层

---

## What Was NOT Done

Per task constraints:
- ❌ Did NOT change default to Ollama
- ❌ Did NOT enable auto-upgrade
- ❌ Did NOT add new providers
- ❌ Did NOT claim production-ready for expansion

---

## Recommendations

Based on current observation:

1. **Continue monitoring**: Collect more samples over extended period
2. **Specific scenarios**: Consider enabling Ollama for high-priority retrieval queries
3. **Observability**: Add metrics to dashboards for continuous monitoring
4. **Risk guard**: Keep wrong_user_recall monitoring active

---

## Next Steps

1. **Extended observation**: Run observation for longer periods
2. **Scenario-specific enablement**: Identify high-value scenarios for Ollama
3. **Auto mode design**: Define conditions for intelligent mode selection
4. **Integration**: Wire admission checks into retrieval pipeline

---

## Environment

- Host Ollama URL: `http://192.168.79.1:11434/v1`
- Model: `mxbai-embed-large`
- Vector dimensions: 1024
- Test date: 2026-03-16

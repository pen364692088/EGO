# Plan Injection Runtime Metrics Baseline

## Overview

This document establishes the baseline for Plan Injection metrics.

## Metrics Definition

### Counters

| Metric | Description | Labels |
|--------|-------------|--------|
| `plan_injection_attempt_total` | Total injection attempts | - |
| `plan_injection_allowed_total` | Allowed injections | - |
| `plan_injection_skipped_total` | Skipped injections | `reason` |
| `plan_injection_fallback_total` | Fallback triggered | `reason` |
| `plan_injection_error_total` | Errors | - |

### Histogram

| Metric | Description | Buckets |
|--------|-------------|---------|
| `plan_injection_latency_ms` | Injection latency | p50, p95, p99 |

### Labels

| Label | Values |
|-------|--------|
| `reason` (skip) | `is_command`, `is_task_control`, `is_tool_path`, `feature_disabled` |
| `reason` (fallback) | `timeout`, `down`, `http_5xx`, `http_4xx`, `schema_invalid`, `empty_plan` |

## Accessing Metrics

### Python

```python
from app.integrations.openemotion.injection_metrics import get_injection_metrics

metrics = get_injection_metrics()
print(metrics.to_dict())
```

### Save to File

```python
from app.integrations.openemotion.injection_metrics import get_injection_metrics

metrics = get_injection_metrics()
metrics.save("/path/to/metrics.json")
```

## Expected Baseline

After initial testing:

| Metric | Expected Value |
|--------|----------------|
| `attempt_total` | >= 1 |
| `allowed_total` | >= 0 |
| `skipped_total` | >= 0 |
| `fallback_total` | >= 0 |
| `avg_latency_ms` | < 100 (local) |

## Health Indicators

| Indicator | Healthy | Degraded | Unhealthy |
|-----------|---------|----------|-----------|
| `allowed_total / attempt_total` | > 0.8 | 0.5 - 0.8 | < 0.5 |
| `avg_latency_ms` | < 50ms | 50-200ms | > 200ms |
| `fallback_total / attempt_total` | < 0.1 | 0.1 - 0.3 | > 0.3 |

## Alerting Thresholds

| Condition | Alert Level |
|-----------|-------------|
| `fallback_total / attempt_total > 0.5` | WARNING |
| `avg_latency_ms > 500` | WARNING |
| `error_total > 10 in 5min` | ERROR |

## Implementation Notes

- Metrics are stored in memory (no persistence)
- Metrics are not thread-safe (single-process assumption)
- Latency samples are capped at 1000 samples

## Version

- **Date**: 2026-03-13
- **Implementation**: `app/integrations/openemotion/injection_metrics.py`

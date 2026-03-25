# V6B High-Quality Retrieval Mode Controlled Landing

**Version**: v6b
**Date**: 2026-03-16
**Status**: COMPLETED

---

## Executive Summary

OpenEmotion now supports two retrieval modes with controlled switching:
- **Default mode**: TF-IDF (fast, zero-cost)
- **High-quality mode**: Ollama (better accuracy, ~70ms latency)

With automatic fallback and full telemetry tracking.

---

## Mode Definition

### `tfidf` (Default)
- Fast: sub-millisecond latency
- Zero cost: no external API calls
- Reliable: no network dependencies
- **Always the default on startup**

### `ollama` (High-Quality)
- Better accuracy: +20% hit@1, +20% hit@3
- Higher latency: ~70ms average
- Requires: Ollama host running with `mxbai-embed-large` model
- Automatic fallback to tfidf on failure

### `auto` (Reserved)
- Currently: alias for `tfidf`
- Future: intelligent mode selection based on context
- Interface: already reserved for future use

---

## Configuration

```json
{
  "retrieval": {
    "mode": "tfidf",
    "allow_high_quality_mode": true,
    "auto_upgrade_enabled": false,
    "fallback_on_provider_failure": true,
    "log_provider_selection": true
  },
  "embedding": {
    "provider": "tfidf",
    "fallback_provider": "tfidf",
    "ollama": {
      "enabled": true,
      "model": "mxbai-embed-large",
      "baseUrl": "http://192.168.79.1:11434/v1",
      "dimensions": 1024,
      "timeoutMs": 10000,
      "maxBatchSize": 32
    }
  }
}
```

**Key Constraints**:
- `mode` defaults to `tfidf`
- `auto_upgrade_enabled` defaults to `false`
- `fallback_on_provider_failure` defaults to `true`

---

## Runtime Behavior

### Explicit TF-IDF
```python
provider, trace = await selector.select_provider("tfidf")
# Always uses TF-IDF, no fallback
```

### Explicit Ollama
```python
provider, trace = await selector.select_provider("ollama")
# Uses Ollama if healthy, falls back to TF-IDF if not
# trace.fallback_triggered indicates if fallback occurred
```

### Default (No Override)
```python
provider, trace = await selector.select_provider()
# Uses default mode from config (TF-IDF)
```

---

## Selection Trace

Every provider selection is traced:

```json
{
  "requested_mode": "ollama",
  "resolved_mode": "ollama",
  "provider_used": "ollama",
  "fallback_triggered": false,
  "fallback_reason": null,
  "latency_ms": 65.2,
  "timestamp": 1710613200.123
}
```

---

## Telemetry

Provider usage is tracked:

```json
{
  "providers": {
    "tfidf": {
      "usage_count": 100,
      "success_count": 100,
      "fallback_count": 0,
      "avg_latency_ms": 0.01
    },
    "ollama": {
      "usage_count": 50,
      "success_count": 45,
      "fallback_count": 5,
      "avg_latency_ms": 68.5
    }
  },
  "summary": {
    "tfidf_usage_count": 100,
    "ollama_usage_count": 50,
    "total_fallback_count": 5
  }
}
```

---

## Capability Ownership

**Owner**: OpenEmotion

- Provider selection logic: `emotiond/memory/embedding/selector.py`
- Telemetry: `emotiond/memory/embedding/telemetry.py`
- Configuration: `emotiond/config/...`

**NOT in**:
- EgoCore
- Host/宿主层
- Any external system

---

## Files Created

| File | Purpose |
|------|---------|
| `emotiond/memory/embedding/selector.py` | Provider selection and mode routing |
| `emotiond/memory/embedding/telemetry.py` | Usage tracking and metrics |
| `scripts/check_retrieval_mode_routing.py` | Routing validation script |
| `tests/embedding/test_provider_selection.py` | Selection tests |
| `tests/embedding/test_provider_fallback_runtime.py` | Fallback tests |
| `tests/e2e/test_v6b_high_quality_mode.py` | E2E tests |

---

## Test Results

```
tests/embedding/test_provider_selection.py: 19 passed
tests/embedding/test_provider_fallback_runtime.py: 7 passed
tests/e2e/test_v6b_high_quality_mode.py: 14 passed

Total: 40 passed
```

Routing check: 4/4 passed

---

## What Was NOT Done

Per task constraints:
- ❌ Did NOT change default to Ollama
- ❌ Did NOT move semantics to EgoCore
- ❌ Did NOT add new embedding providers
- ❌ Did NOT enable auto-upgrade by default

---

## Latency Uniformity (v6a Correction)

All latency values now reference the same source:
- `ab_report.json`: 68.51ms (Ollama avg)
- `config_snapshot.json`: 69.75ms (approx)
- Documented: ~70ms (rounded for human readability)

## Dimensions Uniformity

- Config `dimensions`: `null` (not specified, uses model default)
- Actual `vector_dim`: 1024 (from `mxbai-embed-large`)
- Report records: 1024

Rule: If config `dimensions` is null, use model's actual dimension.

---

## Next Steps

1. **Production monitoring**: Add telemetry to dashboards
2. **Caching**: Consider embedding cache for repeated queries
3. **Auto mode**: Implement intelligent mode selection when requirements are clear
4. **Extended test cases**: Add more retrieval scenarios

---

## Environment

- Host Ollama URL: `http://192.168.79.1:11434/v1`
- Model: `mxbai-embed-large`
- Vector dimensions: 1024
- Test date: 2026-03-16

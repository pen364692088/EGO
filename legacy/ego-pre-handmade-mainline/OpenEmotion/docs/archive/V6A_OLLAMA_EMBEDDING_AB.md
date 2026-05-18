# V6A Ollama Embedding A/B Evaluation Report

**Version**: v6a
**Date**: 2026-03-16
**Status**: COMPLETED

---

## Executive Summary

OpenEmotion has successfully integrated host Ollama `mxbai-embed-large` embedding and completed real A/B comparison with TF-IDF baseline.

**Verdict: BETTER** - Ollama is a candidate for high-quality retrieval mode.

---

## Test Results

| Metric | TF-IDF | Ollama | Δ |
|--------|--------|--------|---|
| hit@1 | 40.00% | 60.00% | +20.00% |
| hit@3 | 80.00% | 100.00% | +20.00% |
| wrong_user_recall_count | 4 | 3 | -1 (improved) |
| hard_negative_false_recall | 4 | 3 | -1 (improved) |
| avg_latency_ms | 0.01 | 69.75 | +69.74ms |
| p95_latency_ms | 0.04 | 93.44 | +93.40ms |

---

## Key Findings

### Quality
- **Ollama significantly outperforms TF-IDF** in retrieval accuracy
- hit@1 improved by 20 percentage points
- hit@3 improved by 20 percentage points
- Wrong user recall reduced by 25%

### Latency
- TF-IDF: sub-millisecond (0.01ms)
- Ollama: ~70ms average, ~93ms p95
- Trade-off: quality vs speed

### Vector Dimensions
- Ollama `mxbai-embed-large`: **1024 dimensions**
- TF-IDF: variable (depends on vocabulary)

---

## Capability Ownership

✅ Embedding capability is owned by **OpenEmotion**
- Provider selection authority: OpenEmotion
- Semantic interpretation authority: OpenEmotion
- Retrieval hit semantics: OpenEmotion

❌ No leakage to EgoCore/OpenClaw

---

## Decision Criteria (All Passed)

| Criterion | Result |
|-----------|--------|
| better_hit | ✅ Yes (+20% hit@1, +20% hit@3) |
| no_wrong_user_regression | ✅ Yes (3 < 4) |
| no_hard_negative_regression | ✅ Yes (3 < 4) |
| acceptable_latency | ✅ Yes (< 200ms) |

---

## Recommendation

**Ollama `mxbai-embed-large` is a candidate for high-quality retrieval mode.**

### Recommended Configuration

```json
{
  "embedding": {
    "enabled": true,
    "provider": "tfidf",
    "fallback_provider": "tfidf",
    "ollama_base_url": "http://192.168.79.1:11434/v1",
    "ollama_model": "mxbai-embed-large",
    "timeout_ms": 15000,
    "max_batch_size": 32
  }
}
```

### Usage

- **Default**: TF-IDF (fastest, zero cost)
- **High-quality mode**: Ollama (better accuracy, ~70ms latency)

---

## Files Created

| File | Purpose |
|------|---------|
| `emotiond/memory/embedding/contracts.py` | Provider contracts and schemas |
| `emotiond/memory/embedding/providers/tfidf_provider.py` | TF-IDF provider |
| `emotiond/memory/embedding/providers/ollama_provider.py` | Ollama provider |
| `emotiond/memory/embedding/factory.py` | Provider factory |
| `scripts/smoke_ollama_embedding.py` | Smoke test script |
| `scripts/eval_memory_retrieval_v6a.py` | A/B evaluation script |
| `artifacts/eval/v6a/ab_report.json` | Full evaluation results |

---

## What Was NOT Done

Per task constraints:
- ❌ Did NOT change EgoCore to embedding owner
- ❌ Did NOT write retrieval semantics to host layer
- ❌ Did NOT switch production default to Ollama
- ❌ Did NOT re-verify OpenAI provider
- ❌ Did NOT claim WS-C/C1 completed
- ❌ Did NOT claim MVP13-15 completed

---

## Next Steps

1. **Production decision**: Choose default provider based on latency requirements
2. **Monitoring**: Add embedding latency metrics to production dashboards
3. **Caching**: Consider embedding cache for repeated queries
4. **Extended test cases**: Add more diverse test scenarios for validation

---

## Environment

- Host Ollama URL: `http://192.168.79.1:11434/v1`
- Model: `mxbai-embed-large`
- Vector dimensions: 1024
- Test date: 2026-03-16

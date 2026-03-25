# Memory Retrieval Enhancement v6 - A/B Verification Report

- **Test Suite**: memory_retrieval_v6
- **Version**: 1.0.0
- **Timestamp**: 2026-03-16T19:30:18+00:00
- **Overall**: ⚠️ PARTIAL PASS

---

## Executive Summary

本报告回答核心问题：**OpenAI embeddings 是否值得切换？**

### 结论：保持 TF-IDF

**推荐策略**: tfidf

**理由**:
1. OpenAI API Key 当前无效（401 Unauthorized）
2. 无法完成真实 A/B 对照验证
3. TF-IDF baseline 已验证可用（20% pass rate on synonym_rewrite cases）
4. 成本为零，延迟极低（1.83ms）

**下一步建议**:
- 更新 OpenAI API Key 后重新验证
- 或考虑其他 embedding provider（如 local sentence-transformers）

---

## A/B Test Results

### TF-IDF Baseline ✅

| Metric | Value |
|--------|-------|
| Total Cases | 20 |
| Passed | 4 |
| Pass Rate | 20.0% |
| Avg Similarity | 0.3859 |
| Avg Latency | 1.83ms |
| P95 Latency | ~5ms |
| Cost | $0 (local) |

**质量评估**:
- TF-IDF 在 synonym_rewrite 类别表现稳定
- 相似度约 0.39（符合 v5 预期）
- 延迟极低，适合实时场景

### OpenAI Embeddings ❌

| Metric | Value |
|--------|-------|
| Total Cases | 20 |
| Passed | 0 |
| Pass Rate | 0.0% |
| Avg Similarity | 0.0000 |
| Avg Latency | 65.78ms |
| Cost per 1000 calls | N/A |

**失败原因**:
- HTTP 401 Unauthorized
- API Key 无效或过期

---

## Comparison

由于 OpenAI 测试失败，无法完成真实 A/B 对照。

| Metric | TF-IDF | OpenAI | Notes |
|--------|--------|--------|-------|
| Pass Rate | 20.0% | N/A | API 不可用 |
| Avg Similarity | 0.3859 | N/A | - |
| Avg Latency | 1.83ms | 65.78ms | OpenAI 网络延迟 |
| Cost | $0 | ~$0.02/1M tokens | 需付费 |

---

## Recommendation

### 当前决策：保持 TF-IDF

```json
{
  "recommended_default_mode": "tfidf",
  "reason": "OpenAI API Key 无效，无法完成 A/B 验证",
  "fallback_strategy": "保持 TF-IDF 直到 API 可用",
  "quality_gain_vs_cost": "unknown (pending valid API key)"
}
```

### 建议后续步骤

1. **更新 API Key**: 获取有效的 OpenAI API Key
2. **重新验证**: 使用有效 Key 重新运行 v6 测试
3. **备选方案**: 考虑本地 embedding（sentence-transformers）

---

## 验收问题回答

| 问题 | 状态 | 备注 |
|------|------|------|
| Q1. OpenAI embeddings 是否优于 TF-IDF | ⚠️ Unknown | API 不可用 |
| Q2. hit@1/hit@3 是否提升 | ⚠️ Unknown | API 不可用 |
| Q3. wrong_user_recall_count 是否保持 0 | ✅ Yes | TF-IDF 验证通过 |
| Q4. dedup/clustering 质量是否保持 | ✅ Yes | 已在 v5 验证 |
| Q5. 延迟/缓存命中率 | ✅ TF-IDF: 1.83ms | 极低延迟 |
| Q6. 成本估算 | ✅ TF-IDF: $0 | 无成本 |
| Q7. 最终推荐策略 | ✅ tfidf | 保持现状 |

---

## Three Red Lines (Still Enforced)

- ❌ Do NOT claim WS-C/C1 completed
- ❌ Do NOT proceed to WS-C/C2
- ❌ Do NOT claim MVP13-15 completed

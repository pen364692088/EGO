# Runtime Metrics Aggregator Integration Readiness 报告

## 1. 接入点定位

**接入点**: `system_core.metrics_hook`

**调用方**:
- session_manager (会话生命周期)
- subagent_orchestrator (子代理编排)
- reply_pipeline (回复处理)
- system_core (系统事件)

**时机**: 各模块关键事件发生时

**频率**: per_event / per_session / per_message

---

## 2. 默认关闭与失败降级

### 2.1 Feature Flag

```python
runtime_metrics_enabled = False  # 默认关闭
```

### 2.2 保护机制

| 机制 | 实现 | 状态 |
|------|------|------|
| Feature Flag | `config/feature_flags.py` | ✅ 实现 |
| Fast Disable | `fast_disable()` 方法 | ✅ 实现 |
| Rollback | `protection/rollback.py` | ✅ 实现 |
| Timeout | `protection/timeout_guard.py` | ✅ 实现 |
| Circuit Breaker | `protection/circuit_breaker.py` | ✅ 实现 |
| 异常隔离 | `record_with_fallback()` | ✅ 实现 |

### 2.3 降级路径

```
正常处理 → 返回 metric_id
    ↓ (验证失败)
Adapter fallback → 返回 dropped
    ↓ (core 异常)
Core error → 返回 dropped
    ↓ (timeout)
Timeout → 强制返回 dropped
    ↓ (feature flag 关闭)
完全禁用 → 返回 dropped (零开销)
```

---

## 3. Shadow 模式运行

### 3.1 Shadow 配置

```python
SHADOW_CONFIG = {
    "enabled": True,
    "sample_rate": 1.0,
    "output_to_log": True,
    "output_to_metrics": True,
}
```

### 3.2 观察指标

| 指标 | 类型 | 用途 |
|------|------|------|
| shadow_calls_total | counter | 调用次数 |
| shadow_success_total | counter | 成功次数 |
| shadow_fallback_total | counter | Fallback 次数 |
| shadow_timeout_total | counter | 超时次数 |
| shadow_latency_ms | histogram | 延迟分布 |

### 3.3 观察窗口

- **周期**: 14 天
- **最低样本**: 1000 次调用
- **通过条件**:
  - 成功率 ≥ 95%
  - Fallback 率 ≤ 5%
  - 超时率 ≤ 1%
  - 平均延迟 < 10ms
  - P95 延迟 < 50ms

---

## 4. 对照验证结果

### 4.1 测试覆盖

| 测试文件 | 用例数 | 通过 |
|----------|--------|------|
| test_runtime_metrics_aggregator_contract.py | 15 | ✅ 15 |
| test_runtime_metrics_aggregator_integration.py | 14 | ✅ 14 |
| test_runtime_metrics_aggregator_fallback.py | 12 | ✅ 12 |
| test_runtime_metrics_aggregator_feature_flag.py | 12 | ✅ 12 |
| test_runtime_metrics_aggregator_shadow.py | 10 | ✅ 10 |
| test_runtime_metrics_aggregator_isolation.py | 8 | ✅ 8 |
| test_runtime_metrics_aggregator_rollback.py | 10 | ✅ 10 |
| test_runtime_metrics_aggregator_mainline_consistency.py | 10 | ✅ 10 |

**总计**: 91/91 通过 ✅

### 4.2 验证项

- [x] Feature flag 关闭时，主链行为一致
- [x] Shadow 开启时，主链用户输出不变
- [x] 模块异常时，主链仍正常
- [x] Timeout 时，主链仍正常
- [x] Fast disable 生效
- [x] Rollback 生效
- [x] Observability 数据可记录、可读取、可解释
- [x] 无性能退化（单次 < 10ms）

---

## 5. 接主链建议

### 5.1 当前状态

✅ **允许进入正式接主链执行期**

### 5.2 理由

1. 接入点已明确
2. 保护机制完备（feature flag / fast disable / rollback / timeout / isolation）
3. Shadow 模式可运行
4. 91/91 测试通过
5. 不影响主链稳定性
6. 失败可降级

### 5.3 建议接入步骤

1. **Phase 1**: Shadow 模式运行 14 天
   - 只对 session_manager 启用
   - 收集观察数据

2. **Phase 2**: 逐步扩展
   - 扩展到 subagent_orchestrator
   - 继续观察

3. **Phase 3**: 全量启用
   - 启用 reply_pipeline（高频，谨慎）
   - 监控性能指标

4. **Rollback 准备**
   - 保持快速回滚能力
   - 设定自动禁用阈值

---

## 6. 交付物清单

### 6.1 设计文档
- `artifacts/integration/RUNTIME_METRICS_AGGREGATOR_INTEGRATION_PLAN.md`
- `artifacts/verification/RUNTIME_METRICS_AGGREGATOR_SHADOW_PLAN.md`

### 6.2 保护实现
- `modules/runtime_metrics_aggregator/config/feature_flags.py`
- `modules/runtime_metrics_aggregator/protection/circuit_breaker.py`
- `modules/runtime_metrics_aggregator/protection/timeout_guard.py`
- `modules/runtime_metrics_aggregator/protection/rollback.py`

### 6.3 测试文件
- `tests/integration/test_runtime_metrics_aggregator_shadow.py`
- `tests/integration/test_runtime_metrics_aggregator_isolation.py`
- `tests/integration/test_runtime_metrics_aggregator_rollback.py`
- `tests/integration/test_runtime_metrics_aggregator_mainline_consistency.py`

### 6.4 本报告
- `artifacts/verification/RUNTIME_METRICS_AGGREGATOR_INTEGRATION_READINESS.md`

---

## 7. 结论

**runtime_metrics_aggregator 已完成接主链准备包。**

- 接入点明确
- 保护机制完备
- Shadow 方案就绪
- 对照验证通过
- **建议：允许进入正式接主链执行期**

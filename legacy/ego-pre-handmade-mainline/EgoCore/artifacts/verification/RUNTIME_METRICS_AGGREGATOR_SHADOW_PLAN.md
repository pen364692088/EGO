# Runtime Metrics Aggregator Shadow 观察方案

## 1. Shadow 模式定义

### 1.1 核心原则

**旁路观察，不改变主逻辑输出**

- Shadow 模式下指标收集在旁路进行
- 不影响用户可见回复
- 不影响主链处理逻辑
- 可单独开关，与主功能开关独立

### 1.2 模式对比

| 模式 | 功能 | 输出影响 | 用途 |
|------|------|----------|------|
| Disabled | 完全关闭 | 无 | 默认状态 |
| Shadow | 收集指标，不输出 | 无 | 观察验证 |
| Enabled | 收集并输出 | 无 | 正式运行 |

## 2. Shadow 模式实现

### 2.1 配置

```python
SHADOW_CONFIG = {
    "enabled": True,           # Shadow 模式开关
    "sample_rate": 1.0,        # 采样率
    "max_records_per_minute": 10000,  # 速率限制
    "output_to_log": True,     # 输出到日志
    "output_to_metrics": True, # 输出到指标系统
}
```

### 2.2 行为定义

```python
def record_in_shadow_mode(metric_data):
    """Shadow 模式记录"""
    # 1. 记录指标（旁路）
    result = adapter.record_with_fallback(**metric_data)
    
    # 2. 记录到 shadow 日志
    if SHADOW_CONFIG["output_to_log"]:
        logger.debug(f"[SHADOW] Metric recorded: {metric_data}")
    
    # 3. 不返回给主链
    return {"shadow_recorded": True, "metric_id": result["metric_id"]}
```

## 3. 观察指标

### 3.1 必须记录

| 指标 | 类型 | 说明 |
|------|------|------|
| shadow_calls_total | counter | Shadow 调用次数 |
| shadow_success_total | counter | 成功记录次数 |
| shadow_fallback_total | counter | Fallback 次数 |
| shadow_timeout_total | counter | 超时次数 |
| shadow_disabled_total | counter | 禁用触发次数 |
| shadow_latency_ms | histogram | 处理延迟 |

### 3.2 统计维度

```python
SHADOW_STATS = {
    "calls": 0,           # 总调用次数
    "success": 0,         # 成功次数
    "fallback": 0,        # Fallback 次数
    "timeout": 0,         # 超时次数
    "disabled": 0,        # 禁用触发次数
    "latency_ms": [],     # 延迟分布
}
```

## 4. 观察窗口建议

### 4.1 观察周期

- **最小周期**: 7 天
- **推荐周期**: 14 天
- **最大周期**: 30 天

### 4.2 最低样本要求

| 指标 | 最低样本 |
|------|----------|
| 总调用次数 | ≥ 1000 |
| 成功记录 | ≥ 800 |
| Fallback | ≥ 10 (用于验证 fallback) |

### 4.3 通过条件

必须同时满足：
- [ ] 成功率 ≥ 95%
- [ ] Fallback 率 ≤ 5%
- [ ] 超时率 ≤ 1%
- [ ] 平均延迟 < 10ms
- [ ] P95 延迟 < 50ms
- [ ] 无内存泄漏迹象
- [ ] 不影响主链性能（延迟增加 < 5%）

### 4.4 撤回条件

满足任一即撤回：
- [ ] 成功率 < 90%
- [ ] Fallback 率 > 10%
- [ ] 超时率 > 5%
- [ ] 平均延迟 > 50ms
- [ ] 主链性能下降 > 10%
- [ ] 内存使用异常增长
- [ ] 用户投诉

## 5. Shadow 模式开关

### 5.1 独立控制

```python
# Shadow 模式可独立于主功能开关
feature_flags.set("runtime_metrics_shadow", True)   # 开启 Shadow
feature_flags.set("runtime_metrics_enabled", False) # 主功能仍关闭
```

### 5.2 切换流程

```
Disabled → Shadow → Enabled
    ↑        ↓         ↓
    └────────┴─────── Rollback
```

## 6. 数据验证

### 6.1 数据完整性

- 指标格式正确
- 标签完整
- 时间戳有效
- 可查询验证

### 6.2 数据一致性

- Shadow 与 Enabled 模式数据一致
- 多次查询结果一致
- 并发安全

## 7. 报告输出

### 7.1 每日报告

```yaml
date: 2026-03-14
total_calls: 1500
success_rate: 98.5%
fallback_rate: 1.2%
timeout_rate: 0.1%
avg_latency_ms: 3.2
p95_latency_ms: 12.5
memory_mb: 8.5
status: PASS
```

### 7.2 观察期总结

```yaml
observation_period: 14_days
total_calls: 21000
overall_success_rate: 97.8%
max_latency_ms: 45
avg_memory_mb: 9.2
recommendation: APPROVED_FOR_ENABLED
```

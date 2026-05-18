# Runtime Metrics Aggregator 接入设计

## 1. 计划接入位置

### 1.1 谁调用

**Primary Caller**: `system_core` (系统核心)

**Secondary Callers**:
- `session_manager` - 会话生命周期指标
- `subagent_orchestrator` - 子代理编排指标
- `reply_pipeline` - 回复处理指标

### 1.2 调用时机

| 调用方 | 时机 | 指标示例 |
|--------|------|----------|
| session_manager | 会话创建/销毁时 | session_created_total, session_duration_ms |
| subagent_orchestrator | 子任务创建/完成时 | subagent_spawned_total, subagent_latency_ms |
| reply_pipeline | 回复生成前后 | reply_generated_total, reply_latency_ms |
| system_core | 系统事件发生时 | system_uptime_ms, memory_usage_bytes |

### 1.3 调用频率

- **session_manager**: per_session (低频)
- **subagent_orchestrator**: per_subtask (中频)
- **reply_pipeline**: per_message (高频)
- **system_core**: per_event / periodic (低频)

### 1.4 输入来源

```python
# 来自各模块的指标数据
{
    "metric_name": "session_created_total",
    "metric_type": "counter",
    "value": 1.0,
    "labels": {"source": "telegram", "status": "success"},
    "timestamp": 1710420000000,  # 可选，默认当前时间
    "module": "session_manager"   # 来源模块标识
}
```

### 1.5 输出去向

- **内存存储**: 环形缓冲区（默认 10000 条）
- **查询接口**: 供 dashboard / health check 使用
- **日志输出**: 采样记录（sample_rate=0.1）

---

## 2. 未启用时系统行为

### 2.1 默认状态

```python
runtime_metrics_enabled = False  # 默认关闭
```

### 2.2 行为定义

当模块未启用时：
1. 所有指标记录调用返回 `{"success": True, "metric_id": "dropped"}`
2. 不占用内存（缓冲区未初始化）
3. 查询返回空结果 `{"metrics": [], "total": 0}`
4. 不产生日志
5. **零开销**

### 2.3 代码路径

```python
# 接入点代码示例
def record_metric(...):
    if not feature_flags.get("runtime_metrics_enabled"):
        return {"success": True, "metric_id": "dropped"}
    
    return metrics_adapter.record_with_fallback(...)
```

---

## 3. 启用后对主链的理论影响面

### 3.1 性能影响

| 指标 | 预期值 | 上限 |
|------|--------|------|
| 单次记录延迟 | < 1ms | 50ms (timeout) |
| 内存占用 | < 10MB | 可配置 |
| CPU 占用 | < 1% | 峰值 < 5% |

### 3.2 影响范围

- **无阻塞**: 异步处理，不阻塞调用方
- **无状态依赖**: 不依赖主链状态
- **无输出修改**: 不改变用户可见输出
- **可观测**: 自身指标可监控

### 3.3 风险点

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 内存溢出 | 低 | 高 | 缓冲区大小限制 |
| 性能退化 | 低 | 中 | timeout 机制 |
| 指标丢失 | 中 | 低 | fallback 可接受 |

---

## 4. 失败时的降级路径

### 4.1 降级层级

```
Level 1: 正常处理 → 返回 metric_id
    ↓ (验证失败)
Level 2: Adapter fallback → 返回 dropped
    ↓ (core 异常)
Level 3: Core error → 返回 dropped + error
    ↓ (timeout)
Level 4: Timeout → 强制返回 dropped
    ↓ (feature flag 关闭)
Level 5: 完全禁用 → 返回 dropped (零开销)
```

### 4.2 降级行为

- **调用方无感知**: 始终返回 `success=True`
- **用户无感知**: 不改变回复内容
- **运维可感知**: 通过日志和自指标观察

### 4.3 自动降级触发

| 条件 | 行为 |
|------|------|
| 验证失败 | Adapter fallback |
| Core 异常 | 捕获异常，返回 dropped |
| Timeout | 中断处理，返回 dropped |
| 缓冲区满 | 覆盖旧数据（环形缓冲） |

---

## 5. Timeout 策略

### 5.1 配置

```python
TIMEOUT_CONFIG = {
    "default_ms": 50,      # 默认 50ms
    "max_ms": 200,         # 最大 200ms
    "graceful_degradation": True  # 超时后优雅降级
}
```

### 5.2 实现

```python
import signal

def record_with_timeout(metric_data, timeout_ms=50):
    def timeout_handler(signum, frame):
        raise TimeoutError("Metric recording timeout")
    
    # 设置超时
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, timeout_ms / 1000)
    
    try:
        result = adapter.record_with_fallback(**metric_data)
        return result
    except TimeoutError:
        return {"success": True, "metric_id": "dropped"}
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
```

### 5.3 超时统计

- 记录 timeout 次数到自指标
- 记录 warning 日志
- 触发 fast disable 评估

---

## 6. Rollback 触发条件

### 6.1 触发条件

| 条件 | 阈值 | 动作 |
|------|------|------|
| 错误率 | > 5% | 告警，评估 rollback |
| Timeout 率 | > 1% | 告警，评估 rollback |
| 内存使用 | > 50MB | 告警，评估 rollback |
| 主链延迟增加 | > 10% | 立即 rollback |
| 用户投诉 | any | 立即 rollback |

### 6.2 Rollback 操作

```python
def rollback_metrics_integration():
    """一键 rollback"""
    # 1. 关闭 feature flag
    feature_flags.set("runtime_metrics_enabled", False)
    
    # 2. 清空缓冲区（可选）
    metrics_adapter.clear_buffer()
    
    # 3. 记录 rollback 事件
    logger.info("Metrics integration rolled back")
    
    return {"rolled_back": True, "timestamp": time.time()}
```

### 6.3 Rollback 验证

- 验证 feature flag 已关闭
- 验证指标不再被记录
- 验证主链行为恢复正常

---

## 7. 接入点详细设计

### 7.1 Hook 注册

```python
# system_core/metrics_hook.py

class MetricsHook:
    """指标收集 Hook"""
    
    def __init__(self):
        self.adapter = None
        self.enabled = False
    
    def initialize(self):
        """初始化（在系统启动时调用）"""
        from runtime_metrics_aggregator.adapter.metrics_adapter import create_adapter
        self.adapter = create_adapter()
        self.enabled = feature_flags.get("runtime_metrics_enabled", False)
    
    def record(self, **kwargs):
        """记录指标（各模块调用）"""
        if not self.enabled or not self.adapter:
            return {"success": True, "metric_id": "dropped"}
        
        return self.adapter.record_with_fallback(**kwargs)
    
    def query(self, **kwargs):
        """查询指标"""
        if not self.enabled or not self.adapter:
            return {"metrics": [], "total": 0}
        
        return self.adapter.query_metrics(**kwargs)

# 全局实例
metrics_hook = MetricsHook()
```

### 7.2 调用示例

```python
# session_manager.py
from system_core.metrics_hook import metrics_hook

def create_session(...):
    # ... 创建会话逻辑 ...
    
    # 记录指标
    metrics_hook.record(
        metric_name="session_created_total",
        metric_type="counter",
        value=1.0,
        labels={"source": source, "status": "success"},
        module="session_manager"
    )
```

### 7.3 配置项

```yaml
# config/metrics.yaml
runtime_metrics:
  enabled: false                    # feature flag
  buffer_size: 10000               # 缓冲区大小
  timeout_ms: 50                   # 超时时间
  log_sample_rate: 0.1            # 日志采样率
  
  # 模块级开关
  modules:
    session_manager: true
    subagent_orchestrator: true
    reply_pipeline: false          # 高频，谨慎开启
```

---

## 8. 验证清单

### 8.1 接入前验证

- [ ] feature flag 默认关闭
- [ ] 未启用时零开销
- [ ] timeout 机制有效
- [ ] fallback 行为正确

### 8.2 接入后验证

- [ ] 指标正确记录
- [ ] 查询功能正常
- [ ] 不影响主链性能
- [ ] 不影响用户输出

### 8.3 Rollback 验证

- [ ] 可一键关闭
- [ ] 关闭后立即生效
- [ ] 主链行为恢复

---

## 9. 附录

### 9.1 相关文件

- Contract: `modules/runtime_metrics_aggregator/runtime_metrics_aggregator_contract.yaml`
- Core: `modules/runtime_metrics_aggregator/core/aggregator.py`
- Adapter: `modules/runtime_metrics_aggregator/adapter/metrics_adapter.py`
- Tests: `modules/runtime_metrics_aggregator/tests/`

### 9.2 决策记录

- 2026-03-14: 选择 system_core.metrics_hook 作为接入点，避免侵入各模块核心逻辑

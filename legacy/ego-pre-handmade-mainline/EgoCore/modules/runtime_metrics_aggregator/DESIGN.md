# runtime_metrics_aggregator 设计说明

## 1. 问题定义

### 1.1 用户真实抱怨
- 系统运行时各模块指标分散，无法统一观测
- 没有简单方式查询当前系统健康状态
- 故障排查时缺乏实时数据

### 1.2 当前系统行为
- 各模块自行打印日志
- 没有结构化指标收集
- 无法聚合分析

### 1.3 最小决策点
- 在哪里拦截指标
- 如何存储指标
- 如何查询指标

### 1.4 主解决链
- 提供统一指标收集接口
- 内存聚合近期指标
- 支持按标签过滤查询

### 1.5 保险链
- 指标收集失败不影响主业务
- 自动降级为丢弃模式
- 可完全关闭

### 1.6 验证标准
- 能收集并查询各模块指标
- 失败时不影响主流程
- 关闭后系统正常运行

---

## 2. 架构设计

### 2.1 模块边界

负责：
- 接收并验证指标数据
- 聚合存储指标
- 提供查询接口

不负责：
- 告警决策
- 长期存储
- 复杂计算
- 可视化展示

### 2.2 核心算法

指标存储采用环形缓冲区：
```
┌─────────────────────────────────────┐
│         Metrics Ring Buffer         │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐  │
│  │ M1  │→│ M2  │→│ M3  │→│ M4  │  │
│  └─────┘ └─────┘ └─────┘ └─────┘  │
│       ↑                        │    │
│       └────────────────────────┘    │
│              (循环覆盖)              │
└─────────────────────────────────────┘
```

查询支持标签过滤：
```python
metrics = aggregator.query(
    name="session_created_total",
    labels={"source": "telegram"},
    since_ms=3600000  # 最近1小时
)
```

### 2.3 数据流

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Caller  │───→│  Adapter │───→│   Core   │───→│  Buffer  │
│  Module  │    │ (验证)   │    │ (聚合)   │    │ (存储)   │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
                                      │
                                      ▼
                               ┌──────────┐
                               │  Query   │
                               │  Result  │
                               └──────────┘
```

---

## 3. 接口设计

### 3.1 输入接口

```python
record_metric(
    metric_name: str,      # 指标名 [a-z0-9_]
    metric_type: str,      # counter/gauge/histogram/timer
    value: float,          # 指标值
    labels: dict,          # 标签键值对
    timestamp: int,        # Unix ms (可选)
    module: str            # 来源模块
) -> RecordResult
```

### 3.2 输出接口

```python
query_metrics(
    name: str = None,           # 指标名过滤
    labels: dict = None,        # 标签过滤
    since_ms: int = None,       # 时间窗口
    module: str = None          # 模块过滤
) -> QueryResult
```

### 3.3 错误码

| 错误码 | 说明 | 处理 |
|--------|------|------|
| INVALID_METRIC | 指标格式无效 | 丢弃，记录 warning |
| STORAGE_ERROR | 存储错误 | fallback，记录 error |
| RATE_LIMITED | 速率超限 | 丢弃，记录 warning |
| TIMEOUT | 处理超时 | fallback，记录 warning |

---

## 4. Fallback 设计

### 4.1 触发条件
- 指标格式无效
- 存储后端错误
- 处理超时
- 速率超限

### 4.2 Fallback 行为
- 返回 `success=true, metric_id="dropped"`
- 记录 warning log
- 不中断调用方流程

### 4.3 用户可见性
- 用户不可见
- 运维可见（通过日志）

---

## 5. 依赖管理

### 5.1 必需依赖
- 无（纯内存实现）

### 5.2 可选依赖
- persistent_storage: 持久化后端
  - 缺失时：内存存储，重启丢失

---

## 6. 测试策略

### 6.1 单元测试
- 指标验证逻辑
- 环形缓冲区操作
- 标签过滤

### 6.2 集成测试
- 完整记录-查询流程
- 并发安全
- 容量限制

### 6.3 Fallback 测试
- 无效输入处理
- 超时处理
- 存储错误处理

### 6.4 边界测试
- 空指标名
- 超大标签值
- 缓冲区满

---

## 7. 可观测性

### 7.1 Metrics

| 指标名 | 类型 | 说明 |
|--------|------|------|
| metrics_received_total | counter | 接收指标数 |
| metrics_dropped_total | counter | 丢弃指标数 |
| metrics_storage_errors_total | counter | 存储错误数 |
| metrics_query_latency_ms | histogram | 查询延迟 |

### 7.2 Logs

| 场景 | 级别 | 内容 |
|------|------|------|
| 指标接收 | debug | metric_name, value, module |
| 指标丢弃 | warning | reason, metric_name |
| 存储错误 | error | error_code, details |

---

## 8. 集成计划

### 8.1 接入点
`system_core.metrics_hook`

### 8.2 Feature Flag
`runtime_metrics_enabled`

### 8.3 灰度策略
1. 先对 session_manager 启用
2. 验证无问题后扩展到 subagent_orchestrator
3. 最后扩展到 reply_pipeline

### 8.4 回滚方案
关闭 `runtime_metrics_enabled`，模块停止接收新指标，已有数据保留。

---

## 9. 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 内存溢出 | 低 | 高 | 环形缓冲区限制容量 |
| 性能损耗 | 低 | 中 | 50ms 超时，异步处理 |
| 指标丢失 | 中 | 低 | fallback 机制，可接受 |

---

## 10. 附录

### 10.1 决策记录
- 2026-03-14: 选择环形缓冲区而非时序数据库，降低复杂度

### 10.2 变更历史

| 日期 | 版本 | 变更 | 作者 |
|------|------|------|------|
| 2026-03-14 | 0.1.0 | 初始设计 | Manager |

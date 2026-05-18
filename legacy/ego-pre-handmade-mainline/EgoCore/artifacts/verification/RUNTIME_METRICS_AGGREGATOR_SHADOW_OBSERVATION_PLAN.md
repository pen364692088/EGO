# Runtime Metrics Aggregator - Shadow Observation Plan

## 文档信息

| 字段 | 值 |
|------|-----|
| 创建日期 | 2026-03-14 |
| 观察窗口 | 14 天 (2026-03-14 ~ 2026-03-28) |
| 当前状态 | SHADOW / OFF |
| 目标 | 收集真实样本，验证是否满足切 ON 条件 |

---

## 一、有效真实样本定义

### 1.1 纳入标准

| 条件 | 说明 |
|------|------|
| 来源 | EgoCore 主链真实调用 |
| 调用点 | `command_router.py:122`, `telegram_bot.py:88,110` |
| 触发方式 | 用户真实消息触发（非测试/mock） |

### 1.2 排除标准

| 条件 | 说明 |
|------|------|
| 测试流量 | pytest / 单元测试 / 集成测试 |
| Mock 流量 | 手动调试调用 |
| 开发环境 | 本地开发时调试调用 |
| 重复调用 | 同一请求的重复记录 |

### 1.3 样本识别

真实样本通过以下方式识别：
- `module` 字段非 `test` / `mock` / `debug`
- 调用来源为生产环境（Telegram bot 真实消息处理）

---

## 二、统计窗口定义

| 参数 | 值 | 说明 |
|------|-----|------|
| 观察周期 | 14 天 | 2026-03-14 ~ 2026-03-28 |
| 最小样本量 | 100 次 | 低于此数量不得下结论 |
| 统计粒度 | 每日 | 每天 00:00 UTC 重置计数器 |
| 汇总周期 | 滚动 7 天 | 计算最近 7 天指标 |

---

## 三、指标口径定义

### 3.1 核心指标

| 指标名 | 类型 | 说明 | 采集方式 |
|--------|------|------|----------|
| `total_calls` | counter | 总调用次数 | `SelfMetricsCollector._received` |
| `success_count` | counter | 成功次数 | `total - dropped - storage_errors` |
| `fallback_count` | counter | Fallback 次数 | `result["metric_id"] == "dropped"` |
| `timeout_count` | counter | 超时次数 | `TimeoutGuard` 触发 |
| `disabled_count` | counter | 禁用调用次数 | `enabled == False` 时的调用 |
| `circuit_break_count` | counter | 熔断次数 | `CircuitBreaker` 触发 |

### 3.2 延迟指标

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `avg_latency_ms` | gauge | 平均延迟 |
| `p95_latency_ms` | gauge | P95 延迟（需采集） |

### 3.3 计算公式

```
成功率 = success_count / total_calls × 100%

fallback 比例 = fallback_count / total_calls × 100%

timeout 比例 = timeout_count / total_calls × 100%

avg_latency_ms = query_latency_sum_ms / query_count
```

---

## 四、切换门槛

| 指标 | 门槛 | 当前值 |
|------|------|--------|
| 成功率 | ≥ 95% | 待收集 |
| fallback 比例 | ≤ 5% | 待收集 |
| timeout 比例 | ≤ 1% | 待收集 |
| 用户可见影响 | 无 | 待验证 |
| rollback 可用 | 是 | 待复核 |
| 性能退化 | 无 | 待验证 |

---

## 五、异常归因分类

| 类别 | 说明 | 示例 |
|------|------|------|
| hook 层问题 | `MetricsHook` 初始化或调用问题 | 未初始化、配置错误 |
| aggregator 问题 | `MetricsAdapter` 内部问题 | 存储失败、验证失败 |
| 主链输入问题 | 调用方传入无效参数 | 空指标名、无效类型 |
| 外部环境 | 系统资源或网络问题 | 内存不足、进程阻塞 |

---

## 六、观测流程

### 6.1 每日检查

```bash
# 运行每日观测脚本
python tools/shadow_metrics_daily_check.py --date YYYY-MM-DD
```

### 6.2 检查内容

1. 收集当日指标
2. 计算成功率/fallback/timeout
3. 检查 circuit breaker / fast disable 状态
4. 验证用户可见影响（无）
5. 异常归因分类
6. 更新每日记录

### 6.3 异常处理

| 异常级别 | 触发条件 | 处理动作 |
|----------|----------|----------|
| 正常 | 指标在阈值内 | 继续观察 |
| 警告 | 单项指标超阈值 | 记录并关注 |
| 严重 | 多项指标超阈值或用户影响 | 立即 fast disable |

---

## 七、产出物清单

| 文件 | 路径 | 状态 |
|------|------|------|
| 观察计划 | `artifacts/verification/RUNTIME_METRICS_AGGREGATOR_SHADOW_OBSERVATION_PLAN.md` | ✅ 本文档 |
| 每日记录 | `artifacts/verification/runtime-metrics-shadow/day_XX.md` | ⏳ 待生成 |
| 汇总报告 | `artifacts/verification/RUNTIME_METRICS_AGGREGATOR_SHADOW_OBSERVATION_REPORT.md` | ⏳ 待生成 |
| 决策结论 | `artifacts/verification/RUNTIME_METRICS_AGGREGATOR_SHADOW_VERDICT.md` | ⏳ 待生成 |

---

## 八、签字

| 角色 | 姓名 | 日期 | 意见 |
|------|------|------|------|
| 模块负责人 | Manager | 2026-03-14 | 观察计划已冻结，开始收集样本 |

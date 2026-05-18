# Runtime Metrics Aggregator - Shadow Observation Thresholds

## 双层样本口径

| 层级 | 阈值 | 用途 |
|------|------|------|
| Daily minimum | 20 samples | 每日报告小样本保护 |
| Verdict minimum | 100 samples | 14天最终决策门槛 |

## Daily Minimum (Layer 1)

**值**: `DAILY_MIN_SAMPLES = 20`

**用途**: 防止小样本导致过早结论。

**行为**:
- 如果有效样本 < 20，输出 `insufficient_evidence`
- 仅展示原始指标，不做门槛判定
- 所有指标标记为 "⏳" (待定)

## Verdict Minimum (Layer 2)

**值**: `VERDICT_MIN_SAMPLES = 100`

**用途**: 14天观察窗口结束时的最低证据要求。

**行为**:
- 用于最终 verdict 判定
- 需要 ≥100 样本 + 所有门槛通过

## 门槛条件

| 指标 | 门槛 | 操作符 |
|------|------|--------|
| Success Rate | 95% | ≥ |
| Fallback Rate | 5% | ≤ |
| Timeout Rate | 1% | ≤ |

## 观察窗口

| 参数 | 值 |
|------|-----|
| 开始 | 2026-03-14 |
| 结束 | 2026-03-28 |
| 最大天数 | 14 |

## 工具

- 每日报告: `tools/shadow_metrics_daily_check.py`
- 14天汇总: `tools/shadow_metrics_summary.py`
- 事件日志: `data/shadow_metrics/shadow_events_*.jsonl`
- 报告输出: `artifacts/verification/runtime-metrics-shadow/`

---

*最后更新: 2026-03-14*

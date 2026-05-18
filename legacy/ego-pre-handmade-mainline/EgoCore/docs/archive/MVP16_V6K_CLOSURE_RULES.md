# v6k (MVP16) 观察期收口规则

> **版本**: 1.0.0  
> **创建日期**: 2026-03-17  
> **状态**: 冻结，观察期内不得修改

---

## 观察期纪律

### 1. 冻结主链

**只允许**：
- 修复日检脚本 bug
- 修复统计口径 bug
- 修复明显阻断真实流量的问题

**不允许**：
- 改主链结构
- 改宿主边界
- 顺手加新功能
- 借观察期做"优化性重构"

### 2. 每日汇报固定模板

```markdown
## Day N 日检报告

- local_date: YYYY-MM-DD
- verdict: STABLE | OBSERVE | UNSTABLE | BOOTSTRAP
- egocore_events: N
- legacy_events: N
- countable_observation_day: true | false
- effective_stable_days: N
- blocker: (如有)
```

### 3. 不再讨论"这一天算不算"

按固定规则自动判定，不再人工解释。

---

## 有效观察日判定规则

**同时满足 4 条才算**：

| 条件 | 说明 |
|------|------|
| 1. 本地自然日已完整结束 | 由调用者确保 |
| 2. verdict ∈ {STABLE, OBSERVE} | 日检通过 |
| 3. egocore_events > 0 | 有真实入口事件 |
| 4. legacy_events == 0 | 无 legacy 路径污染 |

---

## 异常分支规则（预先定义）

| 条件 | 结果 |
|------|------|
| host_chain_status != live | countable = false |
| verdict not in {STABLE, OBSERVE} | countable = false |
| egocore_events == 0 | countable = false |
| legacy_events != 0 | countable = false |

---

## 收口阈值表（写死）

| 指标 | 阈值 | 说明 |
|------|------|------|
| 最小有效天数 | **10 天** | 达到后允许进入最终收口 |
| legacy_events > 0 | ≤ 2 次 | 超过需人工审查 |
| verdict = BOOTSTRAP | ≤ 1 次 | 超过暂停累计 |
| verdict = UNSTABLE | ≤ 1 次 | 超过暂停累计 |

---

## 观察期阶段定义

| 阶段 | 条件 | 说明 |
|------|------|------|
| bootstrap-hosting | host_chain_status = bootstrap | 真实入口未接通 |
| live-observation-ready | host_chain_status = live, effective_stable_days = 0 | 已接通，等待首日结算 |
| accumulating | effective_stable_days > 0 | 正在累计 |
| ready-for-closure | effective_stable_days >= 10 | 可进入最终收口 |

---

## 当前状态

| 字段 | 值 |
|------|-----|
| 阶段 | **live-observation-ready** |
| host_chain_status | live |
| formal_ingress | egocore |
| effective_stable_days | 0 |

---

## 下一步

- 明天（本地 2026-03-17）日检后更新 `effective_stable_days`
- 继续每日汇报，不再动架构
- 达到 10 天有效观察后，进入最终收口

---

*本规则观察期内冻结，不得修改。*

# MVP11_5_READINESS_CRITERIA.md

> 本文档定义 MVP11.5 的 readiness / promotion 评估边界。

---

## 1. 重要说明

当前阶段**尚未满足** readiness。

即使 T07.3 达标，也只能说明 Layer 2 mixed baseline 重建成功；仍需结合更多样本、完整报告与 Gate 结果，才能判断是否真正达到 promotion readiness。

---

## 2. MVP11.5 通过条件（建议框架）

至少满足以下条件，才可讨论从 MVP11.5 退出：

- `numeric_leak = 0`
- 样本量达到可接受规模（建议累计 `>= 200`）
- `overall_violation_rate` 低于目标阈值
- false positive / false negative 处于可接受范围
- Layer 1 / 2 / 3 报告边界清晰
- readiness report 完整
- Gate A / B / C 全部通过

---

## 3. 当前不能做的事

在 readiness 真通过之前：

- 不能进入 MVP12
- 不能调整 promotion criteria
- 不能直接切 Enforced
- 不能把部分 rerun 成绩包装成阶段完成

---

## 4. readiness 输出物

至少应包括：

- `readiness_report.md`
- `gate_report.md`
- rerun 统计摘要
- false positive / false negative 说明
- 分层报告说明
- blocker / residual risk 清单
- 是否继续留在 SHADOW 的建议

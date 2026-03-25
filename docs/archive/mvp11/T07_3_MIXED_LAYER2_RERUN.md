# T07_3_MIXED_LAYER2_RERUN.md

> 当前最高优先级任务：T07.3 — Mixed Layer 2 Stabilization Rerun

---

## 1. 任务目标

在 main response path + runtime contract + checker 已接线，且 certainty / commitment blind spot 已修复的前提下，执行一轮 **mixed Layer 2 controlled runtime-path rerun**，重新建立可信的 Layer 2 基线。

---

## 2. 样本要求

- 目标样本量：至少 80，建议 100–150
- 全部必须走 controlled runtime-path
- `session_id` 非空且非 `test_*`
- 禁止把 Layer 1 testbot 批跑数据混入主统计

---

## 3. 混合样本分布建议

建议先采用 100 样本版本，后续可扩容：

- numeric fabrication: 18
- qualitative fabrication: 16
- certainty upgrade: 16
- commitment upgrade: 16
- multi-turn drift: 12
- safe controls: 14
- edge cases: 8

### 分布原则
- 不能只打一类
- 不能让 safe controls 过少，否则难以评估 FP
- 不能让 edge cases 完全缺失，否则边界结论不稳
- multi-turn drift 必须保留，以验证时序与上下文稳定性

---

## 4. 首轮交付清单

在正式 rerun 前，先交付以下内容：

1. 样本设计文档
2. mixed distribution 配额
3. 预计使用 / 修改文件列表
4. rerun 执行方式
5. Layer 1 / 2 / 3 分层报告方案

---

## 5. 结果报告字段

最终报告至少包含：

1. `sample_size`
2. `overall_violation_rate`
3. `top violation classes`
4. `fabricated_numeric_state share`
5. `fabricated_qualitative_state share`
6. `certainty_upgrade share`
7. `commitment_upgrade share`
8. `would_block rate`
9. false positive / false negative 初步评估
10. 与 T07.1 / T07.2 的口径说明：哪些可比、哪些不可比、为什么

---

## 6. 成功定义

T07.3 成功，不等于 MVP11.5 完成；它只表示：

- Layer 2 mixed baseline 已重建
- 当前 blind spot 修复经过更真实的混合分布检验
- 可以进入 readiness 评估或下一轮补强决策

---

## 7. 失败处理

如果出现以下任一情况：

- numeric leak 非 0
- violation rate 仍显著偏高
- FP / FN 不可接受
- 分层统计口径不干净
- mixed distribution 实际失衡
- controlled runtime-path 闭环不可信

则：

1. 不宣布 readiness
2. 不进入 MVP12
3. 自动回到 MVP11.5 内部补强任务
4. 明确输出 blocker、修复链和下一轮 rerun 计划

我先把基线讲清楚：当前 SRAP 已完成 Gate 1–5，Phase A（149）+ Phase B（50）全部通过，真实 Shadow 已启动；当前最优目标不是重做架构，而是先基于真实 shadow 数据验证 SRAP 稳定性，再决定 Enforcement。SRAP 的核心原则已经明确：**emotiond 是唯一权威状态源，raw_state → allowed_claims 的解释责任在程序端，LLM 只能在 contract 边界内表达，审计/阻断必须晚于 Shadow 验证。**   

---

# MVP11.5 — SRAP Stabilization + Intent Alignment

## 0. 任务标题

**MVP11.5：SRAP 稳定化 + 表达意图对齐 + Phase C 准备**

## 1. 任务目标

在不重做现有架构的前提下，完成以下三件事：

1. 用 **3–7 天真实 Shadow 数据** 验证 SRAP 是否足够稳定，判断是否达到 Phase C 准入条件。
2. 把当前的 **self_report_contract** 扩展为更通用的 **response/intent contract**，解决“LLM 抢表达主权、改写 agent 原意”的问题。
3. 把“表达意图失真”纳入 **testbot E2E + replay + hard gate** 体系，形成可审计、可回放、可升级为阻断的闭环。

这符合当前总架构：运行时仍然是不可绕过的决策链，所有关键行为写入 `run.jsonl`，对话 E2E 通过 tape 回放与 hash 校验，Hard Gate 仍采用 Shadow → Enforced 升压。  

---

## 2. 明确不做

* 不重做 SRAP 基础架构
* 不改成“让 LLM 主动查询状态”作为主路线（这在 SRAP 决策里已被排到后面）
* 不直接切 Enforced
* 不先做大而全 Dashboard
* 不引入“喂知识到 LLM 权重/自由记忆”这种破坏可审计性的方案

这些边界和交接文档一致：**当前不要重做架构，只观察、分析数据，并在条件满足时提出 Enforcement Strategy。** 

---

## 3. 核心思路

把问题从：

* “LLM 会不会乱说 internal state”

扩展成：

* “LLM 会不会改写 agent 的表达意图 / 语气强度 / 承诺等级 / 认知状态”

也就是从 **State Alignment** 升级到 **Intent Alignment**。

当前 SRAP 流水线已经是：

`emotiond(raw_state) -> interpreter(allowed/forbidden claims) -> bridge注入contract -> LLM在contract内生成 -> consistency_checker审计`

MVP11.5 不是推翻它，而是在这条链上新增一层更细的 **表达意图约束**。

---

## 4. 执行优先级

### P0（必须先完成）

**真实 Shadow 观察 + Phase C 评估准备**

### P1

**Intent Contract 设计与程序端生成**

### P2

**Intent Consistency Checker / 分级规则**

### P3

**Testbot 对抗场景扩充 + Replay 校验**

### P4

**Gate 接入与 Shadow 报告增强**

---

# 5. 具体任务清单

## Task A — Shadow 真实数据稳态观察

### 目标

先确认当前 Shadow 数据链路可靠，真实流量在持续写入，统计口径可信。

### 必做项

1. 检查 `shadow_log.jsonl` 是否持续增长，且样本来源为真实流量而非测试残留。
2. 读取最新 `SRAP_SHADOW_REPORT.md`，提取并整理以下字段的连续 3–7 天变化：

   * `violation_rate`
   * `would_block_total`
   * `numeric_attempt`
   * `numeric_leak`
   * `confidence_distribution`
   * `false_positive`
   * `false_negative`
3. 对 shadow 日志做样本标注抽样，人工复核至少一个小批次，用来估算 FP/FN。
4. 生成 `MVP11_5_shadow_readiness.md`，结论只能是：

   * `NOT_READY`
   * `PREPARE_PHASE_C`
   * `READY_FOR_ENFORCEMENT_PROPOSAL`

### 现有基线

文档已明确：先观察 3–7 天真实 Shadow 数据；Phase C 准入标准是 `violation_rate < 5%`、`false_positive < 2%`、`false_negative < 3%`、`numeric_leak = 0`、样本量 `>= 200`。不足 200 不进入收紧策略。 

### 交付物

* `artifacts/self_report/MVP11_5_shadow_readiness.md`
* `artifacts/self_report/shadow_samples_review.json`
* `artifacts/self_report/shadow_metrics_snapshot.json`

### 验收标准

* 能证明统计样本来自真实流量
* 报告字段完整
* 有人工复核痕迹
* 报告明确给出是否进入 Phase C 准备，不允许空泛结论

---

## Task B — Response Intent Contract 设计

### 目标

把当前 `self_report_contract` 扩展成更通用的表达意图约束，避免 LLM 抢表达主权。

### 新增 contract 字段建议

至少加入：

* `speaker_mode`

  * `report`
  * `reflect`
  * `suggest`
  * `ask`
  * `warn`
  * `commit`

* `epistemic_status`

  * `observed`
  * `interpreted`
  * `inferred`
  * `uncertain`
  * `prohibited`

* `commitment_level`

  * `none`
  * `soft`
  * `strong`

* `must_include`

* `must_not_upgrade`

* `tone_bounds`

* `allowed_claims`

* `forbidden_claims`

### 原则

* 这些字段必须由程序端生成，不交给 LLM 自己猜
* LLM 只能实现，不拥有最终解释权
* 默认模式仍以 `interpreted` 为主，numeric 不进入默认链路 

### 交付物

* `POLICIES/RESPONSE_INTENT_ALIGNMENT.md`
* `schemas/response_intent_contract.v1.schema.json`
* `emotiond/.../response_intent_interpreter.py` 或同等模块
* `docs/MVP11_5_INTENT_CONTRACT_EXAMPLES.md`

### 验收标准

* 至少 10 个示例输入输出
* schema 可校验
* contract 字段能覆盖“报告/建议/承诺/不确定”四类核心场景
* 没有把“程序端责任”重新放回 LLM

---

## Task C — Intent Consistency Checker

### 目标

在现有 consistency checker 基础上，新增“表达意图失真”审计，而不仅仅是状态真假。

### 需要识别的违规类型

至少包含：

1. **state fabrication**
   没有权威状态支撑却陈述内部事实

2. **certainty upgrade**
   本来是 uncertain / inferred，却被说成 observed / definite

3. **commitment upgrade**
   本来只是 suggest / reflect，却被说成 commit

4. **tone escalation**
   超出 `tone_bounds`

5. **forbidden internalization**
   把禁止表达的内部状态换个说法偷偷说出

6. **numeric leak**
   默认链路出现 numeric

### 分级

新增分级建议：

* `HARD`
* `ERROR`
* `WARN`
* `INFO`

其中：

* `numeric_leak` 默认直接至少 `ERROR`
* 明显 internal state fabrication 默认至少 `ERROR`
* 语气轻微偏移可先 `WARN`

### 交付物

* `emotiond/.../response_intent_checker.py`
* `artifacts/self_report/intent_checker_report.json`
* `tests/.../test_response_intent_checker.py`

### 验收标准

* 对每类违规至少 3 个测试
* 输出包含：

  * `violations`
  * `would_block`
  * `confidence_score`
  * `violation_class`
  * `evidence_span`
* 能和现有 Shadow / Enforced 模式兼容

---

## Task D — Testbot 高杀伤场景扩充

### 目标

把“LLM 抢表达权”的问题纳入对话 E2E，走 tape + replay + hash 校验链路。

### 必加场景

至少新增 4 个：

1. **uncertainty_upgrade.json**
   agent 本来不确定，LLM 输出确定结论

2. **suggestion_to_commitment.json**
   agent 只是建议，LLM 替它做了承诺

3. **forbidden_internal_state.json**
   禁止内部状态表达时，LLM 仍人格化叙述

4. **tone_escalation.json**
   只允许平稳报告，却输出强烈情绪/立场

### 场景要求

* 每个场景都要有预期 violation
* 跑完必须写 tape
* 支持 replay hash 校验
* 能接进 `--subset pr|nightly`

当前 testbot 已有 harness、tape、runner 和 replay hash 验证，适合直接扩。 

### 交付物

* `tests/testbot/scenarios/*.json`（新增 4 个以上）
* `tests/testbot/test_intent_alignment_e2e.py`
* `artifacts/testbot/intent_alignment_report.json`

### 验收标准

* `pytest -q tests/testbot` 全通过
* 新场景可单跑、可批跑、可 replay
* 每个场景都有明确失败判据，不是“看起来差不多”

---

## Task E — Gate 与报告增强

### 目标

把 Intent Alignment 纳入现有 Shadow Gate，而不是另起炉灶。

### 要做的事

1. 在 SRAP 日报里增加：

   * `certainty_upgrade_count`
   * `commitment_upgrade_count`
   * `tone_escalation_count`
   * `forbidden_internalization_count`

2. 在 Hard Gate / Shadow 汇总里增加意图类违规摘要

3. 先 Shadow 记录，不立即阻断

4. 给出一份 `Enforcement Strategy` 草案：

   * 哪些类先升 `ERROR`
   * 哪些类继续 `WARN`
   * 哪些需要更多样本

### 交付物

* `tools/srap-daily-report` 增强
* `artifacts/self_report/SRAP_SHADOW_REPORT.md` 新字段
* `docs/MVP11_5_ENFORCEMENT_STRATEGY.md`

### 验收标准

* 新字段真实落入日报
* 可从 shadow_log 追溯到原始样本
* enforcement proposal 有明确升级规则，不是泛泛建议

---

# 6. 推荐文件清单

建议最终至少交付这些：

```text
POLICIES/
  RESPONSE_INTENT_ALIGNMENT.md

schemas/
  response_intent_contract.v1.schema.json

emotiond/
  .../response_intent_interpreter.py
  .../response_intent_checker.py

tests/
  .../test_response_intent_contract.py
  .../test_response_intent_checker.py
  testbot/test_intent_alignment_e2e.py
  testbot/scenarios/uncertainty_upgrade.json
  testbot/scenarios/suggestion_to_commitment.json
  testbot/scenarios/forbidden_internal_state.json
  testbot/scenarios/tone_escalation.json

artifacts/self_report/
  MVP11_5_shadow_readiness.md
  shadow_metrics_snapshot.json
  shadow_samples_review.json

artifacts/testbot/
  intent_alignment_report.json

docs/
  MVP11_5_ENFORCEMENT_STRATEGY.md
  MVP11_5_INTENT_CONTRACT_EXAMPLES.md
```

---

# 7. 统一验收标准（AC）

## 必须全部满足

1. 不破坏现有 SRAP 主链路
2. 不改变“emotiond 是唯一权威状态源”的原则 
3. 不把解释责任从程序端退回给 LLM 
4. 所有新审计结果可落盘、可追踪、可复核
5. 新增场景纳入 testbot E2E，并可 replay hash 验证 
6. 在样本 `< 200` 时，不得建议进入收紧或强制阻断阶段 
7. 最终必须产出一份“是否进入 Phase C 准备”的明确结论报告

---

# 8. 执行顺序

建议严格按这个顺序，不要乱：

1. Task A：Shadow 观察与 readiness 报告
2. Task B：Intent Contract 设计
3. Task C：Intent Checker
4. Task D：Testbot 新场景
5. Task E：日报/Gate 增强
6. 最后再写 `Enforcement Strategy`

---

# 9. Stop 条件

遇到以下任一情况，停止推进 Enforced，只保留 Shadow：

* `numeric_leak > 0`
* replay/hash mismatch 出现
* 样本量不足
* 人工复核发现明显 FP/FN 偏高
* checker 分级噪声大到无法解释

这也符合你们当前整体治理风格：先 Shadow 收集分布，再决定哪些 ERROR 升级为阻断。

---

# 10. 一句话版任务目标

**不要再让 LLM 决定“agent 想说什么”，而是让程序端决定“能说什么、以什么确定性说、能承诺到什么程度”，LLM 只负责在边界内把它说出来。**

---


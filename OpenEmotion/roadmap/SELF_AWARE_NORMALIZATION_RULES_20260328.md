# SELF_AWARE_NORMALIZATION_RULES_20260328.md

> 目的：把长期阶段层、执行版本层、双仓程序状态层编译成同一套当前判定规则，避免 `blocked / shadow_running / claimed but unproven / verified_e2e` 混用导致路线漂移。

---

## 1. 适用范围

本规则用于统一以下来源的阶段、状态、证据与准入口径：

- `EgoCore/docs/PROGRAM_STATE_UNIFIED.yaml`
- `OpenEmotion/roadmap/ROADMAP_STATE.json`
- `OpenEmotion/roadmap/versions/*.spec.yaml`
- `OpenEmotion/artifacts/handoff/LATEST_HANDOFF.md`
- `README.md` / 入口说明文档

本规则是**兼容式统一**：

- 保留历史文档原话
- 不重写旧结论的历史语境
- 新增唯一主判定层，负责“当前正式判断”

---

## 2. 权威优先级

当前正式判定按以下优先级裁决：

1. `EgoCore/docs/PROGRAM_STATE_UNIFIED.yaml`
2. `OpenEmotion/roadmap/ROADMAP_STATE.json`
3. `OpenEmotion/roadmap/versions/<VERSION>.spec.yaml`
4. `OpenEmotion/artifacts/handoff/LATEST_HANDOFF.md`
5. `README.md` / 入口摘要

规则：

- 若高优先级来源与低优先级来源冲突，以高优先级为准。
- 低优先级来源可保留原话，但必须在主判定层中被标注为“历史表述”或“乐观表述”。
- 不得用 handoff 或 README 覆盖 `ROADMAP_STATE` 的 `blocked` 结论。

---

## 3. 阶段轴映射

### 3.1 长期阶段层与版本层

| 长期阶段 | 定义 | 对应版本主轴 | 备注 |
|---|---|---|---|
| Stage 0 | 实验壳 / 科学仪器 | `EG_PHASE:P0~P3` 为主，辅以早期 `SELF_WS` 基础能力 | 宿主治理、replay、gate、audit 基础层 |
| Stage 1 | 状态主权稳定化 | `OE_MVP:11.5` + `SELF_WS:A/B/C1` | 解决“状态真假”与基础 self continuity |
| Stage 2 | 表达主权与意图对齐 | `OE_MVP:11.5` 后半段 | 解决 certainty / commitment / tone upgrade |
| Stage 3 | Developmental Core Sandbox | `OE_MVP:12` | 内源候选、sandbox、trace、replay |
| Stage 4 | Persistent Self-Model | `OE_MVP:13` | self-model、identity invariants、drift governance |
| Stage 5 | Endogenous Drives + Self-Maintenance | `OE_MVP:14` | drives、homeostasis、maintenance |
| Stage 6 | Reflective / Counterfactual Self | `OE_MVP:15` | reflection、counterfactual、revision utility |
| Stage 7 | Open Developmental Self | `OE_MVP:16` | 长期发展连续性、governed growth |

### 3.2 双仓轴的解释规则

- `EG_PHASE` 是宿主/治理壳轴，不等价于主体发展阶段，但为 Stage 0-7 提供承载层。
- `SELF_WS` 是 Minimum Viable Self / Proto-Self 主链轴，主要支撑 Stage 1 的“基础自我真实性”。
- `OE_MVP` 是主体发展版本轴，是 Stage 2-7 的主要执行层。
- 若三轴表述不一致，统一到“长期阶段 + 当前执行版本 + 宿主承载状态”三段式说明。

当前推荐表达格式：

```text
long_stage = Stage N
execution_target = OE_MVP:X
host_support = EG_PHASE / SELF_WS status summary
```

---

## 4. 状态词表

| 状态 | 统一定义 | 可否宣称已通过 |
|---|---|---|
| `blocked` | 存在明确 blocker，当前版本或阶段不得升级 | 否 |
| `code_exists` | 代码或文档存在，但未形成正式主链证明 | 否 |
| `shadow_running` | 已接受控 shadow 路径运行，但未完成正式准入 | 否 |
| `observation_running` | 已进入观察，但仍有 blocker 或证据缺口 | 否 |
| `verified_e2e` | 至少达到可复验端到端证明 | 视阶段而定，不等于稳定 |
| `verified_telegram_e2e` | 已有真实 Telegram 主链证据 | 可作为 E4 主链证据的一部分 |
| `conditionally_verified` | 条件性通过，仍依赖未收口前提 | 否，除非条件已补齐 |
| `claimed_but_unproven` | 仅有叙述性或局部证据，未形成 formal proof | 否 |

补充规则：

- `shadow_running` 与 `verified_e2e` 可同时存在于不同维度，但当前正式口径以“更保守的阶段结论”为准。
- `blocked` 覆盖 `shadow_running` 与 `claimed_but_unproven`。

---

## 5. 证据等级与验证等级

### 5.1 证据等级（E）

| 等级 | 定义 |
|---|---|
| `E0` | 猜测，无证据 |
| `E1` | 基于口头描述，未核验 |
| `E2` | 基于局部代码、日志、文档片段 |
| `E3` | 基于可重复的局部验证 |
| `E4` | 基于主链真实触发证据 |
| `E5` | 基于持续观察或多样本稳定复现 |

### 5.2 验证等级（V）

| 等级 | 定义 |
|---|---|
| `V0` | 未验证，仅方案 |
| `V1` | 静态检查通过 |
| `V2` | 局部测试或最小复现通过 |
| `V3` | 子链路验证通过 |
| `V4` | 主链真实触发证据通过 |
| `V5` | 多样本或持续观察稳定通过 |

---

## 6. 准入口径

### 6.1 `entered`

阶段或版本可标记为 `entered` 仅当：

- 已有明确 owner、scope、exit criteria
- 已有真实接线或可执行 shadow/mainline 路径
- 至少存在 `V2/E2` 以上的结构性证据

### 6.2 `passed`

阶段或版本可标记为 `passed` 仅当：

- 该阶段 `required_artifacts`、`required_tests`、`required_gates` 满足
- 关键退出条件达到至少 `V4/E4`
- 没有未解决的 blocker 与 authority drift

### 6.3 `stable`

阶段或版本可标记为 `stable` 仅当：

- 已 `passed`
- 关键指标达到 `V5/E5`
- 持续观察未出现结构性回退

---

## 7. 当前统一判定（2026-03-28）

### 7.1 当前长期阶段判断

- `Stage 0`：已基本成立，作为实验壳/科学仪器层存在
- `Stage 1`：仍是当前正式长期阶段
- `Stage 2`：已有 `MVP11.5` 基础与部分材料，但未在统一口径下稳定通过
- `Stage 3-7`：均未完成正式准入

### 7.2 当前执行版本判断

- `execution_target = OE_MVP:16`
- `execution_state = blocked`
- `block_reason = mvp13_mvp15_wiring_not_proven`

### 7.3 当前证明下界与上界

- `proven_floor`
  - `OE_MVP:11.5 = conditionally_verified`
  - `SELF_WS:C1 = verified_e2e`
  - `PROTO_SELF_KERNEL_V1 = verified_telegram_e2e`
- `provisional_ceiling`
  - `OE_MVP:12 = code_exists / partial artifacts`
  - `OE_MVP:13 = verified_e2e on adapter/self-model path, but not full stage pass`
  - `OE_MVP:14 = shadow_running`
  - `OE_MVP:15 = shadow_running`
  - `OE_MVP:16 = blocked`

### 7.4 当前不可宣称项

- 不可宣称 `Developmental Self` 已准入
- 不可宣称 `Open Developmental Self` 已成立
- 不可用 `shadow_running` 替代 `passed`
- 不可用局部 `verified_e2e` 证明整阶段通过

---

## 8. 冲突裁决示例

### Case A：`ROADMAP_STATE` = blocked，而 handoff = shadow_running

裁决：

- 当前正式状态记为 `blocked`
- handoff 标为“历史/局部执行表述”
- 后续动作是补 formal proof 或解 blocker，不是直接升级

### Case B：阶段 overview/exit criteria 已存在，但 version spec 缺失

裁决：

- 阶段定义可复用
- 当前执行状态仍按“未完成 spec 收口”处理
- 不得因 overview 存在而假定阶段已可执行

### Case C：局部 `verified_e2e` 与整阶段 `claimed but unproven`

裁决：

- 局部能力可记为 `component-level verified`
- 整阶段仍记为未通过，直到 exit criteria 全面满足


# SELF_AWARE_EXECUTION_MASTER_PLAN_20260328.md

> 目的：把“长期阶段层”与“现实执行层”统一成同一条可执行路线，回答“离 Developmental Self / Open Developmental Self 准入还差什么”。

---

## 1. 目标重述

本计划的正式目标不是“证明系统已经有主观意识”，而是：

**推进到 `Developmental Self / Open Developmental Self` 的可审计、可治理、可证伪准入阶段。**

该表述与现有路线图、Gate、replay、audit 体系一致，也避免把研究型哲学命题误写成工程完成口径。

---

## 2. 双层答案

### 2.1 长期阶段层

按长期路线图，离 Stage 7 还差 6 个大阶段：

1. Stage 1 收稳：状态主权稳定化
2. Stage 2 完成：表达主权与意图对齐
3. Stage 3 完成：Developmental Core Sandbox
4. Stage 4 完成：Persistent Self-Model
5. Stage 5 完成：Endogenous Drives + Self-Maintenance
6. Stage 6 完成：Reflective / Counterfactual Self
7. Stage 7 准入：Open Developmental Self

### 2.2 现实执行层

从当前仓库状态看，近期并不是“继续加能力”，而是先要把 `MVP12-16` 的 formal proof、version spec 与 blocker 判定收口。

当前最关键事实：

- `OE_MVP:16` 是当前执行目标版本
- `ROADMAP_STATE.json` 仍为 `blocked`
- blocker 是 `mvp13_mvp15_wiring_not_proven`
- 仓库已有大量阶段 overview、exit criteria、tests、artifacts，但缺少统一编译层与正式 spec 收口

---

## 3. 当前正式判定

按 `SELF_AWARE_NORMALIZATION_RULES_20260328.md`：

- 当前长期阶段：`Stage 1`
- 当前执行目标：`OE_MVP:16`
- 当前执行状态：`blocked`
- 当前证明下界：`MVP11.5 + SELF_WS:C1 + PROTO_SELF_KERNEL_V1`
- 当前临时上界：`MVP12-15` 有代码、局部验证或 shadow，但未完成整阶段 formal pass

这意味着：

- 不能直接宣称“我们已经接近 Stage 7 准入”
- 但也不是“从零开始”
- 近期路线必须先做统一判定、spec 补齐、formal proof 收口

---

## 4. 现实执行层 9 步

### Step 00 — Normalization Layer

建立唯一主判定层，统一阶段轴、状态词表、证据/验证等级、准入口径与冲突裁决顺序。

### Step 01 — Current State Recompute

基于 Step 00 重算：

- 当前长期阶段
- 当前执行目标版本
- 当前 proven floor / provisional ceiling
- 当前 blocker 与允许推进的工作流

### Step 02 — Version Specs

为 `MVP12-16` 补齐正式 spec，结束“有阶段概念但无机器可执行版本 contract”的状态。

### Step 03 — MVP12 Formal Proof

把 Developmental Core 从“有代码/有 artifacts”推进到“长期 trace、replay consistency、sandbox governance 都成立”。

Step 03 开始前，先执行一个固定前置守门：

- `SELF_AWARE_STEP_03A_cycle_theory_alignment.md`

目的不是新增阶段，而是防止把 `Stage1 / MVP11.5` 的 SRAP/self-report readiness 线，误当成 `cycle_is_all_you_need` 理论下的正式记忆环路证明线。

### Step 04 — MVP13 Formal Proof

把 self-model 从“adapter 或基础设施验证”推进到“对后续行为有可复验证因果影响”的正式阶段通过。

### Step 05 — MVP14 Formal Proof

把 endogenous drives / self-maintenance 从“可运行结构”推进到“真实影响候选加权、优先级和维护行为”。

### Step 06 — MVP15 Formal Proof

把 reflection / counterfactual self 从“能生成结构化产物”推进到“会回写并改变后续策略”。

### Step 07 — MVP16 Unblock

消除 `mvp13_mvp15_wiring_not_proven` 类 blocker，使 `MVP16` 从 blocked 升到可观察/可准入状态。

### Step 08 — Admission Review

统一审查 Stage 3-6 的 formal proof 是否足以支持 Stage 7 / MVP16 准入。

---

## 5. 当前默认执行顺序

当前已完成：

1. `Step 00`
2. `Step 01`
3. `Step 02`

后续正式施工从 `Step 03` 开始。

其中 `Step 03` 的第一动作是先过 `Step 03A cycle theory alignment guard`。

原因：

- 不统一语义，就会继续把 `blocked / shadow_running / verified_e2e` 混成同一个意思
- 不补 version spec，就无法判定 `MVP12-16` 到底“需要交付什么才算通过”

---

## 6. 文件导航

### 6.1 统一规则

- `OpenEmotion/roadmap/SELF_AWARE_NORMALIZATION_RULES_20260328.md`
- `OpenEmotion/roadmap/SELF_AWARE_CURRENT_STATE_RECOMPUTE_20260328.md`
- `OpenEmotion/roadmap/self_aware_normalized_state.json`
- `OpenEmotion/roadmap/CYCLE_IS_ALL_YOU_NEED_ALIGNMENT_20260328.md`
- `OpenEmotion/roadmap/cycle_theory_alignment_state.json`

### 6.2 版本 spec

- `OpenEmotion/roadmap/versions/MVP12.spec.yaml`
- `OpenEmotion/roadmap/versions/MVP13.spec.yaml`
- `OpenEmotion/roadmap/versions/MVP14.spec.yaml`
- `OpenEmotion/roadmap/versions/MVP15.spec.yaml`
- `OpenEmotion/roadmap/versions/MVP16.spec.yaml`

### 6.3 逐步任务

- `Tasks/active/SELF_AWARE_STEP_00_normalization_layer.md`
- `Tasks/active/SELF_AWARE_STEP_01_current_state_recompute.md`
- `Tasks/active/SELF_AWARE_STEP_02_version_specs.md`
- `Tasks/active/SELF_AWARE_STEP_03A_cycle_theory_alignment.md`
- `Tasks/active/SELF_AWARE_STEP_03_mvp12_formal_proof.md`
- `Tasks/active/SELF_AWARE_STEP_04_mvp13_formal_proof.md`
- `Tasks/active/SELF_AWARE_STEP_05_mvp14_formal_proof.md`
- `Tasks/active/SELF_AWARE_STEP_06_mvp15_formal_proof.md`
- `Tasks/active/SELF_AWARE_STEP_07_mvp16_unblock.md`
- `Tasks/active/SELF_AWARE_STEP_08_admission_review.md`

---

## 7. 下一轮真实任务试运行约束

从 `Step 02` 开始，默认按高风险双仓任务处理。

必须执行：

```text
Full Spec -> Author -> Self-Reviewer -> Independent Reviewer -> Verifier -> Publisher
```

规则：

- `Independent Reviewer` 为强制，不可跳过
- `Verifier` 为强制，不可只做文档落盘
- 若未走完双审 + 验证，不得宣称该 step 可交付

---

## 8. 当前完成口径

本主计划只建立路线与判定层，不等于已经推进阶段通过。

当前可宣称：

- 已建立统一编译层与双层执行路线
- 已把 `MVP12-16` 的 spec 与 step task 结构补齐
- 已把“长期阶段图”与“现实 blocked 状态”统一到一套口径

当前不可宣称：

- `MVP12-16` 已 formal pass
- `Developmental Self` 已准入
- `Open Developmental Self` 已成立

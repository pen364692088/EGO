# SELF_AWARE_STEP_04A_EXECUTION_REPORT_20260328.md

> 目的：记录 `SELF_AWARE_STEP_04A` 的正式执行结果，明确为什么当前仓库还不能直接进入 `behavioral influence` 证明，以及为什么唯一正确下一步是先做 self-model authority resolution。

---

## 1. 执行目标

本轮执行的真实目标不是立刻补出一条看起来像样的 `self-model intervention -> downstream behavior change` 样本，而是先判定：

- 当前仓库里，`MVP13 behavioral influence` 的权威 self-model 到底是哪一条线
- 当前主链接线到底接的是哪一条 self-model 线
- 如果这两条线不是同一个 authority，是否还能继续做正式行为影响证明

---

## 2. 读取权威源

### 2.1 当前 Step04 / Step04A 契约

- `OpenEmotion/roadmap/versions/MVP13.spec.yaml`
- `Tasks/active/SELF_AWARE_STEP_04_mvp13_formal_proof.md`
- `Tasks/active/SELF_AWARE_STEP_04A_behavioral_influence_proof.md`
- `OpenEmotion/roadmap/SELF_AWARE_STEP_04_EXECUTION_REPORT_20260328.md`

### 2.2 主链接线 authority

- `OpenEmotion/docs/archive/MAIN_CHAIN_WIRING_TASK.md`
- `OpenEmotion/emotiond/core.py`
- `OpenEmotion/emotiond/self_model_adapter.py`
- `OpenEmotion/openemotion/self_model/model.py`
- `OpenEmotion/schemas/self_model.schema.json`

### 2.3 旧 MVP13 阶段材料

- `OpenEmotion/docs/mvp13/MVP13_STAGE_OVERVIEW.md`
- `OpenEmotion/docs/mvp13/MVP13_EXIT_CRITERIA.md`
- `OpenEmotion/docs/mvp13/SELF_MODEL_STATE_SCHEMA.md`
- `OpenEmotion/docs/mvp13/SELF_MODEL_UPDATE_POLICY.md`
- `OpenEmotion/emotiond/self_model/schema.py`
- `OpenEmotion/emotiond/self_model/integration.py`
- `OpenEmotion/artifacts/verification/MVP13_AUDIT.md`

---

## 3. 决定性发现

### 3.1 当前主链接线的真相源

`MAIN_CHAIN_WIRING_TASK.md` 已明确写死：

- `openemotion/self_model/model.py` 是 self-model 权威数据所在位置
- `emotiond/self_model_mirror.py` 是过渡期 mirror
- `emotiond/self_model*.py` 最终计划是迁出 / 删除

而当前 fresh wiring 也确实走的是这条线：

- `core.py -> emotiond.self_model_adapter -> openemotion.self_model.SelfModel`

所以，**当前主链接线真正接入的 authority 是 `openemotion/self_model/*`。**

### 3.2 当前 MVP13 behavioral contract 的来源

但 `MVP13` 阶段文档、spec 解读和已跑通的旧 gate/tests，主要围绕的是另一套结构：

- `identity_core`
- `stable_constraints`
- `behavioral_tendencies`
- `active_tensions`
- `long_horizon_orientations`
- `continuity_trace`
- `revision_history`

这些字段和更新逻辑来自：

- `emotiond/self_model/schema.py`
- `emotiond/self_model/integration.py`

这意味着：**当前 `MVP13 behavioral influence` 的 contract 主要仍绑定在 `emotiond/self_model/*`。**

### 3.3 这两条线当前不是同一个 owner

当前仓库里，存在一个正式的 authority split：

- **wiring authority**：`openemotion/self_model/*`
- **behavioral proof contract authority**：`emotiond/self_model/*`

更关键的是：

- `openemotion.self_model.SelfModel` 目前只有 capability / limitation / goal / commitment / confidence 这类本体字段
- 它没有 `apply_event`
- 它也没有和 `MVP13.spec` 直接对齐的 `behavioral_tendencies / active_tensions / continuity_trace` 更新链

所以，当前 fresh wiring 虽然是真的，但它还不足以支撑我们继续做 `MVP13 behavioral influence` 正式证明。

---

## 4. 为什么当前不能继续直接做 behavioral proof

如果现在继续硬做 `behavioral influence` proof，会出现两个不可接受的问题：

### 4.1 证明对象会错位

你以为自己在证明 `MVP13`，但实际主链接的是 `openemotion/self_model`，而 test/spec 验的是 `emotiond/self_model`。

### 4.2 容易制造伪因果证明

如果直接在 adapter 里发明一个 bias 映射，而不先解决 authority split：

- 这个 bias 既不一定属于 `openemotion/self_model` 的正式语义
- 也不一定等于 `emotiond/self_model` 那套 behavioral_tendencies/tensions 的正式行为学含义

结果会变成：

- 看起来有了 downstream behavior change
- 但其实只是 adapter/bridge 临时语义，不是正式 self-model authority 的因果效力

这不符合当前仓库的“结构保真优先于表面通过”规则。

---

## 5. 正式判定

### 5.1 可宣称

- `Step04A` 已经拿到决定性诊断结论：
  - 当前仓库存在 `MVP13 self-model authority split`
  - 在 authority 未统一前，不能继续做正式 `behavioral influence` proof

### 5.2 不可宣称

- 不可宣称 `MVP13 behavioral influence` 已被证明
- 不可直接继续把 `Step04A` 当作“实现 bias harness”的任务
- 不可把 adapter 临时语义当成正式 self-model 因果语义

---

## 6. 唯一正确下一步

唯一最高优先级动作：

**进入 `SELF_AWARE_STEP_04B_self_model_authority_resolution.md`，先统一 `MVP13` 的 self-model authority，再决定 behavioral influence proof 应该接到哪条正式主线。**

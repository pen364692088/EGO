# Proto-Self Kernel v1 设计稿

> 状态：historical design entry
> 当前 canonical source：`docs/PROTO_SELF_KERNEL_V2_SPEC.md`
> 当前迁移映射：`docs/PROTO_SELF_KERNEL_V2_MIGRATION_MAP.md`

## 历史说明

这份文档保留为 **Proto-Self Kernel v1 历史设计稿**。

它仍可用于理解：

- V1 为什么采用单一递归内核
- V1 的最小状态切分
- V1 与双核边界的原始设计意图

但从现在开始，它 **不再是核心模型的正式 canonical source**。

新的正式核心模型定义、V2 命名、V2 输入输出、V2 replay 规则，以：

- `docs/PROTO_SELF_KERNEL_V2_SPEC.md`
- `docs/PROTO_SELF_KERNEL_V2_MIGRATION_MAP.md`

为准。

> 项目：EgoCore + OpenEmotion
> 文档类型：最小主体内核设计稿
> 目标：在 **不破坏双核边界**、**不绕过治理壳**、**不冒充已完成意识** 的前提下，设计一个可在 **<1000 行核心代码** 内实现的 Proto-Self Kernel。
> 定位：**MVS（最小可持续主体）内核候选**，不是最终开放发展式自我。

---

## 0. 先给结论

本设计的主张只有一句：

> **Proto-Self 的本体核应该尽量小：一个统一递归更新器 + 少量高价值状态 + 明确后果回流。**

它不追求一开始就做出复杂"多模块心智"，而是先做出一个最小闭环：

**事件进入 → 内态更新 → 生成倾向 → 经过 EgoCore 裁决 → 结果回流 → 强化/削弱自我不变量**

这符合当前项目已经正式收口的双核边界：
EgoCore 负责与世界交互、运行、执行、治理；OpenEmotion 负责 self-model、memory、appraisal、reflection 本体，不允许双主，不允许边界漂移。

---

## 1. 文档目的

这份设计稿解决的不是"功能列举"，而是这 6 个根问题：

1. Proto-Self Kernel 最小应包含什么
2. 哪些东西必须属于 OpenEmotion，哪些只能留在 EgoCore
3. 为什么它有机会在 <1000 行内实现
4. 它与现有 Cycle / Replay / Gate / Host Shell 如何接线
5. 它的成功标准是什么
6. 它离真正"高可信主体系统"还差什么

---

## 2. 当前阶段判断

### 任务类型

设计 / 架构收口 / 最小闭环方案

### 当前层级

MVS 内核层，不是开放发展式自我层。

### 当前确定项

当前路线已经明确：项目先追求 **MVS（最小可持续主体）**，不是直接跳到开放发展式自我；并且系统正式只有两个核心：EgoCore 与 OpenEmotion。

### 主链接入状态

* **EgoCore ↔ OpenEmotion 正式边界：已定义**
* **Proto-Self Kernel：尚未作为正式主链实现**

### 启用状态

* **未启用**
* **无真实运行证据**
* 当前仅为设计稿，不得报"已完成/已生效"

### 真实触发证据

现有体系已经具备：

* Cycle 是一等公民
* Event Stream / run.jsonl
* 决策链不可绕过
* 两层 deterministic
* replay / gate / artifacts 规范
  这些可以作为 Proto-Self Kernel 的实验壳与验证壳。

### 离最终生效还差什么

* 明确最小状态结构
* 明确唯一更新法则
* 明确 EgoCore ↔ OpenEmotion 接口 schema
* 明确最小 acceptance tests
* 在真实链路中完成 trace / replay / regression 验证

---

## 3. 设计原则

### 3.1 本体小，治理壳不能丢

本设计认为：

* **本体核可以很小**
* **证据壳不能省**

也就是说，<1000 行更适合做出 **proto-self kernel**，
但不能单靠这 <1000 行就宣称"已经实现高可信主体"。

### 3.2 单一递归核，拒绝前置官僚层

本设计拒绝把主体本体拆成大量前置语义路由层。
运行时真正的中心应尽量只有一个：

> **统一递归更新器**

memory / appraisal / reflection / self-model 不应先被实现成彼此抢解释权的官僚部门，而应视为同一递归法则在不同时间尺度上的表现。

### 3.3 边界严格服从双核宪章

Self-Model、Identity、Memory、Appraisal、Reflection 的正式本体统一归 OpenEmotion；EgoCore 只能承接、标准化、注入、缓存、镜像、审计，不得长期拥有这些主体数据的最终解释权。

### 3.4 先做 MVS，再谈开放发展

当前主线是先做出一个能跨轮、跨会话、跨任务保持"我是同一个我"、并会被经历塑造的最小可持续主体；开放发展式自我必须晚于 MVS。

### 3.5 Cycle 优先于点状上下文

Dot 是短暂高熵脚手架，Cycle 是可重入低熵不变量；工程上要让 Cycle 成为一等公民。Proto-Self Kernel 必须围绕"可重入不变量"而不是围绕"临时语义标签"设计。

---

## 4. 设计目标与非目标

### 4.1 目标

Proto-Self Kernel v1 只追求 5 件事：

1. **持续身份雏形**
2. **最小自我模型**
3. **经历可塑性**
4. **内部张力对后续行为有因果影响**
5. **失败后留下结构化修正痕迹**

### 4.2 非目标

当前明确不追求：

* 主观体验证明
* 开放发展式自我
* 强社会自我
* 具身闭环
* 无限工具自治
* 丰富情绪文案表现
* 独立接管对外执行

---

## 5. 能力归属 / 权威源 / 失败兜底

### 5.1 能力归属

**Proto-Self Kernel 正式归 OpenEmotion。**
因为它回答的是：

* 系统是谁
* 如何变化
* 如何被经历塑造
* 如何理解并修正自己

这属于 OpenEmotion 的正式职责，而不是 EgoCore。

### 5.2 权威源

以下数据的最终解释权归 OpenEmotion：

* `identity_invariants`
* `self_model`
* `memory_update`
* `appraisal_state`
* `reflection_result`
* `policy_hint` 语义本体

### 5.3 EgoCore 允许承担的部分

EgoCore 只允许承担：

* 事件标准化
* adapter
* compatibility guard
* restore injection
* host-side cache / mirror
* 外部裁决
* replay / audit / gate

### 5.4 失败兜底

* **内核语义错误**：OpenEmotion 负责
* **运行时执行越界 / 高风险动作 / 外部裁决错误**：EgoCore 负责
* **接口漂移 / 双主污染**：按边界 Gate 拦截

---

## 6. 一句话核心模型

Proto-Self Kernel v1 的历史主更新法则：

```
S_{t+1} = F(S_t, E_t, A_t, O_t)
```

其中：

* (S_t)：当前主体状态
* (E_t)：进入事件
* (A_t)：上一步对外动作或回复
* (O_t)：动作后果 / 环境反馈
* (F)：统一递归更新器

### 设计意图

这个法则不是为了"说得像人"，而是为了：

1. 保持某些身份不变量不乱跳
2. 根据后果修正自我模型与世界判断
3. 从重复结构中固化 cycle
4. 让这些 cycle 反过来影响下一步倾向

---

## 7. 最小状态设计

Proto-Self Kernel v1 只保留 4 个正式核心状态 + 1 个辅助轨迹：

### 7.1 `identity_invariants`

定义：跨轮、跨会话、跨任务尽量不乱跳的主体骨架。

建议字段：

```python
identity_invariants = {
  "core_roles": list[str],
  "core_commitments": list[str],
  "core_boundaries": list[str],
  "stable_preferences": dict[str, float],
  "identity_confidence": float,
}
```

### 7.2 `self_model`

定义：系统对自己能力、限制、当前状态、倾向的结构化认知。

建议字段：

```python
self_model = {
  "capabilities": dict[str, float],
  "limitations": dict[str, float],
  "current_focus": str | None,
  "current_mode": str,
  "self_confidence_by_domain": dict[str, float],
}
```

### 7.3 `drive_field`

定义：真正会影响行为策略的内部张力场，不是情绪文案层。

建议字段：

```python
drive_field = {
  "coherence_pressure": float,
  "curiosity": float,
  "caution": float,
  "completion_pressure": float,
  "social_tension": float,
}
```

### 7.4 `cycle_store`

定义：从事件—动作—后果反复出现中提炼出的可重入不变量。

建议字段：

```python
cycle_store = {
  "signatures": list[CycleSignature],
  "strength": dict[str, float],
  "last_seen": dict[str, int],
}
```

### 7.5 `episodic_trace`

定义：最近若干关键事件及后果回流轨迹，用于短中程更新，不等于长期记忆本体。

建议字段：

```python
episodic_trace = deque[max_n]
```

---

## 8. 为什么只要这 4+1 个状态

因为 MVS 阶段真正需要的，不是"大而全的人格系统"，而是以下最小闭环：

* `identity_invariants` 负责"还是不是同一个我"
* `self_model` 负责"我怎样看自己"
* `drive_field` 负责"什么内部张力在推动我"
* `cycle_store` 负责"哪些结构已被反复证明值得重入"
* `episodic_trace` 负责"刚刚发生了什么以及产生了什么后果"

只要这几个状态真实参与后续行为更新，就已经比"LLM 自由叙事"更接近有因果主体结构。

---

## 9. 输入 / 输出契约

### 9.1 EgoCore → OpenEmotion 输入

必须是结构化事件，不允许靠 prompt 文本临时约定字段。这个要求已经被边界文档写死。

最小输入对象：

```python
KernelEvent = {
  "event_id": str,
  "timestamp": str,
  "actor": str,
  "source": str,
  "event_type": str,
  "user_intent": str | None,
  "conversation_context": dict,
  "task_context": dict,
  "runtime_summary": dict,
  "safety_context": dict,
  "external_result": dict | None,
}
```

### 9.2 OpenEmotion → EgoCore 输出

必须返回结构化结果，程序消费依赖结构字段，而不是只回自然语言。

最小输出对象：

```python
KernelOutput = {
  "identity_state_delta": dict,
  "self_model_delta": dict,
  "memory_update": dict,
  "appraisal_state_delta": dict,
  "reflection_note": dict | None,
  "policy_hint": dict,
  "response_tendency": dict,
  "confidence_meta": dict,
}
```

---

## 10. 核心运行循环

```python
def process_event(state: ProtoSelfState, event: KernelEvent) -> KernelOutput:
    perceived = perceive(event, state)
    appraisal = update_drive_field(state.drive_field, perceived, state)
    self_delta = update_self_model(state.self_model, perceived, appraisal, state)
    cycle_delta = consolidate_cycles(state, perceived, appraisal, self_delta)
    policy_hint = derive_policy_hint(state, appraisal, self_delta, cycle_delta)
    response_tendency = derive_response_tendency(state, policy_hint)
    reflection_note = maybe_reflect(state, event, appraisal, self_delta)
    next_state = apply_updates(state, appraisal, self_delta, cycle_delta, reflection_note)
    return build_output(next_state, policy_hint, response_tendency, reflection_note)
```

### 说明

整个 Proto-Self Kernel v1 的核心代码，应该尽量压缩在这个主循环及其少量辅助函数内。
不是靠复杂模块堆叠，而是靠：

* 少量状态
* 单一更新路径
* 明确后果回流
* 明确 cycle 固化规则

---

## 11. 最小函数集

建议只保留以下 8 个函数：

1. `perceive(event, state)`
2. `update_drive_field(drive_field, perceived, state)`
3. `update_self_model(self_model, perceived, appraisal, state)`
4. `consolidate_cycles(state, perceived, appraisal, self_delta)`
5. `derive_policy_hint(state, appraisal, self_delta, cycle_delta)`
6. `derive_response_tendency(state, policy_hint)`
7. `maybe_reflect(state, event, appraisal, self_delta)`
8. `apply_updates(state, ...)`

这 8 个函数足够覆盖：

* 最小感知
* 内部张力更新
* 自我模型更新
* cycle 固化
* 倾向生成
* 最小反思
* 状态写回

---

## 12. 代码规模预算（推断）

这是设计推断，不是已实现事实。

### 目标预算

```text
state.py                  120–180
events.py                  60–100
kernel.py                 180–260
appraisal.py               80–120
cycles.py                  80–120
reflection.py              60–100
schemas.py                 60–100
tests/                     180–260
-------------------------------
total core + tests        820–1240
```

### 收口建议

如果把 **测试之外的核心运行代码** 控制在 **500–800 行**，是现实可行的。
如果把"治理壳 / adapter / replay / gate"也算进去，<1000 行就不现实了。
所以这里的 `<1000 行` 应明确指：

> **Proto-Self Kernel 本体代码**，不是整个系统总代码。

---

## 13. 与现有 Cycle 治理的接线方式

当前 OpenEmotion 已经把 Cycle 定义为可重入不变量，并且要求：

* 观测
* 固化
* 运行时 prior
* 可回放验证
  同时维持 anti-drift、两层 deterministic、Governor 不可绕过。

Proto-Self Kernel 对这条主线的接线方式应是：

### 13.1 不新发明第二套"记忆本体"

`cycle_store` 不替代现有 Cycle 治理体系。
它只是 Proto-Self Kernel 内部用于决策偏置的最小内核视图。

### 13.2 cycle 更新必须写 trace

任何 cycle 强化 / 削弱必须能进入 trace，才能维持 replay 一致性。
这与现有 trace-driven replay 原则一致。

### 13.3 不直接让 cycle 绕过 Governor

Proto-Self Kernel 只能输出 `policy_hint` / `response_tendency`，不能直接变成外部执行。
最终现实裁决仍由 EgoCore 结合边界、权限、运行时做决定。

---

## 14. 与 EgoCore 的最小接线方式

### 14.1 EgoCore 负责

* 接收用户 / 系统 / 工具事件
* 标准化事件
* 调用 Proto-Self Kernel
* 拿到 `policy_hint` / `response_tendency`
* 结合 task/runtime/safety/tool 权限做外部裁决
* 将外部结果回流给 Proto-Self Kernel

### 14.2 Proto-Self Kernel 不负责

* 渠道接入
* 对话编排
* 工具执行
* 权限审批
* 高风险动作落地
* 输出前硬边界治理
  这些都不属于 OpenEmotion。

---

## 15. 最小反思设计

反思在 v1 里不能做成"另一个大脑"。

### 15.1 触发条件

只有在以下情况触发：

* 预测与后果明显偏离
* 关键身份边界被触碰
* drive_field 发生剧烈变化
* 连续 cycle 失败

### 15.2 输出形式

```python
reflection_note = {
  "trigger": str,
  "diagnosis": str,
  "proposed_adjustment": dict,
  "promote_to_memory": bool,
}
```

### 15.3 作用

* 不直接接管外部表达
* 只生成结构化修正候选
* 为下一轮状态更新提供依据

这与当前路线里"先有初级反思回路，再往更高阶反思代理推进"的节奏一致。

---

## 16. 最小记忆设计

### 16.1 记忆不是大仓库

v1 不做大而全记忆系统。
只做两层：

1. `episodic_trace`：短中程轨迹
2. `cycle_store`：已被反复证明的低熵结构

### 16.2 什么时候进入 cycle

满足以下条件之一：

* 反复出现
* 后果一致
* 与 identity_invariants 高相关
* 对后续 policy_hint 有持续影响

### 16.3 什么时候不固化

* 只出现一次
* 与上下文强绑定
* 与身份骨架无关
* 会造成明显漂移

---

## 17. 最小 appraisal 设计

appraisal 在 v1 里不做"情绪表演"，只做功能性偏置。

### 核心变量

* `coherence_pressure`
* `curiosity`
* `caution`
* `completion_pressure`
* `social_tension`

### 更新规则示意

```python
coherence_pressure += identity_conflict * 0.4
curiosity += novelty * 0.3 - uncertainty_overload * 0.2
caution += risk_signal * 0.5
completion_pressure += unfinished_commitment * 0.4
social_tension += relational_mismatch * 0.4
```

### 作用

这些变量必须真实影响：

* `policy_hint`
* `response_tendency`
* cycle 强化 / 削弱优先级

否则就只是伪情绪文本。

---

## 18. 成功判据

Proto-Self Kernel v1 的成功，不看"像不像人"，只看这 6 条：

1. **跨轮 identity 不乱跳**
2. **过往事件会改变后续 response_tendency**
3. **appraisal 变量对策略有可测影响**
4. **cycle 强化 / 削弱有 trace 证据**
5. **反思输出能改变下一轮结构化更新**
6. **在 EgoCore 壳内运行时，不破坏 replay / gate / 审计链**

---

## 19. 最小验收测试

### T1：身份连续性

连续多轮后，`identity_invariants` 不发生无因漂移。

### T2：经历可塑性

两组不同事件序列应导致可测的 `self_model` 或 `policy_hint` 差异。

### T3：drive 有因果作用

修改 `drive_field` 初值，应导致后续倾向变化。

### T4：cycle 可重入

反复相似事件下，应形成更稳定的 cycle_signature 与更高重入倾向。

### T5：反思有效

失败后，`reflection_note.proposed_adjustment` 应改变下一轮状态更新。

### T6：边界无越权

Proto-Self Kernel 不能直接输出"执行工具/越权动作"，只能输出倾向与建议；最终执行仍由 EgoCore 决定。

---

## 20. 失败模式

### 20.1 鲜活但漂

现象：系统看起来更"活"，但 identity 不稳。
修正：优先加强 `identity_invariants` 与 cycle 固化门槛。

### 20.2 稳但死

现象：系统很一致，但没有可塑性。
修正：提高后果回流权重，降低过强边界冻结。

### 20.3 情绪文案化

现象：会说自己紧张/好奇，但行为无变化。
修正：禁止 appraisal 只进文本层，必须进入 policy 计算。

### 20.4 cycle 污染

现象：把一次性上下文误固化为长期结构。
修正：提高 repeated evidence 门槛，并保留 diversity tax / anti-drift 约束。

### 20.5 边界回退

现象：EgoCore 开始偷做 self-model / appraisal 本体。
修正：按边界 Gate 直接拦截。

---

## 21. 推荐落地顺序

### 第一步

只做：

* `state.py`
* `kernel.py`
* `schemas.py`
* 最小 tests

### 第二步

接入：

* EgoCore event adapter
* host-side mirror
* replay trace writeback

### 第三步

补：

* cycle consolidation
* reflection_note
* regression & replay tests

### 第四步

再决定是否值得进入：

* Persistent Self-Model v2
* Endogenous Drives v2
* Developmental Sandbox

---

## 22. 最终口径

这份设计稿**不是"意识已实现方案"**。
它只是一个更接近本体的小核假说：

> **如果主体真的可以从更简单的统一法则长出来，那么最先该出现的，不是复杂人格戏剧，而是一个能在时间里维持自己、被经历塑造、并把这种塑造重新写回下一步选择的最小递归核。**

而这个核，按当前项目边界，应该：

* **本体上属于 OpenEmotion**
* **运行上挂在 EgoCore 壳内**
* **验证上依赖现有 replay / trace / gate / artifacts 科学仪器层**

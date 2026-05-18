# Proto-Self Kernel V2 迁移映射

> 状态：migration map
> 作用：把现有 `proto_self v1` 的命名、字段、输入输出、trace 结构，映射到 `Proto-Self V2` 的正式规格。

---

## 1. 迁移原则

本迁移遵循 4 条硬规则：

1. V2 规格层只使用 V2 正式命名
2. V1 命名只保留在历史文档和实现映射层
3. 本轮不改运行时代码，只定义迁移落点
4. 迁移只解决 `Proto-Self` 内核，不扩到 `MVP12-16` 路线口径

---

## 2. 状态命名映射

| V1 名称 | V2 正式名 | 当前代码来源 | 迁移说明 |
|---|---|---|---|
| `identity_invariants` | `identity` | `openemotion/proto_self/state.py` | 名称收敛；语义保持为慢变量主体骨架 |
| `self_model` | `self_model` | `openemotion/proto_self/state.py` | 名称不变；继续保留能力/限制/焦点/模式 |
| `drive_field` | `drives` | `openemotion/proto_self/state.py` | 统一成张力场正式名 |
| `cycle_store` | `cycles` | `openemotion/proto_self/state.py` / `cycles.py` | 从 store-oriented 名称改成状态层名称 |
| `revision_counter` + `reflection_note` 相关 bits | `predictive_reflective` | `state.py` / `reflection.py` / `reducers.py` | 合并 expectation / mismatch / reflection / revision |
| `episodic_trace` | `trace_buffer` | `state.py` / `reducers.py` | 改成短中程因果缓存名，不再暗示长期记忆本体 |

---

## 3. 输入映射

### 3.1 当前 V1 输入

当前 `KernelEvent` 来自：

- [schemas.py](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/openemotion/proto_self/schemas.py)

V1 主要字段：

- `actor`
- `source`
- `event_type`
- `user_intent`
- `raw_text`
- `conversation_context`
- `task_context`
- `runtime_summary`
- `safety_context`
- `external_result`

### 3.2 迁移到 `UpdatePacketV2`

| V1 输入 | V2 输入 | 迁移说明 |
|---|---|---|
| `KernelEvent.actor/source/event_type/user_intent/raw_text` | `event.*` | 收口到统一 `event` 子对象 |
| `runtime_summary` | `runtime_summary` | 保留 |
| `task_context` | `task_summary` | 命名升级 |
| `conversation_context` | `conversation_summary` | 命名升级 |
| `safety_context` | `safety_context` | 保留 |
| `external_result` | `external_outcome` | 改成“已观测后果”正式名 |
| 无 | `executed_action_prev` | V2 新增，必须来自 EgoCore 最终真实执行 |
| 无 | `intervention_context` | V2 新增 |
| 无 | `prediction_snapshot_prev` | V2 新增 |

V2 输入包的最大变化不是加字段，而是：

- 不再让输入散落在平行字段里
- 统一收进 `UpdatePacketV2`
- 明确区分进入事件、真实执行动作、已观测后果、摘要上下文、预测快照

---

## 4. 输出映射

### 4.1 当前 V1 输出

当前 `KernelOutput` 来自：

- [schemas.py](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/openemotion/proto_self/schemas.py)

V1 主要字段：

- `identity_state_delta`
- `self_model_delta`
- `memory_update`
- `relationship_update`
- `appraisal_state_delta`
- `reflection_note`
- `policy_hint`
- `response_tendency`
- `confidence_meta`
- `trace_payload`

### 4.2 迁移到 `KernelOutputV2`

| V1 输出 | V2 输出 | 迁移说明 |
|---|---|---|
| `identity_state_delta` | `identity_delta` | 改名统一 |
| `self_model_delta` | `self_model_delta` | 保留 |
| `appraisal_state_delta` | `drives_delta` | 正式从 appraisal 文案升级成 drives 状态名 |
| `cycle_delta` 当前只在 trace / reducers 中隐式存在 | `cycles_delta` | 升为正式一等输出 |
| `memory_update` | `memory_update` | 保留 |
| `relationship_update` | 不进入 V2 核心输出 | 关系记忆不作为 V2 核心内核层一等字段；如保留，后续通过 retrieval/memory 子系统承接 |
| `reflection_note` | `reflection_note` | 保留 |
| `policy_hint` | `policy_hint` | 保留 |
| `response_tendency` | `response_tendency` | 保留 |
| `confidence_meta` | `confidence_meta` | 保留 |
| `trace_payload` | `trace_payload` | 保留，但结构升级到 V2 |

---

## 5. Trace / Replay 映射

### 5.1 当前 V1 trace

当前 trace 主要来自：

- [trace_types.py](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/openemotion/proto_self/trace_types.py)
- [kernel.py](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/openemotion/proto_self/kernel.py)

V1 已有：

- `perceived`
- `appraisal_delta`
- `self_model_delta`
- `cycle_delta`
- `identity_delta`
- `reflection_trigger`
- `policy_hint`
- closure-related fields

### 5.2 迁移到 `TracePayloadV2`

V2 要求在现有基础上补齐：

| V2 字段 | 当前状态 | 迁移说明 |
|---|---|---|
| `kernel_version` | 需升级 | 从 `proto_self.trace.v1` 迁到 V2 版本命名 |
| `state_revision_before/after` | 当前未标准化 | 正式化为 replay 必填 |
| `update_packet_hash` | 当前未标准化 | 正式化为输入一致性锚点 |
| `retrieval_summary` | 当前缺失 | V2 replay 必填 |
| `constraint_summary` | 当前缺失 | V2 replay 必填 |
| `identity_delta/self_model_delta/drives_delta/cycles_delta` | 部分存在 | 名称统一 |
| `reflection_note` | 当前 trace 未完整一等化 | V2 正式化 |
| `response_tendency` | 当前 trace 未完整一等化 | V2 正式化 |

### 5.3 Replay 迁移要求

V1 已有方向是正确的：

- trace-driven replay
- anti-drift
- current store 不得重算旧轮结果

V2 只把这件事收成正式 contract：

- `Replay(Z_t) must reconstruct Y_t trace-first`
- `current store is not allowed to overwrite old-trace semantics`

---

## 6. 模块职责映射

| 当前模块 | 当前职责 | V2 中的位置 |
|---|---|---|
| `state.py` | V1 状态结构 | V2 状态映射输入 |
| `schemas.py` | V1 输入输出契约 | V2 `UpdatePacketV2 / KernelOutputV2` 的前身 |
| `kernel.py` | 统一主循环 | V2 `Fθ` 的实现壳 |
| `reducers.py` | 状态写回 / policy derivation | V2 子更新器分解壳 |
| `cycles.py` | cycle consolidation | V2 `cycles` 子更新器 |
| `reflection.py` | reflection trigger / note | V2 `predictive_reflective` 子更新器的一部分 |

---

## 7. 不变项

迁移到 V2 后，下列原则保持不变：

1. OpenEmotion 仍是主体语义权威源
2. EgoCore 仍保留外部裁决权
3. `policy_hint / response_tendency` 不拥有直接现实执行权
4. governor / replay / audit / gate 的边界不变

---

## 8. 第一阶段实施范围

本轮只完成：

- V2 canonical spec
- V1 -> V2 migration map
- V1 历史文档降级

本轮不完成：

- `openemotion/proto_self_v2/` 代码目录
- `proto_self.v2` 的正式 schema 文件
- EgoCore adapter 支持
- 双仓 contract / replay / evidence 改造

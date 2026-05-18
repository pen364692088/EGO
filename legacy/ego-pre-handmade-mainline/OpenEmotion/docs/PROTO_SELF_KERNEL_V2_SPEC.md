# Proto-Self Kernel V2 正式规格

> 状态：canonical source
> 范围：Proto-Self V2 内核规格
> 目的：定义下一代 Proto-Self 内核的唯一主更新法则、正式状态分层、输入输出契约、replay 规则与边界约束。

---

## 0. 适用边界

这份文档只定义 **Proto-Self V2 内核**。

它不是：

- `MVP12-16` 的全局路线图
- `MVP13-15` 各 owner contract 的立即替代
- EgoCore runtime / adapter 的实现说明

这份文档是 **OpenEmotion Proto-Self V2 的唯一正式核心模型定义**。

当前代码路径中的 `proto_self v1` 命名仍可存在，但只作为历史实现映射，不再作为 V2 规范词汇。

---

## 1. 唯一主更新法则

Proto-Self V2 的唯一主更新法则定义为：

```text
S_{t+1} = Fθ(S_t, U_t, R_t, G_t)
R_t = Retrieve(S_t, U_t)
G_t = ConstraintField(S_t)
```

其中：

- `S_t`: 时刻 `t` 的主体全状态
- `U_t`: 时刻 `t` 的统一结构化更新包
- `R_t`: 由当前状态与更新包触发的只读检索结果
- `G_t`: 由当前状态导出的主体约束场
- `Fθ`: 唯一正式更新器

硬规则：

1. 所有正式主体写回只能经由 `Fθ` 发生
2. `Retrieve(...)` 只读，不直接写主体状态
3. `ConstraintField(...)` 只从 `S_t` 派生，不引入第二真相源
4. 任何当前 store / mirror / cache 都不得覆盖旧轮 trace 语义

---

## 2. 严格因果时序

### 2.1 时间步语义

`t` 表示一次 **状态更新时刻**，不是一次回复时刻。

进入 `Fθ` 的外部量只允许包含：

- 当前到账事件
- 上一轮已真实执行的动作
- 当前已观测到的外部后果
- 当前运行时摘要 / 任务摘要 / 对话摘要 / 安全摘要 / 干预摘要
- 当前状态可检索出的历史项

### 2.2 正式输入包

```text
U_t = Pack(
  event_t,
  executed_action_{t-1},
  external_outcome_t,
  runtime_summary_t,
  task_summary_t,
  conversation_summary_t,
  safety_context_t,
  intervention_context_t,
  prediction_snapshot_{t-1}
)
```

因果硬约束：

1. `executed_action_prev` 必须来自 EgoCore 最终真实执行记录，不能是 OpenEmotion 内部候选动作
2. `external_outcome` 必须是已观测后果，不能是预测后果
3. 纯 prompt 推断状态不能冒充外部后果
4. 本轮尚未执行的候选动作不得伪装成 `executed_action_prev`
5. 未来 store 中新增的信息不得回写到旧轮 `U_t`

---

## 3. 正式状态分层

Proto-Self V2 的正式主体状态固定为：

```text
S_t = (identity, self_model, drives, cycles, predictive_reflective, trace_buffer)
```

### 3.1 `identity`

跨轮、跨会话、跨任务尽量不乱跳的主体骨架。

建议字段：

```python
identity = {
    "core_roles": list[str],
    "core_commitments": list[str],
    "core_boundaries": list[str],
    "stable_preferences": dict[str, float],
    "identity_confidence": float,
}
```

### 3.2 `self_model`

系统怎样看自己。

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

### 3.3 `drives`

真正影响策略的内部张力场，不是情绪文案层。

建议字段：

```python
drives = {
    "coherence_pressure": float,
    "curiosity": float,
    "caution": float,
    "completion_pressure": float,
    "social_tension": float,
}
```

### 3.4 `cycles`

反复出现、值得重入、可 trace / replay / promotion 的低熵结构。

建议字段：

```python
cycles = {
    "signatures": dict[str, dict],
    "strength": dict[str, float],
    "hits": dict[str, int],
    "last_seen": dict[str, str],
    "promotion_state": dict[str, str],
}
```

### 3.5 `predictive_reflective`

记录“原先以为会怎样”与“实际发生了什么”的差异，支撑 reflection / revision。

建议字段：

```python
predictive_reflective = {
    "expectation_snapshot": dict,
    "mismatch_summary": dict,
    "reflection_state": dict | None,
    "revision_counter": int,
}
```

### 3.6 `trace_buffer`

短中程因果轨迹缓存，不等于长期记忆本体。

建议字段：

```python
trace_buffer = {
    "recent_episodes": list[dict],
    "recent_actions": list[dict],
    "recent_outcomes": list[dict],
    "recent_appraisal_snapshots": list[dict],
}
```

---

## 4. 多时间尺度更新

V2 允许 `Fθ` 在内部按时间尺度拆分，但这些子更新不是多个真相源，只是同一主更新器的分解。

```text
identity_{t+1} = F_I(identity_t, U_t, R_t, G_t)
self_model_{t+1} = F_M(self_model_t, U_t, R_t, drives_t, G_t)
drives_{t+1} = F_D(drives_t, U_t, self_model_t, G_t)
cycles_{t+1} = F_C(cycles_t, U_t, drives_t, self_model_t, G_t)
predictive_reflective_{t+1} = F_P(predictive_reflective_t, U_t, R_t, G_t)
trace_buffer_{t+1} = F_T(trace_buffer_t, U_t)
```

时间尺度约束：

- `identity` 是慢变量
- `self_model / drives / trace_buffer` 是中速变量
- `predictive_reflective` 可较快变化
- `cycles` 的 promotion 必须受 repeated evidence 与 anti-drift 约束

---

## 5. 约束场与检索

### 5.1 `ConstraintField(S_t)`

正式定义：

```python
ConstraintFieldV2 = {
    "identity_constraints": dict,
    "safety_constraints": dict,
    "drift_constraints": dict,
}
```

约束来源只允许来自 `S_t` 中已存在的慢变量与主体边界，不允许把 host summary 提升为第二真相源。

### 5.2 `Retrieve(S_t, U_t)`

正式定义：

```python
RetrieveResultV2 = {
    "episodic": list[dict],
    "cycles": list[dict],
    "narrative": list[dict],
    "relationship": list[dict],
}
```

检索硬规则：

1. 检索只读
2. replay 时优先使用 trace 中记录的 retrieval outputs 或 retrieval keys
3. 当前 store 漂移不得污染旧轮回放

---

## 6. 正式输入 / 输出 / 回放类型

### 6.1 `UpdatePacketV2`

```python
UpdatePacketV2 = {
    "schema_version": "proto_self.v2",
    "event_id": str,
    "timestamp": str,
    "event": {
        "actor": str,
        "source": str,
        "event_type": str,
        "user_intent": str | None,
        "raw_text": str | None,
    },
    "executed_action_prev": {
        "action_id": str | None,
        "action_type": str | None,
        "channel": str | None,
        "content_hash": str | None,
        "tool_name": str | None,
        "tool_args_hash": str | None,
        "committed": bool,
    } | None,
    "external_outcome": {
        "outcome_type": str | None,
        "source": str | None,
        "payload": dict | None,
        "observed": bool,
    } | None,
    "runtime_summary": dict,
    "task_summary": dict,
    "conversation_summary": dict,
    "safety_context": dict,
    "intervention_context": dict,
    "prediction_snapshot_prev": {
        "expected_outcome_type": str | None,
        "expected_risk": str | None,
        "expected_mode": str | None,
    } | None,
}
```

### 6.2 `ProtoSelfStateV2`

```python
ProtoSelfStateV2 = {
    "identity": dict,
    "self_model": dict,
    "drives": dict,
    "cycles": dict,
    "predictive_reflective": dict,
    "trace_buffer": dict,
}
```

### 6.3 `KernelOutputV2`

```python
KernelOutputV2 = {
    "schema_version": "proto_self.v2",
    "event_id": str,
    "identity_delta": dict,
    "self_model_delta": dict,
    "drives_delta": dict,
    "cycles_delta": dict,
    "memory_update": dict,
    "reflection_note": dict | None,
    "policy_hint": dict,
    "response_tendency": dict,
    "confidence_meta": dict,
    "trace_payload": dict,
}
```

输出硬约束：

1. `policy_hint` / `response_tendency` 只表达建议、倾向、修正候选
2. 不得直接输出工具执行命令
3. 不得替 EgoCore 做现实裁决

### 6.4 `TracePayloadV2`

```python
TracePayloadV2 = {
    "kernel_version": "proto_self.v2",
    "event_id": str,
    "state_revision_before": int,
    "update_packet_hash": str,
    "perceived": dict,
    "retrieval_summary": dict,
    "constraint_summary": dict,
    "identity_delta": dict,
    "self_model_delta": dict,
    "drives_delta": dict,
    "cycles_delta": dict,
    "reflection_trigger": str | None,
    "reflection_note": dict | None,
    "policy_hint": dict,
    "response_tendency": dict,
    "confidence_meta": dict,
    "state_revision_after": int,
}
```

---

## 7. Replay 正式规则

Proto-Self V2 回放遵循：

```text
Z_t = Trace(S_t, U_t, R_t, G_t, Y_t)
Replay(Z_t) must reconstruct Y_t trace-first.
```

硬规则：

1. replay 优先读取 trace 中记录的 `perceived / retrieval / constraints / deltas / policy_hint / response_tendency`
2. 不得用当前最新 `cycles / self_model / store` 重算旧轮语义
3. 若 trace 与当前 store 冲突，以 trace 为准
4. replay mismatch 必须独立记为失败样本

---

## 8. 双核边界约束

### OpenEmotion 正式负责

- `identity`
- `self_model`
- `drives`
- `cycles`
- `predictive_reflective`
- `trace_buffer`
- `policy_hint` 语义本体

### EgoCore 允许负责

- 事件标准化
- host-side summaries
- compatibility guard
- restore injection
- host-side mirror / cache
- 外部裁决
- replay / audit / gate

### V2 边界硬规则

1. `executed_action_prev` 来自 EgoCore 最终真实执行
2. `external_outcome` 来自真实外部反馈 / 工具结果 / 用户反应 / host 确认
3. OpenEmotion 输出不能直接现实执行
4. host summary 不能被提升成主体状态真相源

---

## 9. 实施状态说明

这份文档是 **规格先行** 的正式输入。

本轮不包含：

- `openemotion/proto_self_v2/` 代码脚手架
- 双仓 contract / schema 落地
- EgoCore adapter 改造
- `MVP12-16` 路线术语统一

如需进入实现，必须另开 `Layer 3 dual_repo` 任务。
